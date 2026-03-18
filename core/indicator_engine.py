"""
core/indicator_engine.py — 技术指标计算引擎（迭代3）

纯 Python 实现，无第三方指标库依赖。
严格只读，不写入数据库。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from models.kline import KlineBar


# ---------------------------------------------------------------------------
# 信号枚举
# ---------------------------------------------------------------------------

class SignalEnum(str, Enum):
    BULLISH = "bullish"          # 多头 / 超卖区间 / 金叉（🟢 绿色）
    BEARISH = "bearish"          # 空头 / 超买区间 / 死叉（🔴 红色）
    NEUTRAL = "neutral"          # 中性 / 观望（⚖️ 灰色）
    VOLUME_HIGH = "volume_high"  # 放量（🔊 橙色）
    VOLUME_LOW = "volume_low"    # 缩量（🔇 灰色）


# ---------------------------------------------------------------------------
# 指标结果容器
# ---------------------------------------------------------------------------

@dataclass
class IndicatorResult:
    MA: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    EMA: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    BOLL: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    MACD: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    RSI: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    KDJ: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    MAVOL: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    signals: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 计算引擎
# ---------------------------------------------------------------------------

class IndicatorEngine:
    """
    技术指标计算引擎。
    所有方法均为纯函数（静态方法），无副作用，无 IO。
    """

    # ------------------------------------------------------------------ #
    #  基础计算方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def ma(close: List[float], n: int) -> List[Optional[float]]:
        """
        简单移动平均 MA(n)。
        前 n-1 个位置填 None（数据不足无法计算）。
        """
        result: List[Optional[float]] = [None] * len(close)
        for i in range(n - 1, len(close)):
            window = close[i - n + 1: i + 1]
            result[i] = round(sum(window) / n, 4)
        return result

    @staticmethod
    def ema(close: List[float], n: int) -> List[Optional[float]]:
        """
        指数移动平均 EMA(n)，k = 2/(n+1)。
        第一个有效值 = 前 n 个收盘价的算术均值（业界通用做法）。
        前 n-1 个位置填 None。
        """
        if len(close) < n:
            return [None] * len(close)

        k = 2.0 / (n + 1)
        result: List[Optional[float]] = [None] * len(close)

        # 第一个 EMA 用算术均值种子
        seed = sum(close[:n]) / n
        result[n - 1] = round(seed, 6)

        for i in range(n, len(close)):
            prev = result[i - 1]
            result[i] = round(close[i] * k + prev * (1 - k), 6)  # type: ignore[operator]

        return result

    @staticmethod
    def macd(
        close: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        MACD 指标。
        DIF = EMA(fast) - EMA(slow)
        DEA = EMA(DIF, signal)
        MACD 柱 = (DIF - DEA) × 2
        返回 (dif_series, dea_series, macd_bar_series)
        """
        ema_fast = IndicatorEngine.ema(close, fast)
        ema_slow = IndicatorEngine.ema(close, slow)

        # DIF = EMA12 - EMA26；前 slow-1 个位置为 None
        dif: List[Optional[float]] = []
        for f, s in zip(ema_fast, ema_slow):
            if f is None or s is None:
                dif.append(None)
            else:
                dif.append(round(f - s, 6))

        # 从 DIF 序列中提取有效值，用于计算 DEA
        # DEA = EMA(DIF, signal_period)，只在 DIF 有值后才开始计算
        dea: List[Optional[float]] = [None] * len(close)
        macd_bar: List[Optional[float]] = [None] * len(close)

        # 收集 DIF 有效值的起始索引
        first_dif_idx = next((i for i, v in enumerate(dif) if v is not None), None)
        if first_dif_idx is None:
            return dif, dea, macd_bar

        # 从 first_dif_idx 开始对 DIF 做 EMA(signal)
        k = 2.0 / (signal + 1)
        # 需要至少 signal 个有效 DIF 值才能计算第一个 DEA
        valid_dif_count = len(close) - first_dif_idx
        if valid_dif_count < signal:
            return dif, dea, macd_bar

        seed_start = first_dif_idx
        seed_end = first_dif_idx + signal
        seed = sum(dif[seed_start:seed_end]) / signal  # type: ignore[arg-type]
        dea[seed_end - 1] = round(seed, 6)
        macd_bar[seed_end - 1] = round((dif[seed_end - 1] - seed) * 2, 6)  # type: ignore[operator]

        for i in range(seed_end, len(close)):
            if dif[i] is None or dea[i - 1] is None:
                continue
            dea[i] = round(dif[i] * k + dea[i - 1] * (1 - k), 6)  # type: ignore[operator]
            macd_bar[i] = round((dif[i] - dea[i]) * 2, 6)  # type: ignore[operator]

        return dif, dea, macd_bar

    @staticmethod
    def boll(
        close: List[float],
        n: int = 20,
        k: float = 2.0,
    ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        布林带 BOLL(n, k)。
        中轨 = MA(n)
        上轨 = 中轨 + k × STD(close, n)
        下轨 = 中轨 - k × STD(close, n)
        返回 (upper, mid, lower)
        """
        size = len(close)
        upper: List[Optional[float]] = [None] * size
        mid:   List[Optional[float]] = [None] * size
        lower: List[Optional[float]] = [None] * size

        for i in range(n - 1, size):
            window = close[i - n + 1: i + 1]
            avg = sum(window) / n
            variance = sum((x - avg) ** 2 for x in window) / n  # 总体标准差（国内布林带惯例）
            std = math.sqrt(variance)
            mid[i]   = round(avg, 4)
            upper[i] = round(avg + k * std, 4)
            lower[i] = round(avg - k * std, 4)

        return upper, mid, lower

    @staticmethod
    def rsi(close: List[float], n: int = 14) -> List[Optional[float]]:
        """
        相对强弱指数 RSI(n)。
        使用 Wilder 平滑法（等效于 EMA with alpha=1/n）。
        前 n 个位置填 None。
        """
        size = len(close)
        result: List[Optional[float]] = [None] * size

        if size <= n:
            return result

        # 计算每日涨跌幅
        gains: List[float] = []
        losses: List[float] = []
        for i in range(1, size):
            diff = close[i] - close[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))

        # 第一个 RS 用前 n 个涨/跌的算术均值（Wilder 原始做法）
        avg_gain = sum(gains[:n]) / n
        avg_loss = sum(losses[:n]) / n

        def _rsi_from_avg(ag: float, al: float) -> float:
            if al == 0:
                return 100.0
            rs = ag / al
            return round(100 - 100 / (1 + rs), 4)

        result[n] = _rsi_from_avg(avg_gain, avg_loss)

        # Wilder 平滑（等效 EMA alpha=1/n）
        for i in range(n + 1, size):
            gain = gains[i - 1]   # gains[i-1] 对应 close[i] - close[i-1]
            loss = losses[i - 1]
            avg_gain = (avg_gain * (n - 1) + gain) / n
            avg_loss = (avg_loss * (n - 1) + loss) / n
            result[i] = _rsi_from_avg(avg_gain, avg_loss)

        return result

    @staticmethod
    def kdj(
        high: List[float],
        low: List[float],
        close: List[float],
        n: int = 9,
    ) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """
        KDJ 随机指标（中国市场版，K/D 平滑系数=3）。
        RSV(n) = (close - lowest_low(n)) / (highest_high(n) - lowest_low(n)) × 100
        K = 2/3 × K(prev) + 1/3 × RSV   （初始 K=50）
        D = 2/3 × D(prev) + 1/3 × K      （初始 D=50）
        J = 3K - 2D
        返回 (K_series, D_series, J_series)
        """
        size = len(close)
        K_series: List[Optional[float]] = [None] * size
        D_series: List[Optional[float]] = [None] * size
        J_series: List[Optional[float]] = [None] * size

        k_val, d_val = 50.0, 50.0

        for i in range(n - 1, size):
            window_high = high[i - n + 1: i + 1]
            window_low  = low[i - n + 1: i + 1]
            hh = max(window_high)
            ll = min(window_low)

            if hh == ll:
                rsv = 50.0  # 无波动时中性处理
            else:
                rsv = (close[i] - ll) / (hh - ll) * 100

            k_val = 2 / 3 * k_val + 1 / 3 * rsv
            d_val = 2 / 3 * d_val + 1 / 3 * k_val
            j_val = 3 * k_val - 2 * d_val

            K_series[i] = round(k_val, 4)
            D_series[i] = round(d_val, 4)
            J_series[i] = round(j_val, 4)

        return K_series, D_series, J_series

    @staticmethod
    def mavol(
        volume: List[int],
        periods: Tuple[int, ...] = (5, 10, 20),
    ) -> Dict[str, List[Optional[float]]]:
        """
        成交量移动均线 MAVOL。
        返回 {"MAVOL5": [...], "MAVOL10": [...], "MAVOL20": [...]}
        """
        result: Dict[str, List[Optional[float]]] = {}
        for p in periods:
            key = f"MAVOL{p}"
            series: List[Optional[float]] = [None] * len(volume)
            for i in range(p - 1, len(volume)):
                window = volume[i - p + 1: i + 1]
                series[i] = round(sum(window) / p, 0)
            result[key] = series
        return result

    # ------------------------------------------------------------------ #
    #  信号判断方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_signal(indicator: str, values: dict) -> SignalEnum:
        """
        对照 PRD §4.2 信号规范，返回当前信号状态。

        values 字典根据 indicator 名称包含不同键：
          BOLL:  {"latest_close": float, "upper": float|None, "lower": float|None}
          MACD:  {"dif": list, "dea": list}
          RSI:   {"rsi": float|None}
          KDJ:   {"K": float|None, "D": float|None}
          MA:    {"MA5": float|None, "MA20": float|None, "MA60": float|None}
          MAVOL: {"vol": int, "mavol5": float|None}
        """
        if indicator == "BOLL":
            close = values.get("latest_close")
            upper = values.get("upper")
            lower = values.get("lower")
            if close is None or upper is None or lower is None:
                return SignalEnum.NEUTRAL
            if close > upper:
                return SignalEnum.BEARISH   # 超买·上轨突破
            if close < lower:
                return SignalEnum.BULLISH   # 超卖·下轨突破
            return SignalEnum.NEUTRAL

        elif indicator == "MACD":
            # 判断最近一次 DIF/DEA 交叉状态
            dif_list = values.get("dif", [])
            dea_list = values.get("dea", [])
            # 收集有效值
            valid_pairs = [
                (d, e) for d, e in zip(dif_list, dea_list)
                if d is not None and e is not None
            ]
            if len(valid_pairs) < 2:
                return SignalEnum.NEUTRAL
            # 当前和上一根有效 bar 的 DIF-DEA 关系
            cur_dif, cur_dea = valid_pairs[-1]
            prev_dif, prev_dea = valid_pairs[-2]
            if cur_dif > cur_dea and prev_dif <= prev_dea:
                return SignalEnum.BULLISH   # 金叉
            if cur_dif < cur_dea and prev_dif >= prev_dea:
                return SignalEnum.BEARISH   # 死叉
            # 无新交叉：判断当前方向
            if cur_dif > cur_dea:
                return SignalEnum.BULLISH   # 多头持续
            if cur_dif < cur_dea:
                return SignalEnum.BEARISH   # 空头持续
            return SignalEnum.NEUTRAL

        elif indicator == "RSI":
            rsi_val = values.get("rsi")
            if rsi_val is None:
                return SignalEnum.NEUTRAL
            if rsi_val > 70:
                return SignalEnum.BEARISH   # 超买
            if rsi_val < 30:
                return SignalEnum.BULLISH   # 超卖
            return SignalEnum.NEUTRAL

        elif indicator == "KDJ":
            k_val = values.get("K")
            d_val = values.get("D")
            if k_val is None or d_val is None:
                return SignalEnum.NEUTRAL
            if k_val > d_val and k_val < 20:
                return SignalEnum.BULLISH   # 金叉·超卖买入
            if k_val < d_val and k_val > 80:
                return SignalEnum.BEARISH   # 死叉·超买卖出
            return SignalEnum.NEUTRAL

        elif indicator == "MA":
            ma5  = values.get("MA5")
            ma20 = values.get("MA20")
            ma60 = values.get("MA60")
            if ma5 is None or ma20 is None or ma60 is None:
                return SignalEnum.NEUTRAL
            if ma5 > ma20 > ma60:
                return SignalEnum.BULLISH   # 多头排列
            if ma5 < ma20 < ma60:
                return SignalEnum.BEARISH   # 空头排列
            return SignalEnum.NEUTRAL

        elif indicator == "MAVOL":
            vol   = values.get("vol")
            mavol5 = values.get("mavol5")
            if vol is None or mavol5 is None or mavol5 == 0:
                return SignalEnum.NEUTRAL
            if vol > mavol5 * 1.5:
                return SignalEnum.VOLUME_HIGH   # 放量
            if vol < mavol5 * 0.5:
                return SignalEnum.VOLUME_LOW    # 缩量
            return SignalEnum.NEUTRAL

        return SignalEnum.NEUTRAL

    # ------------------------------------------------------------------ #
    #  综合计算入口
    # ------------------------------------------------------------------ #

    @classmethod
    def calculate_all(cls, bars: List[KlineBar]) -> IndicatorResult:
        """
        一次性计算全部7个指标并返回 IndicatorResult（含信号状态）。

        Args:
            bars: 按 trade_date 升序排列的 KlineBar 列表（已复权或原始均可）

        Returns:
            IndicatorResult，各指标序列长度与 bars 相同，
            无法计算的位置填 None。
        """
        if not bars:
            return IndicatorResult()

        close  = [b.close  for b in bars]
        high   = [b.high   for b in bars]
        low    = [b.low    for b in bars]
        volume = [b.volume for b in bars]

        # --- MA ---
        ma5_series  = cls.ma(close, 5)
        ma20_series = cls.ma(close, 20)
        ma60_series = cls.ma(close, 60)
        ma_result = {"MA5": ma5_series, "MA20": ma20_series, "MA60": ma60_series}

        # --- EMA ---
        ema12_series = cls.ema(close, 12)
        ema26_series = cls.ema(close, 26)
        ema_result = {"EMA12": ema12_series, "EMA26": ema26_series}

        # --- BOLL ---
        boll_upper, boll_mid, boll_lower = cls.boll(close, 20, 2.0)
        boll_result = {"upper": boll_upper, "mid": boll_mid, "lower": boll_lower}

        # --- MACD ---
        dif_series, dea_series, macd_bar_series = cls.macd(close)
        macd_result = {"dif": dif_series, "dea": dea_series, "macd": macd_bar_series}

        # --- RSI ---
        rsi14_series = cls.rsi(close, 14)
        rsi_result = {"RSI14": rsi14_series}

        # --- KDJ ---
        k_series, d_series, j_series = cls.kdj(high, low, close, 9)
        kdj_result = {"K": k_series, "D": d_series, "J": j_series}

        # --- MAVOL ---
        mavol_result = cls.mavol(volume, (5, 10, 20))

        # --- 信号判断（取最新有效值）---
        latest_close = close[-1] if close else None

        # BOLL 信号
        boll_signal = cls.get_signal("BOLL", {
            "latest_close": latest_close,
            "upper": _last_valid(boll_upper),
            "lower": _last_valid(boll_lower),
        })

        # MACD 信号
        macd_signal = cls.get_signal("MACD", {
            "dif": dif_series,
            "dea": dea_series,
        })

        # RSI 信号
        rsi_signal = cls.get_signal("RSI", {
            "rsi": _last_valid(rsi14_series),
        })

        # KDJ 信号
        kdj_signal = cls.get_signal("KDJ", {
            "K": _last_valid(k_series),
            "D": _last_valid(d_series),
        })

        # MA 信号
        ma_signal = cls.get_signal("MA", {
            "MA5":  _last_valid(ma5_series),
            "MA20": _last_valid(ma20_series),
            "MA60": _last_valid(ma60_series),
        })

        # MAVOL 信号
        mavol_signal = cls.get_signal("MAVOL", {
            "vol":    volume[-1] if volume else None,
            "mavol5": _last_valid(mavol_result.get("MAVOL5", [])),
        })

        signals = {
            "BOLL":  boll_signal.value,
            "MACD":  macd_signal.value,
            "RSI":   rsi_signal.value,
            "KDJ":   kdj_signal.value,
            "MA":    ma_signal.value,
            "MAVOL": mavol_signal.value,
        }

        return IndicatorResult(
            MA=ma_result,
            EMA=ema_result,
            BOLL=boll_result,
            MACD=macd_result,
            RSI=rsi_result,
            KDJ=kdj_result,
            MAVOL=mavol_result,
            signals=signals,
        )


# ---------------------------------------------------------------------------
# 综合信号判断（Watchlist 总览页用）
# ---------------------------------------------------------------------------

def calc_composite_signal(signals: Dict[str, str], rsi_value: Optional[float]) -> str:
    """
    综合信号判断（PRD §4.3）：
      偏多：MACD==bullish AND 50 ≤ RSI ≤ 70 AND KDJ!=bearish
      偏空：MACD==bearish AND RSI < 50 AND KDJ!=bullish
      其余：neutral
    """
    macd_sig = signals.get("MACD", "neutral")
    kdj_sig  = signals.get("KDJ", "neutral")

    if rsi_value is None:
        return SignalEnum.NEUTRAL.value

    if (macd_sig == SignalEnum.BULLISH.value
            and 50 <= rsi_value <= 70
            and kdj_sig != SignalEnum.BEARISH.value):
        return SignalEnum.BULLISH.value

    if (macd_sig == SignalEnum.BEARISH.value
            and rsi_value < 50
            and kdj_sig != SignalEnum.BULLISH.value):
        return SignalEnum.BEARISH.value

    return SignalEnum.NEUTRAL.value


# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------

def _last_valid(series: List[Optional[float]]) -> Optional[float]:
    """返回序列中最后一个非 None 值；若全为 None 则返回 None。"""
    for v in reversed(series):
        if v is not None:
            return v
    return None
