# Code Review Report — Round 2

**审查日期**：2026-03-04
**基准报告**：`docs/cr_report_2026-03-04.md`
**审查范围**：验证第一轮修复结果 + 新问题扫描

---

## 一、原始问题修复验证

| # | 原始问题 | 修复状态 | 核实说明 |
|---|---------|---------|---------|
| Bug 1a | `KlinePushHandler` 继承错误 | ✅ 正确 | `subscription_manager.py:27` 已继承 `KlineHandlerBase`，`super().__init__()` 正确调用 |
| Bug 1b | `setup_push_handler` 未调用 | ✅ 正确 | `main.py:151` 在连接后、watchlist 加载前调用 `setup_push_handler()` |
| Bug 2 | `failed` 空洞无法重试 | ✅ 正确 | `gap_repo.py:57-71` 用 `ON CONFLICT … DO UPDATE` 将 `failed` 重置为 `open` |
| Bug 3 | 分页截断 + `fetch()` 逻辑错误 | ✅ 正确 | `kline_fetcher.py:61-100` 重写为日期递进翻页；`sync_engine.py:280` 改调 `fetch()` |
| Bug 4 | `invalid_bars` 未写库 | ✅ 正确 | `sync_engine.py:236,267` 两处均调用 `insert_many(invalid_bars)` |
| Bug 5 | `rows_fetched/inserted` 累加 | ✅ 正确 | `sync_meta_repo.py:51-52` 改为直接赋 `excluded.rows_fetched` |
| Bug 6 | `makedirs` edge case | ✅ 正确 | `schema.py:154` 改用 `os.path.abspath(db_path)` |
| 缺陷 1 | `fetch_simple` 无分页 | ✅ 正确 | 方法已删除，统一走 `fetch()` |
| 缺陷 2 | `force_full` 时 `first_sync_date` 不更新 | ✅ 正确 | `sync_meta_repo.py:26` 新增 `force_first_sync_date` 参数；`sync_engine.py:133` 正确传入 |
| 缺陷 7 | `data_gaps` 无唯一约束 | ✅ 正确 | `schema.py:113` 加入 `UNIQUE (stock_code, period, gap_start, gap_end)` |
| Q4 | 日历/复权请求受 K线限频 | ✅ 正确 | 新增 `GeneralRateLimiter`（`rate_limiter.py:110`），独立限频器分离 |
| Q5 | 清空 watchlist 订阅残留 | ✅ 正确 | `main.py:157-166` 将 `sync_subscriptions` 移到 `if not active_stocks` 判断之前 |
| 缺陷 5 | 默认起始日与文档不符 | ⚠️ 保留 | `settings.py:38` 仍为 `2015-01-01`，与需求文档 `2000-01-01` 不一致，建议更新文档说明 |

---

## 二、遗留待确认项

### TODO — Q3：前复权因子是否重复累乘（待联调确认）

**文件**：`core/adjustment_service.py:79-94`

```python
def _calc_forward_multiplier(trade_date: str, factors: List[AdjustFactor]) -> float:
    multiplier = 1.0
    for factor in factors:
        if factor.ex_date > trade_date:
            multiplier *= factor.forward_factor   # ← 累乘所有 ex_date > t 的因子
    return multiplier
```

**疑点**：富途 `get_rehab` 返回的 `forward_factor` 存在两种可能：
- **单次因子**（每次除权事件的独立调整比例）→ 当前累乘逻辑**正确**
- **累积因子**（已是相对于最早日期的历史累积值）→ 当前累乘逻辑**错误**（会重复累乘）

代码注释（`adjust_factor_fetcher.py:47`）写到"富途直接提供累乘值"，但 `adjustment_service.py:87` 注释又写需要累乘各单次因子，两处说法矛盾。

**联调验证方法**：取一只有历史除权记录的 A 股（如贵州茅台 SH.600519），比对 `AdjustmentService.get_adjusted_klines()` 结果与富途 App 前复权价格，确认是否一致。

---

## 三、本轮新发现问题

### 新问题 1：K线拉取无重试保护（P1）

**文件**：`core/sync_engine.py:272-280`

```python
def _fetch_klines_paged(self, stock_code, period, start_date, end_date) -> list:
    return self._kline_fetcher.fetch(stock_code, period, start_date, end_date)
```

`KlineFetcher.fetch()` 内部每页调用 `rate_limiter.acquire()` 控速，但没有重试逻辑。对比日历/复权因子调用：

```python
# sync_engine.py:173,187
self._general_rate_limiter.execute_with_retry(self._calendar_fetcher.fetch, ...)
self._general_rate_limiter.execute_with_retry(self._adjust_factor_fetcher.fetch_factors, ...)
```

K线拉取是最核心的网络调用，超时或连接断开时整次同步直接失败，没有指数退避重试，而频率更低的日历/复权接口反而有重试保护。多页拉取时若第 N 页失败，已拉取的前 N-1 页数据已写入 DB（`INSERT OR IGNORE` 幂等），但本次同步状态会置为 `FAILED`，下次从 `last_sync_date`（未更新）重新全量拉取，存在重复拉取开销。

---

### 新问题 2：`GapRepository.upsert_gaps` 逐条开事务（P2）

**文件**：`db/repositories/gap_repo.py:57-71`

```python
for gap_start, gap_end in gaps:
    with DBConnection(self._db_path) as conn:   # ← 每条记录一次连接+事务
        conn.execute(...)
```

修复 Bug 2 时为实现 `ON CONFLICT` 逻辑从 `executemany` 改为逐条循环，但每条记录独立开关一次 `DBConnection`（含 `PRAGMA` 设置 + 事务提交）。

影响：
1. **性能**：检测到大量空洞时（如重激活长期停用的股票），N 条空洞产生 N 次连接开销
2. **原子性**：第 K 条写入成功后若进程崩溃，前 K 条已持久化、后续未写入，数据库处于中间状态

修复方向：将循环移入单个 `with DBConnection` 块内，对每条记录调用 `conn.execute()`，一个事务提交所有空洞。

---

### 新问题 3：`rows_inserted` 语义不明确（P3）

**文件**：`core/sync_engine.py:267-270`

```python
self._kline_repo.insert_many(invalid_bars)           # 写入但不计入返回值
rows_inserted = self._kline_repo.insert_many(valid_bars)  # 只统计有效行
return rows_fetched, rows_inserted
```

`sync_metadata.rows_inserted` 只记录有效行写入数，`invalid_bars` 的写入量未被计入。无注释说明语义，导致 `rows_inserted` 含义模糊：是"写入 DB 的总行数"还是"写入的有效行数"。建议在字段或变量上明确注释，或拆分为 `rows_inserted_valid` / `rows_inserted_invalid`。

---

### 新问题 4：双限频器合计可能超出富途全局上限（P3）

**文件**：`core/rate_limiter.py:23-107,110-174`

两个限频器各自独立维护计数：
- `RateLimiter`：30s 内最多 25 次（历史K线）
- `GeneralRateLimiter`：30s 内最多 60 次（其他接口）

两者合计上限为 30s/85 次，超出富途官方全局限制 30s/60 次。当前为单线程顺序调用，实际触发概率较低，但对于 watchlist 较大（20+ 只股票）的场景，一轮同步中历史K线 + 日历 + 复权因子请求总量可能超限。

建议：增加注释说明两者不能同时满负荷运行，或引入共享全局计数器作为兜底。

---

## 四、优先级汇总

| 优先级 | 问题 | 文件 & 行号 |
|--------|------|------------|
| TODO | Q3：前复权因子是否重复累乘 | `core/adjustment_service.py:79-94` |
| P1 | 新问题 1：K线拉取无重试保护 | `core/sync_engine.py:272-280` |
| P2 | 新问题 2：`upsert_gaps` 逐条事务 | `db/repositories/gap_repo.py:57-71` |
| P3 | 新问题 3：`rows_inserted` 语义不明 | `core/sync_engine.py:267-270` |
| P3 | 新问题 4：双限频器合计超全局上限 | `core/rate_limiter.py:23,110` |
| ⚠️ | 缺陷 5 遗留：默认起始日与文档不符 | `config/settings.py:38` |
