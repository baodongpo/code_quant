"""
AI 量化辅助决策系统 - 数据源子系统入口

职责：初始化、组装依赖、启动同步。
警告：本系统仅作数据采集，绝对禁止任何自动交易逻辑。
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import date, timedelta
from logging.handlers import TimedRotatingFileHandler

from config.settings import (
    DB_PATH, EXPORT_DIR, HEALTH_CHECK_INTERVAL, HEALTH_FILE,
    LOG_DIR, OPEND_HOST, OPEND_PORT,
    RECONNECT_BASE_INTERVAL, RECONNECT_MAX_RETRIES,
)
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

# 全局优雅退出标志（SIGTERM 设置后，同步完当前 stock 后退出）
_shutdown_requested = False


def _is_connection_error(e: Exception) -> bool:
    """
    判断是否为 OpenD 连接类异常。

    优先使用 isinstance 类型检测（B-1 修复：避免字符串匹配漏判）；
    str 关键词匹配作为 fallback，应对富途 SDK 将连接错误包装为通用 Exception 的情况。
    """
    if isinstance(e, (ConnectionError, TimeoutError, OSError)):
        return True
    err_str = str(e).lower()
    return any(kw in err_str for kw in (
        "connect", "connection", "disconnect", "timeout",
        "opend", "network", "errno", "broken pipe",
    ))


def _handle_sigterm(signum, frame) -> None:
    """SIGTERM 信号处理器：设置退出标志，等待当前同步任务完成后优雅退出。"""
    global _shutdown_requested
    _shutdown_requested = True
    logger = logging.getLogger("main")
    logger.warning("SIGTERM received, will exit after current sync task completes.")


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
    general_rate_limiter = GeneralRateLimiter()  # 其他接口：30s/35次

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
        "sync_meta_repo": sync_meta_repo,
        "adjustment_service": adjustment_service,
        "watchlist_manager": watchlist_manager,
        "subscription_manager": subscription_manager,
        "sync_engine": sync_engine,
    }


def write_health(status: str, detail: str = "") -> None:
    """原子写入健康检查文件（先写 .tmp 再 os.replace，避免监控工具读到半写的 JSON）。"""
    import time
    payload = {
        "status": status,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "detail": detail,
    }
    try:
        health_dir = os.path.dirname(HEALTH_FILE)
        os.makedirs(health_dir, exist_ok=True)
        tmp_path = HEALTH_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_path, HEALTH_FILE)
    except OSError as e:
        logging.getLogger("main").warning("Failed to write health file: %s", e)


def _run_sync_once(
    futu_client: FutuClient,
    logger: logging.Logger,
) -> bool:
    """
    执行一次完整的同步流程（连接已建立）。
    返回 True 表示正常完成，返回 False 表示检测到断线需要重连。
    抛出 KeyboardInterrupt / RuntimeError 等非连接异常由调用方处理。
    """
    deps = build_dependencies(futu_client)
    watchlist_manager: WatchlistManager = deps["watchlist_manager"]
    subscription_manager: SubscriptionManager = deps["subscription_manager"]
    sync_engine: SyncEngine = deps["sync_engine"]

    # 启动恢复：重置宕机残留的 RUNNING 状态（Module C）
    recovered_codes = sync_engine.recover_running_states()

    # 加载 watchlist，执行差异检测
    logger.info("Loading watchlist...")
    active_stocks, newly_added, reactivated = watchlist_manager.load()

    # 将崩溃恢复的 stock 也并入 reactivated（触发空洞检测）
    if recovered_codes:
        recovered_set = set(recovered_codes)
        extra_reactivated = [s for s in active_stocks
                             if s.stock_code in recovered_set
                             and s not in reactivated]
        reactivated = reactivated + extra_reactivated
        logger.info(
            "Crash recovery: %d stocks added to reactivated for gap detection",
            len(extra_reactivated)
        )

    # 注册实时推送 handler（必须在 sync_subscriptions 之前，确保订阅建立时 handler 已就绪）
    subscription_manager.setup_push_handler()

    # 同步订阅状态：活跃股票订阅，非活跃取消（Module B）
    logger.info("Syncing subscriptions...")
    subscription_manager.sync_subscriptions(active_stocks)

    if not active_stocks:
        logger.warning("No active stocks in watchlist. Nothing to sync.")
        write_health("idle", "No active stocks")
        return True

    logger.info(
        "Active stocks: %d, newly added: %d, reactivated: %d",
        len(active_stocks), len(newly_added), len(reactivated)
    )

    write_health("running", f"Syncing {len(active_stocks)} stocks")

    # 执行历史数据同步（全量/增量/空洞修复）
    logger.info("Starting data sync...")
    sync_engine.run_full_sync(
        active_stocks, newly_added, reactivated,
        shutdown_flag=lambda: _shutdown_requested,
    )

    if _shutdown_requested:
        logger.warning("Sync interrupted by SIGTERM after completing current task.")
        write_health("stopped", "Interrupted by SIGTERM")
    else:
        logger.info("Data sync completed")
        write_health("ok", f"Sync completed for {len(active_stocks)} stocks")

    return True


def cmd_sync(_args) -> None:
    """执行历史数据同步（默认子命令），含 OpenD 断线指数退避重连。"""
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("=" * 60)
    logger.info("AI Quant Data Subsystem starting")
    logger.info("DB: %s", DB_PATH)
    logger.info("OpenD: %s:%d", OPEND_HOST, OPEND_PORT)
    logger.info("=" * 60)

    # 注册 SIGTERM 处理器（systemd stop / kill 信号）
    signal.signal(signal.SIGTERM, _handle_sigterm)

    # 初始化数据库（只需一次）
    logger.info("Initializing database...")
    init_db(DB_PATH)
    logger.info("Database initialized at %s", DB_PATH)

    futu_client = FutuClient(OPEND_HOST, OPEND_PORT)
    retry_count = 0

    try:
        # 初始连接
        try:
            futu_client.connect()
        except Exception as e:
            logger.error("Failed to connect to OpenD: %s", e)
            logger.error("Please ensure OpenD is running at %s:%d", OPEND_HOST, OPEND_PORT)
            write_health("error", f"OpenD connection failed: {e}")
            sys.exit(1)

        while not _shutdown_requested:
            try:
                _run_sync_once(futu_client, logger)
                # 正常完成后退出循环（批处理模式：跑完即退）
                break

            except KeyboardInterrupt:
                raise  # 向外层传递，统一处理

            except Exception as e:
                # 判断是否为断线类错误（连接失败时重连，其他错误直接退出）
                if not _is_connection_error(e):
                    logger.error("Non-connection error during sync: %s", e, exc_info=True)
                    write_health("error", str(e))
                    sys.exit(1)

                # 断线重连逻辑：指数退避（30s → 60s → 120s，最多 5 次）
                retry_count += 1
                if retry_count > RECONNECT_MAX_RETRIES:
                    logger.error(
                        "OpenD connection lost and max retries (%d) exceeded. Giving up.",
                        RECONNECT_MAX_RETRIES
                    )
                    write_health("error", f"Max reconnect retries ({RECONNECT_MAX_RETRIES}) exceeded")
                    sys.exit(1)

                wait_seconds = RECONNECT_BASE_INTERVAL * (2 ** (retry_count - 1))
                logger.warning(
                    "OpenD connection error (attempt %d/%d): %s. "
                    "Reconnecting in %ds...",
                    retry_count, RECONNECT_MAX_RETRIES, e, wait_seconds
                )
                write_health("reconnecting", f"Reconnecting ({retry_count}/{RECONNECT_MAX_RETRIES}): {e}")

                # 等待期间每秒检查一次 SIGTERM
                for _ in range(wait_seconds):
                    if _shutdown_requested:
                        break
                    time.sleep(1)
                if _shutdown_requested:
                    break

                try:
                    futu_client.reconnect()
                    logger.info("Reconnected to OpenD (attempt %d)", retry_count)
                    retry_count = 0  # 重连成功后重置计数器
                except Exception as re:
                    logger.error("Reconnect attempt %d failed: %s", retry_count, re)
                    # 继续外层循环，下次迭代会再次判断是否超限

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        write_health("stopped", "Interrupted by user (KeyboardInterrupt)")
    finally:
        futu_client.disconnect()
        logger.info("Disconnected from OpenD")
        logger.info("AI Quant Data Subsystem stopped")


def cmd_export(args) -> None:
    """导出K线数据到文件（Parquet / CSV）。"""
    setup_logging()
    logger = logging.getLogger("main.export")
    from export.exporter import export_klines
    try:
        output_path = export_klines(
            stock_code=args.stock_code,
            period=args.period,
            start_date=args.start,
            end_date=args.end,
            adj_type=args.adj_type,
            fmt=args.fmt,
            output_dir=args.output_dir,
            db_path=DB_PATH,
        )
        logger.info("Export successful: %s", output_path)
        print(output_path)
    except (ValueError, ImportError) as e:
        logger.error("Export failed: %s", e)
        sys.exit(1)


def cmd_migrate(_args) -> None:
    """
    迁移数据库表结构并同步 watchlist 股票名称到 DB（幂等，无需 Futu 连接）。

    两件事：
    1. init_db()  — 建表 / ALTER TABLE 补列，兼容空库（首次安装）和旧库（升级）
    2. 读取 watchlist.json，将所有股票（含 name 字段）upsert 到 stocks 表
       · 仅做 upsert，不执行停用/差异检测（避免无 Futu 连接时产生副作用）
       · watchlist.json 不存在时跳过步骤 2，仅做表结构迁移

    适合在 deploy.sh / start.sh 中调用。
    """
    setup_logging()
    logger = logging.getLogger("main.migrate")

    # ── 1. 表结构迁移 ────────────────────────────────────────────────
    logger.info("Running DB schema migration: %s", DB_PATH)
    init_db(DB_PATH)
    logger.info("DB schema migration complete")

    # ── 2. watchlist 股票 upsert（含 name 字段） ─────────────────────
    from config.settings import WATCHLIST_PATH
    from db.repositories.stock_repo import StockRepository

    if not os.path.exists(WATCHLIST_PATH):
        logger.warning(
            "watchlist.json not found at %s — skipping stock name sync (OK for fresh install)",
            WATCHLIST_PATH,
        )
        return

    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load watchlist.json: %s — skipping stock name sync", e)
        return

    from models.stock import Stock as _Stock

    stocks = []
    for market_node in data.get("markets", []):
        market = market_node.get("market", "")
        market_enabled = bool(market_node.get("enabled", True))
        for item in market_node.get("stocks", []):
            try:
                stock_active = bool(item.get("is_active", True))
                stocks.append(_Stock(
                    stock_code=item["stock_code"],
                    market=market,
                    asset_type=item["asset_type"],
                    is_active=market_enabled and stock_active,
                    lot_size=int(item.get("lot_size", 1)),
                    currency=item["currency"],
                    name=item.get("name"),
                ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Invalid watchlist entry %s: %s", item, e)

    if not stocks:
        logger.warning("No valid stocks in watchlist.json — skipping upsert")
        return

    stock_repo = StockRepository(DB_PATH)
    stock_repo.upsert_many(stocks)
    logger.info("Stock upsert complete: %d stocks (name field synced)", len(stocks))


def cmd_stats(_args) -> None:
    """打印各股票同步状态汇总（E3）。"""
    setup_logging()
    logger = logging.getLogger("main.stats")
    init_db(DB_PATH)

    sync_meta_repo = SyncMetaRepository(DB_PATH)
    stock_repo = StockRepository(DB_PATH)

    from config.settings import ALL_PERIODS
    from models.enums import SyncStatus

    stocks = stock_repo.get_all()
    active = [s for s in stocks if s.is_active]
    inactive = [s for s in stocks if not s.is_active]

    print(f"\n{'='*64}")
    print(f"  AI Quant Data Subsystem — Sync Stats  (DB: {DB_PATH})")
    print(f"{'='*64}")
    print(f"  Active stocks  : {len(active)}")
    print(f"  Inactive stocks: {len(inactive)}")
    print(f"{'='*64}")

    status_counts = {s.value: 0 for s in SyncStatus}
    for stock in active:
        for period in ALL_PERIODS:
            meta = sync_meta_repo.get(stock.stock_code, period)
            status = meta["sync_status"] if meta else "no_record"
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts.setdefault(status, 0)
                status_counts[status] += 1

    print(f"\n  Sync status summary ({len(active)} stocks × {len(ALL_PERIODS)} periods):")
    for status, count in sorted(status_counts.items()):
        print(f"    {status:<12}: {count}")

    # 列出 failed 记录（最多 20 条）
    failed = sync_meta_repo.get_all_by_status(SyncStatus.FAILED.value)
    if failed:
        print(f"\n  ⚠  Failed records ({len(failed)}):")
        for rec in failed[:20]:
            print(f"    {rec['stock_code']:<16} [{rec['period']}]  {rec.get('error_message', '')[:60]}")
        if len(failed) > 20:
            print(f"    ... and {len(failed) - 20} more")

    # 列出有 open gaps 的股票
    gap_repo = GapRepository(DB_PATH)
    open_gaps = gap_repo.get_all_open_gaps() if hasattr(gap_repo, "get_all_open_gaps") else []
    if open_gaps:
        print(f"\n  ⚠  Open data gaps ({len(open_gaps)}):")
        for g in open_gaps[:20]:
            print(f"    {g['stock_code']:<16} [{g['period']}]  {g['gap_start']}~{g['gap_end']}")
        if len(open_gaps) > 20:
            print(f"    ... and {len(open_gaps) - 20} more")

    print(f"\n{'='*64}\n")
    logger.info("Stats command completed")


def setup_logging_check_gaps() -> None:
    """配置 check-gaps 专用日志（写入独立文件 logs/check_gaps_YYYYMMDD.log）。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"check_gaps_{date.today().strftime('%Y%m%d')}.log")

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


def cmd_check_gaps(args) -> None:
    """
    独立空洞检测子命令（只检测，不修复）。

    无需 Futu 连接，只读本地数据库。
    检测结果持久化到 data_gaps 表（status=open），并输出日志和终端汇总。
    """
    setup_logging_check_gaps()
    logger = logging.getLogger("main.check_gaps")

    from config.settings import ALL_PERIODS, DEFAULT_HISTORY_START, A_STOCK_CALENDAR_MARKET
    from db.repositories.calendar_repo import CalendarRepository
    from db.repositories.gap_repo import GapRepository
    from db.repositories.kline_repo import KlineRepository
    from db.repositories.stock_repo import StockRepository
    from core.gap_detector import GapDetector

    today_str = date.today().strftime("%Y-%m-%d")

    # 确定检测周期
    periods = args.period if args.period else ALL_PERIODS

    # 初始化数据库
    init_db(DB_PATH)

    # 获取股票列表
    stock_repo = StockRepository(DB_PATH)
    if args.stock:
        stock = stock_repo.get_by_code(args.stock)
        if stock is None:
            logger.warning("Stock %s not found in stocks table, skipping.", args.stock)
            print(f"\nWARNING: Stock {args.stock} not found in stocks table.\n")
            return
        stocks_to_check = [stock]
    else:
        all_stocks = stock_repo.get_all()
        stocks_to_check = [s for s in all_stocks if s.is_active]

    total_stocks = len(stocks_to_check)

    logger.info("=" * 60)
    logger.info(
        "check-gaps started. stocks=%d, periods=%s",
        total_stocks, periods
    )
    logger.info("DB: %s", DB_PATH)
    logger.info("Detect range: %s ~ %s", DEFAULT_HISTORY_START, today_str)
    logger.info("=" * 60)

    # 终端输出头部
    print("\n" + "=" * 64)
    print(f"  AI Quant — check-gaps  ({today_str})")
    print("=" * 64)
    print(f"  Stocks checked : {total_stocks}")
    print(f"  Periods        : {', '.join(periods)}")
    print(f"  Detect range   : {DEFAULT_HISTORY_START} ~ {today_str}")
    print("=" * 64)
    print()

    # 初始化组件（无需 Futu 连接）
    calendar_repo = CalendarRepository(DB_PATH)
    kline_repo = KlineRepository(DB_PATH)
    gap_repo = GapRepository(DB_PATH)
    gap_detector = GapDetector(calendar_repo, kline_repo)

    # 汇总统计
    stocks_with_gaps = 0
    total_gaps_found = 0
    total_gaps_persisted = 0

    for idx, stock in enumerate(stocks_to_check, 1):
        logger.info("[%d/%d] Checking %s ...", idx, total_stocks, stock.stock_code)
        stock_has_gap = False
        stock_gap_summary = []  # (period, n_gaps, reason)

        for period in periods:
            # P1-01 修复：日历缺失时 GapDetector 返回空列表而不抛异常，
            # 必须在调用前主动检查，缺失则 WARNING + continue，避免误报 "no gaps"。
            calendar_market = A_STOCK_CALENDAR_MARKET if stock.market == "A" else stock.market
            if not calendar_repo.has_calendar(calendar_market, DEFAULT_HISTORY_START, today_str):
                logger.warning(
                    "  [%s] Trading calendar missing for %s [%s~%s], skipping gap detection.",
                    period, calendar_market, DEFAULT_HISTORY_START, today_str
                )
                stock_gap_summary.append((period, 0, "calendar_missing"))
                continue

            gaps = gap_detector.detect_gaps(
                stock_code=stock.stock_code,
                period=period,
                market=stock.market,
                start_date=DEFAULT_HISTORY_START,
                end_date=today_str,
            )

            n_gaps = len(gaps)

            if n_gaps == 0:
                logger.info("  [%s] No gaps found.", period)
                stock_gap_summary.append((period, 0, "ok"))
            else:
                # 迭代8 FEAT-check-gaps-log: 日期展示按周期转换（仅影响展示，不影响DB存储）
                def _format_gap_date(date_str: str, period: str) -> str:
                    """将空洞 trade_date 转为用户友好的展示日期。
                    - 1D: 原样返回
                    - 1W: 返回该周周一（date - timedelta(days=date.weekday())）
                    - 1M: 返回该月第一天（YYYY-MM-01）
                    """
                    from datetime import datetime as _dt, timedelta as _td
                    if period == '1D':
                        return date_str
                    if period == '1W':
                        d = _dt.strptime(date_str, '%Y-%m-%d').date()
                        monday = d - _td(days=d.weekday())
                        return monday.strftime('%Y-%m-%d')
                    if period == '1M':
                        return date_str[:7] + '-01'
                    return date_str

                gap_strs = [f"{_format_gap_date(s, period)}~{_format_gap_date(e, period)}" for s, e in gaps]
                logger.info(
                    "  [%s] Found %d gap(s): [%s]",
                    period, n_gaps, ", ".join(gap_strs)
                )
                # 持久化到 data_gaps 表
                gap_repo.upsert_gaps(stock.stock_code, period, gaps)
                logger.info(
                    "  [%s] Persisted %d gap(s) to data_gaps (status=open).",
                    period, n_gaps
                )
                stock_has_gap = True
                total_gaps_found += n_gaps
                total_gaps_persisted += n_gaps
                stock_gap_summary.append((period, n_gaps, "gaps"))

        if stock_has_gap:
            stocks_with_gaps += 1

        # 终端输出每只股票的结论
        gap_periods = [(p, n) for p, n, reason in stock_gap_summary if reason == "gaps"]
        cal_missing_periods = [p for p, n, reason in stock_gap_summary if reason == "calendar_missing"]
        if gap_periods:
            details = ", ".join(f"[{p}]: {n} gap(s)" for p, n in gap_periods)
            print(f"  Checking {stock.stock_code:<16} ...  ⚠  {details}")
        elif cal_missing_periods:
            missing_str = ", ".join(f"[{p}]" for p in cal_missing_periods)
            print(f"  Checking {stock.stock_code:<16} ...  ⚠  calendar missing for {missing_str} (skipped)")
        else:
            print(f"  Checking {stock.stock_code:<16} ...  OK (no gaps)")

    logger.info("=" * 60)
    logger.info("check-gaps completed.")
    logger.info("Stocks checked : %d", total_stocks)
    logger.info("Stocks with gaps: %d", stocks_with_gaps)
    logger.info("Total gaps found: %d", total_gaps_found)
    logger.info("=" * 60)

    # 终端汇总
    print()
    print("=" * 64)
    print("  Summary:")
    print(f"    Stocks with gaps : {stocks_with_gaps} / {total_stocks}")
    print(f"    Total gaps found : {total_gaps_found}")
    print(f"    Persisted to DB  : {total_gaps_persisted}  (data_gaps, status=open)")
    print()
    print("  Run `python main.py sync` to repair gaps automatically.")
    print("=" * 64 + "\n")


def cmd_repair(args) -> None:
    """
    K线数据强制修复子命令（需要 Futu OpenD 连接）。

    对指定股票/周期/日期执行强制 upsert 覆盖写入，用于手动修复异常数据。
    不修改 sync_metadata 表。
    """
    # 参数验证：--date 格式
    try:
        target_date = date.fromisoformat(args.date)
    except ValueError:
        print(f"\nERROR: Invalid date format '{args.date}'. Expected YYYY-MM-DD.\n", file=sys.stderr)
        sys.exit(1)

    today_date = date.today()
    if target_date > today_date:
        print(f"\nWARNING: --date {args.date} is in the future. Futu API may return empty data.\n")

    setup_logging()
    logger = logging.getLogger("main.repair")

    from config.settings import ALL_PERIODS

    periods = args.period if args.period else ALL_PERIODS

    # 初始化数据库
    init_db(DB_PATH)

    # 连接 Futu OpenD
    futu_client = FutuClient(OPEND_HOST, OPEND_PORT)
    try:
        futu_client.connect()
    except Exception as e:
        logger.error("Failed to connect to OpenD: %s", e)
        logger.error("Please ensure OpenD is running at %s:%d", OPEND_HOST, OPEND_PORT)
        sys.exit(1)

    try:
        deps = build_dependencies(futu_client)
        stock_repo = deps["stock_repo"]   # P2-02：直接用 deps 中的实例，避免重复实例化
        sync_engine: SyncEngine = deps["sync_engine"]

        # 确定修复股票列表
        if args.stock:
            stock = stock_repo.get_by_code(args.stock)
            if stock is None:
                logger.warning("Stock %s not found in stocks table, skipping.", args.stock)
                print(f"\nWARNING: Stock {args.stock} not found in stocks table.\n")
                return
            stocks_to_repair = [stock]
        else:
            all_stocks = stock_repo.get_all()
            stocks_to_repair = [s for s in all_stocks if s.is_active]

        total_stocks = len(stocks_to_repair)

        # P2-01：repair started 日志移到股票列表确定后，包含 stocks=N 字段
        logger.info("=" * 60)
        logger.info(
            "repair started. date=%s, stocks=%d, periods=%s",
            args.date, total_stocks, periods
        )
        logger.info("=" * 60)

        # 终端输出头部
        print("\n" + "=" * 64)
        print(f"  AI Quant — repair  (target date: {args.date})")
        print("=" * 64)
        print(f"  Stocks  : {total_stocks}")
        print(f"  Periods : {', '.join(periods)}")
        print("=" * 64)
        print()

        # 计算各周期的 fetch 区间（业务日期 → fetch 区间映射）
        def calc_fetch_range(period: str) -> tuple:
            """根据周期计算 fetch_start 和 fetch_end。"""
            today_str = today_date.strftime("%Y-%m-%d")
            if period == "1D":
                return args.date, args.date
            elif period == "1W":
                # fetch_start = 该date所在周的周一
                # fetch_end   = 该date所在周的周日，若超过 today 则取 today
                week_start = target_date - timedelta(days=target_date.weekday())
                week_end = week_start + timedelta(days=6)
                if week_end > today_date:
                    week_end = today_date
                return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")
            elif period == "1M":
                # fetch_start = 该date所在月的1日
                # fetch_end   = 该date所在月的最后一天，若超过 today 则取 today
                month_start = target_date.replace(day=1)
                # 月末：下月1日 - 1天
                if target_date.month == 12:
                    month_end = date(target_date.year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)
                if month_end > today_date:
                    month_end = today_date
                return month_start.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")
            else:
                return args.date, args.date

        # 执行修复
        total_tasks = total_stocks * len(periods)
        task_idx = 0
        total_fetched = 0
        total_upserted = 0
        total_failed = 0

        for stock_idx, stock in enumerate(stocks_to_repair, 1):
            for period in periods:
                task_idx += 1
                fetch_start, fetch_end = calc_fetch_range(period)

                logger.info(
                    "[%d/%d] Repairing %s [%s]: fetch_range=%s~%s",
                    task_idx, total_tasks, stock.stock_code, period, fetch_start, fetch_end
                )

                # 确保交易日历已存在
                try:
                    sync_engine._ensure_calendar(stock.market, fetch_start, fetch_end)
                except Exception as e:
                    logger.warning(
                        "Failed to ensure calendar for %s [%s]: %s",
                        stock.stock_code, period, e
                    )

                try:
                    rows_fetched, rows_upserted = sync_engine.repair_one(
                        stock=stock,
                        period=period,
                        fetch_start=fetch_start,
                        fetch_end=fetch_end,
                    )
                    total_fetched += rows_fetched
                    total_upserted += rows_upserted
                    logger.info(
                        "[%d/%d] %s [%s] done: fetched=%d, upserted=%d",
                        task_idx, total_tasks, stock.stock_code, period,
                        rows_fetched, rows_upserted
                    )
                    print(
                        f"  [{task_idx}/{total_tasks}] {stock.stock_code:<12} [{period}]  "
                        f"{fetch_start}~{fetch_end}  →  "
                        f"fetched={rows_fetched}, upserted={rows_upserted}  ✓"
                    )
                except Exception as e:
                    total_failed += 1
                    logger.error(
                        "[%d/%d] %s [%s] FAILED: %s",
                        task_idx, total_tasks, stock.stock_code, period, e, exc_info=True
                    )
                    print(
                        f"  [{task_idx}/{total_tasks}] {stock.stock_code:<12} [{period}]  "
                        f"{fetch_start}~{fetch_end}  →  ERROR: {e}  ✗"
                    )

        logger.info("=" * 60)
        logger.info(
            "repair completed. total_fetched=%d, total_upserted=%d, total_failed=%d",
            total_fetched, total_upserted, total_failed
        )
        logger.info("=" * 60)

        # 终端汇总
        print()
        print("=" * 64)
        print("  Summary:")
        print(f"    Total fetched  : {total_fetched}")
        print(f"    Total upserted : {total_upserted}")
        if total_failed > 0:
            print(f"    Failed         : {total_failed}  ← check logs for details")
        print("=" * 64 + "\n")

    finally:
        futu_client.disconnect()
        logger.info("Disconnected from OpenD")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="AI Quant Data Subsystem — 数据采集子系统（禁止交易逻辑）",
    )
    subparsers = parser.add_subparsers(dest="command")

    # 默认子命令：sync
    sub_sync = subparsers.add_parser("sync", help="执行历史数据同步（默认）")
    sub_sync.set_defaults(func=cmd_sync)

    # 子命令：export
    sub_export = subparsers.add_parser("export", help="导出K线数据到文件")
    sub_export.add_argument("stock_code", help="股票代码，如 SH.600519")
    sub_export.add_argument("period", choices=["1D", "1W", "1M"], help="K线周期")
    sub_export.add_argument("start", metavar="START_DATE", help="起始日期 YYYY-MM-DD")
    sub_export.add_argument("end", metavar="END_DATE", help="结束日期 YYYY-MM-DD")
    sub_export.add_argument(
        "--adj-type", dest="adj_type", choices=["qfq", "raw"], default="qfq",
        help="复权类型（默认 qfq 前复权）",
    )
    sub_export.add_argument(
        "--fmt", choices=["parquet", "csv"], default="parquet",
        help="输出格式（默认 parquet）",
    )
    sub_export.add_argument(
        "--output-dir", dest="output_dir", default=EXPORT_DIR,
        help=f"输出目录（默认 {EXPORT_DIR}）",
    )
    sub_export.set_defaults(func=cmd_export)

    # 子命令：migrate
    sub_migrate = subparsers.add_parser(
        "migrate",
        help="迁移 DB 表结构并同步 watchlist 股票名称（幂等，无需 Futu 连接）",
    )
    sub_migrate.set_defaults(func=cmd_migrate)

    # 子命令：stats
    sub_stats = subparsers.add_parser("stats", help="打印同步状态汇总")
    sub_stats.set_defaults(func=cmd_stats)

    # 子命令：check-gaps
    sub_check_gaps = subparsers.add_parser(
        "check-gaps",
        help="独立空洞检测（只检测，不修复；检测结果写入 data_gaps 表）"
    )
    sub_check_gaps.add_argument(
        "--stock", dest="stock", default=None,
        help="指定股票代码（不传则检测所有活跃股票）"
    )
    sub_check_gaps.add_argument(
        "--period", dest="period", nargs="+", choices=["1D", "1W", "1M"], default=None,
        help="指定周期（可多选：1D 1W 1M；不传则检测全部）"
    )
    sub_check_gaps.set_defaults(func=cmd_check_gaps)

    # 子命令：repair
    sub_repair = subparsers.add_parser(
        "repair",
        help="强制 upsert 覆盖指定日期的 K 线数据（需要富途 OpenD 连接）"
    )
    sub_repair.add_argument(
        "--date", dest="date", required=True, metavar="YYYY-MM-DD",
        help="目标业务日期，如 2026-03-19"
    )
    sub_repair.add_argument(
        "--stock", dest="stock", default=None,
        help="指定股票代码（不传则修复所有活跃股票）"
    )
    sub_repair.add_argument(
        "--period", dest="period", nargs="+", choices=["1D", "1W", "1M"], default=None,
        help="指定周期（可多选；不传则修复全部）"
    )
    sub_repair.set_defaults(func=cmd_repair)

    args = parser.parse_args()

    # 默认无子命令时执行 sync
    if args.command is None:
        args.func = cmd_sync

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
