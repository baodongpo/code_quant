import logging
from typing import List

from futu import KLType, RET_OK, AuType

from futu.client import FutuClient
from models.kline import KlineBar

logger = logging.getLogger(__name__)

# 富途 KLType 映射
_PERIOD_MAP = {
    "1D": KLType.K_DAY,
    "1W": KLType.K_WEEK,
    "1M": KLType.K_MON,
}

# 每次请求最大返回行数（富途限制单次 1000 条）
_PAGE_SIZE = 1000


class KlineFetcher:
    """封装 get_history_kline，支持分页拉取原始未复权K线。"""

    def __init__(self, client: FutuClient):
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
        自动分页处理超过 1000 条的情况。
        """
        kl_type = _PERIOD_MAP.get(period)
        if kl_type is None:
            raise ValueError(f"Unsupported period: {period}")

        all_bars: List[KlineBar] = []
        next_time = start_date

        while True:
            ret, data, next_page_req_key = self._client.ctx.request_history_kline(
                code=stock_code,
                start=next_time,
                end=end_date,
                ktype=kl_type,
                autype=AuType.QFQ,  # 我们请求不复权，但 API 要求此参数；下方取原始价格字段
                fields=None,        # 拉取所有字段
                max_count=_PAGE_SIZE,
                page_req_key=None if next_time == start_date else next_page_req_key,
            )

            # 注意：富途 request_history_kline 接口签名与 get_history_kline 不同
            # 若 SDK 版本不支持 request_history_kline，退化到 get_history_kline
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

            if next_page_req_key is None:
                break
            next_time = next_page_req_key

        return all_bars

    def fetch_simple(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
    ) -> List[KlineBar]:
        """
        使用 get_history_kline（非分页版本）拉取，适用于数据量较小的场景。
        """
        kl_type = _PERIOD_MAP.get(period)
        if kl_type is None:
            raise ValueError(f"Unsupported period: {period}")

        ret, data = self._client.ctx.get_history_kline(
            code=stock_code,
            start=start_date,
            end=end_date,
            ktype=kl_type,
            autype=AuType.NONE,   # 不复权，存原始价格
            fields=None,
            max_count=_PAGE_SIZE,
        )

        if ret != RET_OK:
            logger.error(
                "get_history_kline failed for %s [%s]: %s",
                stock_code, period, data
            )
            return []

        if data is None or data.empty:
            return []

        return self._parse_dataframe(stock_code, period, data)

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
