# Code Review Report — Round 3

**审查日期**：2026-03-04
**基准报告**：`docs/cr_report_2026-03-04_round2.md`
**审查范围**：验证第二轮新问题修复结果 + 全量代码扫描

---

## 一、第二轮新问题修复验证

### 新问题 1：K线拉取无重试保护
**修复状态**：✅ 正确

`kline_fetcher.py` 新增 `_fetch_one_page_with_retry` 方法（:83-128），每页独立做指数退避重试（1s/2s/4s），重试逻辑与 `GeneralRateLimiter.execute_with_retry` 一致。`fetch()` 的翻页循环（:62-81）改为调用该方法，已拉取的前 N-1 页数据不受后续页失败影响，断点续传语义正确。

---

### 新问题 2：`upsert_gaps` 逐条事务
**修复状态**：✅ 正确

`gap_repo.py:57-74` 将 `ON CONFLICT` 逻辑提取为单条 SQL，用 `executemany` 在单个 `with DBConnection` 块内批量提交，恢复了原子性。

---

### 新问题 3：`rows_inserted` 语义不明
**修复状态**：✅ 已通过注释明确

`sync_engine.py:269` 加入注释：`# rows_inserted 仅统计有效行写入数；invalid_bars 写入量见上方 WARNING 日志`，语义已明确为"有效行数"。

---

### 新问题 4：双限频器合计可能超全局上限
**修复状态**：✅ 已通过注释说明，接受为已知风险

`rate_limiter.py:30-34`（`RateLimiter` 类注释）和 `:122-124`（`GeneralRateLimiter` 类注释）均已说明两者独立计数、合计上限超出富途全局限制的情况，并给出了调整建议。设计决策明确，可接受。

---

## 二、遗留 TODO 状态

| # | 状态 | 说明 |
|---|------|------|
| Q3 | **待联调** | `core/adjustment_service.py:89-93` 前复权因子是单次相乘还是累积因子需联调确认，本轮不变 |

---

## 三、本轮全量扫描新发现问题

### 新问题 A：`_fetch_one_page_with_retry` 最后一次循环缺少 `return`（P0，运行时 Bug）

**文件**：`futu/kline_fetcher.py:96-128`

```python
for attempt in range(max_retries + 1):   # 默认 range(4)，即 0,1,2,3
    self._rate_limiter.acquire()
    ret, data = self._client.ctx.get_history_kline(...)

    if ret == RET_OK:
        ...
        return self._parse_dataframe(...)   # 成功时返回

    if attempt < max_retries:
        ...
        time.sleep(wait)                    # 非最后一次：等待后继续循环
    else:
        ...
        raise RuntimeError(...)             # 最后一次失败：抛出异常
```

逻辑上看，循环结束路径只有两条：`return`（成功）或 `raise`（耗尽重试）。但 Python 函数在 `for` 循环正常结束后会隐式 `return None`——如果 `max_retries=0` 且 `ret != RET_OK`，循环体执行到 `attempt < max_retries`（`0 < 0` 为 `False`）走 `else` 分支抛出 `RuntimeError`，没问题。

**然而**：当 `ret == RET_OK` 且 `data is None or data.empty` 时，`return []` 正常退出。但如果 `ret != RET_OK` 且 `attempt == max_retries`，走 `raise`，也没问题。

仔细推导后：**此 Bug 不存在**，逻辑覆盖完整。但函数末尾没有显式 `return` 或 `raise`（只靠循环内的 `raise`），mypy/pylint 会报 "missing return statement"，建议在函数末尾加一行兜底：
```python
raise RuntimeError("unreachable")
```
这是代码规范问题，不是运行时 Bug，降级为 P3。

---

### 新问题 B：增量同步的 `start_date` 使用 `last_sync_date` 可能导致重复拉取（P2，数据逻辑）

**文件**：`core/sync_engine.py:117-118`

```python
elif meta.get("last_sync_date"):
    start_date = meta["last_sync_date"]   # 从上次同步日期开始（含该日）
```

`last_sync_date` 记录的是上次同步成功时的 `today`（`sync_engine.py:155`），即当天日期。下次运行时用同一天作为 `start_date`，会重复拉取最后一天的数据。由于写入用 `INSERT OR IGNORE`（幂等），不会产生重复记录，但存在无意义的重复请求开销。

严格来说正确做法应为 `last_sync_date` 的次日（`_next_date(last_sync_date)`）。当前行为不会造成数据错误，属于轻微效率问题，日K影响最小（1条），但月K可能在月末重复拉整月数据（若恰好当天也是月末 bar）。

---

### 新问题 C：`_fetch_one_page_with_retry` 重试时未重新 `acquire()` 限频（P2，限频逻辑）

**文件**：`futu/kline_fetcher.py:96-120`

```python
for attempt in range(max_retries + 1):
    self._rate_limiter.acquire()        # 每次循环都 acquire
    ret, data = self._client.ctx.get_history_kline(...)

    if ret == RET_OK:
        ...
    if attempt < max_retries:
        wait = 2 ** attempt
        time.sleep(wait)               # sleep 后继续下一次循环 → 下一次循环开头再 acquire
```

每次重试前先 `sleep(wait)`，然后循环回到开头执行 `acquire()`。`acquire()` 的最小间隔约束（`self._last_request_time`）会在 `sleep` 结束后立刻满足，不影响正确性。

**但**：重试的 `sleep` 时长（最长 4s）与 `acquire()` 的滑动窗口计数器无关——`sleep` 期间窗口计数已自然衰减，重试后 `acquire()` 会将本次重试也计入请求计数。这意味着一次失败+重试实际消耗了 2 个限频配额。对于高频触发重试的场景（如批量拉取时持续触发限频错误），配额消耗速度会加倍。这是轻微的设计问题，不影响正确性。

---

### 新问题 D：`KlineFetcher` 的 `_parse_dataframe` 中零值字段被当作 falsy 过滤（P2，数据正确性）

**文件**：`futu/kline_fetcher.py:145-148`

```python
turnover=float(row["turnover"]) if "turnover" in row and row["turnover"] else None,
pe_ratio=float(row["pe_ratio"]) if "pe_ratio" in row and row["pe_ratio"] else None,
turnover_rate=float(row["turnover_rate"]) if "turnover_rate" in row and row["turnover_rate"] else None,
last_close=float(row["last_close"]) if "last_close" in row and row["last_close"] else None,
```

条件 `row["turnover"]` 在值为 `0`、`0.0`、`"0"` 时均为 falsy，导致成交额为零的 bar（如停牌日或新股首日）的 `turnover`、`turnover_rate`、`last_close` 被错误地设为 `None` 而非 `0.0`。

影响：
- `last_close=None` 会导致 `AdjustmentService._apply_adjustment` 中 `round(bar.last_close * multiplier, 4) if bar.last_close else None` 的判断恰好正确（跳过），但丢失了真实的前收盘价为 0 的信息（实际不应出现，但 `pe_ratio=0` 在亏损股中合法）
- `pe_ratio=0` 在亏损/净利为零的股票中是有效值，被过滤为 `None` 后算法层无法区分"无PE数据"与"PE=0"

正确写法应为：
```python
turnover=float(row["turnover"]) if "turnover" in row and row["turnover"] is not None else None,
```

---

### 新问题 E：`GapRepository.insert()` 方法返回值在唯一约束冲突时不可靠（P3）

**文件**：`db/repositories/gap_repo.py:9-17`

```python
def insert(self, ...) -> int:
    sql = "INSERT OR IGNORE INTO data_gaps ... VALUES (?, ?, ?, ?, 'open')"
    ...
    return cursor.lastrowid
```

`INSERT OR IGNORE` 在冲突时不插入，`cursor.lastrowid` 返回 `0` 或上一条成功插入的 id（SQLite 行为），调用方若依赖返回值判断是否插入成功会得到误导。该方法目前没有调用方（`upsert_gaps` 已替代其用途），是死代码，但若将来被使用会有隐患。

---

## 四、优先级汇总

| 优先级 | 问题 | 文件 & 行号 |
|--------|------|------------|
| TODO | Q3：前复权因子累乘语义 | `core/adjustment_service.py:89-93` |
| P2 | 新问题 B：增量同步重复拉取最后一天 | `core/sync_engine.py:117-118` |
| P2 | 新问题 D：零值字段被 falsy 过滤为 None | `futu/kline_fetcher.py:145-148` |
| P2 | 新问题 C：重试消耗双倍限频配额 | `futu/kline_fetcher.py:96-120` |
| P3 | 新问题 A：函数末尾缺兜底 raise（规范） | `futu/kline_fetcher.py:128` |
| P3 | 新问题 E：`insert()` 返回值不可靠（死代码） | `db/repositories/gap_repo.py:9-17` |
