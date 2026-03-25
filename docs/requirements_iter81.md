# 迭代8.1-patch 需求文档 — VPA 空仓阻力线 + 图例按钮化

**文档版本**：v1.0
**日期**：2026-03-24
**状态**：已确认，研发进行中
**作者**：PM（产品经理）
**说明**：老板已口头确认迭代8.1-patch 范围（2026-03-24），含 FEAT-resistance 和 FEAT-legend-toggle 两个功能点，可安排研发执行。

---

## 一、迭代背景与目标

### 背景

迭代8（UI 体验优化）范围已锁定为纯前端 UI 优化，以下两个功能点因涉及新功能扩展（后端+前端），不适合混入迭代8，故单独提取为 iter8.1-patch 独立交付：

1. **FEAT-resistance（VPA 副图新增空仓阻力线）**：在 VPADefenderPanel 左 Y 轴新增"空仓阻力线"曲线（橙黄色），与现有蓝色防守线形成"上有阻力、下有支撑"的双线通道视图。算法基于历史最低收盘价 + ATR 倍数，"只降不升"约束，不参与综合信号计算。涉及后端 `indicator_engine.py`、API 透传层和前端 `VPADefenderPanel.jsx`。

2. **FEAT-legend-toggle（图例按钮化 — 点击切换曲线显示/隐藏）**：将各指标副图（MACD / RSI / KDJ / VPA-Defender）右侧 ChartSidebar 的图例条目升级为可交互按钮。用户点击图例，可实时切换对应 ECharts series 曲线的显示/隐藏，inactive 状态呈删除线+半透明样式。纯前端实现，不涉及任何后端改动。

### 目标

- 为 VPA-Defender 副图补全"空仓阻力线"能力，形成防守线（多头止损）+ 阻力线（空头压力）双线通道
- 提升用户图表阅读效率：按需隐藏不感兴趣的指标曲线，减少视觉噪音
- 以上两点均不改变综合信号计算逻辑，不影响已验收的 useChartSync 跨图联动

---

## 二、§1 FEAT-resistance：VPA 副图新增空仓阻力线

**功能描述**：在 VPADefenderPanel 左 Y 轴（价格轴）新增"空仓阻力线"曲线，与现有防守线配合，形成"上有阻力、下有支撑"的双线通道视图。

---

### 1.1 后端改动 — `core/indicator_engine.py`

1. `calc_vpa_defender` 方法新增 `resistance_line` 序列计算（复用已有 `atr_series`，无需新增参数）。
2. 返回字典新增 `"resistance_line"` 键，类型与 `stop_line` 相同（`List[Optional[float]]`）。
3. 同步更新 `IndicatorResult.VPA_DEFENDER` 注释（无类型变更，dict 结构天然支持新增键）。

**算法**：

- `running_min_close` 追踪历史最低收盘价（只降不升）
- `resistance_line[i] = running_min_close + 3.0 × ATR[i]`
- "只降不升"约束：若候选值 > 上一根值，保持上一根值

---

### 1.2 后端改动 — `api/` 路由/服务

`api/services/kline_service.py`（或对应透传逻辑）：将 `vpa_defender` 返回字典中的 `resistance_line` 字段透传至 API 响应，与 `stop_line` 并列。

**新字段**：`resistance_line: List[float | null]`（与 `stop_line` 字段格式完全一致）

无需新增路由，无需修改 API schema 文档结构（JSON 键新增向下兼容）。

---

### 1.3 前端改动 — `web/src/components/VPADefenderPanel.jsx`

1. **新增阻力线曲线**（左 Y 轴，与防守线共享价格坐标系）：
   - 颜色：**橙黄色 `#ffa726`**（与防守线蓝色 `#42a5f5` 形成冷暖对比，阻力线偏暖）
   - 线型：实线，线宽 1.5（比防守线 2px 细，降低视觉权重）
   - 数据来源：`vpaData.resistance_line`
   - 系列名称：`'阻力线'`

2. **`HELP_ITEMS` 新增说明条目**（新手浮层）：
   - `iconType: 'line'`，`color: '#ffa726'`
   - `text: '<b>橙黄（空仓阻力线）</b>：追踪历史最低价上方 ATR 倍数距离，只降不升。价格长期在线下方运行，说明上方压力持续；价格有效突破阻力线，可关注趋势反转信号。'`
   - 说明：**不含任何买卖操作指令**（遵守 CLAUDE.md 迭代裁定规范）

3. **右侧 ChartSidebar 图例**（`legendItems`）：
   - 新增阻力线图例条目，`type: 'line'`，`color: '#ffa726'`，`label: '阻力线'`

4. **颜色区分说明**：

   | 曲线 | 颜色 | 含义 |
   |------|------|------|
   | 防守线（stop_line） | 蓝色 `#42a5f5` | 多头动态止损参考，"守住就没破位" |
   | 阻力线（resistance_line） | 橙黄 `#ffa726` | 空仓动态压力参考，"突破才能反转" |
   | 收盘价曲线 | 灰色 `#9e9e9e` | 价格走势参考 |

---

### 1.4 信号说明

**四象限信号：不变**。阻力线仅作为视觉参考曲线，不参与 `signal_series` 计算，不影响综合信号。（若后续使用一段时间后老板决定纳入信号，作为独立迭代另行规划。）

---

### 1.5 验收标准（AC）

- [ ] AC-resistance-1：VPA 副图左 Y 轴展示橙黄色阻力线，与蓝色防守线、灰色收盘价共三条曲线同轴显示。
- [ ] AC-resistance-2：阻力线在价格持续下跌阶段随之下移，在价格反弹时保持水平（不上移），视觉验证"只降不升"特性。
- [ ] AC-resistance-3：阻力线与防守线"上下夹击"形态正常——多数情况下防守线在下、阻力线在上，形成价格通道。
- [ ] AC-resistance-4：hover 浮层（tooltip）显示阻力线当日数值，标注为"阻力线"。
- [ ] AC-resistance-5：`[?]` 说明浮层中新增阻力线说明条目，颜色为橙黄，说明文案不含买卖指令。
- [ ] AC-resistance-6：右侧 ChartSidebar 图例新增阻力线（橙黄横实线 + "阻力线"文字）。
- [ ] AC-resistance-7：VPA 折叠/展开后阻力线正常渲染，不出现闪烁或数据丢失。
- [ ] AC-resistance-8：各股票（A股/港股/美股）阻力线均可正常计算，不出现全 null 序列或异常值。

---

## 三、§2 FEAT-legend-toggle：图例按钮化（点击切换曲线显示/隐藏）

### 3.1 功能描述

将各指标副图面板（MACD / RSI / KDJ / VPA-Defender）右侧 ChartSidebar 中的 **图例条目（legendItems）升级为可交互按钮**。用户点击图例条目，可实时切换对应指标曲线的显示或隐藏，同一指标面板中其他曲线不受影响。

**典型用户场景**：
- 用户只想看 DIF 线和 DEA 线的金叉/死叉，隐藏 MACD 柱，让零轴线更清晰
- 用户在 KDJ 面板中隐藏波动剧烈的 J 线，只看 K/D 两线趋势
- 用户在 VPA-Defender 面板中隐藏 OBV 均线，只看 OBV 原始波动

---

### 3.2 各 Panel 的 ECharts Series Name 与 legendItems label 对应关系

#### MACD 面板（`MACDPanel.jsx`）

| ECharts series name | 当前 legendItems label | 类型 | 是否可切换 |
|---------------------|----------------------|------|----------|
| `'DIF'` | `'DIF'` | 折线（line） | ✅ 可切换 |
| `'DEA'` | `'DEA'` | 折线（line） | ✅ 可切换 |
| `'MACD柱'` | `'柱(正)'` + `'柱(负)'`（共用同一 series） | 柱状（bar） | ✅ 可切换（两个图例条目控制同一 series，统一联动） |
| 无独立 series（markPoint 挂载在 DIF 上）| `'金叉'` / `'死叉'` | 圆形标记 | ❌ 不可独立切换（依附 DIF series，隐藏 DIF 后自动消失） |

> **说明**：`'柱(正)'` 和 `'柱(负)'` 共用 series `'MACD柱'`，点击任意一个均控制同一 series 的显示/隐藏，视觉上两个按钮会同步进入 inactive 状态。`'金叉'`/`'死叉'` 图例条目保持纯展示，不渲染为按钮。

#### RSI 面板（`RSIPanel.jsx`）

| ECharts series name | 当前 legendItems label | 类型 | 是否可切换 |
|---------------------|----------------------|------|----------|
| `'RSI14'` | `'RSI(14)'` | 折线（line） | ✅ 可切换 |
| 无独立 series（markArea 挂载在 RSI14 上）| `'超买区(卖)'` / `'超卖区(买)'` | 区域背景 | ❌ 不可独立切换（依附 RSI14 series） |

#### KDJ 面板（`KDJPanel.jsx`）

| ECharts series name | 当前 legendItems label | 类型 | 是否可切换 |
|---------------------|----------------------|------|----------|
| `'K'` | `'K线'` | 折线（line） | ✅ 可切换 |
| `'D'` | `'D线'` | 折线（line） | ✅ 可切换 |
| `'J'` | `'J线'` | 折线（dashed） | ✅ 可切换 |
| 无独立 series（markPoint 挂载在 K 上）| `'金叉'` / `'死叉'` | 圆形标记 | ❌ 不可独立切换（依附 K series） |

> **注意**：legendItems label（`'K线'`）与 series name（`'K'`）不一致，需在 legendItems 中通过 `seriesName` 字段指定实际 series name，不改变 label 展示文字。

#### VPA-Defender 面板（`VPADefenderPanel.jsx`）

| ECharts series name | 当前 legendItems label | 类型 | 是否可切换 |
|---------------------|----------------------|------|----------|
| `'收盘价'` | `'收盘价'` | 折线（line） | ✅ 可切换 |
| `'防守线'` | `'防守线'` | 折线（line） | ✅ 可切换 |
| `'OBV'` | `'OBV'` | 折线（line） | ✅ 可切换 |
| `'OBV均线'` | `'OBV均线'` | 折线（dashed） | ✅ 可切换 |

> **特点**：VPA 面板四条 series name 与 legendItems label **完全一致**，无需额外字段映射。

---

### 3.3 推荐技术方案

**方案：React State 驱动 series visibility（Option B — 最简化，数据流清晰）**

#### 3.3.1 数据结构扩展

**`legendItems` 每条新增可选 `seriesName` 字段**：

```js
// 现有结构
{ color, type, label }

// 扩展后结构
{ color, type, label, seriesName?: string }
// seriesName 存在 → 渲染为可点击按钮，对应 ECharts series name
// seriesName 缺省 → 纯展示图例，不可点击（如金叉/死叉/超买区）
```

**示例（StockAnalysis.jsx 中 MACD 图例配置修改）**：

```js
const macdSidebarLegend = [
  { color: C.dif,        type: 'line',   label: 'DIF',    seriesName: 'DIF'    },
  { color: C.dea,        type: 'line',   label: 'DEA',    seriesName: 'DEA'    },
  { color: C.macdBarPos, type: 'bar',    label: '柱(正)', seriesName: 'MACD柱' },
  { color: C.macdBarNeg, type: 'bar',    label: '柱(负)', seriesName: 'MACD柱' },  // 与上行同 seriesName，联动切换
  { color: C.buy,        type: 'circle', label: '金叉'                          },  // 纯展示，无 seriesName
  { color: C.sell,       type: 'circle', label: '死叉'                          },
]
```

**KDJ 图例配置（需 seriesName 显式映射）**：

```js
const kdjSidebarLegend = [
  { color: C.kLine, type: 'line',   label: 'K线', seriesName: 'K' },
  { color: C.dLine, type: 'line',   label: 'D线', seriesName: 'D' },
  { color: C.jLine, type: 'dashed', label: 'J线', seriesName: 'J' },
  { color: C.buy,   type: 'circle', label: '金叉'                  },
  { color: C.sell,  type: 'circle', label: '死叉'                  },
]
```

#### 3.3.2 ChartSidebar 改动

新增 `onLegendToggle: (seriesName: string) => void` prop（可选）。

legendItems 渲染逻辑按 `seriesName` 是否存在分支：
- **有 `seriesName`**：渲染为 `<button>` 样式，内部维护 `activeMap: { [seriesName]: boolean }` 状态（初始全为 true，`useReducer` 或 `useState` 管理）
  - active 样式：正常颜色（现有样式不变）
  - inactive 样式：文字 `textDecoration: 'line-through'`，LegendMark 和文字 `opacity: 0.35`，背景微灰
  - 点击时切换 activeMap 对应 seriesName 的布尔值，并调用 `onLegendToggle(seriesName)`
  - **注意**：同一 `seriesName`（如 `'MACD柱'`）可能对应多个 legendItems，点击任意一个后，所有该 seriesName 的条目 activeMap 状态同步切换
- **无 `seriesName`**：保持当前纯展示 `<div>` 渲染，不响应点击

折叠按钮 `onToggle` prop 逻辑不变，与本功能正交。

#### 3.3.3 StockAnalysis 改动（各层 Panel 连接）

StockAnalysis.jsx 中每个 ChartSidebar 新增 `onLegendToggle` 回调，通过 panel ref 调用 ECharts 实例的 `dispatchAction`：

```jsx
{/* MACD 副图 */}
<ChartSidebar
  ...
  legendItems={macdSidebarLegend}
  onLegendToggle={(seriesName) => {
    macdRef.current?.getEchartsInstance()
      ?.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
  }}
/>
```

同理为 RSI / KDJ / VPA 三个面板的 ChartSidebar 各加对应回调。

#### 3.3.4 各 Panel option 改动（ECharts legend 注册）

ECharts 的 `dispatchAction('legendToggleSelect')` 依赖 legend 组件中有对应 series name 的注册才能生效。各 Panel 需在 option 中新增 `legend` 配置（`show: false`，仅做注册，不渲染 UI）：

```js
// MACDPanel option 新增：
legend: {
  show: false,
  data: ['DIF', 'DEA', 'MACD柱'],
},

// KDJPanel option 新增：
legend: {
  show: false,
  data: ['K', 'D', 'J'],
},

// RSIPanel option 新增：
legend: {
  show: false,
  data: ['RSI14'],
},

// VPADefenderPanel 已有 legend: { show: false }，补充 data 字段：
legend: {
  show: false,
  data: ['收盘价', '防守线', 'OBV', 'OBV均线'],
},
```

#### 3.3.5 折叠后再展开的状态保持

**问题**：Panel 展开时 ECharts 实例重建（`notMerge: true`），`dispatchAction` 产生的 legend 选中状态会被重置，导致用户折叠前已隐藏的 series 在展开后又重新显示，与 ChartSidebar 的 activeMap 视觉状态不一致。

**解决方案**：
- ChartSidebar 的 `activeMap` 是 React state，折叠展开不会重置（组件始终挂载），视觉状态保持。
- Panel 展开后（ECharts 实例刚挂载），需将当前 activeMap 中值为 `false` 的 series 重新 dispatchAction 一次。
- 实现方式：在 `useEffect` 中监听 `collapsed` 从 `true → false` 的变化，展开后遍历 activeMap，对所有 inactive series 调用 `dispatchAction('legendToggleSelect')`。
- **具体位置**：可在 StockAnalysis.jsx 中，每个 panel 展开时触发同步逻辑；或在 ChartSidebar 新增 `onPanelExpand()` 回调，由 ChartSidebar 主动通知父组件做同步。

建议用 `onPanelExpand` 回调方式（职责更清晰），StockAnalysis 中在 `togglePanel('MACD')` 时若变更为展开，随即遍历当前 activeMap 同步 dispatchAction。

---

### 3.4 验收标准（AC）

- [ ] AC-legend-toggle-1：MACD / RSI / KDJ / VPA 四个副图，右侧 ChartSidebar 中有 `seriesName` 的图例条目可被点击，无 `seriesName` 的条目（金叉/死叉/超买区/超卖区）不可点击（光标无 `pointer`，无点击响应）。
- [ ] AC-legend-toggle-2：点击任意可切换图例，对应 ECharts series 曲线立即消失；再次点击，曲线重新出现。
- [ ] AC-legend-toggle-3：切换一条 series 时，同一面板其他 series 的显示状态不受影响。
- [ ] AC-legend-toggle-4：图例按钮 inactive 状态下，图例图标和文字均呈现半透明+删除线样式，与 active 状态有明显视觉区分。
- [ ] AC-legend-toggle-5：`'MACD柱'` 对应的两个图例条目（`'柱(正)'` 和 `'柱(负)'`）点击任意一个，两个条目均同步进入 inactive 状态，MACD 柱 series 整体隐藏；再次点击其中任意一个，两个条目均恢复 active，MACD 柱重新显示。
- [ ] AC-legend-toggle-6：副图折叠后再展开，ChartSidebar 图例按钮的 active/inactive 视觉状态与折叠前一致，ECharts 图表中 series 显示状态同步恢复（之前隐藏的 series 仍为隐藏）。
- [ ] AC-legend-toggle-7：各面板默认加载时，所有图例按钮均为 active 状态（全部曲线显示），不影响当前默认渲染行为。
- [ ] AC-legend-toggle-8：切换股票或刷新数据后，图例状态重置为全 active（新股票重新开始，不保留上一只股票的隐藏状态）。
- [ ] AC-legend-toggle-9：hover 十字线联动（useChartSync）正常工作，曲线隐藏后联动不报错。
- [ ] AC-legend-toggle-10：折叠按钮（`∧`/`∨`）功能不受影响，与图例切换独立运作。

---

## 四、影响文件汇总

### §1 FEAT-resistance 影响文件

| 文件 | 修改内容 |
|------|---------|
| `core/indicator_engine.py` | `calc_vpa_defender` 新增 `resistance_line` 序列计算（约 15 行）；返回字典新增 `"resistance_line"` 字段 |
| `api/services/kline_service.py`（或透传层） | 透传 `resistance_line` 字段至 API 响应 |
| `web/src/components/VPADefenderPanel.jsx` | 新增橙黄阻力线曲线；`HELP_ITEMS` 新增说明条目；`legendItems` 新增图例 |

**不涉及改动**：
- 其他副图组件（MACD / RSI / KDJ）
- `useChartSync.js`（联动逻辑不变）
- 综合信号（`compositeSignal.js`、`calc_composite_signal`）
- 四象限 `signal_series` 计算逻辑

### §2 FEAT-legend-toggle 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/ChartSidebar.jsx` | legendItems 渲染逻辑：有 `seriesName` 的条目改为 `<button>`；新增 `activeMap` state（`useState`）；新增 `onLegendToggle` prop；inactive 样式（删除线+半透明） |
| `web/src/pages/StockAnalysis.jsx` | `macdSidebarLegend` / `kdjSidebarLegend` / `rsiSidebarLegend` / `vpaSidebarLegend` 各条目补充 `seriesName` 字段；各副图 ChartSidebar 调用处新增 `onLegendToggle` 回调（通过 panel ref 调用 ECharts dispatchAction）；Panel 展开时触发 legend 状态同步逻辑 |
| `web/src/components/MACDPanel.jsx` | option 新增 `legend: { show: false, data: ['DIF', 'DEA', 'MACD柱'] }` |
| `web/src/components/RSIPanel.jsx` | option 新增 `legend: { show: false, data: ['RSI14'] }` |
| `web/src/components/KDJPanel.jsx` | option 新增 `legend: { show: false, data: ['K', 'D', 'J'] }` |
| `web/src/components/VPADefenderPanel.jsx` | option 中已有 `legend: { show: false }`，补充 `data: ['收盘价', '防守线', 'OBV', 'OBV均线']` |

**不涉及改动**：
- 所有后端文件（纯前端交互功能）
- `useChartSync.js`（跨图联动逻辑不变）
- `compositeSignal.js` / `indicator_engine.py`（指标计算逻辑不变）
- `BottomBar.jsx`、`SignalBanner.jsx`、`SignalTag.jsx` 等其他组件

---

## 五、迭代裁定记录

| 日期 | 迭代 | 裁定内容 | 背景 |
|------|------|---------|------|
| 2026-03-24 | 迭代8.1-patch | **老板口头确认 iter8.1-patch 范围**，含 FEAT-resistance（VPA 副图新增空仓阻力线）和 FEAT-legend-toggle（图例按钮化）两个功能点，可安排研发执行 | 两功能点在迭代8 PRD（requirements_iter8.md §七、§八）预起草完毕，老板确认后提取为独立迭代 |
| 2026-03-24 | 迭代8.1-patch | **FEAT-resistance 阻力线不参与综合信号计算**，仅作为视觉参考曲线，与四象限信号体系完全独立 | 遵守 2026-03-23 迭代7裁定：VPA-Defender 信号不参与综合信号计算，两套体系独立并存 |
| 2026-03-24 | 迭代8.1-patch | **FEAT-legend-toggle 为纯前端实现**，不涉及任何后端文件改动，不影响指标计算逻辑与 useChartSync 联动 | 功能定性为 UI 交互增强，边界清晰 |

---

*文档结束 — docs/requirements_iter81.md v1.0 — 2026-03-24*
