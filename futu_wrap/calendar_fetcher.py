import logging
from typing import List

from futu import RET_OK, Market as FutuMarket

from futu_wrap.client import FutuClient

logger = logging.getLogger(__name__)

# 本系统 market 字符串 → 富途 Market 枚举映射
_MARKET_MAP = {
    "HK": FutuMarket.HK,
    "US": FutuMarket.US,
    "SH": FutuMarket.SH,
    "SZ": FutuMarket.SZ,
    "A":  FutuMarket.SH,   # A股用 SH 日历
}


class CalendarFetcher:
    """封装 get_trading_days，获取指定市场的交易日列表。"""

    def __init__(self, client: FutuClient):
        self._client = client

    def fetch(self, market: str, start_date: str, end_date: str) -> List[str]:
        """
        拉取指定市场在 [start_date, end_date] 范围内的交易日列表。
        返回格式：['YYYY-MM-DD', ...]，升序排列。
        """
        futu_market = _MARKET_MAP.get(market)
        if futu_market is None:
            raise ValueError(f"Unsupported market for calendar: {market}")

        ret, data = self._client.ctx.get_trading_days(
            market=futu_market,
            start=start_date,
            end=end_date,
        )

        if ret != RET_OK:
            logger.error(
                "get_trading_days failed for market=%s [%s~%s]: %s",
                market, start_date, end_date, data
            )
            return []

        if data is None or data.empty:
            return []

        # 富途返回的列名为 'time'
        col = "time" if "time" in data.columns else data.columns[0]
        trading_days = [str(d)[:10] for d in data[col].tolist()]
        logger.debug(
            "Fetched %d trading days for %s [%s~%s]",
            len(trading_days), market, start_date, end_date
        )
        return sorted(set(trading_days))
