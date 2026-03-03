from typing import List, Optional
from db.connection import DBConnection


class GapRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def insert(self, stock_code: str, period: str, gap_start: str, gap_end: str) -> int:
        """插入新的空洞记录，返回新行 ID。"""
        sql = """
            INSERT OR IGNORE INTO data_gaps (stock_code, period, gap_start, gap_end, status)
            VALUES (?, ?, ?, ?, 'open')
        """
        with DBConnection(self._db_path) as conn:
            cursor = conn.execute(sql, (stock_code, period, gap_start, gap_end))
            return cursor.lastrowid

    def get_open_gaps(self, stock_code: str, period: str) -> List[dict]:
        sql = """
            SELECT * FROM data_gaps
            WHERE stock_code = ? AND period = ? AND status = 'open'
            ORDER BY gap_start
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (stock_code, period)).fetchall()
        return [dict(r) for r in rows]

    def mark_filling(self, gap_id: int) -> None:
        with DBConnection(self._db_path) as conn:
            conn.execute(
                "UPDATE data_gaps SET status = 'filling' WHERE id = ?", (gap_id,)
            )

    def mark_filled(self, gap_id: int) -> None:
        with DBConnection(self._db_path) as conn:
            conn.execute(
                "UPDATE data_gaps SET status = 'filled', filled_at = datetime('now') WHERE id = ?",
                (gap_id,)
            )

    def mark_failed(self, gap_id: int) -> None:
        with DBConnection(self._db_path) as conn:
            conn.execute(
                "UPDATE data_gaps SET status = 'failed' WHERE id = ?", (gap_id,)
            )

    def upsert_gaps(
        self, stock_code: str, period: str, gaps: List[tuple]
    ) -> None:
        """批量写入空洞列表，已存在则忽略。gaps: [(gap_start, gap_end), ...]"""
        sql = """
            INSERT OR IGNORE INTO data_gaps (stock_code, period, gap_start, gap_end, status)
            VALUES (?, ?, ?, ?, 'open')
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [
                (stock_code, period, g[0], g[1]) for g in gaps
            ])
