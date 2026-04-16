"""
akshare_wrap/kline_fetcher.py — 美股K线数据拉取

AkShare 使用 stock_us_daily 接口获取美股历史K线。
支持前复权（adjust='qfq'），数据源为东方财富。

接口签名兼容 tushare_wrap/kline_fetcher.py 的 TuShareKlineFetcher。

AkShare stock_us_daily 接口：
  - 输入：symbol（如 AAPL）、adjust
  - 输出：date, open, high, low, close, volume（英文列名）
  - 无需 Token，完全免费
  - 数据按日期升序排列
"""

import logging
from typing import List, Tuple

import pandas as pd

from models.kline import KlineBar, AdjustFactor
from akshare_wrap.client import AkShareClient

logger = logging.getLogger(__name__)


class AkShareKlineFetcher:
    """
    美股K线数据拉取器。
    - 使用 AkShare stock_us_daily 接口拉取日K线
    - 仅支持日K（period="1D"），不支持周K和月K
    - 内置请求间隔控制 + 滑动窗口限频
    - 支持前复权（adjust='qfq'）
    """

    # AkShare 美股仅支持日K
    SUPPORTED_PERIODS = ["1D"]

    def __init__(self, client: AkShareClient):
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
                f"AkShare US stock only supports daily K-line. "
                f"Requested period: {period}, supported: {self.SUPPORTED_PERIODS}"
            )

        # 转换股票代码格式：US.AAPL → AAPL
        symbol = stock_code.split(".", 1)[1] if "." in stock_code else stock_code

        logger.info(
            "[%s][%s] AkShare stock_us_daily request: symbol=%s, start=%s, end=%s",
            stock_code, period, symbol, start_date, end_date,
        )

        # 请求间隔 + 滑动窗口限频
        self._client.wait_rate_limit()

        try:
            import akshare as ak
            df = ak.stock_us_daily(
                symbol=symbol,
                adjust="qfq",  # 前复权
            )
        except Exception as e:
            logger.error(
                "AkShare stock_us_daily request failed for %s: %s",
                stock_code, e,
            )
            raise RuntimeError(f"AkShare stock_us_daily request failed: {e}") from e

        if df is None or df.empty:
            logger.info(
                "[%s][%s] AkShare stock_us_daily response: 0 bars (empty)",
                stock_code, period,
            )
            return []

        bars = self._parse_dataframe(stock_code, period, df, start_date, end_date)

        if bars:
            logger.info(
                "[%s][%s] AkShare stock_us_daily response: %d bars, first=%s, last=%s",
                stock_code, period, len(bars),
                bars[0].trade_date, bars[-1].trade_date,
            )
        else:
            logger.info(
                "[%s][%s] AkShare stock_us_daily response: 0 bars (filtered or parse error)",
                stock_code, period,
            )

        return bars

    @staticmethod
    def _parse_dataframe(
        stock_code: str,
        period: str,
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
    ) -> List[KlineBar]:
        """将 AkShare stock_us_daily 返回的 DataFrame 解析为 KlineBar 列表。
        
        列名映射（英文）：
          - date → trade_date
          - open, high, low, close, volume → 直接使用
        """
        bars = []

        for _, row in df.iterrows():
            try:
                # 日期格式：YYYY-MM-DD（可能是 datetime 或字符串）
                trade_date_val = row["date"]
                if hasattr(trade_date_val, 'strftime'):
                    trade_date = trade_date_val.strftime("%Y-%m-%d")
                else:
                    trade_date = str(trade_date_val)[:10]  # 取前10位 YYYY-MM-DD

                # 日期过滤
                if trade_date < start_date or trade_date > end_date:
                    continue

                bar = KlineBar(
                    stock_code=stock_code,
                    period=period,
                    trade_date=trade_date,
                    open=round(float(row["open"]), 4),
                    high=round(float(row["high"]), 4),
                    low=round(float(row["low"]), 4),
                    close=round(float(row["close"]), 4),
                    volume=int(row["volume"]) if row["volume"] else 0,
                    turnover=None,  # AkShare 不提供成交额
                    pe_ratio=None,
                    pb_ratio=None,
                    ps_ratio=None,
                    turnover_rate=None,
                    last_close=None,
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse AkShare bar row: %s, error: %s",
                    dict(row) if hasattr(row, "__iter__") else str(row), e,
                )

        # stock_us_daily 返回的数据已按日期升序，无需反转
        return bars

    def fetch_with_factors(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> Tuple[List[KlineBar], List[AdjustFactor]]:
        """
        拉取K线数据并计算复权因子。

        AkShare 使用 adjust='qfq' 直接返回前复权价格，
        复权因子可以从原始价格与前复权价格的比值反推。

        注意：AkShare 不提供原始价格，只提供前复权价格。
        因此，复权因子记录为基准值 1.0，实际复权已在数据层面完成。

        Args:
            stock_code: 股票代码，如 US.AAPL
            period: K线周期，仅支持 "1D"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            Tuple[List[KlineBar], List[AdjustFactor]]
        """
        bars = self.fetch(stock_code, period, start_date, end_date)

        if not bars:
            return bars, []

        # 创建基准复权因子记录（factor=1.0）
        # 因为 AkShare 已返回前复权价格，无需额外计算
        factors = [
            AdjustFactor(
                stock_code=stock_code,
                ex_date=bars[-1].trade_date,  # 最新日期
                forward_factor=1.0,
                forward_factor_b=0.0,
                backward_factor=1.0,
                backward_factor_b=0.0,
                factor_source="akshare_qfq",
            )
        ]

        return bars, factors
