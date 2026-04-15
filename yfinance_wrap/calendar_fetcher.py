"""
yfinance_wrap/calendar_fetcher.py — 美股交易日历拉取

使用 pandas-market-calendars 获取 NYSE 交易日历。
纯 Python 计算，无需 API 调用，无需网络连接。
"""

import logging
from typing import List

from config.settings import DEFAULT_HISTORY_START

logger = logging.getLogger(__name__)


class YFinanceCalendarFetcher:
    """
    美股交易日历拉取器。
    使用 pandas-market-calendars 的 NYSE 日历。
    """

    def __init__(self):
        try:
            import pandas_market_calendars as mcal  # noqa: F401
        except ImportError:
            raise ImportError(
                "pandas-market-calendars is required for US trading calendar. "
                "Install with: pip install pandas-market-calendars"
            )

    def fetch(self, market: str, start_date: str, end_date: str) -> List[str]:
        """
        获取指定日期范围内的美股交易日列表。

        Args:
            market: 市场代码，应为 "US"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"

        Returns:
            交易日期列表 ["YYYY-MM-DD", ...]
        """
        import pandas_market_calendars as mcal

        if market != "US":
            raise ValueError(f"YFinanceCalendarFetcher only supports market='US', got '{market}'")

        try:
            nyse = mcal.get_calendar("NYSE")
            schedule = nyse.schedule(start_date=start_date, end_date=end_date)

            if schedule is None or schedule.empty:
                logger.debug("No NYSE trading days in [%s~%s]", start_date, end_date)
                return []

            # schedule 的 index 是 DatetimeIndex（tz-naive，pandas-market-calendars 默认）
            trading_days = []
            for dt in schedule.index:
                day_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                trading_days.append(day_str)

            # 构建 is_trading_day 列表（全为 True，因为 schedule 只返回交易日）
            # 返回格式与 futu CalendarFetcher 一致：日期字符串列表
            logger.debug(
                "Fetched %d NYSE trading days [%s~%s]",
                len(trading_days), start_date, end_date,
            )
            return trading_days

        except Exception as e:
            logger.error("Failed to fetch NYSE calendar [%s~%s]: %s", start_date, end_date, e)
            return []
