# 迭代3 详细设计文档

**版本**: v1.0
**日期**: 2026-03-18
**作者**: Dev
**对应 PRD**: docs/requirements_iter3.md v3.1

---

## 1. 技术选型

### 1.1 后端框架：FastAPI

**理由**：
- 原生 async/await 支持，与 SQLite WAL 模式兼容性好
- 自带 OpenAPI 文档（`/docs`），方便调试
- Python 3.10 原生支持，与现有 env_quant 环境一致
- `StaticFiles` 原生支持，生产模式一命令 serve 前端构建产物
- 参数校验集成 Pydantic，减少样板代码

### 1.2 前端框架：React + Vite

**理由**：
- Vite 构建速度快，开发热重载体验好
- React 生态完善，组件化方便复用
- 与 ECharts for React (`echarts-for-react`) 集成成熟
- `npm create vite` 一键脚手架，零配置启动

### 1.3 K线图表库：Apache ECharts（通过 echarts-for-react）

**理由**：
- 原生支持 K 线蜡烛图（`candlestick` 系列）
- 多 Y 轴 + 多子图（`grid`）联动十字线开箱即用（`axisPointer`）
- 区间着色通过 `markArea` 或 `visualMap` 实现
- 动态数据更新性能优秀（canvas 渲染）
- 国内金融图表使用最广泛，社区资料丰富

### 1.4 包管理

- 后端：pip（复用现有 env_quant），新增 `fastapi uvicorn[standard]`
- 前端：npm（项目内 `web/` 目录）

---

## 2. 新增目录结构

在现有代码库基础上新增：

```
code_quant/
├── api/                          # 后端 FastAPI 应用（新增）
│   ├── __init__.py
│   ├── main.py                   # FastAPI app 入口，挂载路由，生产模式 serve 静态文件
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── stocks.py             # GET /api/stocks
│   │   ├── kline.py              # GET /api/kline
│   │   ├── watchlist.py          # GET /api/watchlist/summary
│   │   └── indicators.py         # GET /api/indicators
│   └── services/
│       ├── __init__.py
│       └── kline_service.py      # 封装 AdjustmentService + IndicatorEngine
│
├── core/
│   └── indicator_engine.py       # 新增：7个指标计算 + 信号判断
│
├── web/                          # 前端 React 应用（新增）
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/
│       │   └── client.js         # Axios 封装，统一 API 调用
│       ├── components/
│       │   ├── StockSelector.jsx
│       │   ├── PeriodSelector.jsx
│       │   ├── TimeRangeSelector.jsx
│       │   ├── MainChart.jsx     # K线主图 + MA + BOLL + 成交量
│       │   ├── MACDPanel.jsx     # MACD 副图
│       │   ├── RSIPanel.jsx      # RSI 副图（含区间背景色）
│       │   ├── KDJPanel.jsx      # KDJ 副图（含区间背景色）
│       │   ├── BottomBar.jsx     # 底部信息条（最新价、信号标签）
│       │   └── SignalTag.jsx     # 信号标签通用组件（绿/红/灰）
│       ├── pages/
│       │   ├── StockAnalysis.jsx # 个股分析页 /
│       │   └── WatchlistPage.jsx # Watchlist 总览页 /watchlist
│       └── utils/
│           └── signals.js        # 前端信号判断辅助函数
│
├── deploy/
│   └── quant-web.service         # systemd Web 服务配置（新增）
│
└── requirements.txt              # 新增 fastapi uvicorn[standard]
```

---

## 3. IndicatorEngine 接口设计

### 3.1 数据结构

```python
# core/indicator_engine.py

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

class SignalEnum(str, Enum):
    BULLISH = "bullish"    # 多头信号（绿色）
    BEARISH = "bearish"    # 空头信号（红色）
    NEUTRAL = "neutral"    # 中性/观望（灰色）
    VOLUME_HIGH = "volume_high"  # 放量（橙色）
    VOLUME_LOW  = "volume_low"   # 缩量（灰色）

@dataclass
class IndicatorResult:
    MA: Dict[str, List[Optional[float]]]   # {"MA5": [...], "MA20": [...], "MA60": [...]}
    EMA: Dict[str, List[Optional[float]]]  # {"EMA12": [...], "EMA26": [...]}
    BOLL: Dict[str, List[Optional[float]]] # {"upper": [...], "mid": [...], "lower": [...]}
    MACD: Dict[str, List[Optional[float]]] # {"dif": [...], "dea": [...], "macd": [...]}
    RSI: Dict[str, List[Optional[float]]]  # {"RSI14": [...]}
    KDJ: Dict[str, List[Optional[float]]]  # {"K": [...], "D": [...], "J": [...]}
    MAVOL: Dict[str, List[Optional[float]]]# {"MAVOL5": [...], "MAVOL10": [...], "MAVOL20": [...]}
    signals: Dict[str, str]                # {"BOLL": "neutral", "MACD": "bullish", ...}
```

### 3.2 计算方法签名

```python
class IndicatorEngine:
    @staticmethod
    def ma(close: List[float], n: int) -> List[Optional[float]]:
        """简单移动平均。前 n-1 个值为 None。"""

    @staticmethod
    def ema(close: List[float], n: int) -> List[Optional[float]]:
        """指数移动平均，k=2/(n+1)。第一个有效值为第 n 个收盘价的算术均值。"""

    @staticmethod
    def macd(close: List[float], fast=12, slow=26, signal=9
             ) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """返回 (dif_series, dea_series, macd_bar_series)。"""

    @staticmethod
    def boll(close: List[float], n=20, k=2
             ) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """返回 (upper, mid, lower)。"""

    @staticmethod
    def rsi(close: List[float], n=14) -> List[Optional[float]]:
        """相对强弱指数，前 n 个值为 None。"""

    @staticmethod
    def kdj(high: List[float], low: List[float], close: List[float], n=9
            ) -> tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        """返回 (K, D, J)。初始 K=50, D=50。"""

    @staticmethod
    def mavol(volume: List[int], periods=(5, 10, 20)) -> Dict[str, List[Optional[float]]]:
        """成交量移动平均。返回各周期均线列表。"""

    @classmethod
    def calculate_all(cls, bars) -> IndicatorResult:
        """一次性计算所有指标并返回 IndicatorResult（含信号）。"""

    @staticmethod
    def get_signal(indicator: str, values: dict) -> SignalEnum:
        """对照 PRD §4.2 信号规范，返回当前信号状态。"""
```

### 3.3 信号判断逻辑（对照 PRD §4.2）

| 指标 | 条件 | 信号 |
|------|------|------|
| BOLL | latest_close > upper | BEARISH（🔴超买·上轨突破）|
| BOLL | latest_close < lower | BULLISH（🟢超卖·下轨突破）|
| BOLL | 其余 | NEUTRAL |
| MACD | 最近一次交叉为金叉（dif[-1]>dea[-1] 且 dif[-2]<=dea[-2]，或持续金叉）| BULLISH |
| MACD | 最近一次交叉为死叉 | BEARISH |
| MACD | 无交叉 | NEUTRAL |
| RSI | rsi[-1] > 70 | BEARISH |
| RSI | rsi[-1] < 30 | BULLISH |
| RSI | 30 ≤ rsi ≤ 70 | NEUTRAL |
| KDJ | K[-1] > D[-1] 且 K[-1] < 20（金叉超卖区）| BULLISH |
| KDJ | K[-1] < D[-1] 且 K[-1] > 80（死叉超买区）| BEARISH |
| KDJ | 其余 | NEUTRAL |
| MA | MA5 > MA20 > MA60 | BULLISH |
| MA | MA5 < MA20 < MA60 | BEARISH |
| MA | 其余 | NEUTRAL |
| MAVOL | vol[-1] > mavol5[-1] × 1.5 | VOLUME_HIGH |
| MAVOL | vol[-1] < mavol5[-1] × 0.5 | VOLUME_LOW |
| MAVOL | 其余 | NEUTRAL |

**综合信号（watchlist 总览页）**：

```
偏多：MACD==BULLISH AND 50 ≤ RSI[-1] ≤ 70 AND KDJ!=BEARISH
偏空：MACD==BEARISH AND RSI[-1] < 50 AND KDJ!=BULLISH
其余：NEUTRAL
```

---

## 4. API 端点详细设计

### 4.1 GET `/api/stocks`

**响应**：
```json
{
  "stocks": [
    {
      "stock_code": "SH.600519",
      "market": "A",
      "asset_type": "STOCK",
      "currency": "CNY",
      "lot_size": 100
    }
  ]
}
```

**实现**：调用 `StockRepository.get_active()`

---

### 4.2 GET `/api/kline`

**请求参数**：

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| code | str | ✅ | - | 股票代码，如 SH.600519 |
| period | str | ✅ | - | 1D / 1W / 1M |
| start | str | ❌ | 近1年 | YYYY-MM-DD |
| end | str | ❌ | 今天 | YYYY-MM-DD |
| adj | str | ❌ | qfq | qfq / raw |

**响应**（与 PRD §5.2 一致，新增 MAVOL）：
```json
{
  "stock_code": "SH.600519",
  "period": "1D",
  "adj_type": "qfq",
  "bars": [
    {
      "date": "2024-01-02",
      "open": 1800.0,
      "high": 1850.0,
      "low": 1795.0,
      "close": 1830.0,
      "volume": 1200000,
      "turnover": 2196000000.0,
      "pe_ratio": 28.5,
      "pb_ratio": 9.2,
      "ps_ratio": 11.4
    }
  ],
  "indicators": {
    "MA": {"MA5": [...], "MA20": [...], "MA60": [...]},
    "BOLL": {"upper": [...], "mid": [...], "lower": [...]},
    "MACD": {"dif": [...], "dea": [...], "macd": [...]},
    "RSI": {"RSI14": [...]},
    "KDJ": {"K": [...], "D": [...], "J": [...]},
    "MAVOL": {"MAVOL5": [...], "MAVOL10": [...], "MAVOL20": [...]}
  },
  "signals": {
    "BOLL": "neutral",
    "MACD": "bullish",
    "RSI": "bearish",
    "KDJ": "neutral",
    "MA": "bullish",
    "MAVOL": "volume_high"
  }
}
```

**错误响应**：
```json
{"detail": "Stock not found: XX.999999"}   // 404
{"detail": "Invalid period: 1H"}            // 422
```

---

### 4.3 GET `/api/watchlist/summary`

**响应**：
```json
{
  "summary": [
    {
      "stock_code": "SH.600519",
      "latest_close": 1830.0,
      "change_pct": 1.2,
      "pe_ratio": 28.5,
      "pb_ratio": 9.2,
      "signals": {
        "RSI": "bearish",
        "RSI_value": 72.3,
        "MACD": "bullish",
        "KDJ": "neutral",
        "composite": "neutral"
      }
    }
  ]
}
```

**实现**：对每只活跃股票取最近 60 个交易日的日K数据，计算各指标并取最新信号。

---

### 4.4 GET `/api/indicators`

**响应**：返回系统支持的指标清单，供前端动态配置用。

```json
{
  "indicators": [
    {"name": "MA", "label": "移动平均线", "type": "overlay", "params": {"periods": [5, 20, 60]}},
    {"name": "BOLL", "label": "布林带", "type": "overlay", "params": {"n": 20, "k": 2}},
    {"name": "MACD", "label": "MACD", "type": "panel", "params": {"fast": 12, "slow": 26, "signal": 9}},
    {"name": "RSI", "label": "RSI", "type": "panel", "params": {"n": 14}},
    {"name": "KDJ", "label": "KDJ", "type": "panel", "params": {"n": 9}},
    {"name": "MAVOL", "label": "量均线", "type": "volume_overlay", "params": {"periods": [5, 10, 20]}}
  ]
}
```

---

## 5. 前端组件划分

### 5.1 页面路由

```
/          → StockAnalysis 个股分析页
/watchlist → WatchlistPage 总览页
```

### 5.2 组件层级

```
App.jsx
├── React Router
│   ├── / → StockAnalysis.jsx
│   │   ├── 顶部导航栏
│   │   │   ├── StockSelector.jsx      # 下拉选择活跃股票
│   │   │   ├── PeriodSelector.jsx     # 1D/1W/1M 切换
│   │   │   └── TimeRangeSelector.jsx  # 近3月/近6月/近1年/近3年/自定义
│   │   ├── MainChart.jsx              # K线主图（ECharts）
│   │   │   ├── 蜡烛图
│   │   │   ├── MA5/MA20/MA60 叠加线
│   │   │   ├── BOLL 三轨（上轨/中轨/下轨 + markArea 着色）
│   │   │   └── 成交量柱 + MAVOL5/MAVOL10 叠加
│   │   ├── MACDPanel.jsx              # MACD 副图
│   │   │   ├── DIF/DEA 曲线
│   │   │   ├── MACD 柱（正红负绿）
│   │   │   ├── 交叉点标记（markPoint ▲▼）
│   │   │   └── SignalTag.jsx（右上角信号标签）
│   │   ├── RSIPanel.jsx               # RSI 副图
│   │   │   ├── RSI14 曲线
│   │   │   ├── 70/30 参考线（markLine）
│   │   │   ├── 70~100 浅红 markArea + "超买"文字
│   │   │   ├── 0~30 浅绿 markArea + "超卖"文字
│   │   │   └── SignalTag.jsx
│   │   ├── KDJPanel.jsx               # KDJ 副图
│   │   │   ├── K/D/J 曲线
│   │   │   ├── 80/20 参考线
│   │   │   ├── 80~100 浅红 markArea + "超买"
│   │   │   ├── 0~20 浅绿 markArea + "超卖"
│   │   │   ├── K/D 交叉点标记
│   │   │   └── SignalTag.jsx
│   │   └── BottomBar.jsx              # 底部信息条
│   │
│   └── /watchlist → WatchlistPage.jsx
│       ├── 股票表格（各指标信号列）
│       └── SignalTag.jsx（内嵌各单元格）
│
└── SignalTag.jsx                       # 通用信号标签（绿/红/灰/橙）
```

### 5.3 SignalTag 规范

```jsx
// 输入: signal="bullish"|"bearish"|"neutral"|"volume_high"|"volume_low"
// 输入: label="金叉·多头信号" 等文字
// 输出: 带背景色的小标签徽章

const COLOR_MAP = {
  bullish:     { bg: "#e8f5e9", text: "#2e7d32", icon: "🟢" },
  bearish:     { bg: "#ffebee", text: "#c62828", icon: "🔴" },
  neutral:     { bg: "#f5f5f5", text: "#616161", icon: "⚖️" },
  volume_high: { bg: "#fff3e0", text: "#e65100", icon: "🔊" },
  volume_low:  { bg: "#f5f5f5", text: "#9e9e9e", icon: "🔇" },
}
```

---

## 6. B-1 修复方案

### 6.1 问题定位

扫描所有文件后，**字符串匹配式异常判断**出现在以下位置：

| 文件 | 行 | 问题描述 |
|------|----|---------|
| `main.py` | L269-273 | `str(e).lower()` 字符串关键字检测连接错误 |
| `core/rate_limiter.py` | L95-100 | `str(e).lower()` 检测可重试错误（同时有 type 名称检测）|
| `core/rate_limiter.py` | L165-171 | 同上（`GeneralRateLimiter`）|

### 6.2 修复策略

富途 SDK (`futu`) 的连接相关异常类层级：

```
Exception
└── Exception（futu SDK 直接 raise 或包装为通用 Exception）
    ├── ConnectionError（Python 内置）
    ├── TimeoutError（Python 内置）
    └── futu.common.err 中的自定义异常（需运行时确认）
```

由于富途 SDK 的连接错误可能包装为通用 `Exception` 且没有稳定的专用子类，**正确的 isinstance 修复策略**为：

1. **`main.py`**：保留字符串匹配作为后备，但优先 isinstance 检测 Python 内置连接类异常；将判断封装为独立函数 `_is_connection_error(e: Exception) -> bool`，同时检测 `isinstance(e, (ConnectionError, TimeoutError, OSError))` 以及消息字符串（作为 fallback）
2. **`core/rate_limiter.py`**：已有 `type(e).__name__` 检测，已是正确做法；将 `str(e).lower()` 的 fallback 保留作为补充，但消息来源限制为更精确的关键词

**最终修复**：将 B-1 的 isinstance 修复聚焦在 `main.py`，将判断逻辑封装为 `_is_connection_error()` 函数：

```python
def _is_connection_error(e: Exception) -> bool:
    """
    判断是否为 OpenD 连接类异常。
    优先使用 isinstance 类型检测，str 匹配作为 fallback（应对 futu SDK 包装的通用异常）。
    """
    if isinstance(e, (ConnectionError, TimeoutError, OSError)):
        return True
    err_str = str(e).lower()
    return any(kw in err_str for kw in (
        "connect", "connection", "disconnect", "timeout",
        "opend", "network", "errno", "broken pipe",
    ))
```

---

## 7. 实现顺序与工作量估算

| 顺序 | 模块 | 内容 | 估计工时 |
|------|------|------|---------|
| 1 | I10 | B-1 Bug 修复（`main.py` + rate_limiter.py 整理）| 0.5h |
| 2 | I1 | `core/indicator_engine.py`（7个指标 + 信号）| 3h |
| 3 | I2 | `api/` 后端（FastAPI + 4端点 + kline_service）| 2h |
| 4 | I3 | 前端脚手架 + K线主图（蜡烛图+成交量）| 2h |
| 5 | I4 | 主图叠加（MA + BOLL + 区间背景色）| 1h |
| 6 | I5 | 副图面板（MACD/RSI/KDJ + 信号标签 + 交叉标记）| 2h |
| 7 | I6 | 控制栏（股票/周期/时间范围 + 60s 自动刷新）| 1h |
| 8 | I7 | 底部信息条 | 0.5h |
| 9 | I8 | Watchlist 总览页 | 1h |
| 10 | I9 | systemd 部署配置 | 0.5h |
| **合计** | | | **~13.5h** |

---

## 8. 关键约束确认

- **严格只读**：`api/` 层所有代码不调用任何 `Repository` 的写入方法（`insert_many`、`upsert_many` 等）
- **指标计算内存化**：`IndicatorEngine` 纯函数设计，无状态，无 IO
- **复权透传**：`adj=qfq` 时调用 `AdjustmentService.get_adjusted_klines()`，`adj=raw` 时直接调用 `KlineRepository.get_bars()`
- **CORS**：开发模式通过 FastAPI `CORSMiddleware` 允许 `localhost:5173`（Vite 默认端口）
- **生产模式**：`WEB_MODE=production` 时 `app.mount("/", StaticFiles(directory="web/dist"))` serve 前端产物
- **端口配置**：`WEB_PORT`（默认 8000）通过 `.env` 配置，前端 `VITE_API_BASE` 环境变量配置 API 地址

---

*设计文档 v1.0，2026-03-18，Dev*
