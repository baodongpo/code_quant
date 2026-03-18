import logging
from datetime import date, timedelta
from typing import List
import time

from futu import RET_OK, TradeDateMarket

from futu_wrap.client import FutuClient

logger = logging.getLogger(__name__)

# 本系统 market 字符串 → 富途 TradeDateMarket 枚举映射
_MARKET_MAP = {
    "HK": TradeDateMarket.HK,
    "US": TradeDateMarket.US,
    "SH": TradeDateMarket.CN,
    "SZ": TradeDateMarket.CN,
    "A":  TradeDateMarket.CN,
}

# request_trading_days 单次查询最大跨度（天）
_MAX_DAYS_PER_REQUEST = 365


class CalendarFetcher:
    """封装 request_trading_days，获取指定市场的交易日列表。"""

    def __init__(self, client: FutuClient):
        self._client = client

    def fetch(self, market: str, start_date: str, end_date: str) -> List[str]:
        """
        拉取指定市场在 [start_date, end_date] 范围内的交易日列表。
        自动按 365 天分段拉取。
        返回格式：['YYYY-MM-DD', ...]，升序排列。
        """
        futu_market = _MARKET_MAP.get(market)
        if futu_market is None:
            raise ValueError(f"Unsupported market for calendar: {market}")

        all_days: List[str] = []
        seg_start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        while seg_start <= end:
            seg_end = min(seg_start + timedelta(days=_MAX_DAYS_PER_REQUEST - 1), end)
            ret, data = self._client.ctx.request_trading_days(
                market=futu_market,
                start=seg_start.strftime("%Y-%m-%d"),
                end=seg_end.strftime("%Y-%m-%d"),
            )

            if ret != RET_OK:
                raise RuntimeError(
                    f"request_trading_days failed for market={market} "
                    f"[{seg_start}~{seg_end}]: {data}"
                )

            if data:
                # request_trading_days 返回 list[dict]，每个 dict 含 "time" 键
                # 部分旧版 SDK 可能返回 DataFrame；使用显式 TypeError 而非 assert，
                # 避免 Python -O 优化模式下 assert 被跳过导致后续 TypeError 难以排查
                if not isinstance(data, list):
                    raise TypeError(
                        f"Unexpected data type from request_trading_days: {type(data)}, "
                        f"expected list[dict]"
                    )
                all_days.extend(item["time"][:10] for item in data)

            logger.debug(
                "Fetched %d trading days for %s [%s~%s]",
                len(data) if data else 0, market, seg_start, seg_end
            )
            seg_start = seg_end + timedelta(days=1)
            if seg_start <= end:
                # 分段间手动限速：fetch() 内部实际发出多次 API 请求，
                # 外层 execute_with_retry 仅计一次调用，sleep 在此直接控速。
                time.sleep(0.6)

        return sorted(set(all_days))
