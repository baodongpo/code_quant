"""api/routes/kline.py — GET /api/kline"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.services.kline_service import get_kline_with_indicators

router = APIRouter()

_VALID_PERIODS = {"1D", "1W", "1M"}
_VALID_ADJ     = {"qfq", "raw"}


@router.get("/kline")
def get_kline(
    code:   str            = Query(...,   description="股票代码，如 SH.600519"),
    period: str            = Query(...,   description="K线周期：1D / 1W / 1M"),
    start:  Optional[str]  = Query(None,  description="起始日期 YYYY-MM-DD（默认近1年）"),
    end:    Optional[str]  = Query(None,  description="结束日期 YYYY-MM-DD（默认今天）"),
    adj:    str            = Query("qfq", description="复权类型：qfq（前复权）/ raw（原始）"),
):
    """
    返回指定股票的 K线数据 + 全部技术指标。
    """
    if period not in _VALID_PERIODS:
        raise HTTPException(status_code=422, detail=f"Invalid period: {period}. Must be one of {_VALID_PERIODS}")
    if adj not in _VALID_ADJ:
        raise HTTPException(status_code=422, detail=f"Invalid adj type: {adj}. Must be one of {_VALID_ADJ}")

    try:
        result = get_kline_with_indicators(
            stock_code=code,
            period=period,
            start_date=start,
            end_date=end,
            adj_type=adj,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result
