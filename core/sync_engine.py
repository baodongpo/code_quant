import logging
import math
from datetime import date, timedelta
from typing import Callable, List, Optional, Set, Tuple

from config.settings import ALL_PERIODS, DEFAULT_HISTORY_START, A_STOCK_CALENDAR_MARKET, RATE_LIMIT_MIN_INTERVAL, RATE_LIMIT_MAX_IN_WINDOW, RATE_LIMIT_WINDOW_SECONDS
from core.gap_detector import GapDetector
from core.rate_limiter import GeneralRateLimiter
from core.validator import KlineValidator
from db.repositories.adjust_factor_repo import AdjustFactorRepository
from db.repositories.calendar_repo import CalendarRepository
from db.repositories.gap_repo import GapRepository
from db.repositories.kline_repo import KlineRepository
from db.repositories.sync_meta_repo import SyncMetaRepository
from futu_wrap.adjust_factor_fetcher import AdjustFactorFetcher
from futu_wrap.calendar_fetcher import CalendarFetcher
from futu_wrap.kline_fetcher import KlineFetcher
from models.enums import SyncStatus
from models.stock import Stock

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    核心同步编排器。
    负责全量历史拉取、增量同步、空洞检测与修复。
    绝对禁止任何自动交易逻辑。
    """

    def __init__(
        self,
        kline_repo: KlineRepository,
        calendar_repo: CalendarRepository,
        sync_meta_repo: SyncMetaRepository,
        gap_repo: GapRepository,
        adjust_factor_repo: AdjustFactorRepository,
        kline_fetcher: KlineFetcher,
        calendar_fetcher: CalendarFetcher,
        adjust_factor_fetcher: AdjustFactorFetcher,
        gap_detector: GapDetector,
        validator: KlineValidator,
        general_rate_limiter: GeneralRateLimiter,
    ):
        self._kline_repo = kline_repo
        self._calendar_repo = calendar_repo
        self._sync_meta_repo = sync_meta_repo
        self._gap_repo = gap_repo
        self._adjust_factor_repo = adjust_factor_repo
        self._kline_fetcher = kline_fetcher
        self._calendar_fetcher = calendar_fetcher
        self._adjust_factor_fetcher = adjust_factor_fetcher
        self._gap_detector = gap_detector
        self._validator = validator
        self._general_rate_limiter = general_rate_limiter

    def recover_running_states(self) -> List[str]:
        """
        启动恢复：将上次宕机时残留的 RUNNING 状态重置为 PENDING。
        返回被重置的 (stock_code, period) 对应的 stock_code 列表（去重），
        调用方应对这些股票强制执行空洞检测（等同 is_reactivated=True）。
        """
        running_records = self._sync_meta_repo.get_all_by_status(SyncStatus.RUNNING.value)
        if not running_records:
            return []
        recovered_codes = []
        for rec in running_records:
            stock_code = rec["stock_code"]
            period = rec["period"]
            self._sync_meta_repo.set_status(stock_code, period, SyncStatus.PENDING.value)
            logger.warning(
                "Recovered dirty RUNNING state for %s [%s] → pending (crash recovery)",
                stock_code, period
            )
            if stock_code not in recovered_codes:
                recovered_codes.append(stock_code)
        logger.info("Crash recovery: reset %d RUNNING records for %d stocks",
                    len(running_records), len(recovered_codes))
        return recovered_codes

    def run_full_sync(
        self,
        active_stocks: List[Stock],
        newly_added: List[Stock],
        reactivated: List[Stock],
        shutdown_flag: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        对所有活跃股票执行同步。
        - newly_added: 强制全量历史拉取
        - reactivated: 从 first_sync_date 开始补洞
        - 其余: 增量同步（从上次成功同步日期开始）
        - shutdown_flag: 可选回调，返回 True 时在股票边界优雅退出
        """
        newly_added_codes: Set[str] = {s.stock_code for s in newly_added}
        reactivated_codes: Set[str] = {s.stock_code for s in reactivated}
        today = date.today().strftime("%Y-%m-%d")

        total = len(active_stocks)
        # E1：预估同步耗时（每只股票每个周期至少 1 次 API 调用，按 RATE_LIMIT_MIN_INTERVAL 估算）
        num_periods = len(ALL_PERIODS)
        estimated_seconds = total * num_periods * RATE_LIMIT_MIN_INTERVAL
        estimated_minutes = math.ceil(estimated_seconds / 60)
        logger.info(
            "Starting sync: %d stocks × %d periods. "
            "Estimated min time ~%d min (rate_limit=%.1fs/req, actual may vary).",
            total, num_periods, estimated_minutes, RATE_LIMIT_MIN_INTERVAL
        )
        for idx, stock in enumerate(active_stocks, 1):
            # 检查 SIGTERM 优雅退出标志（在每只股票开始前检查）
            if shutdown_flag is not None and shutdown_flag():
                logger.warning(
                    "Shutdown requested, stopping sync at stock %d/%d (%s)",
                    idx, total, stock.stock_code
                )
                break
            force_full = stock.stock_code in newly_added_codes
            is_reactivated = stock.stock_code in reactivated_codes
            logger.info(
                "[%d/%d] Syncing %s (force_full=%s, reactivated=%s)",
                idx, total, stock.stock_code, force_full, is_reactivated
            )
            for period in ALL_PERIODS:
                try:
                    self._sync_one(
                        stock=stock,
                        period=period,
                        today=today,
                        force_full=force_full,
                        is_reactivated=is_reactivated,
                    )
                except Exception as e:
                    logger.error(
                        "Sync failed for %s [%s]: %s",
                        stock.stock_code, period, e, exc_info=True
                    )
                    self._sync_meta_repo.upsert(
                        stock_code=stock.stock_code,
                        period=period,
                        status=SyncStatus.FAILED.value,
                        error_message=str(e),
                    )

    def _sync_one(
        self,
        stock: Stock,
        period: str,
        today: str,
        force_full: bool = False,
        is_reactivated: bool = False,
    ) -> None:
        stock_code = stock.stock_code

        # 1. 确定同步起始日
        meta = self._sync_meta_repo.get(stock_code, period)
        if force_full or meta is None:
            start_date = DEFAULT_HISTORY_START
        elif is_reactivated and meta.get("first_sync_date"):
            start_date = meta["first_sync_date"]
        elif meta.get("last_sync_date"):
            last = meta["last_sync_date"]
            y, m, d = last.split("-")
            start_date = (date(int(y), int(m), int(d)) + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = DEFAULT_HISTORY_START

        # 2a. 已是最新，跳过（1W/1M 末日推算可能超出今天）
        if start_date > today:
            logger.info(
                "Sync %s [%s]: start_date=%s > today=%s, already up-to-date, skipping",
                stock_code, period, start_date, today
            )
            return

        logger.info(
            "Sync %s [%s]: start_date=%s, end_date=%s",
            stock_code, period, start_date, today
        )

        # 2. 标记运行中；force_full 时强制更新 first_sync_date
        self._sync_meta_repo.upsert(
            stock_code=stock_code,
            period=period,
            status=SyncStatus.RUNNING.value,
            first_sync_date=start_date if (force_full or meta is None) else None,
            force_first_sync_date=(force_full or meta is None),
        )

        # 3. 确保交易日历已存在（使用通用限频器）
        self._ensure_calendar(stock.market, start_date, today)

        # 4. 刷新复权因子（使用通用限频器，仅追加新事件）
        self._refresh_adjust_factors(stock_code)

        # 5. 拉取增量数据（先拉取再检测空洞，避免初次全量同步时双倍 API 调用）
        rows_fetched, rows_inserted = self._fetch_and_store(
            stock, period, start_date, today
        )

        # 6. 检测并修复剩余空洞（主拉取完成后再检测，初次同步后空洞应极少）
        self._heal_gaps(stock, period, start_date, today)

        # 7. 更新同步状态
        self._sync_meta_repo.upsert(
            stock_code=stock_code,
            period=period,
            status=SyncStatus.SUCCESS.value,
            last_sync_date=today,
            rows_fetched=rows_fetched,
            rows_inserted=rows_inserted,
        )
        logger.info(
            "Sync %s [%s] done: fetched=%d, inserted=%d",
            stock_code, period, rows_fetched, rows_inserted
        )

    def _ensure_calendar(self, market: str, start_date: str, end_date: str) -> None:
        """确保交易日历已存在，不足则从 API 拉取补充（使用通用限频器）。"""
        calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market

        if not self._calendar_repo.has_calendar(calendar_market, start_date, end_date):
            logger.info(
                "Fetching trading calendar for %s [%s~%s]",
                calendar_market, start_date, end_date
            )
            trading_days = self._general_rate_limiter.execute_with_retry(
                self._calendar_fetcher.fetch,
                calendar_market, start_date, end_date
            )
            if trading_days:
                self._calendar_repo.insert_many(calendar_market, trading_days)
                logger.info(
                    "Inserted %d trading days for %s", len(trading_days), calendar_market
                )

    def _refresh_adjust_factors(self, stock_code: str) -> None:
        """从 API 拉取复权因子，仅追加新事件（使用通用限频器）。"""
        logger.debug("Refreshing adjust factors for %s", stock_code)
        try:
            factors = self._general_rate_limiter.execute_with_retry(
                self._adjust_factor_fetcher.fetch_factors,
                stock_code
            )
            if factors:
                self._adjust_factor_repo.insert_new_only(factors)
                logger.debug(
                    "Upserted %d adjust factors for %s", len(factors), stock_code
                )
        except Exception as e:
            logger.warning(
                "Failed to refresh adjust factors for %s: %s", stock_code, e
            )

    def _heal_gaps(
        self, stock: Stock, period: str, start_date: str, end_date: str
    ) -> None:
        """检测并修复数据空洞（空洞补填使用历史K线限频器）。"""
        stock_code = stock.stock_code

        # 检测新空洞并持久化（failed 的会被重置为 open）
        gaps = self._gap_detector.detect_gaps(
            stock_code=stock_code,
            period=period,
            market=stock.market,
            start_date=start_date,
            end_date=end_date,
        )
        if gaps:
            self._gap_repo.upsert_gaps(stock_code, period, gaps)

        # 处理所有 open 状态的空洞（含刚重置的 failed）
        open_gaps = self._gap_repo.get_open_gaps(stock_code, period)
        for gap in open_gaps:
            gap_id = gap["id"]
            gap_start = gap["gap_start"]
            gap_end = gap["gap_end"]
            logger.info(
                "Filling gap %s [%s] %s~%s", stock_code, period, gap_start, gap_end
            )
            self._gap_repo.mark_filling(gap_id)
            try:
                bars = self._fetch_klines_paged(
                    stock_code, period, gap_start, gap_end
                )
                valid_bars, invalid_bars = self._validator.validate_many(bars)
                if valid_bars:
                    self._kline_repo.insert_many(valid_bars)
                if invalid_bars:
                    self._kline_repo.insert_many(invalid_bars)  # 以 is_valid=0 写入
                self._gap_repo.mark_filled(gap_id)
                logger.info(
                    "Gap filled %s [%s] %s~%s: %d valid, %d invalid",
                    stock_code, period, gap_start, gap_end,
                    len(valid_bars), len(invalid_bars)
                )
            except Exception as e:
                self._gap_repo.mark_failed(gap_id)
                logger.error(
                    "Gap fill failed %s [%s] %s~%s: %s",
                    stock_code, period, gap_start, gap_end, e
                )

    def _fetch_and_store(
        self, stock: Stock, period: str, start_date: str, end_date: str
    ) -> Tuple[int, int]:
        """拉取并存储K线数据，返回 (rows_fetched, rows_inserted)。"""
        stock_code = stock.stock_code
        bars = self._fetch_klines_paged(stock_code, period, start_date, end_date)

        rows_fetched = len(bars)
        if not bars:
            return 0, 0

        valid_bars, invalid_bars = self._validator.validate_many(bars)
        if invalid_bars:
            logger.warning(
                "%d invalid bars for %s [%s], storing with is_valid=0",
                len(invalid_bars), stock_code, period
            )
            self._kline_repo.insert_many(invalid_bars)  # is_valid=0 写入，供追查

        # rows_inserted 仅统计有效行写入数；invalid_bars 写入量见上方 WARNING 日志
        rows_inserted = self._kline_repo.insert_many(valid_bars)
        return rows_fetched, rows_inserted

    def _fetch_klines_paged(
        self, stock_code: str, period: str, start_date: str, end_date: str
    ) -> list:
        """
        分页拉取K线。
        RateLimiter.acquire() 已内置在 KlineFetcher.fetch() 的每页循环中，
        此处直接调用，无需外层 execute_with_retry 包装。
        """
        return self._kline_fetcher.fetch(stock_code, period, start_date, end_date)
