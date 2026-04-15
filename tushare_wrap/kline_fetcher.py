"""
tushare_wrap/kline_fetcher.py — 美股K线数据拉取

TuShare 美股数据仅支持日K线（us_daily），不支持周K和月K。
接口签名兼容 yfinance_wrap/kline_fetcher.py 的 YFinanceKlineFetcher。

TuShare us_daily 接口：
  - 输入：ts_code（如 AAPL）、start_date、end_date
  - 输出：open, high, low, close, vol, pe, pb, total_mv 等
  - 单次限量：6000行
  - 权限：120积分可试用
"""

import logging
from datetime import date, timedelta
from typing import List

from models.kline import KlineBar
from tushare_wrap.client import TuShareClient

logger = logging.getLogger(__name__)


class TuShareKlineFetcher:
    """
    美股K线数据拉取器。
    - 使用 TuShare us_daily 接口拉取日K线
    - 仅支持日K（period="1D"），不支持周K和月K
    - 内置请求间隔控制 + 滑动窗口限频
    """

    # TuShare 美股仅支持日K
    SUPPORTED_PERIODS = ["1D"]

    def __init__(self, client: TuShareClient):
        self._client = client

    def fetch(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> List[KlineBar]:
        """
        拉取指定股票、周期、日期范围的历史K线。

        Args:
            stock_code: 股票代码，如 US.AAPL
            period: K线周期，仅支持 "1D"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            List[KlineBar]，按 trade_date 升序
        """
        if period not in self.SUPPORTED_PERIODS:
            raise ValueError(
                f"TuShare US stock only supports daily K-line. "
                f"Requested period: {period}, supported: {self.SUPPORTED_PERIODS}"
            )

        # 转换股票代码格式：US.AAPL → AAPL
        ts_code = stock_code.split(".", 1)[1] if "." in stock_code else stock_code

        # 转换日期格式：YYYY-MM-DD → YYYYMMDD
        start_date_num = start_date.replace("-", "")
        end_date_num = end_date.replace("-", "")

        logger.info(
            "[%s][%s] TuShare us_daily request: ts_code=%s, start=%s, end=%s",
            stock_code, period, ts_code, start_date_num, end_date_num,
        )

        # 请求间隔 + 滑动窗口限频
        self._client.wait_rate_limit()

        try:
            df = self._client.pro.us_daily(
                ts_code=ts_code,
                start_date=start_date_num,
                end_date=end_date_num,
            )
        except Exception as e:
            logger.error(
                "TuShare us_daily request failed for %s: %s",
                stock_code, e,
            )
            raise RuntimeError(f"TuShare us_daily request failed: {e}") from e

        if df is None or df.empty:
            logger.info(
                "[%s][%s] TuShare us_daily response: 0 bars (empty)",
                stock_code, period,
            )
            return []

        bars = self._parse_dataframe(stock_code, period, df)

        if bars:
            logger.info(
                "[%s][%s] TuShare us_daily response: %d bars, first=%s, last=%s",
                stock_code, period, len(bars),
                bars[0].trade_date, bars[-1].trade_date,
            )
        else:
            logger.info(
                "[%s][%s] TuShare us_daily response: 0 bars (parse error)",
                stock_code, period,
            )

        return bars

    @staticmethod
    def _parse_dataframe(stock_code: str, period: str, df) -> List[KlineBar]:
        """将 TuShare us_daily 返回的 DataFrame 解析为 KlineBar 列表。"""
        bars = []

        # TuShare 返回的日期格式：YYYYMMDD
        for _, row in df.iterrows():
            try:
                trade_date_raw = str(row["trade_date"])
                trade_date = f"{trade_date_raw[:4]}-{trade_date_raw[4:6]}-{trade_date_raw[6:8]}"

                # TuShare 字段映射
                # vol → volume（股），amount → turnover（美元）
                # pe, pb, total_mv, turnover_ratio 为估值指标
                bar = KlineBar(
                    stock_code=stock_code,
                    period=period,
                    trade_date=trade_date,
                    open=round(float(row["open"]), 4),
                    high=round(float(row["high"]), 4),
                    low=round(float(row["low"]), 4),
                    close=round(float(row["close"]), 4),
                    volume=int(row["vol"]) if row["vol"] else 0,
                    turnover=float(row["amount"]) if row.get("amount") else 0.0,
                    pe_ratio=float(row["pe"]) if row.get("pe") else None,
                    pb_ratio=float(row["pb"]) if row.get("pb") else None,
                    ps_ratio=None,  # TuShare us_daily 不提供 PS
                    turnover_rate=float(row["turnover_ratio"]) if row.get("turnover_ratio") else None,
                    last_close=float(row["pre_close"]) if row.get("pre_close") else None,
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse TuShare bar row: %s, error: %s",
                    dict(row) if hasattr(row, "__iter__") else str(row), e,
                )

        # TuShare 返回的数据按日期降序，需要反转
        bars.reverse()
        return bars
