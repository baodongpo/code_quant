"""
akshare_wrap/client.py — AkShare 连接管理

AkShare 是免费开源的金融数据接口库，无需 Token。
数据源：东方财富、新浪财经等，有反爬机制。

请求频率建议：
  - 间隔：0.5-2秒，推荐 1 秒
  - 高频会触发反爬（HTTP 403/429）

AkShare 文档：https://akshare.akfamily.xyz/data/stock/stock.html#id2
"""

import logging
import random
import time
from collections import deque

logger = logging.getLogger(__name__)


class AkShareClient:
    """
    AkShare 连接管理器。
    - 无需 Token，完全免费
    - 管理请求间隔，避免反爬
    - 不需要 connect()/disconnect() 生命周期
    """

    # 保守限频：30次/分钟
    RATE_LIMITS = [
        (30, 60),  # 30次/分钟
    ]

    def __init__(self, request_interval: float = 1.0):
        """
        初始化 AkShare 客户端。

        Args:
            request_interval: 请求间隔（秒），默认 1.0
        """
        self._request_interval = request_interval
        self._last_request_time = 0.0

        # 滑动窗口限频：记录每次请求的时间戳
        self._request_timestamps: deque[float] = deque()

        logger.info(
            "AkShare client initialized (request_interval=%.1fs, no token required)",
            self._request_interval,
        )

    def wait_rate_limit(self) -> None:
        """
        请求间隔控制 + 滑动窗口限频，避免触发反爬。

        实现两级限频机制：
        1. 固定间隔：每次请求后强制等待 `_request_interval` 秒，加上随机抖动（0-0.5秒）
           避免固定频率被识别为爬虫
        2. 滑动窗口：检查最近60秒内的请求次数，若超过30次则等待至最早记录过期

        调用此方法后，会在内部记录本次请求时间戳，供后续限频检查使用。
        """
        # 1. 固定间隔 + 随机抖动（避免固定频率被识别为爬虫）
        elapsed = time.time() - self._last_request_time
        jitter = random.uniform(0, 0.5)  # 随机抖动 0-0.5 秒
        wait_time = self._request_interval - elapsed + jitter
        if wait_time > 0:
            time.sleep(wait_time)

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
                        "AkShare rate limit approaching: %d/%d in %ds window, "
                        "waiting %.1fs",
                        len(self._request_timestamps), max_count,
                        window_seconds, wait_time,
                    )
                    time.sleep(wait_time)

        # 记录本次请求时间
        self._last_request_time = time.time()
        self._request_timestamps.append(self._last_request_time)

    def is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为反爬限频错误。"""
        err_str = str(error).lower()
        return (
            "403" in err_str
            or "429" in err_str
            or "rate limit" in err_str
            or "forbidden" in err_str
            or "too many" in err_str
        )

    @property
    def request_count(self) -> int:
        """当前滑动窗口内的请求计数（最近60秒）。"""
        now = time.time()
        cutoff = now - 60
        return sum(1 for t in self._request_timestamps if t >= cutoff)

    @property
    def is_available(self) -> bool:
        """AkShare 始终可用（无需 Token）。"""
        return True
