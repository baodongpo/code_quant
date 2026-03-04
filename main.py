"""
AI 量化辅助决策系统 - 数据源子系统入口

职责：初始化、组装依赖、启动同步。
警告：本系统仅作数据采集，绝对禁止任何自动交易逻辑。
"""

import logging
import os
import sys
from datetime import date
from logging.handlers import TimedRotatingFileHandler

from config.settings import DB_PATH, LOG_DIR, OPEND_HOST, OPEND_PORT
from core.adjustment_service import AdjustmentService
from core.gap_detector import GapDetector
from core.rate_limiter import RateLimiter, GeneralRateLimiter
from core.sync_engine import SyncEngine
from core.validator import KlineValidator
from core.watchlist_manager import WatchlistManager
from db.repositories.adjust_factor_repo import AdjustFactorRepository
from db.repositories.calendar_repo import CalendarRepository
from db.repositories.gap_repo import GapRepository
from db.repositories.kline_repo import KlineRepository
from db.repositories.stock_repo import StockRepository
from db.repositories.subscription_repo import SubscriptionRepository
from db.repositories.sync_meta_repo import SyncMetaRepository
from db.schema import init_db
from futu_wrap.adjust_factor_fetcher import AdjustFactorFetcher
from futu_wrap.calendar_fetcher import CalendarFetcher
from futu_wrap.client import FutuClient
from futu_wrap.kline_fetcher import KlineFetcher
from futu_wrap.subscription_manager import SubscriptionManager


def setup_logging() -> None:
    """配置按日轮转的日志输出（同时输出到控制台和文件）。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"sync_{date.today().strftime('%Y%m%d')}.log")

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def build_dependencies(futu_client: FutuClient) -> dict:
    """组装所有依赖对象（依赖注入）。"""
    # Repositories
    stock_repo = StockRepository(DB_PATH)
    kline_repo = KlineRepository(DB_PATH)
    calendar_repo = CalendarRepository(DB_PATH)
    sync_meta_repo = SyncMetaRepository(DB_PATH)
    gap_repo = GapRepository(DB_PATH)
    adjust_factor_repo = AdjustFactorRepository(DB_PATH)
    sub_repo = SubscriptionRepository(DB_PATH)

    # 限频器
    kline_rate_limiter = RateLimiter()           # 历史K线：双约束（0.5s + 30s/25次）
    general_rate_limiter = GeneralRateLimiter()  # 其他接口：30s/60次

    # Futu API（KlineFetcher 持有 rate_limiter，每页调用前控频）
    kline_fetcher = KlineFetcher(futu_client, kline_rate_limiter)
    calendar_fetcher = CalendarFetcher(futu_client)
    adjust_factor_fetcher = AdjustFactorFetcher(futu_client)

    # Core services
    validator = KlineValidator()
    gap_detector = GapDetector(calendar_repo, kline_repo)
    adjustment_service = AdjustmentService(kline_repo, adjust_factor_repo)

    # Watchlist manager
    watchlist_manager = WatchlistManager(stock_repo, sync_meta_repo)

    # Subscription manager
    subscription_manager = SubscriptionManager(futu_client, kline_repo, sub_repo)

    # Sync engine
    sync_engine = SyncEngine(
        kline_repo=kline_repo,
        calendar_repo=calendar_repo,
        sync_meta_repo=sync_meta_repo,
        gap_repo=gap_repo,
        adjust_factor_repo=adjust_factor_repo,
        kline_fetcher=kline_fetcher,
        calendar_fetcher=calendar_fetcher,
        adjust_factor_fetcher=adjust_factor_fetcher,
        gap_detector=gap_detector,
        validator=validator,
        general_rate_limiter=general_rate_limiter,
    )

    return {
        "stock_repo": stock_repo,
        "kline_repo": kline_repo,
        "adjustment_service": adjustment_service,
        "watchlist_manager": watchlist_manager,
        "subscription_manager": subscription_manager,
        "sync_engine": sync_engine,
    }


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("=" * 60)
    logger.info("AI Quant Data Subsystem starting")
    logger.info("DB: %s", DB_PATH)
    logger.info("OpenD: %s:%d", OPEND_HOST, OPEND_PORT)
    logger.info("=" * 60)

    # 1. 初始化数据库
    logger.info("Initializing database...")
    init_db(DB_PATH)
    logger.info("Database initialized at %s", DB_PATH)

    # 2. 连接富途 OpenD
    futu_client = FutuClient(OPEND_HOST, OPEND_PORT)
    try:
        futu_client.connect()
    except Exception as e:
        logger.error("Failed to connect to OpenD: %s", e)
        logger.error(
            "Please ensure OpenD is running at %s:%d", OPEND_HOST, OPEND_PORT
        )
        sys.exit(1)

    try:
        deps = build_dependencies(futu_client)
        watchlist_manager: WatchlistManager = deps["watchlist_manager"]
        subscription_manager: SubscriptionManager = deps["subscription_manager"]
        sync_engine: SyncEngine = deps["sync_engine"]

        # 3. 注册实时K线推送回调
        subscription_manager.setup_push_handler()

        # 4. 加载 watchlist，执行差异检测
        logger.info("Loading watchlist...")
        active_stocks, newly_added, reactivated = watchlist_manager.load()

        # 5. 同步订阅状态（即使 active_stocks 为空也执行，确保取消残留订阅）
        logger.info("Syncing subscriptions...")
        subscription_manager.sync_subscriptions(active_stocks)
        logger.info(
            "Subscriptions active: %d", subscription_manager.get_subscription_count()
        )

        if not active_stocks:
            logger.warning("No active stocks in watchlist. Nothing to sync.")
            return

        logger.info(
            "Active stocks: %d, newly added: %d, reactivated: %d",
            len(active_stocks), len(newly_added), len(reactivated)
        )

        # 6. 执行历史数据同步（全量/增量/空洞修复）
        logger.info("Starting data sync...")
        sync_engine.run_full_sync(active_stocks, newly_added, reactivated)
        logger.info("Data sync completed")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        futu_client.disconnect()
        logger.info("Disconnected from OpenD")
        logger.info("AI Quant Data Subsystem stopped")


if __name__ == "__main__":
    main()
