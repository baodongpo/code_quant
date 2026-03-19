# CLAUDE.md — 项目上下文（AI 助手读取用）

## 项目概述

**AI 量化辅助决策系统 - 数据源子系统**
仅数据采集，绝对禁止任何自动交易逻辑。

目标：为 A股 / 港股 / 美股量化算法提供完整的历史与实时K线数据，支持前复权动态转换。

---

## 当前状态

- **迭代3已完成 + 联调全部通过**（2026-03-18），HEAD commit `57a9c12`，tag `v0.3.1`
- 迭代1（K线采集）✅ 迭代2（服务化+估值+导出）✅ 迭代3（指标可视化 Web 服务）✅
- 虚拟环境 `env_quant/` 已创建（Python 3.10），依赖已安装
- **下一步**：规划迭代4（基本面数据/备用数据源）

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
WEB_MODE=production ./env_quant/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000

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
- [ ] 迭代3.5：Web 界面优化（综合信号横幅、宽松布局、买卖标记、红涨绿跌配色、侧边说明栏、跨图联动）进行中
- [ ] 迭代4规划：基本面数据（ROE/PB/PS）、备用数据源、归档清理（PRD 已暂存 docs/requirements_iter4.md）

---

## 迭代裁定记录（已确认，不可被 PRD 文字推翻）

> 此处记录经老板口头确认、优先级高于文档文字的设计裁定。
> **任何 agent（Dev/QA/PM）在执行任务时，如遇代码与 PRD 文字冲突，以此表为准。**

| 日期 | 迭代 | 裁定内容 | 背景 |
|------|------|---------|------|
| 2026-03-18 | 迭代3.5 | **副图高度统一 200px**（MACD/RSI/KDJ 三图均为 200px） | 原型评审时老板确认；PRD v3.5 中 MACD=180/RSI=160/KDJ=160 为 PM 笔误，已在 PRD v3.5.2 修正 |
| 2026-03-18 | 迭代3.5 | **去掉鼠标滚轮缩放**（所有图表不用 type:'inside' dataZoom） | 原型评审确认，仅保留底部滑动条 |
| 2026-03-18 | 迭代3.5 | **配色：买入信号=红色系，卖出信号=绿色系**（红涨绿跌原则） | 原型评审确认，与 A股惯例一致 |

---



- **禁止**在代码中添加任何交易、下单、报价逻辑
- `watchlist.json` 和 `.env` 是个人配置，已加入 `.gitignore`，不要提交
- 富途 SDK `futu` 包与项目内 `futu_wrap/` 目录不同名，import 时注意：项目内模块用相对路径，SDK 直接 `from futu import ...`
- 系统 Python 是 3.9，务必在 `env_quant`（Python 3.10）下运行
- **【强制规则】所有 Python 依赖必须安装到虚拟环境 `env_quant/`，严禁装入系统 Python**
  - 永远使用显式路径：`./env_quant/bin/pip install`、`./env_quant/bin/python`、`./env_quant/bin/uvicorn`
  - 不依赖 `mamba activate` / `source activate` 的 shell 激活状态（CI、子 shell、Claude Code 执行环境均不保证继承激活状态）
  - 凡是在 CLAUDE.md、脚本、文档中出现的 `pip`/`python`/`uvicorn` 裸命令，均应替换为 `./env_quant/bin/` 前缀版本
