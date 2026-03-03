from typing import List, Optional
from db.connection import DBConnection
from models.stock import Stock


class StockRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def upsert(self, stock: Stock) -> None:
        sql = """
            INSERT INTO stocks (stock_code, market, asset_type, is_active, lot_size, currency, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(stock_code) DO UPDATE SET
                market      = excluded.market,
                asset_type  = excluded.asset_type,
                is_active   = excluded.is_active,
                lot_size    = excluded.lot_size,
                currency    = excluded.currency,
                updated_at  = datetime('now')
        """
        with DBConnection(self._db_path) as conn:
            conn.execute(sql, (
                stock.stock_code, stock.market, stock.asset_type,
                1 if stock.is_active else 0,
                stock.lot_size, stock.currency
            ))

    def upsert_many(self, stocks: List[Stock]) -> None:
        sql = """
            INSERT INTO stocks (stock_code, market, asset_type, is_active, lot_size, currency, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(stock_code) DO UPDATE SET
                market      = excluded.market,
                asset_type  = excluded.asset_type,
                is_active   = excluded.is_active,
                lot_size    = excluded.lot_size,
                currency    = excluded.currency,
                updated_at  = datetime('now')
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [
                (s.stock_code, s.market, s.asset_type,
                 1 if s.is_active else 0, s.lot_size, s.currency)
                for s in stocks
            ])

    def get_all(self) -> List[Stock]:
        with DBConnection(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM stocks").fetchall()
        return [self._row_to_stock(r) for r in rows]

    def get_active(self) -> List[Stock]:
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM stocks WHERE is_active = 1"
            ).fetchall()
        return [self._row_to_stock(r) for r in rows]

    def get_by_code(self, stock_code: str) -> Optional[Stock]:
        with DBConnection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM stocks WHERE stock_code = ?", (stock_code,)
            ).fetchone()
        return self._row_to_stock(row) if row else None

    def set_active(self, stock_code: str, is_active: bool) -> None:
        with DBConnection(self._db_path) as conn:
            conn.execute(
                "UPDATE stocks SET is_active = ?, updated_at = datetime('now') WHERE stock_code = ?",
                (1 if is_active else 0, stock_code)
            )

    @staticmethod
    def _row_to_stock(row) -> Stock:
        return Stock(
            stock_code=row["stock_code"],
            market=row["market"],
            asset_type=row["asset_type"],
            is_active=bool(row["is_active"]),
            lot_size=row["lot_size"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
