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
        """
        检查某市场的日历数据是否已覆盖到 end_date。

        修复 BUG-01：原实现仅判断范围内是否存在任意记录（COUNT > 0），
        导致增量同步时因历史数据已存在而跳过，造成近期交易日缺失。
        现改为检查 MAX(trade_date) >= end_date，确保日历数据覆盖到请求范围末尾。

        发现-01：必须加 is_trading_day = 1 过滤，否则节假日补录的休市记录
        （is_trading_day=0）会使 MAX 偏大，导致误判已覆盖而跳过增量拉取。

        注意：若 end_date 为周末/节假日（非交易日），MAX(trade_date) 为上一个
        交易日（< end_date），此时返回 False 并触发增量拉取。增量拉取为幂等操作
        （INSERT OR IGNORE），对已有数据无副作用，轻微的重复拉取可接受。
        """
        sql = """
            SELECT MAX(trade_date) AS max_date FROM trading_calendar
            WHERE market = ? AND is_trading_day = 1
        """
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (market,)).fetchone()
        max_date = row["max_date"] if row else None
        return max_date is not None and max_date >= end_date

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

    def get_weekly_mondays(
        self, market: str, start_date: str, end_date: str
    ) -> List[str]:
        """
        返回每周周一日期列表（用于周K空洞检测）。
        
        富途API返回的周K time_key 是周一，因此空洞检测也需要用周一作为基准。
        只返回该周内有交易日的周一。
        """
        from datetime import date, timedelta
        
        all_days = self.get_trading_days(market, start_date, end_date)
        if not all_days:
            return []
        
        # 找出所有有交易日的周，返回对应的周一
        weeks = set()
        for trade_day in all_days:
            d = date.fromisoformat(trade_day)
            monday = d - timedelta(days=d.weekday())  # 该周的周一
            weeks.add(monday)
        
        # 返回排序后的周一列表
        return sorted([str(d) for d in weeks])

    def get_monthly_first_days(
        self, market: str, start_date: str, end_date: str
    ) -> List[str]:
        """
        返回每月第一天日期列表（用于月K空洞检测）。
        
        富途API返回的月K time_key 是每月第一天，因此空洞检测也需要用第一天作为基准。
        只返回该月内有交易日的月份。
        """
        all_days = self.get_trading_days(market, start_date, end_date)
        if not all_days:
            return []
        
        # 找出所有有交易日的月份，返回对应的第一天
        months = set()
        for trade_day in all_days:
            first_day = trade_day[:7] + "-01"  # YYYY-MM-01
            months.add(first_day)
        
        # 返回排序后的月第一天列表
        return sorted(list(months))

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
