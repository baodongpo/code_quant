"""
yfinance_wrap/adjust_fetcher.py — 美股复权因子拉取

方案A（推荐）：从 Adj Close 反推 forward_factor
  forward_factor = Adj Close / Close
  forward_factor_b = 0.0（纯乘法模型）

与富途 adjust_factors 表格式兼容：
  adj_price = raw_price × A + B
  yfinance: A = Adj Close / Close, B = 0

优化：
- 复用 kline_fetcher 的数据，避免重复拉取全历史
- 带 429 特殊处理的重试机制
"""

import logging
from datetime import date
from typing import List, Optional

from config.settings import DEFAULT_HISTORY_START
from models.kline import AdjustFactor
from yfinance_wrap.client import YFinanceClient
from yfinance_wrap.kline_fetcher import YFinanceKlineFetcher

logger = logging.getLogger(__name__)


class YFinanceAdjustFetcher:
    """
    美股复权因子拉取器。
    从 Adj Close / Close 反推 forward_factor。

    优化：优先复用 kline_fetcher 已拉取的数据，
    仅在无缓存时独立拉取（复用同一个 fetcher 实例）。
    """

    def __init__(self, client: YFinanceClient, kline_fetcher: YFinanceKlineFetcher = None):
        self._client = client
        self._kline_fetcher = kline_fetcher
        # 缓存最近一次 kline fetch 的 Adj Close 数据
        # key: (stock_code, period, start_date, end_date) -> {trade_date: adj_close}
        self._adj_close_cache = {}

    def set_kline_fetcher(self, fetcher: YFinanceKlineFetcher) -> None:
        """设置 kline_fetcher 引用，用于复用数据。"""
        self._kline_fetcher = fetcher

    def cache_adj_close(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        adj_close_map: dict,
    ) -> None:
        """
        缓存 kline_fetcher 拉取的 Adj Close 数据，避免重复请求。

        由 SyncEngine 在 kline_fetcher 拉取后调用。
        """
        key = (stock_code, period, start_date, end_date)
        self._adj_close_cache[key] = adj_close_map
        logger.debug(
            "Cached adj_close for %s [%s] %s~%s: %d entries",
            stock_code, period, start_date, end_date, len(adj_close_map),
        )

    def fetch_factors(self, stock_code: str) -> List[AdjustFactor]:
        """
        拉取股票的复权因子列表。

        实现策略：
        1. 优先从缓存获取 Adj Close 数据
        2. 缓存未命中时，通过 kline_fetcher 拉取全历史日K
        3. 从 Adj Close / Close 反推 forward_factor

        Returns:
            按 ex_date 升序排列的 AdjustFactor 列表
        """
        today = date.today().strftime("%Y-%m-%d")
        end_plus_one = (date.today() + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        # 尝试从缓存获取 Adj Close
        adj_close_map = self._find_cached_adj_close(stock_code, DEFAULT_HISTORY_START, today)

        if adj_close_map:
            logger.debug("Using cached adj_close for %s factors", stock_code)
            # 还需要 Close 价格来计算 ratio，缓存中只有 adj_close
            # 仍需从 kline 数据中获取 Close，但 kline_fetcher 的 bars 已在内存
            # 使用 _extract_factors_from_kline_fetcher 方法
            return self._extract_factors_via_kline(stock_code)

        # 缓存未命中，通过 kline_fetcher 拉取（复用，不重复请求）
        if self._kline_fetcher is not None:
            return self._extract_factors_via_kline(stock_code)

        # 最后兜底：独立拉取（不应走到这里，正常流程 kline_fetcher 总是存在）
        return self._fetch_factors_independent(stock_code)

    def _find_cached_adj_close(
        self, stock_code: str, start_date: str, end_date: str
    ) -> Optional[dict]:
        """在缓存中查找匹配的 Adj Close 数据。"""
        for key, value in self._adj_close_cache.items():
            sc, period, sd, ed = key
            if sc == stock_code and sd <= start_date and ed >= end_date:
                return value
        return None

    def _extract_factors_via_kline(self, stock_code: str) -> List[AdjustFactor]:
        """通过 kline_fetcher 拉取日K并提取复权因子（一次请求，数据复用）。"""
        today = date.today().strftime("%Y-%m-%d")
        end_plus_one = (date.today() + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        # 使用 fetch_and_extract_adj_close 获取 K线和 Adj Close
        bars, adj_close_map = self._kline_fetcher.fetch_and_extract_adj_close(
            stock_code, "1D", DEFAULT_HISTORY_START, today,
        )

        if not bars or not adj_close_map:
            logger.debug("No data for adjust factors %s via kline_fetcher", stock_code)
            return []

        return self._compute_factors_from_bars(stock_code, bars, adj_close_map)

    def _fetch_factors_independent(self, stock_code: str) -> List[AdjustFactor]:
        """独立拉取复权因子（兜底，不推荐，会产生额外请求）。"""
        self._client.wait_rate_limit()

        import yfinance as yf
        ticker = self._client.get_ticker(stock_code)

        today = date.today().strftime("%Y-%m-%d")
        end_plus_one = (date.today() + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        # 带重试的拉取
        for attempt in range(self._client.max_retries + 1):
            try:
                df = ticker.history(
                    start=DEFAULT_HISTORY_START,
                    end=end_plus_one,
                    interval="1d",
                    auto_adjust=False,
                )
                break
            except Exception as e:
                is_429 = self._client.is_rate_limit_error(e)
                if attempt < self._client.max_retries:
                    if is_429:
                        wait = 30 * (2 ** min(attempt, 2))
                    else:
                        wait = 2 ** attempt
                    logger.warning(
                        "yfinance adjust fetch failed for %s (attempt %d/%d): %s. "
                        "Retrying in %ds...",
                        stock_code, attempt + 1, self._client.max_retries, e, wait,
                    )
                    time.sleep(wait) if not hasattr(self, '_time') else None
                    import time; time.sleep(wait)
                else:
                    logger.error(
                        "yfinance adjust fetch failed for %s after %d retries: %s",
                        stock_code, self._client.max_retries, e,
                    )
                    return []

        if df is None or df.empty:
            return []

        # 从 DataFrame 提取
        adj_close_map = {}
        for index, row in df.iterrows():
            trade_date = index.strftime("%Y-%m-%d") if hasattr(index, "strftime") else str(index)[:10]
            try:
                adj_close_map[trade_date] = float(row["Adj Close"])
            except (KeyError, ValueError, TypeError):
                pass

        # 用 bars 的 Close 价格计算 ratio
        factors = []
        for index, row in df.iterrows():
            try:
                close = float(row["Close"])
                adj_close = float(row["Adj Close"])
                if close == 0:
                    continue
                ratio = adj_close / close
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
        return factors

    @staticmethod
    def _compute_factors_from_bars(
        stock_code: str,
        bars: list,
        adj_close_map: dict,
    ) -> List[AdjustFactor]:
        """从 KlineBar 列表 + Adj Close 映射计算复权因子。"""
        factors = []
        for bar in bars:
            adj_close = adj_close_map.get(bar.trade_date)
            if adj_close is None or bar.close == 0:
                continue

            ratio = adj_close / bar.close

            # 只记录有除权事件的日期（ratio ≠ 1.0）
            if abs(ratio - 1.0) > 1e-6:
                factors.append(AdjustFactor(
                    stock_code=stock_code,
                    ex_date=bar.trade_date,
                    forward_factor=round(ratio, 10),
                    forward_factor_b=0.0,
                    backward_factor=round(1.0 / ratio, 10),
                    backward_factor_b=0.0,
                    factor_source="yfinance",
                ))

        factors.sort(key=lambda f: f.ex_date)
        logger.debug(
            "Computed %d adjust factors for %s from %d bars",
            len(factors), stock_code, len(bars),
        )
        return factors
