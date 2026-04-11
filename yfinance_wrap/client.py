"""
yfinance_wrap/client.py — yfinance 连接管理

yfinance 不需要持久连接（HTTP 请求），但需管理代理配置和请求频率。
不实现 connect()/disconnect() 生命周期，与 FutuClient 不同。

注意：yfinance >= 0.2.36 要求使用 curl_cffi session（自动处理），
不要手动设置 requests.Session，否则会报 YFDataException。
代理必须通过 os.environ 设置，curl_cffi 才会读取。

Yahoo Finance API 限频规则（基于 IP）：
  - 每分钟 60 次
  - 每小时 360 次
  - 每天 8000 次
超限返回 HTTP 429 (YFRateLimitError)。
"""

import logging
import os
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
    - 管理代理配置和请求间隔
    - 不需要 connect()/disconnect() 生命周期
    - 不手动创建 session（yfinance 自动使用 curl_cffi）
    - 滑动窗口限频（60/min, 360/hour, 8000/day）
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

        # 设置代理（curl_cffi 通过环境变量读取）
        self._setup_proxy()

    def _setup_proxy(self) -> None:
        """配置代理环境变量，让 curl_cffi 自动使用。

        同时设置 NO_PROXY 排除本地地址，避免富途 OpenD (127.0.0.1:11111)
        等本地服务请求被代理拦截。
        """
        if self._proxy:
            os.environ["HTTP_PROXY"] = self._proxy
            os.environ["HTTPS_PROXY"] = self._proxy
            # NO_PROXY：本地回环地址不走代理，保护富途 OpenD 等本地服务
            no_proxy = os.environ.get("NO_PROXY", "")
            local_hosts = "localhost,127.0.0.1,0.0.0.0"
            if not no_proxy:
                os.environ["NO_PROXY"] = local_hosts
            elif "127.0.0.1" not in no_proxy:
                os.environ["NO_PROXY"] = f"{no_proxy},{local_hosts}"
            logger.info(
                "yfinance proxy configured via env: %s (NO_PROXY=%s)",
                self._proxy, os.environ["NO_PROXY"],
            )
        else:
            # 清除可能存在的旧代理配置
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)

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
        不传入 session，让 yfinance 自动使用 curl_cffi。
        """
        import yfinance as yf

        symbol = stock_code.split(".", 1)[1] if "." in stock_code else stock_code
        ticker = yf.Ticker(symbol)
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
