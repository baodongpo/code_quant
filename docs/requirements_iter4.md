# AI 量化辅助决策系统 - 迭代4产品需求文档（PRD）

**版本**: v4.0
**日期**: 2026-03-18
**范围**: 基本面数据采集、备用数据源容灾切换、数据归档清理、告警推送
**前置**: 迭代1（K线采集）、迭代2（服务化+估值+导出）、迭代3（技术指标可视化 Web 服务）均已完成，tag v0.3.1

---

## 1. 迭代4目标

**主题：从可视化辅助工具到基本面+技术面双维度量化数据平台**

| 迭代 | 目标 |
|------|------|
| 迭代1 | 能跑、能采数据 |
| 迭代2 | 能持续运行、服务器无人值守 |
| 迭代3 | 能看、能分析——技术指标可视化辅助决策 |
| **迭代4** | **能更全、更稳、更主动——基本面数据入库、容灾切换保障数据连续性、归档清理控制存储成本、告警推送主动提示关键信号** |
| 迭代5+ | 量化因子回测框架（独立系统，不在本系统范围内）|

**核心用户场景**：
1. 用户在 Web 界面查看某股票时，除技术指标外，还能看到 ROE 趋势、净利润增速等基本面指标，辅助判断该公司是否值得长持。
2. 富途 OpenD 连接异常时，系统自动降级到 AKShare 继续采集 A 股历史数据，保障数据管道不断；异常恢复后自动回切。
3. 系统在夜间自动将 3 年以前的周K/月K 数据压缩归档，主库保持轻量，用户查询历史数据时无感知。
4. RSI 进入超买区域或 MACD 金叉发生时，系统自动发送微信/邮件通知，用户无需盯盘也能及时知晓关键信号。

---

## 2. 功能全景

迭代4新增四大模块：

```
┌─────────────────────────────────────────────────────────────┐
│                    迭代4新增部分                              │
├──────────────────┬──────────────────┬────────────────────────┤
│  模块F：基本面    │  模块G：备用数据源 │   模块H：数据归档清理   │
│  数据采集        │  容灾切换         │                        │
│                  │                  │                        │
│  FundamentalRepo │  FallbackSource  │  ArchiveManager        │
│  FinancialFetcher│  SourceRouter    │  归档查询透明代理        │
│  API扩展         │  健康检测        │  归档策略配置           │
└──────────────────┴──────────────────┴────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                  模块I：告警推送                              │
│                                                             │
│  AlertRule（规则引擎）  AlertSender（推送发送）               │
│  支持：微信推送 / 邮件 SMTP                                   │
│  触发条件：技术指标信号 + 基本面阈值                           │
└─────────────────────────────────────────────────────────────┘
           ↑ 读取（只读）+ 写入（基本面数据、归档元数据）
┌─────────────────────────────────────────────────────────────┐
│              迭代1/2/3 已有部分（不修改已有逻辑）              │
│  SQLite kline_data / adjust_factors / stocks 等              │
│  FastAPI 后端 + React 前端 Web 服务                           │
└─────────────────────────────────────────────────────────────┘
```

**严格约束**：禁止任何交易、下单、报价逻辑。告警仅推送数据信号提示，不包含"买入/卖出"操作指令。

---

## 3. 功能清单与优先级

| 编号 | 功能 | 模块 | 优先级 | 说明 |
|------|------|------|--------|------|
| F1 | 基本面财务数据采集（ROE/净利润增速/营收增速）| F | **P0** | 核心新增，量化因子基础 |
| F2 | 基本面数据 API 端点扩展 | F | **P0** | F1 前提，前端可视化依赖 |
| F3 | Web 前端基本面趋势图展示 | F | **P0** | 用户直接感知的价值 |
| G1 | AKShare 备用数据源集成 | G | **P0** | 容灾核心，保障数据连续性 |
| G2 | 数据源路由器（主/备自动切换）| G | **P0** | G1 前提 |
| G3 | 数据源健康检测与自动回切 | G | P1 | 自动回切，减少人工干预 |
| H1 | 数据归档策略与执行器 | H | P1 | 控制存储成本 |
| H2 | 归档数据查询透明代理 | H | P1 | 保障历史数据可访问性 |
| H3 | 归档管理命令行工具 | H | P2 | 运维辅助 |
| I1 | 告警规则引擎 | I | P1 | 主动感知关键信号 |
| I2 | 微信推送通道（企业微信群机器人）| I | P1 | 推送首选通道 |
| I3 | 邮件推送通道（SMTP）| I | P2 | 推送备选通道 |
| I4 | 告警静默策略（防频繁重复推送）| I | P1 | 避免骚扰 |
| E1 | 迭代3遗留指标补全（CCI/OBV/ATR/BBW/均线排列）| F | P2 | 来自迭代3规划遗留 |
| E2 | PE/PB/PS 历史走势图展示 | F | P2 | 来自迭代3规划遗留 |

---

## 4. 模块F：基本面数据采集

### 4.1 需求背景

迭代2已采集 PE/PB/PS（来自 `kline_data` 日K字段），但这些都是**市场定价类估值指标**，并非企业经营质量指标。
ROE（净资产收益率）、净利润增速、营收增速是衡量企业成长质量的核心**财务类指标**，也是 A/港股量化因子策略最高频使用的基本面因子。

**富途 API 能力边界判断**：

| 数据项 | 富途接口 | 字段 | 可用性 |
|--------|---------|------|--------|
| ROE（净资产收益率）| `get_stock_basicinfo` / `get_financial_info` | `return_equity_ratio` | ✅ 支持 |
| 净利润（绝对值）| `get_financial_info` | `net_profit` | ✅ 支持 |
| 营收（总收入）| `get_financial_info` | `total_revenue` | ✅ 支持 |
| 净利润增速（YoY%）| 需自行计算（相邻季度/年度净利润对比）| 派生计算 | ✅ 可计算 |
| 营收增速（YoY%）| 需自行计算（相邻季度/年度营收对比）| 派生计算 | ✅ 可计算 |
| 每股收益 EPS | `get_financial_info` | `eps` | ✅ 支持 |
| 净资产（BPS）| `get_financial_info` | `net_asset` | ✅ 支持 |
| 毛利率 | `get_financial_info` | `gross_profit_margin` | ✅ 支持 |
| 资产负债率 | `get_financial_info` | `debt_ratio` | ✅ 支持 |
| 分季度/分年度 | `get_financial_info` 支持 `report_type`（季报/半年报/年报）| — | ✅ 支持 |

> **注意**：美股 `get_financial_info` 返回字段与 A/港股存在差异，部分字段仅在年报中存在；财务数据更新频率为财报季（季度/半年/年度），并非每日更新。

---

### 4.2 F1：基本面财务数据采集

#### 4.2.1 新增数据库表：`fundamentals`

```sql
CREATE TABLE fundamentals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code      TEXT    NOT NULL,
    report_date     TEXT    NOT NULL,
    report_type     TEXT    NOT NULL,
    currency        TEXT    DEFAULT 'CNY',
    roe             REAL,
    eps             REAL,
    gross_margin    REAL,
    net_profit      REAL,
    total_revenue   REAL,
    net_asset       REAL,
    net_profit_yoy  REAL,
    revenue_yoy     REAL,
    debt_ratio      REAL,
    data_source     TEXT    DEFAULT 'futu',
    fetched_at      TEXT    NOT NULL,
    is_valid        INTEGER DEFAULT 1,
    UNIQUE(stock_code, report_date, report_type)
);

CREATE INDEX idx_fundamentals_stock_date ON fundamentals(stock_code, report_date DESC);
```

字段说明：
- `report_date`：报告期，格式 YYYY-MM-DD（如 2024-09-30 代表三季报）
- `report_type`：annual（年报）/ quarterly（季报）
- `net_profit_yoy`：净利润同比增速（%），计算逻辑：`(net_profit_t - net_profit_t-4) / abs(net_profit_t-4) × 100`
- `revenue_yoy`：营收同比增速（%），同上计算逻辑

#### 4.2.2 新增模块：`futu_wrap/financial_fetcher.py`

新增 `FinancialFetcher` 类，封装富途 `get_financial_info` 调用：

- 支持按股票代码批量拉取历史财报（最多回溯 10 年）
- 支持 `report_type`：`FundamentalDataType.ANNUAL`（年报）、`QUARTERLY`（季报）
- 返回标准化 `FundamentalRecord` dataclass（含派生增速字段）
- 增速在采集层计算后写入，需至少 5 期历史数据才能计算同比

#### 4.2.3 新增模块：`db/repositories/fundamental_repo.py`

新增 `FundamentalRepository`，提供：

```python
upsert_fundamentals(records: List[FundamentalRecord]) -> int
get_fundamentals(stock_code: str, report_type: str, limit: int = 20) -> List[FundamentalRecord]
get_latest_fundamental(stock_code: str) -> Optional[FundamentalRecord]
```

#### 4.2.4 同步逻辑集成

- `SyncEngine.run_full_sync()` 新增步骤：每次同步完成后，对 `active_stocks` 中每只股票触发财务数据更新
- 更新频率：**每周触发一次**（非每日，财报数据更新频率低），由 `sync_metadata` 记录上次财报更新时间控制
- 仅采集**年报 + 季报**两档，半年报不单独采集
- 富途财报接口不受日K限频器约束（独立接口），但需间隔 ≥ 0.5s/次

#### 4.2.5 数据校验规范

| 字段 | 校验规则 |
|------|---------|
| roe | -100% ≤ ROE ≤ 500%，异常值标记 `is_valid=0` 但保留 |
| net_profit_yoy | -1000% ≤ 增速 ≤ 1000%，超出则标记异常 |
| revenue_yoy | 同上 |
| debt_ratio | 0% ≤ 负债率 ≤ 100% |

---

### 4.3 F2：基本面数据 API 端点扩展

在现有 `api/routes/` 下新增 `fundamentals.py`：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/fundamentals/{code}` | GET | 返回指定股票最近 N 期财报数据 |
| `/api/fundamentals/{code}/summary` | GET | 返回最新一期关键指标摘要 |

`/api/fundamentals/{code}` 请求参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `report_type` | str | `quarterly` | 报告类型：quarterly / annual |
| `limit` | int | 12 | 返回期数（季报12期=3年） |

响应结构示例：

```json
{
  "stock_code": "SH.600519",
  "report_type": "quarterly",
  "records": [
    {
      "report_date": "2024-09-30",
      "roe": 28.5,
      "eps": 18.6,
      "net_profit": 196800,
      "total_revenue": 382400,
      "net_profit_yoy": 15.2,
      "revenue_yoy": 17.8,
      "gross_margin": 91.2,
      "debt_ratio": 22.1,
      "data_source": "futu"
    }
  ]
}
```

---

### 4.4 F3：Web 前端基本面趋势图展示

在现有 `web/src/pages/StockAnalysis` 页面增加基本面面板（独立折叠区块）：

#### 基本面指标卡片（最新一期数据）

```
┌────────────────────────────────────────────────────────────────┐
│  基本面快照（最新季报：2024Q3）                                   │
│  ROE: 28.5%  ↑  |  净利润增速: +15.2%  ↑  |  营收增速: +17.8% ↑ │
│  毛利率: 91.2%    |  资产负债率: 22.1%       |  EPS: 18.6 元      │
└────────────────────────────────────────────────────────────────┘
```

#### 基本面趋势图（折叠展开）

- **ROE 趋势柱状图**：近 12 个季度 ROE，配水平参考线（ROE=15%，行业优秀线）
- **净利润/营收增速折线图**：近 12 个季度同比增速，0% 参考线（正负增长分界）
- **净利润绝对值柱状图**：近 12 个季度净利润，辅助判断规模变化

#### 基本面信号标签规范

| 条件 | 标签 | 颜色 |
|------|------|------|
| ROE ≥ 15% 且连续 4 季度 | 🟢 ROE 优质 | 绿色 |
| ROE < 8% 连续 2 季度 | 🔴 ROE 偏低 | 红色 |
| 净利润增速 > 20% | 🟢 高速增长 | 绿色 |
| 净利润增速 < 0%（同比转负）| 🔴 利润下滑 | 红色 |
| 营收增速 > 15% | 🟢 营收高增 | 绿色 |

> **免责声明**：以上信号为财务数据的机械判断，仅供参考，不构成投资建议。

---

## 5. 模块G：备用数据源容灾切换

### 5.1 需求背景

富途 OpenD 依赖桌面客户端在线、账户登录状态正常，存在以下故障场景：
- 富途客户端崩溃 / 网络断连 / 账户被踢登录
- 富途服务器维护或接口限制
- 本地 OpenD 进程异常退出

**AKShare 能力边界说明**：

| 市场 | AKShare 支持 | 说明 |
|------|------------|------|
| A 股（SH/SZ）| ✅ 完整支持 | `stock_zh_a_hist()` 提供完整历史 OHLCV |
| 港股 | ⚠️ 部分支持 | 数据质量较低，不作为备用源 |
| 美股 | ❌ 不支持 | 不作为备用源 |
| ETF（A股）| ✅ 支持 | `fund_etf_hist_em()` 接口 |

> **结论**：备用数据源 AKShare 仅覆盖 A 股（SH./SZ.）股票和 A 股 ETF，港股、美股故障时不启用降级，记录 WARNING 日志等待人工处理。

---

### 5.2 G1：AKShare 备用数据源集成

#### 新增模块：`futu_wrap/akshare_fetcher.py`

新增 `AKShareFetcher` 类，对外暴露与 `KlineFetcher` **相同接口签名**：

```python
class AKShareFetcher:
    def get_history_kline(
        self,
        stock_code: str,   # 如 SH.600519
        period: str,       # "1D" / "1W" / "1M"
        start_date: str,
        end_date: str,
        adj_type: str,     # "qfq" / "raw"（AKShare 原生支持前复权）
    ) -> List[KlineBar]:
```

**字段映射规范**（AKShare A 股接口 → `KlineBar`）：

| AKShare 字段 | KlineBar 字段 | 说明 |
|-------------|--------------|------|
| `日期` | `time_key` | 格式转换为 YYYY-MM-DD |
| `开盘` | `open` | 元 |
| `最高` | `high` | 元 |
| `最低` | `low` | 元 |
| `收盘` | `close` | 元 |
| `成交量` | `volume` | 手 × 100 = 股 |
| `成交额` | `turnover` | 元 |
| `换手率` | `turnover_rate` | % |
| N/A | `pe_ratio` | NULL（AKShare 不提供实时 PE）|
| N/A | `pb_ratio` | NULL |

- AKShare 采集的数据，`data_source` 字段标记为 `'akshare'`
- 写入时使用与富途相同的 `INSERT OR IGNORE` 幂等策略

#### 新增依赖

`requirements.txt` 新增 `akshare>=1.12.0`（安装至 `env_quant/`，用 `./env_quant/bin/pip install`）

---

### 5.3 G2：数据源路由器

#### 新增模块：`core/source_router.py`

新增 `SourceRouter` 类，封装主/备数据源切换逻辑：

**路由决策逻辑**：

```
调用 get_history_kline(stock_code, ...)
    │
    ├── 判断市场：非 A 股（HK/US）→ 只走富途，失败则抛出原始异常
    │
    └── A 股：
          ├── primary_healthy = True？→ 调用 FutuKlineFetcher
          │       ├── 成功 → 返回结果，重置 failure_count
          │       └── 失败 → failure_count += 1
          │                    failure_count >= FALLBACK_THRESHOLD（默认=3）？
          │                         YES → 切换 primary_healthy = False
          │
          └── primary_healthy = False？→ 调用 AKShareFetcher
                  ├── 成功 → 返回结果（data_source='akshare'）
                  └── 失败 → 抛出异常，记录 ERROR
```

- `FALLBACK_THRESHOLD`：连续失败 3 次触发降级（避免偶发错误误触发）
- 降级状态写入 `data/health.json` 的 `data_source` 字段

---

### 5.4 G3：健康检测与自动回切

- 主数据源故障后，每 **10 分钟**尝试一次探活（调用轻量级 `FutuClient.is_connected()`）
- 探活成功后，将 `primary_healthy` 重置为 `True`，并记录 INFO 日志：`主数据源已恢复，自动回切富途`
- 切换状态变化时，触发告警推送（若模块I已配置推送通道）

---

## 6. 模块H：数据归档清理

### 6.1 归档策略决策

| K线粒度 | 是否归档 | 保留年限 | 理由 |
|--------|---------|--------|------|
| 日K（1D）| **不归档** | 全量保留 | 技术指标计算主力数据（如 MA250 需 250 日），不宜归档 |
| 周K（1W）| **归档** | 保留近 3 年 | 中线分析 3 年已足，更早数据使用频率极低 |
| 月K（1M）| **归档** | 保留近 5 年 | 长线趋势判断 5 年已足 |

**归档定义**：将超出保留期数据从主库（`kline_data`）迁移至归档数据库（`data/archive/quant_archive_YYYY.db`），主库删除对应行。归档 ≠ 删除，数据完整保留于归档文件中。

---

### 6.2 H1：数据归档策略与执行器

#### 新增模块：`core/archive_manager.py`

新增 `ArchiveManager` 类：

```python
class ArchiveManager:
    def run_archive(self, dry_run: bool = False) -> ArchiveResult
    def get_archive_stats(self) -> Dict
```

**归档执行流程**：

```
1. 查询 kline_data WHERE period='1W' AND time_key < (today - 3年)
2. 查询 kline_data WHERE period='1M' AND time_key < (today - 5年)
3. 按 time_key 年份路由到对应归档 DB（quant_archive_2020.db 等）
4. 在事务内：INSERT 归档行到归档 DB → 确认成功 → DELETE 主库行
5. 写入归档日志（归档 DB 内 archive_log 表）
```

**事务原子性保障**：INSERT + DELETE 在同一事务内，任一步骤失败整体回滚，杜绝数据丢失。

#### 触发机制

- **定时归档**：每月 1 日凌晨 03:00 自动执行（通过现有 systemd timer 机制扩展）
- 归档耗时预计 < 60 秒，不影响日间数据同步
- 归档操作使用独立子命令（`python main.py archive`），与采集服务并行无干扰

#### 归档配置（`.env` 新增）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ARCHIVE_DIR` | `data/archive/` | 归档数据库存放目录 |
| `ARCHIVE_WEEKLY_RETENTION_YEARS` | `3` | 周K保留年限 |
| `ARCHIVE_MONTHLY_RETENTION_YEARS` | `5` | 月K保留年限 |

---

### 6.3 H2：归档数据查询透明代理

**核心目标**：`AdjustmentService` 或 API 层查询任意历史数据时，无需感知数据是在主库还是归档库，系统自动路由。

#### 实现方案：`KlineRepository` 扩展

在 `db/repositories/kline_repo.py` 的 `get_klines()` 方法中增加归档穿透查询：

```python
def get_klines(self, stock_code, period, start_date, end_date):
    # 1. 先查主库（覆盖绝大多数日常查询）
    rows = self._query_main_db(...)

    # 2. 若 start_date 早于归档边界且已开启归档查询，追加查询归档库
    if ENABLE_ARCHIVE_QUERY and start_date < self._get_archive_boundary(period):
        archive_rows = self._query_archive_dbs(...)
        rows = archive_rows + rows  # 归档数据在前（时间较早）

    return rows
```

- 归档穿透查询默认**关闭**（`ENABLE_ARCHIVE_QUERY=false`）
- 日常 Web 可视化（近 3 年内数据）不触发归档穿透，性能零影响
- 开启后，`python main.py export` 可导出包含归档数据的完整历史

---

### 6.4 H3：归档管理命令行工具

`main.py` 扩展子命令：

```bash
# 预演归档（只统计，不执行）
./env_quant/bin/python main.py archive --dry-run

# 执行归档
./env_quant/bin/python main.py archive

# 查看归档统计
./env_quant/bin/python main.py archive --stats
```

`--dry-run` 输出示例：

```
=== 归档预演（仅统计，不执行）===
待归档周K数据：12,450 行（2019-01-01 ~ 2022-12-31）
待归档月K数据：2,860 行（2015-01-01 ~ 2020-12-31）
预计释放主库空间：约 1.2 MB
目标归档文件：
  data/archive/quant_archive_2019.db（新建）
  data/archive/quant_archive_2020.db（新建）
  data/archive/quant_archive_2021.db（新建）
  data/archive/quant_archive_2022.db（新建）
执行归档请去掉 --dry-run 参数
```

---

## 7. 模块I：告警推送

### 7.1 需求背景

迭代3实现 Web 可视化后，用户需主动打开浏览器才能感知指标信号。迭代4增加**主动推送**能力，当关键技术或基本面信号触发时，系统自动向用户发送通知。

**设计原则**：
- 告警仅传递信号信息，**不包含任何"建议买入/卖出"的操作性指令**，严守系统边界
- 每只股票每种信号，**24 小时内最多推送 1 次**（静默策略，防骚扰）
- 推送内容为文本描述，方便在手机上快速阅读

---

### 7.2 I1：告警规则引擎

#### 新增模块：`core/alert_engine.py`

新增 `AlertEngine` 类：

```python
class AlertEngine:
    def check_alerts(self, stock_code: str, bars: List[KlineBar]) -> List[AlertEvent]
    def filter_by_silence(self, events: List[AlertEvent]) -> List[AlertEvent]
```

#### 技术指标类触发条件（P0 规则，默认开启）

| 规则 ID | 触发条件 | 推送文案示例 | 优先级 |
|---------|---------|------------|--------|
| T-RSI-OB | RSI14 **上穿** 70（本日 > 70 且昨日 ≤ 70）| `[SH.600519 贵州茅台] RSI 进入超买区间（RSI=72.3），近期价格可能面临回调压力` | P0 |
| T-RSI-OS | RSI14 **下穿** 30（本日 < 30 且昨日 ≥ 30）| `[SH.600519 贵州茅台] RSI 进入超卖区间（RSI=27.1），价格处于低估区域` | P0 |
| T-MACD-GC | MACD **金叉**（DIF 上穿 DEA）| `[SH.600519 贵州茅台] MACD 金叉信号（DIF=2.3 穿越 DEA=1.8），多头趋势可能启动` | P0 |
| T-MACD-DC | MACD **死叉**（DIF 下穿 DEA）| `[SH.600519 贵州茅台] MACD 死叉信号（DIF=1.2 跌破 DEA=1.9），空头趋势可能启动` | P0 |
| T-BOLL-UB | 收盘价 **上穿** 布林上轨（本日 > 上轨 且昨日 ≤ 上轨）| `[HK.00700 腾讯控股] 价格突破布林上轨（收盘 385 > 上轨 382），短期超买警示` | P0 |
| T-BOLL-LB | 收盘价 **下穿** 布林下轨（本日 < 下轨 且昨日 ≥ 下轨）| `[HK.00700 腾讯控股] 价格跌破布林下轨（收盘 361 < 下轨 364），短期超卖关注` | P0 |
| T-KDJ-GC | KDJ **金叉且 K < 30**（超卖区金叉）| `[SZ.000858 五粮液] KDJ 在超卖区金叉（K=22.1 穿越 D=19.8），短线反弹信号` | P1 |
| T-KDJ-DC | KDJ **死叉且 K > 70**（超买区死叉）| `[SZ.000858 五粮液] KDJ 在超买区死叉（K=78.4 跌破 D=82.1），短线回调注意` | P1 |

#### 基本面类触发条件（仅在财报季更新后触发）

| 规则 ID | 触发条件 | 推送文案示例 | 优先级 |
|---------|---------|------------|--------|
| F-ROE-HIGH | ROE **≥ 20%** 且同比提升 ≥ 3pct | `[SH.600519 贵州茅台] 最新季报 ROE=28.5%，同比提升 3.2pct，盈利质量持续改善` | P1 |
| F-PROFIT-NEG | 净利润同比增速**转负**（本期 < 0 且上期 ≥ 0）| `[SH.600010 包钢股份] 最新季报净利润同比下滑（增速=-12.3%），关注基本面变化` | P1 |
| F-REV-HIGH | 营收同比增速 **≥ 30%** 且连续 2 季度 | `[SZ.300750 宁德时代] 连续2季度营收增速>30%，营收高增长趋势确认` | P2 |

#### 告警规则配置

支持在 `watchlist.json` 中按股票精细配置（可覆盖全局默认规则）：

```json
{
  "stocks": [
    {
      "code": "SH.600519",
      "name": "贵州茅台",
      "is_active": true,
      "alert_rules": {
        "disabled": ["T-RSI-OB"],
        "rsi_ob_threshold": 75
      }
    }
  ],
  "global_alert_rules": {
    "enabled": true,
    "rules": ["T-RSI-OB", "T-RSI-OS", "T-MACD-GC", "T-MACD-DC", "T-BOLL-UB", "T-BOLL-LB"]
  }
}
```

---

### 7.3 I2：微信推送通道（企业微信群机器人）

**方案说明**：采用**企业微信群机器人 Webhook**，个人可创建群并添加机器人，零成本、无需企业账号，是个人量化工具最常用的即时通知方案。

**推送格式**（Markdown 卡片）：

```
📊 量化信号提醒

股票：SH.600519 贵州茅台
信号：MACD 金叉
详情：DIF=2.31 上穿 DEA=1.85，多头趋势可能启动
时间：2026-03-18 收盘后
---
当前指标：RSI=65.2 ⚖️中性 | KDJ=K52>D48 ⚖️中性
最新收盘：1830.0 (+1.2%)
---
⚠️ 本提醒为技术指标机械判断，不构成投资建议
```

**配置项**（`.env` 新增）：

| 变量 | 说明 |
|------|------|
| `WECHAT_WEBHOOK_URL` | 企业微信群机器人 Webhook URL |
| `ALERT_ENABLED` | `true` / `false`，全局告警开关，默认 `false`（需显式开启）|

---

### 7.4 I3：邮件推送通道（SMTP）

作为备选通道，当微信 Webhook 不可用时可配置邮件推送：

**配置项**（`.env` 新增）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMAIL_SMTP_HOST` | — | SMTP 服务器，如 `smtp.qq.com` |
| `EMAIL_SMTP_PORT` | `465` | SMTP 端口（SSL）|
| `EMAIL_SENDER` | — | 发件人邮箱 |
| `EMAIL_PASSWORD` | — | 邮箱授权码（非登录密码）|
| `EMAIL_RECIPIENT` | — | 收件人邮箱 |
| `ALERT_CHANNEL` | `wechat` | 推送通道：`wechat` / `email` / `both` |

邮件主题格式：`[量化信号] SH.600519 贵州茅台 - MACD 金叉（2026-03-18）`

---

### 7.5 I4：告警静默策略

| 规则 | 说明 |
|------|------|
| 同股同规则静默 | 同一股票、同一告警规则，**24 小时内只推送 1 次** |
| 趋势持续不重推 | RSI 持续超买，只在**进入时**推送一次，不每天重推 |
| 夜间静默（可选）| 00:00~08:00 期间不推送，延迟到 08:00 发送 |
| 推送失败重试 | HTTP 推送失败，等待 60 秒后重试 1 次，仍失败则记录 WARNING |

**静默状态存储**：新增数据库表 `alert_history`：

```sql
CREATE TABLE alert_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code  TEXT    NOT NULL,
    rule_id     TEXT    NOT NULL,
    triggered_at TEXT   NOT NULL,
    sent_at     TEXT,
    channel     TEXT,
    message     TEXT,
    UNIQUE(stock_code, rule_id, date(triggered_at))
);
```

---

## 8. 迭代3遗留指标补全（模块E，P2）

来自迭代3 §3.6 规划遗留，本迭代一并实现：

| 指标 | 规则 ID | 迭代3状态 | 迭代4计划 |
|------|---------|---------|---------|
| 均线多空排列 MA Alignment | T5 | ⏭ 遗留 | ✅ 实现 |
| 顺势指标 CCI | O3 | ⏭ 遗留 | ✅ 实现 |
| 能量潮 OBV | V1 | ⏭ 遗留 | ✅ 实现 |
| 平均真实波幅 ATR | W1 | ⏭ 遗留 | ✅ 实现 |
| 布林带宽度 BBW | W2 | ⏭ 遗留 | ✅ 实现 |
| PE/PB/PS 历史走势 | E1 | ⏭ 遗留 | ✅ 实现（依赖 F 模块完成后）|

> 上述指标的告警规则亦可同步加入 AlertEngine（如 CCI > 100 超买警报，ATR 突破历史高位波动率警报）。

---

## 9. 数据库变更汇总

| 表名 | 操作 | 说明 |
|------|------|------|
| `fundamentals` | 新增 | 基本面财务数据（模块F）|
| `alert_history` | 新增 | 告警推送历史记录（模块I）|
| `kline_data` | 无变更 | 现有表结构不变 |
| `archive_log`（归档 DB 内）| 新增 | 归档执行日志，存于归档数据库文件中 |

总计新增 **2 张主库表**（fundamentals, alert_history），归档数据库独立存放，不影响现有 Schema。

---

## 10. 配置项汇总（`.env.example` 新增）

```dotenv
# ===== 迭代4新增配置 =====

# --- 模块G：备用数据源 ---
FALLBACK_SOURCE_ENABLED=true
FALLBACK_THRESHOLD=3
FALLBACK_HEALTH_CHECK_INTERVAL=600

# --- 模块H：数据归档 ---
ARCHIVE_DIR=data/archive/
ARCHIVE_WEEKLY_RETENTION_YEARS=3
ARCHIVE_MONTHLY_RETENTION_YEARS=5
ENABLE_ARCHIVE_QUERY=false

# --- 模块I：告警推送 ---
ALERT_ENABLED=false
ALERT_CHANNEL=wechat
WECHAT_WEBHOOK_URL=
EMAIL_SMTP_HOST=smtp.qq.com
EMAIL_SMTP_PORT=465
EMAIL_SENDER=
EMAIL_PASSWORD=
EMAIL_RECIPIENT=
ALERT_SILENCE_HOURS=24
ALERT_NIGHT_SILENCE=false
```

---

## 11. 模块划分与开发顺序建议

| 模块 | 内容 | 估计复杂度 | 优先级 |
|------|------|-----------|--------|
| F1 | 基本面财务数据采集（DB 表 + FinancialFetcher + FundamentalRepo）| 中 | P0 |
| F2 | 基本面 API 端点（2 个端点）| 小 | P0 |
| G1 | AKShareFetcher（接口实现）| 中 | P0 |
| G2 | SourceRouter（路由逻辑）| 小 | P0 |
| F3 | Web 前端基本面面板（卡片 + 趋势图）| 中 | P0 |
| G3 | 数据源健康检测与自动回切 | 小 | P1 |
| I1 | AlertEngine（规则引擎 + 静默逻辑）| 中 | P1 |
| I2 | 微信推送通道 | 小 | P1 |
| I4 | 静默策略 + alert_history 表 | 小 | P1 |
| H1 | ArchiveManager（归档执行器）| 中 | P1 |
| H2 | 归档查询透明代理（KlineRepo 扩展）| 小 | P1 |
| I3 | 邮件推送通道 | 小 | P2 |
| H3 | 归档命令行工具 | 小 | P2 |
| E1-E2 | 遗留指标补全 + PE/PB/PS 走势 | 小~中 | P2 |

**建议开发顺序**：F1 → F2 → G1 → G2（P0 主链路）→ F3（前端基本面展示）→ G3（容灾回切）→ I1+I2+I4（告警主链路）→ H1+H2（归档）→ P2 遗留补全

---

## 12. 非功能需求

| 项目 | 要求 | 说明 |
|------|------|------|
| 财务数据更新频率 | 每周触发一次 | 财报发布频率低，无需每日更新 |
| AKShare 降级延迟 | < 30 秒感知并切换 | 3次失败（各超时10秒）后完成切换 |
| 归档操作时间 | < 60 秒完成 | 月度触发，凌晨执行，不影响日间 |
| 告警推送延迟 | < 60 秒（收盘后触发）| 收盘同步完成后立即扫描规则并推送 |
| 新增表迁移 | 向后兼容 | `init_db()` 中用 `CREATE TABLE IF NOT EXISTS`，不破坏现有数据 |
| 归档数据安全 | 事务原子性 | INSERT + DELETE 在同一事务内，杜绝数据丢失 |
| 告警不含交易指令 | 严格文案审核 | 所有推送模板不包含"买入/卖出"等操作性词汇 |
| 虚拟环境 | 所有新依赖装入 `env_quant/` | 使用 `./env_quant/bin/pip install` |

---

## 13. 不做什么（范围边界）

| 不做 | 原因 |
|------|------|
| 自动交易、下单、报价 | 系统核心约束，严禁 |
| 港股/美股基本面完整覆盖 | 富途港股财报字段差异较大，迭代4专注 A 股，港股/美股后续迭代补全 |
| TuShare 备用数据源 | 需付费 Token，管理成本高；AKShare 免费且覆盖足够 |
| WebSocket 实时告警 | 60 秒轮询已足够日K场景，实时 WebSocket 复杂度高、收益低 |
| 策略回测 | 超出数据源子系统定位，属于独立系统 |
| 多用户/认证 | 个人工具，localhost 访问 |
| 自定义告警公式编辑器 | 复杂度高，非核心需求；规则硬编码+watchlist配置已足够 |
| 归档数据自动删除 | 归档 ≠ 删除，归档数据保留于归档 DB |
| 港股/美股备用数据源 | AKShare 对港股、美股支持质量不足 |

---

## 14. 验收标准

### 模块F：基本面数据

1. `init_db()` 执行后 `fundamentals` 表正常创建（总计 9 张表）
2. `./env_quant/bin/python main.py sync` 执行后，`fundamentals` 表有数据写入，`stock_code` / `report_date` / `roe` 字段值合理
3. `/api/fundamentals/SH.600519` 返回最近 12 期季报数据，`net_profit_yoy` 字段与手工计算一致
4. Web 页面个股分析页面显示基本面快照卡片（ROE / 净利润增速 / 营收增速）及对应信号标签
5. Web 页面折叠展开 ROE 趋势图、净利润增速折线图，数据与 API 返回一致

### 模块G：备用数据源

6. 模拟富途 OpenD 断线，3 次请求失败后日志出现 `数据源降级：切换至 AKShare`，`health.json` 中 `data_source` 字段更新为 `akshare`
7. 降级状态下，A 股历史 K 线采集正常执行，`kline_data` 数据正常写入，`data_source='akshare'` 标记正确
8. 模拟 OpenD 恢复（重启 OpenD），10 分钟内探活成功，日志出现 `主数据源已恢复，自动回切富途`
9. 港股/美股在富途故障时，不触发 AKShare 降级，记录 WARNING 日志

### 模块H：数据归档

10. `./env_quant/bin/python main.py archive --dry-run` 正确统计待归档行数，不执行实际操作
11. `./env_quant/bin/python main.py archive` 执行后：主库 3 年前周K / 5 年前月K 数据被删除；归档 DB 文件创建并包含被迁移数据；归档前后数据总行数不变
12. 启用 `ENABLE_ARCHIVE_QUERY=true` 后，`AdjustmentService.get_adjusted_klines()` 查询 5 年前月K 数据，能正确返回归档数据

### 模块I：告警推送

13. `ALERT_ENABLED=true` 配置后，收盘同步完成后 AlertEngine 自动执行规则扫描，日志出现 `Alert scan completed: N events found`
14. 手动模拟 RSI > 70 场景（修改测试数据），企业微信群收到推送消息，文案格式正确，不含"买入/卖出"词汇
15. 同一股票同一规则 24 小时内只推送 1 次（`alert_history` 表唯一键约束验证）
16. `ALERT_CHANNEL=email` 配置后，邮件推送正常发出（SMTP 连接成功，邮件主题格式正确）
17. 富途数据源切换事件触发系统级告警推送（若已配置推送通道）

### 通用

18. 新增依赖（`akshare` 等）均安装在 `env_quant/`，系统 Python 未被污染
19. 迭代1/2/3 原有验收标准全部继续通过（无回归）
20. 全量同步后 Web 服务正常运行，基本面面板 + 技术指标面板并行展示无报错

---

## 15. 算法支持矩阵（迭代4更新）

| 算法类型 | 所需数据 | 满足情况 |
|---------|---------|---------|
| 技术分析（MA/MACD/RSI/KDJ/BOLL）| OHLCV | ✅ 满足（迭代1/3）|
| 量价因子 | volume, turnover, turnover_rate | ✅ 满足（迭代1）|
| 动量/反转因子 | close, last_close | ✅ 满足（迭代1）|
| 估值因子（PE+PB+PS）| pe_ratio, pb_ratio, ps_ratio | ✅ 满足（迭代2）|
| 基本面因子（ROE/净利润增速/营收增速）| fundamentals 表 | ✅ **迭代4新增** |
| 数据连续性保障 | 备用数据源容灾 | ✅ **迭代4新增（仅A股）** |
| 算法离线运行 | Parquet 导出（含归档数据）| ✅ 满足（迭代2 + 迭代4归档穿透）|
| 主动信号感知 | 告警推送 | ✅ **迭代4新增** |

---

## 16. 遗留问题与待规划功能

### BUG-01：交易日历增量更新缺失（待迭代修复）

**发现日期**：2026-03-19
**优先级**：P1

**问题描述**：
`CalendarRepository.has_calendar()` 仅判断指定范围内是否存在任意记录（COUNT > 0），而非严格检查是否覆盖到 `end_date`。导致以下问题：
- 冷启动时日历 DB 为空，`has_calendar` 返回 False，触发全量拉取（历史起始日到今天），拉取量大，行为符合预期
- **后续增量同步时**：DB 已有历史日历数据，`has_calendar` 返回 True 直接跳过，不会补充新交易日，导致近期日历可能缺失
- 影响范围：`GapDetector` 空洞检测可能漏报最近几个交易日的数据缺口（K 线数据本身不受影响，主流程正常）

**修复方案**：
将 `has_calendar` 或 `_ensure_calendar` 改为检查 `max(trade_date)` 是否 ≥ `end_date`，不足则增量拉取缺失部分。

---

### BUG-02：Watchlist 总览页表格内容未居中对齐

**发现日期**：2026-03-19
**优先级**：P2

**问题描述**：
Watchlist 总览页面（`/watchlist`）表格中，列标题（header）已水平居中，但每行的单元格内容未跟随居中，导致标题与内容对齐方式不一致。

**修复范围**：`web/src/pages/WatchlistPage`（或对应表格组件）中表格 `<td>` 的 `text-align` 或 Tailwind/CSS 类，与 `<th>` 保持一致。

---

### FEAT-01：指标图表新手解释浮层

**发现日期**：2026-03-19
**优先级**：P1（下一 UI 迭代实现）

**需求描述**：
MACD、RSI、KDJ 等副图指标对初学者不友好，需在图表上提供判断逻辑的科普说明。
为保持视觉简洁，说明内容**默认隐藏**，仅在用户主动触发时显示。

**触发方式**（二选一，评审时确认）：
- 鼠标悬停在买入/卖出标记点（散点 markPoint）上时，Tooltip 内展示该信号的判断依据说明
- 图表右上角放置 `[?]` 图标，点击后展开侧边说明栏（固定位置，描述该指标的整体判读方法）

**各指标说明内容规范**：

| 指标 | 买入信号说明示例 | 卖出信号说明示例 |
|------|----------------|----------------|
| MACD | DIF 上穿 DEA（金叉），表示短期均线动能超过长期均线，多头趋势可能启动 | DIF 下穿 DEA（死叉），表示短期动能减弱，空头趋势可能启动 |
| RSI | RSI 从超卖区（<30）向上回升，表示价格跌幅过大、短期存在反弹动能 | RSI 进入超买区（>70），表示短期涨幅过大、可能面临回调压力 |
| KDJ | K 线在低位（<20）上穿 D 线（金叉），超卖区反转信号 | K 线在高位（>80）下穿 D 线（死叉），超买区回调信号 |

**设计约束**：
- 说明文字需通俗，避免专业术语堆砌，目标受众为无量化背景的普通投资者
- 不包含任何"建议买入/卖出"的操作性指令，仅描述技术现象及含义
- **未来迭代新增的指标曲线，必须同步补充相应的新手解释内容**，此为强制规范

---

*文档由 PM 输出，版本 v4.0，2026-03-18*
*核心决策：①基本面以富途财报 API 为主数据源，覆盖 ROE/净利润增速/营收增速等 9 项财务指标，仅采集年报+季报；②备用数据源 AKShare 仅覆盖 A 股，3 次失败触发降级，10 分钟探活自动回切；③周K 归档 3 年前/月K 归档 5 年前，事务原子归档不丢数据，查询透明穿透；④告警推送严禁含买卖操作指令，6 类 P0 技术信号+3 类基本面信号，24 小时同股同规则静默策略防骚扰*
