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
            if last >= today:
                # 上次已同步到今天（含盘中半日），本次仍从今天开始，确保当日数据被 upsert 覆盖
                start_date = today
            else:
                y, m, d = last.split("-")
                start_date = (date(int(y), int(m), int(d)) + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            start_date = DEFAULT_HISTORY_START

        # 强制回溯最近2个周期，确保最后几条数据被 upsert 覆盖
        # 全量/重激活场景不做回溯（start_date 本来就是最早起点）
        fetch_start = start_date
        if not force_full and not is_reactivated:
            rollback_start = self._calc_rollback_start(period, start_date, stock.market)
            if rollback_start < start_date:
                fetch_start = rollback_start
                logger.info(
                    "Sync %s [%s]: rollback_start=%s (extended from %s), fetch_range=%s~%s",
                    stock_code, period, rollback_start, start_date, fetch_start, today
                )
        else:
            rollback_start = start_date

        # 2a. 已是最新，跳过（1W/1M 末日推算可能超出今天）
        if fetch_start > today:
            logger.info(
                "Sync %s [%s]: fetch_start=%s > today=%s, already up-to-date, skipping",
                stock_code, period, fetch_start, today
            )
            return

        logger.info(
            "Sync %s [%s]: fetch_start=%s, rollback_start=%s, end_date=%s",
            stock_code, period, fetch_start, rollback_start, today
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
            stock, period, fetch_start, today,
            latest_date=rollback_start if (not force_full and not is_reactivated) else today
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

    def _calc_rollback_start(self, period: str, start_date: str, market: str) -> str:
        """
        计算回溯覆盖起始日。
        覆盖规则（老板确认 2026-03-20）：
          1D：当日 + 前2个交易日 → upsert_from = T-2（查交易日历精确计算）
          1W：当周 + 上周 → upsert_from = 上周一
          1M：当月 + 上个月 → upsert_from = 上个月1日
        """
        today = date.today()

        if period == "1D":
            # 查交易日历，取 start_date 之前（含）往前第3个交易日 = T-2
            # 注意：此处在 _ensure_calendar 之前调用，依赖上次 sync 已写入日历；
            # force_full/is_reactivated 场景不走此分支，故首次 full_sync 无影响。
            # 若日历缺失，则静默 fallback 至 start_date（不回溯，安全兜底）。
            calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market
            query_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            trading_days = self._calendar_repo.get_trading_days(
                calendar_market, query_start,
                (today - timedelta(days=1)).strftime("%Y-%m-%d")  # 昨天及之前的交易日
            )
            if len(trading_days) >= 2:
                return trading_days[-2]   # T-2：前2个交易日
            elif len(trading_days) >= 1:
                return trading_days[-1]   # 兜底：只有1个交易日
            return start_date             # 兜底：日历不足

        elif period == "1W":
            # 上周一 = 本周一 - 7天
            this_monday = today - timedelta(days=today.weekday())  # 本周一
            last_monday = this_monday - timedelta(days=7)           # 上周一
            rollback = last_monday
            return max(rollback, date.fromisoformat(DEFAULT_HISTORY_START)).strftime("%Y-%m-%d")

        elif period == "1M":
            # 上个月1日
            if today.month == 1:
                last_month_first = date(today.year - 1, 12, 1)
            else:
                last_month_first = date(today.year, today.month - 1, 1)
            rollback = last_month_first
            return max(rollback, date.fromisoformat(DEFAULT_HISTORY_START)).strftime("%Y-%m-%d")

        else:
            return start_date

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
        self, stock: Stock, period: str, start_date: str, end_date: str,
        latest_date: str = None,
    ) -> Tuple[int, int]:
        """拉取并存储K线数据，返回 (rows_fetched, rows_inserted)。

        写入策略：
          - latest_date（通常为 today）当日的 bar → upsert_many（INSERT OR CONFLICT DO UPDATE）
            保证进程中途退出后重启时，当日半日数据可被最新数据覆盖写。
          - 早于 latest_date 的历史 bar → insert_many（INSERT OR IGNORE）
            历史数据不重复写入，保持幂等。
          - latest_date 为 None 时，全部使用 insert_many（兼容旧调用路径）。
        """
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
            if latest_date is None:
                self._kline_repo.insert_many(invalid_bars)
            else:
                inv_history = [b for b in invalid_bars if b.trade_date < latest_date]
                inv_latest  = [b for b in invalid_bars if b.trade_date >= latest_date]
                if inv_history:
                    self._kline_repo.insert_many(inv_history)
                if inv_latest:
                    self._kline_repo.upsert_many(inv_latest)

        # rows_inserted 仅统计有效行写入数；invalid_bars 写入量见上方 WARNING 日志
        if latest_date is None:
            # 兼容旧路径：全部 INSERT OR IGNORE
            rows_inserted = self._kline_repo.insert_many(valid_bars)
        else:
            # 区分历史日期与最新交易日，分别使用不同写入策略
            history_bars = [b for b in valid_bars if b.trade_date < latest_date]
            latest_bars  = [b for b in valid_bars if b.trade_date >= latest_date]
            rows_inserted = 0
            if history_bars:
                rows_inserted += self._kline_repo.insert_many(history_bars)
            if latest_bars:
                rows_inserted += self._kline_repo.upsert_many(latest_bars)
                logger.debug(
                    "Upserted %d bar(s) for %s [%s] on latest_date=%s",
                    len(latest_bars), stock_code, period, latest_date,
                )
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

    def repair_one(
        self,
        stock: Stock,
        period: str,
        fetch_start: str,
        fetch_end: str,
    ) -> Tuple[int, int]:
        """
        强制 upsert 覆盖指定区间的 K 线数据。

        与 _fetch_and_store 的区别：
        - 所有数据（包括历史日期）全部走 upsert_many（覆盖写）
        - 不区分 latest_date，不更新 sync_metadata

        Returns:
            (rows_fetched, rows_upserted)
        """
        stock_code = stock.stock_code
        bars = self._fetch_klines_paged(stock_code, period, fetch_start, fetch_end)

        rows_fetched = len(bars)
        if not bars:
            logger.info(
                "repair_one %s [%s] %s~%s: no data returned from API",
                stock_code, period, fetch_start, fetch_end
            )
            return 0, 0

        valid_bars, invalid_bars = self._validator.validate_many(bars)
        rows_upserted = 0
        if valid_bars:
            rows_upserted += self._kline_repo.upsert_many(valid_bars)
        if invalid_bars:
            self._kline_repo.upsert_many(invalid_bars)  # invalid 也覆盖写
            logger.warning(
                "%d invalid bars for %s [%s], upserted with is_valid=0",
                len(invalid_bars), stock_code, period
            )
        logger.info(
            "repair_one %s [%s] %s~%s: fetched=%d, upserted=%d",
            stock_code, period, fetch_start, fetch_end, rows_fetched, rows_upserted
        )
        return rows_fetched, rows_upserted
