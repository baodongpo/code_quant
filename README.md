# AI 量化辅助决策系统

> **声明**：本系统仅负责数据采集、存储与可视化分析，严禁包含任何自动下单、报价、交易相关逻辑。

---

## 这是什么

一套面向量化策略研究的**本地数据服务 + 可视化辅助决策工具**，以富途 OpenD 为 A股/港股数据源、TuShare 为美股数据源，将 A股、港股、美股的历史与实时 K 线数据落库到本地 SQLite，并提供动态前复权、技术指标计算和浏览器可视化能力。

**核心能力：**

| 能力 | 说明 |
|------|------|
| 历史 K 线采集 | 日/周/月 K，从 2000-01-01 起，支持增量续拉和空洞自动修复 |
| 动态前复权 | 存原始价格 + 复权因子，算法层按需计算，无需重刷历史 |
| 实时 K 线推送 | 富途 OpenD 实时推送，当日最新 bar 写库 |
| 技术指标计算 | MA/EMA/MACD/BOLL/RSI/KDJ/MAVOL 七大指标，纯内存计算 |
| 可视化 Web 服务 | 浏览器访问 K 线图 + 指标副图 + 买卖信号标签 |
| 数据导出 | 支持 CSV / Parquet 格式，前复权或原始价格 |
| 数据运维工具 | 独立空洞检测、手动修复指定日期 K 线数据 |

---

## 快速开始

### 前置条件

- [富途牛牛](https://www.futunn.com/download/papertrading) 客户端已启动（OpenD 默认监听 `127.0.0.1:11111`）
- [mamba](https://github.com/conda-forge/miniforge) 或 conda 已安装
- Node.js 18+（前端构建，仅 Web 服务需要）

### 1. 创建虚拟环境

```bash
mamba create -p ./env_quant python=3.10 -y
./env_quant/bin/pip install -r requirements.txt
```

> **注意**：本项目强制使用虚拟环境显式路径（`./env_quant/bin/python`），不依赖 `activate` 激活状态。下文所有命令均遵循此规范。

### 2. 初始化配置

```bash
# 环境变量配置
cp .env.example .env
# 按需修改（OpenD 地址端口等，一般保持默认即可）

# Watchlist 配置
cp watchlist.json.example watchlist.json
# 编辑 watchlist.json，填入你关注的股票
```

`watchlist.json` 按市场分组，示例：

```json
{
  "markets": [
    {
      "market": "HK",
      "enabled": true,
      "stocks": [
        {"stock_code": "HK.00700", "name": "腾讯控股", "asset_type": "stock",
         "is_active": true, "lot_size": 100, "currency": "HKD"}
      ]
    },
    {
      "market": "A",
      "enabled": true,
      "stocks": [
        {"stock_code": "SH.600519", "name": "贵州茅台", "asset_type": "stock",
         "is_active": true, "lot_size": 100, "currency": "CNY"}
      ]
    },
    {
      "market": "US",
      "enabled": true,
      "stocks": [
        {"stock_code": "US.AAPL", "name": "Apple", "asset_type": "stock",
         "is_active": true, "lot_size": 1, "currency": "USD"}
      ]
    }
  ]
}
```

### 3. 初始化数据库（首次或版本升级后执行）

```bash
./env_quant/bin/python main.py migrate
```

此命令幂等，无需富途连接，建表/补列并同步 watchlist 中的股票信息到数据库。

### 4. 启动数据采集服务

```bash
./env_quant/bin/python main.py sync
```

首次运行会全量拉取 watchlist 中所有股票的历史 K 线（日/周/月）。查看实时日志：

```bash
tail -f logs/sync_$(date +%Y%m%d).log
```

### 5. 启动可视化 Web 服务

#### 方式 A：开发模式（前后端分离，推荐调试时使用）

```bash
# 终端1：启动后端 API
./env_quant/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

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
WEB_MODE=production ./env_quant/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
```

浏览器访问：`http://localhost:8000`

---

## 命令行完整参考

所有命令均使用虚拟环境显式路径：`./env_quant/bin/python main.py <子命令>`

### 命令总览

| 子命令 | 是否需要 OpenD | 说明 |
|--------|--------------|------|
| `sync` | A股/港股需要，美股不需要 | 历史数据采集 + 增量同步（默认命令）|
| `migrate` | 不需要 | DB 表结构迁移 + watchlist 股票信息同步 |
| `stats` | 不需要 | 打印同步状态与数据空洞汇总 |
| `export` | 不需要 | 导出 K 线数据到 CSV / Parquet 文件 |
| `check-gaps` | 不需要 | 独立空洞检测，结果写入 `data_gaps` 表 |
| `repair` | A股/港股需要，美股不需要 | 强制 upsert 覆盖指定日期的 K 线数据 |

---

### `sync` — 数据采集同步

```bash
./env_quant/bin/python main.py sync
./env_quant/bin/python main.py        # 等价，无子命令时默认执行 sync
```

**执行逻辑：**

1. 连接富途 OpenD（watchlist 仅有美股时可跳过，进入 yfinance-only 模式）
2. 读取 `watchlist.json`，与数据库做差异检测（新增 / 重激活 / 停用）
3. 对所有活跃股票执行历史 K 线同步（日/周/月）
4. 检测并修复数据空洞
5. 维护实时推送订阅（当日行情）

**Watchlist 变化处理：**

| 变化类型 | 触发行为 |
|---------|---------|
| 新增股票 | 全量历史拉取（从 `DEFAULT_HISTORY_START` 起）|
| `is_active: false → true`（重新激活）| 空洞检测 + 自动补全 |
| `is_active: true → false`（停用）| 取消实时订阅，历史数据保留 |

**优雅退出：** 支持 SIGTERM（systemd stop），完成当前股票任务后退出。

---

### `migrate` — 数据库迁移

```bash
./env_quant/bin/python main.py migrate
```

**适用场景：**

- 首次安装，初始化建表
- 版本升级后，补充新增字段（幂等，可重复执行）
- 修改 `watchlist.json` 后，同步股票名称到数据库

**无需富途连接**，可在 `deploy.sh` / `start.sh` 中作为启动前检查步骤调用。

---

### `stats` — 同步状态汇总

```bash
./env_quant/bin/python main.py stats
```

**输出内容：**

- 活跃 / 非活跃股票数量
- 每只股票 × 每个周期的同步状态分布（pending / running / success / failed）
- 失败记录列表（最多 20 条，含错误信息）
- 当前未修复的数据空洞列表（open 状态）

**示例输出（部分）：**

```
================================================================
  AI Quant Data Subsystem — Sync Stats  (DB: data/quant.db)
================================================================
  Active stocks  : 3
  Inactive stocks: 1
================================================================

  Sync status summary (3 stocks × 3 periods):
    success     : 9
    pending     : 0

  ⚠  Open data gaps (1):
    SH.600519        [1D]  2020-02-03~2020-02-03
================================================================
```

---

### `export` — 导出 K 线数据

```bash
./env_quant/bin/python main.py export <STOCK_CODE> <PERIOD> <START_DATE> <END_DATE> \
    [--adj-type qfq|raw] \
    [--fmt parquet|csv] \
    [--output-dir <DIR>]
```

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `STOCK_CODE` | 位置参数 | 是 | 股票代码，如 `SH.600519` |
| `PERIOD` | 位置参数 | 是 | K线周期：`1D` / `1W` / `1M` |
| `START_DATE` | 位置参数 | 是 | 起始日期，格式 `YYYY-MM-DD` |
| `END_DATE` | 位置参数 | 是 | 结束日期，格式 `YYYY-MM-DD` |
| `--adj-type` | 可选 | 否 | 复权类型：`qfq`（前复权，默认）/ `raw`（不复权）|
| `--fmt` | 可选 | 否 | 输出格式：`parquet`（默认）/ `csv` |
| `--output-dir` | 可选 | 否 | 输出目录（默认 `exports/`）|

**示例：**

```bash
# 导出贵州茅台日K，前复权，Parquet 格式（默认）
./env_quant/bin/python main.py export SH.600519 1D 2020-01-01 2024-12-31

# 导出腾讯控股日K，不复权，CSV 格式
./env_quant/bin/python main.py export HK.00700 1D 2023-01-01 2024-12-31 \
    --adj-type raw --fmt csv

# 导出苹果周K，指定输出目录
./env_quant/bin/python main.py export US.AAPL 1W 2022-01-01 2024-12-31 \
    --adj-type qfq --fmt csv --output-dir /tmp/my_exports
```

**输出文件命名：** `<STOCK_CODE>_<PERIOD>_<ADJ>_<START>_<END>.<ext>`，如 `SH.600519_1D_qfq_20200101_20241231.parquet`

---

### `check-gaps` — 独立空洞检测

```bash
./env_quant/bin/python main.py check-gaps \
    [--stock <STOCK_CODE>] \
    [--period 1D [1W] [1M]]
```

**无需富途连接**，只读本地数据库。

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--stock` | 可选 | 否 | 指定股票代码；不传则检测所有活跃股票 |
| `--period` | 可选，可多选 | 否 | 指定周期（`1D` `1W` `1M`）；不传则检测全部三个周期 |

**执行逻辑：**

1. 对每只股票 × 每个周期，调用 `GapDetector` 检测 `DEFAULT_HISTORY_START` 至今的数据空洞
2. 发现空洞后写入 `data_gaps` 表（`status=open`），幂等（同一空洞不重复写入）
3. 检测结果写入 `logs/check_gaps_YYYYMMDD.log`，同时在终端打印汇总
4. **只检测，不修复**，修复由下次 `sync` 自动完成

**示例：**

```bash
# 检测所有活跃股票的全部周期
./env_quant/bin/python main.py check-gaps

# 仅检测腾讯控股
./env_quant/bin/python main.py check-gaps --stock HK.00700

# 仅检测日K数据
./env_quant/bin/python main.py check-gaps --period 1D

# 检测贵州茅台的日K和周K
./env_quant/bin/python main.py check-gaps --stock SH.600519 --period 1D 1W
```

**终端输出示例：**

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
  Checking US.AAPL   ...  OK (no gaps)

================================================================
  Summary:
    Stocks with gaps : 1 / 3
    Total gaps found : 2
    Persisted to DB  : 2  (data_gaps, status=open)

  Run `python main.py sync` to repair gaps automatically.
================================================================
```

**日志文件：** `logs/check_gaps_YYYYMMDD.log`

---

### `repair` — K 线数据强制修复

```bash
./env_quant/bin/python main.py repair \
    --date <YYYY-MM-DD> \
    [--stock <STOCK_CODE>] \
    [--period 1D [1W] [1M]]
```

**需要富途 OpenD 连接（美股除外：指定 `--stock US.xxx` 时仅需 yfinance）。**

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--date` | `YYYY-MM-DD` | **是** | 目标业务日期 |
| `--stock` | 可选 | 否 | 指定股票代码；不传则修复所有活跃股票 |
| `--period` | 可选，可多选 | 否 | 指定周期；不传则修复全部三个周期 |

**执行逻辑：**

- 对指定日期的 K 线数据，从富途 API 重新拉取后执行 **强制 upsert 覆盖写入**，无论数据库中是否已存在
- 各周期自动映射 fetch 区间（无需用户关心）：
  - `1D`：仅查当天
  - `1W`：查当天所在整周（周一~周日）
  - `1M`：查当天所在整月（1日~月末）
- **不修改 `sync_metadata`**，不影响后续增量同步逻辑

**适用场景：**

- 盘中 sync 因网络中断导致当日数据不完整
- 历史某日数据异常，需强制刷新
- 补录指定日期的半日数据

**示例：**

```bash
# 修复所有股票 2026-03-19 的全部周期数据
./env_quant/bin/python main.py repair --date 2026-03-19

# 修复腾讯控股 2026-03-20 的日K
./env_quant/bin/python main.py repair --date 2026-03-20 --stock HK.00700 --period 1D

# 修复贵州茅台 2026-03-17（周一）所在周的周K
./env_quant/bin/python main.py repair --date 2026-03-17 --stock SH.600519 --period 1W

# 修复苹果 2026-03-01 所在月的月K和日K
./env_quant/bin/python main.py repair --date 2026-03-01 --stock US.AAPL --period 1D 1M
```

**终端输出示例：**

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

---

## 可视化 Web 服务

浏览器打开 `http://localhost:8000`（生产模式）或 `http://localhost:5173`（开发模式）。

### 个股分析页（主页 `/`）

```
顶部控制栏
  ├── 股票选择：按综合信号分组（偏多 / 偏空 / 中性）
  ├── 周期选择：1D / 1W / 1M
  └── 时间范围：近3月 / 近6月 / 近1年 / 近3年 / 自定义

主图区域（K 线蜡烛图）
  ├── 叠加：MA5（黄）/ MA20（蓝）/ MA60（橙）
  ├── 叠加：BOLL 三轨（上轨红虚线 / 中轨灰虚线 / 下轨绿虚线）
  │         上轨以上浅红背景（超买警示）/ 下轨以下浅绿背景（超卖提示）
  └── 底部：成交量柱 + MAVOL5/10 均线

副图面板（各含右上角实时信号标签 + [?] 新手说明浮层）
  ├── MACD：DIF/DEA 曲线 + MACD 柱，金叉 ▲ / 死叉 ▼ 标记
  ├── RSI：曲线 + 70/30 参考线 + 超买（70~100 浅红）/ 超卖（0~30 浅绿）背景
  └── KDJ：K/D/J 三线 + 80/20 参考线 + 超买（80~100 浅红）/ 超卖（0~20 浅绿）背景

导航栏右上角
  └── 系统版本号（如 v0.6.0，与 git tag 保持一致）
```

**信号标签颜色规范（A股红涨绿跌惯例）：**

| 颜色 | 含义 |
|------|------|
| 🔴 红色 | 买入区间（超卖反弹、金叉、多头排列）|
| 🟢 绿色 | 卖出区间（超买回调、死叉、空头排列）|
| ⚖️ 灰色 | 中性观望（信号不明确）|
| 🟠 橙色 | 放量（成交量异常放大）|

> 信号为技术指标机械判断，仅供参考，不构成投资建议。

**交互功能：**

- 鼠标悬停显示当日 OHLCV + 各指标值 + 数据更新时间（Tooltip）
- 各子图时间轴联动，十字线跨图显示，底部滑动条全局联动
- 每 60 秒自动刷新最新数据

### Watchlist 总览页（`/watchlist`）

表格展示所有活跃股票的最新价、涨跌幅、RSI / MACD / KDJ 信号状态和综合信号，点击任意行跳转个股分析页。

**综合信号判断逻辑：**

| 综合信号 | 条件 |
|---------|------|
| 🔴 偏多 | MACD 金叉 且 RSI 在 50~70 且 KDJ 非死叉超买 |
| 🟢 偏空 | MACD 死叉 且 RSI < 50 且 KDJ 非金叉超卖 |
| ⚖️ 中性 | 其余（信号分歧或均处中性区间）|

### Web API

后端 API 文档（Swagger UI）：`http://localhost:8000/docs`

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 服务健康检查（含版本号）|
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

## 定时任务配置

### macOS / 通用 Linux（cron）

`crontab -e` 添加：

```cron
# A股/港股：每个交易日 17:30 同步（收盘后约 1.5 小时）
30 17 * * 1-5 cd /path/to/code_quant && ./env_quant/bin/python main.py >> logs/cron.log 2>&1

# 美股：次日 07:00 同步（固定安全时间，无需区分冬夏令时）
0 7 * * 2-6 cd /path/to/code_quant && ./env_quant/bin/python main.py >> logs/cron.log 2>&1
```

> **美股同步时间说明**：美股收盘时间为北京时间次日 04:00（夏令）/ 05:00（冬令），盘后交易持续至 08:00/09:00。07:00 为固定安全时间，兼容两种时令，Yahoo Finance 此时已处理完前一交易日 EOD 数据，无需每年手动切换。

> **注意**：cron 不继承 shell 环境，务必用虚拟环境的 Python **绝对路径**；macOS 需在「系统设置 → 隐私与安全 → 完全磁盘访问」授权 cron。

### Linux 服务器（systemd）

```bash
cat deploy/README.md   # 查看 systemd 部署指南
```

---

## 局域网访问与 Token 鉴权

默认仅本机访问（`127.0.0.1`）。若需在局域网其他设备访问，在 `.env` 中配置：

```ini
WEB_HOST=0.0.0.0
WEB_ACCESS_TOKEN=your-secret-token
```

启动后，局域网设备访问：

```
http://<服务器IP>:8000/?token=your-secret-token
```

首次通过 token 鉴权后，浏览器会写入 Cookie，后续访问无需再带 token 参数。本机回环地址（`127.0.0.1`）始终豁免鉴权。

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
| `kline_data` | K 线原始数据（未复权，含 pe_ratio / pb_ratio / ps_ratio / updated_at）|
| `adjust_factors` | 复权因子（每次除权事件一条记录）|
| `trading_calendar` | 各市场交易日历 |
| `sync_metadata` | 每只股票每个周期的同步状态与进度 |
| `data_gaps` | 检测到的数据空洞记录（open / filling / filled / failed）|
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
| `WEB_HOST` | `127.0.0.1` | uvicorn 绑定地址；`0.0.0.0` 开放局域网 |
| `WEB_ACCESS_TOKEN` | 空（不鉴权）| 局域网访问 Token，留空则不启用 |
| `YFINANCE_PROXY` | 空（已禁用）| yfinance HTTP 代理地址（已禁用，保留配置）|
| `YFINANCE_REQUEST_INTERVAL` | `0.5` | yfinance 请求最小间隔（已禁用）|
| `YFINANCE_MAX_RETRIES` | `3` | yfinance 请求最大重试次数（已禁用）|
| `TUSHARE_TOKEN` | 空 | TuShare API Token（注册即获120积分试用）|
| `TUSHARE_REQUEST_INTERVAL` | `1.2` | TuShare 请求最小间隔（50次/分钟）|
| `US_STOCK_SOURCE` | `tushare` | 美股数据源：tushare（默认）/ yfinance（已禁用）|
| `APP_VERSION` | `dev` | 系统版本号，前端导航栏展示，与 git tag 保持一致 |
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
├── main.py                  # 入口：数据采集 + 运维子命令
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
│   ├── sync_engine.py       # 历史同步 + 空洞修复编排
│   ├── gap_detector.py      # 基于交易日历的空洞检测
│   └── ...
├── db/                      # 数据库层
│   ├── schema.py            # DDL + init_db()
│   └── repositories/        # 7个 Repository（全部只读供 Web 层调用）
├── futu_wrap/               # 富途 SDK 封装（A股/港股数据源）
├── yfinance_wrap/           # yfinance 封装（已禁用，保留代码）
├── tushare_wrap/            # TuShare 封装（美股数据源）
├── models/                  # 数据模型（Stock / KlineBar / AdjustFactor）
├── config/settings.py       # 配置（从 .env 读取）
├── export/exporter.py       # 数据导出（CSV / Parquet）
├── deploy/                  # systemd 服务配置
│   ├── quant-sync.service   # 数据采集服务（+ 三个市场 timer）
│   ├── quant-web.service    # Web 可视化服务
│   └── README.md            # Linux 服务器部署指南
├── docs/                    # 产品需求和设计文档
├── logs/                    # 日志目录（sync_*.log / check_gaps_*.log）
└── data/quant.db            # SQLite 数据库（不提交仓库）
```

---

## 注意事项

- `watchlist.json` 和 `.env` 含个人配置，已加入 `.gitignore`，**请勿提交仓库**
- 富途 SDK 包名为 `futu`，与项目内 `futu_wrap/` 目录不同，import 时注意：SDK 用 `from futu import ...`，项目模块用相对路径
- Web 层严格只读，不向数据库写入任何数据
- **系统 Python 是 3.9**，必须使用虚拟环境 `./env_quant/bin/python`，勿使用裸 `python`/`pip`/`uvicorn`
- 本系统严禁添加任何交易、下单、报价逻辑

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档 v1](docs/requirements.md) | 迭代1原始需求 |
| [迭代2需求](docs/requirements_iter2.md) | 迭代2 PRD（估值字段/服务化/导出）|
| [迭代3需求](docs/requirements_iter3.md) | 迭代3 PRD（可视化 Web 服务）|
| [迭代4需求](docs/requirements_iter4.md) | 迭代4 PRD（Bug修复/指标说明浮层/迁移工具）|
| [迭代5需求](docs/requirements_iter5.md) | 迭代5 PRD（稳定性加固/局域网鉴权/Tooltip增强）|
| [迭代6需求](docs/requirements_iter6.md) | 迭代6 PRD（版本号/check-gaps/repair）|
| [迭代7需求](docs/requirements_iter7.md) | 迭代7 PRD（crosshair联动/VPA-Defender指标）|
| [迭代8需求](docs/requirements_iter8.md) | 迭代8 PRD（UI对齐/说明浮层/折叠按钮/check-gaps日志）|
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
| 迭代3.5 | ✅ 已完成 | Web 界面优化（综合信号横幅、买卖标记、红涨绿跌配色、跨图联动）|
| 迭代4 | ✅ 已完成 | Bug 修复、指标新手说明浮层、`migrate` 子命令、交易日历修复 |
| 迭代5 | ✅ 已完成（v0.5.1-fix）| upsert 覆盖写、Tooltip 数据更新时间、信号分组下拉、局域网 Token 鉴权 |
| 迭代6 | ✅ 已完成 | 版本号展示（FEAT-version）、`check-gaps` 子命令、`repair` 子命令 |
| 迭代7 | ✅ 已完成 | crosshair 十字线联动优化、VPA-Defender 量价共振防守指标 |
| 迭代0.7.1-patch | ✅ 已完成 | VPA emoji 修复、收盘价曲线、版本号硬编码至代码 |
| 迭代8 | ✅ 已完成 | UI 对齐优化（Y轴）、说明浮层重构、折叠按钮重构、check-gaps 日志增强、VPA 配色修正、说明图标统一 |
| 迭代8.1-patch | ✅ 已完成 | 空仓阻力线指标（FEAT-resistance）、图例按钮化（FEAT-legend-toggle）|
| 迭代8.2-patch | ✅ 已完成 | 图例 icon 缺失修复（bar/line 类型）、图例切换 toggle 联动曲线显隐修复（notMerge→false）|
| 迭代8.3-feat | ✅ 已完成 | 各图表 Y 轴添加名称/单位标识（元/万股/MACD/RSI/KDJ/OBV），RSI formatter 截断修复，VPA 双轴颜色关联，多轴策略规范文档 |
| 迭代8.4-patch | ✅ 已完成 | 空洞检测 BUG 修复：周K/月K日期格式不匹配、sync 修复历史空洞 |
| 迭代8.5-patch | ✅ 已完成 | 临时停市空洞智能验证：引入 `no_data` 状态标记台风等临时停市日期，自动迁移 CHECK 约束 |
| 迭代8.6-patch | ✅ 已完成 | no_data 状态完善：stats 命令显示 no_data 统计，upsert_gaps 注释完善 |
| 迭代8.7-patch | ✅ 已完成 | check-gaps 排除 no_data 空洞 |
| 迭代9 | ✅ 已完成 | yfinance 美股数据源接入、多数据源路由架构、定时同步配置统一 |
| 迭代10 | ✅ 已完成 | TuShare 美股数据源替代 yfinance、复权因子近似计算、前端周K/月K屏蔽 |
