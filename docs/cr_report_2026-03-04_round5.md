# Code Review 报告 — Round 5

**项目**：AI 量化数据采集子系统
**审查日期**：2026-03-04
**覆盖文件**：main.py、config/settings.py、models/*.py、db/schema.py、db/connection.py、db/repositories/*.py、futu_wrap/*.py、core/*.py

---

## 问题列表

---

### CR-R5-01：`kline_repo.py` `insert_many` 的 `rowcount` 在 SQLite 下不可靠

- **优先级**：P1
- **文件 & 行号**：`db/repositories/kline_repo.py`，第 19–20 行
- **问题描述**：
  `cursor.rowcount` 在 `executemany` + `INSERT OR IGNORE` 组合下，SQLite 的行为取决于 Python 版本和驱动实现。Python 3.11 之前 `executemany` 的 `rowcount` 返回最后一条语句影响的行数（固定为 0 或 1），而非累计插入行数。即使在新版本中，`INSERT OR IGNORE` 的冲突行计为 `0`，`rowcount` 最终值只反映最后一条语句，依赖 `sqlite3_changes()`。

  `sync_engine.py` 第 272 行将 `insert_many` 的返回值作为 `rows_inserted` 写入 `sync_metadata`，导致监控数据失真（极可能显示为 0 或 1，而非真实插入行数）。

- **修复建议**：
  改用 `SELECT changes()` 方案：
  ```python
  with DBConnection(self._db_path) as conn:
      conn.executemany(sql, [...])
      total = conn.execute("SELECT changes()").fetchone()[0]
  return total
  ```
  `changes()` 返回本次事务内所有 `INSERT OR IGNORE` 实际插入（非忽略）的总行数，语义与预期完全吻合。

---

### CR-R5-02：`validator.py` 中 `object.__setattr__` 调用无效且逻辑矛盾

- **优先级**：P1
- **文件 & 行号**：`core/validator.py`，第 37–38 行
- **问题描述**：
  ```python
  object.__setattr__(bar, "is_valid", False) if hasattr(bar, "__dict__") else None
  ```
  两个问题：
  1. `KlineBar` 是普通 `@dataclass`（非 `frozen=True`），直接 `bar.is_valid = False` 即可，`object.__setattr__` 是为冻结 dataclass 准备的绕过方式，此处不必要。
  2. 这行代码修改了原始 `bar` 对象（in-place mutation），但 `invalid` 分支 append 的是新建的 `KlineBar(is_valid=False)`（下方第 39–53 行），对原始 `bar` 的修改无效，是副作用死代码。

  更严重的是：若 `hasattr(bar, "__dict__")` 为真，原始 `bar.is_valid` 已被设为 `False`，但此时它理应被放入 `valid` 列表——逻辑矛盾。

- **修复建议**：
  删除第 37–38 行。`invalid` 分支已正确构建了新 `KlineBar(is_valid=False)`，`valid` 分支直接使用原始 `bar`（其 `is_valid` 默认 `True`）即可。

---

### CR-R5-03：`adjustment_service.py` 对 `last_close` 使用了错误的复权系数

- **优先级**：P1
- **文件 & 行号**：`core/adjustment_service.py`，第 118 行
- **问题描述**：
  ```python
  last_close=round(bar.last_close * A + B, 4) if bar.last_close is not None else None,
  ```
  `last_close` 是**前一交易日的收盘价**（原始未复权）。当 `trade_date` 正好是除权日当天时，`last_close` 所属的前一交易日与 `trade_date` 适用的复权系数 `(A, B)` 不同——前一交易日应使用 `ex_date > (trade_date - 1)` 对应的系数。

  若两日之间有除权事件（即 `last_close` 所在日 < `ex_date` <= `trade_date`），对 `last_close` 施加 `trade_date` 的 `(A, B)` 会多乘一次该除权事件的因子，导致复权后的涨跌幅计算错误。

- **修复建议**：
  对 `last_close` 应使用前一交易日的复权系数。在 `get_adjusted_klines` 中按序遍历 bars 时，可将上一个 bar 的调整后 `close` 直接作为当前 bar 的 `last_close`：
  ```python
  prev_adj_close = None
  for bar in raw_bars:
      A, B = self._calc_forward_multiplier(bar.trade_date, factors)
      adj_bar = self._apply_adjustment(bar, A, B, prev_adj_close)
      adjusted_bars.append(adj_bar)
      prev_adj_close = adj_bar.close
  ```
  或对 `last_close` 单独计算前一交易日的 `(A_prev, B_prev)`。

---

### CR-R5-04：`kline_repo.py` `upsert_many` 的 `rowcount` 语义误导

- **优先级**：P2
- **文件 & 行号**：`db/repositories/kline_repo.py`，第 22、45 行
- **问题描述**：
  `upsert_many` 注释"返回受影响行数"，但 `ON CONFLICT ... DO UPDATE` 的 `rowcount` 在 SQLite 中对 INSERT 和 UPDATE 的计数行为不一致，同样存在 CR-R5-01 的问题，只反映最后一条语句影响的行数。

- **修复建议**：
  同 CR-R5-01，改为 `SELECT changes()` 方式，保持与 `insert_many` 的接口语义一致。

---

### CR-R5-05：两个限频器配额合计超出富途全局上限，且日历分段内部不受限频控制

- **优先级**：P2
- **文件 & 行号**：`core/rate_limiter.py`，第 33–34 行；`config/settings.py`，第 27、35 行
- **问题描述**：
  `RATE_LIMIT_MAX_IN_WINDOW`（K线，默认 25）+ `GENERAL_RATE_LIMIT_MAX_IN_WINDOW`（通用，默认 60）= 85 次/30s，超出富途全局限制 60 次/30s。注释说"单线程顺序执行不会同时打满"，但：

  `_ensure_calendar` 内部 `CalendarFetcher.fetch()` 对超过 365 天的范围发出多次 `request_trading_days` 请求，每段之间有 0.6s sleep，这些请求**不经过** `GeneralRateLimiter`（`execute_with_retry` 只计一次入口调用，内部分页不被计数）。当同步大量股票且需要刷新多年日历数据时，实际 API 调用频率可能大幅超出 60 次/30s。

- **修复建议**：
  将 `CalendarFetcher.fetch()` 的内部分段循环改为通过 `GeneralRateLimiter.acquire()` 控频，而不是硬编码 `time.sleep(0.6)`。建议将 `general_rate_limiter` 注入到 `CalendarFetcher` 构造函数中：
  ```python
  # calendar_fetcher.py
  def __init__(self, client: FutuClient, rate_limiter: RateLimiter):
      self._rate_limiter = rate_limiter

  # 每次分段请求前：
  self._rate_limiter.acquire()
  ret, data = self._client.ctx.request_trading_days(...)
  ```

---

### CR-R5-06：`sync_engine.py` `_heal_gaps` 与 `_fetch_and_store` 数据范围重叠，导致双倍 API 调用

- **优先级**：P2
- **文件 & 行号**：`core/sync_engine.py`，第 145–150 行
- **问题描述**：
  `_heal_gaps` 在 `[start_date, today]` 范围内检测并修复空洞，随后 `_fetch_and_store` 也在同样的 `[start_date, today]` 范围内拉取全量数据并以 `INSERT OR IGNORE` 写入。

  对于初次全量同步一只股票（`start_date=2015-01-01`），`_heal_gaps` 先检测出空洞（此时所有数据都是"空洞"），拉取一次；`_fetch_and_store` 再拉取一次，浪费了一倍的 API 配额。虽然 `INSERT OR IGNORE` 保证数据正确性，但 API 配额和耗时均被双重消耗。

- **修复建议**：
  调整执行顺序：`_fetch_and_store` 先执行（将数据写入），再执行 `_heal_gaps`（检测写入后仍缺失的区间）。这样初次同步时 `_heal_gaps` 发现的空洞已全部被 `_fetch_and_store` 填满，补填步骤几乎为零，避免双倍调用。

---

### CR-R5-07：`watchlist_manager.py` 中 `json_inactive_codes` 定义但从未使用

- **优先级**：P2
- **文件 & 行号**：`core/watchlist_manager.py`，第 47 行
- **问题描述**：
  ```python
  json_inactive_codes = {s.stock_code for s in json_stocks if not s.is_active}
  ```
  该集合在整个 `load()` 方法中从未被使用，是无效计算，可能是逻辑遗留代码。

- **修复建议**：
  删除该行。若后续需要对 JSON 中显式标记为 inactive 的股票做特殊处理，再按需补充。

---

### CR-R5-08：`db/connection.py` 每次连接均重复执行 `PRAGMA journal_mode=WAL`

- **优先级**：P2
- **文件 & 行号**：`db/connection.py`，第 13–16 行
- **问题描述**：
  每次 `with DBConnection(db_path)` 均执行：
  ```python
  self._conn.execute("PRAGMA journal_mode=WAL;")
  self._conn.execute("PRAGMA foreign_keys=ON;")
  ```
  `PRAGMA journal_mode=WAL` 是数据库级别的持久化配置，一旦设置即保持，**无需每次连接时重复设置**（产生额外 I/O 开销）。在单次 `run_full_sync` 中，多只股票多个周期将创建大量 `DBConnection`，`PRAGMA journal_mode=WAL` 将被反复执行数百次。

  `PRAGMA foreign_keys=ON` 是连接级配置，确实需要每次设置，无需改动。

- **修复建议**：
  将 `journal_mode=WAL` 从 `DBConnection.__enter__` 中移除，仅在 `schema.py` 的 `init_db()` 中设置一次（已有此调用）。`DBConnection` 仅保留 `foreign_keys=ON` 和 `row_factory` 设置。

---

### CR-R5-09：`subscription_manager.py` 推送 handler 中 `kl_type` 未知时静默 fallback 到 `"1D"`

- **优先级**：P2
- **文件 & 行号**：`futu_wrap/subscription_manager.py`，第 67 行
- **问题描述**：
  ```python
  period = _KL_TYPE_TO_PERIOD.get(kl_type, "1D")
  ```
  当 `kl_type` 不在映射表中时，静默 fallback 到 `"1D"`，会将非日 K 的推送数据错误地以 `period="1D"` 写入数据库，破坏数据完整性。当前批量跑批模式下不使用实时推送，但如果将来启用，该 bug 会静默污染数据。

- **修复建议**：
  ```python
  period = _KL_TYPE_TO_PERIOD.get(kl_type)
  if period is None:
      logger.warning("Unknown kl_type in push: %s, skipping", kl_type)
      return
  ```

---

### CR-R5-10：`schema.py` `init_db` 迁移 `ALTER TABLE` 在并发场景下可能抛 duplicate column 异常

- **优先级**：P2
- **文件 & 行号**：`db/schema.py`，第 164–176 行
- **问题描述**：
  若多进程并发运行 `init_db`（例如测试或部署脚本意外并发），两个进程同时通过 `PRAGMA table_info` 发现列不存在，同时执行 `ALTER TABLE`，SQLite 会抛出 `OperationalError: duplicate column name`，导致 `init_db` 崩溃。

- **修复建议**：
  将 `ALTER TABLE` 包裹在 `try/except sqlite3.OperationalError`，捕获 duplicate column 错误并静默忽略（幂等）：
  ```python
  for col, ddl in [
      ("forward_factor_b", "ALTER TABLE adjust_factors ADD COLUMN forward_factor_b REAL NOT NULL DEFAULT 0"),
      ("backward_factor_b", "ALTER TABLE adjust_factors ADD COLUMN backward_factor_b REAL NOT NULL DEFAULT 0"),
  ]:
      if col not in existing:
          try:
              conn.execute(ddl)
          except sqlite3.OperationalError:
              pass  # 并发场景下已被其他进程添加，忽略
  ```

---

### CR-R5-11：`calendar_fetcher.py` 未对 `data` 类型做防御，依赖 SDK 返回 `list[dict]`

- **优先级**：P2
- **文件 & 行号**：`futu_wrap/calendar_fetcher.py`，第 60–61 行
- **问题描述**：
  ```python
  if data:
      all_days.extend(item["time"][:10] for item in data)
  ```
  若 SDK 某版本将 `data` 返回为 `DataFrame`（部分富途 SDK 版本存在此差异），则 `item["time"]` 会引发 `TypeError`。当前代码无类型保护，SDK 版本变化时会静默崩溃。

- **修复建议**：
  在注释中明确注明依赖 SDK 返回 `list[dict]` 类型，并添加防御性断言或类型检查：
  ```python
  if data:
      # request_trading_days 返回 list[dict]，每个 dict 含 "time" 键
      assert isinstance(data, list), f"Unexpected data type from request_trading_days: {type(data)}"
      all_days.extend(item["time"][:10] for item in data)
  ```

---

### CR-R5-12：`adjust_factor_repo.py` 方法名 `upsert_many` 与实际行为 `INSERT OR IGNORE` 不符

- **优先级**：P3
- **文件 & 行号**：`db/repositories/adjust_factor_repo.py`，第 10–11 行
- **问题描述**：
  方法名为 `upsert_many`（通常语义为 insert or update），但实际 SQL 为 `INSERT OR IGNORE`（存在冲突时不更新）。若富途 API 修正了历史因子值（数据订正场景），该方法会静默忽略，导致 DB 保留错误的旧因子。

- **修复建议**：
  若确实要求"不修改历史因子"，将方法名改为 `insert_new_only`，并在注释中说明原因。若需支持数据订正，改为 `ON CONFLICT DO UPDATE`。

---

### CR-R5-13：`main.py` 中 `SubscriptionManager` 注释缺失，误导实时推送功能已激活

- **优先级**：P3
- **文件 & 行号**：`main.py`，第 92、112–115 行
- **问题描述**：
  `subscription_manager` 被构建并暴露，但 `sync_subscriptions` 的实现仅取消所有已有订阅（清理动作），实时推送功能未激活。`KlinePushHandler` 等代码已实例化备用，缺少注释说明，增加维护者理解成本。

- **修复建议**：
  在 `SubscriptionManager.sync_subscriptions` 和 `KlinePushHandler` 类上补充注释，明确标注"跑批模式下仅执行清理，实时推送功能未激活"。

---

### CR-R5-14：`validator.py` 日期格式检查仅验证长度，未验证 YYYY-MM-DD 解析有效性

- **优先级**：P3
- **文件 & 行号**：`core/validator.py`，第 92–93 行
- **问题描述**：
  ```python
  if not bar.trade_date or len(bar.trade_date) != 10:
  ```
  只检查长度为 10，`"2024-13-99"` 等非法日期也能通过。

- **修复建议**：
  ```python
  try:
      datetime.strptime(bar.trade_date, "%Y-%m-%d")
  except (ValueError, TypeError):
      issues.append(f"invalid trade_date={bar.trade_date!r}")
  ```

---

### CR-R5-15：`settings.py` 中 `ALL_PERIODS` 与 `Period` 枚举双重维护，存在不同步风险

- **优先级**：P3
- **文件 & 行号**：`config/settings.py`，第 50 行；`models/enums.py`，第 12–15 行
- **问题描述**：
  `Period` 枚举已完整定义了周期集合，但 `settings.py` 中 `ALL_PERIODS` 是手动维护的字符串列表，形成双重来源。若将来增加新周期，需同时在两处修改。

- **修复建议**：
  ```python
  from models.enums import Period
  ALL_PERIODS = [p.value for p in Period]
  ```

---

### CR-R5-16：`gap_detector.py` `_group_consecutive` 中 `td_index.get` fallback `-1` 存在潜在误合并

- **优先级**：P3
- **文件 & 行号**：`core/gap_detector.py`，第 120–122 行
- **问题描述**：
  ```python
  prev_idx = td_index.get(prev, -1)
  curr_idx = td_index.get(curr, -1)
  if curr_idx == prev_idx + 1:
  ```
  若 `prev` 和 `curr` 均不在 `td_index` 中（异常情况），则 `-1 + 1 == -1 + 1`，条件成立，两个"不在索引中"的日期会被错误地判定为连续并合并到同一 gap 区间。

- **修复建议**：
  若 `td_index.get` 返回 `-1`，应记录 WARNING 并跳过：
  ```python
  if prev_idx == -1 or curr_idx == -1:
      logger.warning("Date not in trading_days index: prev=%s, curr=%s", prev, curr)
      gaps.append((current_start, current_end))  # 结束当前 group
      current_start = current_end = curr
      continue
  ```

---

## 优先级汇总表

| 编号 | 优先级 | 文件 & 行号 | 问题摘要 |
|------|--------|------------|---------|
| CR-R5-01 | P1 | `db/repositories/kline_repo.py:19-20` | `insert_many` rowcount 在 executemany+INSERT OR IGNORE 下不可靠 |
| CR-R5-02 | P1 | `core/validator.py:37-38` | `object.__setattr__` 无效且与 valid 分支逻辑矛盾 |
| CR-R5-03 | P1 | `core/adjustment_service.py:118` | `last_close` 复权使用了错误交易日的复权系数 |
| CR-R5-04 | P2 | `db/repositories/kline_repo.py:22,45` | `upsert_many` rowcount 语义误导 |
| CR-R5-05 | P2 | `core/rate_limiter.py:33-34`；`config/settings.py:27,35` | 双限频器配额超出富途全局上限；日历分段不受限频控制 |
| CR-R5-06 | P2 | `core/sync_engine.py:145-150` | `_heal_gaps` 与 `_fetch_and_store` 范围重叠，双倍 API 调用 |
| CR-R5-07 | P2 | `core/watchlist_manager.py:47` | `json_inactive_codes` 定义但从未使用（死代码） |
| CR-R5-08 | P2 | `db/connection.py:13-16` | `PRAGMA journal_mode=WAL` 每次连接重复设置 |
| CR-R5-09 | P2 | `futu_wrap/subscription_manager.py:67` | `kl_type` 未知时静默 fallback 到 `"1D"` 可能污染数据 |
| CR-R5-10 | P2 | `db/schema.py:164-176` | 并发 `init_db` 时迁移 `ALTER TABLE` 可能抛 duplicate column 异常 |
| CR-R5-11 | P2 | `futu_wrap/calendar_fetcher.py:60-61` | `data` 类型依赖 SDK 版本，未做类型保护 |
| CR-R5-12 | P3 | `db/repositories/adjust_factor_repo.py:10-11` | 方法名 `upsert_many` 与实际行为 `INSERT OR IGNORE` 不符 |
| CR-R5-13 | P3 | `main.py:92,112-115` | `SubscriptionManager` 实时推送未激活但缺少注释说明 |
| CR-R5-14 | P3 | `core/validator.py:92-93` | 日期格式仅验证长度，未验证 YYYY-MM-DD 解析有效性 |
| CR-R5-15 | P3 | `config/settings.py:50` | `ALL_PERIODS` 与 `Period` 枚举双重维护 |
| CR-R5-16 | P3 | `core/gap_detector.py:120-122` | `_group_consecutive` fallback `-1` 存在潜在误合并 |

**P1 合计：3 项，P2 合计：8 项，P3 合计：5 项，共 16 项**

---

*报告生成时间：2026-03-04*
*基于 Round 1–4 已修复问题均不重复报告。*
