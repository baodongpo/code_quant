"""
akshare_wrap/__init__.py — AkShare 美股数据源封装

AkShare 是免费开源的金融数据接口库，无需 Token。
数据源：东方财富、新浪财经等。

美股数据使用 stock_us_hist 接口，支持前复权。
"""

from akshare_wrap.client import AkShareClient
from akshare_wrap.kline_fetcher import AkShareKlineFetcher

__all__ = [
    "AkShareClient",
    "AkShareKlineFetcher",
]
