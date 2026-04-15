"""
tushare_wrap/__init__.py — TuShare 美股数据源封装

TuShare 是国内金融数据平台，提供稳定的美股日线数据。
120积分试用用户限制：50次/分钟、8000次/天。
"""

from tushare_wrap.client import TuShareClient
from tushare_wrap.kline_fetcher import TuShareKlineFetcher
from tushare_wrap.adjust_fetcher import TuShareAdjustFetcher
from tushare_wrap.calendar_fetcher import TuShareCalendarFetcher

__all__ = [
    "TuShareClient",
    "TuShareKlineFetcher",
    "TuShareAdjustFetcher",
    "TuShareCalendarFetcher",
]
