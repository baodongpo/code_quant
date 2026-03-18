"""
数据导出接口。
支持将 K 线数据（原始或前复权）导出为 Parquet 或 CSV 格式。
"""

import logging
import os
from typing import List

from config.settings import DB_PATH, EXPORT_DIR
from core.adjustment_service import AdjustmentService
from db.repositories.adjust_factor_repo import AdjustFactorRepository
from db.repositories.kline_repo import KlineRepository
from models.kline import KlineBar

logger = logging.getLogger(__name__)

_SUPPORTED_ADJ = ("qfq", "raw")
_SUPPORTED_FORMATS = ("parquet", "csv")


def export_klines(
    stock_code: str,
    period: str,
    start_date: str,
    end_date: str,
    adj_type: str = "qfq",
    fmt: str = "parquet",
    output_dir: str = EXPORT_DIR,
    db_path: str = DB_PATH,
) -> str:
    """
    导出指定股票 K 线数据到文件。

    Args:
        stock_code: 股票代码，如 "SH.600519"
        period:     K 线周期，"1D" / "1W" / "1M"
        start_date: 起始日期 "YYYY-MM-DD"
        end_date:   结束日期 "YYYY-MM-DD"
        adj_type:   复权类型 "qfq"（前复权）/ "raw"（原始）
        fmt:        输出格式 "parquet"（默认）/ "csv"
        output_dir: 输出目录，默认读取 settings.EXPORT_DIR
        db_path:    数据库路径，默认读取 settings.DB_PATH

    Returns:
        输出文件的绝对路径
    """
    if adj_type not in _SUPPORTED_ADJ:
        raise ValueError(f"Unsupported adj_type: {adj_type!r}. Supported: {_SUPPORTED_ADJ}")
    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {fmt!r}. Supported: {_SUPPORTED_FORMATS}")

    # 读取数据
    kline_repo = KlineRepository(db_path)
    if adj_type == "qfq":
        adjust_factor_repo = AdjustFactorRepository(db_path)
        service = AdjustmentService(kline_repo, adjust_factor_repo)
        bars: List[KlineBar] = service.get_adjusted_klines(
            stock_code, period, start_date, end_date, adj_type="qfq"
        )
    else:
        bars = kline_repo.get_bars(stock_code, period, start_date, end_date)

    if not bars:
        raise ValueError(
            f"No data found for {stock_code} [{period}] {start_date}~{end_date} "
            f"with adj_type={adj_type!r}"
        )

    # 转为 DataFrame
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for export. Install it with: pip install pandas")

    records = []
    for b in bars:
        records.append({
            "stock_code":    b.stock_code,
            "period":        b.period,
            "trade_date":    b.trade_date,
            "open":          b.open,
            "high":          b.high,
            "low":           b.low,
            "close":         b.close,
            "volume":        b.volume,
            "turnover":      b.turnover,
            "pe_ratio":      b.pe_ratio,
            "pb_ratio":      b.pb_ratio,
            "ps_ratio":      b.ps_ratio,
            "turnover_rate": b.turnover_rate,
            "last_close":    b.last_close,
            "is_valid":      b.is_valid,
            "adj_type":      b.adjust_type,
        })
    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    # 生成文件名：{stock_code}_{period}_{start}_{end}_{adj_type}.{ext}
    safe_code = stock_code.replace(".", "_")
    filename = f"{safe_code}_{period}_{start_date}_{end_date}_{adj_type}.{fmt}"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)

    # 写出文件
    if fmt == "parquet":
        try:
            df.to_parquet(output_path, index=False, engine="pyarrow")
        except ImportError:
            raise ImportError(
                "pyarrow is required for Parquet export. Install it with: pip install pyarrow"
            )
    else:
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(
        "Exported %d bars for %s [%s] %s~%s (%s) → %s",
        len(bars), stock_code, period, start_date, end_date, adj_type, output_path
    )
    return output_path
