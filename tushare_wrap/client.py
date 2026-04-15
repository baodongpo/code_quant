"""
tushare_wrap/client.py — TuShare 连接管理

TuShare 使用 Token 鉴权，通过 pro_api 初始化。
120积分试用用户限制：
  - 每分钟 50 次
  - 每天 8000 次

API 文档：https://tushare.pro/document/2?doc_id=254
"""

import logging
import time
from collections import deque

from config.settings import (
    TUSHARE_REQUEST_INTERVAL,
    TUSHARE_TOKEN,
)

logger = logging.getLogger(__name__)


class TuShareClient:
    """
    TuShare 连接管理器。
    - 管理 Token 鉴权
    - 管理请求间隔和滑动窗口限频
    - 不需要 connect()/disconnect() 生命周期
    """

    # 120积分试用用户限制
    RATE_LIMITS = [
        (50, 60),       # 50次/分钟
        (8000, 86400),  # 8000次/天
    ]

    def __init__(
        self,
        token: str = None,
        request_interval: float = None,
    ):
        self._token = token if token is not None else TUSHARE_TOKEN
        self._request_interval = (
            request_interval if request_interval is not None
            else TUSHARE_REQUEST_INTERVAL
        )
        self._last_request_time = 0.0

        # 滑动窗口限频：记录每次请求的时间戳
        self._request_timestamps = deque()

        # 懒加载 tushare pro_api
        self._pro = None

        if not self._token:
            logger.warning(
                "TUSHARE_TOKEN not configured. US stock data will not be available."
            )

    def _init_pro(self):
        """懒加载 tushare pro_api。"""
        if self._pro is None:
            try:
                import tushare as ts
                self._pro = ts.pro_api(self._token)
                logger.info("TuShare pro_api initialized successfully")
            except ImportError:
                raise ImportError(
                    "tushare is required for US stock data. "
                    "Install with: pip install tushare"
                )
        return self._pro

    @property
    def pro(self):
        """获取 tushare pro_api 对象。"""
        return self._init_pro()

    def wait_rate_limit(self) -> None:
        """请求间隔控制 + 滑动窗口限频，避免超出 TuShare 限制。"""
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
                        "TuShare rate limit approaching: %d/%d in %ds window, "
                        "waiting %.1fs",
                        len(self._request_timestamps), max_count,
                        window_seconds, wait_time,
                    )
                    time.sleep(wait_time)

        # 记录本次请求时间
        self._last_request_time = time.time()
        self._request_timestamps.append(self._last_request_time)

    def is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为 TuShare 限频错误。"""
        err_str = str(error).lower()
        return (
            "抱歉" in err_str and "积分" in err_str
            or "权限" in err_str
            or "rate limit" in err_str
        )

    @property
    def request_count(self) -> int:
        """当前滑动窗口内的请求计数（最近60秒）。"""
        now = time.time()
        cutoff = now - 60
        return sum(1 for t in self._request_timestamps if t >= cutoff)

    @property
    def is_available(self) -> bool:
        """检查 TuShare 是否可用（Token 已配置）。"""
        return bool(self._token)
