"""
yfinance_wrap/kline_fetcher.py — 美股K线数据拉取

接口签名兼容 futu_wrap/kline_fetcher.py 的 KlineFetcher.fetch()。
使用 auto_adjust=False 获取原始价格 + Adj Close。
"""

import logging
import time
from datetime import date, timedelta
from typing import List

from models.kline import KlineBar
from yfinance_wrap.client import YFinanceClient

logger = logging.getLogger(__name__)

_PERIOD_MAP = {
    "1D": "1d",
    "1W": "1wk",
    "1M": "1mo",
}


class YFinanceKlineFetcher:
    """
    美股K线数据拉取器。
    - 使用 yfinance Ticker.history() 拉取K线
    - 返回原始价格（auto_adjust=False），Adj Close 用于复权因子
    - 内置请求间隔控制
    """

    def __init__(self, client: YFinanceClient):
        self._client = client

    def fetch(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> List[KlineBar]:
        """
        拉取指定股票、周期、日期范围的历史K线（原始未复权）。

        yfinance history(start, end) 的 end 是不包含的，需 +1 天。

        Args:
            stock_code: 股票代码，如 US.AAPL
            period: K线周期 "1D"/"1W"/"1M"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            List[KlineBar]，按 trade_date 升序
        """
        interval = _PERIOD_MAP.get(period)
        if interval is None:
            raise ValueError(f"Unsupported period: {period}")

        # 请求间隔控制
        self._client.wait_rate_limit()

        # yfinance end 是不包含的，需 +1 天
        end_dt = date.fromisoformat(end_date) + timedelta(days=1)
        end_str = end_dt.strftime("%Y-%m-%d")

        logger.info(
            "[%s][%s] yfinance request start: start=%s, end=%s (actual_end=%s)",
            stock_code, period, start_date, end_date, end_str,
        )

        ticker = self._client.get_ticker(stock_code)

        for attempt in range(self._client.max_retries + 1):
            try:
                df = ticker.history(
                    start=start_date,
                    end=end_str,
                    interval=interval,
                    auto_adjust=False,
                )
                break
            except Exception as e:
                if attempt < self._client.max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "yfinance request failed for %s [%s] "
                        "(attempt %d/%d): %s. Retrying in %ds...",
                        stock_code, period, attempt + 1,
                        self._client.max_retries, e, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "yfinance request failed for %s [%s] after %d retries: %s",
                        stock_code, period, self._client.max_retries, e,
                    )
                    raise RuntimeError(
                        f"yfinance request failed after {self._client.max_retries} "
                        f"retries: {e}"
                    ) from e

        if df is None or df.empty:
            logger.info(
                "[%s][%s] yfinance request done: total_bars=0 (empty response)",
                stock_code, period,
            )
            return []

        bars = self._parse_dataframe(stock_code, period, df)

        if bars:
            logger.info(
                "[%s][%s] yfinance request done: total_bars=%d, "
                "first_trade_date=%s, last_trade_date=%s",
                stock_code, period, len(bars),
                bars[0].trade_date, bars[-1].trade_date,
            )
        else:
            logger.info(
                "[%s][%s] yfinance request done: total_bars=0 (no valid bars)",
                stock_code, period,
            )
        return bars

    @staticmethod
    def _parse_dataframe(stock_code: str, period: str, df) -> List[KlineBar]:
        """将 yfinance 返回的 DataFrame 解析为 KlineBar 列表。"""
        bars = []
        for index, row in df.iterrows():
            try:
                # yfinance 返回的 index 是 DatetimeIndex（带时区）
                if hasattr(index, "strftime"):
                    trade_date = index.strftime("%Y-%m-%d")
                else:
                    trade_date = str(index)[:10]

                # 读取 Adj Close 用于后续复权因子计算（不写入 KlineBar）
                adj_close = row.get("Adj Close", row.get("Close", None))

                bar = KlineBar(
                    stock_code=stock_code,
                    period=period,
                    trade_date=trade_date,
                    open=round(float(row["Open"]), 4),
                    high=round(float(row["High"]), 4),
                    low=round(float(row["Low"]), 4),
                    close=round(float(row["Close"]), 4),  # 原始收盘价
                    volume=int(row["Volume"]),
                    turnover=0.0,  # yfinance 不提供成交额
                    pe_ratio=None,  # yfinance 不在K线中提供
                    pb_ratio=None,
                    ps_ratio=None,
                    turnover_rate=None,
                    last_close=None,
                )
                # 将 adj_close 临时挂载到 bar 上（用于复权因子计算）
                bar._adj_close = round(float(adj_close), 6) if adj_close is not None else None
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse yfinance bar row: %s, error: %s",
                    dict(row) if hasattr(row, "__iter__") else str(row), e,
                )
        return bars
