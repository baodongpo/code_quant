# 代码量化系统完整代码汇总

## 项目概览
本项目为 AI 量化辅助决策系统，包含前后端代码。前端基于 React + ECharts，后端基于 FastAPI + SQLite。系统支持 A股、港股、美股数据展示与分析。

**核心配置**：美股数据源可配置为 `futu`（默认，支持日/周/月K）或 `akshare`（备选，仅支持日K）

---

## 1. 前端 PeriodSelector 组件

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/web/src/components/PeriodSelector.jsx`

### 完整代码
```jsx
/**
 * components/PeriodSelector.jsx — 周期切换（1D/1W/1M）
 *
 * 美股周期控制：
 * - usStockSource === 'futu' 时，美股显示完整 1D/1W/1M
 * - 其他数据源（akshare 等）时，美股仅显示 1D
 */
import React from 'react'

const PERIODS = [
  { value: '1D', label: '日K' },
  { value: '1W', label: '周K' },
  { value: '1M', label: '月K' },
]

export default function PeriodSelector({ value, onChange, stockCode, usStockSource }) {
  const isUS = stockCode?.startsWith('US.')
  // 仅当美股且数据源不是 futu 时才隐藏周K/月K
  const periods = (isUS && usStockSource !== 'futu')
    ? PERIODS.filter(p => p.value === '1D')
    : PERIODS

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {periods.map(p => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          style={{
            padding:      '4px 12px',
            borderRadius: 6,
            border:       '1px solid',
            borderColor:  value === p.value ? '#388bfd' : '#30363d',
            background:   value === p.value ? '#1f3a5e' : '#1c2128',
            color:        value === p.value ? '#79c0ff' : '#8b949e',
            cursor:       'pointer',
            fontSize:     13,
            fontWeight:   value === p.value ? 600 : 400,
            transition:   'all 0.15s',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
```

### 核心逻辑
- **输入参数**：
  - `value`：当前选中周期（'1D'|'1W'|'1M'）
  - `onChange`：周期变化回调
  - `stockCode`：股票代码（如 'US.AAPL' 判断是否为美股）
  - `usStockSource`：美股数据源（'futu'|'akshare'|其他）
  
- **条件渲染**：
  - 当 `stockCode` 以 'US.' 开头 **且** `usStockSource !== 'futu'` 时，仅显示日K按钮
  - 其他情况显示完整的日K、周K、月K三个按钮

- **使用场景**：在 StockAnalysis.jsx 中被使用，通过 `/api/health` 获取的 `us_stock_source` 参数控制

---

## 2. 前端首页股票下拉列表组件

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/web/src/components/StockSelector.jsx`

### 完整代码
```jsx
/**
 * components/StockSelector.jsx — 股票下拉选择
 * 显示格式：股票名称 (代码)，多头信号用红色、空头信号用绿色
 */
import React from 'react'

const styles = {
  label:  { fontSize: 13, color: '#8b949e', marginRight: 6 },
  select: {
    background: '#1c2128', border: '1px solid #30363d',
    padding: '4px 8px', borderRadius: 6, fontSize: 13, cursor: 'pointer',
    minWidth: 200,
  },
}

/** 根据信号判断文字颜色：bullish=红，bearish=绿，neutral=默认 */
function signalColor(signal) {
  if (signal === 'bullish') return '#ef5350'  // 红涨
  if (signal === 'bearish') return '#26a69a'  // 绿跌
  return '#e6edf3'
}

/** 格式化显示标签：名称+代码 */
function stockLabel(s) {
  return s.name ? `${s.name} (${s.stock_code})` : s.stock_code
}

/** 按市场分组，顺序：A股 → 港股 → 美股 */
const MARKET_GROUPS = [
  { key: 'A',  label: 'A股' },
  { key: 'HK', label: '港股' },
  { key: 'US', label: '美股' },
]

export default function StockSelector({ stocks, value, onChange, signals }) {
  // signals: { [stock_code]: 'bullish'|'bearish'|'neutral' }，可选
  const sigMap = signals || {}

  // 找当前选中股票用于着色顶部选择框文字
  const selected = stocks.find(s => s.stock_code === value)
  const selectedSignal = selected ? (sigMap[value] || 'neutral') : 'neutral'

  // 按市场分组，组内保留信号颜色
  const groups = MARKET_GROUPS.map(g => ({
    ...g,
    stocks: stocks.filter(s => s.market === g.key),
  })).filter(g => g.stocks.length > 0)

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={styles.label}>股票</span>
      <div style={{ position: 'relative' }}>
        <select
          style={{ ...styles.select, color: signalColor(selectedSignal) }}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        >
          {groups.map(g => (
            <optgroup key={g.key} label={g.label} style={{ color: '#8b949e' }}>
              {g.stocks.map(s => {
                const sig = sigMap[s.stock_code] || 'neutral'
                return (
                  <option
                    key={s.stock_code}
                    value={s.stock_code}
                    // NOTE: option style.color 在 Safari/Firefox 中不生效，属已知平台限制；
                    // 已选中项的颜色通过 <select> 自身的 color 属性正常显示（跨浏览器有效）
                    style={{ color: signalColor(sig), background: '#1c2128' }}
                  >
                    {stockLabel(s)}
                  </option>
                )
              })}
            </optgroup>
          ))}
        </select>
      </div>
    </div>
  )
}
```

### 核心逻辑

#### 迭代12新增：按市场分组逻辑
- **分组顺序**：A股 → 港股 → 美股（MARKET_GROUPS 定义）
- **实现机制**：
  ```jsx
  const groups = MARKET_GROUPS.map(g => ({
    ...g,
    stocks: stocks.filter(s => s.market === g.key),
  })).filter(g => g.stocks.length > 0)
  ```
- **渲染方式**：使用 HTML5 `<optgroup>` 分组显示

#### 原有分组逻辑：按信号（多空中性）
- **信号颜色映射**：
  - `bullish`（多头） → 红色 `#ef5350`
  - `bearish`（空头） → 绿色 `#26a69a`
  - `neutral`（中性） → 灰白 `#e6edf3`
  
- **应用场景**：
  - 选中项的 `<select>` 文本颜色反映其信号
  - 下拉选项中每只股票的颜色也对应其信号（虽然某些浏览器不显示）

#### 输入参数
- `stocks`：股票列表，包含 `stock_code`, `market`, `name` 等字段
- `value`：当前选中的股票代码
- `onChange`：选择变化回调
- `signals`：可选，`{ [stock_code]: signal_type }` 映射

#### 数据源
- 股票列表来自 `/api/stocks` 接口（后端 GET /api/stocks）
- 信号来自 `/api/watchlist/summary` 接口（后端 GET /api/watchlist/summary），其中 `composite` 字段为综合信号

---

## 3. 后端 /api/health 接口

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/api/main.py`

### 完整代码
```python
from fastapi import FastAPI
from datetime import datetime, timezone
from config.settings import WEB_ACCESS_TOKEN, APP_VERSION, US_STOCK_SOURCE

# ... 其他代码 ...

@app.get("/api/health", tags=["system"])
def health():
    """服务健康检查，返回 ok、当前时间戳、版本号和美股数据源。"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "us_stock_source": US_STOCK_SOURCE,
    }
```

### 返回格式
```json
{
  "status": "ok",
  "timestamp": "2026-04-17T12:34:56.789123+00:00",
  "version": "v0.9.4",
  "us_stock_source": "futu"
}
```

### 关键字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态，固定为 "ok" |
| `timestamp` | string | 当前 UTC 时间戳（ISO 8601 格式） |
| `version` | string | 系统版本号（如 v0.9.4，硬编码在 config/settings.py） |
| `us_stock_source` | string | 美股数据源配置：`"futu"`（默认）或 `"akshare"`（备选） |

### 配置来源

#### 版本号配置
`config/settings.py` 第 102 行：
```python
APP_VERSION = "v0.9.4"
```
- **特点**：硬编码，随代码发布更新，不依赖 .env 配置文件

#### 美股数据源配置
`config/settings.py` 第 97 行：
```python
# 美股数据源：futu（默认）| akshare（备选，仅支持日K）
US_STOCK_SOURCE = os.getenv("US_STOCK_SOURCE", "futu")
```
- **默认值**：`"futu"`
- **可选值**：
  - `"futu"`：使用富途 OpenD 数据源（支持日K/周K/月K）
  - `"akshare"`：使用 AkShare 数据源（仅支持日K）
- **配置方式**：通过环境变量 `US_STOCK_SOURCE` 设置，或在 `.env` 文件中配置

### 前端使用场景

在 `web/src/pages/StockAnalysis.jsx` 中：
```javascript
useEffect(() => {
  fetchHealth()
    .then(data => {
      if (data?.version) setAppVersion(data.version)
      if (data?.us_stock_source) setUsStockSource(data.us_stock_source)
    })
    .catch(() => {
      // 静默降级：版本号区域不展示，不影响其他功能
    })
}, [])
```

将 `us_stock_source` 传递给 `PeriodSelector` 组件，控制美股周期按钮的显示/隐藏。

---

## 4. 后端 /api/stocks 接口

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/api/routes/stocks.py`

### 完整代码
```python
"""api/routes/stocks.py — GET /api/stocks"""

from fastapi import APIRouter
from config.settings import DB_PATH
from db.repositories.stock_repo import StockRepository

router = APIRouter()


@router.get("/stocks")
def list_stocks():
    """返回 watchlist 中全部活跃股票列表。"""
    repo = StockRepository(DB_PATH)
    stocks = repo.get_active()
    return {
        "stocks": [
            {
                "stock_code": s.stock_code,
                "name":       s.name,
                "market":     s.market,
                "asset_type": s.asset_type,
                "currency":   s.currency,
                "lot_size":   s.lot_size,
            }
            for s in stocks
        ]
    }
```

### 返回格式
```json
{
  "stocks": [
    {
      "stock_code": "SH.600893",
      "name": "航发动力",
      "market": "A",
      "asset_type": "stock",
      "currency": "CNY",
      "lot_size": 100
    },
    {
      "stock_code": "HK.00700",
      "name": "腾讯控股",
      "market": "HK",
      "asset_type": "stock",
      "currency": "HKD",
      "lot_size": 100
    },
    {
      "stock_code": "US.AAPL",
      "name": "Apple",
      "market": "US",
      "asset_type": "stock",
      "currency": "USD",
      "lot_size": 1
    }
  ]
}
```

### 数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | string | 股票代码（如 SH.600893、HK.00700、US.AAPL） |
| `name` | string | 股票名称（如 航发动力、腾讯控股、Apple） |
| `market` | string | 市场标识：`A`（A股）、`HK`（港股）、`US`（美股） |
| `asset_type` | string | 资产类型，通常为 "stock" |
| `currency` | string | 交易货币（CNY、HKD、USD） |
| `lot_size` | int | 每手数量 |

### 数据来源
- 数据来自 SQLite 数据库 `stocks` 表
- 仅返回 `is_active=true` 的股票（`repo.get_active()` 过滤）
- 股票信息从 `watchlist.json` 通过 `python main.py migrate` 命令同步到数据库

### 前端使用
```javascript
const stocks = await fetchStocks()  // 在 web/src/api/client.js 中定义
// 返回 stocks 数组，直接用于 StockSelector 组件
```

---

## 5. 后端 /api/watchlist/summary 接口

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/api/routes/watchlist.py`  
`/Users/bladebao/Documents/code_python/code_quant/api/services/kline_service.py`

### 完整代码

#### 路由定义（watchlist.py）
```python
"""api/routes/watchlist.py — GET /api/watchlist/summary"""

from fastapi import APIRouter
from api.services.kline_service import get_watchlist_summary

router = APIRouter()


@router.get("/watchlist/summary")
def watchlist_summary():
    """返回 watchlist 总览（各股最新指标信号）。"""
    return get_watchlist_summary()
```

#### 服务实现（kline_service.py 中的关键部分）
```python
def get_watchlist_summary() -> Dict[str, Any]:
    """
    返回 watchlist 所有活跃股票的最新指标信号。
    每只股票取最近 90 个交易日的日K，只计算日K。
    """
    stock_repo = StockRepository(DB_PATH)
    kline_repo = KlineRepository(DB_PATH)
    adjust_factor_repo = AdjustFactorRepository(DB_PATH)
    adj_service = AdjustmentService(kline_repo, adjust_factor_repo)

    active_stocks = stock_repo.get_active()
    today = date.today().isoformat()
    start_90d = (date.today() - timedelta(days=130)).isoformat()  # 多取一些确保有足够 bar

    summary = []
    for stock in active_stocks:
        bars = adj_service.get_adjusted_klines(
            stock.stock_code, "1D", start_90d, today, adj_type="qfq"
        )
        if not bars:
            continue

        ind = IndicatorEngine.calculate_all(bars)
        latest = bars[-1]

        # 涨跌幅
        change_pct: Optional[float] = None
        if latest.last_close and latest.last_close != 0:
            change_pct = round((latest.close - latest.last_close) / latest.last_close * 100, 2)

        # RSI 最新值（用于综合信号）
        rsi_val = _last_valid(ind.RSI.get("RSI14", []))

        composite = calc_composite_signal(ind.signals, rsi_val)

        summary.append({
            "stock_code":   stock.stock_code,
            "name":         stock.name,
            "market":       stock.market,
            "latest_close": latest.close,
            "change_pct":   change_pct,
            "pe_ratio":     latest.pe_ratio,
            "pb_ratio":     latest.pb_ratio,
            "signals": {
                "RSI":       ind.signals.get("RSI", "neutral"),
                "RSI_value": rsi_val,
                "MACD":      ind.signals.get("MACD", "neutral"),
                "KDJ":       ind.signals.get("KDJ", "neutral"),
                "composite": composite,
            },
        })

    return {"summary": summary}
```

### 返回格式
```json
{
  "summary": [
    {
      "stock_code": "SH.600893",
      "name": "航发动力",
      "market": "A",
      "latest_close": 45.67,
      "change_pct": 2.15,
      "pe_ratio": 15.3,
      "pb_ratio": 2.1,
      "signals": {
        "RSI": "bullish",
        "RSI_value": 72.5,
        "MACD": "bullish",
        "KDJ": "neutral",
        "composite": "bullish"
      }
    },
    {
      "stock_code": "HK.00700",
      "name": "腾讯控股",
      "market": "HK",
      "latest_close": 432.5,
      "change_pct": -1.23,
      "pe_ratio": 25.7,
      "pb_ratio": 3.2,
      "signals": {
        "RSI": "neutral",
        "RSI_value": 52.3,
        "MACD": "bearish",
        "KDJ": "bearish",
        "composite": "bearish"
      }
    },
    {
      "stock_code": "US.AAPL",
      "name": "Apple",
      "market": "US",
      "latest_close": 178.45,
      "change_pct": 0.89,
      "pe_ratio": 32.1,
      "pb_ratio": 58.3,
      "signals": {
        "RSI": "neutral",
        "RSI_value": 48.2,
        "MACD": "neutral",
        "KDJ": "neutral",
        "composite": "neutral"
      }
    }
  ]
}
```

### 数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | string | 股票代码 |
| `name` | string | 股票名称 |
| `market` | string | 市场（A/HK/US） |
| `latest_close` | float | 最新收盘价 |
| `change_pct` | float \| null | 涨跌幅百分比 |
| `pe_ratio` | float \| null | 市盈率 |
| `pb_ratio` | float \| null | 市净率 |
| **signals** | object | 技术指标信号汇总 |
| `signals.RSI` | string | RSI 信号：bullish/bearish/neutral |
| `signals.RSI_value` | float \| null | RSI 最新数值（14日） |
| `signals.MACD` | string | MACD 信号：bullish/bearish/neutral |
| `signals.KDJ` | string | KDJ 信号：bullish/bearish/neutral |
| `signals.composite` | string | 综合信号（由上述指标综合计算） |

### 信号值说明
- **bullish**（多头/看涨）：技术指标显示上升趋势或超卖反弹
- **bearish**（空头/看跌）：技术指标显示下降趋势或超买回调
- **neutral**（中性）：技术指标处于中间状态，无明确方向

### 前端使用场景

#### 1. Watchlist 页面（pages/WatchlistPage.jsx）
- 显示所有活跃股票的汇总表格
- 按市场（A股/港股/美股）分组显示
- 实时显示各股的最新价、涨跌幅、指标信号

#### 2. 股票下拉列表着色（StockSelector.jsx）
- 用 `composite` 信号值为下拉列表的选项着色
- bullish → 红色，bearish → 绿色，neutral → 灰白色

---

## 6. 前端 API 客户端

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/web/src/api/client.js`

### 完整代码
```javascript
/**
 * api/client.js — Axios 封装，统一 API 调用
 */
import axios from 'axios'
import { getToken } from '../utils/auth.js'

const BASE_URL = import.meta.env.VITE_API_BASE || ''

const client = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

/** 请求拦截器：自动附加 X-Access-Token 请求头（token 为空时不附加）*/
client.interceptors.request.use(config => {
  const token = getToken()
  if (token) config.headers['X-Access-Token'] = token
  return config
})

/** 获取活跃股票列表 */
export async function fetchStocks() {
  const res = await client.get('/api/stocks')
  return res.data.stocks  // [{stock_code, market, ...}]
}

/**
 * 获取 K线 + 指标数据
 * @param {string} code
 * @param {string} period  1D | 1W | 1M
 * @param {string|null} start  YYYY-MM-DD
 * @param {string|null} end    YYYY-MM-DD
 * @param {string} adj  qfq | raw
 */
export async function fetchKline(code, period, start = null, end = null, adj = 'qfq') {
  const params = { code, period, adj }
  if (start) params.start = start
  if (end)   params.end   = end
  const res = await client.get('/api/kline', { params })
  return res.data
}

/** 获取 Watchlist 总览信号 */
export async function fetchWatchlistSummary() {
  const res = await client.get('/api/watchlist/summary')
  return res.data.summary  // [...]
}

/** 获取指标清单 */
export async function fetchIndicators() {
  const res = await client.get('/api/indicators')
  return res.data.indicators
}

/** 获取健康检查状态（含版本号） */
export async function fetchHealth() {
  const res = await client.get('/api/health')
  return res.data  // { status, timestamp, version, us_stock_source }
}
```

### API 汇总

| 函数 | 方法 | 端点 | 说明 |
|------|------|------|------|
| `fetchStocks()` | GET | `/api/stocks` | 获取活跃股票列表 |
| `fetchKline(code, period, start, end, adj)` | GET | `/api/kline` | 获取K线 + 指标数据 |
| `fetchWatchlistSummary()` | GET | `/api/watchlist/summary` | 获取Watchlist总览信号 |
| `fetchIndicators()` | GET | `/api/indicators` | 获取指标清单 |
| `fetchHealth()` | GET | `/api/health` | 获取健康检查（含版本号、美股数据源） |

---

## 7. 后端配置文件

### 文件路径
`/Users/bladebao/Documents/code_python/code_quant/config/settings.py`

### 完整代码（关键部分）
```python
import os
from dotenv import load_dotenv

# 优先加载项目根目录下的 .env 文件（本地开发用，不提交仓库）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, ".env"))

# ============================================================
# OpenD 连接配置（从环境变量读取，fallback 到本地默认值）
# ============================================================
OPEND_HOST = os.getenv("OPEND_HOST", "127.0.0.1")
OPEND_PORT = int(os.getenv("OPEND_PORT", "11111"))

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = _BASE_DIR
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "quant.db"))
LOG_DIR = os.path.join(BASE_DIR, "logs")
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")

# ... 其他配置 ...

# ============================================================
# 美股数据源配置（迭代11新增）
# ============================================================
AKSHARE_REQUEST_INTERVAL = float(os.getenv("AKSHARE_REQUEST_INTERVAL", "1.0"))  # 请求间隔（秒）

# 美股数据源：futu（默认）| akshare（备选，仅支持日K）
US_STOCK_SOURCE = os.getenv("US_STOCK_SOURCE", "futu")

# ============================================================
# 系统版本号（硬编码，随代码发布更新，不依赖 .env 配置文件）
# ============================================================
APP_VERSION = "v0.9.4"
```

### 核心配置变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPEND_HOST` | "127.0.0.1" | 富途 OpenD 服务器地址 |
| `OPEND_PORT` | 11111 | 富途 OpenD 服务器端口 |
| `DB_PATH` | data/quant.db | SQLite 数据库文件路径 |
| `WATCHLIST_PATH` | watchlist.json | 股票监控清单配置文件 |
| `US_STOCK_SOURCE` | "futu" | 美股数据源：futu（完整）或 akshare（日K限制） |
| `APP_VERSION` | "v0.9.4" | 系统版本号（硬编码） |
| `WEB_ACCESS_TOKEN` | "" | Web访问Token（留空不启用鉴权） |

### 配置方式

1. **环境变量**（优先）
   ```bash
   export US_STOCK_SOURCE=akshare
   python main.py sync
   ```

2. **.env 文件**（次优先）
   ```
   # .env
   US_STOCK_SOURCE=akshare
   OPEND_HOST=192.168.1.100
   OPEND_PORT=11111
   ```

3. **硬编码默认值**（最后fallback）

---

## 8. 数据流向图

```
┌─────────────────────────────────────────────────────────────────┐
│                      前端 (React)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  StockAnalysis.jsx (主页面)                                     │
│    ├─ fetchHealth() ────────────┐                               │
│    │  ↓ us_stock_source         │                               │
│    │  PeriodSelector.jsx        │                               │
│    │    └─ 控制周K/月K显示/隐藏 │                               │
│    │                             │                               │
│    ├─ fetchStocks() ────────────────────────┐                  │
│    │  ↓ stocks                              │                   │
│    │  StockSelector.jsx                     │                   │
│    │    └─ 按市场(A/HK/US)分组              │                   │
│    │                              │          │                   │
│    ├─ fetchWatchlistSummary() ──┤          │                   │
│    │  ↓ signals (composite)       │          │                   │
│    │  StockSelector 着色          │          │                   │
│    │    └─ bullish→红 / bearish→绿 │          │                   │
│    │                              │          │                   │
│    └─ fetchKline()               └──────────┴──────┐           │
│       ↓ bars + indicators + signals                │           │
│       MainChart / MACD / RSI / KDJ 副图           │           │
│       └─ 显示K线、指标、信号                      │           │
│                                                    │           │
│  WatchlistPage.jsx (Watchlist总览)               │           │
│    └─ fetchWatchlistSummary() ───────────────────┤           │
│       └─ 显示表格（按市场分组）                   │           │
│                                                    │           │
└──────────────────────────┬───────────────────────┬─────────────┘
                           │                       │
                    HTTP RESTful API             │
                           │                       │
┌──────────────────────────▼───────────────────────▼─────────────┐
│                   后端 (FastAPI)                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  GET /api/health                                                 │
│  ├─ 返回 us_stock_source 配置                                   │
│  └─ → config.settings.US_STOCK_SOURCE                           │
│                                                                   │
│  GET /api/stocks                                                 │
│  ├─ 查询 DB: SELECT * FROM stocks WHERE is_active=true         │
│  └─ → StockRepository.get_active()                              │
│      └─ 返回 {stock_code, name, market, ...}                   │
│                                                                   │
│  GET /api/watchlist/summary                                      │
│  ├─ 读取所有活跃股票                                            │
│  │  └─ StockRepository.get_active()                             │
│  ├─ 各股取最近90个交易日日K                                     │
│  │  └─ KlineRepository.get_bars() + AdjustmentService           │
│  ├─ 计算技术指标                                                │
│  │  └─ IndicatorEngine.calculate_all(bars)                      │
│  │     └─ 计算 RSI, MACD, KDJ 等信号                           │
│  ├─ 综合信号计算                                                │
│  │  └─ calc_composite_signal(ind.signals, rsi_val)              │
│  └─ 返回 {summary: [...]}                                       │
│                                                                   │
│  GET /api/kline?code=XX&period=1D&start=YYYY-MM-DD&end=YYYY-MM-DD
│  ├─ 读取指定期间的K线（可选前复权）                            │
│  ├─ 计算全部指标（MA, BOLL, MACD, RSI, KDJ, VPA等）            │
│  └─ 返回 {bars: [...], indicators: {...}, signals: {...}}      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
           ↑
           │
           └─ SQLite DB (data/quant.db)
              ├─ stocks 表（股票基本信息）
              ├─ klines 表（日K/周K/月K数据）
              ├─ adjust_factors 表（复权因子）
              └─ 其他数据表
```

---

## 9. 迭代特性说明

### 迭代11：美股数据源架构
- 新增 `US_STOCK_SOURCE` 配置参数
- 支持 AkShare 作为美股备选数据源
- AkShare 模式仅支持日K（无周K/月K）

### 迭代12：股票下拉分组优化
- **新增**：按市场（A股/港股/美股）分组显示
- **保留**：按信号（多空中性）着色
- **分组顺序**：A股 → 港股 → 美股
- **实现**：使用 HTML5 `<optgroup>` 元素

### FEAT-1：美股周期选项控制
- PeriodSelector 根据 `usStockSource` 动态显示/隐藏周K月K按钮
- futu 源时完整显示，其他源（如 akshare）时仅显示日K
- 参数通过 `/api/health` 接口下发

### FEAT-version：系统版本号显示
- `/api/health` 返回 `version` 字段
- 前端显示在页面顶部（可选）
- 版本号硬编码在 config/settings.py

---

## 10. 环境变量配置示例

### 标准配置（使用富途 OpenD）
```bash
# .env
US_STOCK_SOURCE=futu          # 美股数据源：完整支持日/周/月K
OPEND_HOST=127.0.0.1
OPEND_PORT=11111
DB_PATH=./data/quant.db
WEB_ACCESS_TOKEN=              # 留空不启用Token鉴权
```

### AkShare 降级配置（美股仅支持日K）
```bash
# .env
US_STOCK_SOURCE=akshare        # 美股数据源：仅支持日K
AKSHARE_REQUEST_INTERVAL=1.0   # AkShare 请求间隔
OPEND_HOST=127.0.0.1
OPEND_PORT=11111
DB_PATH=./data/quant.db
WEB_ACCESS_TOKEN=              # Token鉴权
```

---

## 11. 开发技术栈

### 前端
- **框架**：React 18
- **图表**：ECharts 5
- **HTTP客户端**：Axios
- **构建工具**：Vite
- **状态管理**：React Hooks (useState, useEffect, useCallback, useRef)
- **样式**：内联 CSS + GitHub Dark 配色

### 后端
- **框架**：FastAPI
- **服务器**：Uvicorn
- **数据库**：SQLite 3
- **ORM**：自定义 Repository 模式（非 ORM 框架）
- **三方库**：yfinance, AkShare, 富途 SDK
- **限频**：自定义限频器（RateLimiter）

---

## 12. 总结表

| 模块 | 文件路径 | 责职 | 关键字段 |
|------|--------|------|--------|
| **PeriodSelector** | web/src/components/PeriodSelector.jsx | 周期选择（1D/1W/1M） | usStockSource, stockCode |
| **StockSelector** | web/src/components/StockSelector.jsx | 股票下拉（按市场分组+信号着色） | market, signals, composite |
| **/api/health** | api/main.py | 健康检查 | us_stock_source, version |
| **/api/stocks** | api/routes/stocks.py | 活跃股票列表 | stock_code, market, name |
| **/api/watchlist/summary** | api/routes/watchlist.py + api/services/kline_service.py | Watchlist总览（指标信号） | signals.composite, signals.RSI 等 |
| **API客户端** | web/src/api/client.js | HTTP请求封装 | fetchHealth, fetchStocks 等 |
| **配置** | config/settings.py | 系统配置 | US_STOCK_SOURCE, APP_VERSION |

---

## 13. 快速开始

### 后端启动
```bash
# 数据同步（首次运行）
python main.py migrate      # 迁移DB + 同步watchlist
python main.py sync         # 同步K线数据

# 启动 Web API 服务
export US_STOCK_SOURCE=futu
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 前端启动
```bash
cd web
npm install
npm run dev                 # 开发模式（Vite）
# 或
npm run build              # 生产构建
```

### 访问
- **前端**：http://localhost:5173 (开发) 或 http://localhost:8000 (生产)
- **API 文档**：http://localhost:8000/docs (Swagger)
- **健康检查**：http://localhost:8000/api/health

