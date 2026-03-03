# AI 量化辅助决策系统 - 数据源子系统详细设计文档

**版本**: v1.0
**日期**: 2026-03-03

---

## 1. 系统架构总览

```
main.py
  ├─ init_db()                          # 初始化 SQLite（WAL 模式）
  ├─ WatchlistManager.load()
  │    └─ 差异检测 → (active, newly_added, reactivated)
  ├─ SubscriptionManager.sync_subscriptions(active_stocks)
  │    └─ 对活跃股票建立实时K线订阅（推送回调 → kline_data）
  └─ SyncEngine.run_full_sync(active, newly_added, reactivated)
       └─ for stock, for period in [1D, 1W, 1M]:
            sync_one()
              ├─ 确定 start_date（新增/重激活/增量）
              ├─ CalendarFetcher → 补充交易日历
              ├─ AdjustFactorFetcher → 刷新复权因子
              ├─ GapDetector → 检测空洞 → KlineFetcher 补洞
              ├─ KlineFetcher.fetch_simple() → RateLimiter → get_history_kline
              ├─ KlineValidator → OHLCV 校验
              ├─ KlineRepository.insert_many()（INSERT OR IGNORE）
              └─ SyncMetaRepository.upsert(SUCCESS)

实时推送路径（并行）：
  OpenD 推送 → SubscriptionManager.on_kline_push()
             → KlineRepository.upsert_many()（INSERT OR REPLACE）
```

---

## 2. 目录结构

```
code_quant/
├── main.py                         # 入口：初始化、组装依赖、启动同步
├── watchlist.json                  # 用户关注列表（不提交仓库）
├── watchlist.json.example          # Watchlist 模板（提交仓库）
├── requirements.txt                # Python 依赖
├── .env                            # 本地环境配置（不提交仓库）
├── .env.example                    # 环境配置模板（提交仓库）
├── .gitignore
├── env_quant/                      # mamba 虚拟环境（不提交仓库）
├── data/
│   └── quant.db                    # SQLite 数据库（不提交仓库）
├── logs/
│   └── sync_YYYYMMDD.log           # 按日轮转日志（不提交仓库）
├── docs/
│   ├── requirements.md             # 需求文档
│   └── design.md                   # 详细设计文档（本文件）
├── config/
│   └── settings.py                 # 全局常量（从 .env 读取）
├── models/
│   ├── enums.py                    # Market, Period, SyncStatus 等枚举
│   ├── stock.py                    # Stock dataclass
│   └── kline.py                    # KlineBar, AdjustFactor dataclass
├── db/
│   ├── schema.py                   # DDL + init_db()
│   ├── connection.py               # DBConnection 上下文管理器
│   └── repositories/
│       ├── stock_repo.py
│       ├── kline_repo.py
│       ├── calendar_repo.py
│       ├── sync_meta_repo.py
│       ├── gap_repo.py
│       ├── adjust_factor_repo.py
│       └── subscription_repo.py
├── futu/
│   ├── client.py                   # FutuClient：OpenQuoteContext 生命周期
│   ├── kline_fetcher.py            # KlineFetcher：get_history_kline 封装
│   ├── calendar_fetcher.py         # CalendarFetcher：get_trading_days 封装
│   ├── adjust_factor_fetcher.py    # AdjustFactorFetcher：get_rehab 封装
│   └── subscription_manager.py    # SubscriptionManager：订阅管理
└── core/
    ├── watchlist_manager.py        # WatchlistManager：差异检测
    ├── rate_limiter.py             # RateLimiter：双约束令牌桶
    ├── gap_detector.py             # GapDetector：交易日连续空洞检测
    ├── validator.py                # KlineValidator：OHLCV 校验
    ├── adjustment_service.py       # AdjustmentService：前复权动态转换
    └── sync_engine.py              # SyncEngine：核心同步编排
```

---

## 3. 数据库设计

### 3.1 表结构概览

| 表名 | 说明 | 主键 |
|------|------|------|
| `stocks` | 股票基础信息 | `stock_code` |
| `kline_data` | K线数据（原始未复权）| `(stock_code, period, trade_date)` |
| `adjust_factors` | 复权因子 | `(stock_code, ex_date)` |
| `trading_calendar` | 交易日历 | `(market, trade_date)` |
| `sync_metadata` | 同步状态追踪 | `(stock_code, period)` |
| `data_gaps` | 数据空洞记录 | `id` AUTO |
| `subscription_status` | 订阅状态 | `(stock_code, period)` |

### 3.2 复权策略

**存储**：`kline_data` 存原始未复权价格（真实成交价），`adjust_factors` 存每次除权事件。

**前复权计算公式**：
```
前复权价格(t) = 原始价格(t) × ∏{ forward_factor(i) | ex_date(i) > t }
```
即：对某交易日 `t`，将其之后所有除权事件的 `forward_factor` 累乘，作为当日的调整系数。

**优势**：拆股/分红后只需插入一条复权因子记录，全部历史 OHLCV 数据无需修改。

### 3.3 Volume 单位

`kline_data.volume` 单位为**股（shares）**。换算手数：`volume_in_lots = volume / lot_size`，`lot_size` 存储在 `stocks` 表。

---

## 4. 关键模块设计

### 4.1 RateLimiter（双约束令牌桶）

仅作用于历史K线查询（`get_history_kline`），实时推送不受限。

```
约束1 - 最小请求间隔：
  elapsed = now - last_request_time
  if elapsed < 0.5s: sleep(0.5 - elapsed)

约束2 - 滑动窗口突发限制：
  维护近 30s 内的请求时间戳 deque
  if len(requests_in_window) >= 25: sleep 至窗口过期

重试策略（execute_with_retry）：
  指数退避：1s → 2s → 4s
  仅对 RateLimitError / TimeoutError / ConnectionError 重试
  其他异常直接抛出
```

### 4.2 GapDetector（交易日空洞检测）

```python
detect_gaps(stock_code, period, market, start_date, end_date):
  1. 从 trading_calendar 获取基准交易日列表
     - 1D：全部交易日
     - 1W：每周最后一个交易日
     - 1M：每月最后一个交易日
  2. 从 kline_data 获取已存储日期集合
  3. missing = [d for d in trading_days if d not in stored]
  4. _group_consecutive(missing, trading_days) → [(start, end), ...]
```

`_group_consecutive` 关键：**连续**定义为在 `trading_days` 列表中索引相差 1（交易日连续，非日历日连续）。

### 4.3 WatchlistManager（差异检测）

```
load() 返回三元组 (active_stocks, newly_added, reactivated)：

  新增（DB 无此 code）      → newly_added   → SyncEngine 全量拉取
  重新激活（0→1）           → reactivated   → SyncEngine 从 first_sync_date 补洞
  停用（1→0）               → 触发取消订阅，保留历史数据
  JSON 中不存在（已移除）   → 同停用处理
```

### 4.4 SyncEngine（同步编排）

```
sync_one(stock, period, today, force_full, is_reactivated):
  1. 确定 start_date：
     force_full / 首次  → DEFAULT_HISTORY_START ("2000-01-01")
     is_reactivated     → sync_metadata.first_sync_date
     正常增量           → sync_metadata.last_sync_date
  2. set_status(RUNNING)
  3. _ensure_calendar(market, start_date, today)
  4. _refresh_adjust_factors(stock_code)   # 仅追加新事件
  5. _heal_gaps(stock, period, ...)        # 修复已知空洞
  6. _fetch_and_store(stock, period, ...)  # 拉取增量
  7. upsert(status=SUCCESS, last_sync_date=today)
```

### 4.5 SubscriptionManager（订阅额度管理）

- 维护 `subscription_status` 表记录当前订阅状态
- `subscribe()` 前检查当前订阅数是否达到 `MAX_SUBSCRIPTIONS` 上限
- 超限时记录 WARNING，优先级按 watchlist 顺序
- `sync_subscriptions()` 批量对齐：活跃股票确保订阅，非活跃确保取消

---

## 5. 数据流

```
写入路径1（历史拉取）：
  KlineFetcher.fetch_simple()
    → [KlineBar(is_adjusted=False)]
    → KlineValidator.validate_many()
    → KlineRepository.insert_many()  [INSERT OR IGNORE]
    → kline_data 表

写入路径2（实时推送）：
  OpenD 推送
    → SubscriptionManager.on_kline_push()
    → KlineRepository.upsert_many()  [INSERT OR REPLACE]
    → kline_data 表

读取路径（算法层）：
  AdjustmentService.get_adjusted_klines(stock, period, start, end, adj_type="qfq")
    → KlineRepository.get_bars()         # 读原始价格
    → AdjustFactorRepository.get_factors()  # 读复权因子
    → 计算前复权乘数
    → [KlineBar(is_adjusted=True)]       # 返回，不写库
```

---

## 6. 市场差异对照

| 项目 | A股 (SH/SZ) | 港股 (HK) | 美股 (US) |
|------|------------|----------|----------|
| 富途代码前缀 | SH. / SZ. | HK. | US. |
| 日历 market | SH | HK | US |
| 典型 lot_size | 100 | 100~1000 | 1 |
| 币种 | CNY | HKD | USD |

> A股 `market` 字段存 `"A"` 作为逻辑分组，日历查询统一映射到 `SH`。

---

## 7. 配置说明

所有可调参数通过项目根目录 `.env` 文件注入，参考 `.env.example`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPEND_HOST` | `127.0.0.1` | OpenD 监听地址 |
| `OPEND_PORT` | `11111` | OpenD 监听端口 |
| `DB_PATH` | `data/quant.db` | SQLite 数据库路径 |
| `RATE_LIMIT_MIN_INTERVAL` | `0.5` | 请求最小间隔（秒）|
| `RATE_LIMIT_WINDOW_SECONDS` | `30` | 限频滑动窗口（秒）|
| `RATE_LIMIT_MAX_IN_WINDOW` | `25` | 窗口内最大请求数 |
| `RATE_LIMIT_MAX_RETRIES` | `3` | 最大重试次数 |
| `MAX_SUBSCRIPTIONS` | `100` | 最大实时订阅数 |
| `DEFAULT_HISTORY_START` | `2000-01-01` | 历史拉取起始日 |

---

## 8. 环境搭建

```bash
# 创建虚拟环境（Python 3.10）
mamba create -p ./env_quant python=3.10 -y
mamba activate ./env_quant

# 安装依赖
pip install -r requirements.txt

# 配置本地环境
cp .env.example .env
# 编辑 .env 按需修改 OPEND_HOST/PORT 等

# 配置 watchlist
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json 填入自己的股票列表

# 启动 OpenD 后运行
python main.py
```
