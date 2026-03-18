from dataclasses import dataclass
from typing import Optional


@dataclass
class KlineBar:
    stock_code: str
    period: str            # "1D", "1W", "1M"
    trade_date: str        # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: int            # 成交量（股，shares）
    turnover: Optional[float] = None    # 成交额
    pe_ratio: Optional[float] = None    # 市盈率（TTM，仅日K）
    turnover_rate: Optional[float] = None  # 换手率（%）
    last_close: Optional[float] = None  # 前收盘价（原始未复权）
    is_valid: bool = True
    is_adjusted: bool = False  # True 表示已经过复权计算
    adjust_type: Optional[str] = None  # 复权类型："qfq"（前复权）/ None（未复权），不落库，调用层填充


@dataclass
class AdjustFactor:
    stock_code: str
    ex_date: str            # 除权日 "YYYY-MM-DD"
    forward_factor: float   # 前复权乘法系数 A（拆送股调整）
    forward_factor_b: float # 前复权加法偏移 B（现金分红调整）
    backward_factor: float  # 后复权乘法系数 A（备用）
    backward_factor_b: float # 后复权加法偏移 B（备用）
    factor_source: str = "futu"
    # 前复权公式：adj_price = raw_price × A + B
    # 对交易日 t，将 ex_date > t 的所有事件按时间倒序依次作用：
    #   price = (...((price × A_n + B_n) × A_{n-1} + B_{n-1})...) × A_1 + B_1
