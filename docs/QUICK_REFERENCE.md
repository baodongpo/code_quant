# 代码量化系统 - 快速查阅表

## 📋 核心文件清单（按功能分类）

### 前端组件 (React)
| 组件 | 文件路径 | 核心功能 |
|------|--------|--------|
| **PeriodSelector** | `web/src/components/PeriodSelector.jsx` | 周期切换（1D/1W/1M），根据 `usStockSource` 动态显示/隐藏周K月K |
| **StockSelector** | `web/src/components/StockSelector.jsx` | 股票下拉列表，按市场分组（A股/港股/美股），按信号着色（红/绿） |
| **MainChart** | `web/src/components/MainChart.jsx` | 主K线图表（ECharts） |
| **MACDPanel** | `web/src/components/MACDPanel.jsx` | MACD 副图 |
| **RSIPanel** | `web/src/components/RSIPanel.jsx` | RSI 副图 |
| **KDJPanel** | `web/src/components/KDJPanel.jsx` | KDJ 副图 |
| **SignalBanner** | `web/src/components/SignalBanner.jsx` | 综合信号横幅 |
| **ChartSidebar** | `web/src/components/ChartSidebar.jsx` | 图表说明侧边栏 |

### 前端页面
| 页面 | 文件路径 | 核心功能 |
|------|--------|--------|
| **StockAnalysis** | `web/src/pages/StockAnalysis.jsx` | 主页（个股分析），fetchHealth 获取 us_stock_source |
| **WatchlistPage** | `web/src/pages/WatchlistPage.jsx` | Watchlist总览，按市场分组显示信号表格 |

### 前端 API 客户端
| 模块 | 文件路径 | 关键函数 |
|------|--------|--------|
| **API Client** | `web/src/api/client.js` | `fetchHealth()` / `fetchStocks()` / `fetchWatchlistSummary()` / `fetchKline()` |

### 后端 API 路由
| 端点 | 文件路径 | 返回内容 |
|------|--------|---------|
| `GET /api/health` | `api/main.py` | `{status, timestamp, version, us_stock_source}` |
| `GET /api/stocks` | `api/routes/stocks.py` | `{stocks: [{stock_code, market, name, ...}]}` |
| `GET /api/watchlist/summary` | `api/routes/watchlist.py` | `{summary: [{stock_code, signals: {RSI, MACD, KDJ, composite}, ...}]}` |
| `GET /api/kline` | `api/routes/kline.py` | `{bars: [...], indicators: {...}, signals: {...}}` |

### 后端服务
| 服务 | 文件路径 | 核心方法 |
|------|--------|--------|
| **KlineService** | `api/services/kline_service.py` | `get_watchlist_summary()` / `get_kline_with_indicators()` |

### 后端数据访问
| 仓库 | 文件路径 | 核心方法 |
|------|--------|--------|
| **StockRepository** | `db/repositories/stock_repo.py` | `get_active()` / `get_by_code()` / `get_all()` |
| **KlineRepository** | `db/repositories/kline_repo.py` | `get_bars()` / `upsert_many()` |

### 配置文件
| 配置 | 文件路径 | 关键变量 |
|------|--------|--------|
| **Settings** | `config/settings.py` | `US_STOCK_SOURCE` / `APP_VERSION` / `DB_PATH` |

---

## 🔑 关键概念

### 1. 美股数据源 (US_STOCK_SOURCE)
- **futu**：使用富途 OpenD（默认，支持日/周/月K）
- **akshare**：使用 AkShare（仅支持日K）
- **配置位置**：`config/settings.py:97`
- **环境变量**：`US_STOCK_SOURCE`

### 2. 市场分类
- **A**：A股（人民币）
- **HK**：港股（港币）
- **US**：美股（美元）
- **渲染顺序**：A股 → 港股 → 美股

### 3. 技术指标信号
- **bullish**：多头/看涨（红色 #ef5350）
- **bearish**：空头/看跌（绿色 #26a69a）
- **neutral**：中性/无方向（灰白 #e6edf3）

### 4. 指标类型
- **RSI**：相对强弱指数（14日）
- **MACD**：指数平滑异同移动平均线（DIF/DEA/柱）
- **KDJ**：随机指标（K/D/J线）
- **MA**：移动平均线（5/20/60日）
- **BOLL**：布林带（上轨/中轨/下轨）
- **VPA_DEFENDER**：能量防守线（OBV + 防守线）

---

## 📍 数据流向 (Quick Map)

```
前端初始化
  ├─ fetchHealth() 
  │   └─ GET /api/health → us_stock_source
  │       └─ 传给 PeriodSelector（控制周K月K显示）
  │
  ├─ fetchStocks()
  │   └─ GET /api/stocks → [{stock_code, market, name, ...}]
  │       └─ 传给 StockSelector（显示下拉列表，按市场分组）
  │
  └─ fetchWatchlistSummary()
      └─ GET /api/watchlist/summary → [{stock_code, signals: {composite, RSI, ...}, ...}]
          └─ 用于 StockSelector 着色（信号→颜色）

用户选择股票 → 加载K线数据
  └─ fetchKline(code, period, start, end)
      └─ GET /api/kline → {bars: [...], indicators: {...}, signals: {...}}
          └─ 渲染 MainChart / MACD / RSI / KDJ
```

---

## 🎯 重要参数传递

### 1. 美股数据源控制流
```
/api/health 
  ↓ us_stock_source
StockAnalysis.jsx: usStockSource state
  ↓ prop
PeriodSelector.jsx: usStockSource prop
  ↓ 条件判断
if (isUS && usStockSource !== 'futu')
  显示 [日K] 只
else
  显示 [日K] [周K] [月K]
```

### 2. 信号着色流
```
/api/watchlist/summary 
  ↓ signals.composite
StockAnalysis.jsx: watchlistSignals state
  ↓ prop signals
StockSelector.jsx: signals prop
  ↓ signalColor(signal)
option style: color = #ef5350|#26a69a|#e6edf3
```

### 3. 股票市场分组流
```
/api/stocks 
  ↓ market (A|HK|US)
StockSelector.jsx
  ↓ MARKET_GROUPS filter
stocks.filter(s => s.market === g.key)
  ↓ 渲染
<optgroup label="A股|港股|美股">
  <option>...</option>
</optgroup>
```

---

## 🔧 配置修改指南

### 切换美股数据源到 AkShare（仅支持日K）
```bash
# .env 文件
US_STOCK_SOURCE=akshare

# 或直接环境变量
export US_STOCK_SOURCE=akshare

# 重启 Web API
uvicorn api.main:app --reload
```

### 修改周期按钮逻辑
**文件**：`web/src/components/PeriodSelector.jsx`
```jsx
// 当前逻辑（第19-20行）
const periods = (isUS && usStockSource !== 'futu')
  ? PERIODS.filter(p => p.value === '1D')
  : PERIODS

// 修改示例：只对 akshare 源限制
const periods = (isUS && usStockSource === 'akshare')
  ? PERIODS.filter(p => p.value === '1D')
  : PERIODS
```

### 修改股票分组顺序
**文件**：`web/src/components/StockSelector.jsx`（第28-32行）
```jsx
const MARKET_GROUPS = [
  { key: 'US', label: '美股' },    // 改为美股优先
  { key: 'HK', label: '港股' },
  { key: 'A',  label: 'A股' },
]
```

### 修改信号颜色
**文件**：`web/src/components/StockSelector.jsx`（第17-21行）
```jsx
function signalColor(signal) {
  if (signal === 'bullish') return '#00ff00'  // 改为绿色
  if (signal === 'bearish') return '#ff0000'  // 改为红色
  return '#808080'  // 改为灰色
}
```

---

## 📊 数据库架构

### stocks 表
```sql
CREATE TABLE stocks (
  stock_code TEXT PRIMARY KEY,
  market TEXT,              -- A|HK|US
  name TEXT,
  asset_type TEXT,
  currency TEXT,
  lot_size INT,
  is_active BOOLEAN
)
```

### klines 表
```sql
CREATE TABLE klines (
  stock_code TEXT,
  period TEXT,              -- 1D|1W|1M
  trade_date TEXT,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  volume INT,
  turnover REAL,
  pe_ratio REAL,
  pb_ratio REAL,
  ps_ratio REAL,
  turnover_rate REAL,
  last_close REAL,
  updated_at TEXT,
  PRIMARY KEY (stock_code, period, trade_date)
)
```

---

## 🚀 常见操作

### 查看系统版本和美股数据源
```bash
curl http://localhost:8000/api/health
# 输出: {"status":"ok","timestamp":"...","version":"v0.9.4","us_stock_source":"futu"}
```

### 获取所有活跃股票
```bash
curl http://localhost:8000/api/stocks
```

### 获取 Watchlist 总览（含信号）
```bash
curl http://localhost:8000/api/watchlist/summary
```

### 获取单只股票K线（日K，近365天）
```bash
curl "http://localhost:8000/api/kline?code=SH.600893&period=1D"
```

### 获取单只股票K线（周K，自定义日期范围）
```bash
curl "http://localhost:8000/api/kline?code=US.AAPL&period=1W&start=2024-01-01&end=2024-12-31"
```

---

## 🐛 常见问题排查

### 问题1：前端周K月K按钮不显示（美股）
**排查**：
1. 检查 `/api/health` 返回的 `us_stock_source` 值
   - 若为 "akshare"，则正常不显示
   - 若为 "futu"，检查 PeriodSelector.jsx 的条件判断逻辑
2. 检查股票代码是否以 "US." 开头

### 问题2：下拉列表没有按市场分组
**排查**：
1. 检查 `/api/stocks` 返回的数据中 `market` 字段是否为空
2. 检查 StockSelector.jsx 的 MARKET_GROUPS 定义是否正确
3. 检查浏览器是否支持 HTML5 `<optgroup>` 元素

### 问题3：信号颜色不显示
**排查**：
1. 检查 `/api/watchlist/summary` 返回的 `signals.composite` 值
2. 某些浏览器（Safari/Firefox）option 标签 style.color 可能不生效，但 select 标签的 color 应该正常显示
3. 尝试在浏览器开发工具中调试样式

---

## 📚 相关文档

- **完整代码汇总**：`CODE_SUMMARY.md`
- **README**：`README.md`
- **CLAUDE 开发日志**：`CLAUDE.md`

