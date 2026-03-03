import logging
from typing import List, Tuple

from models.kline import KlineBar

logger = logging.getLogger(__name__)

# OHLCV 合理性校验阈值
MAX_PRICE = 1_000_000.0    # 单股最高价上限（USD/HKD/CNY）
MIN_PRICE = 0.0001         # 最低价下限（防止零价）
MAX_VOLUME = 10 ** 13      # 最大成交量上限（股数）


class KlineValidator:
    """
    K线数据合理性校验。
    校验失败的 bar 会被标记为 is_valid=False，而非直接丢弃，
    以便记录并后续人工核查。
    """

    def validate_many(self, bars: List[KlineBar]) -> Tuple[List[KlineBar], List[KlineBar]]:
        """
        批量校验K线数据。

        Returns:
            (valid_bars, invalid_bars)
        """
        valid = []
        invalid = []
        for bar in bars:
            issues = self._check(bar)
            if issues:
                logger.warning(
                    "Invalid bar %s [%s] %s: %s",
                    bar.stock_code, bar.period, bar.trade_date, "; ".join(issues)
                )
                object.__setattr__(bar, "is_valid", False) if hasattr(bar, "__dict__") else None
                # dataclass 不可用 setattr 直接改（is_valid 是普通字段，可以改）
                invalid.append(KlineBar(
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
                    is_valid=False,
                ))
            else:
                valid.append(bar)
        return valid, invalid

    def validate(self, bar: KlineBar) -> bool:
        return len(self._check(bar)) == 0

    @staticmethod
    def _check(bar: KlineBar) -> List[str]:
        issues = []

        # 价格范围检查
        for field, val in [("open", bar.open), ("high", bar.high),
                           ("low", bar.low), ("close", bar.close)]:
            if val is None or val < MIN_PRICE or val > MAX_PRICE:
                issues.append(f"{field}={val} out of range [{MIN_PRICE}, {MAX_PRICE}]")

        # OHLC 逻辑关系检查
        if bar.high is not None and bar.low is not None and bar.high < bar.low:
            issues.append(f"high({bar.high}) < low({bar.low})")

        if bar.open is not None and bar.high is not None and bar.open > bar.high:
            issues.append(f"open({bar.open}) > high({bar.high})")

        if bar.open is not None and bar.low is not None and bar.open < bar.low:
            issues.append(f"open({bar.open}) < low({bar.low})")

        if bar.close is not None and bar.high is not None and bar.close > bar.high:
            issues.append(f"close({bar.close}) > high({bar.high})")

        if bar.close is not None and bar.low is not None and bar.close < bar.low:
            issues.append(f"close({bar.close}) < low({bar.low})")

        # 成交量检查
        if bar.volume < 0 or bar.volume > MAX_VOLUME:
            issues.append(f"volume={bar.volume} out of range [0, {MAX_VOLUME}]")

        # 日期格式检查
        if not bar.trade_date or len(bar.trade_date) != 10:
            issues.append(f"invalid trade_date={bar.trade_date!r}")

        return issues
