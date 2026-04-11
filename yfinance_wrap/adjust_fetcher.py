"""
yfinance_wrap/adjust_fetcher.py — 美股复权因子拉取

方案A（推荐）：从 Adj Close 反推 forward_factor
  forward_factor = Adj Close / Close
  forward_factor_b = 0.0（纯乘法模型）

与富途 adjust_factors 表格式兼容：
  adj_price = raw_price × A + B
  yfinance: A = Adj Close / Close, B = 0
"""

import logging
from datetime import date
from typing import List

from config.settings import DEFAULT_HISTORY_START
from models.kline import AdjustFactor
from yfinance_wrap.client import YFinanceClient

logger = logging.getLogger(__name__)


class YFinanceAdjustFetcher:
    """
    美股复权因子拉取器。
    从 Adj Close / Close 反推 forward_factor。
    """

    def __init__(self, client: YFinanceClient):
        self._client = client

    def fetch_factors(self, stock_code: str) -> List[AdjustFactor]:
        """
        拉取股票的复权因子列表。

        实现：
        1. 拉取全历史日K（auto_adjust=False），获取 Close 和 Adj Close
        2. 找出 Adj Close / Close ≠ 1.0 的日期（浮点容差 1e-6）
        3. 每个日期计算 forward_factor = Adj Close / Close
        4. 返回 AdjustFactor 列表

        Returns:
            按 ex_date 升序排列的 AdjustFactor 列表
        """
        import yfinance as yf

        self._client.wait_rate_limit()

        ticker = self._client.get_ticker(stock_code)

        today = date.today().strftime("%Y-%m-%d")
        end_plus_one = (date.today() + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            df = ticker.history(
                start=DEFAULT_HISTORY_START,
                end=end_plus_one,
                interval="1d",
                auto_adjust=False,
            )
        except Exception as e:
            logger.error(
                "yfinance history failed for adjust factors %s: %s",
                stock_code, e,
            )
            return []

        if df is None or df.empty:
            logger.debug("No history data for adjust factors %s", stock_code)
            return []

        factors = []
        for index, row in df.iterrows():
            try:
                close = float(row["Close"])
                adj_close = float(row["Adj Close"])

                if close == 0:
                    continue

                ratio = adj_close / close

                # 只记录有除权事件的日期（ratio ≠ 1.0）
                if abs(ratio - 1.0) > 1e-6:
                    ex_date = index.strftime("%Y-%m-%d") if hasattr(index, "strftime") else str(index)[:10]
                    factors.append(AdjustFactor(
                        stock_code=stock_code,
                        ex_date=ex_date,
                        forward_factor=round(ratio, 10),
                        forward_factor_b=0.0,
                        backward_factor=round(1.0 / ratio, 10),
                        backward_factor_b=0.0,
                        factor_source="yfinance",
                    ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(
                    "Failed to parse adjust factor row: %s, error: %s",
                    dict(row) if hasattr(row, "__iter__") else str(row), e,
                )

        factors.sort(key=lambda f: f.ex_date)
        logger.debug(
            "Fetched %d adjust factors for %s (yfinance)",
            len(factors), stock_code,
        )
        return factors
