# 迭代6 Code Review 报告

**日期**：2026-03-20
**Reviewer**：QA
**Review 范围**：FEAT-version / FEAT-check-gaps / FEAT-repair（全部7个改动文件）
**PRD 版本**：requirements_iter6.md v1.0
**涉及文件**：
- `config/settings.py`
- `api/main.py`
- `web/src/api/client.js`
- `web/src/pages/StockAnalysis.jsx`
- `.env.example`
- `main.py`（`setup_logging_check_gaps` / `cmd_check_gaps` / `cmd_repair`）
- `core/sync_engine.py`（`repair_one`）

---

## P0（阻塞发布）

> 本次 CR **未发现 P0 级问题**。

---

## P1（应当修复，影响功能正确性）

### [P1-01] `cmd_check_gaps`：calendar missing 检测为死代码，终端错误显示 "OK"

- **文件**：`main.py` L588–603
- **问题描述**：

  `GapDetector.detect_gaps()` 在日历缺失时**不抛异常**，而是调用 `calendar_repo.get_trading_days()` 返回 `[]` 后直接 `return []`（见 `core/gap_detector.py` L65–70）：

  ```python
  if not trading_days:
      logger.warning(
          "No trading days found for %s [%s~%s], cannot detect gaps",
          calendar_market, start_date, end_date
      )
      return []   # ← 返回空列表，不抛异常
  ```

  而 `cmd_check_gaps` 中，`calendar_missing` 分支处于 `except Exception` 块内：

  ```python
  try:
      gaps = gap_detector.detect_gaps(...)
  except Exception as e:
      # 此路径在 "日历缺失" 时永远不会触发！
      logger.warning("  [%s] Trading calendar missing ...", period, ...)
      stock_gap_summary.append((period, 0, "calendar_missing"))
      continue

  # detect_gaps 日历缺失时返回 [], 代码走到这里
  n_gaps = len(gaps)  # n_gaps == 0
  if n_gaps == 0:
      logger.info("  [%s] No gaps found.", period)  # 错误地报告"no gaps"
      stock_gap_summary.append((period, 0, "ok"))
  ```

  **后果**：
  1. 日历缺失时，终端输出错误显示 `OK (no gaps)`，而 PRD 要求显示 `⚠  calendar missing for [1D] (skipped)`
  2. 日志中 `main.check_gaps` 上下文不输出 "calendar missing" 警告（仅 `core.gap_detector` 有内部 warning），与 PRD § 2.4 日志规格不符
  3. 用户可能因此误判数据完整，而实际上该周期的空洞根本未被检测

- **影响范围**：任何本地交易日历尚未同步的市场股票（如 US 市场未 sync 过），check-gaps 均会静默给出误导性"no gaps"结论
- **修复建议**：在 `detect_gaps()` 调用前，增加日历是否存在的预检查；若日历缺失则跳过并记录：

  ```python
  # 在 cmd_check_gaps 中，调用 detect_gaps 之前插入
  calendar_market = "SH" if stock.market == "A" else stock.market
  if not calendar_repo.has_calendar(calendar_market, DEFAULT_HISTORY_START, today_str):
      logger.warning(
          "  [%s] Trading calendar missing for %s [%s~%s], skipping gap detection.",
          period, stock.market, DEFAULT_HISTORY_START, today_str
      )
      stock_gap_summary.append((period, 0, "calendar_missing"))
      continue
  # 然后再调用 detect_gaps
  gaps = gap_detector.detect_gaps(...)
  ```

---

## P2（建议优化，不阻塞发布）

### [P2-01] `cmd_repair`：`repair started` 日志缺少 `stocks=N` 字段

- **文件**：`main.py` L686–691
- **问题描述**：

  PRD § 3.5 日志规格示例：
  ```
  repair started. date=2026-03-19, stocks=2, periods=['1D']
  ```
  实际代码：
  ```python
  logger.info(
      "repair started. date=%s, periods=%s",
      args.date, periods
  )
  ```
  `stocks=N` 字段缺失。原因是该日志写在股票列表确定**之前**（`total_stocks` 尚未赋值），导致无法直接引用。

- **修复建议**：将 `repair started` 日志移到股票列表确定后，或先确定股票列表再打印启动日志：
  ```python
  # 先确定股票列表（提前到 logger.info 之前）
  ...
  total_stocks = len(stocks_to_repair)
  logger.info("=" * 60)
  logger.info(
      "repair started. date=%s, stocks=%d, periods=%s",
      args.date, total_stocks, periods
  )
  logger.info("=" * 60)
  ```

---

### [P2-02] `cmd_repair`：`stock_repo` 重复实例化

- **文件**：`main.py` L706–708
- **问题描述**：

  `build_dependencies()` 已在内部创建 `StockRepository` 实例并以 `"stock_repo"` 键返回到 `deps` 字典中，但 `cmd_repair` 另行单独实例化了一个新的 `StockRepository`：

  ```python
  deps = build_dependencies(futu_client)       # deps["stock_repo"] 已包含实例
  stock_repo = StockRepository(DB_PATH)        # ← 冗余，重复实例化
  sync_engine: SyncEngine = deps["sync_engine"]
  ```

  SQLite 允许多连接，不影响正确性，但浪费资源且不一致。

- **修复建议**：
  ```python
  deps = build_dependencies(futu_client)
  stock_repo = deps["stock_repo"]   # 复用已有实例
  sync_engine: SyncEngine = deps["sync_engine"]
  ```

---

### [P2-03] `cmd_repair`：未使用的 `DEFAULT_HISTORY_START` 导入

- **文件**：`main.py` L682
- **问题描述**：

  ```python
  from config.settings import ALL_PERIODS, DEFAULT_HISTORY_START
  ```

  `DEFAULT_HISTORY_START` 在 `cmd_repair` 函数体内从未引用，属于死导入。

- **修复建议**：移除未使用的导入：
  ```python
  from config.settings import ALL_PERIODS
  ```

---

## 通过项（已确认正确的关键逻辑）

### FEAT-version

| 检查点 | 结论 |
|--------|------|
| `config/settings.py`：`APP_VERSION = os.getenv("APP_VERSION", "dev")`，默认值 `"dev"` | ✅ 通过 |
| `api/main.py`：正确 `import APP_VERSION`，`/api/health` 响应含 `"version": APP_VERSION` | ✅ 通过 |
| `api/main.py`：FastAPI app 自身的 `version="0.3.0"` 参数与 `APP_VERSION` 分离，语义不冲突 | ✅ 通过 |
| `web/src/api/client.js`：`fetchHealth()` 封装正确，返回完整 `res.data` | ✅ 通过 |
| `web/src/pages/StockAnalysis.jsx`：`useState(null)` 初始化，`fetchHealth().catch(() => {})` 静默降级 | ✅ 通过 |
| 前端：`{appVersion && <span>...}</span>` — `version` 字段缺失/接口失败时不展示、不报错 | ✅ 通过 |
| `.env.example`：`APP_VERSION=v0.6.0` 明确未注释（提醒用户手动更新），注释说明清晰 | ✅ 通过 |
| 边界：`.env` 未配置 `APP_VERSION` → 后端返回 `"dev"` → 前端显示 `dev` | ✅ 通过 |

### FEAT-check-gaps

| 检查点 | 结论 |
|--------|------|
| `--period` 使用 `nargs="+"` + `choices=["1D", "1W", "1M"]`，支持多值传参 | ✅ 通过 |
| 检测范围：`start_date=DEFAULT_HISTORY_START`，`end_date=date.today()` | ✅ 通过 |
| 无需 Futu 连接：仅使用 `StockRepository / CalendarRepository / KlineRepository / GapRepository / GapDetector`，均为本地 DB 操作 | ✅ 通过 |
| 空洞持久化：调用 `gap_repo.upsert_gaps(stock.stock_code, period, gaps)` 写入 `data_gaps`（status=open） | ✅ 通过 |
| 幂等：`upsert_gaps` ON CONFLICT 逻辑：open/filling/filled 不变，failed 重置为 open | ✅ 通过 |
| 独立日志文件：`check_gaps_{YYYYMMDD}.log`，不写入 `sync_{YYYYMMDD}.log` | ✅ 通过 |
| 日志格式与 sync 统一：`%(asctime)s [%(levelname)s] %(name)s: %(message)s` | ✅ 通过 |
| `--stock` 不存在时：打印 WARNING 并 `return`（非 `sys.exit(1)`），正常退出码 | ✅ 通过 |
| 无活跃股票边界：`stocks_to_check = []` 时，循环不执行，打印汇总 `0/0`，无崩溃 | ✅ 通过 |
| 终端汇总格式：含 stocks_with_gaps / total_gaps_found / persisted 数量 + `sync` 提示 | ✅ 通过 |
| 子命令注册：`nargs="+" / choices / set_defaults` 与 PRD § 2.6 完全一致 | ✅ 通过 |

### FEAT-repair

| 检查点 | 结论 |
|--------|------|
| `--date` 格式校验：`date.fromisoformat(args.date)` 捕获 `ValueError` → 打印错误信息 + `sys.exit(1)` | ✅ 通过 |
| `--date` 未来日期：打印 WARNING，继续执行（不退出） | ✅ 通过 |
| 1D 映射：`fetch_start = fetch_end = args.date` | ✅ 通过 |
| 1W 映射：`week_start = target_date - timedelta(days=target_date.weekday())`（周一），`week_end = week_start + 6`（周日），超 today 取 today | ✅ 通过 |
| 1M 映射：`month_start = target_date.replace(day=1)`（月初1日），`month_end` 正确处理12月边界，超 today 取 today | ✅ 通过 |
| `repair_one`：全部走 `kline_repo.upsert_many()`（含 valid_bars 和 invalid_bars），不调用 `insert_many` | ✅ 通过 |
| `repair_one`：不调用 `sync_meta_repo` 任何方法，不修改 `sync_metadata` 表 | ✅ 通过 |
| `repair_one` 返回值：`(rows_fetched, rows_upserted)`，`rows_upserted` 仅计 valid_bars，invalid_bars 覆盖写但不计入返回值（与 PRD 规格一致） | ✅ 通过 |
| `_ensure_calendar` 失败：捕获异常记 WARNING，继续执行 `repair_one`（日历失败不阻断修复） | ✅ 通过 |
| `--stock` 不在 stocks 表：打印 WARNING，`return`（在 `try` 块内，`finally` 仍 disconnect），正常退出码 | ✅ 通过 |
| OpenD 未启动：`futu_client.connect()` 异常 → 打印错误 + `sys.exit(1)` | ✅ 通过 |
| 单个任务失败：捕获异常记 ERROR，`total_failed` 计数，继续处理下一只股票 | ✅ 通过 |
| 终端汇总：含 total_fetched / total_upserted，`total_failed > 0` 时额外打印失败数量 | ✅ 通过 |
| 子命令注册：`required=True` for `--date`，`nargs="+"` for `--period`，与 PRD § 3.7 一致 | ✅ 通过 |

### core/sync_engine.py

| 检查点 | 结论 |
|--------|------|
| `repair_one` 方法签名：`(self, stock: Stock, period: str, fetch_start: str, fetch_end: str) -> Tuple[int, int]` | ✅ 通过 |
| `Tuple` 类型已从 `typing` 导入 | ✅ 通过 |
| 复用 `_fetch_klines_paged`（分页拉取，限频器已内置） | ✅ 通过 |
| `_validator.validate_many(bars)` 调用正确 | ✅ 通过 |
| 日志上下文：`logger = logging.getLogger(__name__)` → `core.sync_engine`，与 PRD 日志示例一致 | ✅ 通过 |

---

## 总结

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 | 0 | 无阻塞发布问题 |
| P1 | 1 | `cmd_check_gaps` calendar missing 场景未能正确检测（except 块为死代码），终端误报 "OK" |
| P2 | 3 | `repair started` 日志缺 stocks 数量；`stock_repo` 冗余实例化；`DEFAULT_HISTORY_START` 未使用导入 |

**建议**：修复 P1-01 后即可发布。P2-01/02/03 改动量极小，建议在本次迭代内一并处理。

---

## 复查记录（v1.1）

**复查日期**：2026-03-20
**复查 commit**：1a8166c
**复查结论**：全部 P1/P2 问题已正确修复，复查通过。

| 编号 | 修复内容 | 复查结论 |
|------|--------|--------|
| P1-01 | `cmd_check_gaps` 移除 `try/except`，在 `detect_gaps()` 调用前增加 `calendar_repo.has_calendar()` 前置检查（L591）；日历缺失时输出 WARNING 日志并 `continue`，不再走 "No gaps found" 路径 | ✅ 已确认。A股映射正确使用 `A_STOCK_CALENDAR_MARKET`（L590），日历缺失分支终端输出符合 PRD 格式 |
| P2-01 | `repair started` 日志移到股票列表确定后（`total_stocks` 赋值后），包含 `stocks=%d` 字段（L721–725） | ✅ 已确认，日志格式与 PRD § 3.5 一致 |
| P2-02 | `stock_repo` 改为 `deps["stock_repo"]` 复用已有实例，不再重复实例化（L702） | ✅ 已确认，仅一处实例化 |
| P2-03 | `cmd_repair` 中 `DEFAULT_HISTORY_START` 无用导入已删除，L684 仅保留 `from config.settings import ALL_PERIODS` | ✅ 已确认，无死导入 |

**最终结论：迭代6代码复查通过，可进入产品验收阶段。**

---

*CR 报告 v1.1，2026-03-20，QA（v1.0 初版 → v1.1 复查通过）*
