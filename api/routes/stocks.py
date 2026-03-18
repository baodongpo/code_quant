"""api/routes/stocks.py — GET /api/stocks"""

from fastapi import APIRouter
from config.settings import DB_PATH
from db.repositories.stock_repo import StockRepository

router = APIRouter()


@router.get("/stocks")
def list_stocks():
    """返回 watchlist 中全部活跃股票列表。"""
    repo = StockRepository(DB_PATH)
    stocks = repo.get_active()
    return {
        "stocks": [
            {
                "stock_code": s.stock_code,
                "market":     s.market,
                "asset_type": s.asset_type,
                "currency":   s.currency,
                "lot_size":   s.lot_size,
            }
            for s in stocks
        ]
    }
