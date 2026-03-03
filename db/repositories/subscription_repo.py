from typing import List
from db.connection import DBConnection


class SubscriptionRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def upsert_subscribed(self, stock_code: str, period: str) -> None:
        sql = """
            INSERT INTO subscription_status (stock_code, period, is_subscribed, subscribed_at)
            VALUES (?, ?, 1, datetime('now'))
            ON CONFLICT(stock_code, period) DO UPDATE SET
                is_subscribed   = 1,
                subscribed_at   = datetime('now'),
                unsubscribed_at = NULL
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (stock_code, period))

    def upsert_unsubscribed(self, stock_code: str, period: str) -> None:
        sql = """
            INSERT INTO subscription_status (stock_code, period, is_subscribed, unsubscribed_at)
            VALUES (?, ?, 0, datetime('now'))
            ON CONFLICT(stock_code, period) DO UPDATE SET
                is_subscribed   = 0,
                unsubscribed_at = datetime('now')
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (stock_code, period))

    def get_subscribed_count(self) -> int:
        sql = "SELECT COUNT(*) AS cnt FROM subscription_status WHERE is_subscribed = 1"
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql).fetchone()
        return row["cnt"]

    def get_all_subscribed(self) -> List[dict]:
        sql = "SELECT * FROM subscription_status WHERE is_subscribed = 1"
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def is_subscribed(self, stock_code: str, period: str) -> bool:
        sql = """
            SELECT is_subscribed FROM subscription_status
            WHERE stock_code = ? AND period = ?
        """
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (stock_code, period)).fetchone()
        return bool(row["is_subscribed"]) if row else False
