import logging
from typing import List, Optional
from db.connection import DBConnection
from models.enums import SyncStatus

logger = logging.getLogger(__name__)


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
        force_first_sync_date: bool = False,
    ) -> None:
        """
        更新同步元数据。

        first_sync_date 更新策略：
        - force_first_sync_date=True（全量重同步场景）：强制覆盖
        - force_first_sync_date=False（默认）：仅在 DB 中无值时写入
        rows_fetched / rows_inserted 语义：本次同步的行数（非累计）。
        """
        if force_first_sync_date:
            first_sync_date_sql = "excluded.first_sync_date"
        else:
            first_sync_date_sql = "COALESCE(sync_metadata.first_sync_date, excluded.first_sync_date)"

        sql = f"""
            INSERT INTO sync_metadata
                (stock_code, period, sync_status, last_sync_date, first_sync_date,
                 last_sync_ts, rows_fetched, rows_inserted, error_message)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
            ON CONFLICT(stock_code, period) DO UPDATE SET
                sync_status    = excluded.sync_status,
                last_sync_date = COALESCE(excluded.last_sync_date, sync_metadata.last_sync_date),
                first_sync_date = {first_sync_date_sql},
                last_sync_ts   = datetime('now'),
                rows_fetched   = excluded.rows_fetched,
                rows_inserted  = excluded.rows_inserted,
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
            logger.debug(
                "[sync_metadata] UPSERT: stock=%s, period=%s, status=%s, "
                "last_sync_date=%s, rows_fetched=%d, rows_inserted=%d",
                stock_code, period, status,
                last_sync_date, rows_fetched, rows_inserted
            )

    def set_status(self, stock_code: str, period: str, status: str) -> None:
        sql = """
            UPDATE sync_metadata SET sync_status = ?, last_sync_ts = datetime('now')
            WHERE stock_code = ? AND period = ?
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (status, stock_code, period))
            logger.debug(
                "[sync_metadata] UPDATE status: stock=%s, period=%s → %s",
                stock_code, period, status
            )

    def get_all_by_status(self, status: str) -> List[dict]:
        """返回所有符合指定 sync_status 的记录列表。"""
        sql = "SELECT * FROM sync_metadata WHERE sync_status = ?"
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (status,)).fetchall()
        return [dict(row) for row in rows]

    def ensure_exists(self, stock_code: str, period: str) -> None:
        """确保记录存在（初始 pending 状态）。"""
        sql = """
            INSERT OR IGNORE INTO sync_metadata (stock_code, period, sync_status)
            VALUES (?, ?, 'pending')
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (stock_code, period))
