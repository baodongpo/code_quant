import logging
from datetime import date, timedelta
from typing import List

from db.repositories.kline_repo import KlineRepository
from db.repositories.adjust_factor_repo import AdjustFactorRepository
from models.kline import KlineBar, AdjustFactor

logger = logging.getLogger(__name__)


class AdjustmentService:
    """
    动态计算前复权价格序列。
    原始价格存储在 kline_data 表，复权因子存储在 adjust_factors 表。
    本服务在算法层动态转换，不修改数据库中的原始价格。
    """

    def __init__(
        self,
        kline_repo: KlineRepository,
        adjust_factor_repo: AdjustFactorRepository,
    ):
        self._kline_repo = kline_repo
        self._adjust_factor_repo = adjust_factor_repo

    def get_adjusted_klines(
        self,
        stock_code: str,
        period: str,
        start_date: str,
        end_date: str,
        adj_type: str = "qfq",  # 目前仅支持前复权 "qfq"
    ) -> List[KlineBar]:
        """
        返回前复权后的K线列表。

        前复权逻辑：
          对每个交易日 t，前复权价格 = 原始价格 × ∏(所有 ex_date > t 的 forward_factor)
          即：越早的历史数据，乘以越多的复权因子（因为经历了更多的除权事件）

        Args:
            stock_code: 股票代码
            period: K线周期 ("1D", "1W", "1M")
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            adj_type: 复权类型，目前仅支持 "qfq"（前复权）

        Returns:
            已调整价格的 KlineBar 列表，is_adjusted=True
        """
        if adj_type != "qfq":
            raise ValueError(f"Unsupported adj_type: {adj_type}. Only 'qfq' is supported.")

        # 1. 读取原始价格序列
        raw_bars = self._kline_repo.get_bars(stock_code, period, start_date, end_date)
        if not raw_bars:
            return []

        # 2. 读取所有复权因子（按 ex_date 升序）
        factors = self._adjust_factor_repo.get_factors(stock_code)
        if not factors:
            # 无复权事件，直接返回原始价格（标记为已调整，但值不变）
            return [self._mark_adjusted(b) for b in raw_bars]

        # 3. 构建前复权系数映射
        # 对每个交易日 t，OHLC 使用 t 日系数；last_close 语义为 t-1 日收盘价，使用 t-1 日系数
        adjusted_bars = []
        for bar in raw_bars:
            A, B = self._calc_forward_multiplier(bar.trade_date, factors)
            prev_date = (date.fromisoformat(bar.trade_date) - timedelta(days=1)).isoformat()
            A_prev, B_prev = self._calc_forward_multiplier(prev_date, factors)
            adjusted_bars.append(self._apply_adjustment(bar, A, B, A_prev, B_prev))

        logger.debug(
            "Adjusted %d bars for %s [%s] from %s to %s",
            len(adjusted_bars), stock_code, period, start_date, end_date
        )
        return adjusted_bars

    @staticmethod
    def _calc_forward_multiplier(trade_date: str, factors: List[AdjustFactor]) -> tuple:
        """
        计算指定交易日的前复权系数 (A, B)，使得：
            adj_price = raw_price × A + B

        前复权逻辑：将 ex_date > trade_date 的所有除权事件，
        按时间从近到远（倒序）依次复合：
            (A, B) 初始为 (1.0, 0.0)
            对每个事件 (a, b)（由近到远）：
                A_new = A × a
                B_new = B × a + b
        等价于：price_adj = (...((price × a_n + b_n) × a_{n-1} + b_{n-1})...) × a_1 + b_1
        """
        # 筛选出 ex_date > trade_date 的事件，按时间倒序排列（最近的先处理）
        relevant = [f for f in factors if f.ex_date > trade_date]
        relevant.sort(key=lambda f: f.ex_date, reverse=True)

        A, B = 1.0, 0.0
        for f in relevant:
            a, b = f.forward_factor, f.forward_factor_b
            A = A * a
            B = B * a + b
        return A, B

    @staticmethod
    def _apply_adjustment(bar: KlineBar, A: float, B: float, A_prev: float, B_prev: float) -> KlineBar:
        """
        将前复权系数应用到价格字段：adj = raw × A + B。
        - OHLC 使用当日系数 (A, B)
        - last_close 使用前一日系数 (A_prev, B_prev)，保证除权日 last_close == 前一日 close
        - volume 不调整
        """
        return KlineBar(
            stock_code=bar.stock_code,
            period=bar.period,
            trade_date=bar.trade_date,
            open=round(bar.open * A + B, 4),
            high=round(bar.high * A + B, 4),
            low=round(bar.low * A + B, 4),
            close=round(bar.close * A + B, 4),
            volume=bar.volume,
            turnover=bar.turnover,
            pe_ratio=bar.pe_ratio,
            turnover_rate=bar.turnover_rate,
            last_close=round(bar.last_close * A_prev + B_prev, 4) if bar.last_close is not None else None,
            is_valid=bar.is_valid,
            is_adjusted=True,
        )

    @staticmethod
    def _mark_adjusted(bar: KlineBar) -> KlineBar:
        return KlineBar(
            stock_code=bar.stock_code,
            period=bar.period,
            trade_date=bar.trade_date,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            turnover=bar.turnover,
            pe_ratio=bar.pe_ratio,
            turnover_rate=bar.turnover_rate,
            last_close=bar.last_close,
            is_valid=bar.is_valid,
            is_adjusted=True,
        )
