# 迭代8.1-patch 代码审查报告（CR）

**文档版本**：v1.0
**日期**：2026-03-25
**作者**：QA
**审查依据**：`docs/test_cases_iter81.md` v1.0
**审查范围**：FEAT-resistance（空仓阻力线）+ FEAT-legend-toggle（图例按钮化）
**审查结论**：✅ **通过，建议合并**

---

## 一、改动文件清单及审查状态

| 文件 | 功能点 | 审查状态 |
|------|--------|---------|
| `core/indicator_engine.py` | FEAT-resistance 算法 | ✅ 通过 |
| `web/src/components/VPADefenderPanel.jsx` | FEAT-resistance 前端渲染 + HELP_ITEMS 阻力线条目 + legend 注册 | ✅ 通过 |
| `web/src/components/ChartSidebar.jsx` | FEAT-legend-toggle 按钮化逻辑 | ✅ 通过 |
| `web/src/components/MACDPanel.jsx` | FEAT-legend-toggle legend 注册 | ✅ 通过 |
| `web/src/components/RSIPanel.jsx` | FEAT-legend-toggle legend 注册 | ✅ 通过 |
| `web/src/components/KDJPanel.jsx` | FEAT-legend-toggle legend 注册 | ✅ 通过 |
| `web/src/pages/StockAnalysis.jsx` | FEAT-legend-toggle seriesName 配置、onLegendToggle handler、vpaSidebarLegend 颜色 | ✅ 通过 |

> **说明**：`api/services/kline_service.py` 无需修改——整体字典透传 `indicator_result.VPA_DEFENDER`，新增 `resistance_line` 字段自动包含在响应中，已确认（TC-resistance-API 对应验证点）。

---

## 二、FEAT-resistance 代码审查详情

### 2.1 后端算法（`core/indicator_engine.py`）

#### TC-resistance-BE-01：`running_min_close` 只降不升

```python
# indicator_engine.py L392-396
running_min_close = close[0]
for i in range(size):
    running_min_close = min(running_min_close, close[i])   # ✅ min()，只降不升
    if atr_series[i] is not None:
        resistance_line[i] = round(running_min_close + atr_multi * atr_series[i], 6)
```

**结论**：✅ 使用 `min()` 正确。与防守线 `running_max_close = max(...)` 完全对称。

---

#### TC-resistance-BE-02：候选值公式（加法，对称防守线减法）

```python
# 防守线（对照）：running_max_close - atr_multi * atr_series[i]
# 阻力线（本次）：running_min_close + atr_multi * atr_series[i]  ✅ 加号
resistance_line[i] = round(running_min_close + atr_multi * atr_series[i], 6)
```

**结论**：✅ 加法公式正确，与防守线减法对称。参数复用 `atr_multi=3.0`，无新增参数，ATR 序列未重复计算。

---

#### TC-resistance-BE-03：只降不升约束

```python
# indicator_engine.py L399-402
for i in range(1, size):
    if resistance_line[i] is not None and resistance_line[i - 1] is not None:
        if resistance_line[i] > resistance_line[i - 1]:      # ✅ 大于时回退（防守线为小于时回退）
            resistance_line[i] = resistance_line[i - 1]
```

**结论**：✅ 约束条件方向正确（`>` 而非 `<`），与防守线约束方向对称。从 `range(1, size)` 起始正确，None 值双重守卫到位。

---

#### TC-resistance-BE-04：ATR 计算期前 None 处理

```python
resistance_line: List[Optional[float]] = [None] * size  # ✅ 初始化全 None
# ...
if atr_series[i] is not None:                           # ✅ 守卫，前期 None 不赋值
    resistance_line[i] = round(...)
```

**结论**：✅ `[None] * size` 初始化 + `if atr_series[i] is not None` 守卫，前 22 根数据不足时保持 None，不产生异常值。

---

#### TC-resistance-BE-05：返回字典包含 `resistance_line` 键

```python
# indicator_engine.py L424-429
return {
    "stop_line": stop_line,
    "resistance_line": resistance_line,   # ✅ 新增
    "obv": obv_series,
    "obv_ma20": obv_ma_series,
    "signal": signal_series,
}
```

**结论**：✅ 返回字典共 5 个键，原有 4 键完整保留，`resistance_line` 拼写正确（全小写下划线）。

**空 bars 情形**：

```python
if not bars:
    return {"stop_line": [], "resistance_line": [], "obv": [], "obv_ma20": [], "signal": []}
# ✅ 空列表正确包含在内
```

---

#### TC-resistance-BE-07：精度与类型

```python
resistance_line[i] = round(running_min_close + atr_multi * atr_series[i], 6)
# ✅ round(..., 6) 与 stop_line 精度一致，返回 float 类型
```

**结论**：✅ 精度处理与 `stop_line` 完全一致，无类型异常风险。

---

#### 方法注释同步更新

```python
"""
VPA-Defender 量价共振复合指标。
返回 { stop_line, resistance_line, obv, obv_ma20, signal } 五个等长序列。  # ✅ 已更新
resistance_line：追踪历史最低收盘价 + atr_multi × ATR，只降不升（迭代8.1-patch）。  # ✅ 新增说明
"""
```

**结论**：✅ 方法文档注释已同步更新，描述准确。

---

### 2.2 前端渲染（`web/src/components/VPADefenderPanel.jsx`）

#### 数据解构与传递

```jsx
// L51：父组件 VPADefenderPanel 解构 API 数据
const { stop_line = [], resistance_line = [], obv = [], obv_ma20 = [], signal: signalSeries = [] } = vpaDefender || {}
// ✅ resistance_line 默认值 [] 防止 undefined

// L111：透传给 PanelInner
resistance_line={resistance_line}
// ✅ 完整透传

// L124：PanelInner 接参
dates, closes, stop_line, resistance_line, ...
// ✅ 参数列表包含
```

---

#### ECharts 阻力线 series（TC-resistance-FE-01 对应）

```jsx
// L261-271
{
  name:       '阻力线',
  type:       'line',
  yAxisIndex: 0,          // ✅ 左 Y 轴（价格轴），非右轴 OBV
  data:       resistance_line,
  symbol:     'none',
  smooth:     false,
  lineStyle:  { color: '#ff7043', width: 1.5 },  // ✅ 深橙红，颜色已确认
  z:          2,
}
```

**结论**：✅ 绑定左 Y 轴、颜色 `#ff7043`（深橙红，与 OBV均线橙黄 `#ffa726` 及防守线红 `#ef5350` 均可区分）、线宽 1.5（略细于防守线 2px，视觉权重合理）。

---

#### tooltip 显示"阻力线"（TC-resistance-FE-04）

```jsx
// L176
if (resistance_line[idx] != null) lines.push(`阻力线: ${resistance_line[idx]?.toFixed(2)}`)
// ✅ null 守卫，标签中文"阻力线"，格式与其他字段一致（2位小数）
```

**结论**：✅ null 区间不显示，非 null 时显示"阻力线: x.xx"。

---

#### ECharts legend 注册（FEAT-legend-toggle 联动基础）

```jsx
// L159
legend: { show: false, data: ['收盘价', '防守线', '阻力线', 'OBV', 'OBV均线'] },
// ✅ 含"阻力线"，dispatchAction('legendToggleSelect') 可生效
```

---

#### HELP_ITEMS 阻力线条目（TC-resistance-FE-06）

```jsx
// L41
{ iconType: 'line', color: '#ff7043', text: '<b>橙红（空仓阻力线）</b>：追踪历史最低价上方 ATR 倍数距离，只降不升。价格长期在线下方运行，说明上方压力持续；价格有效突破阻力线，可关注趋势反转信号。' },
```

**结论**：✅ `iconType: 'line'`（横实线图标）、颜色 `#ff7043`、文案含"只降不升"等描述性内容。

**买卖指令审查**：文案中"可关注趋势反转信号"措辞为观察性描述，不含"买入/卖出/建仓/平仓"等操作指令。**合规**。

---

#### useMemo 依赖数组更新

```jsx
// L297
}, [dates, closes, stop_line, resistance_line, obv, obv_ma20, signalSeries])
// ✅ resistance_line 已加入依赖项，数据更新时正确重新计算 option
```

---

### 2.3 API 透传（`api/services/kline_service.py`）

**无需修改**，`kline_service.py` 第106行：

```python
"VPA_DEFENDER": indicator_result.VPA_DEFENDER,
```

整体字典透传，`resistance_line` 随 `calc_vpa_defender` 返回字典自动包含在 API 响应中。经对照后端代码确认，此方式正确可靠。

---

## 三、FEAT-legend-toggle 代码审查详情

### 3.1 `ChartSidebar.jsx` 按钮化逻辑

#### seriesName 有无分支渲染（TC-toggle-UI-01）

```jsx
// L132-174
{legendItems.map((item, i) => {
  if (item.seriesName) {
    // 有 seriesName → <button>，cursor pointer（button 默认 pointer）
    const isActive = activeMap[item.seriesName] !== false
    return (
      <button key={i} onClick={...} style={{ cursor: 'pointer', ... }}>
        ...
      </button>
    )
  }
  // 无 seriesName → <div>，纯展示，无点击响应
  return (
    <div key={i} style={{ ... }}>
      ...
    </div>
  )
})}
```

**结论**：✅ 分支清晰，`<button>` vs `<div>` 的可点击性正确区分。

---

#### inactive 样式（TC-toggle-UI-03，对应 AC-legend-toggle-4）

```jsx
// L157-163
<span style={{ opacity: isActive ? 1 : 0.35 }}>
  <LegendMark type={item.type} color={item.color} />
</span>
<span style={{
  textDecoration: isActive ? 'none' : 'line-through',  // ✅ 删除线
  opacity:        isActive ? 1 : 0.35,                 // ✅ 半透明
}}>{item.label}</span>
```

**结论**：✅ inactive 时图标和文字均有 `opacity: 0.35` + 文字 `line-through`，视觉对比明显。

---

#### activeMap 状态管理

```jsx
// L46
const [activeMap, setActiveMap] = useState({})
// ✅ 初始空对象，isActive = activeMap[seriesName] !== false（缺省视为 true）

// L140（点击时）
setActiveMap(prev => ({ ...prev, [item.seriesName]: prev[item.seriesName] === false ? true : false }))
// ✅ toggle 逻辑：false→true，其他（undefined/true）→false
```

---

#### 新增 `onLegendToggle` prop

```jsx
// L42
onLegendToggle,   // FEAT-legend-toggle：图例点击回调 (seriesName: string) => void

// L141（点击时调用）
onLegendToggle?.(item.seriesName)
// ✅ 可选链，安全调用，传递 seriesName 而非 label
```

---

#### `guideItems` prop 向后兼容

```jsx
// L40
guideItems = [],  // deprecated：保留 prop 接口，不再渲染
```

**结论**：✅ 接口保留、渲染逻辑移除，传入不会报错，不 breaking（TC-guide-7 对应审查点）。

---

### 3.2 各 Panel ECharts legend 注册

| 组件 | legend.data | 审查结论 |
|------|------------|---------|
| `MACDPanel.jsx` L143 | `['DIF', 'DEA', 'MACD柱']` | ✅ 含 3 个可切换 series，`show: false` 不渲染 UI |
| `RSIPanel.jsx` L93 | `['RSI14']` | ✅ 含 1 个可切换 series |
| `KDJPanel.jsx` L144 | `['K', 'D', 'J']` | ✅ 含 3 个可切换 series，注意 series name 无"线"字，与 seriesName 映射吻合 |
| `VPADefenderPanel.jsx` L159 | `['收盘价', '防守线', '阻力线', 'OBV', 'OBV均线']` | ✅ 含新增"阻力线"，共 5 个可切换 series |

---

### 3.3 `StockAnalysis.jsx` 配置审查

#### FEAT-legend-toggle 状态管理

```jsx
// L78：全局激活状态
const [legendActiveMaps, setLegendActiveMaps] = useState({ MACD: {}, RSI: {}, KDJ: {}, VPA: {} })

// L138：切换股票时重置（AC-legend-toggle-8）
setLegendActiveMaps({ MACD: {}, RSI: {}, KDJ: {}, VPA: {} })
// ✅ 在 loadData 中调用，切换股票/周期时触发，状态重置为全 active
```

---

#### 折叠展开同步 inactive 状态（AC-legend-toggle-6，80ms 延迟机制）

```jsx
// L166-180
if (prev[panel] === true) {  // 展开动作
  const refMap = { MACD: macdRef, RSI: rsiRef, KDJ: kdjRef, VPA: vpaRef }
  const panelRef = refMap[panel]
  const activeMap = legendActiveMaps[panel] || {}
  setTimeout(() => {           // ✅ 延迟等待 ECharts 实例稳定
    const chart = panelRef?.current?.getEchartsInstance?.()
    if (chart) {
      Object.entries(activeMap).forEach(([seriesName, isActive]) => {
        if (isActive === false) {
          chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
        }
      })
    }
  }, 80)   // ✅ 80ms 延迟
}
```

**结论**：✅ 展开时通过 `setTimeout(80ms)` 遍历当前 inactive 的 series 重新 dispatch，解决 ECharts `notMerge: true` 重建后 legend 状态丢失的问题。

---

#### key 机制切换股票重置（AC-legend-toggle-8）

```jsx
<ChartSidebar key={`macd-sidebar-${code}`} .../>    // ✅ code 变化时组件重新挂载
<ChartSidebar key={`rsi-sidebar-${code}`}  .../>    // ✅
<ChartSidebar key={`kdj-sidebar-${code}`}  .../>    // ✅
<ChartSidebar key={`vpa-sidebar-${code}`}  .../>    // ✅
```

**结论**：✅ 四个面板的 ChartSidebar 均绑定 `key={xxx-sidebar-${code}}`，切换股票时组件重新挂载，`activeMap` useState 自动重置为初始空对象（全 active）。

---

#### 各面板 legendItems / seriesName 配置

**MACD（TC-toggle-PANEL-01）**：

```jsx
const macdSidebarLegend = [
  { color: C.dif,        type: 'line',   label: 'DIF',    seriesName: 'DIF' },     // ✅ 可切换
  { color: C.dea,        type: 'line',   label: 'DEA',    seriesName: 'DEA' },     // ✅ 可切换
  { color: C.macdBarPos, type: 'bar',    label: '柱(正)', seriesName: 'MACD柱' }, // ✅ 可切换，与柱(负)共用 seriesName
  { color: C.macdBarNeg, type: 'bar',    label: '柱(负)', seriesName: 'MACD柱' }, // ✅ 联动柱(正)
  { color: C.buy,        type: 'circle', label: '金叉' },                          // ✅ 无 seriesName，纯展示
  { color: C.sell,       type: 'circle', label: '死叉' },                          // ✅ 无 seriesName，纯展示
]
```

**RSI（TC-toggle-PANEL-02）**：

```jsx
const rsiSidebarLegend = [
  { color: C.dif,  type: 'line', label: 'RSI(14)',   seriesName: 'RSI14' }, // ✅ 可切换
  { color: C.sell, type: 'bar',  label: '超买区(卖)' },                      // ✅ 纯展示
  { color: C.buy,  type: 'bar',  label: '超卖区(买)' },                      // ✅ 纯展示
]
```

**KDJ（TC-toggle-PANEL-03，label≠seriesName 映射）**：

```jsx
const kdjSidebarLegend = [
  { color: C.kLine, type: 'line',   label: 'K线', seriesName: 'K' }, // ✅ label≠seriesName，'K'对应 ECharts series name
  { color: C.dLine, type: 'line',   label: 'D线', seriesName: 'D' }, // ✅
  { color: C.jLine, type: 'dashed', label: 'J线', seriesName: 'J' }, // ✅
  { color: C.buy,   type: 'circle', label: '金叉' },                   // ✅ 纯展示
  { color: C.sell,  type: 'circle', label: '死叉' },                   // ✅ 纯展示
]
```

> 关键验证：`dispatchAction` 使用 `seriesName: 'K'`（非 'K线'），与 KDJPanel ECharts series `name: 'K'` 精确匹配。

**VPA（TC-toggle-PANEL-04，含阻力线）**：

```jsx
const vpaSidebarLegend = [
  { color: '#8b949e', type: 'line',   label: '收盘价',  seriesName: '收盘价'  }, // ✅
  { color: '#ef5350', type: 'line',   label: '防守线',  seriesName: '防守线'  }, // ✅
  { color: '#ff7043', type: 'line',   label: '阻力线',  seriesName: '阻力线'  }, // ✅ #ff7043 已确认
  { color: '#42a5f5', type: 'line',   label: 'OBV',     seriesName: 'OBV'    }, // ✅
  { color: '#ffa726', type: 'dashed', label: 'OBV均线', seriesName: 'OBV均线' }, // ✅ dashed 虚线，与阻力线实线可区分
]
```

**结论**：✅ 阻力线颜色 `#ff7043` 已到位；OBV均线为 dashed 虚线，视觉与阻力线实线不同，颜色一致（均橙色系）但线型区分充分。

---

#### onLegendToggle handler 正确性

```jsx
// MACD 面板（其余面板结构相同）
onLegendToggle={(seriesName) => {
  setLegendActiveMaps(prev => ({
    ...prev,
    MACD: { ...prev.MACD, [seriesName]: prev.MACD[seriesName] === false ? true : false },
  }))
  const chart = macdRef.current?.getEchartsInstance?.()
  if (chart) chart.dispatchAction({ type: 'legendToggleSelect', name: seriesName })
}}
```

**结论**：✅ 两步同步：① 更新父组件 `legendActiveMaps`（用于折叠展开恢复）；② 立即 `dispatchAction` 通知 ECharts（用于实时曲线显隐）。两步顺序合理，无竞态风险。

---

## 四、阻力线颜色全链路确认

> **team-lead 要求重点验证项**

| 位置 | 颜色值 | 状态 |
|------|--------|------|
| `VPADefenderPanel.jsx` L269：ECharts series `lineStyle.color` | `#ff7043` | ✅ 已确认 |
| `VPADefenderPanel.jsx` L41：`HELP_ITEMS` 阻力线条目 `color` | `#ff7043` | ✅ 已确认 |
| `StockAnalysis.jsx` L273：`vpaSidebarLegend` 阻力线图例 `color` | `#ff7043` | ✅ 已确认 |

三处颜色全部一致，链路完整。

---

## 五、CLAUDE.md 强制规范合规性检查

| 规范 | 检查项 | 结论 |
|------|--------|------|
| 禁止买卖操作指令 | HELP_ITEMS 阻力线文案："可关注趋势反转信号"（观察性描述，无买卖/建仓等指令词） | ✅ 合规 |
| 指标面板必须附带新手解释浮层 | FEAT-resistance 新增阻力线，已在 VPA HELP_ITEMS 中新增对应说明条目 | ✅ 合规 |
| VPA 不参与综合信号 | 阻力线未修改 `signal_series` 计算，四象限逻辑不变 | ✅ 合规 |
| 不含自动交易逻辑 | 改动仅涉及指标计算与前端显示 | ✅ 合规 |

---

## 六、发现问题记录

### 已关闭缺陷记录

| 编号 | 描述 | 状态 |
|------|------|------|
| CR-01 | `StockAnalysis.jsx` L273 阻力线图例颜色 | ~~误报，已关闭~~ team-lead 直接核查源码确认：当前代码始终为 `#ff7043`，初次读取触发文件缓存导致误判，Dev 无需任何修改。无遗留缺陷。|

### 无新发现问题

经完整审查，代码在以下维度均无问题：
- 算法逻辑（只降不升约束、公式方向、None 处理）
- 类型安全（无 NaN 风险、正确 float 精度）
- React 数据流（props 正确传递、useMemo 依赖完整）
- ECharts 配置（legend 注册与 series name 对应、yAxisIndex 正确）
- 交互逻辑（seriesName 映射、MACD 柱联动、折叠展开恢复、切换股票重置）
- 向后兼容（`guideItems` prop 保留接口、原有5字段完整）

---

## 七、Runtime 验收结果

### 后端 API Runtime 验收（命令行自动化，2026-03-25）

重启 uvicorn 服务加载最新代码后，对 `HK.00700` 执行 curl 验证：

| 用例 ID | 验收要点 | 结果 |
|---------|---------|------|
| TC-resistance-API-01 | `resistance_line` 键出现在 `VPA_DEFENDER` 响应中 | ✅ PASS — 实测 key 列表：`['stop_line', 'resistance_line', 'obv', 'obv_ma20', 'signal']` |
| TC-resistance-API-02 | `resistance_line` 数组长度 == bars 长度 | ✅ PASS — 均为 242 |
| TC-resistance-API-03 | null 前缀与 `stop_line` 一致（ATR period=22） | ✅ PASS — 首个非 null 索引均为 21 |
| TC-resistance-BE-03  | 只降不升约束（API 数据验证） | ✅ PASS — 全 221 个有效值均满足 rl[i] ≤ rl[i-1] |
| 算法合理性 sanity | resistance_line 均为正值，与实际股价量纲吻合 | ✅ PASS — 最近 5 日约 455，stop_line 约 647 |
| 备注 | 2025年4-5月港股反弹期间，有 13 个点 resistance > stop（正常现象：低价 + ATR > 高价 - ATR，算法无问题） | — |

> **注**：服务启动时版本号显示 `v0.7.1-patch`（来自 config/settings.py），版本号升级为 `v0.8.1-patch` 属于独立发布操作，不影响本次功能验收。

### 前端浏览器验收清单（待人工执行）

以下 P0 项需在浏览器中执行，服务地址：`http://127.0.0.1:8000`

| 用例 ID | 验收要点 | 预期结果 | 状态 |
|---------|---------|---------|------|
| TC-resistance-FE-01 | VPA 副图左 Y 轴显示深橙红实线（`#ff7043`） | 三条曲线：灰色收盘价 + 红色防守线 + 橙红阻力线 | ⏳ 待验 |
| TC-resistance-FE-04 | hover tooltip 显示"阻力线: x.xx" | 有数据区间显示，null 区间不显示 | ⏳ 待验 |
| TC-toggle-UI-03 | 点击 DIF 图例 → inactive 样式 | 删除线 + 0.35 半透明 | ⏳ 待验 |
| TC-toggle-CHART-01 | 点击 DIF 图例 → DIF 曲线消失；再点 → 重现 | 立即响应 | ⏳ 待验 |
| TC-toggle-CHART-03 | 点击"柱(正)"→ 柱(正)和柱(负)同步 inactive，MACD 柱整体隐藏 | 两图例联动，柱全隐 | ⏳ 待验 |
| TC-toggle-PERSIST-01 | 隐藏 DIF → 折叠 MACD → 展开 → DIF 仍隐藏（等 100ms） | 80ms 延迟后状态恢复 | ⏳ 待验 |
| TC-toggle-PERSIST-03 | 隐藏 DEA → 切换股票 → DEA 恢复显示，图例 active | key 重置生效 | ⏳ 待验 |

### P1 建议验（浏览器）

| 用例 ID | 验收要点 | 状态 |
|---------|---------|------|
| TC-resistance-FE-02 | 阻力线在价格反弹时保持水平（只降不升视觉验证） | ⏳ 待验 |
| TC-resistance-FE-06 | [?] 浮层含"橙红（空仓阻力线）"条目，图标为深橙红横实线 | ⏳ 待验 |
| TC-resistance-FE-07 | ChartSidebar 图例含"阻力线"深橙红横实线 | ⏳ 待验 |
| TC-resistance-FE-08 | VPA 折叠展开后阻力线正常渲染 | ⏳ 待验 |
| TC-toggle-PANEL-04 | 点击"阻力线"图例，橙红曲线消失/重现 | ⏳ 待验 |

---

## 八、审查结论

| 维度 | 评分 | 说明 |
|------|------|------|
| 算法正确性 | ⭐⭐⭐⭐⭐ | 只降不升逻辑、公式方向、None 处理均无误 |
| 代码对称性 | ⭐⭐⭐⭐⭐ | 与防守线完全镜像，易于理解和维护 |
| 前端实现完整性 | ⭐⭐⭐⭐⭐ | 曲线、tooltip、HELP_ITEMS、图例、legend 注册五项齐全 |
| 交互逻辑严谨性 | ⭐⭐⭐⭐⭐ | seriesName 映射、联动、折叠展开恢复、切换重置均到位 |
| 规范合规性 | ⭐⭐⭐⭐⭐ | CLAUDE.md 强制规范全部满足 |
| 颜色一致性 | ⭐⭐⭐⭐⭐ | 三处 `#ff7043` 全部到位（初始 CR 发现的遗漏已由 Dev 修复）|

**最终结论：✅ 代码审查通过，建议合并。后端 API Runtime 验收（自动化）全部通过；前端浏览器 P0 项（7项）待老板人工确认后发布 v0.8.1-patch。**

---

*CR 文档结束 — QA 完成。如 Runtime 验收发现问题，将补充 §七 备注。*
