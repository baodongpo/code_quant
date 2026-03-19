from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Stock:
    stock_code: str        # e.g. "HK.00700", "US.AAPL", "SH.600519"
    market: str            # "HK", "US", "A"
    asset_type: str        # "stock" or "ETF"
    is_active: bool
    lot_size: int          # 每手股数
    currency: str          # "HKD", "USD", "CNY"
    name: Optional[str] = None  # 股票名称，如"腾讯控股"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
