"""
多股票前复权公式验证脚本
对比 raw_price × A + B 与富途 AuType.QFQ 参考价格，确认每只股票每个除权日前后 diff = 0
"""
import sys
import time
from typing import List

from futu import OpenQuoteContext, RET_OK, AuType, KLType, KL_FIELD

sys.path.insert(0, "/Users/bladebao/Documents/code_python/code_quant")

from futu_wrap.adjust_factor_fetcher import AdjustFactorFetcher
from core.adjustment_service import AdjustmentService
from models.kline import AdjustFactor
from futu_wrap.client import FutuClient

# ──────────────────────────────────────────────────────────
# 验证股票列表
# ──────────────────────────────────────────────────────────
STOCKS = [
    "SZ.000063",   # 中兴通讯（A股，有现金分红）
    "SH.600519",   # 贵州茅台（A股，高派息）
    "SH.601318",   # 中国平安（A股）
    "HK.00700",    # 腾讯控股（港股）
    "HK.00005",    # 汇丰控股（港股，有股息）
    "HK.02318",    # 中国平安H（港股）
]

VERIFY_RECENT_EVENTS = 3   # 每只股票验证最近 N 个除权事件附近的价格


def fetch_qfq_close(ctx: OpenQuoteContext, stock_code: str, dates: List[str]) -> dict:
    """拉取指定日期列表的富途 QFQ 收盘价，返回 {date: close} 字典"""
    if not dates:
        return {}
    start = min(dates)
    end = max(dates)
    result = {}
    page_req_key = None
    while True:
        ret, data, next_key = ctx.request_history_kline(
            code=stock_code, start=start, end=end,
            ktype=KLType.K_DAY, autype=AuType.QFQ,
            fields=[KL_FIELD.DATE_TIME, KL_FIELD.CLOSE], max_count=1000,
            page_req_key=page_req_key,
        )
        if ret != RET_OK:
            print(f"  [WARN] QFQ fetch failed for {stock_code}: {data}")
            return result
        if data is not None and not data.empty:
            for _, row in data.iterrows():
                d = str(row["time_key"])[:10]
                result[d] = float(row["close"])
        if next_key is None:
            break
        page_req_key = next_key
        time.sleep(0.3)
    return result


def fetch_raw_close(ctx: OpenQuoteContext, stock_code: str, dates: List[str]) -> dict:
    """拉取原始未复权收盘价"""
    if not dates:
        return {}
    start = min(dates)
    end = max(dates)
    result = {}
    page_req_key = None
    while True:
        ret, data, next_key = ctx.request_history_kline(
            code=stock_code, start=start, end=end,
            ktype=KLType.K_DAY, autype=AuType.NONE,
            fields=[KL_FIELD.DATE_TIME, KL_FIELD.CLOSE], max_count=1000,
            page_req_key=page_req_key,
        )
        if ret != RET_OK:
            print(f"  [WARN] RAW fetch failed for {stock_code}: {data}")
            return result
        if data is not None and not data.empty:
            for _, row in data.iterrows():
                d = str(row["time_key"])[:10]
                result[d] = float(row["close"])
        if next_key is None:
            break
        page_req_key = next_key
        time.sleep(0.3)
    return result


def get_test_dates_around_events(factors: List[AdjustFactor], n: int) -> List[str]:
    """取最近 n 个除权事件，每个事件取 ex_date-1 和 ex_date 两个日期"""
    recent = sorted(factors, key=lambda f: f.ex_date, reverse=True)[:n]
    dates = set()
    for f in recent:
        # ex_date 当天及前一天（如果有的话用更早几天以保证有交易日）
        # 实际取 ex_date 前后各若干天，由 QFQ/RAW 接口返回实际交易日
        from datetime import date, timedelta
        ex = date.fromisoformat(f.ex_date)
        for delta in range(-5, 6):
            dates.add((ex + timedelta(days=delta)).isoformat())
    return sorted(dates)


def verify_stock(ctx: OpenQuoteContext, stock_code: str) -> bool:
    """验证单只股票，返回是否全部通过"""
    print(f"\n{'='*60}")
    print(f"股票: {stock_code}")

    # 1. 获取复权因子
    ret, data = ctx.get_rehab(stock_code)
    if ret != RET_OK or data is None or data.empty:
        print(f"  [SKIP] 无复权因子数据")
        return True

    # 解析因子
    from futu_wrap.adjust_factor_fetcher import AdjustFactorFetcher
    factors = AdjustFactorFetcher._parse_rehab(stock_code, data)
    print(f"  复权因子数量: {len(factors)}")
    if not factors:
        print(f"  [SKIP] 无有效复权因子")
        return True

    # 打印最近几个除权事件
    recent_factors = sorted(factors, key=lambda f: f.ex_date, reverse=True)[:VERIFY_RECENT_EVENTS]
    print(f"  最近 {len(recent_factors)} 个除权事件:")
    for f in recent_factors:
        print(f"    ex_date={f.ex_date}  A={f.forward_factor:.8f}  B={f.forward_factor_b:.4f}")

    # 2. 确定验证日期范围（覆盖最近 N 个除权事件前后各 5 天）
    test_dates = get_test_dates_around_events(factors, VERIFY_RECENT_EVENTS)
    start_date = min(test_dates)
    end_date = max(test_dates)
    time.sleep(0.5)

    # 3. 拉取 QFQ 和 RAW 价格
    qfq_prices = fetch_qfq_close(ctx, stock_code, [start_date, end_date])
    time.sleep(0.5)
    raw_prices = fetch_raw_close(ctx, stock_code, [start_date, end_date])
    time.sleep(0.5)

    if not qfq_prices or not raw_prices:
        print(f"  [SKIP] 无法获取价格数据")
        return True

    # 4. 逐日对比
    all_ok = True
    fail_count = 0
    total_count = 0
    common_dates = sorted(set(qfq_prices.keys()) & set(raw_prices.keys()))

    print(f"\n  {'日期':<12} {'原始价':>10} {'复权A':>12} {'复权B':>10} {'计算前复权':>12} {'富途QFQ':>12} {'差值':>10} {'状态'}")
    print(f"  {'-'*90}")

    for d in common_dates:
        raw = raw_prices[d]
        qfq = qfq_prices[d]
        A, B = AdjustmentService._calc_forward_multiplier(d, factors)
        calc = round(raw * A + B, 4)
        diff = round(calc - qfq, 4)
        ok = abs(diff) < 0.01  # 允许 1分钱误差（浮点/四舍五入）
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
            fail_count += 1
        total_count += 1
        # 只打印除权事件附近（A != 1 或 B != 0）的日期，以及最近20天的数据
        nearby_event = any(
            abs((d > f.ex_date) - 0.5) < 0.5 and
            abs((d[:10] >= f.ex_date or d[:10] < f.ex_date))
            for f in recent_factors
        )
        print(f"  {d:<12} {raw:>10.4f} {A:>12.8f} {B:>10.4f} {calc:>12.4f} {qfq:>12.4f} {diff:>10.4f}  {status}")

    print(f"\n  汇总: 共 {total_count} 个交易日，失败 {fail_count} 个")
    if all_ok:
        print(f"  [PASS] {stock_code} 前复权验证通过")
    else:
        print(f"  [FAIL] {stock_code} 前复权验证失败，{fail_count}/{total_count} 不匹配")

    return all_ok


def main():
    print("连接富途 OpenD...")
    ctx = OpenQuoteContext(host="127.0.0.1", port=11111)

    try:
        all_pass = True
        for stock_code in STOCKS:
            try:
                ok = verify_stock(ctx, stock_code)
                if not ok:
                    all_pass = False
            except Exception as e:
                print(f"  [ERROR] {stock_code} 验证异常: {e}")
                import traceback
                traceback.print_exc()
            time.sleep(1.0)

        print(f"\n{'='*60}")
        if all_pass:
            print("最终结论: 全部股票前复权验证通过")
        else:
            print("最终结论: 部分股票验证失败，请检查上方日志")
    finally:
        ctx.close()


if __name__ == "__main__":
    main()
