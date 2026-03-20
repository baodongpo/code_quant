# 产品需求文档 · 迭代6

**文档版本**：v1.0
**日期**：2026-03-20
**作者**：PM
**适用对象**：Dev（实现）、QA（验收）
**迭代目标**：运维能力增强 + 版本可视化

---

## 目录

1. [FEAT-version：前端展示版本号](#1-feat-version前端展示版本号)
2. [FEAT-check-gaps：独立空洞检测子命令](#2-feat-check-gaps独立空洞检测子命令)
3. [FEAT-repair：K线数据强制修复子命令](#3-feat-repair-k线数据强制修复子命令)
4. [配置变更汇总](#4-配置变更汇总)
5. [不在范围内](#5-不在范围内)

---

## 1. FEAT-version：前端展示版本号

### 1.1 需求概述

主页面导航栏右上角展示系统版本号（如 `v0.5.1-fix`），与当前 git tag 保持人工一致。版本号通过后端 `/api/health` 接口透传给前端，前端静态展示。

### 1.2 功能逻辑

#### 后端（Python）

**新增配置项**（`config/settings.py`）：

```python
# ============================================================
# 系统版本号（与 git tag 保持一致，在 .env 中手动维护）
# ============================================================
APP_VERSION = os.getenv("APP_VERSION", "dev")
```

**修改 `/api/health` 接口**（`api/main.py`）：

在健康检查响应中新增 `version` 字段：

```python
@app.get("/api/health", tags=["system"])
def health():
    """服务健康检查，返回 ok、当前时间戳和版本号。"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,   # 新增字段
    }
```

响应示例：

```json
{
  "status": "ok",
  "timestamp": "2026-03-20T08:30:00+00:00",
  "version": "v0.6.0"
}
```

#### 前端（React）

- 页面加载时调用 `/api/health`，从响应中取出 `version` 字段
- 展示位置：导航栏右上角，紧靠现有元素右侧
- 展示格式：灰色小字，如 `v0.6.0`（不需要图标，不需要点击跳转）
- 若接口未返回 `version` 字段（兼容旧后端），则不展示该区域（静默降级）

#### 配置说明

`.env.example` 新增：

```
# 系统版本号（与 git tag 保持一致，升级时手动更新）
APP_VERSION=v0.6.0
```

### 1.3 边界条件

| 场景 | 处理方式 |
|------|---------|
| `.env` 未配置 `APP_VERSION` | 后端返回 `"dev"`，前端展示 `dev` |
| 前端调用 `/api/health` 失败 | 版本号区域不展示，不影响其他功能 |
| 后端旧版本不含 `version` 字段 | 前端静默降级，不报错 |

---

## 2. FEAT-check-gaps：独立空洞检测子命令

### 2.1 需求概述

新增 `python main.py check-gaps` 子命令，对本地 K 线数据库执行空洞检测。只检测、不修复（修复仍由 `sync` 完成）。检测结果写入 `data_gaps` 表（`status=open`），并输出日志和终端汇总。

**重要**：此命令无需连接富途 OpenD，只读本地数据库。

### 2.2 命令参数规格

```
python main.py check-gaps [--stock STOCK_CODE] [--period PERIOD [PERIOD ...]]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--stock` | `str` | 否 | 指定单只股票代码，如 `HK.00700`；不传则检测 watchlist 中所有活跃股票 |
| `--period` | `str`（可多选） | 否 | 指定周期，可选值 `1D` `1W` `1M`；可同时传多个，如 `--period 1D 1W`；不传则检测全部三个周期 |

**用法示例**：

```bash
# 检测所有活跃股票的全部周期
./env_quant/bin/python main.py check-gaps

# 仅检测某只股票
./env_quant/bin/python main.py check-gaps --stock HK.00700

# 仅检测日K数据
./env_quant/bin/python main.py check-gaps --period 1D

# 检测某只股票的日K和周K
./env_quant/bin/python main.py check-gaps --stock SH.600519 --period 1D 1W
```

### 2.3 功能逻辑

#### 执行流程

```
1. setup_logging_check_gaps()   → 初始化日志，写入 logs/check_gaps_YYYYMMDD.log
2. init_db(DB_PATH)             → 确保 DB 已初始化（幂等）
3. 确定检测股票列表             → 按 --stock 参数过滤，或取 watchlist 全部活跃股票
4. 确定检测周期列表             → 按 --period 参数，或 ALL_PERIODS
5. 对每只股票 × 每个周期：
   a. 调用 GapDetector.detect_gaps(
        stock_code, period, market,
        start_date=DEFAULT_HISTORY_START,
        end_date=today
      )
   b. 若发现空洞 → 调用 gap_repo.upsert_gaps() 写入 data_gaps（status=open）
   c. 记录检测结论到日志
6. 输出汇总统计到终端（stdout）和日志
```

#### 股票来源

- 从 `stocks` 表读取所有 `is_active=1` 的股票（通过 `StockRepository.get_all()` 过滤）
- 若 `--stock` 参数指定了不在 stocks 表中的股票代码，打印 WARNING 并跳过（不退出）

#### 注意事项

- **无需 Futu 连接**：`GapDetector` 只读本地 DB（`calendar_repo`、`kline_repo`），不调用富途 API
- **交易日历依赖**：若本地交易日历缺失，`GapDetector` 会记录 WARNING 并返回空列表（无法检测该区间）；命令需在日志中记录"日历缺失，跳过检测"
- **不修改 sync_metadata**：check-gaps 只写 `data_gaps` 表，不触碰 `sync_metadata`
- **幂等**：多次运行对同一空洞，`upsert_gaps` 的 ON CONFLICT 逻辑确保不重复写入（已有 open/filling/filled 状态的不变，仅 failed 状态重置为 open）

### 2.4 日志规格

#### 日志文件

路径：`logs/check_gaps_YYYYMMDD.log`（按调用日期命名）
格式：与 sync 日志统一

```
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

#### 日志内容示例

```
2026-03-20 10:00:01 [INFO] main.check_gaps: ============================================================
2026-03-20 10:00:01 [INFO] main.check_gaps: check-gaps started. stocks=3, periods=['1D', '1W', '1M']
2026-03-20 10:00:01 [INFO] main.check_gaps: DB: /path/to/quant.db
2026-03-20 10:00:01 [INFO] main.check_gaps: Detect range: 2000-01-01 ~ 2026-03-20
2026-03-20 10:00:01 [INFO] main.check_gaps: ============================================================
2026-03-20 10:00:01 [INFO] main.check_gaps: [1/3] Checking HK.00700 ...
2026-03-20 10:00:01 [INFO] main.check_gaps:   [1D] No gaps found.
2026-03-20 10:00:01 [INFO] main.check_gaps:   [1W] No gaps found.
2026-03-20 10:00:01 [INFO] main.check_gaps:   [1M] No gaps found.
2026-03-20 10:00:02 [INFO] main.check_gaps: [2/3] Checking SH.600519 ...
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1D] Found 2 gap(s): [2020-02-03~2020-02-03, 2021-09-08~2021-09-09]
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1D] Persisted 2 gap(s) to data_gaps (status=open).
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1W] No gaps found.
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1M] No gaps found.
2026-03-20 10:00:02 [INFO] main.check_gaps: [3/3] Checking US.AAPL ...
2026-03-20 10:00:02 [WARNING] main.check_gaps:   [1D] Trading calendar missing for US [2000-01-01~2026-03-20], skipping gap detection.
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1W] No gaps found.
2026-03-20 10:00:02 [INFO] main.check_gaps:   [1M] No gaps found.
2026-03-20 10:00:02 [INFO] main.check_gaps: ============================================================
2026-03-20 10:00:02 [INFO] main.check_gaps: check-gaps completed.
2026-03-20 10:00:02 [INFO] main.check_gaps: Stocks checked : 3
2026-03-20 10:00:02 [INFO] main.check_gaps: Stocks with gaps: 1
2026-03-20 10:00:02 [INFO] main.check_gaps: Total gaps found: 2
2026-03-20 10:00:02 [INFO] main.check_gaps: ============================================================
```

### 2.5 终端输出格式（stdout）

```
================================================================
  AI Quant — check-gaps  (2026-03-20)
================================================================
  Stocks checked : 3
  Periods        : 1D, 1W, 1M
  Detect range   : 2000-01-01 ~ 2026-03-20
================================================================

  Checking HK.00700  ...  OK (no gaps)
  Checking SH.600519 ...  ⚠  2 gap(s) found in [1D]
  Checking US.AAPL   ...  ⚠  calendar missing for [1D] (skipped)

================================================================
  Summary:
    Stocks with gaps : 1 / 3
    Total gaps found : 2
    Persisted to DB  : 2  (data_gaps, status=open)

  Run `python main.py sync` to repair gaps automatically.
================================================================
```

### 2.6 main.py 注册方式

参考现有 `cmd_stats` 和 `cmd_migrate` 的写法，在 `main()` 中注册新子命令：

```python
# 子命令：check-gaps
sub_check_gaps = subparsers.add_parser(
    "check-gaps",
    help="独立空洞检测（只检测，不修复；检测结果写入 data_gaps 表）"
)
sub_check_gaps.add_argument(
    "--stock", dest="stock", default=None,
    help="指定股票代码（不传则检测所有活跃股票）"
)
sub_check_gaps.add_argument(
    "--period", dest="period", nargs="+", choices=["1D", "1W", "1M"], default=None,
    help="指定周期（可多选：1D 1W 1M；不传则检测全部）"
)
sub_check_gaps.set_defaults(func=cmd_check_gaps)
```

---

## 3. FEAT-repair：K线数据强制修复子命令

### 3.1 需求概述

新增 `python main.py repair` 子命令，支持对指定股票/周期/日期的 K 线数据执行强制 `upsert` 覆盖写入，用于手动修复已知异常数据（如半日数据、数据源错误等）。

**重要**：此命令需要连接富途 OpenD，拉取最新数据后覆盖写入数据库。

### 3.2 命令参数规格

```
python main.py repair --date DATE [--stock STOCK_CODE] [--period PERIOD [PERIOD ...]]
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--date` | `str`（YYYY-MM-DD） | **是** | 目标业务日期，如 `2026-03-19` |
| `--stock` | `str` | 否 | 指定单只股票代码；不传则修复 watchlist 所有活跃股票 |
| `--period` | `str`（可多选） | 否 | 指定周期；不传则修复全部三个周期（`1D 1W 1M`） |

**用法示例**：

```bash
# 修复所有股票 2026-03-19 的全部周期数据
./env_quant/bin/python main.py repair --date 2026-03-19

# 修复某只股票的当日日K
./env_quant/bin/python main.py repair --date 2026-03-20 --stock HK.00700 --period 1D

# 修复某只股票某周的周K
./env_quant/bin/python main.py repair --date 2026-03-20 --stock SH.600519 --period 1W

# 修复多个周期
./env_quant/bin/python main.py repair --date 2026-03-19 --stock US.AAPL --period 1D 1M
```

### 3.3 业务日期 → fetch 区间映射

用户传入的是**业务日期**，命令内部需根据周期类型映射为实际的 fetch 区间（`start_date`、`end_date`）。

#### 数据规律（2026-03-20 实测）

| 周期 | trade_date 规律 | fetch 区间说明 |
|------|----------------|--------------|
| 1D | 当天 | `start=date`，`end=date` |
| 1W | 该周最后一个交易日（港股=周五） | `start=该周一`，`end=该周最后一天（自然日周日）` |
| 1M | 该月第一个交易日 | `start=该月1日`，`end=该月最后一天` |

#### 1W 特别说明

- `start=today,end=today` 查询 Futu 历史接口**返回空**（富途接口行为），故 1W 必须使用包含整周的区间，确保 Futu 返回本周的周K bar
- 计算方式：
  - `week_start` = date 所在周的周一（`date - timedelta(days=date.weekday())`）
  - `week_end` = date 所在周的周日（`week_start + timedelta(days=6)`），若超过 `today`，则取 `today`

#### 1M 特别说明

- trade_date 实测为**该月第一个交易日**（非1号，若1号为非交易日则顺延）
- 计算方式：
  - `month_start` = date 所在月的1日（`date.replace(day=1)`）
  - `month_end` = date 所在月的最后一天，若超过 `today`，则取 `today`

### 3.4 功能逻辑

#### 执行流程

```
1. 参数验证：--date 格式必须为 YYYY-MM-DD，否则报错退出
2. setup_logging()            → 复用 sync 日志格式，输出到 sync_YYYYMMDD.log
3. init_db(DB_PATH)           → 确保 DB 已初始化
4. 连接富途 OpenD             → 与 sync 相同的连接方式
5. 确定修复股票列表           → --stock 过滤 或 全部活跃股票
6. 确定修复周期列表           → --period 过滤 或 ALL_PERIODS
7. 对每只股票 × 每个周期：
   a. 计算 fetch_start、fetch_end（按上节映射规则）
   b. 确保交易日历已存在（调用 _ensure_calendar）
   c. 调用 SyncEngine.repair_one(stock, period, fetch_start, fetch_end)
      → 内部全部走 kline_repo.upsert_many()（覆盖写）
      → 不修改 sync_metadata
   d. 打印修复结果
8. 断开富途连接
9. 打印汇总统计到终端
```

#### SyncEngine 新增公开方法

为支持 repair 命令，在 `SyncEngine` 中新增以下公开方法（Dev 实现时可以对 `_fetch_and_store` 做轻量封装，或直接实现）：

```python
def repair_one(
    self,
    stock: Stock,
    period: str,
    fetch_start: str,
    fetch_end: str,
) -> Tuple[int, int]:
    """
    强制 upsert 覆盖指定区间的 K 线数据。

    与 _fetch_and_store 的区别：
    - 所有数据（包括历史日期）全部走 upsert_many（覆盖写）
    - 不区分 latest_date，不更新 sync_metadata

    Returns:
        (rows_fetched, rows_upserted)
    """
    stock_code = stock.stock_code
    bars = self._fetch_klines_paged(stock_code, period, fetch_start, fetch_end)

    rows_fetched = len(bars)
    if not bars:
        logger.info("repair_one %s [%s] %s~%s: no data returned from API",
                    stock_code, period, fetch_start, fetch_end)
        return 0, 0

    valid_bars, invalid_bars = self._validator.validate_many(bars)
    rows_upserted = 0
    if valid_bars:
        rows_upserted += self._kline_repo.upsert_many(valid_bars)
    if invalid_bars:
        self._kline_repo.upsert_many(invalid_bars)  # invalid 也覆盖写
        logger.warning(
            "%d invalid bars for %s [%s], upserted with is_valid=0",
            len(invalid_bars), stock_code, period
        )
    logger.info(
        "repair_one %s [%s] %s~%s: fetched=%d, upserted=%d",
        stock_code, period, fetch_start, fetch_end, rows_fetched, rows_upserted
    )
    return rows_fetched, rows_upserted
```

### 3.5 日志与终端输出格式

#### 日志（写入 sync_YYYYMMDD.log）

```
2026-03-20 10:30:00 [INFO] main.repair: ============================================================
2026-03-20 10:30:00 [INFO] main.repair: repair started. date=2026-03-19, stocks=2, periods=['1D']
2026-03-20 10:30:00 [INFO] main.repair: ============================================================
2026-03-20 10:30:00 [INFO] main.repair: [1/2] Repairing HK.00700 [1D]: fetch_range=2026-03-19~2026-03-19
2026-03-20 10:30:01 [INFO] core.sync_engine: repair_one HK.00700 [1D] 2026-03-19~2026-03-19: fetched=1, upserted=1
2026-03-20 10:30:01 [INFO] main.repair: [1/2] HK.00700 [1D] done: fetched=1, upserted=1
2026-03-20 10:30:01 [INFO] main.repair: [2/2] Repairing SH.600519 [1D]: fetch_range=2026-03-19~2026-03-19
2026-03-20 10:30:02 [INFO] core.sync_engine: repair_one SH.600519 [1D] 2026-03-19~2026-03-19: fetched=1, upserted=1
2026-03-20 10:30:02 [INFO] main.repair: [2/2] SH.600519 [1D] done: fetched=1, upserted=1
2026-03-20 10:30:02 [INFO] main.repair: ============================================================
2026-03-20 10:30:02 [INFO] main.repair: repair completed. total_fetched=2, total_upserted=2
2026-03-20 10:30:02 [INFO] main.repair: ============================================================
```

#### 终端输出（stdout）

```
================================================================
  AI Quant — repair  (target date: 2026-03-19)
================================================================
  Stocks  : 2
  Periods : 1D
================================================================

  [1/2] HK.00700  [1D]  2026-03-19~2026-03-19  →  fetched=1, upserted=1  ✓
  [2/2] SH.600519 [1D]  2026-03-19~2026-03-19  →  fetched=1, upserted=1  ✓

================================================================
  Summary:
    Total fetched  : 2
    Total upserted : 2
================================================================
```

### 3.6 错误处理

| 场景 | 处理方式 |
|------|---------|
| `--date` 格式非法 | 打印错误信息 + `sys.exit(1)` |
| `--date` 超过今天 | 打印 WARNING，继续执行（Futu 可能返回空） |
| 富途 OpenD 未启动 | 与 sync 相同：打印连接错误 + `sys.exit(1)` |
| 单只股票单个周期修复失败 | 打印 ERROR 日志，继续处理下一只；最终汇总标注失败数量 |
| Futu API 返回空数据 | 打印 WARNING，标记为 `fetched=0, upserted=0`；不视为失败 |
| 指定 --stock 不在 stocks 表中 | 打印 WARNING 并跳过，不退出 |

### 3.7 main.py 注册方式

```python
# 子命令：repair
sub_repair = subparsers.add_parser(
    "repair",
    help="强制 upsert 覆盖指定日期的 K 线数据（需要富途 OpenD 连接）"
)
sub_repair.add_argument(
    "--date", dest="date", required=True, metavar="YYYY-MM-DD",
    help="目标业务日期，如 2026-03-19"
)
sub_repair.add_argument(
    "--stock", dest="stock", default=None,
    help="指定股票代码（不传则修复所有活跃股票）"
)
sub_repair.add_argument(
    "--period", dest="period", nargs="+", choices=["1D", "1W", "1M"], default=None,
    help="指定周期（可多选；不传则修复全部）"
)
sub_repair.set_defaults(func=cmd_repair)
```

---

## 4. 配置变更汇总

### 4.1 `.env.example` 新增

```ini
# ============================================================
# 系统版本号（与 git tag 保持一致，升级时手动更新）
# ============================================================
APP_VERSION=v0.6.0
```

### 4.2 `config/settings.py` 新增

```python
# ============================================================
# 系统版本号（从环境变量读取，默认 dev）
# ============================================================
APP_VERSION = os.getenv("APP_VERSION", "dev")
```

### 4.3 数据库变更

**无新增表或字段**。本迭代仅使用已有的 `data_gaps` 表（`upsert_gaps` 接口已支持 check-gaps 所需写入）。

---

## 5. 不在范围内

以下内容**明确不在本迭代实现范围内**：

- 任何自动交易、下单逻辑（项目级永久禁止）
- check-gaps 联网补数据（只检测不修复，修复由 sync 完成）
- repair 修改 `sync_metadata` 表（repair 仅覆盖 K 线数据）
- Web 界面增加 check-gaps / repair 触发入口（CLI only）
- `--dry-run` 模式（当前版本不需要）
- repair 结果写入独立日志文件（复用 sync 日志即可）

---

## 附录 A：模块影响汇总

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `config/settings.py` | 新增配置项 | `APP_VERSION` |
| `api/main.py` | 修改接口 | `/api/health` 响应新增 `version` 字段 |
| `web/src/` | 新增 UI | 导航栏右上角展示版本号（需调用 `/api/health`） |
| `main.py` | 新增子命令 | `check-gaps`（`cmd_check_gaps`）、`repair`（`cmd_repair`） |
| `core/sync_engine.py` | 新增公开方法 | `repair_one(stock, period, fetch_start, fetch_end)` |
| `.env.example` | 新增示例配置 | `APP_VERSION=v0.6.0` |
| `docs/requirements_iter6.md` | 新增文档 | 本文件 |

---

## 附录 B：验收标准

### FEAT-version

- [ ] `/api/health` 返回 JSON 中包含 `version` 字段，值与 `.env` 中 `APP_VERSION` 一致
- [ ] 前端导航栏右上角显示版本号字样（如 `v0.6.0`）
- [ ] `.env` 未配置时，后端返回 `"dev"`，前端正常展示

### FEAT-check-gaps

- [ ] `python main.py check-gaps` 无报错退出，终端打印汇总
- [ ] `python main.py check-gaps --stock HK.00700 --period 1D` 只检测指定股票+周期
- [ ] 发现空洞时，`data_gaps` 表中对应记录状态为 `open`
- [ ] `logs/check_gaps_YYYYMMDD.log` 生成，内容格式符合规格
- [ ] 无 OpenD 连接情况下也能正常运行
- [ ] 对同一空洞多次运行，`data_gaps` 不重复写入（幂等）

### FEAT-repair

- [ ] `python main.py repair --date 2026-03-19 --stock HK.00700 --period 1D` 成功覆盖写入 1 条日K
- [ ] `python main.py repair --date 2026-03-17 --stock HK.00700 --period 1W` 成功覆盖写入周K（使用整周区间拉取）
- [ ] `python main.py repair --date 2026-03-01 --stock SH.600519 --period 1M` 成功覆盖写入月K
- [ ] repair 后 `sync_metadata` 表内容不变
- [ ] `--date` 格式非法时，命令以非零退出码退出并打印错误信息
- [ ] OpenD 未启动时，命令报错并以非零退出码退出
