# AI 量化辅助决策系统

> **声明**：本系统仅负责数据采集、存储与可视化分析，严禁包含任何自动下单、报价、交易相关逻辑。

---

## 这是什么

一套面向量化策略研究的**本地数据服务 + 可视化辅助决策工具**，以富途 OpenD 为数据源，将 A股、港股、美股的历史与实时 K 线数据落库到本地 SQLite，并提供动态前复权、技术指标计算和浏览器可视化能力。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 历史 K 线采集 | 日/周/月 K，从 2000-01-01 起，支持增量续拉和空洞自动修复 |
| 动态前复权 | 存原始价格 + 复权因子，算法层按需计算，无需重刷历史 |
| 实时 K 线推送 | 富途 OpenD 实时推送，当日最新 bar 写库 |
| 技术指标计算 | MA/EMA/MACD/BOLL/RSI/KDJ/MAVOL 七大指标，纯内存计算 |
| 可视化 Web 服务 | 浏览器访问 K 线图 + 指标副图 + 买卖信号标签 |
| 数据导出 | 支持 CSV / Parquet 格式，前复权或原始价格 |

---

## 快速开始

### 前置条件

- [富途牛牛](https://www.futunn.com/download/papertrading) 客户端已启动（OpenD 默认监听 `127.0.0.1:11111`）
- [mamba](https://github.com/conda-forge/miniforge) 或 conda 已安装
- Node.js 18+（前端构建，仅 Web 服务需要）

### 1. 创建虚拟环境

```bash
mamba create -p ./env_quant python=3.10 -y
mamba activate ./env_quant
pip install -r requirements.txt
```

### 2. 初始化配置

```bash
# 环境变量配置
cp .env.example .env
# 按需修改（OpenD 地址端口等，一般保持默认即可）

# Watchlist 配置
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json，填入你关注的股票
```

`watchlist.json` 示例：

```json
[
  { "stock_code": "SH.600519", "name": "贵州茅台", "is_active": true },
  { "stock_code": "HK.00700",  "name": "腾讯控股", "is_active": true },
  { "stock_code": "US.AAPL",   "name": "苹果",     "is_active": true }
]
```

### 3. 启动数据采集服务

```bash
python main.py
```

首次运行会自动建表，然后全量拉取 watchlist 中所有股票的历史 K 线（日/周/月）。

查看实时日志：

```bash
tail -f logs/sync_$(date +%Y%m%d).log
```

### 4. 启动可视化 Web 服务

#### 方式 A：开发模式（前后端分离，推荐调试时使用）

```bash
# 终端1：启动后端 API
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# 终端2：启动前端开发服务器
cd web
npm install     # 首次需要
npm run dev     # 默认监听 http://localhost:5173
```

浏览器访问：`http://localhost:5173`

#### 方式 B：生产模式（单进程，推荐日常使用）

```bash
# 第一步：构建前端（仅首次或前端代码变更后需要）
cd web && npm install && npm run build && cd ..

# 第二步：启动生产服务（后端同时 serve 前端构建产物）
WEB_MODE=production uvicorn api.main:app --host 0.0.0.0 --port 8000
```

浏览器访问：`http://localhost:8000`

---

## 使用说明

### 数据采集服务（`main.py`）

#### 常用命令

```bash
# 正常同步（采集历史 K 线 + 实时订阅）
python main.py

# 查看数据库统计
python main.py stats

# 导出数据为 CSV（前复权）
python main.py export --format csv --adj qfq --output exports/

# 导出数据为 Parquet（原始价格）
python main.py export --format parquet --adj raw --output exports/
```

#### Watchlist 管理

每次运行 `main.py` 会自动检测 `watchlist.json` 的变化：

| 变化类型 | 触发行为 |
|---------|---------|
| 新增股票 | 全量历史拉取（从 2000-01-01 起）|
| `is_active: false → true`（重新激活）| 空洞检测 + 自动补全 |
| `is_active: true → false`（停用）| 取消实时订阅，历史数据保留 |

#### 定时任务配置（cron）

建议在各市场收盘后自动触发，`crontab -e` 添加：

```cron
# A股/港股：每个交易日 17:00 同步（收盘后 1 小时，等待数据就绪）
0 17 * * 1-5 cd /path/to/code_quant && ./env_quant/bin/python main.py >> logs/cron.log 2>&1

# 美股：每个交易日次日 06:00 同步（北京时间冬令时；夏令时改为 05:00）
0 6 * * 2-6 cd /path/to/code_quant && ./env_quant/bin/python main.py >> logs/cron.log 2>&1
```

> **注意**：cron 不继承 shell 环境，务必用虚拟环境的 Python **绝对路径**；macOS 需在「系统设置 → 隐私与安全 → 完全磁盘访问」授权 cron。

Linux 服务器可使用项目内 systemd 配置：

```bash
cat deploy/README.md   # 查看 systemd 部署指南
```

---

### 可视化 Web 服务

浏览器打开 `http://localhost:8000`（生产模式）或 `http://localhost:5173`（开发模式）。

#### 个股分析页（主页 `/`）

```
顶部控制栏
  ├── 股票选择：下拉选 watchlist 中的活跃股票
  ├── 周期选择：1D / 1W / 1M
  └── 时间范围：近3月 / 近6月 / 近1年 / 近3年 / 自定义

主图区域（K 线蜡烛图）
  ├── 叠加：MA5（黄）/ MA20（蓝）/ MA60（橙）
  ├── 叠加：BOLL 三轨（上轨红虚线 / 中轨灰虚线 / 下轨绿虚线）
  │         上轨以上浅红背景（超买警示）/ 下轨以下浅绿背景（超卖提示）
  └── 底部：成交量柱 + MAVOL5/10 均线

副图面板（各含右上角实时信号标签）
  ├── MACD：DIF/DEA 曲线 + MACD 柱，金叉 ▲ / 死叉 ▼ 标记
  ├── RSI：曲线 + 70/30 参考线 + 超买（70~100 浅红）/ 超卖（0~30 浅绿）背景
  └── KDJ：K/D/J 三线 + 80/20 参考线 + 超买（80~100 浅红）/ 超卖（0~20 浅绿）背景

底部信息条
  └── 最新收盘价 / 涨跌幅 / PE / PB / 各指标当前信号标签
```

**信号标签颜色规范：**

| 颜色 | 含义 |
|------|------|
| 🟢 绿色 | 买入区间（超卖反弹、金叉、多头排列）|
| 🔴 红色 | 卖出区间（超买回调、死叉、空头排列）|
| ⚖️ 灰色 | 中性观望（信号不明确）|
| 🔊 橙色 | 放量（成交量异常放大）|

> 信号为技术指标机械判断，仅供参考，不构成投资建议。

**交互功能：**

- 鼠标悬停显示当日 OHLCV + 各指标值 + 信号状态（Tooltip）
- 各子图时间轴联动，十字线跨图显示
- 每 60 秒自动刷新最新数据

#### Watchlist 总览页（`/watchlist`）

表格展示所有活跃股票的最新价、涨跌幅、RSI / MACD / KDJ 信号状态和综合信号，点击任意行跳转个股分析页。

**综合信号判断逻辑：**

| 综合信号 | 条件 |
|---------|------|
| 🟢 偏多 | MACD 金叉 且 RSI 在 50~70 且 KDJ 非死叉超买 |
| 🔴 偏空 | MACD 死叉 且 RSI < 50 且 KDJ 非金叉超卖 |
| ⚖️ 中性 | 其余（信号分歧或均处中性区间）|

#### Web API

后端 API 文档（Swagger UI）：`http://localhost:8000/docs`

| 端点 | 说明 |
|------|------|
| `GET /api/stocks` | 返回 watchlist 中全部活跃股票 |
| `GET /api/kline` | K 线数据 + 技术指标（支持前复权）|
| `GET /api/watchlist/summary` | Watchlist 总览（各股最新指标信号）|
| `GET /api/indicators` | 支持的指标清单及参数说明 |

`/api/kline` 主要参数：

```
?code=SH.600519    股票代码
&period=1D         周期：1D / 1W / 1M
&start=2024-01-01  起始日期
&end=2024-12-31    结束日期
&adj=qfq           复权类型：qfq（前复权）/ raw（不复权）
```

---

## 技术指标说明

指标在后端内存中计算，**不写入数据库**。

| 指标 | 类型 | 默认参数 | 说明 |
|------|------|---------|------|
| MA | 趋势 | n=5/20/60 | 简单移动平均 |
| EMA | 趋势 | n=12/26 | 指数移动平均，k=2/(n+1) |
| MACD | 趋势 | 12/26/9 | DIF/DEA/MACD 柱 |
| BOLL | 趋势 | n=20, k=2 | 上中下轨（总体标准差，与通达信/Wind 一致）|
| RSI | 震荡 | n=14 | Wilder 平滑法 |
| KDJ | 震荡 | n=9 | K/D/J，初始值 K=D=50 |
| MAVOL | 成交量 | n=5/10/20 | 成交量移动平均 |

---

## 复权说明

采用**存储原始价格 + 独立复权因子**策略（与 Wind/聚宽/掘金一致）：

```
前复权价格(t) = 原始价格(t) × ∏{ forward_factor(i) | ex_date(i) > t }
```

优势：除权后只需插入一条复权因子记录，历史 OHLCV 无需重刷。

Python 调用方式：

```python
from core.adjustment_service import AdjustmentService

bars = adj_service.get_adjusted_klines(
    stock_code="SH.600519",
    period="1D",
    start_date="2020-01-01",
    end_date="2024-12-31",
    adj_type="qfq"   # 前复权
)
# 返回 List[KlineBar]，is_adjusted=True，不写库
```

---

## 数据库结构

共 7 张表，SQLite WAL 模式：

| 表名 | 说明 |
|------|------|
| `stocks` | 股票基础信息（代码、名称、市场、lot_size 等）|
| `kline_data` | K 线原始数据（未复权，含 pe_ratio / pb_ratio / ps_ratio）|
| `adjust_factors` | 复权因子（每次除权事件一条记录）|
| `trading_calendar` | 各市场交易日历 |
| `sync_metadata` | 每只股票每个周期的同步状态与进度 |
| `data_gaps` | 检测到的数据空洞记录 |
| `subscription_status` | 实时订阅状态 |

---

## 支持市场

| 市场 | 代码前缀 | 示例 |
|------|---------|------|
| A股（沪）| `SH.` | `SH.600519` 贵州茅台 |
| A股（深）| `SZ.` | `SZ.000858` 五粮液 |
| 港股 | `HK.` | `HK.00700` 腾讯 |
| 美股 | `US.` | `US.AAPL` 苹果 |

---

## 配置参考（`.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPEND_HOST` | `127.0.0.1` | OpenD 监听地址 |
| `OPEND_PORT` | `11111` | OpenD 监听端口 |
| `DB_PATH` | `data/quant.db` | SQLite 数据库路径 |
| `DEFAULT_HISTORY_START` | `2000-01-01` | 历史拉取起始日 |
| `MAX_SUBSCRIPTIONS` | `100` | 最大实时订阅数 |
| `WEB_MODE` | `development` | `production` 时 serve 前端构建产物 |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许的跨域来源（开发模式）|
| `RATE_LIMIT_MIN_INTERVAL` | `0.5` | 请求最小间隔（秒）|
| `RATE_LIMIT_MAX_IN_WINDOW` | `25` | 30 秒窗口内最大请求数 |
| `RECONNECT_MAX_RETRIES` | `5` | OpenD 断线最大重连次数 |
| `EXPORT_DIR` | `exports/` | 数据导出目录 |

---

## 环境要求

- Python 3.10（虚拟环境 `env_quant/`，勿使用系统 Python）
- Node.js 18+（前端构建，仅 Web 服务需要）
- 富途 OpenD（本地运行，随富途牛牛客户端启动）

---

## 目录结构

```
code_quant/
├── main.py                  # 入口：数据采集服务
├── api/                     # 后端 FastAPI Web 服务
│   ├── main.py              # FastAPI app 入口，生产模式 serve 前端
│   ├── routes/              # 路由：stocks / kline / watchlist / indicators
│   └── services/            # 服务层：封装 AdjustmentService + IndicatorEngine
├── web/                     # 前端 React + ECharts 应用
│   ├── src/
│   │   ├── pages/           # 页面：StockAnalysis / WatchlistPage
│   │   └── components/      # 组件：MainChart / MACDPanel / RSIPanel / KDJPanel 等
│   └── package.json
├── core/                    # 业务逻辑
│   ├── indicator_engine.py  # 技术指标计算引擎（MA/MACD/BOLL/RSI/KDJ/MAVOL）
│   ├── adjustment_service.py
│   ├── sync_engine.py
│   └── ...
├── db/                      # 数据库层
│   ├── schema.py            # DDL + init_db()
│   └── repositories/        # 7个 Repository（全部只读供 Web 层调用）
├── futu_wrap/               # 富途 SDK 封装
├── models/                  # 数据模型（Stock / KlineBar / AdjustFactor）
├── config/settings.py       # 配置（从 .env 读取）
├── export/exporter.py       # 数据导出（CSV / Parquet）
├── deploy/                  # systemd 服务配置
│   ├── quant-sync.service   # 数据采集服务（+ 三个市场 timer）
│   ├── quant-web.service    # Web 可视化服务
│   └── README.md            # Linux 服务器部署指南
├── docs/                    # 文档
└── data/quant.db            # SQLite 数据库（不提交仓库）
```

---

## 注意事项

- `watchlist.json` 和 `.env` 含个人配置，已加入 `.gitignore`，**请勿提交仓库**
- 富途 SDK 包名为 `futu`，与项目内 `futu_wrap/` 目录不同，import 时注意：SDK 用 `from futu import ...`，项目模块用相对路径
- Web 层严格只读，不向数据库写入任何数据
- 本系统严禁添加任何交易、下单、报价逻辑

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档 v1](docs/requirements.md) | 迭代1原始需求 |
| [迭代2需求](docs/requirements_iter2.md) | 迭代2 PRD（估值字段/服务化/导出）|
| [迭代3需求](docs/requirements_iter3.md) | 迭代3 PRD v3.1（可视化 Web 服务）|
| [系统设计](docs/design.md) | 迭代1/2 详细设计 |
| [迭代3设计](docs/design_iter3.md) | 迭代3 详细设计（技术选型/API/前端架构）|
| [部署指南](deploy/README.md) | systemd 服务配置与部署 |

---

## 迭代路线图

| 迭代 | 状态 | 内容 |
|------|------|------|
| 迭代1 | ✅ 已完成 | K 线采集、复权、空洞检测、实时订阅 |
| 迭代2 | ✅ 已完成 | PB/PS 估值字段、systemd 部署、数据导出、崩溃恢复 |
| 迭代3 | ✅ 已完成 | 技术指标可视化 Web 服务（MA/EMA/MACD/BOLL/RSI/KDJ/MAVOL）|
| 迭代4 | 规划中 | 基本面数据（ROE）、备用数据源（AKShare）、数据归档清理 |
