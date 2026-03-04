import logging
import time
from typing import List, Optional, TYPE_CHECKING

from futu import KLType, RET_OK, AuType

from config.settings import RATE_LIMIT_MAX_RETRIES
from futu_wrap.client import FutuClient
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


class KlineFetcher:
    """
    封装 request_history_kline，支持分页拉取原始未复权K线。
    每页调用前通过 rate_limiter.acquire() 控频，并对失败做指数退避重试。
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
        使用 page_req_key 自动分页，每页独立限频+重试。
        """
        kl_type = _PERIOD_MAP.get(period)
        if kl_type is None:
            raise ValueError(f"Unsupported period: {period}")

        all_bars: List[KlineBar] = []
        page_req_key: Optional[str] = None

        while True:
            bars, next_key = self._fetch_one_page_with_retry(
                stock_code, kl_type, period, start_date, end_date, page_req_key
            )

            all_bars.extend(bars)
            logger.debug(
                "Fetched %d bars for %s [%s], total so far: %d",
                len(bars), stock_code, period, len(all_bars)
            )

            if next_key is None:
                break
            page_req_key = next_key

        return all_bars

    def _fetch_one_page_with_retry(
        self,
        stock_code: str,
        kl_type,
        period: str,
        start: str,
        end: str,
        page_req_key: Optional[str],
        max_retries: int = RATE_LIMIT_MAX_RETRIES,
    ):
        """
        拉取单页K线，失败时指数退避重试（1s/2s/4s）。
        返回 (bars, next_page_req_key)，next_page_req_key 为 None 表示已是最后一页。
        重试耗尽后抛出 RuntimeError。
        """
        for attempt in range(max_retries + 1):
            self._rate_limiter.acquire()
            ret, data, next_key = self._client.ctx.request_history_kline(
                code=stock_code,
                start=start,
                end=end,
                ktype=kl_type,
                autype=AuType.NONE,
                fields=None,
                max_count=_PAGE_SIZE,
                page_req_key=page_req_key,
            )

            if ret == RET_OK:
                if data is None or data.empty:
                    return [], None
                return self._parse_dataframe(stock_code, period, data), next_key

            if attempt < max_retries:
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "request_history_kline failed for %s [%s] "
                    "(attempt %d/%d): %s. Retrying in %ds...",
                    stock_code, period, attempt + 1, max_retries, data, wait
                )
                time.sleep(wait)
            else:
                logger.error(
                    "request_history_kline failed for %s [%s] after %d retries: %s",
                    stock_code, period, max_retries, data
                )
                raise RuntimeError(
                    f"request_history_kline failed after {max_retries} retries: {data}"
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
