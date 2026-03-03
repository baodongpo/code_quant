import logging
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
        # 对每个交易日，找到所有 ex_date > trade_date 的因子，累乘其 forward_factor
        adjusted_bars = []
        for bar in raw_bars:
            multiplier = self._calc_forward_multiplier(bar.trade_date, factors)
            adjusted_bars.append(self._apply_adjustment(bar, multiplier))

        logger.debug(
            "Adjusted %d bars for %s [%s] from %s to %s",
            len(adjusted_bars), stock_code, period, start_date, end_date
        )
        return adjusted_bars

    @staticmethod
    def _calc_forward_multiplier(trade_date: str, factors: List[AdjustFactor]) -> float:
        """
        计算指定交易日的前复权乘数。

        前复权：对该日期之后发生的所有除权事件，将其 forward_factor 累乘。
        即：历史价格需要向前调整，以匹配当前价格量级。

        注意：富途 forward_factor 是累乘值（已经是从最早到该除权日的累积因子）。
        如果 SDK 返回的是每次除权的单次因子，则需要累乘所有 ex_date > trade_date 的因子。
        """
        multiplier = 1.0
        for factor in factors:
            # 除权日严格大于交易日时，该除权事件影响历史数据
            if factor.ex_date > trade_date:
                multiplier *= factor.forward_factor
        return multiplier

    @staticmethod
    def _apply_adjustment(bar: KlineBar, multiplier: float) -> KlineBar:
        """将复权乘数应用到 OHLC 价格。volume 不调整。"""
        from dataclasses import replace
        return KlineBar(
            stock_code=bar.stock_code,
            period=bar.period,
            trade_date=bar.trade_date,
            open=round(bar.open * multiplier, 4),
            high=round(bar.high * multiplier, 4),
            low=round(bar.low * multiplier, 4),
            close=round(bar.close * multiplier, 4),
            volume=bar.volume,
            turnover=bar.turnover,
            pe_ratio=bar.pe_ratio,
            turnover_rate=bar.turnover_rate,
            last_close=round(bar.last_close * multiplier, 4) if bar.last_close else None,
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
