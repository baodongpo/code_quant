# 迭代9需求文档 — yfinance 美股数据源接入（多数据源路由 + 美股K线同步 + 美股复权 + 美股交易日历）

**文档版本**：v1.0
**日期**：2026-04-11
**状态**：待总经理审批
**作者**：PM（产品经理）
**变更记录**：
- v1.0（2026-04-11）— 初版

---

## 一、迭代背景与目标

### 背景

当前项目的 A股/港股 K线数据来源于富途 OpenD API（`futu_wrap/` 模块），但富途不提供免费的美股数据。系统中虽然 `watchlist.json` 支持配置美股（`US.` 前缀），但实际同步时依赖富途 OpenD 连接，无法获取美股历史K线。

经 PM 调研、总经理审批，确认采用 **yfinance**（Yahoo Finance Python SDK）作为美股数据源：
- 完全免费，无需注册，无 API Key 管理开销
- 提供完整 OHLCV + Adj Close + Split + Dividend 数据
- 支持日K/周K/月K全历史拉取
- Python SDK，与项目技术栈天然兼容

### 目标

1. 新增 `yfinance_wrap/` 模块作为美股数据源，与现有 `futu_wrap/` 对称设计
2. `SyncEngine` 按市场码路由数据源（`US.*` → yfinance，`HK.*`/`SH.*`/`SZ.*` → 富途）
3. 美股K线支持增量同步（日K/周K/月K），复用现有同步流程
4. 美股复权因子获取与前复权计算，与项目 `adjust_factors` 表格式兼容
5. 美股交易日历获取与空洞检测适配
6. **现有富途数据源逻辑不受任何影响**

---

## 二、功能点详细说明

---

### P0 — FEAT-yfinance：新增 yfinance_wrap/ 模块

#### 2.1 问题描述

当前项目中所有数据获取均通过 `futu_wrap/` 模块封装富途 OpenD API，没有针对其他数据源的抽象层。美股数据需要通过 yfinance 获取，需要一个对称的数据源封装模块。

#### 2.2 期望行为

新增 `yfinance_wrap/` 包，与 `futu_wrap/` 对称设计，包含以下模块：

| 模块 | 类名 | 职责 |
|------|------|------|
| `client.py` | `YFinanceClient` | yfinance 连接管理（无需持久连接，封装代理、限频等） |
| `kline_fetcher.py` | `YFinanceKlineFetcher` | 美股K线数据拉取（日K/周K/月K），返回 `List[KlineBar]` |
| `adjust_fetcher.py` | `YFinanceAdjustFetcher` | 美股复权因子拉取（Split + Dividend），转换为 `adjust_factors` 表格式 |

**YFinanceClient 设计**：
- yfinance 不需要持久连接（HTTP 请求），但需管理代理配置和请求频率
- 内置请求间隔控制（默认 `time.sleep(0.5)`），避免 Yahoo 封 IP
- 支持 `.env` 配置代理（`YFINANCE_PROXY`）
- 不实现 `connect()/disconnect()` 生命周期（与 FutuClient 不同），使用前无需显式连接

**YFinanceKlineFetcher 设计**：
- 接口签名与 `futu_wrap/kline_fetcher.py` 的 `KlineFetcher.fetch()` 兼容
- 输入：`stock_code`（如 `US.AAPL`）、`period`（`1D`/`1W`/`1M`）、`start_date`、`end_date`
- 输出：`List[KlineBar]`，字段映射如下：

| yfinance 字段 | KlineBar 字段 | 说明 |
|--------------|-------------|------|
| `Date` | `trade_date` | 交易日期 |
| `Open` | `open` | 开盘价 |
| `High` | `high` | 最高价 |
| `Low` | `low` | 最低价 |
| `Close` | `close` | 收盘价（原始价，非 Adj Close） |
| `Volume` | `volume` | 成交量（股） |
| — | `turnover` | 成交额（yfinance 不提供，设为 0） |
| — | `pe_ratio` | PE（yfinance 不在K线中提供，设为 None） |
| — | `pb_ratio` | PB（yfinance 不在K线中提供，设为 None） |
| — | `ps_ratio` | PS（yfinance 不在K线中提供，设为 None） |

> **关键**：使用 `auto_adjust=False` 获取原始价格 + Adj Close，原始价格写入 `kline_data` 表，Adj Close 用于计算复权因子。

**YFinanceAdjustFetcher 设计**：
- 拉取 `ticker.splits`（拆股记录）和 `ticker.dividends`（股息记录）
- 转换为项目 `adjust_factors` 表格式（`ex_date`, `forward_factor`）
- 转换算法：
  - `forward_factor = Adj Close / Close`（每个除权日的复权因子）
  - 或从 Split/Dividend 原始数据计算累积因子（与富途 adjust_factors 格式一致）

#### 2.3 验收标准（AC）

- [ ] AC-yfinance-1：`yfinance_wrap/` 包包含 `__init__.py`、`client.py`、`kline_fetcher.py`、`adjust_fetcher.py` 四个模块。
- [ ] AC-yfinance-2：`YFinanceKlineFetcher.fetch("US.AAPL", "1D", "2024-01-01", "2024-12-31")` 返回 `List[KlineBar]`，字段完整且类型正确。
- [ ] AC-yfinance-3：返回的 KlineBar 中 `close` 为原始收盘价（非前复权价），`volume` 单位为股。
- [ ] AC-yfinance-4：`YFinanceAdjustFetcher` 能获取 AAPL 的拆股和股息记录，并转换为 `adjust_factors` 表格式。
- [ ] AC-yfinance-5：请求间隔默认 ≥ 0.5 秒，避免 Yahoo 封 IP；可通过 `YFINANCE_REQUEST_INTERVAL` 配置。
- [ ] AC-yfinance-6：yfinance 依赖已添加到 `requirements.txt`。

#### 2.4 影响文件

| 文件 | 修改内容 |
|------|---------|
| `yfinance_wrap/__init__.py` | 新建，导出 YFinanceClient / YFinanceKlineFetcher / YFinanceAdjustFetcher |
| `yfinance_wrap/client.py` | 新建，YFinanceClient 类 |
| `yfinance_wrap/kline_fetcher.py` | 新建，YFinanceKlineFetcher 类 |
| `yfinance_wrap/adjust_fetcher.py` | 新建，YFinanceAdjustFetcher 类 |
| `requirements.txt` | 新增 `yfinance` 依赖 |

---

### P0 — FEAT-multi-source：多数据源路由架构

#### 2.5 问题描述

当前 `SyncEngine` 硬编码依赖 `futu_wrap` 的 `KlineFetcher`、`CalendarFetcher`、`AdjustFactorFetcher`，无法按市场选择不同数据源。

#### 2.6 期望行为

**SyncEngine 按市场码路由数据源**：

```
stock_code 以 "US." 开头 → 使用 yfinance_wrap 的 Fetcher
stock_code 以 "HK."/"SH."/"SZ." 开头 → 使用 futu_wrap 的 Fetcher（行为不变）
```

**实现方案：Fetcher 路由层**

在 `SyncEngine` 中引入 Fetcher 路由逻辑（不新增抽象基类，最小改动）：

```python
class SyncEngine:
    def __init__(self, ..., yfinance_kline_fetcher=None, yfinance_adjust_fetcher=None):
        # 现有富途 fetcher 保留
        self._kline_fetcher = kline_fetcher               # FutuKlineFetcher
        self._adjust_factor_fetcher = adjust_factor_fetcher  # FutuAdjustFactorFetcher
        # 新增 yfinance fetcher
        self._yfinance_kline_fetcher = yfinance_kline_fetcher
        self._yfinance_adjust_fetcher = yfinance_adjust_fetcher

    def _get_kline_fetcher(self, stock_code: str):
        """按市场码返回对应的 K线 Fetcher"""
        if stock_code.startswith("US."):
            return self._yfinance_kline_fetcher
        return self._kline_fetcher

    def _get_adjust_fetcher(self, stock_code: str):
        """按市场码返回对应的复权因子 Fetcher"""
        if stock_code.startswith("US."):
            return self._yfinance_adjust_fetcher
        return self._adjust_factor_fetcher
```

**`main.py` 的 `build_dependencies()` 调整**：
- 新增 yfinance 相关依赖的组装
- SyncEngine 构造时传入 yfinance fetcher
- 仅当 watchlist 中存在 `US.*` 股票时才初始化 yfinance 相关对象
- 富途 OpenD 连接失败时，美股同步不受影响（yfinance 不依赖 OpenD）

**美股同步时跳过富途特有功能**：
- 美股不调用 `CalendarFetcher`（yfinance 不提供交易日历，见 FEAT-us-calendar）
- 美股不调用 `SubscriptionManager`（yfinance 无实时推送，美股实时数据延后规划）
- 美股空洞检测使用独立逻辑（见 FEAT-us-gap）

#### 2.7 验收标准（AC）

- [ ] AC-multi-1：`SyncEngine` 新增 `yfinance_kline_fetcher` 和 `yfinance_adjust_fetcher` 参数，现有富途逻辑不受影响。
- [ ] AC-multi-2：`stock_code` 以 `US.` 开头时，K线拉取走 `YFinanceKlineFetcher`，复权因子走 `YFinanceAdjustFetcher`。
- [ ] AC-multi-3：`stock_code` 以 `HK.`/`SH.`/`SZ.` 开头时，行为与迭代8完全一致，无回归。
- [ ] AC-multi-4：`build_dependencies()` 正确组装 yfinance 依赖，SyncEngine 接收新参数。
- [ ] AC-multi-5：富途 OpenD 未启动时，美股同步仍可正常执行（yfinance 不依赖 OpenD）。
- [ ] AC-multi-6：富途 OpenD 未启动时，A股/港股同步失败不影响美股同步流程。

#### 2.8 影响文件

| 文件 | 修改内容 |
|------|---------|
| `core/sync_engine.py` | 新增 yfinance fetcher 属性；K线/复权拉取方法中按市场码路由 fetcher；美股跳过日历和订阅逻辑 |
| `main.py` | `build_dependencies()` 新增 yfinance 依赖组装；SyncEngine 构造新增参数 |
| `config/settings.py` | 新增 yfinance 相关配置项 |

---

### P0 — FEAT-us-sync：美股K线增量同步（日K/周K/月K）

#### 2.9 问题描述

现有 `SyncEngine` 的增量同步逻辑基于 `sync_metadata` 表记录的 `last_sync_date`，结合富途 `KlineFetcher` 拉取增量数据。美股需要复用同一套增量同步流程，但数据源不同。

#### 2.10 期望行为

**美股同步复用现有 SyncEngine 流程**：

1. 读取 `sync_metadata` 表获取每只美股每个周期的 `last_sync_date`
2. 若 `last_sync_date` 为 None（新股票），全量拉取（从 `DEFAULT_HISTORY_START` 起）
3. 若 `last_sync_date` 存在，增量拉取（从 `last_sync_date + 1` 起至今天）
4. 拉取后 `upsert_many` 写入 `kline_data` 表（与富途数据共用同一张表）
5. 更新 `sync_metadata` 状态

**yfinance 的K线拉取细节**：

| 周期 | yfinance interval | yfinance period 参数 | 说明 |
|------|------------------|---------------------|------|
| 1D | `1d` | `start` + `end` 日期范围 | 日K |
| 1W | `1wk` | `start` + `end` 日期范围 | 周K |
| 1M | `1mo` | `start` + `end` 日期范围 | 月K |

**批量拉取策略**：
- 单次 `yf.download()` 或 `Ticker.history()` 最多获取全历史数据
- 无需像富途那样分页（yfinance 单次返回全量）
- 但仍需遵守请求间隔，避免触发 Yahoo 限频

**与现有流程的差异**：
- 美股不需要 `CalendarFetcher`（yfinance 自动处理交易日）
- 美股不需要 `SubscriptionManager`（无实时推送）
- 美股 `KlineBar.turnover` = 0（yfinance 不提供成交额）
- 美股 `KlineBar.pe_ratio/pb_ratio/ps_ratio` = None（yfinance 不在K线中提供）

#### 2.11 验收标准（AC）

- [ ] AC-us-sync-1：watchlist.json 中配置美股股票（如 `US.AAPL`），执行 `python main.py sync` 能成功拉取日K/周K/月K数据。
- [ ] AC-us-sync-2：美股K线数据正确写入 `kline_data` 表，`stock_code` = `US.AAPL`，`trade_date`/`open`/`high`/`low`/`close`/`volume` 字段完整。
- [ ] AC-us-sync-3：美股 `sync_metadata` 正确更新（`last_sync_date`、`status`）。
- [ ] AC-us-sync-4：再次执行 `sync`，增量同步仅拉取 `last_sync_date + 1` 之后的新数据，不重复拉取已有数据。
- [ ] AC-us-sync-5：`python main.py stats` 命令能正确显示美股股票的同步状态。
- [ ] AC-us-sync-6：美股与A股/港股在同一数据库中共存，互不影响。
- [ ] AC-us-sync-7：yfinance 请求失败时（网络异常、Yahoo 限频），同步流程优雅处理并记录错误日志，不崩溃。

#### 2.12 影响文件

| 文件 | 修改内容 |
|------|---------|
| `core/sync_engine.py` | 美股增量同步逻辑（路由至 yfinance fetcher）；美股跳过日历/订阅步骤 |
| `yfinance_wrap/kline_fetcher.py` | 实现 `fetch()` 方法，支持日K/周K/月K |

---

### P1 — FEAT-us-adjust：美股复权因子获取与前复权计算

#### 2.13 问题描述

项目采用"存原始价格 + adjust_factors 表，算法层动态前复权"策略。yfinance 提供 `Adj Close` 和 `Split`/`Dividend` 数据，需转换为项目的 `adjust_factors` 表格式。

#### 2.14 期望行为

**数据来源**：
- `ticker.splits`：拆股记录（Pandas Series，index=日期，value=拆股比例，如 4.0 表示 1拆4）
- `ticker.dividends`：股息记录（Pandas Series，index=日期，value=每股股息）
- `ticker.history(auto_adjust=False)` 的 `Adj Close` 列：前复权收盘价

**转换方案**：

方案A（推荐）：**从 Adj Close 反推 forward_factor**
```
forward_factor(t) = Adj Close(t) / Close(t)
```
- 优点：简单直接，与 Adj Close 数据一致性最高
- 每个 `Adj Close ≠ Close` 的日期即为一个除权事件，写入 `adjust_factors` 表

方案B：**从 Split + Dividend 计算**
- 需要复现 Yahoo 的复权计算公式，复杂度高，容易与 Adj Close 不一致

**推荐方案A**，实现步骤：
1. 拉取全历史K线（`auto_adjust=False`），获取 `Close` 和 `Adj Close`
2. 找出所有 `Adj Close / Close ≠ 1.0` 的日期
3. 每个日期计算 `forward_factor = Adj Close / Close`
4. 写入 `adjust_factors` 表（`stock_code`, `ex_date`, `forward_factor`）

**复权验证**：
- 写入后，使用现有 `AdjustmentService.get_adjusted_klines()` 验证前复权计算结果
- 比对 `AdjustmentService` 计算的前复权收盘价与 yfinance 的 `Adj Close`，误差应在合理范围内

#### 2.15 验收标准（AC）

- [ ] AC-us-adjust-1：美股股票（如 AAPL）的复权因子正确写入 `adjust_factors` 表，`stock_code` = `US.AAPL`。
- [ ] AC-us-adjust-2：调用 `AdjustmentService.get_adjusted_klines("US.AAPL", "1D", ...)` 返回前复权数据，`is_adjusted=True`。
- [ ] AC-us-adjust-3：前复权收盘价与 yfinance `Adj Close` 对比，误差 < 0.1%。
- [ ] AC-us-adjust-4：A股/港股的复权计算逻辑不受影响，无回归。
- [ ] AC-us-adjust-5：美股股票多次执行 sync，复权因子幂等更新（不产生重复记录）。

#### 2.16 影响文件

| 文件 | 修改内容 |
|------|---------|
| `yfinance_wrap/adjust_fetcher.py` | 实现从 Adj Close 反推 forward_factor 的逻辑 |
| `core/sync_engine.py` | 美股复权因子同步路由至 YFinanceAdjustFetcher |

---

### P1 — FEAT-us-calendar：美股交易日历获取

#### 2.17 问题描述

yfinance 不提供交易日历 API。当前项目的空洞检测（`GapDetector`）依赖 `trading_calendar` 表判断交易日。美股需要独立的交易日历来源。

#### 2.18 期望行为

**方案：使用 pandas-market-calendars 库**

- `pandas-market-calendars` 提供 NYSE/NASDAQ 交易日历，覆盖历史和未来
- 纯 Python 计算，无需 API 调用，无需网络连接
- 与项目现有的 `trading_calendar` 表格式兼容

**实现**：
1. 新增 `yfinance_wrap/calendar_fetcher.py`，包含 `YFinanceCalendarFetcher` 类
2. 使用 `pandas_market_calendars.get_calendar('NYSE')` 获取交易日历
3. 转换为 `trading_calendar` 表格式（`market='US'`, `trade_date`, `is_trading_day`）
4. 在 `SyncEngine` 中，美股日历请求路由至 `YFinanceCalendarFetcher`
5. 美股日历增量更新逻辑与A股/港股一致

**备选方案**（如不想引入新依赖）：
- 从 yfinance 拉取某个大盘指数（如 `^GSPC`）的全历史日K，以出现的交易日作为交易日历
- 缺点：不如 `pandas-market-calendars` 规范，且无法预知未来交易日

#### 2.19 验收标准（AC）

- [ ] AC-us-calendar-1：`pandas-market-calendars` 依赖已添加到 `requirements.txt`。
- [ ] AC-us-calendar-2：`YFinanceCalendarFetcher` 能获取 NYSE 交易日历并写入 `trading_calendar` 表，`market='US'`。
- [ ] AC-us-calendar-3：交易日历覆盖 `DEFAULT_HISTORY_START` 至今，`is_trading_day` 字段正确。
- [ ] AC-us-calendar-4：A股/港股日历获取逻辑不受影响，仍走富途 `CalendarFetcher`。
- [ ] AC-us-calendar-5：`python main.py sync` 执行时，美股日历自动增量更新。

#### 2.20 影响文件

| 文件 | 修改内容 |
|------|---------|
| `yfinance_wrap/calendar_fetcher.py` | 新建，YFinanceCalendarFetcher 类 |
| `core/sync_engine.py` | 美股日历请求路由至 YFinanceCalendarFetcher |
| `main.py` | `build_dependencies()` 新增 YFinanceCalendarFetcher 组装 |
| `requirements.txt` | 新增 `pandas-market-calendars` 依赖 |

---

### P2 — FEAT-us-gap：美股空洞检测与修复

#### 2.21 问题描述

当前空洞检测（`GapDetector`）基于 `trading_calendar` 表判断交易日连续性。美股接入后，空洞检测需要适配美股交易日历。

#### 2.22 期望行为

**核心逻辑复用**：
- `GapDetector` 已按 `market` 字段查询交易日历，美股日历写入 `trading_calendar` 表（`market='US'`）后，空洞检测自动适用
- 美股股票代码以 `US.` 开头，`GapDetector` 中 `market` 提取逻辑需适配（当前 `US.00700` → `market='US'`，需验证）

**需要确认的适配点**：
1. `GapDetector._group_consecutive()` 中 `market` 的提取逻辑（当前 `HK.00700` → `HK`，`SH.600519` → 映射为 `A`，`US.AAPL` → 需映射为 `US`）
2. 美股日历的 `market` 值为 `US`（非 `A`），`calendar_repo` 查询需支持 `market='US'`
3. `check-gaps` 和 `repair` 子命令对美股的支持

**预期**：由于 `GapDetector` 已基于 `trading_calendar` 表做通用检测，只要美股日历数据正确写入，大部分逻辑应自动生效。主要工作在于验证和边界适配。

#### 2.23 验收标准（AC）

- [ ] AC-us-gap-1：`python main.py check-gaps --stock US.AAPL` 能正确检测美股空洞，结果写入 `data_gaps` 表。
- [ ] AC-us-gap-2：`python main.py check-gaps`（不指定股票）能同时检测 A股/港股/美股空洞。
- [ ] AC-us-gap-3：`python main.py repair --date 2024-01-02 --stock US.AAPL` 能修复指定日期的美股K线数据。
- [ ] AC-us-gap-4：美股空洞修复流程与A股/港股一致（yfinance 拉取 → upsert 覆盖写入 → 更新 gap 状态）。

#### 2.24 影响文件

| 文件 | 修改内容 |
|------|---------|
| `core/gap_detector.py` | 验证 `market='US'` 的日历查询适配；必要时调整 market 提取逻辑 |
| `core/sync_engine.py` | `repair_one()` 方法中美股路由至 yfinance fetcher |
| `main.py` | `cmd_check_gaps` / `cmd_repair` 中美股适配 |

---

### P2 — CONFIG：.env 新增 yfinance 相关配置项

#### 2.25 新增配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `YFINANCE_PROXY` | 空（不使用代理） | yfinance HTTP 代理地址（如 `http://127.0.0.1:7890`），国内访问 Yahoo Finance 可能需要 |
| `YFINANCE_REQUEST_INTERVAL` | `0.5` | yfinance 请求间隔（秒），避免 Yahoo 限频 |
| `YFINANCE_MAX_RETRIES` | `3` | yfinance 请求最大重试次数 |

#### 2.26 验收标准（AC）

- [ ] AC-config-1：`.env.example` 新增上述三个配置项及注释说明。
- [ ] AC-config-2：`config/settings.py` 正确读取上述配置项，提供合理默认值。
- [ ] AC-config-3：不配置 `.env` 时（使用默认值），yfinance 功能正常工作。

#### 2.27 影响文件

| 文件 | 修改内容 |
|------|---------|
| `config/settings.py` | 新增 `YFINANCE_PROXY`、`YFINANCE_REQUEST_INTERVAL`、`YFINANCE_MAX_RETRIES` |
| `.env.example` | 新增三个配置项及注释 |

---

## 三、实现优先级

| 优先级 | ID | 功能点 | 原因 |
|--------|-----|--------|-----|
| P0 | FEAT-yfinance | yfinance_wrap/ 模块 | 基础模块，所有美股功能依赖此模块 |
| P0 | FEAT-multi-source | 多数据源路由架构 | 核心架构改动，SyncEngine 路由逻辑 |
| P0 | FEAT-us-sync | 美股K线增量同步 | 核心功能，验证数据通路可用 |
| P1 | FEAT-us-adjust | 美股复权因子 | 前复权计算依赖，影响可视化正确性 |
| P1 | FEAT-us-calendar | 美股交易日历 | 空洞检测依赖，非核心但重要 |
| P2 | FEAT-us-gap | 美股空洞检测与修复 | 依赖交易日历，优先级较低 |
| P2 | CONFIG | .env 配置项 | 配合其他功能点，可并行完成 |

> **建议开发顺序**：CONFIG → FEAT-yfinance → FEAT-multi-source → FEAT-us-sync → FEAT-us-adjust → FEAT-us-calendar → FEAT-us-gap
>
> 注：CONFIG 和 FEAT-yfinance 可并行。FEAT-us-calendar 和 FEAT-us-adjust 依赖 FEAT-us-sync 完成。FEAT-us-gap 依赖 FEAT-us-calendar。

---

## 四、影响文件汇总

| 文件路径 | 涉及功能点 |
|---------|-----------|
| `yfinance_wrap/__init__.py` | FEAT-yfinance（新建） |
| `yfinance_wrap/client.py` | FEAT-yfinance（新建） |
| `yfinance_wrap/kline_fetcher.py` | FEAT-yfinance、FEAT-us-sync（新建） |
| `yfinance_wrap/adjust_fetcher.py` | FEAT-yfinance、FEAT-us-adjust（新建） |
| `yfinance_wrap/calendar_fetcher.py` | FEAT-us-calendar（新建） |
| `core/sync_engine.py` | FEAT-multi-source、FEAT-us-sync、FEAT-us-adjust、FEAT-us-gap |
| `core/gap_detector.py` | FEAT-us-gap |
| `main.py` | FEAT-multi-source、FEAT-us-gap |
| `config/settings.py` | CONFIG |
| `.env.example` | CONFIG |
| `requirements.txt` | FEAT-yfinance、FEAT-us-calendar |
| `CLAUDE.md` | 迭代9状态更新 |
| `README.md` | 多数据源说明更新 |

**不涉及改动**：
- `api/` 所有后端文件（API 层只读，数据写入由 sync 流程完成）
- `web/` 所有前端文件（前端通过 API 获取数据，不关心数据源）
- `core/indicator_engine.py`（指标计算逻辑不变）
- `core/adjustment_service.py`（复权计算逻辑不变，仅新增美股 adjust_factors 数据）
- `futu_wrap/` 所有文件（富途数据源逻辑不变）
- `db/schema.py`（数据库结构不变，复用现有表）

---

## 五、风险说明

### R1 — yfinance 非官方 API，可能随时失效

**风险**：yfinance 依赖 Yahoo Finance 网页端非公开 API，Yahoo 可能随时更改接口导致 yfinance 失效。

**缓解**：
- yfinance 是社区活跃维护的开源项目（GitHub 12k+ stars），对 Yahoo API 变更有较快响应
- 将 yfinance 依赖限制在 `yfinance_wrap/` 模块内，失效时只需替换此模块
- 代理配置支持，在国内网络环境下可通过代理访问 Yahoo

### R2 — Yahoo Finance 限频导致 IP 封禁

**风险**：短时间大量请求不同股票数据，可能触发 Yahoo 限频，返回 403/429 错误。

**缓解**：
- `YFinanceClient` 内置请求间隔控制（默认 0.5 秒）
- 美股同步采用串行拉取（非并行），降低并发压力
- 支持配置代理，被封后可切换 IP
- 请求失败时指数退避重试（最多 3 次）

### R3 — 美股复权因子精度问题

**风险**：从 `Adj Close / Close` 反推的 `forward_factor` 可能存在浮点精度问题，导致前复权计算与 yfinance `Adj Close` 有微小差异。

**缓解**：
- `forward_factor` 使用 `decimal.Decimal` 或高精度浮点计算
- 验收标准设定误差 < 0.1%，实际精度应远优于此
- 与富途 A股/港股复权因子使用相同的存储格式和计算流程

### R4 — 美股实时数据缺失

**风险**：yfinance 无实时推送能力，美股盘中数据需要定时轮询或手动触发 sync。

**缓解**：
- 本迭代不实现美股实时推送（明确不在范围内）
- 盘中通过 `python main.py sync` 手动触发增量同步
- 未来可考虑 WebSocket 数据源（如 Finnhub 免费版）补充实时能力

### R5 — pandas-market-calendars 与实际交易日可能存在微小差异

**风险**：`pandas-market-calendars` 的 NYSE 日历基于规则计算，可能遗漏罕见的临时停市（类似 A股台风停市问题）。

**缓解**：
- 项目已有 `no_data` 状态机制（迭代8.5-patch），可处理此类情况
- sync 验证空洞时若 yfinance 返回空数据，自动标记为 `no_data`
- 与 A股临时停市的处理方式一致

---

## 六、不在本迭代范围内的事项

- **美股实时推送**（yfinance 无 WebSocket，需引入新数据源，作为独立迭代规划）
- **美股成交额（turnover）字段**（yfinance 不提供，设为 0，未来可从其他数据源补充）
- **美股 PE/PB/PS 估值字段**（yfinance 不在K线中提供，未来可通过 `ticker.info` 补充）
- **前端任何改动**（前端通过 API 获取数据，数据源切换对前端透明）
- **API 层任何改动**（API 只读，数据写入由 sync 流程完成）
- **A股/港股数据源切换**（保持富途 OpenD，不变）
- **watchlist.json 格式变更**（保持兼容，美股配置格式不变）

---

*文档结束 — 待总经理审批后启动研发。*
