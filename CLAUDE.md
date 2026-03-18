# CLAUDE.md — 项目上下文（AI 助手读取用）

## 项目概述

**AI 量化辅助决策系统 - 数据源子系统**
仅数据采集，绝对禁止任何自动交易逻辑。

目标：为 A股 / 港股 / 美股量化算法提供完整的历史与实时K线数据，支持前复权动态转换。

---

## 当前状态

- **迭代3已完成**（2026-03-18），HEAD commit `db55b31`，待打 tag `v0.3.0`
- 迭代1（K线采集）✅ 迭代2（服务化+估值+导出）✅ 迭代3（指标可视化 Web 服务）✅
- 虚拟环境 `env_quant/` 已创建（Python 3.10）
- **下一步**：联调验证（需 OpenD 在线），然后规划迭代4（基本面数据/备用数据源）

### 快速打 tag（需手动执行）
```bash
git tag -a v0.3.0 -m "迭代3：技术指标可视化 Web 服务"
```

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

# 2. 激活虚拟环境
mamba activate ./env_quant
pip install -r requirements.txt   # 含迭代3新增 fastapi uvicorn[standard]

# 3. 生成本地配置（首次）
cp .env.example .env
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json，填入实际关注股票

# 4. 启动数据采集服务
python main.py sync

# 5. 启动 Web 服务（迭代3新增）
# 开发模式（前后端分离）：
uvicorn api.main:app --reload --port 8000   # 后端
cd web && npm install && npm run dev         # 前端 http://localhost:5173

# 生产模式（单进程，后端 serve 前端）：
cd web && npm run build
WEB_MODE=production uvicorn api.main:app --host 0.0.0.0 --port 8000

# 6. 查看日志
tail -f logs/sync_$(date +%Y%m%d).log
```

---

## 待办事项

- [x] 迭代1：K线采集（已完成，tag v0.1.0）
- [x] 迭代2：服务化 + 估值 + 导出（已完成，tag v0.2.0）
- [x] 迭代3：技术指标可视化 Web 服务（已完成，commit db55b31，待打 tag v0.3.0）
- [ ] 打 tag：`git tag -a v0.3.0 -m "迭代3：技术指标可视化 Web 服务"`
- [ ] 联调验证（需 OpenD 在线）
  - [ ] `init_db()` 建表验证
  - [ ] 首次全量同步（watchlist 股票）
  - [ ] Web 服务 `/api/stocks` 返回正确列表
  - [ ] `/api/kline` 前复权结果与富途 App 对比
  - [ ] 浏览器验收：K线图 + 指标面板 + 信号标签显示正确
  - [ ] 24小时并行运行稳定性验证
- [ ] 迭代4规划：基本面数据（ROE/PB/PS）、备用数据源、归档清理
- [ ] 推送远端 GitHub：
  ```bash
  gh repo create code_quant --private --source=. --remote=origin --push
  ```

---

## 注意事项

- **禁止**在代码中添加任何交易、下单、报价逻辑
- `watchlist.json` 和 `.env` 是个人配置，已加入 `.gitignore`，不要提交
- 富途 SDK `futu` 包与项目内 `futu_wrap/` 目录不同名，import 时注意：项目内模块用相对路径，SDK 直接 `from futu import ...`
- 系统 Python 是 3.9，务必在 `env_quant`（Python 3.10）下运行
