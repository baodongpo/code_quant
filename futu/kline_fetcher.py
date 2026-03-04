import logging
from datetime import date, timedelta
from typing import List, TYPE_CHECKING

from futu import KLType, RET_OK, AuType

from futu.client import FutuClient
from models.kline import KlineBar

if TYPE_CHECKING:
    from core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# 富途 KLType 映射
_PERIOD_MAP = {
    "1D": KLType.K_DAY,
    "1W": KLType.K_WEEK,
    "1M": KLType.K_MON,
}

# 每次请求最大返回行数（富途单次上限 1000 条）
_PAGE_SIZE = 1000


def _next_date(date_str: str) -> str:
    """返回给定日期的下一个自然日（格式 YYYY-MM-DD）。"""
    y, m, d = date_str.split("-")
    next_day = date(int(y), int(m), int(d)) + timedelta(days=1)
    return next_day.strftime("%Y-%m-%d")


class KlineFetcher:
    """
    封装 get_history_kline，支持分页拉取原始未复权K线。
    每次翻页前通过 rate_limiter.acquire() 控频，确保每一页都受限频保护。
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
        自动分页，每页调用前通过限频器控速。
        """
        kl_type = _PERIOD_MAP.get(period)
        if kl_type is None:
            raise ValueError(f"Unsupported period: {period}")

        all_bars: List[KlineBar] = []
        current_start = start_date

        while True:
            self._rate_limiter.acquire()

            ret, data = self._client.ctx.get_history_kline(
                code=stock_code,
                start=current_start,
                end=end_date,
                ktype=kl_type,
                autype=AuType.NONE,   # 存原始未复权价格
                fields=None,
                max_count=_PAGE_SIZE,
            )

            if ret != RET_OK:
                logger.error(
                    "get_history_kline failed for %s [%s]: %s",
                    stock_code, period, data
                )
                break

            if data is None or data.empty:
                break

            bars = self._parse_dataframe(stock_code, period, data)
            all_bars.extend(bars)

            logger.debug(
                "Fetched %d bars for %s [%s], total so far: %d",
                len(bars), stock_code, period, len(all_bars)
            )

            # 本页返回条数小于上限，已是最后一页
            if len(bars) < _PAGE_SIZE:
                break

            # 下一页从本页最后一条的次日开始
            last_date = bars[-1].trade_date
            current_start = _next_date(last_date)
            if current_start > end_date:
                break

        return all_bars

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
                    turnover=float(row["turnover"]) if "turnover" in row and row["turnover"] else None,
                    pe_ratio=float(row["pe_ratio"]) if "pe_ratio" in row and row["pe_ratio"] else None,
                    turnover_rate=float(row["turnover_rate"]) if "turnover_rate" in row and row["turnover_rate"] else None,
                    last_close=float(row["last_close"]) if "last_close" in row and row["last_close"] else None,
                )
                bars.append(bar)
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Failed to parse bar row: %s, error: %s", dict(row), e)
        return bars
