import logging
from typing import List, Tuple

from config.settings import A_STOCK_CALENDAR_MARKET
from db.repositories.calendar_repo import CalendarRepository
from db.repositories.kline_repo import KlineRepository

logger = logging.getLogger(__name__)


class GapDetector:
    """
    基于交易日历的数据空洞检测。
    "连续"定义为交易日连续，而非日历日连续。
    """

    def __init__(
        self,
        calendar_repo: CalendarRepository,
        kline_repo: KlineRepository,
    ):
        self._calendar_repo = calendar_repo
        self._kline_repo = kline_repo

    def detect_gaps(
        self,
        stock_code: str,
        period: str,
        market: str,
        start_date: str,
        end_date: str,
    ) -> List[Tuple[str, str]]:
        """
        检测指定股票、周期、日期范围内的数据空洞。

        Args:
            stock_code: 股票代码
            period: K线周期 ("1D", "1W", "1M")
            market: 市场代码 ("HK", "US", "A", "SH", "SZ")
            start_date: 检测起始日 "YYYY-MM-DD"
            end_date: 检测结束日 "YYYY-MM-DD"

        Returns:
            [(gap_start, gap_end), ...] 空洞区间列表（交易日）
        """
        # A股用 SH 日历
        calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market

        # 根据周期获取基准交易日列表
        # FIX: 周K使用周一、月K使用每月第一天，与富途API返回的 time_key 格式一致
        if period == "1D":
            trading_days = self._calendar_repo.get_trading_days(
                calendar_market, start_date, end_date
            )
        elif period == "1W":
            trading_days = self._calendar_repo.get_weekly_mondays(
                calendar_market, start_date, end_date
            )
        elif period == "1M":
            trading_days = self._calendar_repo.get_monthly_first_days(
                calendar_market, start_date, end_date
            )
        else:
            raise ValueError(f"Unsupported period: {period}")

        if not trading_days:
            logger.warning(
                "No trading days found for %s [%s~%s], cannot detect gaps",
                calendar_market, start_date, end_date
            )
            return []

        # 已存储的交易日集合
        stored_dates = set(
            self._kline_repo.get_dates_in_range(stock_code, period, start_date, end_date)
        )

        # 缺失的交易日（保持顺序）
        missing = [d for d in trading_days if d not in stored_dates]

        if not missing:
            logger.debug(
                "No gaps detected for %s [%s] in [%s~%s]",
                stock_code, period, start_date, end_date
            )
            return []

        gaps = self._group_consecutive(missing, trading_days)
        logger.info(
            "Detected %d gaps for %s [%s]: %s",
            len(gaps), stock_code, period, gaps
        )
        return gaps

    @staticmethod
    def _group_consecutive(
        missing: List[str], trading_days: List[str]
    ) -> List[Tuple[str, str]]:
        """
        将缺失交易日列表分组为连续区间。
        "连续"定义为在 trading_days 中相邻（索引相差1）。

        示例：
          trading_days = [..., 2024-06-10, 2024-06-11, 2024-06-12, 2024-06-13, 2024-06-14, ...]
          missing      = [2024-06-10, 2024-06-11, 2024-06-14]
          → gaps       = [(2024-06-10, 2024-06-11), (2024-06-14, 2024-06-14)]
        """
        if not missing:
            return []

        # 建立交易日索引映射
        td_index = {d: i for i, d in enumerate(trading_days)}

        groups: List[Tuple[str, str]] = []
        gap_start = missing[0]
        gap_end = missing[0]

        for i in range(1, len(missing)):
            prev = missing[i - 1]
            curr = missing[i]
            prev_idx = td_index[prev]
            curr_idx = td_index[curr]

            if curr_idx == prev_idx + 1:
                # 交易日连续，延伸当前区间
                gap_end = curr
            else:
                # 不连续，记录上一个区间，开始新区间
                groups.append((gap_start, gap_end))
                gap_start = curr
                gap_end = curr

        groups.append((gap_start, gap_end))
        return groups
