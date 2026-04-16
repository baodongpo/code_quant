# 美股数据源快速参考

## 📋 关键配置项速查

| 配置项 | 位置 | 默认值 | 说明 |
|------|------|--------|------|
| `US_STOCK_SOURCE` | `config/settings.py:97` | `"akshare"` | 美股数据源选择（当前仅支持akshare） |
| `AKSHARE_REQUEST_INTERVAL` | `config/settings.py:94` | `1.0` | AkShare请求间隔（秒） |
| `YFINANCE_PROXY` | `config/settings.py:81` | `""` | yfinance代理地址（已禁用） |
| `TUSHARE_TOKEN` | `config/settings.py:88` | `""` | TuShare API Token（已禁用） |

---

## 🔄 数据源路由决策

### K线获取流程

```
sync_engine._fetch_klines_paged(stock_code, period, start, end)
  │
  ├─→ _get_kline_fetcher(stock_code)
  │    │
  │    ├─ stock_code.startswith("US.") && AkShare已初始化?
  │    │  ├─ YES → AkShareKlineFetcher (仅1D)
  │    │  └─ NO  → FutuKlineFetcher (1D/1W/1M)
  │    │
  │
  └─→ fetcher.fetch(stock_code, period, start, end)
```

### 日历获取流程

```
sync_engine._ensure_calendar(market, start_date, end_date)
  │
  ├─ market == "US" && TuShareCalendarFetcher已初始化?
  │  ├─ YES → TuShareCalendarFetcher (pandas-market-calendars NYSE)
  │  └─ NO  → FutuCalendarFetcher
```

### 复权因子获取流程

```
sync_engine._refresh_adjust_factors(stock_code)
  │
  ├─ stock_code.startswith("US.") && AkShare已初始化?
  │  ├─ YES → 跳过（AkShare返回前复权价格）
  │  └─ NO  → FutuAdjustFactorFetcher
```

---

## 🎯 各数据源代码位置速查

### 文件结构

```
.
├── akshare_wrap/              ← 迭代11（当前）✅
│   ├── __init__.py           (导出接口)
│   ├── client.py             (限频管理、反爬处理)
│   └── kline_fetcher.py      (日K获取，前复权内置)
│
├── tushare_wrap/              ← 迭代10（已禁用）
│   ├── __init__.py           (导出接口)
│   ├── client.py
│   ├── kline_fetcher.py      (仅日K)
│   ├── adjust_fetcher.py
│   ├── calendar_fetcher.py   (NYSE日历，不需Token)
│   └── subscription_manager.py
│
├── yfinance_wrap/             ← 迭代9（已禁用）
│   ├── __init__.py           (导出接口)
│   ├── client.py
│   ├── kline_fetcher.py      (日K/周K/月K)
│   ├── adjust_fetcher.py     (复权因子计算)
│   └── calendar_fetcher.py
│
├── futu_wrap/                 ← 富途（被US替代）
│   ├── kline_fetcher.py      (日K/周K/月K，未复权)
│   ├── calendar_fetcher.py   (支持US市场)
│   ├── adjust_factor_fetcher.py
│   └── subscription_manager.py
│
├── config/settings.py         ← 配置汇总
├── core/sync_engine.py        ← 路由逻辑核心
└── web/src/components/
    └── PeriodSelector.jsx     ← 前端周K/月K过滤
```

---

## 🚀 AkShare 限频详解

### 限频规则

```python
# akshare_wrap/client.py
RATE_LIMITS = [(30, 60)]  # 30次/60秒（内置限制）
_request_interval = 1.0   # 基础间隔1秒 + 随机抖动0-0.5秒
```

### 等待流程

```python
def wait_rate_limit():
    # 1. 固定间隔 + 随机抖动
    elapsed = time.time() - last_request_time
    jitter = random.uniform(0, 0.5)
    wait_time = request_interval - elapsed + jitter
    if wait_time > 0:
        sleep(wait_time)
    
    # 2. 滑动窗口检查
    # 清除60秒前的记录
    while oldest_timestamp < (now - 60):
        remove_oldest()
    
    # 检查当前窗口内是否超过30次
    if len(request_timestamps) >= 30:
        # 等待最早记录过期
        wait = oldest + 60 - now + 0.1
        if wait > 0:
            sleep(wait)
    
    # 3. 记录本次请求
    request_timestamps.append(now)
```

### 反爬判断

```python
def is_rate_limit_error(error):
    # 识别 403/429/rate limit/forbidden/too many
    return any(keyword in str(error).lower() for keyword in [
        "403", "429", "rate limit", "forbidden", "too many"
    ])
```

---

## 📊 支持矩阵 - 细节版

### 周期支持

```python
# 迭代11（当前）
AkShare:
  - 1D: ✅ stock_us_daily (前复权)
  - 1W: ❌ 无接口
  - 1M: ❌ 无接口

# 迭代10（可参考）
TuShare:
  - 1D: ✅ pro.us_daily()
  - 1W: ❌ 无接口
  - 1M: ❌ 无接口

# 迭代9（可参考）
yfinance:
  - 1D: ✅ interval='1d'
  - 1W: ✅ interval='1wk'
  - 1M: ✅ interval='1mo'

# 富途（被替代但能力健全）
Futu:
  - 1D: ✅ KLType.K_DAY
  - 1W: ✅ KLType.K_WEEK
  - 1M: ✅ KLType.K_MON
```

### 代码框架

```python
# 数据源代码结构对称（可复用）
class YFinanceKlineFetcher:
    def fetch(stock_code, period, start_date, end_date) -> List[KlineBar]
    def fetch_and_extract_adj_close(...) -> Tuple[List[KlineBar], dict]

class TuShareKlineFetcher:
    def fetch(stock_code, period, start_date, end_date) -> List[KlineBar]
    @staticmethod
    def _parse_dataframe(stock_code, period, df) -> List[KlineBar]

class AkShareKlineFetcher:
    def fetch(stock_code, period, start_date, end_date) -> List[KlineBar]
    def fetch_with_factors(...) -> Tuple[List[KlineBar], List[AdjustFactor]]
    @staticmethod
    def _parse_dataframe(stock_code, period, df, start_date, end_date) -> List[KlineBar]
```

---

## 🔌 初始化入口

### Main.py build_dependencies()

```python
def build_dependencies(futu_client, enable_akshare=False):
    # AkShare 初始化（迭代11）
    if enable_akshare:
        ak_client = AkShareClient(request_interval=AKSHARE_REQUEST_INTERVAL)
        akshare_kline_fetcher = AkShareKlineFetcher(ak_client)
        tushare_calendar_fetcher = TuShareCalendarFetcher()
    
    # TuShare/yfinance 保留但不初始化（已禁用）
    tushare_kline_fetcher = None
    yfinance_kline_fetcher = None
    
    # 传入 SyncEngine
    sync_engine = SyncEngine(
        akshare_kline_fetcher=akshare_kline_fetcher,
        tushare_calendar_fetcher=tushare_calendar_fetcher,
        # ... 其他参数
    )
```

### 何时启用 AkShare

```python
# main.py _run_sync_once()
deps = build_dependencies(futu_client, enable_akshare=has_us)
#                                                    ↑
#                        由 _has_us_stocks() 判定

def _has_us_stocks():
    """检查 watchlist.json 中是否有美股"""
    for market_node in data.get("markets", []):
        if market_node.get("market") == "US" and market_node.get("enabled"):
            for item in market_node.get("stocks", []):
                if item.get("is_active"):
                    return True  # ← 返回 True 则启用 AkShare
    return False
```

---

## 🎬 前端周期过滤

### 组件

```jsx
// web/src/components/PeriodSelector.jsx

const PERIODS = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
]

export default function PeriodSelector({ value, onChange, stockCode }) {
  // ← 美股自动过滤
  const isUS = stockCode?.startsWith('US.')
  const periods = isUS 
    ? PERIODS.filter(p => p.value === '1D')  // 仅日K
    : PERIODS                                 // 日周月K
  
  return (
    <div>
      {periods.map(p => <button key={p.value}>{p.label}</button>)}
    </div>
  )
}
```

### 迭代12扩展建议

如要支持美股周K/月K，需改为：

```jsx
const periods = isUS 
  ? PERIODS.filter(p => ['1D', '1W', '1M'].includes(p.value))  // 全部
  : PERIODS
```

---

## 🔄 迭代路线演变

```
迭代9        迭代10       迭代11          迭代12?
yfinance ─→ TuShare ──→ AkShare ──→ AkShare + Futu (条件路由)
日周月K      仅日K       仅日K       按周期选源
429限频      Token型      免费型      多源优先级
需VPN        50req/min    30req/min   智能降级
```

---

## ⚡ 常见问题快速定位

| 问题 | 排查位置 | 关键代码 |
|------|--------|--------|
| 美股无法拉周K | `sync_engine._get_kline_fetcher()` | 第682-689行 |
| 前端美股周K按钮隐藏 | `web/src/components/PeriodSelector.jsx` | 第14-17行 |
| AkShare限频报错 | `akshare_wrap/client.py` | wait_rate_limit() |
| 美股日历获取失败 | `sync_engine._ensure_calendar()` | 第303-330行 |
| 复权因子重复拉取 | `sync_engine._refresh_adjust_factors()` | 第332-356行 |

---

## 📝 下一步迭代检查清单

- [ ] 确认富途 OpenD 是否可用（需激活周K/月K）
- [ ] 评估 yfinance 代理方案（需VPN）
- [ ] 测试多源按周期降级逻辑
- [ ] 修改前端 PeriodSelector 启用美股周K/月K
- [ ] 在 config/settings.py 添加 US_STOCK_SOURCES_BY_PERIOD 配置
- [ ] 修改 sync_engine._get_kline_fetcher() 支持按周期路由
- [ ] 验证日历与K线数据一致性
- [ ] 更新文档和注释

