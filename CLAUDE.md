# CLAUDE.md — 项目上下文（AI 助手读取用）

## 项目概述

**AI 量化辅助决策系统 - 数据源子系统**
仅数据采集，绝对禁止任何自动交易逻辑。

目标：为 A股 / 港股 / 美股量化算法提供完整的历史与实时K线数据，支持前复权动态转换。

---

## 当前状态

- 代码已完整实现，本地 git 有一个干净的 commit（尚未推送远端 GitHub）
- 虚拟环境 `env_quant/` 尚未创建，依赖尚未安装
- `.env` 和 `watchlist.json` 尚未从模板生成（首次运行前需要创建）
- **下一步**：启动 OpenD，创建虚拟环境，安装依赖，运行联调

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
main.py              # 入口，组装所有依赖并启动同步
config/settings.py   # 从 .env 读取配置，有合理默认值
models/              # enums, Stock, KlineBar, AdjustFactor dataclass
db/schema.py         # 所有 DDL，init_db() 建表
db/repositories/     # 7个 repo（stocks/kline/calendar/sync_meta/gap/adjust_factor/subscription）
futu_wrap/             # FutuClient, KlineFetcher, CalendarFetcher, AdjustFactorFetcher, SubscriptionManager
core/                # RateLimiter, WatchlistManager, AdjustmentService, GapDetector, KlineValidator, SyncEngine
docs/                # requirements.md（需求）, design.md（详细设计）
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

# 2. 激活虚拟环境（首次需先创建）
mamba create -p ./env_quant python=3.10 -y
mamba activate ./env_quant
pip install -r requirements.txt

# 3. 生成本地配置（首次）
cp .env.example .env
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json，填入实际关注股票

# 4. 运行
python main.py

# 5. 查看日志
tail -f logs/sync_$(date +%Y%m%d).log
```

---

## 待办事项

- [ ] 联调验证（需 OpenD 在线）
  - [ ] `init_db()` 建表验证
  - [ ] 首次全量同步（watchlist 三只股票）
  - [ ] `adjust_factors` 有复权事件写入
  - [ ] `AdjustmentService` 前复权结果与富途 App 对比
  - [ ] 手动制造空洞，验证 `GapDetector` 检测与自动修复
  - [ ] 验证实时订阅推送写入
- [ ] 联调通过后推送远端 GitHub：
  ```bash
  gh repo create code_quant --private --source=. --remote=origin --push
  ```

---

## 注意事项

- **禁止**在代码中添加任何交易、下单、报价逻辑
- `watchlist.json` 和 `.env` 是个人配置，已加入 `.gitignore`，不要提交
- 富途 SDK `futu` 包与项目内 `futu_wrap/` 目录不同名，import 时注意：项目内模块用相对路径，SDK 直接 `from futu import ...`
- 系统 Python 是 3.9，务必在 `env_quant`（Python 3.10）下运行
