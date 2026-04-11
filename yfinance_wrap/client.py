"""
yfinance_wrap/client.py — yfinance 连接管理

yfinance 不需要持久连接（HTTP 请求），但需管理代理配置和请求频率。
不实现 connect()/disconnect() 生命周期，与 FutuClient 不同。

代理方案：通过 curl_cffi Session 的 proxy 参数设置，
仅影响 yfinance 请求，不污染 os.environ（不影响富途 OpenD 等本地服务）。

Yahoo Finance API 限频规则（基于 IP）：
  - 每分钟 60 次
  - 每小时 360 次
  - 每天 8000 次
超限返回 HTTP 429 (YFRateLimitError)。
"""

import logging
import time
from collections import deque

from config.settings import (
    YFINANCE_MAX_RETRIES,
    YFINANCE_PROXY,
    YFINANCE_REQUEST_INTERVAL,
)

logger = logging.getLogger(__name__)


class YFinanceClient:
    """
    yfinance 连接管理器。
    - 管理代理配置（curl_cffi Session 级别，不影响进程其他请求）
    - 管理请求间隔和滑动窗口限频
    - 不需要 connect()/disconnect() 生命周期

    代理配置仅作用于 yfinance 请求，通过 curl_cffi Session 实现，
    不设置 os.environ，不影响富途 OpenD 等本地服务。
    """

    # Yahoo 官方限频规则
    RATE_LIMITS = [
        (60, 60),       # 60 次每分钟
        (360, 3600),    # 360 次每小时
        (8000, 86400),  # 8000 次每天
    ]

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

        # 滑动窗口限频：记录每次请求的时间戳
        self._request_timestamps = deque()

        # 创建 curl_cffi Session（带代理，仅 yfinance 使用）
        self._session = self._build_session()

    def _build_session(self):
        """构建 curl_cffi Session，仅 yfinance 使用。

        通过 Session 级别 proxy 设置代理，不污染 os.environ，
        富途 OpenD 等本地服务不受影响。
        """
        from curl_cffi.requests import Session

        kwargs = {}
        if self._proxy:
            kwargs["proxy"] = self._proxy
            logger.info("yfinance proxy configured (session-level): %s", self._proxy)
        else:
            logger.info("yfinance no proxy configured (direct connection)")

        return Session(**kwargs)

    def wait_rate_limit(self) -> None:
        """请求间隔控制 + 滑动窗口限频，避免 Yahoo 429。"""
        # 1. 固定间隔（最低保障）
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)

        # 2. 滑动窗口检查
        now = time.time()
        for max_count, window_seconds in self.RATE_LIMITS:
            # 清除过期记录
            cutoff = now - window_seconds
            while self._request_timestamps and self._request_timestamps[0] < cutoff:
                self._request_timestamps.popleft()

            # 检查是否超限
            if len(self._request_timestamps) >= max_count:
                # 需要等待最早的一条记录过期
                oldest = self._request_timestamps[0]
                wait_time = oldest + window_seconds - now + 0.1  # +0.1s 安全余量
                if wait_time > 0:
                    logger.warning(
                        "yfinance rate limit approaching: %d/%d in %ds window, "
                        "waiting %.1fs",
                        len(self._request_timestamps), max_count,
                        window_seconds, wait_time,
                    )
                    time.sleep(wait_time)

        # 记录本次请求时间
        self._last_request_time = time.time()
        self._request_timestamps.append(self._last_request_time)

    def is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为 Yahoo 限频错误（429）。"""
        err_str = str(error).lower()
        return (
            "429" in err_str
            or "rate limit" in err_str
            or "too many requests" in err_str
        )

    def get_ticker(self, stock_code: str):
        """
        获取 yfinance Ticker 对象。

        stock_code 格式转换：US.AAPL → AAPL
        传入 curl_cffi Session（带代理配置），仅影响 yfinance 请求。
        """
        import yfinance as yf

        symbol = stock_code.split(".", 1)[1] if "." in stock_code else stock_code
        ticker = yf.Ticker(symbol, session=self._session)
        return ticker

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def request_count(self) -> int:
        """当前滑动窗口内的请求计数（最近60秒）。"""
        now = time.time()
        cutoff = now - 60
        return sum(1 for t in self._request_timestamps if t >= cutoff)
