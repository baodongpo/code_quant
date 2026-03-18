from enum import Enum


class Market(str, Enum):
    HK = "HK"
    US = "US"
    A = "A"    # A股逻辑分组（SH/SZ）
    # 日历查询时，Market.A 由 calendar_fetcher._MARKET_MAP 映射为字符串 "SH"/"SZ"，不使用 Market 枚举


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
