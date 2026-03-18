import logging
from datetime import datetime
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
                    pb_ratio=bar.pb_ratio,
                    ps_ratio=bar.ps_ratio,
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

        # PB/PS 合理性校验（仅日K 填充，周K/月K 为 NULL；若非 NULL 则必须 > 0）
        if bar.pb_ratio is not None and bar.pb_ratio <= 0:
            issues.append(f"pb_ratio={bar.pb_ratio} must be > 0")
        if bar.ps_ratio is not None and bar.ps_ratio <= 0:
            issues.append(f"ps_ratio={bar.ps_ratio} must be > 0")

        # 日期格式检查：验证 YYYY-MM-DD 可解析性，仅检查长度无法过滤 "2024-13-99" 等非法日期
        try:
            datetime.strptime(bar.trade_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            issues.append(f"invalid trade_date={bar.trade_date!r}")

        return issues
