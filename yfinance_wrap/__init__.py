"""
yfinance_wrap — yfinance 美股数据源封装模块（迭代9）

与 futu_wrap 对称设计，为美股提供 K线拉取、复权因子、交易日历能力。
严格只读，绝对禁止任何交易/下单逻辑。
"""

from yfinance_wrap.client import YFinanceClient
from yfinance_wrap.kline_fetcher import YFinanceKlineFetcher
from yfinance_wrap.adjust_fetcher import YFinanceAdjustFetcher

__all__ = [
    "YFinanceClient",
    "YFinanceKlineFetcher",
    "YFinanceAdjustFetcher",
]
