# 迭代7 Code Review 报告

**日期**: 2026-03-23
**审查人**: QA 工程师
**范围**: BUG-crosshair + FEAT-vpa-defender 全部改动文件

---

## 1. 审查总结

| 类别 | 数量 |
|------|------|
| BUG（必须修复） | 1 |
| 建议（建议改进） | 2 |
| 通过 | 其余所有检查项 |

**总体评价**：代码质量良好，算法实现正确，架构与现有代码风格一致。发现 1 个需要修复的问题和 2 个改进建议。

---

## 2. BUG 清单

### BUG-CR7-01：VPADefenderPanel 缺少 [?] 新手解释浮层（P0）

**文件**: `web/src/components/VPADefenderPanel.jsx`
**严重性**: P0（违反迭代裁定规范）

**问题描述**：
PRD §4.6.3 明确要求面板标题栏包含 **[?] 图标**，点击展开解释浮层，默认隐藏。迭代4+裁定规范也强制要求"每个指标图表必须附带新手解释浮层"。

当前 `VPADefenderPanel.jsx` 的标题行（第 254~289 行）仅有参数文字 `VPA-Defender(22,3.0,20)` + 信号标签 + 折叠按钮，**没有 [?] 图标和浮层组件**。

虽然 `StockAnalysis.jsx` 中的 `ChartSidebar` 提供了 `vpaSidebarGuide` 解释文字（第 252~258 行），但这是侧边栏的图例说明，不是 PRD 要求的面板内 [?] 浮层。现有 MACD/RSI/KDJ 面板也各自有独立的 [?] 浮层（在迭代4 FEAT-01 中实现）。

**修复方案**：在 `VPADefenderPanelInner` 的标题行中新增 [?] 图标 + 浮层组件，与 MACD/RSI/KDJ 面板的实现方式一致。浮层内容使用 PRD §4.6.3 定义的通俗文字。

> **注意**：审查了 MACDPanel.jsx，发现其标题行也没有 [?] 图标。推测 [?] 浮层可能是由其他组件（如 InfoOverlay 或类似组件）在 StockAnalysis 层注入的。需要 Dev 确认现有 [?] 浮层的实现位置，并确保 VPA 面板也接入同一机制。

---

## 3. 建议清单

### SUGGESTION-CR7-01：骨架屏未包含 VPA 面板占位

**文件**: `web/src/pages/StockAnalysis.jsx`，第 584 行
**严重性**: 低

```jsx
{[500, 200, 200, 200].map((h, i) => (
```

原有骨架屏为 4 个占位块（主图 500 + MACD/RSI/KDJ 各 200），新增 VPA 面板后应为 5 个：

```jsx
{[500, 200, 200, 200, 200].map((h, i) => (
```

**影响**：加载时骨架屏少一块，视觉不匹配，功能无影响。

### SUGGESTION-CR7-02：OBV_MA 计算可复用 `cls.ma()` 方法

**文件**: `core/indicator_engine.py`，第 391~394 行
**严重性**: 极低（代码风格建议）

`calc_vpa_defender` 中的 OBV_MA20 计算逻辑与 `cls.ma()` 方法完全一致（SMA），但手写了一遍而非复用。PRD §4.3.4 也提到"复用 `IndicatorEngine.ma()` 方法的逻辑"。

当前实现功能正确，仅建议代码简化：
```python
# 当前
obv_ma_series: List[Optional[float]] = [None] * size
for i in range(obv_ma_period - 1, size):
    window = obv_series[i - obv_ma_period + 1: i + 1]
    obv_ma_series[i] = round(sum(window) / obv_ma_period, 4)

# 建议
obv_ma_series = cls.ma(obv_series, obv_ma_period)
```

注意：`cls.ma()` 的精度为 `round(..., 4)`，当前手写版也是 4 位，一致。类型签名 `ma` 接收 `List[float]`，OBV 序列也是 `List[float]`，兼容。

---

## 4. 逐文件审查详情

### 4.1 `core/indicator_engine.py` ✅（1 建议）

#### 4.1.1 `atr()` 方法 ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 签名 | ✅ | `atr(high, low, close, period=22) -> List[Optional[float]]` |
| 第一根 TR | ✅ | 第 310~312 行：`i == 0` 时 `TR = high - low`，与 PRD 一致 |
| 标准 TR 公式 | ✅ | 第 314~317 行：`max(hl, hc, lc)` 三项取最大，正确 |
| SMA 计算 | ✅ | 第 321~323 行：滑动窗口 `sum/period`，正确 |
| 前 period-1 为 None | ✅ | 第 320~321 行：初始化 `[None] * size`，循环从 `period-1` 开始 |
| 空输入 | ✅ | 第 304~305 行：`size == 0` 返回 `[]` |
| 精度 | ✅ | `round(..., 6)` |

#### 4.1.2 `obv()` 方法 ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 签名 | ✅ | `obv(close, volume) -> List[float]` |
| OBV(0) = 0 | ✅ | 第 339 行：`result = [0.0]` |
| 三分支 | ✅ | 第 341~346 行：`>` 加、`<` 减、`==` 不变 |
| 空输入 | ✅ | 第 336~337 行返回 `[]` |

#### 4.1.3 `calc_vpa_defender()` 方法 ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 返回 4 个键 | ✅ | stop_line, obv, obv_ma20, signal |
| running_max_close | ✅ | 第 375~377 行：逐 bar `max(running_max_close, close[i])` |
| Stop_Line 只升不降 | ✅ | 第 382~385 行：二次遍历确保 `stop_line[i] >= stop_line[i-1]` |
| OBV_MA SMA | ✅ | 第 391~394 行：正确（建议复用 `cls.ma()`，见 SUGGESTION-CR7-02） |
| 信号判断逻辑 | ✅ | 第 405~408 行：与 PRD §4.4 伪代码完全一致 |
| 数据不足时 signal=None | ✅ | 第 401~402 行：`sl is None or om is None` 时 `continue` |
| 空 bars | ✅ | 第 361~362 行返回空结构 |

#### 4.1.4 `IndicatorResult` ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| VPA_DEFENDER 字段 | ✅ | 第 43 行：`VPA_DEFENDER: Dict[str, list] = field(default_factory=dict)` |

#### 4.1.5 `calculate_all()` 集成 ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 调用 calc_vpa_defender | ✅ | 第 572 行 |
| VPA_DEFENDER 存入结果 | ✅ | 第 642 行 |
| 信号映射 | ✅ | 第 621 行：`{1: "bullish", 2: "neutral", 3: "bearish", 4: "neutral"}`，与 PRD §4.5.3 一致 |
| signals dict 新增键 | ✅ | 第 631 行 |

#### 4.1.6 `calc_composite_signal()` 未改动 ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 函数体未变 | ✅ | 第 651~674 行完全未改动，仅读取 MACD/KDJ，不受 VPA_DEFENDER 影响 |

#### 4.1.7 无副作用 / 无交易指令 ✅

代码注释中无买卖操作指令，所有方法无 IO。

---

### 4.2 `api/services/kline_service.py` ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| VPA_DEFENDER 透传 | ✅ | 第 106 行：`"VPA_DEFENDER": indicator_result.VPA_DEFENDER` |
| 无数据时兼容 | ✅ | 第 62~70 行空 bars 返回空 dict，不涉及 VPA_DEFENDER |
| watchlist_summary 不受影响 | ✅ | 第 112~163 行未改动，composite 仅用 MACD/RSI/KDJ |

---

### 4.3 `api/routes/indicators.py` ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| VPA_DEFENDER 条目 | ✅ | 第 50~54 行 |
| name | ✅ | `"VPA_DEFENDER"` |
| label | ✅ | `"量价共振防守"` |
| type | ✅ | `"panel"` |
| params | ✅ | `{"atr_period": 22, "atr_multi": 3.0, "obv_ma_period": 20}` |

---

### 4.4 `web/src/hooks/useChartSync.js` ✅

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 所有图表注册 updateAxisPointer | ✅ | 第 58~74 行：`allCharts.forEach` 对每个图表注册，副图也参与 |
| 副图 → 主图联动 | ✅ | 每个图表 handler 里 `others.forEach(c => dispatchAction showTip)` |
| syncing 互斥标志 | ✅ | 第 51 行 `syncing`，第 61/66/70 行使用，防止循环触发 |
| 所有图表 DOM mouseleave | ✅ | 第 78~86 行：`allCharts.forEach` 对每个 DOM 注册 mouseleave |
| mouseleave hideTip | ✅ | 第 82 行：广播 `hideTip` 到其他图表 |
| dataZoom 不受影响 | ✅ | 第 88~106 行：dataZoom 逻辑结构不变，复用同一 `syncing` 标志 |
| cleanup 完整 | ✅ | 第 109~118 行：三类 handler 全部 off/removeEventListener |
| collapsed 依赖 | ✅ | 第 128 行：`collapsed` 在依赖数组中 |
| vpaRef 文档更新 | ✅ | 第 29 行注释已更新 subRefs 包含 vpaRef |

**潜在风险评估**：`syncing` 互斥标志在 `updateAxisPointer` 和 `dataZoom` 之间共享（同一 `syncing` 对象），这在同步代码中是安全的，因为 JavaScript 单线程不会在 `syncing.value = true` 和 `syncing.value = false` 之间被打断。✅ 无风险。

---

### 4.5 `web/src/components/VPADefenderPanel.jsx` ✅（1 BUG）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| forwardRef | ✅ | 第 29 行和第 100 行 |
| 面板高度 | ✅ | 第 293 行 `style={{ height: 280 }}`（与 MACDPanel 第 240 行一致，含 dataZoom 区域） |
| 双 Y 轴 | ✅ | 第 184~207 行：左轴价格，右轴 OBV |
| Stop_Line 配色 | ✅ | `#ef5350` 红色实线 width:2 |
| OBV 配色 | ✅ | `#42a5f5` 蓝色实线 width:1 |
| OBV_MA20 配色 | ✅ | `#ffa726` 橙色虚线 width:1 type:dashed |
| 信号色带 markArea | ✅ | 第 108~133 行实现，按信号值连续区段分段着色 |
| 最新信号标签 | ✅ | 第 261~272 行：标题行右侧显示信号 emoji + 文字 |
| tooltip | ✅ | 第 148~160 行：日期+防守线+OBV+OBV均线+信号 |
| OBV 右轴格式化 | ✅ | 第 199~203 行：亿/万单位自动转换 |
| 禁止滚轮缩放 | ✅ | 仅 slider，无 inside dataZoom |
| 折叠逻辑 | ✅ | 第 40~82 行：与 MACD/RSI/KDJ 模式一致 |
| **[?] 浮层** | **BUG** | **缺失**，见 BUG-CR7-01 |
| 禁止文字检查 | ✅ | 无"买入""卖出""持有""清仓""建仓" |

---

### 4.6 `web/src/pages/StockAnalysis.jsx` ✅（1 建议）

| 检查项 | 结果 | 说明 |
|--------|------|------|
| import VPADefenderPanel | ✅ | 第 32 行 |
| vpaRef 声明 | ✅ | 第 82 行 `useRef(null)` |
| useChartSync 包含 vpaRef | ✅ | 第 87 行 `[macdRef, rsiRef, kdjRef, vpaRef]` |
| collapsed 默认含 VPA | ✅ | 第 59 行 `{ MACD: false, RSI: false, KDJ: false, VPA: false }` |
| 折叠按钮组含 VPA | ✅ | 第 412 行 `['MACD', 'RSI', 'KDJ', 'VPA']` |
| VPA 按钮文字 | ✅ | 第 427 行 `'VPA 量价共振'` |
| VPA 面板位置（KDJ 下方） | ✅ | 第 528~558 行，在 KDJ 之后 |
| collapsed/expanded 双分支 | ✅ | collapsed → 仅标题；expanded → 面板+ChartSidebar |
| ChartSidebar 配置 | ✅ | 第 246~259 行 vpaSidebarLegend/Guide |
| ChartSidebar 浮层无禁止文字 | ✅ | 第 252~258 行内容通俗，无投资指令 |
| 骨架屏 | 建议 | 仍为 4 块，未包含 VPA 占位（SUGGESTION-CR7-01） |

---

## 5. 算法正确性抽查

### 5.1 ATR 手工验算

用 3 根 bar 验证（period=3）：
```
Bar 0: H=12, L=10, C=11  → TR = 12-10 = 2
Bar 1: H=13, L=10, C=12  → TR = max(3, |13-11|, |10-11|) = max(3,2,1) = 3
Bar 2: H=14, L=11, C=13  → TR = max(3, |14-12|, |11-12|) = max(3,2,1) = 3
ATR(2) = (2+3+3)/3 = 2.666667
```

代码逻辑（第 308~323 行）：
- Bar 0: `hl = 2`，`i == 0`，`tr_list = [2]` ✅
- Bar 1: `prev_close = 11`，`hl=3, hc=2, lc=1`，`tr_list = [2, 3]` ✅
- Bar 2: `prev_close = 12`，`hl=3, hc=2, lc=1`，`tr_list = [2, 3, 3]` ✅
- `ATR[2] = (2+3+3)/3 = 2.666667` ✅

### 5.2 OBV 手工验算

```
Bar 0: C=10, V=1000 → OBV = 0
Bar 1: C=11, V=2000 → 11>10 → OBV = 0+2000 = 2000
Bar 2: C=10, V=1500 → 10<11 → OBV = 2000-1500 = 500
Bar 3: C=10, V=3000 → 10==10 → OBV = 500
```

代码逻辑（第 339~346 行）：完全一致 ✅

### 5.3 Stop_Line 单调不减验证

代码第 374~385 行采用两遍扫描：
1. 第一遍（376~379）：`running_max_close - atr_multi * ATR` 计算原始值
2. 第二遍（382~385）：`if stop_line[i] < stop_line[i-1]: stop_line[i] = stop_line[i-1]`

两遍扫描确保单调不减 ✅

### 5.4 四象限信号边界值

代码第 405~408 行：
```python
if c > sl:     # 严格大于
    signal = 1 if o > om else 2
else:          # c <= sl（包含等于）
    signal = 4 if o > om else 3
```

- `close == stop_line` → 进入 else → 状态3或4 ✅（与 PRD "close <= Stop_Line" 一致）
- `obv == obv_ma` → `o > om` 为 False → 状态2或3 ✅（与 PRD "OBV <= OBV_MA20" 一致）

---

## 6. 结论

| 项 | 状态 |
|----|------|
| BUG-crosshair (useChartSync.js) | ✅ 通过 CR |
| FEAT-vpa-defender 后端 (indicator_engine.py) | ✅ 通过 CR |
| FEAT-vpa-defender API (kline_service.py + indicators.py) | ✅ 通过 CR |
| FEAT-vpa-defender 前端 (VPADefenderPanel.jsx) | ⚠️ 1 BUG（缺少 [?] 浮层） |
| 页面集成 (StockAnalysis.jsx) | ✅ 通过 CR（1 建议） |
| 回归风险 | ✅ 低风险：calc_composite_signal 未改动，现有指标数据流不变 |

**需要 Dev 修复**：BUG-CR7-01（VPADefenderPanel 缺少 [?] 新手解释浮层）

**建议改进**（不阻塞发布）：SUGGESTION-CR7-01（骨架屏 +1 块）、SUGGESTION-CR7-02（OBV_MA 复用 ma()）
