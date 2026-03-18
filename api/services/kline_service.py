"""
api/services/kline_service.py — K线 + 指标数据服务层

封装 AdjustmentService + IndicatorEngine 调用，供路由层使用。
严格只读：不调用任何 Repository 写入方法。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from config.settings import DB_PATH
from core.adjustment_service import AdjustmentService
from core.indicator_engine import IndicatorEngine, calc_composite_signal, _last_valid
from db.repositories.adjust_factor_repo import AdjustFactorRepository
from db.repositories.kline_repo import KlineRepository
from db.repositories.stock_repo import StockRepository
from models.kline import KlineBar


def _default_start(period: str, end_date: str) -> str:
    """根据周期返回默认起始日期（近1年）。"""
    end = date.fromisoformat(end_date)
    return (end - timedelta(days=365)).isoformat()


def get_kline_with_indicators(
    stock_code: str,
    period: str,
    start_date: Optional[str],
    end_date: Optional[str],
    adj_type: str = "qfq",
) -> Dict[str, Any]:
    """
    读取 K线数据并计算全部指标。
    返回符合 PRD §5.2 的响应字典。
    """
    today = date.today().isoformat()
    end_date = end_date or today
    start_date = start_date or _default_start(period, end_date)

    # 只读 Repositories
    kline_repo = KlineRepository(DB_PATH)
    adjust_factor_repo = AdjustFactorRepository(DB_PATH)
    stock_repo = StockRepository(DB_PATH)

    # 校验 stock 存在
    stock = stock_repo.get_by_code(stock_code)
    if stock is None:
        raise ValueError(f"Stock not found: {stock_code}")

    # 获取 K线（前复权 or 原始）
    if adj_type == "qfq":
        adj_service = AdjustmentService(kline_repo, adjust_factor_repo)
        bars: List[KlineBar] = adj_service.get_adjusted_klines(
            stock_code, period, start_date, end_date, adj_type="qfq"
        )
    else:
        bars = kline_repo.get_bars(stock_code, period, start_date, end_date)

    if not bars:
        return {
            "stock_code": stock_code,
            "period": period,
            "adj_type": adj_type,
            "bars": [],
            "indicators": {},
            "signals": {},
        }

    # 计算指标
    indicator_result = IndicatorEngine.calculate_all(bars)

    # 序列化 bars
    bars_json = [
        {
            "date":         b.trade_date,
            "open":         b.open,
            "high":         b.high,
            "low":          b.low,
            "close":        b.close,
            "volume":       b.volume,
            "turnover":     b.turnover,
            "pe_ratio":     b.pe_ratio,
            "pb_ratio":     b.pb_ratio,
            "ps_ratio":     b.ps_ratio,
            "turnover_rate": b.turnover_rate,
        }
        for b in bars
    ]

    return {
        "stock_code": stock_code,
        "period":     period,
        "adj_type":   adj_type,
        "bars":       bars_json,
        "indicators": {
            "MA":    indicator_result.MA,
            "BOLL":  indicator_result.BOLL,
            "MACD":  indicator_result.MACD,
            "RSI":   indicator_result.RSI,
            "KDJ":   indicator_result.KDJ,
            "MAVOL": indicator_result.MAVOL,
        },
        "signals": indicator_result.signals,
    }


def get_watchlist_summary() -> Dict[str, Any]:
    """
    返回 watchlist 所有活跃股票的最新指标信号。
    每只股票取最近 90 个交易日的日K，只计算日K。
    """
    stock_repo = StockRepository(DB_PATH)
    kline_repo = KlineRepository(DB_PATH)
    adjust_factor_repo = AdjustFactorRepository(DB_PATH)
    adj_service = AdjustmentService(kline_repo, adjust_factor_repo)

    active_stocks = stock_repo.get_active()
    today = date.today().isoformat()
    start_90d = (date.today() - timedelta(days=130)).isoformat()  # 多取一些确保有足够 bar

    summary = []
    for stock in active_stocks:
        bars = adj_service.get_adjusted_klines(
            stock.stock_code, "1D", start_90d, today, adj_type="qfq"
        )
        if not bars:
            continue

        ind = IndicatorEngine.calculate_all(bars)
        latest = bars[-1]

        # 涨跌幅
        change_pct: Optional[float] = None
        if latest.last_close and latest.last_close != 0:
            change_pct = round((latest.close - latest.last_close) / latest.last_close * 100, 2)

        # RSI 最新值（用于综合信号）
        rsi_val = _last_valid(ind.RSI.get("RSI14", []))

        composite = calc_composite_signal(ind.signals, rsi_val)

        summary.append({
            "stock_code":   stock.stock_code,
            "latest_close": latest.close,
            "change_pct":   change_pct,
            "pe_ratio":     latest.pe_ratio,
            "pb_ratio":     latest.pb_ratio,
            "signals": {
                "RSI":       ind.signals.get("RSI", "neutral"),
                "RSI_value": rsi_val,
                "MACD":      ind.signals.get("MACD", "neutral"),
                "KDJ":       ind.signals.get("KDJ", "neutral"),
                "composite": composite,
            },
        })

    return {"summary": summary}
