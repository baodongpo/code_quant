import logging
from typing import Optional
from futu import OpenQuoteContext

from config.settings import OPEND_HOST, OPEND_PORT

logger = logging.getLogger(__name__)


class FutuClient:
    """OpenQuoteContext 生命周期管理器，支持上下文管理器协议。"""

    def __init__(self, host: str = OPEND_HOST, port: int = OPEND_PORT):
        self._host = host
        self._port = port
        self._ctx: Optional[OpenQuoteContext] = None

    def connect(self) -> "FutuClient":
        if self._ctx is None:
            logger.info("Connecting to OpenD at %s:%d", self._host, self._port)
            self._ctx = OpenQuoteContext(host=self._host, port=self._port)
            logger.info("Connected to OpenD")
        return self

    def disconnect(self) -> None:
        if self._ctx is not None:
            logger.info("Disconnecting from OpenD")
            self._ctx.close()
            self._ctx = None

    @property
    def ctx(self) -> OpenQuoteContext:
        if self._ctx is None:
            raise RuntimeError("FutuClient not connected. Call connect() first.")
        return self._ctx

    def __enter__(self) -> "FutuClient":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.disconnect()
        return False
