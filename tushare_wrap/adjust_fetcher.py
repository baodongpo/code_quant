"""
tushare_wrap/adjust_fetcher.py — 美股复权因子拉取

TuShare us_adjfactor 接口需要独立权限（2000元/年），120积分试用用户无法访问。

方案B：从 us_daily 的 close/pre_close 近似计算复权因子
- 累计复权因子 = close / latest_close（以最新收盘价为基准）
- 前复权价格 = 原始价格 × 累计复权因子

注意：此方案为近似计算，对于分红/拆股事件的复权精度略低于官方接口，
但对于个人投资分析场景已足够使用。
"""

import logging
from datetime import date
from typing import List

from config.settings import DEFAULT_HISTORY_START
from models.kline import AdjustFactor
from tushare_wrap.client import TuShareClient

logger = logging.getLogger(__name__)


class TuShareAdjustFetcher:
    """
    美股复权因子拉取器。

    由于 120积分试用用户无 us_adjfactor 接口权限，
    采用方案B：从 us_daily 的 close/pre_close 近似计算复权因子。
    """

    def __init__(self, client: TuShareClient):
        self._client = client

    def fetch_factors(self, stock_code: str) -> List[AdjustFactor]:
        """
        从 us_daily 数据近似计算复权因子。

        Args:
            stock_code: 股票代码，如 US.AAPL

        Returns:
            按 ex_date 升序排列的 AdjustFactor 列表
        """
        # 转换股票代码格式：US.AAPL → AAPL
        ts_code = stock_code.split(".", 1)[1] if "." in stock_code else stock_code

        logger.info(
            "[%s] TuShare computing adjust factors from us_daily: ts_code=%s",
            stock_code, ts_code,
        )

        # 从 us_daily 获取日线数据（用于计算复权因子）
        # 请求间隔 + 滑动窗口限频
        self._client.wait_rate_limit()

        try:
            df = self._client.pro.us_daily(
                ts_code=ts_code,
                start_date="20000101",  # 获取全历史
                end_date=date.today().strftime("%Y%m%d"),
            )
        except Exception as e:
            logger.error(
                "TuShare us_daily request failed for %s: %s",
                stock_code, e,
            )
            raise RuntimeError(f"TuShare us_daily request failed: {e}") from e

        if df is None or df.empty:
            logger.info(
                "[%s] TuShare us_daily response: 0 rows (empty)",
                stock_code,
            )
            return []

        factors = self._compute_factors_from_daily(stock_code, df)

        logger.info(
            "[%s] TuShare computed %d adjust factors from us_daily",
            stock_code, len(factors),
        )

        return factors

    @staticmethod
    def _compute_factors_from_daily(stock_code: str, df) -> List[AdjustFactor]:
        """
        从日线数据近似计算复权因子。

        计算方法：
        1. 以最新收盘价为基准（累计复权因子 = 1.0）
        2. 向前计算每日累计复权因子 = close / latest_close
        3. 仅在有除权事件（close/pre_close 异常跳变）时生成复权因子记录

        这样计算的前复权价格 = 原始价格 × 累计复权因子
        """
        # 按日期排序
        df = df.sort_values("trade_date", ascending=True)

        # 解析数据
        records = []
        for _, row in df.iterrows():
            try:
                trade_date_raw = str(row["trade_date"])
                trade_date = f"{trade_date_raw[:4]}-{trade_date_raw[4:6]}-{trade_date_raw[6:8]}"
                close = float(row["close"])
                pre_close = float(row.get("pre_close", close)) if row.get("pre_close") else close
                records.append({
                    "trade_date": trade_date,
                    "close": close,
                    "pre_close": pre_close,
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse TuShare daily row: %s, error: %s",
                    dict(row) if hasattr(row, "__iter__") else str(row), e,
                )

        if not records:
            return []

        # 获取最新收盘价作为基准
        latest_close = records[-1]["close"]

        # 计算累计复权因子
        # 从最新日向前计算：每日的累计复权因子 = close / latest_close
        factors = []
        cumulative_factor = 1.0

        # 逆向遍历，从最新日向前
        for i in range(len(records) - 1, -1, -1):
            record = records[i]
            current_close = record["close"]
            current_pre_close = record["pre_close"]

            # 计算当日复权因子（相对最新日）
            # 累计复权因子 = close / latest_close
            daily_factor = current_close / latest_close if latest_close != 0 else 1.0

            # 检测除权事件：close/pre_close 跳变超过正常涨跌幅范围
            # 美股单日涨跌幅通常不超过 50%，超过则可能有除权事件
            if i > 0:
                prev_record = records[i - 1]
                prev_close = prev_record["close"]
                # 正常情况：pre_close 应该等于前一日的 close
                # 除权时：pre_close != 前一日 close
                if prev_close != 0:
                    gap_ratio = abs(current_pre_close - prev_close) / prev_close
                    if gap_ratio > 0.1:  # 超过 10% 的跳变，可能是除权事件
                        # 记录除权日
                        forward_factor = round(daily_factor, 10)
                        backward_factor = round(1.0 / daily_factor, 10) if daily_factor != 0 else 0.0

                        factors.append(AdjustFactor(
                            stock_code=stock_code,
                            ex_date=record["trade_date"],
                            forward_factor=forward_factor,
                            forward_factor_b=0.0,
                            backward_factor=backward_factor,
                            backward_factor_b=0.0,
                            factor_source="tushare_approx",
                        ))

            cumulative_factor = daily_factor

        # 如果没有任何除权事件记录，添加一条基准记录
        if not factors:
            factors.append(AdjustFactor(
                stock_code=stock_code,
                ex_date=records[-1]["trade_date"],  # 最新日
                forward_factor=1.0,
                forward_factor_b=0.0,
                backward_factor=1.0,
                backward_factor_b=0.0,
                factor_source="tushare_approx",
            ))

        # 按日期升序排列
        factors.sort(key=lambda f: f.ex_date)
        return factors
