# 迭代9 技术设计文档 — yfinance 美股数据源接入

**文档版本**：v1.0
**日期**：2026-04-11
**关联PRD**：docs/requirements_iter9.md

---

## 一、设计概览

### 1.1 目标

在现有富途数据源基础上，新增 yfinance 作为美股数据源，实现按市场码自动路由的同步架构。

### 1.2 核心设计原则

1. **最小侵入**：不引入抽象基类，不修改 futu_wrap 任何代码
2. **对称设计**：yfinance_wrap 与 futu_wrap 结构对称
3. **路由分层**：SyncEngine 内部按 `stock_code` 前缀路由 Fetcher
4. **现有功能零回归**：A股/港股流程完全不受影响

---

## 二、模块设计

### 2.1 CONFIG — 配置项

**文件**：`config/settings.py`、`.env.example`

新增三个配置项：

```python
# config/settings.py
YFINANCE_PROXY = os.getenv("YFINANCE_PROXY", "")
YFINANCE_REQUEST_INTERVAL = float(os.getenv("YFINANCE_REQUEST_INTERVAL", "0.5"))
YFINANCE_MAX_RETRIES = int(os.getenv("YFINANCE_MAX_RETRIES", "3"))
```

### 2.2 FEAT-yfinance — yfinance_wrap 模块

#### 2.2.1 YFinanceClient（`yfinance_wrap/client.py`）

```
职责：yfinance 连接管理（无需持久连接）
设计要点：
  - 无 connect()/disconnect() 生命周期
  - 管理代理配置（session.proxies）
  - 内置请求间隔控制（time.sleep）
  - 重试逻辑（指数退避）
```

```python
class YFinanceClient:
    def __init__(self):
        self._proxy = YFINANCE_PROXY
        self._request_interval = YFINANCE_REQUEST_INTERVAL
        self._max_retries = YFINANCE_MAX_RETRIES
        self._last_request_time = 0.0

    def _wait_rate_limit(self):
        """请求间隔控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def get_ticker(self, stock_code: str):
        """获取 yfinance Ticker 对象（stock_code 转 yfinance 格式）"""
        # US.AAPL → AAPL
        symbol = stock_code.split(".", 1)[1] if "." in stock_code else stock_code
        ticker = yf.Ticker(symbol)
        if self._proxy:
            # 配置代理 session
            ...
        return ticker

    def download_with_retry(self, **kwargs) -> pd.DataFrame:
        """带重试的 yf.download 调用"""
        ...
```

**stock_code 格式转换**：
- 项目格式：`US.AAPL`（与 watchlist.json 一致）
- yfinance 格式：`AAPL`
- 转换：`stock_code.split(".", 1)[1]`

#### 2.2.2 YFinanceKlineFetcher（`yfinance_wrap/kline_fetcher.py`）

```
接口签名兼容 futu_wrap/kline_fetcher.py 的 KlineFetcher.fetch()
输入：stock_code, period, start_date, end_date
输出：List[KlineBar]
```

```python
class YFinanceKlineFetcher:
    def __init__(self, client: YFinanceClient):
        self._client = client

    def fetch(self, stock_code: str, period: str,
              start_date: str, end_date: str) -> List[KlineBar]:
        self._client._wait_rate_limit()
        # period 映射：1D→1d, 1W→1wk, 1M→1mo
        interval = {"1D": "1d", "1W": "1wk", "1M": "1mo"}[period]
        ticker = self._client.get_ticker(stock_code)
        df = ticker.history(
            start=start_date, end=end_date_plus_one,
            interval=interval, auto_adjust=False
        )
        # 解析 DataFrame → List[KlineBar]
        # 关键：Close 为原始价，Adj Close 用于复权因子
        # turnover=0, pe/pb/ps=None, turnover_rate=None, last_close=None
```

**yfinance history() 返回字段映射**：
- `Open` → `open`
- `High` → `high`
- `Low` → `low`
- `Close` → `close`（原始价，auto_adjust=False）
- `Volume` → `volume`
- `Adj Close` → 仅用于计算复权因子，不写入 kline_data
- `turnover` = 0（yfinance 不提供）
- `pe_ratio/pb_ratio/ps_ratio/turnover_rate/last_close` = None

**日期处理**：
- yfinance `history(start, end)` 的 end 是**不包含**的，需 +1 天
- 时区处理：yfinance 返回的 DatetimeIndex 是 UTC 或 America/New_York，需统一转为 date 字符串

#### 2.2.3 YFinanceAdjustFetcher（`yfinance_wrap/adjust_fetcher.py`）

```
接口签名兼容 futu_wrap/adjust_factor_fetcher.py 的 AdjustFactorFetcher.fetch_factors()
输入：stock_code
输出：List[AdjustFactor]
```

**方案A实现**（从 Adj Close 反推 forward_factor）：

```python
class YFinanceAdjustFetcher:
    def __init__(self, client: YFinanceClient, kline_fetcher: YFinanceKlineFetcher):
        self._client = client
        self._kline_fetcher = kline_fetcher

    def fetch_factors(self, stock_code: str) -> List[AdjustFactor]:
        # 1. 拉取全历史日K（auto_adjust=False），获取 Close 和 Adj Close
        df = ticker.history(start=DEFAULT_HISTORY_START, end=today,
                           interval="1d", auto_adjust=False)
        # 2. 找出 Adj Close / Close ≠ 1.0 的日期（浮点容差 1e-6）
        factors = []
        for date_str, row in df.iterrows():
            ratio = row["Adj Close"] / row["Close"]
            if abs(ratio - 1.0) > 1e-6:
                factors.append(AdjustFactor(
                    stock_code=stock_code,
                    ex_date=date_str.strftime("%Y-%m-%d"),
                    forward_factor=ratio,       # A = Adj Close / Close
                    forward_factor_b=0.0,       # B = 0（方案A不含加法偏移）
                    backward_factor=1.0/ratio,  # 后复权取倒数
                    backward_factor_b=0.0,
                    factor_source="yfinance",
                ))
        return factors
```

**与富途 AdjustFactor 格式的兼容性**：
- 富途：`adj_price = raw_price × A + B`（A 是乘法系数，B 是加法偏移）
- yfinance 方案A：`adj_price = raw_price × A`（B=0）
- 两者公式兼容：AdjustmentService 的 `_calc_forward_multiplier()` 复合公式 `A_new = A × a; B_new = B × a + b` 在 b=0 时退化为 `A_new = A × a; B_new = 0`，完全正确。

**注意事项**：
- yfinance 的 Adj Close 是相对最新日期的前复权价，每次拉取时 Adj Close 可能因新除权事件而变化
- 但我们的 adjust_factors 表使用 `INSERT OR IGNORE`（幂等），已存在的 ex_date 不会更新
- 需要改为 `INSERT OR REPLACE` 或 `upsert` 策略，确保复权因子能更新
- **或者**：每次全量拉取后，删除该股票旧因子再重新插入（更简单、更可靠）

### 2.3 FEAT-multi-source — 数据源路由

**核心改动**：`core/sync_engine.py`、`main.py`

#### SyncEngine 改动

```python
class SyncEngine:
    def __init__(self, ..., yfinance_kline_fetcher=None, yfinance_adjust_fetcher=None):
        # 现有属性保留
        self._kline_fetcher = kline_fetcher                      # FutuKlineFetcher
        self._adjust_factor_fetcher = adjust_factor_fetcher       # FutuAdjustFactorFetcher
        # 新增
        self._yfinance_kline_fetcher = yfinance_kline_fetcher     # YFinanceKlineFetcher
        self._yfinance_adjust_fetcher = yfinance_adjust_fetcher   # YFinanceAdjustFetcher

    def _get_kline_fetcher(self, stock_code: str):
        return self._yfinance_kline_fetcher if stock_code.startswith("US.") else self._kline_fetcher

    def _get_adjust_fetcher(self, stock_code: str):
        return self._yfinance_adjust_fetcher if stock_code.startswith("US.") else self._adjust_factor_fetcher
```

**路由点**：
1. `_fetch_klines_paged()` → `_get_kline_fetcher(stock_code).fetch()`
2. `_refresh_adjust_factors()` → `_get_adjust_fetcher(stock_code).fetch_factors()`
3. `_ensure_calendar()` → 美股路由到 YFinanceCalendarFetcher
4. `repair_one()` → `_get_kline_fetcher(stock_code).fetch()`

**美股跳过逻辑**：
- `_ensure_calendar()`：美股使用 YFinanceCalendarFetcher（见 FEAT-us-calendar）
- `_heal_gaps()`：美股正常执行（依赖 trading_calendar 表，已写入 US 日历）
- 订阅推送：美股不参与 SubscriptionManager（在 main.py 过滤）

#### main.py build_dependencies() 改动

```python
def build_dependencies(futu_client: FutuClient) -> dict:
    # ... 现有代码保留 ...

    # 新增：yfinance 依赖（无条件初始化，不依赖 OpenD 连接）
    yfinance_client = YFinanceClient()
    yfinance_kline_fetcher = YFinanceKlineFetcher(yfinance_client)
    yfinance_adjust_fetcher = YFinanceAdjustFetcher(yfinance_client, yfinance_kline_fetcher)
    yfinance_calendar_fetcher = YFinanceCalendarFetcher()

    # SyncEngine 新增参数
    sync_engine = SyncEngine(
        ...,
        yfinance_kline_fetcher=yfinance_kline_fetcher,
        yfinance_adjust_fetcher=yfinance_adjust_fetcher,
        yfinance_calendar_fetcher=yfinance_calendar_fetcher,
    )
```

### 2.4 FEAT-us-sync — 美股K线增量同步

**核心逻辑**：完全复用 SyncEngine._sync_one() 流程

**路由改造后的自然支持**：
1. `_sync_one()` 读取 `sync_metadata`，确定 start_date → 复用
2. `_fetch_klines_paged()` 路由到 `YFinanceKlineFetcher.fetch()` → 自动
3. `_fetch_and_store()` 写入 `kline_data` 表 → 复用
4. `sync_metadata` 更新 → 复用

**美股同步差异处理**：

| 步骤 | A股/港股 | 美股 |
|------|---------|------|
| 交易日历 | 富途 CalendarFetcher | YFinanceCalendarFetcher |
| 复权因子 | 富途 AdjustFactorFetcher | YFinanceAdjustFetcher |
| K线拉取 | 富途 KlineFetcher（分页） | YFinanceKlineFetcher（单次） |
| 实时推送 | SubscriptionManager | 跳过 |
| 数据验证 | KlineValidator | KlineValidator（复用） |
| 空洞检测 | GapDetector | GapDetector（复用，需 US 日历） |

**yfinance 不需要分页**：
- `_fetch_klines_paged()` 对美股只调用一次 `YFinanceKlineFetcher.fetch()`
- YFinanceKlineFetcher 内部不实现分页，单次返回全量

**美股在 cmd_sync 中的处理**：
- SubscriptionManager.sync_subscriptions() 需过滤掉 US.* 股票
- 已有的 active_stocks 列表包含 US.* 股票，subscription_manager 应只处理 HK/SH/SZ

### 2.5 FEAT-us-adjust — 美股复权因子

**设计**：见 2.2.3 YFinanceAdjustFetcher

**复权因子更新策略**：
- yfinance 的 Adj Close 每次拉取都可能因新除权事件而变化
- 使用 `INSERT OR REPLACE` 替代 `INSERT OR IGNORE`，确保因子能更新
- 新增 `AdjustFactorRepository.upsert_factors()` 方法

**验证方案**：
- 写入后调用 `AdjustmentService.get_adjusted_klines("US.AAPL", "1D", ...)`
- 对比前复权 close 与 yfinance Adj Close，误差应 < 0.1%

### 2.6 FEAT-us-calendar — 美股交易日历

**文件**：`yfinance_wrap/calendar_fetcher.py`

```python
class YFinanceCalendarFetcher:
    """使用 pandas-market-calendars 获取美股交易日历"""

    def fetch(self, market: str, start_date: str, end_date: str) -> List[str]:
        """
        获取 NYSE 交易日列表。
        market 参数为 "US"（与 trading_calendar 表 market 字段一致）。
        """
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar('NYSE')
        schedule = nyse.schedule(start_date=start_date, end_date=end_date)
        trading_days = schedule.index.strftime('%Y-%m-%d').tolist()
        return trading_days
```

**SyncEngine 路由**：
```python
def _ensure_calendar(self, market, start_date, end_date):
    calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market
    if not self._calendar_repo.has_calendar(calendar_market, start_date, end_date):
        # 按市场选择 fetcher
        if calendar_market == "US":
            trading_days = self._yfinance_calendar_fetcher.fetch(calendar_market, start_date, end_date)
        else:
            trading_days = self._general_rate_limiter.execute_with_retry(
                self._calendar_fetcher.fetch, calendar_market, start_date, end_date
            )
        if trading_days:
            self._calendar_repo.insert_many(calendar_market, trading_days)
```

**trading_calendar 表兼容性**：
- 现有 CHECK 约束：`market IN ('HK','US','SH','SZ')`，已包含 'US'
- 无需修改 schema.py

### 2.7 FEAT-us-gap — 美股空洞检测

**GapDetector 适配分析**：

1. `detect_gaps()` 中 `market` 参数：美股股票的 `stock.market` 为 `"US"`（来自 watchlist.json 的 `"market": "US"`）
2. `calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market` → `calendar_market = "US"` → 正确
3. `calendar_repo.get_trading_days("US", ...)` → 已写入 US 日历数据 → 正确

**GapDetector 基本无需改动**，只需验证：
- `_group_consecutive()` 对 US 交易日历工作正常 → 通用逻辑，不受市场影响
- `check-gaps` 子命令：stock.market 字段正确映射 → 验证通过

**SyncEngine.repair_one() 适配**：
- `_fetch_klines_paged()` 已路由 → 自然支持
- `_ensure_calendar()` 已路由 → 自然支持

**cmd_check_gaps 和 cmd_repair 适配**：
- `calendar_market = A_STOCK_CALENDAR_MARKET if stock.market == "A" else stock.market`
- 对 US 股票：`stock.market = "US"` → `calendar_market = "US"` → 正确
- 需确保 `gap_repo` 中美股的 no_data 处理正常

---

## 三、数据库变更

**无需 DDL 变更**：
- `trading_calendar` 表 CHECK 约束已包含 `'US'`
- `adjust_factors` 表无市场限制，`factor_source` 字段可存 `"yfinance"`
- `kline_data` 表无市场限制，`stock_code` 字段可存 `US.AAPL`
- `data_gaps` 表无市场限制

**数据写入**：
- `trading_calendar`：market='US' 的交易日记录
- `kline_data`：stock_code='US.AAPL' 的K线记录
- `adjust_factors`：stock_code='US.AAPL', factor_source='yfinance' 的复权因子
- `sync_metadata`：stock_code='US.AAPL' 的同步状态

---

## 四、依赖变更

**requirements.txt 新增**：
```
yfinance>=0.2.36
pandas-market-calendars>=4.3.0
```

---

## 五、影响文件汇总

| 文件 | 变更类型 | 功能点 |
|------|---------|--------|
| `yfinance_wrap/__init__.py` | 新建 | FEAT-yfinance |
| `yfinance_wrap/client.py` | 新建 | FEAT-yfinance |
| `yfinance_wrap/kline_fetcher.py` | 新建 | FEAT-yfinance, FEAT-us-sync |
| `yfinance_wrap/adjust_fetcher.py` | 新建 | FEAT-yfinance, FEAT-us-adjust |
| `yfinance_wrap/calendar_fetcher.py` | 新建 | FEAT-us-calendar |
| `core/sync_engine.py` | 修改 | FEAT-multi-source, FEAT-us-sync, FEAT-us-adjust, FEAT-us-calendar, FEAT-us-gap |
| `main.py` | 修改 | FEAT-multi-source, FEAT-us-sync, FEAT-us-gap |
| `config/settings.py` | 修改 | CONFIG |
| `.env.example` | 修改 | CONFIG |
| `requirements.txt` | 修改 | FEAT-yfinance, FEAT-us-calendar |
| `db/repositories/adjust_factor_repo.py` | 修改 | FEAT-us-adjust |

**不涉及改动**：
- `futu_wrap/` 所有文件
- `api/` 所有文件
- `web/` 所有文件
- `core/indicator_engine.py`
- `core/adjustment_service.py`
- `db/schema.py`

---

## 六、实现顺序与依赖关系

```
CONFIG (独立)
  ↓
FEAT-yfinance (新建 yfinance_wrap 模块)
  ↓
FEAT-multi-source (SyncEngine 路由 + main.py 依赖组装)
  ↓
FEAT-us-sync (美股增量同步，依赖路由就绪)
  ↓
FEAT-us-adjust (复权因子，依赖 yfinance K线拉取)
  ↓
FEAT-us-calendar (交易日历，依赖 SyncEngine 路由)
  ↓
FEAT-us-gap (空洞检测，依赖日历 + 路由)
```
