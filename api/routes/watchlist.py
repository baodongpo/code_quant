"""api/routes/watchlist.py — GET /api/watchlist/summary"""

from fastapi import APIRouter
from api.services.kline_service import get_watchlist_summary

router = APIRouter()


@router.get("/watchlist/summary")
def watchlist_summary():
    """返回 watchlist 总览（各股最新指标信号）。"""
    return get_watchlist_summary()
