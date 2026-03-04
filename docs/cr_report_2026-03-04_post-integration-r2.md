# Code Review Report — Post-Integration Round 2

**审查日期**：2026-03-04
**阶段标记**：功能性联调通过后第二轮审查
**基准报告**：`docs/cr_report_2026-03-04_post-integration.md`

---

## 一、Post-Integration Round 1 问题修复验证

### 问题 1：日历分段失败后部分数据永久被视为完整
**修复状态**：✅ 正确

`futu_wrap/calendar_fetcher.py:53-57`，分段失败时改为抛出 `RuntimeError`：

```python
if ret != RET_OK:
    raise RuntimeError(
        f"request_trading_days failed for market={market} [{seg_start}~{seg_end}]: {data}"
    )
```

外层 `execute_with_retry` 捕获异常后触发重试，失败不再静默写入部分数据。

---

### 问题 2：`verify_adj_multi.py` 中 `nearby_event` 死代码
**修复状态**：✅ 正确

`verify_adj_multi.py:155-167`，`nearby_event` 相关代码已删除，改为无条件逐行打印所有交易日数据，简洁直接。

---

### 问题 3：日历分段内部 `sleep` 绕过限频计数器
**修复状态**：✅ 已通过注释说明接受为已知限制

`futu_wrap/calendar_fetcher.py:68-70` 加入注释，明确说明此处 `sleep` 是 `fetch()` 内部的手动限速，外层限频器仅计一次调用。

---

## 二、本轮全量扫描新发现问题

### 问题 A：`KlineFetcher` 改回 `request_history_kline` 后 `fields=[""]` 参数异常（P1）

**文件**：`futu_wrap/kline_fetcher.py:94`

```python
ret, data, next_key = self._client.ctx.request_history_kline(
    ...
    fields=[""],   # ← 空字符串列表
    ...
)
```

联调期间 `KlineFetcher` 从 `get_history_kline`（旧接口）切换回了 `request_history_kline`（官方分页接口），分页逻辑也随之改为正确的 `page_req_key` 方式。但 `fields=[""]` 传入了一个含空字符串的列表，而非 `None` 或合法字段列表。

富途 SDK `request_history_kline` 的 `fields` 参数应传 `None`（返回全字段）或 `[KL_FIELD.xxx, ...]` 枚举列表。传入 `[""]` 的行为未在官方文档中定义：
- 可能被忽略（退化为返回全字段）
- 可能导致返回空 DataFrame 或报错

这是联调切换接口时遗留的残余参数，应改为 `fields=None`。

---

### 问题 B：`KlineValidator.validate_many` 中 `object.__setattr__` 调用是死代码（P3）

**文件**：`core/validator.py:37`

```python
object.__setattr__(bar, "is_valid", False) if hasattr(bar, "__dict__") else None
```

紧接着第 39 行重新构造了一个 `is_valid=False` 的新 `KlineBar` 对象并 `append` 到 `invalid`，`bar` 原对象并未被使用。这行 `object.__setattr__` 实际修改的是即将被丢弃的 `bar`，对结果没有任何影响，是冗余代码，且注释（第 38 行）说"dataclass 不可用 setattr 直接改"与实现矛盾（普通 dataclass 完全可以直接 `bar.is_valid = False`）。

---

### 问题 C：`GapDetector._group_consecutive` 中 `td_index.get(prev, -1)` 的默认值可能引起误合并（P2）

**文件**：`core/gap_detector.py:120-123`

```python
prev_idx = td_index.get(prev, -1)
curr_idx = td_index.get(curr, -1)

if curr_idx == prev_idx + 1:   # 判断是否连续
```

`missing` 中的日期来自 `[d for d in trading_days if d not in stored_dates]`，因此所有 `missing` 中的日期必然在 `trading_days` 中存在，`td_index.get` 永远不会走到默认值 `-1`。

但若未来调用方传入的 `missing` 包含不在 `trading_days` 中的日期（如函数被复用），两个不存在的日期 `get` 都返回 `-1`，`curr_idx == prev_idx + 1` 即 `-1 == 0` 为 `False`，不会误合并。但如果只有 `curr` 不存在（返回 `-1`）而 `prev_idx` 恰好是 `-2`（不可能），也不会误合并。实际上默认值 `-1` 的选取是安全的，但语义不够清晰。属于防御性编程的代码质量问题，非 Bug。

---

### 问题 D：`WatchlistManager.load` 中 `to_deactivate` 可能包含重复项（P3）

**文件**：`core/watchlist_manager.py:64-73`

```python
# 路径1：JSON 中存在但 is_active=False → to_deactivate
elif db_stock.is_active and not stock.is_active:
    to_deactivate.append(stock.stock_code)

# 路径2：JSON 中不存在 → to_deactivate
for code in db_stocks:
    if code not in json_codes:
        if db_stocks[code].is_active:
            to_deactivate.append(code)
```

如果一只股票在 JSON 中显式设置了 `is_active=False`，它会进入路径 1 被加入 `to_deactivate`。路径 2 的 `code not in json_codes` 条件会将 JSON 中完全不存在的股票加入，与路径 1 不重叠。两路径互斥，**实际不会产生重复项**。

但若将来逻辑有调整，此处没有去重保护。`set_active(code, False)` 是幂等操作，重复调用不影响结果，无实际危害。

---

## 三、遗留状态汇总

| # | 问题 | 状态 |
|---|------|------|
| 新问题 C（重试双倍配额） | 已知限制 | 保留，注释说明 |

---

## 四、优先级汇总

| 优先级 | 问题 | 文件 & 行号 |
|--------|------|------------|
| P1 | 问题 A：`fields=[""]` 参数异常，应为 `None` | `futu_wrap/kline_fetcher.py:94` |
| P2 | 问题 C：`td_index.get` 默认值语义不清晰 | `core/gap_detector.py:120-121` |
| P3 | 问题 B：`object.__setattr__` 是死代码 | `core/validator.py:37-38` |
| P3 | 问题 D：`to_deactivate` 理论上可能重复（幂等，无实际危害） | `core/watchlist_manager.py:64-73` |
