from typing import List
from db.connection import DBConnection


class CalendarRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def insert_many(self, market: str, dates: List[str], is_trading: bool = True) -> None:
        """批量插入交易日历，已存在则忽略。"""
        sql = """
            INSERT OR IGNORE INTO trading_calendar (market, trade_date, is_trading_day)
            VALUES (?, ?, ?)
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [(market, d, 1 if is_trading else 0) for d in dates])

    def get_trading_days(self, market: str, start_date: str, end_date: str) -> List[str]:
        """返回指定市场、日期范围内的交易日列表（升序）。"""
        sql = """
            SELECT trade_date FROM trading_calendar
            WHERE market = ? AND trade_date >= ? AND trade_date <= ?
              AND is_trading_day = 1
            ORDER BY trade_date
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (market, start_date, end_date)).fetchall()
        return [r["trade_date"] for r in rows]

    def has_calendar(self, market: str, start_date: str, end_date: str) -> bool:
        """检查某市场在指定范围内是否已有日历数据。"""
        sql = """
            SELECT COUNT(*) AS cnt FROM trading_calendar
            WHERE market = ? AND trade_date >= ? AND trade_date <= ?
        """
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (market, start_date, end_date)).fetchone()
        return row["cnt"] > 0

    def get_weekly_last_trading_days(
        self, market: str, start_date: str, end_date: str
    ) -> List[str]:
        """返回每周最后一个交易日（用于周K空洞检测）。"""
        all_days = self.get_trading_days(market, start_date, end_date)
        return self._last_of_period(all_days, period="week")

    def get_monthly_last_trading_days(
        self, market: str, start_date: str, end_date: str
    ) -> List[str]:
        """返回每月最后一个交易日（用于月K空洞检测）。"""
        all_days = self.get_trading_days(market, start_date, end_date)
        return self._last_of_period(all_days, period="month")

    @staticmethod
    def _last_of_period(trading_days: List[str], period: str) -> List[str]:
        """从交易日列表中提取每周/每月的最后一个交易日。"""
        if not trading_days:
            return []
        result = []
        for i, date_str in enumerate(trading_days):
            year, month, day = date_str.split("-")
            is_last = False
            if i == len(trading_days) - 1:
                is_last = True
            else:
                next_y, next_m, next_d = trading_days[i + 1].split("-")
                if period == "week":
                    from datetime import date
                    cur = date(int(year), int(month), int(day))
                    nxt = date(int(next_y), int(next_m), int(next_d))
                    is_last = cur.isocalendar()[1] != nxt.isocalendar()[1] or cur.year != nxt.year
                elif period == "month":
                    is_last = (year, month) != (next_y, next_m)
            if is_last:
                result.append(date_str)
        return result
