from typing import List, Optional
from db.connection import DBConnection
from models.kline import AdjustFactor


class AdjustFactorRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def upsert_many(self, factors: List[AdjustFactor]) -> None:
        """插入或更新复权因子。仅插入新事件，不修改历史。"""
        sql = """
            INSERT OR IGNORE INTO adjust_factors
                (stock_code, ex_date, forward_factor, forward_factor_b,
                 backward_factor, backward_factor_b, factor_source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with DBConnection(self._db_path) as conn:
            conn.executemany(sql, [
                (f.stock_code, f.ex_date, f.forward_factor, f.forward_factor_b,
                 f.backward_factor, f.backward_factor_b, f.factor_source)
                for f in factors
            ])

    def get_factors(self, stock_code: str) -> List[AdjustFactor]:
        """返回指定股票所有复权因子（按除权日升序）。"""
        sql = """
            SELECT * FROM adjust_factors
            WHERE stock_code = ?
            ORDER BY ex_date ASC
        """
        with DBConnection(self._db_path) as conn:
            rows = conn.execute(sql, (stock_code,)).fetchall()
        return [
            AdjustFactor(
                stock_code=row["stock_code"],
                ex_date=row["ex_date"],
                forward_factor=row["forward_factor"],
                forward_factor_b=row["forward_factor_b"],
                backward_factor=row["backward_factor"],
                backward_factor_b=row["backward_factor_b"],
                factor_source=row["factor_source"],
            )
            for row in rows
        ]

    def get_latest_ex_date(self, stock_code: str) -> Optional[str]:
        sql = """
            SELECT MAX(ex_date) AS latest FROM adjust_factors
            WHERE stock_code = ?
        """
        with DBConnection(self._db_path) as conn:
            row = conn.execute(sql, (stock_code,)).fetchone()
        return row["latest"] if row else None
