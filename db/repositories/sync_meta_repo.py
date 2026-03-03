from typing import Optional
from db.connection import DBConnection
from models.enums import SyncStatus


class SyncMetaRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def get(self, stock_code: str, period: str) -> Optional[dict]:
        sql = "SELECT * FROM sync_metadata WHERE stock_code = ? AND period = ?"
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (stock_code, period)).fetchone()
        return dict(row) if row else None

    def upsert(
        self,
        stock_code: str,
        period: str,
        status: str,
        last_sync_date: Optional[str] = None,
        first_sync_date: Optional[str] = None,
        rows_fetched: int = 0,
        rows_inserted: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        sql = """
            INSERT INTO sync_metadata
                (stock_code, period, sync_status, last_sync_date, first_sync_date,
                 last_sync_ts, rows_fetched, rows_inserted, error_message)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
            ON CONFLICT(stock_code, period) DO UPDATE SET
                sync_status    = excluded.sync_status,
                last_sync_date = COALESCE(excluded.last_sync_date, sync_metadata.last_sync_date),
                first_sync_date = COALESCE(
                    sync_metadata.first_sync_date,
                    excluded.first_sync_date
                ),
                last_sync_ts   = datetime('now'),
                rows_fetched   = sync_metadata.rows_fetched + excluded.rows_fetched,
                rows_inserted  = sync_metadata.rows_inserted + excluded.rows_inserted,
                error_message  = excluded.error_message,
                retry_count    = CASE
                    WHEN excluded.sync_status = 'failed'
                    THEN sync_metadata.retry_count + 1
                    ELSE sync_metadata.retry_count
                END
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (
                stock_code, period, status, last_sync_date, first_sync_date,
                rows_fetched, rows_inserted, error_message
            ))

    def set_status(self, stock_code: str, period: str, status: str) -> None:
        sql = """
            UPDATE sync_metadata SET sync_status = ?, last_sync_ts = datetime('now')
            WHERE stock_code = ? AND period = ?
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (status, stock_code, period))

    def ensure_exists(self, stock_code: str, period: str) -> None:
        """确保记录存在（初始 pending 状态）。"""
        sql = """
            INSERT OR IGNORE INTO sync_metadata (stock_code, period, sync_status)
            VALUES (?, ?, 'pending')
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (stock_code, period))
