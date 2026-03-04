import time
import logging
from collections import deque
from typing import Callable, TypeVar

from config.settings import (
    RATE_LIMIT_MIN_INTERVAL,
    RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_MAX_IN_WINDOW,
    RATE_LIMIT_MAX_RETRIES,
    GENERAL_RATE_LIMIT_WINDOW_SECONDS,
    GENERAL_RATE_LIMIT_MAX_IN_WINDOW,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 富途 SDK 可能抛出的限频相关异常类名
_RETRYABLE_ERRORS = ("RateLimitError", "TimeoutError", "ConnectionError")


class RateLimiter:
    """
    双约束令牌桶，用于历史K线查询（get_history_kline）。

    约束1：每次请求最小间隔 MIN_INTERVAL 秒（默认 0.5s）
    约束2：WINDOW_SECONDS 窗口内最多 MAX_IN_WINDOW 次请求（默认 30s/25次）

    注意：富途全局限制为任意 30s 内所有接口调用总次数不超过 60 次。
    RateLimiter（K线，上限 25次）与 GeneralRateLimiter（其他接口，上限 60次）
    各自独立计数，理论合计上限为 85次/30s，超出富途全局限制。
    实际为单线程顺序调用，不会同时满负荷，但若 watchlist 较大时请适当
    调低两者的 max_in_window 之和使其 ≤ 60。
    """

    def __init__(
        self,
        min_interval: float = RATE_LIMIT_MIN_INTERVAL,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        max_in_window: int = RATE_LIMIT_MAX_IN_WINDOW,
    ):
        self._min_interval = min_interval
        self._window_seconds = window_seconds
        self._max_in_window = max_in_window
        self._last_request_time: float = 0.0
        self._request_times: deque = deque()

    def acquire(self) -> None:
        """阻塞直到可以发出下一个请求。"""
        now = time.monotonic()

        # 约束1：最小间隔
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            logger.debug("RateLimiter: sleeping %.3fs (min interval)", sleep_time)
            time.sleep(sleep_time)
            now = time.monotonic()

        # 约束2：滑动窗口
        window_start = now - self._window_seconds
        while self._request_times and self._request_times[0] < window_start:
            self._request_times.popleft()

        if len(self._request_times) >= self._max_in_window:
            oldest = self._request_times[0]
            sleep_time = (oldest + self._window_seconds) - now + 0.01
            if sleep_time > 0:
                logger.debug(
                    "RateLimiter: sleeping %.3fs (window limit %d/%d)",
                    sleep_time, len(self._request_times), self._max_in_window
                )
                time.sleep(sleep_time)
            now = time.monotonic()

        self._last_request_time = now
        self._request_times.append(now)

    def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        max_retries: int = RATE_LIMIT_MAX_RETRIES,
        **kwargs,
    ) -> T:
        """
        带指数退避重试的执行器。
        仅对限频/超时/连接错误重试，其他异常直接抛出。
        """
        for attempt in range(max_retries + 1):
            self.acquire()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_type = type(e).__name__
                is_retryable = any(
                    name in error_type for name in _RETRYABLE_ERRORS
                ) or any(
                    name.lower() in str(e).lower()
                    for name in ("rate limit", "timeout", "connection")
                )

                if is_retryable and attempt < max_retries:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "Retryable error on attempt %d/%d: %s. Retrying in %ds...",
                        attempt + 1, max_retries, e, wait
                    )
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("execute_with_retry exhausted without return or raise")


class GeneralRateLimiter:
    """
    单约束滑动窗口限频器，用于所有非K线富途接口（日历、复权因子等）。
    富途全局限制：任意 30s 内所有接口调用总次数不超过 60 次。
    无最小间隔约束。

    注意：与 RateLimiter 共享富途全局配额，两者合计 max_in_window 建议 ≤ 60。
    当前默认值：K线 25次 + 通用 60次 = 85次，实际单线程顺序执行不会同时打满，
    若出现富途全局限频错误，请在 .env 中降低 GENERAL_RATE_LIMIT_MAX_IN_WINDOW。
    """

    def __init__(
        self,
        window_seconds: float = GENERAL_RATE_LIMIT_WINDOW_SECONDS,
        max_in_window: int = GENERAL_RATE_LIMIT_MAX_IN_WINDOW,
    ):
        self._window_seconds = window_seconds
        self._max_in_window = max_in_window
        self._request_times: deque = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        window_start = now - self._window_seconds
        while self._request_times and self._request_times[0] < window_start:
            self._request_times.popleft()

        if len(self._request_times) >= self._max_in_window:
            oldest = self._request_times[0]
            sleep_time = (oldest + self._window_seconds) - now + 0.01
            if sleep_time > 0:
                logger.debug(
                    "GeneralRateLimiter: sleeping %.3fs (window limit %d/%d)",
                    sleep_time, len(self._request_times), self._max_in_window
                )
                time.sleep(sleep_time)
            now = time.monotonic()

        self._request_times.append(now)

    def execute_with_retry(
        self,
        func: Callable[..., T],
        *args,
        max_retries: int = RATE_LIMIT_MAX_RETRIES,
        **kwargs,
    ) -> T:
        for attempt in range(max_retries + 1):
            self.acquire()
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_type = type(e).__name__
                is_retryable = any(
                    name in error_type for name in _RETRYABLE_ERRORS
                ) or any(
                    name.lower() in str(e).lower()
                    for name in ("rate limit", "timeout", "connection")
                )

                if is_retryable and attempt < max_retries:
                    wait = 2 ** attempt
                    logger.warning(
                        "Retryable error on attempt %d/%d: %s. Retrying in %ds...",
                        attempt + 1, max_retries, e, wait
                    )
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError("execute_with_retry exhausted without return or raise")
