# CLAUDE.md — 项目上下文（AI 助手读取用）

## 项目概述

**AI 量化辅助决策系统 - 数据源子系统**
仅数据采集，绝对禁止任何自动交易逻辑。

目标：为 A股 / 港股 / 美股量化算法提供完整的历史与实时K线数据，支持前复权动态转换。

---

## 当前状态

- **迭代5已完成 + 热修复已发布**（2026-03-19），最新 tag `v0.5.1-fix`
- 迭代1（K线采集）✅ 迭代2（服务化+估值+导出）✅ 迭代3（指标可视化 Web 服务）✅ 迭代4（基本面/容灾/归档/告警）✅ 迭代5（稳定性加固+用户体验提升）✅
- 虚拟环境 `env_quant/` 已创建（Python 3.10），依赖已安装
- **下一步**：待规划迭代6

---

## 技术选型

| 项目 | 选型 |
|------|------|
| 数据库 | SQLite（WAL 模式） |
| 数据源 | 富途 OpenD（futu-api） |
| 复权策略 | 存原始价格 + adjust_factors 表，算法层动态前复权 |
| K线粒度 | 日K（1D）、周K（1W）、月K（1M） |
| 虚拟环境 | mamba，路径 `./env_quant`，Python 3.10 |
| 配置管理 | `.env` 文件（python-dotenv），不提交仓库 |

---

## 目录结构关键说明

```
main.py              # 入口，数据采集同步（python main.py sync）
config/settings.py   # 从 .env 读取配置，有合理默认值
models/              # enums, Stock, KlineBar, AdjustFactor dataclass
db/schema.py         # 所有 DDL，init_db() 建表
db/repositories/     # 7个 repo（stocks/kline/calendar/sync_meta/gap/adjust_factor/subscription）
futu_wrap/           # FutuClient, KlineFetcher, CalendarFetcher, AdjustFactorFetcher, SubscriptionManager
core/                # RateLimiter, WatchlistManager, AdjustmentService, GapDetector, KlineValidator, SyncEngine
core/indicator_engine.py  # 【迭代3新增】7个技术指标计算 + 信号判断
api/                 # 【迭代3新增】FastAPI 后端 REST API（只读）
  main.py            # FastAPI app 入口（uvicorn api.main:app）
  routes/            # stocks / kline / watchlist / indicators
  services/          # kline_service（封装 AdjustmentService + IndicatorEngine）
web/                 # 【迭代3新增】React 前端（Vite + ECharts）
  src/components/    # MainChart, MACDPanel, RSIPanel, KDJPanel, BottomBar, SignalTag 等
  src/pages/         # StockAnalysis（/）, WatchlistPage（/watchlist）
export/              # 数据导出（Parquet/CSV）
deploy/              # systemd 服务配置（quant-sync.service, quant-web.service）
docs/                # PRD / 设计文档 / CR 报告
watchlist.json       # 个人持仓列表（不提交仓库），从 watchlist.json.example 复制
.env                 # 本地配置（不提交仓库），从 .env.example 复制
```

---

## 关键设计决策

1. **复权**：不存前复权价格，存原始价格 + `adjust_factors` 表，`AdjustmentService` 动态计算
2. **Volume 单位**：股（shares），换算手数用 `volume / lot_size`
3. **空洞检测**：基于交易日历的连续性（非日历日），`GapDetector._group_consecutive()`
4. **限频**：双约束令牌桶，仅作用于 `get_history_kline`，实时推送不受限
5. **Watchlist 差异检测**：新增/重激活/停用三种场景，`WatchlistManager.load()` 返回三元组
6. **A股日历**：market 字段存 `"A"`，日历查询映射到 `"SH"`

---

## 数据库表（7张）

`stocks` / `kline_data` / `adjust_factors` / `trading_calendar` / `sync_metadata` / `data_gaps` / `subscription_status`

---

## 恢复工作步骤

```bash
# 1. 启动富途 OpenD（打开富途牛牛客户端）

# 2. 安装依赖（显式使用虚拟环境，不依赖 activate）
./env_quant/bin/pip install -r requirements.txt

# 3. 生成本地配置（首次）
cp .env.example .env
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json，填入实际关注股票

# 4. 启动数据采集服务
./env_quant/bin/python main.py sync

# 5. 启动 Web 服务（迭代3新增）
# 开发模式（前后端分离）：
./env_quant/bin/uvicorn api.main:app --reload --port 8000   # 后端
cd web && npm install && npm run dev                         # 前端 http://localhost:5173

# 生产模式（单进程，后端 serve 前端）：
cd web && npm run build
WEB_MODE=production ./env_quant/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000

# 6. 查看日志
tail -f logs/sync_$(date +%Y%m%d).log
```

---

## 待办事项

- [x] 迭代1：K线采集（已完成，tag v0.1.0）
- [x] 迭代2：服务化 + 估值 + 导出（已完成，tag v0.2.0）
- [x] 迭代3：技术指标可视化 Web 服务（已完成，tag v0.3.0）
- [x] 部署打包脚本（pack.sh / deploy.sh / start.sh / stop.sh / plist，tag v0.3.1）
- [x] 联调验证（/api/health ✅ /api/stocks ✅ /api/watchlist/summary ✅ /docs ✅ 浏览器 K线图+指标面板 ✅）
- [x] 迭代3.5：Web 界面优化（综合信号横幅、宽松布局、买卖标记、红涨绿跌配色、侧边说明栏、跨图联动）✅ 全部完成
- [x] 迭代4（范围已确认 2026-03-19，全部完成 2026-03-19，发布包 v0.4.0-20260319，待目标机验收后打 tag）：
  - [x] BUG-01：交易日历增量更新缺失（calendar_repo.has_calendar 改为 max(trade_date) >= end_date）✅
  - [x] BUG-02：Watchlist 表格单元格居中对齐 ✅
  - [x] BUG-03：副图滑动条无法与主图全局联动 ✅ useChartSync 双向 dataZoom 广播+互斥标志+折叠重建重绑定
  - [x] stock name：watchlist.json 加 name 字段，全链路显示股票名称，优化布局 ✅
  - [x] 下拉配色：首页股票选择下拉多头红色/空头绿色字体 ✅
  - [x] FEAT-01：指标图表新手解释浮层（MACD/RSI/KDJ [?] 图标，默认隐藏，点击展开，不含买卖指令）✅
  - [x] deploy/start.sh 版本更新迁移支持：新增 `python main.py migrate` 子命令 ✅
  - [x] 发现-01（附加）：has_calendar SQL 补 `AND is_trading_day = 1` 过滤 ✅
- [x] 迭代5（全部完成 2026-03-19，tag v0.5.0）：
  - [x] TODO-01：sync 重启时对最新交易日使用 `upsert_many`（覆盖写）而非 `insert_many`（跳过），修复进程中途退出导致当日半日K线永远不更新为全日数据的问题。涉及 `SyncEngine` 增量逻辑，需区分"历史日期"与"最新交易日"两种写入策略 ✅
  - [x] FEAT-02：K线图悬停浮层增加当日数据更新时间。即 `kline_data.updated_at` 字段（推送覆盖时更新），需后端 API 在 bars 中透传 `updated_at`，前端 MainChart tooltip 展示（格式如"数据更新：2026-03-19 16:32:05"）✅
  - [x] FEAT-03：首页股票下拉菜单按综合信号分组，多头（bullish）一组、空头（bearish）一组、中性（neutral）一组，使用 `<optgroup>` 实现，便于直观区分多空方向 ✅
  - [x] FEAT-04：局域网访问 + Token 鉴权。Web 服务绑定 `0.0.0.0` 对局域网开放（静态文件 + `/api/*` 同一进程）。在 `.env` 中配置固定 `WEB_ACCESS_TOKEN`，所有请求（页面 + API）均需鉴权，本机回环（`127.0.0.1`）豁免鉴权 ✅
  - [x] BUG-ITER5-01：`kline_data.updated_at` 列缺少旧库迁移逻辑（`db/schema.py` `init_db()` 补列修复）✅
  - [x] 热修复 v0.5.1-fix（2026-03-19）：
    - sync `last_sync_date==today` 时 `start_date` 被推到 tomorrow 导致当日数据跳过（根本原因修复）✅
    - `upsert_many` 中 `datetime('now')` 为 UTC，改为 `datetime('now', '+8 hours')` 修复 updated_at 时区问题 ✅
    - `deploy/start.sh` 未显式赋值 `WEB_HOST` 导致旧版脚本写死 `127.0.0.1`，无法局域网访问 ✅
- [ ] 迭代6（待规划）：
  - [ ] FEAT-repair：新增 `python main.py repair` 子命令，支持对指定股票/周期/日期强制 upsert 覆盖 K线数据。
    - 参数：`--stock`（可选，不传则修复所有关注股票）、`--date`（目标日期）、`--period`（1D/1W/1M，可多选，不传则修复全部）
    - 用户只需传业务日期，命令内部自动映射到对应的 trade_date：
      - 1D：直接用指定日期
      - 1W：trade_date 为该周最后一个交易日（港股=周五），需从指定日期推算所在周的周末日
      - 1M：trade_date 为该月第一个交易日（实测规律），需从指定日期推算所在月的月初交易日
    - 实现：复用 `SyncEngine._fetch_and_store`，对映射后的日期范围全部走 `upsert_many`，不改 `sync_metadata`
    - 注意：盘中调用 1D 可获取当日半日数据（已验证）；1W 用 `start=today,end=today` 查询返回空，需用所在周的末日作为查询范围
    - 已知数据规律（2026-03-20 实测）：1D `time_key[:10]=当天`，1W `trade_date=周末最后交易日`，1M `trade_date=月初第一交易日`

---

## 迭代裁定记录（已确认，不可被 PRD 文字推翻）

> 此处记录经老板口头确认、优先级高于文档文字的设计裁定。
> **任何 agent（Dev/QA/PM）在执行任务时，如遇代码与 PRD 文字冲突，以此表为准。**

| 日期 | 迭代 | 裁定内容 | 背景 |
|------|------|---------|------|
| 2026-03-18 | 迭代3.5 | **副图高度统一 200px**（MACD/RSI/KDJ 三图均为 200px） | 原型评审时老板确认；PRD v3.5 中 MACD=180/RSI=160/KDJ=160 为 PM 笔误，已在 PRD v3.5.2 修正 |
| 2026-03-18 | 迭代3.5 | **去掉鼠标滚轮缩放**（所有图表不用 type:'inside' dataZoom） | 原型评审确认，仅保留底部滑动条 |
| 2026-03-18 | 迭代3.5 | **配色：买入信号=红色系，卖出信号=绿色系**（红涨绿跌原则） | 原型评审确认，与 A股惯例一致 |
| 2026-03-19 | 迭代4+ | **每个指标图表必须附带新手解释浮层**（默认隐藏，悬停/点击买卖标记点或 [?] 图标时显示），**未来新增指标曲线时同样强制执行此规范** | 老板确认；说明内容需通俗，不含任何买卖操作指令；详见 docs/requirements_iter4.md §16 FEAT-01 |

---



- **禁止**在代码中添加任何交易、下单、报价逻辑
- `watchlist.json` 和 `.env` 是个人配置，已加入 `.gitignore`，不要提交
- 富途 SDK `futu` 包与项目内 `futu_wrap/` 目录不同名，import 时注意：项目内模块用相对路径，SDK 直接 `from futu import ...`
- 系统 Python 是 3.9，务必在 `env_quant`（Python 3.10）下运行
- **【强制规则】所有 Python 依赖必须安装到虚拟环境 `env_quant/`，严禁装入系统 Python**
  - 永远使用显式路径：`./env_quant/bin/pip install`、`./env_quant/bin/python`、`./env_quant/bin/uvicorn`
  - 不依赖 `mamba activate` / `source activate` 的 shell 激活状态（CI、子 shell、Claude Code 执行环境均不保证继承激活状态）
  - 凡是在 CLAUDE.md、脚本、文档中出现的 `pip`/`python`/`uvicorn` 裸命令，均应替换为 `./env_quant/bin/` 前缀版本
- **【团队协作规则】各角色各司其职，不越权**
  - team-lead 负责任务分配、流程协调、进度跟踪，不直接写业务代码
  - Dev 负责代码实现，QA 负责代码审查和测试，PM 负责需求评估和验收
- **【迭代启动规则】任何迭代计划，必须等待老板明确确认范围后方可启动开发**，不得提前分配任务或开始实现
