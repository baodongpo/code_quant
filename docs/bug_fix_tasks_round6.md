# Dev 修复任务单 — Round 6 CR（复权链路 + 遗留问题）

**发起人：** QA / CR
**日期：** 2026-03-04
**基准版本：** commit 90229af
**关联 CR 会话：** 本轮覆盖 `adjustment_service.py`、`adjust_factor_fetcher.py`、`gap_detector.py`（L-2）、`watchlist_manager.py`（L-3）

---

## 优先级定义

| 级别 | 含义 |
|------|------|
| P0 | 上线阻塞，必须在联调前修复 |
| P1 | 上线阻塞，必须在联调中验证通过 |
| P2 | 中等风险，本期修复 |
| P3 | 技术债，下期跟踪 |

---

## P0 — 代码修复（联调前完成）

---

### TASK-1：修复 `last_close` 使用错误复权系数

**文件：** `core/adjustment_service.py:118`
**严重级：** 严重 / P0

**问题描述：**
`last_close` 是当日（trade_date = t）的前收盘价，语义为 `t-1` 日的原始收盘价。当前代码对其使用 `t` 日的复权系数 `(A, B)` 进行调整：

```python
last_close=round(bar.last_close * A + B, 4) if bar.last_close is not None else None,
```

在除权日当天，`t` 日与 `t-1` 日的复权系数不同：`t-1` 日需要将该除权事件纳入计算（`ex_date > t-1`），而 `t` 日不纳入（`ex_date > t` 不满足）。用错系数导致调整后的 `last_close` 与 `t-1` 日的 `close` 值不连续，破坏前收盘价的语义。

**修复方案（二选一，请 Dev 确认）：**

方案 A：对 `last_close` 单独传入 `t-1` 日的复权系数。需在 `_calc_forward_multiplier` 外部计算 `prev_date` 对应的 `(A', B')`，然后：
```python
last_close=round(bar.last_close * A_prev + B_prev, 4) if bar.last_close is not None else None,
```

方案 B：不对 `last_close` 做复权调整，直接置 `None`，由算法层从前一 bar 的 `close` 自行取值：
```python
last_close=None,
```

**验收标准：** 联调时取含除权事件的日期（如除权日当天及前后各一天），验证 `adjusted_bar[t].last_close == adjusted_bar[t-1].close`。

---

### TASK-2：修复 `_group_consecutive` 默认值 `-1` 的隐患

**文件：** `core/gap_detector.py:120-121`
**严重级：** 严重 / P0

**问题描述：**
```python
prev_idx = td_index.get(prev, -1)
curr_idx = td_index.get(curr, -1)
```

当 `missing` 中某个日期不在 `td_index` 里时：
- 若两者都命中默认值 `-1`：`curr_idx == prev_idx + 1` → `-1 == 0` → `False`，将连续缺失日切分为多个独立空洞（虚增空洞数量，触发多余拉取）。
- 若 `prev` 命中 `-1`，`curr` 恰好是 `td_index` 中索引为 `0` 的日期：`0 == -1+1` → `True`，本不连续的日期被错误合并为一个区间（扩大修复范围）。

**修复方案：**
去掉 `get(..., -1)` 的容错默认值，改为显式断言，在违反前置条件时快速失败：

```python
prev_idx = td_index[prev]   # 若 KeyError 则抛出，暴露上游 bug
curr_idx = td_index[curr]
```

或在函数入口处加前置断言：
```python
assert all(d in td_index for d in missing), \
    f"missing contains dates not in trading_days: {set(missing) - td_index.keys()}"
```

**验收标准：** 单测覆盖以下场景：
1. 连续缺失区间正确合并
2. 不连续缺失日正确切分
3. 传入不在 `trading_days` 里的 `missing` 日期时抛出明确异常（而非静默错误结果）

---

### TASK-3：修复 JSON 文件损坏时全量停用活跃股票

**文件：** `core/watchlist_manager.py:94-103`
**严重级：** 严重 / P0

**问题描述：**
`_load_json` 在 `FileNotFoundError` 或 `JSONDecodeError` 时返回空列表 `[]`。`load()` 接收到空列表后，判定 DB 中所有活跃股票均不在 JSON 中，将其全部加入 `to_deactivate`，执行 `set_active(code, False)`，**破坏性地将所有活跃股票停用**。后续同步引擎收到 `active_stocks=[]`，静默退出，错误完全被掩盖。

**修复方案：**
`_load_json` 在文件级错误时返回 `None`（区别于"文件存在但为空列表"），`load()` 在检测到 `None` 时提前中止，不执行任何 DB 写操作：

```python
def _load_json(self) -> List[Stock] | None:
    try:
        ...
    except FileNotFoundError:
        logger.error("watchlist.json not found at %s", self._watchlist_path)
        return None          # ← 改为 None
    except json.JSONDecodeError as e:
        logger.error("watchlist.json parse error: %s", e)
        return None          # ← 改为 None

def load(self) -> Tuple[List[Stock], List[Stock], List[Stock]]:
    json_stocks = self._load_json()
    if json_stocks is None:
        raise RuntimeError(f"Failed to load watchlist from {self._watchlist_path}, aborting.")
    ...
```

**验收标准：**
1. 删除或损坏 `watchlist.json` 后运行，程序抛出 `RuntimeError` 并记录 error 日志，DB 中任何股票的 `is_active` 均未被修改。
2. 正常空 watchlist（`markets: []`）不受影响，返回三个空列表。

---

### TASK-4：修复 `reactivated` 股票停用期数据缺口不触发补充同步

**文件：** `core/watchlist_manager.py:83-85`，`db/repositories/sync_meta_repo.py:74-81`
**严重级：** 严重 / P0

**问题描述：**
股票重新激活（`is_active: 0→1`）后，代码调用：

```python
self._sync_meta_repo.ensure_exists(stock.stock_code, period)
```

`ensure_exists` 实现为 `INSERT OR IGNORE`，对已存在的记录完全无效，`sync_status` 保持 `completed`（上次停用前的状态）。同步引擎将认为无需补同步，停用期间产生的 K 线空洞和复权事件永久缺失。

**修复方案：**
对 `reactivated` 股票，不应调用 `ensure_exists`，而应将其 `sync_status` 重置为 `pending`，触发重新扫描：

```python
for stock in newly_added:
    for period in ALL_PERIODS:
        self._sync_meta_repo.ensure_exists(stock.stock_code, period)

for stock in reactivated:
    for period in ALL_PERIODS:
        self._sync_meta_repo.set_status(stock.stock_code, period, "pending")
```

`set_status` 已存在于 `sync_meta_repo.py:66-72`，可直接使用。

**验收标准：**
1. 股票停用后再重新激活，其所有 period 的 `sync_status` 变为 `pending`。
2. 同步引擎下次运行时对该股票执行增量补充同步，填补停用期空洞。

---

## P1 — 联调验证项（联调中确认，不通过则升级为 P0 代码修复）

---

### TASK-5：验证 `forward_factor_b` 符号语义（含现金分红股票）

**文件：** `futu_wrap/adjust_factor_fetcher.py:57`，`core/adjustment_service.py:98-100`
**严重级：** 严重 / P1

**问题描述：**
富途 `get_rehab` 返回的 `forward_adj_factorB` 注释说明"现金分红时为负值"。代码直接代入 `adj_price = raw × A + B`，隐含假设该 B 值已经是前复权方向下的正确偏移，无需变号。若富途给出的 B 是原始除权事件的现金量（需要在前复权公式中取负），则所有含现金分红的股票复权价格将系统性偏差。

**验证步骤：**
1. 选取一只含现金分红记录的股票（建议：招商银行 `SH.600036` 或工商银行 `SH.601398`）。
2. 打印该股票某除权日前后的 `forward_adj_factorA`、`forward_adj_factorB` 原始值。
3. 用系统计算的前复权收盘价与富途 App「前复权」模式下同日期的价格对比。
4. 误差应 < 0.01 元（或 < 0.01%），否则需检查 B 的符号。

**结果登记：** 验证通过在任务单标注 ✓，不通过立即提 Bug 并暂停该路径上线。

---

### TASK-6：验证 `ex_div_date` 字段 `None` 值过滤

**文件：** `futu_wrap/adjust_factor_fetcher.py:52-53`
**严重级：** 中等 / P2（可在联调中顺带验证）

**问题描述：**
```python
ex_date = str(row.get("ex_div_date", row.get("time", "")))[:10]
if not ex_date or ex_date == "nan":
    continue
```

当 `ex_div_date` 字段存在但值为 `None` 时，`row.get("ex_div_date", ...)` 返回 `None`（不走 fallback），`str(None)` = `"None"`，不被现有过滤条件拦截，导致写入 DB 的 `ex_date = "None"`，污染复权因子表。

**修复方案：**
扩展过滤条件：
```python
if not ex_date or ex_date in ("nan", "None", "NaT"):
    continue
```

**验收标准：** 联调时检查 `adjust_factors` 表，`ex_date` 列无 `"None"`/`"nan"`/`"NaT"` 等非日期字符串。

---

## P3 — 技术债（下期跟踪，不阻塞本期上线）

| 编号 | 文件 | 行 | 摘要 |
|------|------|----|------|
| DEBT-1 | `adjustment_service.py` | 60 | `get_factors` 全量加载，可按 `end_date` 截断；依赖"DB 无未来事件"隐式假设 |
| DEBT-2 | `adjustment_service.py` | 93-94 | 每 bar 重复 filter+sort，可预处理一次降为 O(n log k) |
| DEBT-3 | `adjustment_service.py` | 32,51 | `adj_type` 不支持 `"none"` 返回原始价格，接口扩展性缺失 |
| DEBT-4 | `gap_detector.py` | 78 | `missing` 升序依赖无注释/断言，日后修改可能引入静默错误 |
| DEBT-5 | `adjust_factor_fetcher.py` | 70 | `KeyError` 与 `ValueError` 混合捕获，列名变更被静默吞掉 |
| DEBT-6 | `adjust_factor_fetcher.py` | 25 | SDK 内部异常无统一捕获，网络抖动时直接向上传播 |

---

## 验收 Checklist（Dev 完成后，QA 签收）

- [ ] TASK-1：除权日当天 `adjusted_bar[t].last_close == adjusted_bar[t-1].close`
- [ ] TASK-2：`_group_consecutive` 单测三场景全通过
- [ ] TASK-3：JSON 损坏时抛 `RuntimeError`，DB `is_active` 无变化
- [ ] TASK-4：重新激活股票的 `sync_status` 重置为 `pending`
- [ ] TASK-5：含现金分红股票前复权价格与富途 App 误差 < 0.01
- [ ] TASK-6：`adjust_factors` 表 `ex_date` 列无脏字符串

---

*本任务单由 QA/CR 于 2026-03-04 基于 commit 90229af 生成。*
