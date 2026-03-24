"""api/routes/indicators.py — GET /api/indicators"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/indicators")
def list_indicators():
    """返回系统支持的指标清单及参数说明。"""
    return {
        "indicators": [
            {
                "name":   "MA",
                "label":  "移动平均线",
                "type":   "overlay",
                "params": {"periods": [5, 20, 60]},
            },
            {
                "name":   "BOLL",
                "label":  "布林带",
                "type":   "overlay",
                "params": {"n": 20, "k": 2},
            },
            {
                "name":   "MACD",
                "label":  "MACD",
                "type":   "panel",
                "params": {"fast": 12, "slow": 26, "signal": 9},
            },
            {
                "name":   "RSI",
                "label":  "RSI",
                "type":   "panel",
                "params": {"n": 14},
            },
            {
                "name":   "KDJ",
                "label":  "KDJ",
                "type":   "panel",
                "params": {"n": 9},
            },
            {
                "name":   "MAVOL",
                "label":  "成交量均线",
                "type":   "volume_overlay",
                "params": {"periods": [5, 10, 20]},
            },
            {
                "name":   "VPA_DEFENDER",
                "label":  "量价共振防守",
                "type":   "panel",
                "params": {"atr_period": 22, "atr_multi": 3.0, "obv_ma_period": 20},
            },
        ]
    }
