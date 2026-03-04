from typing import List, Optional, Set
from db.connection import DBConnection
from models.kline import KlineBar


class KlineRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def insert_many(self, bars: List[KlineBar]) -> int:
        """INSERT OR IGNORE：不覆盖已有数据（历史拉取用）。返回实际插入行数。"""
        sql = """
            INSERT OR IGNORE INTO kline_data
                (stock_code, period, trade_date, open, high, low, close,
                 volume, turnover, pe_ratio, turnover_rate, last_close, is_valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [self._bar_to_tuple(b) for b in bars])
            return conn.execute("SELECT changes()").fetchone()[0]

    def upsert_many(self, bars: List[KlineBar]) -> int:
        """INSERT OR REPLACE：实时推送更新当日 bar 用。返回受影响行数。"""
        sql = """
            INSERT INTO kline_data
                (stock_code, period, trade_date, open, high, low, close,
                 volume, turnover, pe_ratio, turnover_rate, last_close, is_valid,
                 updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(stock_code, period, trade_date) DO UPDATE SET
                open          = excluded.open,
                high          = excluded.high,
                low           = excluded.low,
                close         = excluded.close,
                volume        = excluded.volume,
                turnover      = excluded.turnover,
                pe_ratio      = excluded.pe_ratio,
                turnover_rate = excluded.turnover_rate,
                last_close    = excluded.last_close,
                is_valid      = excluded.is_valid,
                updated_at    = datetime('now')
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [self._bar_to_tuple(b) for b in bars])
            return conn.execute("SELECT changes()").fetchone()[0]

    def get_dates_in_range(
        self, stock_code: str, period: str, start_date: str, end_date: str
    ) -> List[str]:
        """返回指定范围内已存储的交易日列表（升序）。"""
        sql = """
            SELECT trade_date FROM kline_data
            WHERE stock_code = ? AND period = ?
              AND trade_date >= ? AND trade_date <= ?
              AND is_valid = 1
            ORDER BY trade_date
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (stock_code, period, start_date, end_date)).fetchall()
        return [r["trade_date"] for r in rows]

    def get_bars(
        self, stock_code: str, period: str, start_date: str, end_date: str
    ) -> List[KlineBar]:
        sql = """
            SELECT * FROM kline_data
            WHERE stock_code = ? AND period = ?
              AND trade_date >= ? AND trade_date <= ?
              AND is_valid = 1
            ORDER BY trade_date
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (stock_code, period, start_date, end_date)).fetchall()
        return [self._row_to_bar(r) for r in rows]

    def get_latest_date(self, stock_code: str, period: str) -> Optional[str]:
        sql = """
            SELECT MAX(trade_date) AS latest FROM kline_data
            WHERE stock_code = ? AND period = ? AND is_valid = 1
        """
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (stock_code, period)).fetchone()
        return row["latest"] if row else None

    @staticmethod
    def _bar_to_tuple(b: KlineBar):
        return (
            b.stock_code, b.period, b.trade_date,
            b.open, b.high, b.low, b.close,
            b.volume, b.turnover, b.pe_ratio,
            b.turnover_rate, b.last_close,
            1 if b.is_valid else 0,
        )

    @staticmethod
    def _row_to_bar(row) -> KlineBar:
        return KlineBar(
            stock_code=row["stock_code"],
            period=row["period"],
            trade_date=row["trade_date"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
            turnover=row["turnover"],
            pe_ratio=row["pe_ratio"],
            turnover_rate=row["turnover_rate"],
            last_close=row["last_close"],
            is_valid=bool(row["is_valid"]),
        )
