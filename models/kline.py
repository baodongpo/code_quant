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


@dataclass
class AdjustFactor:
    stock_code: str
    ex_date: str           # 除权日 "YYYY-MM-DD"
    forward_factor: float  # 前复权因子
    backward_factor: float # 后复权因子（备用）
    factor_source: str = "futu"
