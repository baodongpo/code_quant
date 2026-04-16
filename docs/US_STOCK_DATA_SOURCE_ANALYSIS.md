# 美股数据源实现状态分析报告

## 一、配置层关键配置项

### 位置：`config/settings.py` (第 92-97 行)

#### 美股数据源选择配置

```python
# 美股数据源：akshare（默认）
US_STOCK_SOURCE = os.getenv("US_STOCK_SOURCE", "akshare")

# AkShare 美股数据源配置（迭代11新增）
AKSHARE_REQUEST_INTERVAL = float(os.getenv("AKSHARE_REQUEST_INTERVAL", "1.0"))  # 请求间隔（秒）
```

**配置项名称**：
- **`US_STOCK_SOURCE`**：美股数据源选择（目前仅支持 `"akshare"`）
- **`AKSHARE_REQUEST_INTERVAL`**：AkShare 请求间隔（默认 1.0 秒）

**历史配置**（已禁用但保留）：
```python
# 迭代9：yfinance（已禁用）
YFINANCE_PROXY = os.getenv("YFINANCE_PROXY", "")
YFINANCE_REQUEST_INTERVAL = float(os.getenv("YFINANCE_REQUEST_INTERVAL", "0.5"))
YFINANCE_MAX_RETRIES = int(os.getenv("YFINANCE_MAX_RETRIES", "3"))

# 迭代10：TuShare（已禁用）
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_REQUEST_INTERVAL = float(os.getenv("TUSHARE_REQUEST_INTERVAL", "1.2"))
```

---

## 二、三代美股数据源对比

### 2.1 迭代9：yfinance（已禁用）

**位置**：`yfinance_wrap/`

**支持周期**：✅ 日K、周K、月K
- `"1D"` → `"1d"`
- `"1W"` → `"1wk"`
- `"1M"` → `"1mo"`

**实现特点**：
- 使用 `yfinance.Ticker.history()` 获取原始未复权价格 + Adj Close
- 通过 Adj Close / Close 比值计算复权因子
- 支持 429 限频特殊处理（30s/60s/120s 退避）
- 需要处理代理配置（中国需 VPN）

**限频策略**：
```python
_RATE_LIMIT_BACKOFF = [30, 60, 120]  # 429 特殊退避
```

**当前状态**：已禁用（保留代码以供参考）

---

### 2.2 迭代10：TuShare（已禁用）

**位置**：`tushare_wrap/`

**支持周期**：❌ 仅日K
- `"1D"` ✅
- `"1W"` ❌
- `"1M"` ❌

**实现特点**：
- 使用 `pro.us_daily()` 获取日K数据
- 支持前复权（返回已复权价格）
- 需要 Token（120积分试用用户限制 50次/分钟、8000次/天）
- 提供估值指标（PE、PB、PS）

**关键代码**：
```python
# tushare_wrap/kline_fetcher.py
SUPPORTED_PERIODS = ["1D"]  # 仅支持日K

# 美股交易日历使用 pandas-market-calendars（不依赖 TuShare Token）
class TuShareCalendarFetcher:
    def fetch(self, market: str, start_date: str, end_date: str) -> List[str]:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        schedule = nyse.schedule(start_date=start_date, end_date=end_date)
```

**当前状态**：已禁用（保留代码以供参考）

---

### 2.3 迭代11：AkShare（当前主数据源）✅ ACTIVE

**位置**：`akshare_wrap/`

**支持周期**：❌ 仅日K
- `"1D"` ✅
- `"1W"` ❌
- `"1M"` ❌

**实现特点**：
- 使用 `ak.stock_us_daily()` 获取美股历史K线
- 数据源：东方财富（已前复权，无需单独复权因子）
- **无需 Token，完全免费**
- 内置反爬机制（HTTP 403/429）

**限频策略**：
```python
# akshare_wrap/client.py
RATE_LIMITS = [(30, 60)]  # 30次/60秒
_request_interval = 1.0    # 默认 1 秒间隔 + 0-0.5 秒随机抖动
```

**关键代码**：
```python
# akshare_wrap/kline_fetcher.py
SUPPORTED_PERIODS = ["1D"]

def fetch(self, stock_code: str, period: str, start_date: str, end_date: str) -> List[KlineBar]:
    if period not in self.SUPPORTED_PERIODS:
        raise ValueError(f"AkShare US stock only supports daily K-line.")
    
    import akshare as ak
    df = ak.stock_us_daily(
        symbol=symbol,
        adjust="qfq",  # 前复权
    )
```

**数据特点**：
- 返回前复权（qfq）价格，无需单独复权计算
- 复权因子记录为基准值 1.0（示意已复权）

**当前状态**：✅ 生产级别（迭代11）

---

## 三、富途对美股的支持分析

### 位置：`futu_wrap/kline_fetcher.py`

富途通过 OpenD 接口支持美股 K 线，使用统一的 `request_history_kline()` 方法。

**周期映射**（FutuClient 内部）：
```python
_PERIOD_MAP = {
    "1D": KLType.K_DAY,
    "1W": KLType.K_WEEK,
    "1M": KLType.K_MON,
}
```

**富途支持的美股接口**：
1. **K 线接口**（`request_history_kline`）
   - 支持日K、周K、月K
   - 原始未复权数据
   - 分页支持（每页1000条）
   
2. **交易日历接口**（`request_trading_days`）
   - 支持 US 市场查询
   - 映射：`Market.US → TradeDateMarket.US`

3. **复权因子接口**（`request_ex_div_info`）
   - 用于计算前复权/后复权系数

**关键代码**：
```python
# futu_wrap/calendar_fetcher.py
_MARKET_MAP = {
    "HK": TradeDateMarket.HK,
    "US": TradeDateMarket.US,    # ✅ 支持美股
    "SH": TradeDateMarket.CN,
    "SZ": TradeDateMarket.CN,
    "A":  TradeDateMarket.CN,
}
```

**美股在富途的现状**：
- ✅ 理论上支持日K/周K/月K
- ⚠️ 但在当前系统中**完全被 AkShare 替代**（见 sync_engine.py 第 266-268 行）
- ⚠️ 需要富途 OpenD 连接才能使用
- ✅ 交易日历支持

---

## 四、多数据源路由逻辑

### 位置：`core/sync_engine.py` (第 266-289 行)

```python
# 迭代11：美股使用 AkShare（K线已前复权，无需单独拉复权因子）
# 富途流程不变：先刷新复权因子再拉K线
is_us_stock = stock_code.startswith("US.") and self._akshare_kline_fetcher is not None

if not is_us_stock:
    # 4a. 富途：先刷新复权因子（使用通用限频器，仅追加新事件）
    self._refresh_adjust_factors(stock_code)

# 5. 拉取增量数据
rows_fetched, rows_inserted = self._fetch_and_store(
    stock, period, fetch_start, today,
    latest_date=_latest_date_arg
)

# 迭代11：AkShare 返回前复权数据，无需单独拉取复权因子
# 无需存储复权因子，因为 AkShare 返回的数据已是前复权价格
```

**K 线获取路由**（第 682-689 行）：
```python
def _get_kline_fetcher(self, stock_code: str):
    """按市场码返回对应的 K线 Fetcher。
    
    迭代11：美股使用 AkShare（支持日K前复权），其他使用富途。
    """
    if stock_code.startswith("US.") and self._akshare_kline_fetcher is not None:
        return self._akshare_kline_fetcher
    return self._kline_fetcher  # 富途
```

**路由决策树**：
```
stock_code 以 "US." 开头？
├─ YES + AkShare 已初始化 → 使用 AkShareKlineFetcher（日K前复权）
└─ NO 或 AkShare 未初始化 → 使用富途 KlineFetcher
```

**美股日历获取**（第 303-330 行）：
```python
def _ensure_calendar(self, market: str, start_date: str, end_date: str) -> None:
    calendar_market = A_STOCK_CALENDAR_MARKET if market == "A" else market
    
    # 迭代11：美股使用 TuShareCalendarFetcher（pandas-market-calendars NYSE）
    if calendar_market == "US" and self._tushare_calendar_fetcher is not None:
        trading_days = self._tushare_calendar_fetcher.fetch(
            calendar_market, start_date, end_date
        )
    else:
        # 其他市场使用富途
        trading_days = self._general_rate_limiter.execute_with_retry(
            self._calendar_fetcher.fetch,
            calendar_market, start_date, end_date
        )
```

---

## 五、前端周期过滤

### 位置：`web/src/components/PeriodSelector.jsx`（第 14-17 行）

```jsx
export default function PeriodSelector({ value, onChange, stockCode }) {
  // 美股仅支持日K，过滤掉周K和月K
  const isUS = stockCode?.startsWith('US.')
  const periods = isUS ? PERIODS.filter(p => p.value === '1D') : PERIODS
  
  // ... 渲染逻辑
}
```

**过滤位置**：
- **前端屏蔽位置**：`PeriodSelector` 组件
- **屏蔽方式**：客户端判断股票代码是否为美股（`US.*`），动态过滤周期列表
- **过滤逻辑**：美股只显示 `1D`，其他市场显示 `1D/1W/1M`

**完整期货列表定义**（第 8-12 行）：
```jsx
const PERIODS = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
]
```

---

## 六、数据源初始化流程

### 位置：`main.py` (build_dependencies 函数，第 102-199 行)

```python
def build_dependencies(
    futu_client: FutuClient = None,
    enable_akshare: bool = False,  # 关键开关
) -> dict:
    # ...
    
    # AkShare 美股数据源（迭代11）
    akshare_kline_fetcher = None
    tushare_calendar_fetcher = None
    if enable_akshare:
        from akshare_wrap import AkShareClient, AkShareKlineFetcher
        from tushare_wrap import TuShareCalendarFetcher
        
        ak_client = AkShareClient(request_interval=AKSHARE_REQUEST_INTERVAL)
        akshare_kline_fetcher = AkShareKlineFetcher(ak_client)
        tushare_calendar_fetcher = TuShareCalendarFetcher()
        logger.info("AkShare data source enabled (request_interval=%.1fs)",
                   AKSHARE_REQUEST_INTERVAL)
    
    # TuShare 美股数据源（迭代10，已禁用）
    tushare_kline_fetcher = None
    tushare_adjust_fetcher = None
    
    # yfinance 美股数据源（迭代9，已禁用）
    yfinance_kline_fetcher = None
    yfinance_adjust_fetcher = None
    yfinance_calendar_fetcher = None
    
    # 传入 SyncEngine
    sync_engine = SyncEngine(
        # ...
        akshare_kline_fetcher=akshare_kline_fetcher,
        tushare_calendar_fetcher=tushare_calendar_fetcher,
    )
```

**AkShare 初始化触发条件**（第 238-248 行）：
```python
def _run_sync_once(
    futu_client: FutuClient,
    logger: logging.Logger,
    enable_akshare: bool = False,
) -> bool:
    deps = build_dependencies(futu_client, enable_akshare=enable_akshare)
```

**调用触发点**（第 367 行）：
```python
_run_sync_once(futu_client, logger, enable_akshare=has_us)
```

其中 `has_us` 由 `_has_us_stocks()` 判定（第 221-235 行）

---

## 七、美股支持的周期列表

### 当前生产状态

```python
# 在 AkShare 下
支持周期：["1D"]

# 在 yfinance 下（已禁用）
支持周期：["1D", "1W", "1M"]

# 在 TuShare 下（已禁用）  
支持周期：["1D"]

# 在富途下（被 AkShare 替代）
支持周期：["1D", "1W", "1M"]
```

### 系统级配置源

```python
# config/settings.py
from models.enums import Period
ALL_PERIODS = [p.value for p in Period]  # ["1D", "1W", "1M"]
```

但在前端（PeriodSelector）会**动态过滤美股为仅日K**。

---

## 八、数据源能力对比矩阵

| 功能 | yfinance | TuShare | AkShare | 富途 |
|------|----------|---------|---------|------|
| **日K** | ✅ | ✅ | ✅ | ✅ |
| **周K** | ✅ | ❌ | ❌ | ✅ |
| **月K** | ✅ | ❌ | ❌ | ✅ |
| **无需 Token** | ✅ | ❌ | ✅ | ❌ |
| **前复权支持** | ✅ (Adj Close) | ✅ | ✅ | ✅ |
| **限频强度** | 严格（需 VPN） | 中等 | 宽松 | 中等 |
| **当前状态** | 已禁用 | 已禁用 | ✅ 生产 | 被替代 |

---

## 九、历史迭代路线

```
迭代9（yfinance）
  ├─ 支持日周月K
  ├─ 需要 VPN（中国）
  └─ 高频限制（429）

    ↓ 问题：稳定性不足、易被限

迭代10（TuShare）
  ├─ 支持仅日K
  ├─ 需要 Token（50次/分钟）
  ├─ 提供估值指标
  └─ 成本：120积分试用

    ↓ 问题：成本、功能受限

迭代11（AkShare）✅ CURRENT
  ├─ 支持仅日K
  ├─ 无需 Token（免费）
  ├─ 数据源：东方财富
  ├─ 前复权内置（adjust='qfq'）
  └─ 限频：30次/60秒
```

---

## 十、关键发现总结

### ✅ 当前架构优点

1. **多源支持**：虽然生产级别仅 AkShare，但保留了 yfinance/TuShare 代码供参考
2. **灵活路由**：`_get_kline_fetcher()` 动态选择数据源
3. **前端智能过滤**：美股自动隐藏周K/月K，避免用户误操作
4. **成本优化**：AkShare 完全免费，无需额外付费

### ⚠️ 当前限制

1. **美股仅日K**：AkShare 不支持周K/月K（前复权已内置，但粒度受限）
2. **富途被闲置**：美股完全转向 AkShare，富途的周K/月K 能力未启用
3. **未来扩展空间**：若要支持美股周K/月K，需要：
   - 方案A：切换到 yfinance（需 VPN）
   - 方案B：启用富途美股接口（需要 OpenD 连接）
   - 方案C：寻找其他免费数据源

### 🔧 配置扩展建议

若要在迭代12支持美股周K/月K，建议在 `config/settings.py` 中添加：

```python
# 美股数据源选择
US_STOCK_KLINE_SOURCE = os.getenv("US_STOCK_KLINE_SOURCE", "akshare")  # akshare|yfinance|futu

# 按周期区分数据源（高级配置）
US_STOCK_SOURCES_BY_PERIOD = {
    "1D": "akshare",    # 日K：免费稳定
    "1W": "futu",       # 周K：富途支持
    "1M": "futu",       # 月K：富途支持
}
```

---

## 十一、下一步迭代建议

### 短期（迭代12）：扩展美股周K/月K

1. **激活富途美股周K/月K**
   - 在 `sync_engine.py` 中添加条件：仅日K 走 AkShare，周K/月K 走富途
   - 修改 `_get_kline_fetcher()` 逻辑
   - 前端对美股 US.* 不再完全隐藏周K/月K

2. **修改前端 PeriodSelector**
   ```jsx
   const isUS = stockCode?.startsWith('US.')
   const periods = isUS 
     ? PERIODS.filter(p => ['1D', '1W', '1M'].includes(p.value))  // 启用全部
     : PERIODS
   ```

3. **数据源优先级配置**
   ```python
   # config/settings.py
   US_STOCK_SOURCES_BY_PERIOD = {
       "1D": "akshare",
       "1W": "futu",
       "1M": "futu",
   }
   ```

### 中期（迭代13）：备用美股数据源管理

1. **实现多源降级**：如 AkShare 不可用，自动降级到 yfinance
2. **添加数据源健康检查**：定期检测各数据源可用性
3. **美股数据源优化**：评估其他免费 API（如 polygon.io 免费层）

