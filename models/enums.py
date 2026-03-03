from enum import Enum


class Market(str, Enum):
    HK = "HK"
    US = "US"
    A = "A"    # A股逻辑分组（SH/SZ），日历查询映射到 SH
    SH = "SH"
    SZ = "SZ"


class Period(str, Enum):
    DAY = "1D"
    WEEK = "1W"
    MONTH = "1M"


class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class GapStatus(str, Enum):
    OPEN = "open"
    FILLING = "filling"
    FILLED = "filled"
    FAILED = "failed"


class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "ETF"
