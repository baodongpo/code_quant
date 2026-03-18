# AI 量化辅助决策系统 - 数据源子系统需求文档（迭代2）

**版本**: v2.0
**日期**: 2026-03-18
**范围**: 服务化增强、估值字段扩充、实时订阅启用、数据导出接口
**前置**: 迭代1（requirements.md v1.0）已完成并验收通过

---

## 1. 迭代2目标

**主题：从跑批工具到可服务化的数据平台**

| 迭代 | 目标 |
|------|------|
| 迭代1 | 能跑、能采数据（基础采集能力） |
| **迭代2** | **能持续运行、能对外提供数据、能在服务器上无人值守长期服务** |
| 迭代3 | 与量化算法联动，补充基本面数据（待规划）|

---

## 2. 功能需求

### 模块A：数据字段增强

#### A1. PB 市净率字段（变更）

- `kline_data` 表新增 `pb_ratio REAL` 字段（仅日K，周K/月K 存 NULL）
- `KlineBar` dataclass 增加 `pb_ratio: Optional[float] = None`
- `KlineFetcher` 补充字段映射（富途 `get_history_kline` 已提供 `pb_ratio`）
- `KlineValidator` 增加 PB 合理性校验（`pb_ratio > 0` 或 NULL）
- 实时推送路径（`KlinePushHandler`）同步支持新字段

#### A2. PS 市销率字段（新增，与 A1 捆绑实施）

- `kline_data` 表新增 `ps_ratio REAL` 字段（仅日K，周K/月K 存 NULL）
- `KlineBar` dataclass 增加 `ps_ratio: Optional[float] = None`
- `KlineFetcher` 补充字段映射（富途 `get_history_kline` 已提供 `ps_ratio`）
- `KlineValidator` 增加 PS 合理性校验（`ps_ratio > 0` 或 NULL）

**业务价值**：
- PE + PB 构成 A 股价值投资最高频的估值双因子（格雷厄姆条件）
- 银行股、地产股 PE 普遍失真，PB 是核心估值指标
- 科技股、亏损成长股 PE/PB 意义有限，PS 是最常用补充
- 三指标覆盖后，估值因子支持覆盖率从当前 30% 提升至行业标准水平

---

### 模块B：实时订阅真正启用

#### 背景

迭代1代码中 `KlinePushHandler` 和 `setup_push_handler()` 均已实现，但因跑批模式设计，`sync_subscriptions()` 当前逻辑为**取消所有订阅**，且 `setup_push_handler()` 从未被调用。迭代2需真正激活此能力。

#### B1. `sync_subscriptions()` 逻辑反转（变更）

- 原逻辑：取消所有订阅（释放额度）
- 新逻辑：
  - 对 `active_stocks` 中的每只股票建立实时K线订阅
  - 对不在 `active_stocks` 中的已订阅股票取消订阅
  - 超出 `MAX_SUBSCRIPTIONS` 上限时按 watchlist 顺序优先订阅，超出部分记录 WARNING

#### B2. `setup_push_handler()` 注册（变更）

- `main.py` 中在 `sync_subscriptions()` 调用前，先调用 `subscription_manager.setup_push_handler()`
- 将 `KlinePushHandler` 注册到 OpenQuoteContext，激活推送回调

#### B3. 主进程常驻事件循环（变更）

- 历史同步完成后，主进程不退出，进入等待循环持续接收推送
- 等待循环：每 60 秒检查一次连接健康状态，更新 `data/health.json`
- 支持 SIGTERM 和 SIGINT 优雅退出（完成当前写入后再断开）

#### B4. OpenD 断线重连机制（新增）

- 常驻进程检测 OpenD 连接状态（通过心跳或错误捕获）
- 断线后指数退避重连：30s → 60s → 120s，最多重试 5 次
- 重连成功后自动重新注册 `KlinePushHandler` 并恢复订阅
- 超过最大重试次数后写入 ERROR 日志并触发系统告警（写入 `data/health.json` 的 `status: error`）

#### B5. 推送字段映射更新（变更，依赖 A1/A2）

- `KlinePushHandler._handle()` 解析逻辑同步支持 `pb_ratio`、`ps_ratio` 字段

---

### 模块C：服务化部署能力

#### C1. SIGTERM 优雅退出（变更）

- `main.py` 注册 `signal.signal(signal.SIGTERM, ...)` handler
- 收到 SIGTERM 时：设置退出标志 → 等待当前 K 线写入完成 → 断开 OpenD 连接 → 正常退出
- 确保 `systemctl stop quant-sync` 不会强杀进程

#### C2. 启动恢复逻辑（新增）

针对宕机场景，启动时自动恢复：

```
SyncEngine.run_full_sync() 执行前：
  1. 查询 sync_metadata WHERE sync_status = 'running'
  2. 将这些记录重置为 'pending'（清理脏状态）
  3. 本次同步时对这些股票强制执行空洞检测
     （等同 is_reactivated=True 的处理路径）
```

说明：迭代1已实现 `last_sync_date` 续传、`data_gaps` 空洞修复、`failed→open` 重试，迭代2仅补充 RUNNING 脏状态清理这一环节，即可覆盖全部宕机场景。

#### C3. systemd service 配置模板（新增）

新增 `deploy/quant-sync.service`：

```ini
[Unit]
Description=AI Quant Data Subsystem
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/code_quant
ExecStart=/path/to/env_quant/bin/python main.py
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### C4. systemd timer 定时触发配置（新增）

新增 `deploy/quant-sync-*.timer`，按市场精细触发：

| Timer 文件 | 触发时间（北京时间）| 覆盖市场 | 说明 |
|-----------|----------------|---------|------|
| `quant-sync-a.timer` | 每个工作日 16:30 | A股（SH/SZ）| 收盘后 30 分钟 |
| `quant-sync-hk.timer` | 每个工作日 17:30 | 港股（HK）| 收盘后 30 分钟 |
| `quant-sync-us.timer` | 每日 07:00 | 美股（US）| 美东时间前日收盘后次日早晨 |

> 非交易日 timer 仍触发，`SyncEngine` 检测 `start_date > today` 自然跳过，无副作用。

#### C5. 健康检查文件输出（新增）

每次同步完成及常驻等待循环中定期写入 `data/health.json`：

```json
{
  "status": "running",
  "start_time": "2026-03-18T08:00:00",
  "last_sync_time": "2026-03-18T16:35:42",
  "last_sync_status": "success",
  "active_stocks": 10,
  "subscribed_stocks": 10,
  "db_path": "data/quant.db"
}
```

status 枚举：`running`（正常）/ `syncing`（同步中）/ `reconnecting`（重连中）/ `error`（故障）

---

### 模块D：数据导出接口

#### D1. 导出核心逻辑（新增）

新增 `export/exporter.py`，提供：

```python
export_klines(
    stock_code: str,
    period: str,          # "1D" / "1W" / "1M"
    start_date: str,      # "YYYY-MM-DD"
    end_date: str,        # "YYYY-MM-DD"
    adj_type: str,        # "qfq"（前复权）/ "raw"（原始）
    format: str,          # "parquet"（默认）/ "csv"
    output_dir: str,      # 默认读取 settings.EXPORT_DIR
) -> str                  # 返回输出文件路径
```

输出文件命名规范：`{stock_code}_{period}_{start}_{end}_{adj_type}.{ext}`
例：`SH.600519_1D_2024-01-01_2024-12-31_qfq.parquet`

#### D2. 格式支持

**Parquet（默认，推荐）**：
- 依赖 `pyarrow`（pandas 量化环境通常已有）
- 列式存储，压缩比约为 CSV 的 1/10
- 列类型自动保留，`pd.read_parquet()` 开箱即用
- 适合生产算法使用

**CSV（调试选项）**：
- 无额外依赖
- 含表头，`index=False`
- 适合 Excel 查看、快速验证

#### D3. 命令行接入（新增）

`main.py` 支持 `export` 子命令：

```bash
# 导出前复权日K，Parquet 格式
python main.py export --code SH.600519 --period 1D \
  --start 2024-01-01 --end 2024-12-31 \
  --adj qfq --format parquet

# 导出原始价格，CSV 格式
python main.py export --code HK.00700 --period 1D \
  --start 2024-01-01 --end 2024-12-31 \
  --adj raw --format csv
```

#### D4. 配置

`.env.example` 新增：

```
EXPORT_DIR=exports/   # 数据导出目录，默认 exports/
```

---

### 模块E：工程体验优化

#### E1. 启动时同步预估耗时日志（变更）

- `SyncEngine.run_full_sync()` 开始前，根据 `active_stocks × periods` 计算总请求数
- 结合 `RateLimiter` 参数（0.5s 间隔 / 25次/30s）估算最短耗时
- 输出日志示例：`预计同步请求数: 90，最短耗时约 45 秒`
- 同步进行中输出进度：`[3/10] Syncing HK.00700 ...`（迭代1已有 `[idx/total]` 格式，保持）

#### E2. Watchlist 超限 WARNING（变更）

- `WatchlistManager.load()` 中检查：`len(active_stocks) >= MAX_SUBSCRIPTIONS * 0.8`
- 超过阈值（默认 80 只）时输出 WARNING：`活跃股票数 (85) 已接近订阅上限 (100)，建议减少 watchlist`
- `watchlist.json.example` 注释中补充说明建议活跃股票不超过 90 只

#### E3. `stats` 存储监控命令（新增）

新增 `python main.py stats` 命令，输出示例：

```
=== 数据统计 ===
数据库：data/quant.db（128.5 MB）
活跃股票：10 只

股票代码        1D行数   最老日期     最新日期     同步状态
SH.600519      6245    2000-01-04   2026-03-17   success
HK.00700       5890    2004-06-16   2026-03-17   success
US.AAPL        6520    2000-01-03   2026-03-17   success
...

未填补空洞：2 条
```

---

## 3. 触发机制设计（双轨并行）

### 3.1 主保障：定时触发增量同步

| 触发时间（北京时间）| 覆盖市场 | 触发文件 |
|----------------|---------|---------|
| 每个工作日 16:30 | A股（SH/SZ）| `quant-sync-a.timer` |
| 每个工作日 17:30 | 港股（HK）| `quant-sync-hk.timer` |
| 每日 07:00 | 美股（US）| `quant-sync-us.timer` |

**特点**：数据完整性唯一可靠保障；每次独立执行，失败不影响下次；宕机后重启自动补齐缺口。

### 3.2 辅增强：实时订阅推送

常驻进程运行期间，活跃股票的当日K线随富途 OpenD 推送实时写入。

**特点**：盘中行情分钟级更新；进程在线则有，宕机则无；宕机后盘中数据缺口由下次定时触发补齐。

### 3.3 两者协作关系

```
写入幂等性保障（无数据冲突）：
  实时推送：INSERT OR REPLACE（保证当日最新 bar）
  定时拉取：INSERT OR IGNORE（不覆盖已有数据）
```

---

## 4. 宕机恢复能力

| 宕机场景 | 恢复机制 |
|---------|---------|
| 主拉取进行中宕机 | `last_sync_date` 未更新，重启后从上次成功日期续拉 ✅ |
| 主拉取完成、空洞检测前宕机 | 启动时清理 RUNNING 脏状态，强制空洞检测（迭代2新增）✅ |
| 实时推送期间宕机 | 盘中数据缺口由下次定时触发补齐 ✅ |
| 连续多日宕机 | `last_sync_date` 驱动，重启后拉取所有缺失日期 ✅ |
| 空洞修复失败后宕机 | `data_gaps.status = 'failed'` 下次自动重置为 `'open'` 重试 ✅ |

---

## 5. 算法支持矩阵（更新）

| 算法类型 | 所需数据 | 满足情况 |
|---------|---------|---------|
| 技术分析（MA/MACD/RSI/KDJ/布林带）| OHLCV | ✅ 满足 |
| 量价因子（成交量异动、换手率）| volume, turnover, turnover_rate | ✅ 满足 |
| 动量/反转因子 | close, last_close | ✅ 满足 |
| 估值因子（PE + PB + PS）| pe_ratio, pb_ratio, ps_ratio（仅日K）| ✅ **迭代2补全** |
| 基本面因子（ROE/营收增速）| 财务数据 | ❌ 迭代3规划 |
| 复权后价格序列 | 原始价格 + 复权因子 | ✅ 动态转换 |
| 算法离线运行 | Parquet 导出 | ✅ **迭代2新增** |

---

## 6. 非功能需求（新增/变更）

| 项目 | 迭代1 | 迭代2变更 |
|------|-------|---------|
| 运行模式 | 跑批（手动执行）| 常驻进程 + 定时触发双模式 |
| 进程管理 | 无 | systemd service，崩溃自动重启 |
| 定时触发 | 无 | systemd timer，三市场独立时间点 |
| 宕机恢复 | 部分（续传已有）| 完整（RUNNING 脏状态清理 + 空洞检测）|
| 健康检查 | 无 | `data/health.json` 实时写入 |
| 数据导出 | 无 | Parquet（默认）/ CSV，支持复权选项 |
| 断线处理 | 无 | 指数退避重连（最多 5 次）|

---

## 7. 配置项（新增）

`.env.example` 新增：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EXPORT_DIR` | `exports/` | 数据导出目录 |
| `RECONNECT_MAX_RETRIES` | `5` | OpenD 断线最大重连次数 |
| `RECONNECT_BASE_INTERVAL` | `30` | 断线重连基础间隔（秒，指数退避）|
| `HEALTH_CHECK_INTERVAL` | `60` | 健康检查文件写入间隔（秒）|

---

## 8. 验收标准

### 迭代2新增验收项

1. **估值字段**：`kline_data` 表包含 `pb_ratio`、`ps_ratio` 字段；日K数据正常写入，周K/月K 值为 NULL
2. **实时订阅**：启动后 `subscription_status` 表显示活跃股票已订阅，日志出现 `Subscribed HK.XXXXX [1D]`
3. **推送写入**：交易日盘中，推送回调触发，日志出现 `KlinePush upserted N bars`，`kline_data` 当日数据更新
4. **服务化**：`systemctl start quant-sync` 可正常启动；`systemctl stop quant-sync` 优雅退出（日志出现 `Disconnected from OpenD`）
5. **崩溃重启**：强制 kill 进程后，systemd 在 30 秒内自动重启，日志显示恢复逻辑执行
6. **宕机恢复**：手动制造 `sync_status = 'running'` 的脏数据，重启后日志显示清理并触发空洞检测
7. **健康检查**：`data/health.json` 存在，`last_sync_time` 为当日，`status` 为 `running`
8. **定时触发**：配置 systemd timer 后，在指定时间点验证自动触发并完成增量同步
9. **数据导出（Parquet）**：
   ```bash
   python main.py export --code SH.600519 --period 1D \
     --adj qfq --format parquet
   ```
   生成正确 Parquet 文件，`pd.read_parquet()` 读入后 `close` 列为前复权价格，列类型正确
10. **数据导出（CSV）**：同上，`--format csv` 生成可用 Excel 打开的标准 CSV
11. **存储监控**：`python main.py stats` 正确输出各股票行数、日期范围、DB 文件大小
12. **Watchlist 警告**：活跃股票超过 80 只时，启动日志出现 WARNING 提示

### 沿用迭代1验收标准

迭代1全部验收标准继续有效（参见 `requirements.md §6`）。

---

## 9. 不在本迭代范围

- 基本面数据（ROE / 营收增速）：迭代3与量化算法联动时规划
- 备用数据源（AKShare/TuShare）：迭代3 P3 功能
- 数据归档/清理策略：迭代3 P3 功能
- 周K/月K 与富途 App 精确对齐验证：联调过程中持续验证，发现偏差即时修复（不单独立项）

---

*文档由 PM 输出，版本 v2.0，2026-03-18*
