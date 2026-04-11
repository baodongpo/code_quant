"""
yfinance_wrap/client.py — yfinance 连接管理

yfinance 不需要持久连接（HTTP 请求），但需管理代理配置和请求频率。
不实现 connect()/disconnect() 生命周期，与 FutuClient 不同。
"""

import logging
import time

import requests

from config.settings import (
    YFINANCE_MAX_RETRIES,
    YFINANCE_PROXY,
    YFINANCE_REQUEST_INTERVAL,
)

logger = logging.getLogger(__name__)


class YFinanceClient:
    """
    yfinance 连接管理器。
    - 管理代理配置和请求间隔
    - 不需要 connect()/disconnect() 生命周期
    """

    def __init__(
        self,
        proxy: str = None,
        request_interval: float = None,
        max_retries: int = None,
    ):
        self._proxy = proxy if proxy is not None else YFINANCE_PROXY
        self._request_interval = (
            request_interval if request_interval is not None
            else YFINANCE_REQUEST_INTERVAL
        )
        self._max_retries = (
            max_retries if max_retries is not None
            else YFINANCE_MAX_RETRIES
        )
        self._last_request_time = 0.0
        self._session = self._build_session()

        if self._proxy:
            logger.info("yfinance proxy configured: %s", self._proxy)

    def _build_session(self) -> requests.Session:
        """构建带代理的 requests.Session。"""
        session = requests.Session()
        if self._proxy:
            session.proxies = {
                "http": self._proxy,
                "https": self._proxy,
            }
        return session

    def wait_rate_limit(self) -> None:
        """请求间隔控制，避免 Yahoo 限频。"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def get_ticker(self, stock_code: str):
        """
        获取 yfinance Ticker 对象。

        stock_code 格式转换：US.AAPL → AAPL
        """
        import yfinance as yf

        symbol = stock_code.split(".", 1)[1] if "." in stock_code else stock_code
        ticker = yf.Ticker(symbol, session=self._session)
        return ticker

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def session(self) -> requests.Session:
        return self._session
