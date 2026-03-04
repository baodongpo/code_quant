import logging
import time
from datetime import date, timedelta
from typing import List, TYPE_CHECKING

from futu import KLType, RET_OK, AuType

from config.settings import RATE_LIMIT_MAX_RETRIES
from futu.client import FutuClient
from models.kline import KlineBar

if TYPE_CHECKING:
    from core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_PERIOD_MAP = {
    "1D": KLType.K_DAY,
    "1W": KLType.K_WEEK,
    "1M": KLType.K_MON,
}

_PAGE_SIZE = 1000


def _next_date(date_str: str) -> str:
    """返回给定日期的下一个自然日（格式 YYYY-MM-DD）。"""
    y, m, d = date_str.split("-")
    next_day = date(int(y), int(m), int(d)) + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")


class KlineFetcher:
    """
    封装 get_history_kline，支持分页拉取原始未复权K线。
    每页调用前通过 rate_limiter.acquire() 控频，并对网络错误做指数退避重试。
    已拉取成功的页不会因后续页失败而重复拉取。
    """

    def __init__(self, client: FutuClient, rate_limiter: "RateLimiter"):
        self._client = client
        self._rate_limiter = rate_limiter

    def fetch(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> List[KlineBar]:
        """
        拉取指定股票、周期、日期范围的历史K线（原始未复权）。
        自动分页，每页独立限频+重试，已拉取页不重复拉取。
        """
        kl_type = _PERIOD_MAP.get(period)
        if kl_type is None:
            raise ValueError(f"Unsupported period: {period}")

        all_bars: List[KlineBar] = []
        current_start = start_date

        while True:
            bars = self._fetch_one_page_with_retry(
                stock_code, kl_type, period, current_start, end_date
            )

            all_bars.extend(bars)
            logger.debug(
                "Fetched %d bars for %s [%s], total so far: %d",
                len(bars), stock_code, period, len(all_bars)
            )

            if len(bars) < _PAGE_SIZE:
                break

            last_date = bars[-1].trade_date
            current_start = _next_date(last_date)
            if current_start > end_date:
                break

        return all_bars

    def _fetch_one_page_with_retry(
        self,
        stock_code: str,
        kl_type,
        period: str,
        start: str,
        end: str,
        max_retries: int = RATE_LIMIT_MAX_RETRIES,
    ) -> List[KlineBar]:
        """
        拉取单页K线，失败时指数退避重试（1s/2s/4s）。
        重试耗尽后抛出 RuntimeError，由调用方决定如何处理。
        """
        for attempt in range(max_retries + 1):
            self._rate_limiter.acquire()
            ret, data = self._client.ctx.get_history_kline(
                code=stock_code,
                start=start,
                end=end,
                ktype=kl_type,
                autype=AuType.NONE,   # 存原始未复权价格
                fields=None,
                max_count=_PAGE_SIZE,
            )

            if ret == RET_OK:
                if data is None or data.empty:
                    return []
                return self._parse_dataframe(stock_code, period, data)

            if attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "get_history_kline failed for %s [%s] page starting %s "
                    "(attempt %d/%d): %s. Retrying in %ds...",
                    stock_code, period, start, attempt + 1, max_retries, data, wait
                )
                time.sleep(wait)
            else:
                logger.error(
                    "get_history_kline failed for %s [%s] after %d retries: %s",
                    stock_code, period, max_retries, data
                )
                raise RuntimeError(
                    f"get_history_kline failed after {max_retries} retries: {data}"
                )
        raise RuntimeError("unreachable")

    @staticmethod
    def _parse_dataframe(stock_code: str, period: str, df) -> List[KlineBar]:
        """将富途返回的 DataFrame 解析为 KlineBar 列表。"""
        bars = []
        for _, row in df.iterrows():
            try:
                bar = KlineBar(
                    stock_code=stock_code,
                    period=period,
                    trade_date=str(row.get("time_key", row.get("date", "")))[:10],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                    turnover=float(row["turnover"]) if "turnover" in row and row["turnover"] is not None else None,
                    pe_ratio=float(row["pe_ratio"]) if "pe_ratio" in row and row["pe_ratio"] is not None else None,
                    turnover_rate=float(row["turnover_rate"]) if "turnover_rate" in row and row["turnover_rate"] is not None else None,
                    last_close=float(row["last_close"]) if "last_close" in row and row["last_close"] is not None else None,
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Failed to parse bar row: %s, error: %s", dict(row), e)
        return bars
