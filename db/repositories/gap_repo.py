from typing import List, Optional
from db.connection import DBConnection


class GapRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def get_open_gaps(self, stock_code: str, period: str) -> List[dict]:
        sql = """
            SELECT * FROM data_gaps
            WHERE stock_code = ? AND period = ? AND status = 'open'
            ORDER BY gap_start
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (stock_code, period)).fetchall()
        return [dict(r) for r in rows]

    def get_all_open_gaps(self) -> List[dict]:
        """返回所有 open 状态的空洞（跨股票，供 stats 命令展示）。"""
        sql = """
            SELECT * FROM data_gaps
            WHERE status = 'open'
            ORDER BY stock_code, period, gap_start
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql).fetchall()
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
        """
        批量写入空洞列表（单事务，原子提交）。
        - 新空洞（不存在）：插入为 'open'
        - 已存在且为 'failed' 的空洞：重置为 'open' 以允许重试
        - 已存在且为 'open'/'filling'/'filled' 的空洞：不变
        """
        sql = """
            INSERT INTO data_gaps (stock_code, period, gap_start, gap_end, status)
            VALUES (?, ?, ?, ?, 'open')
            ON CONFLICT(stock_code, period, gap_start, gap_end) DO UPDATE SET
                status = CASE
                    WHEN data_gaps.status = 'failed' THEN 'open'
                    ELSE data_gaps.status
                END,
                detected_at = CASE
                    WHEN data_gaps.status = 'failed' THEN datetime('now')
                    ELSE data_gaps.detected_at
                END
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [
                (stock_code, period, gap_start, gap_end)
                for gap_start, gap_end in gaps
            ])
