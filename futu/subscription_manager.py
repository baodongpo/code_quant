import logging
from typing import List, Callable, Optional

from futu import RET_OK, SubType, KlineHandlerBase

from config.settings import MAX_SUBSCRIPTIONS, ALL_PERIODS
from db.repositories.kline_repo import KlineRepository
from db.repositories.subscription_repo import SubscriptionRepository
from futu.client import FutuClient
from futu.kline_fetcher import KlineFetcher
from models.kline import KlineBar
from models.stock import Stock

logger = logging.getLogger(__name__)

# 周期 → 富途订阅类型映射（K线推送）
_SUB_TYPE_MAP = {
    "1D": SubType.K_DAY,
    "1W": SubType.K_WEEK,
    "1M": SubType.K_MON,
}

# 反查 period 字符串
_KL_TYPE_TO_PERIOD = {v: k for k, v in _SUB_TYPE_MAP.items()}


class KlinePushHandler(KlineHandlerBase):
    """
    实时K线推送回调处理器。
    继承富途 SDK KlineHandlerBase，通过 ctx.set_handler() 注册到 OpenQuoteContext。
    """

    def __init__(
        self,
        kline_repo: KlineRepository,
        on_bar_callback: Optional[Callable[[KlineBar], None]] = None,
    ):
        super().__init__()
        self._kline_repo = kline_repo
        self._on_bar_callback = on_bar_callback

    def on_recv_rsp(self, rsp_pb):
        """富途 SDK 推送回调入口（由 SDK 内部线程调用）。"""
        ret, content = super().on_recv_rsp(rsp_pb)
        if ret != RET_OK:
            logger.warning("KlinePush recv error: %s", content)
            return ret, content

        self._handle(content)
        return ret, content

    def handle_data(self, stock_code: str, period: str, data) -> None:
        """直接处理解析后的 DataFrame（供测试或手动调用）。"""
        bars = KlineFetcher._parse_dataframe(stock_code, period, data)
        self._store(bars)

    def _handle(self, content) -> None:
        """解析推送内容并存储。"""
        try:
            stock_code = content.get("stock_code", "")
            kl_type = content.get("kl_type", "")
            data = content.get("kline_list", None)

            if not stock_code or data is None:
                return

            period = _KL_TYPE_TO_PERIOD.get(kl_type, "1D")
            bars = KlineFetcher._parse_dataframe(stock_code, period, data)
            self._store(bars)
        except Exception as e:
            logger.error("KlinePush handle error: %s", e, exc_info=True)

    def _store(self, bars: List[KlineBar]) -> None:
        if not bars:
            return
        try:
            count = self._kline_repo.upsert_many(bars)
            logger.debug("KlinePush upserted %d bars", count)
            if self._on_bar_callback:
                for bar in bars:
                    self._on_bar_callback(bar)
        except Exception as e:
            logger.error("KlinePush store error: %s", e, exc_info=True)


class SubscriptionManager:
    """
    管理富途实时K线订阅，维护订阅状态，防止超出额度上限。
    """

    def __init__(
        self,
        client: FutuClient,
        kline_repo: KlineRepository,
        sub_repo: SubscriptionRepository,
        max_subscriptions: int = MAX_SUBSCRIPTIONS,
    ):
        self._client = client
        self._kline_repo = kline_repo
        self._sub_repo = sub_repo
        self._max = max_subscriptions
        self._push_handler: Optional[KlinePushHandler] = None

    def setup_push_handler(self) -> None:
        """创建并注册 K线推送回调到 OpenQuoteContext。应在 connect() 之后调用。"""
        self._push_handler = KlinePushHandler(self._kline_repo)
        self._client.ctx.set_handler(self._push_handler)
        logger.info("KlinePushHandler registered")

    def subscribe(self, stock_code: str, period: str) -> bool:
        """
        订阅单只股票的实时K线。
        超出额度上限时记录警告并返回 False。
        """
        sub_type = _SUB_TYPE_MAP.get(period)
        if sub_type is None:
            logger.warning("Unsupported period for subscription: %s", period)
            return False

        current_count = self._sub_repo.get_subscribed_count()
        if current_count >= self._max:
            logger.warning(
                "Subscription limit reached (%d/%d), cannot subscribe %s [%s]",
                current_count, self._max, stock_code, period
            )
            return False

        ret, err = self._client.ctx.subscribe(
            [stock_code], [sub_type], subscribe_push=True
        )
        if ret != RET_OK:
            logger.error("Subscribe failed for %s [%s]: %s", stock_code, period, err)
            return False

        self._sub_repo.upsert_subscribed(stock_code, period)
        logger.info("Subscribed %s [%s]", stock_code, period)
        return True

    def unsubscribe(self, stock_code: str, period: str) -> bool:
        """取消订阅单只股票的实时K线。"""
        sub_type = _SUB_TYPE_MAP.get(period)
        if sub_type is None:
            return False

        ret, err = self._client.ctx.unsubscribe([stock_code], [sub_type])
        if ret != RET_OK:
            logger.error("Unsubscribe failed for %s [%s]: %s", stock_code, period, err)
            return False

        self._sub_repo.upsert_unsubscribed(stock_code, period)
        logger.info("Unsubscribed %s [%s]", stock_code, period)
        return True

    def get_subscription_count(self) -> int:
        return self._sub_repo.get_subscribed_count()

    def sync_subscriptions(self, active_stocks: List[Stock]) -> None:
        """
        批量对齐订阅状态与 watchlist：
        - 活跃股票 → 确保已订阅（1D/1W/1M 三个周期）
        - 非活跃或已移除的股票 → 确保已取消订阅
        """
        active_codes = {s.stock_code for s in active_stocks}

        # 取消不再活跃的股票订阅
        for sub in self._sub_repo.get_all_subscribed():
            if sub["stock_code"] not in active_codes:
                self.unsubscribe(sub["stock_code"], sub["period"])

        # 订阅活跃股票的所有周期
        for stock in active_stocks:
            for period in ALL_PERIODS:
                if not self._sub_repo.is_subscribed(stock.stock_code, period):
                    success = self.subscribe(stock.stock_code, period)
                    if not success:
                        logger.warning(
                            "Stopping subscription sync due to quota limit"
                        )
                        return
