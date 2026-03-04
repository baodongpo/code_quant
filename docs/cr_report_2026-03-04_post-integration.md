# Code Review Report — Post-Integration Round 1

**审查日期**：2026-03-04
**阶段标记**：功能性联调通过后首轮审查
**基准报告**：`docs/cr_report_2026-03-04_round4.md`

---

## 一、联调阶段闭环确认

### Q3：前复权因子语义 —— 已完全解决

联调期间完成了以下工作：

1. **`futu/` 目录重命名为 `futu_wrap/`**，彻底消除与富途 SDK 包名 `futu` 的冲突隐患
2. **`AdjustFactor` 数据模型重构**（`models/kline.py`）：从单字段扩展为富途真实的双系数结构

   ```python
   forward_factor:   float  # 乘法系数 A（拆送股调整，拆股时 < 1.0）
   forward_factor_b: float  # 加法偏移  B（现金分红调整，分红时为负值）
   ```

3. **`AdjustmentService._calc_forward_multiplier` 重写**（`core/adjustment_service.py:79-101`）：从简单累乘改为线性变换复合公式：

   ```
   adj_price = raw_price × A + B
   多事件复合（由近到远倒序）：
       A_new = A × a_i
       B_new = B × a_i + b_i
   ```

4. **`verify_adj_multi.py` 验证脚本**：覆盖 A 股高派息（贵州茅台）、港股股息（汇丰控股）、除权前后日期对比，与富途 App QFQ 价格逐日比对，误差 < 0.01，验证通过。

**Q3 正式关闭。**

---

## 二、新发现问题

### 问题 1：日历分段失败后部分数据被永久视为完整（P1）

**文件**：`futu_wrap/calendar_fetcher.py:53-58` + `core/sync_engine.py:168`

`CalendarFetcher.fetch()` 按 365 天分段拉取，某段 API 失败时 `break` 退出，返回已拉取的前 N 段数据。`_ensure_calendar` 写入后不验证完整性：

```python
# sync_engine.py:168
if not self._calendar_repo.has_calendar(calendar_market, start_date, end_date):
    trading_days = self._general_rate_limiter.execute_with_retry(
        self._calendar_fetcher.fetch, ...
    )
    if trading_days:
        self._calendar_repo.insert_many(...)
# 写入部分数据后结束，下次运行 has_calendar() 查到有记录 → 跳过重拉 → 永久不完整
```

`has_calendar` 只检查范围内是否存在**任意一条**记录，部分写入后即返回 `True`。`GapDetector` 基于不完整日历做空洞检测，会将无日历记录的交易日误判为无数据，产生空洞漏报。

**修复方向**：`CalendarFetcher.fetch()` 内部分段失败时抛出异常（而非静默 break 返回部分数据），让外层 `execute_with_retry` 触发重试或整体失败，避免写入不完整日历。

---

### 问题 2：`verify_adj_multi.py` 中 `nearby_event` 是死代码（P3，仅影响验证脚本）

**文件**：`verify_adj_multi.py:168-173`

```python
nearby_event = any(
    abs((d > f.ex_date) - 0.5) < 0.5 and
    abs((d[:10] >= f.ex_date or d[:10] < f.ex_date))   # ← 恒为 abs(True) = 1
    for f in recent_factors
)
print(f"  {d:<12} ...")   # ← nearby_event 从未被使用
```

第二个条件对任意两个字符串恒为 `True`（任何字符串必然满足 `>=` 或 `<` 之一），`nearby_event` 计算完后也未参与任何判断，是无效代码。不影响验证结论（`all_ok`/`fail_count` 逻辑正确），但过滤意图未实现——实际是无条件打印所有交易日。

---

### 问题 3：`CalendarFetcher` 分段内部 `sleep` 绕过 `GeneralRateLimiter` 计数（P3）

**文件**：`futu_wrap/calendar_fetcher.py:69`

```python
if seg_start <= end:
    time.sleep(0.6)  # 分段间隔，手动控速
```

`fetch()` 通过 `general_rate_limiter.execute_with_retry` 调用，限频器只记录一次外层调用，但 `fetch()` 内部循环实际发出 N 次 API 请求（N 段），每段 0.6s 间隔由 `sleep` 控制，`GeneralRateLimiter` 对这些内部请求的计数形同虚设。

从 2015 年至今约需 10 次分段，期间限频计数仅增加 1。当前 watchlist 较小，实际不易触发富途全局限频，但与架构意图不符，建议在注释中说明此特殊处理，或将分段内部请求纳入限频计数。

---

## 三、遗留状态汇总

| # | 问题 | 状态 |
|---|------|------|
| Q3 | 前复权因子累乘语义 | ✅ 联调验证通过，已关闭 |
| 新问题 C | 重试消耗双倍限频配额 | 已知限制，注释说明，保留 |

---

## 四、优先级汇总

| 优先级 | 问题 | 文件 & 行号 |
|--------|------|------------|
| P1 | 问题 1：日历分段失败后部分数据永久被视为完整 | `futu_wrap/calendar_fetcher.py:53-58`，`core/sync_engine.py:168` |
| P3 | 问题 2：`verify_adj_multi.py` 中 `nearby_event` 死代码 | `verify_adj_multi.py:168-173` |
| P3 | 问题 3：日历分段内部 `sleep` 绕过限频计数器 | `futu_wrap/calendar_fetcher.py:69` |
