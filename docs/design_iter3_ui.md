# 迭代3.5 UI 优化详细设计文档

**版本**: v1.1
**日期**: 2026-03-18
**依据**: PRD v3.5.1 + 原型 web/prototype_ui.html（老板已确认）
**范围**: 纯前端改造，后端零改动

> **[P1-02 裁定注记]** 副图高度统一实现为 **200px**，以 2026-03-18 原型评审老板确认结论为准。
> PRD §3.2.1 中出现的 180/160/160 数字为 PM 写文档时的笔误，代码实现不跟随，保持 200px 不变。

---

## 1. 改动文件清单

### 新增文件
| 文件 | 说明 |
|------|------|
| `web/src/utils/colors.js` | 配色常量（红涨绿跌体系） |
| `web/src/utils/compositeSignal.js` | 综合信号评分算法（前端计算） |
| `web/src/components/SignalBanner.jsx` | 综合信号横幅组件 |
| `web/src/components/ChartSidebar.jsx` | 图表右侧固定200px说明栏 |
| `web/src/hooks/useChartSync.js` | 跨图联动 Hook |

### 修改文件
| 文件 | 改动要点 |
|------|---------|
| `web/src/utils/signals.js` | 更新信号文案（通俗化）+ 颜色遵循红买绿卖 |
| `web/src/components/MainChart.jsx` | 去 inside dataZoom、加买卖 markPoint、去 legend、暴露 ref、高度500px |
| `web/src/components/MACDPanel.jsx` | 加金叉/死叉圆圈标记（circle symbolSize=10）、去 inside dataZoom、去内置 legend、支持折叠、暴露 ref |
| `web/src/components/RSIPanel.jsx` | 超买=绿底/超卖=红底（修正颜色）、去 inside dataZoom、支持折叠、暴露 ref |
| `web/src/components/KDJPanel.jsx` | 金叉/死叉圆圈标记、超买=绿底/超卖=红底、去 inside dataZoom、支持折叠、暴露 ref |
| `web/src/components/BottomBar.jsx` | 配色同步红买绿卖、双层结构 |
| `web/src/components/SignalTag.jsx` | 更新 labels（通俗化）、字号13px、圆角6px |
| `web/src/pages/StockAnalysis.jsx` | 引入 SignalBanner、图表包裹 ChartSidebar、接入 useChartSync、副图折叠控制 |

---

## 2. 每个文件关键改动说明

### 2.1 `web/src/utils/colors.js`（新增）

全局配色常量，导出 `C` 对象，所有组件统一引用：

```js
export const C = {
  buy:           '#f85149',   // 买入主色（红）
  buyBg:         '#3a1a1a',   // 买入背景
  buyBgLight:    'rgba(248,81,73,0.12)',
  buyText:       '#ff7b72',   // 买入文字
  sell:          '#2ea043',   // 卖出主色（绿）
  sellBg:        '#1a3a2a',   // 卖出背景
  sellBgLight:   'rgba(46,160,67,0.12)',
  sellText:      '#3fb950',   // 卖出文字
  neutral:       '#8c8c8c',
  neutralBg:     '#1c2128',
  neutralBorder: '#484f58',
  overbought:    'rgba(46,160,67,0.10)',   // 超买=卖出信号=绿底
  overboughtLine:'#26a69a55',
  oversold:      'rgba(248,81,73,0.10)',   // 超卖=买入信号=红底
  oversoldLine:  '#ef535055',
  disclaimer:    '#bfbfbf',
  // K线颜色
  candleUp:      '#ef5350',
  candleDown:    '#26a69a',
  // 图表UI
  chartBg:       '#0d1117',
  panelBg:       '#161b22',
  border:        '#21262d',
  border2:       '#30363d',
  text:          '#e6edf3',
  textMuted:     '#8b949e',
  textDim:       '#484f58',
  gridLine:      '#21262d',
  axisLine:      '#30363d',
}
```

### 2.2 `web/src/utils/compositeSignal.js`（新增）

综合信号评分算法，输入 `{ signals, indicators, bars }` 对象，输出综合结论：

**算法（对应 PRD §3.1.1）**：
```js
// 输入：
//   signals   = { MACD, RSI, KDJ, BOLL, MA }  （后端返回信号字符串）
//   indicators = { MACD: {dif,dea,...}, RSI: {RSI14}, KDJ: {K,D}, BOLL, MA }
//   bars       = [...]  最新K线数组

// 输出：
// {
//   level: 'bullish' | 'bearish' | 'neutral',
//   score: number,   // -12 ~ +12
//   label: string,   // 综合结论文案
//   votes: [{ indicator, score, label }]
// }
```

评分规则按 PRD §3.1.1 表格实现：
- MACD: 金叉(最近3根)+3 / 多头持续+2 / 空头持续-2 / 死叉(最近3根)-3
- RSI: 分区间计分（20-30:+2, 30-50:+1, 50-70:+2, >70:-1, <20:+1）
- KDJ: 金叉低位+2 / 金叉中位+1 / 死叉高位-2 / 死叉中位-1
- BOLL: 价格<下轨+2 / >上轨-2 / 上1/3+1 / 下1/3-1
- MA: 多头排列+2 / 空头排列-2

总分→结论：≥+5:积极做多 / +2~+4:偏多 / -1~+1:中性 / -2~-4:偏空 / ≤-5:积极做空

### 2.3 `web/src/components/SignalBanner.jsx`（新增）

**Props**:
```ts
interface SignalBannerProps {
  // 来自 compositeSignal() 的输出
  level:  'bullish' | 'bearish' | 'neutral'
  score:  number
  label:  string
  votes:  Array<{ indicator: string, score: number, label: string }>
}
```

**UI结构**：
- 外层 `<div>` 带 `bullish/bearish/neutral` 配色（参考原型 `.signal-banner`）
- 左侧：大图标 + 标题（结论文案）+ 小字描述
- 右侧：各因子 chip（votes），正分=红系，负分=绿系，0分=灰色
- 底部全宽：免责声明（常驻，11px灰色，不可关闭）

### 2.4 `web/src/components/ChartSidebar.jsx`（新增）

**Props**:
```ts
interface ChartSidebarProps {
  title:       string                          // 面板标题（如 "📶 MACD 趋势动能"）
  signal?:     string                          // 信号值（bullish/bearish/neutral）
  signalLabel?: string                         // 信号文案（可选覆盖）
  valueItems?: Array<{ label: string, value: string | number, type?: 'bull'|'bear'|'neut' }>
  legendItems: Array<{
    color:      string
    type:       'line' | 'bar' | 'circle' | 'dashed'
    label:      string
  }>
  guideItems:  Array<{
    dotColor?:  string
    dotType?:   'bull' | 'bear' | 'neut'      // 若提供则用语义色
    text:       string                         // 支持 <b> 标签
  }>
}
```

**UI结构**（参考原型 `.chart-sidebar`）：
- 宽度固定 200px
- 第一块：title + valueItems + signal 标签
- 分割线
- 第二块：HTML图例 legendItems
- 分割线
- 第三块：解读文案 guideItems（圆点 + 文字）

### 2.5 `web/src/hooks/useChartSync.js`（新增）

```ts
/**
 * 跨图联动 Hook
 * @param mainRef    主图 ReactECharts ref
 * @param subRefs    副图 ReactECharts ref 数组 [macdRef, rsiRef, kdjRef]
 */
function useChartSync(mainRef: RefObject, subRefs: RefObject[]): void
```

**核心逻辑**：
1. 在 `useEffect` 中，获取主图实例 `mainRef.current.getEchartsInstance()`
2. 绑定 `updateAxisPointer` 事件：
   ```js
   main.on('updateAxisPointer', e => {
     const xInfo = e.axesInfo?.find(a => a.axisDim === 'x')
     if (!xInfo) return
     const dataIndex = xInfo.value
     subs.forEach(c => c.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex }))
   })
   ```
3. 绑定主图 DOM `mouseleave` 事件 → `hideTip`
4. 绑定主图 `dataZoom` 事件 → 同步副图范围
5. 在 cleanup 中解绑（`main.off(...)` + `removeEventListener`）

### 2.6 `web/src/utils/signals.js`（修改）

**改动**：更新 `SIGNAL_LABELS` 与 `SIGNAL_COLORS`，遵循红买绿卖：

```diff
- BOLL.bullish: '🟢 超卖·下轨突破'   → '🔴 超卖·下轨突破'  // 超卖=买=红
- MACD.bullish: '🟢 金叉·多头信号'   → '🔴 MACD 金叉，上升动能增强'
- MACD.bearish: '🔴 死叉·空头信号'   → '🟢 MACD 死叉，下行压力增大'
- RSI.bullish:  '🟢 超卖区间·关注反弹'→ '🔴 RSI 超卖（{n}），关注反弹机会'
- RSI.bearish:  '🔴 超买区间·注意回调'→ '🟢 RSI 超买（{n}），短期或有回调'
- KDJ.bullish:  '🟢 金叉·超卖买入'  → '🔴 KDJ 金叉（低位），超卖反弹信号'
- KDJ.bearish:  '🔴 死叉·超买卖出'  → '🟢 KDJ 死叉（高位），超买回调信号'
```

`SIGNAL_COLORS` 改为红买绿卖（与原来逻辑对调）：
```diff
- bullish: { bg: '#1a3a2a', border: '#2ea043', text: '#3fb950' }  // 绿
+ bullish: { bg: '#3a1a1a', border: '#f85149', text: '#ff7b72' }  // 红（买入=红）
- bearish: { bg: '#3a1a1a', border: '#f85149', text: '#ff7b72' }  // 红
+ bearish: { bg: '#1a3a2a', border: '#2ea043', text: '#3fb950' }  // 绿（卖出=绿）
```

### 2.7 `web/src/components/MainChart.jsx`（修改）

关键改动：
1. **高度**：`style={{ height: 440 }}` → `style={{ height: 500 }}`
2. **去 inside dataZoom**：删除 `type: 'inside'` 项，只保留 slider
3. **去 legend**：删除 `legend` 配置项（改由侧边栏 HTML 图例）
4. **加买卖 markPoint**：在 K线 series 上加 `markPoint`
   - 遍历 MACD 数据检测金叉死叉（`dif[i-1]<=dea[i-1] && dif[i]>dea[i]`）
   - 金叉→买标记：圆形 symbolSize=12，红色圈，K线最低价 `*0.998`，文字`买▲` 17px加粗，position bottom
   - 死叉→卖标记：圆形 symbolSize=12，绿色圈，K线最高价 `*1.002`，文字`卖▼` 17px加粗，position top
5. **暴露 ref**：改为 `React.forwardRef`，将 ref 传给 `<ReactECharts ref={echartsRef} />`
6. **成交量区域比例**：grid 高度调整为 K线区 56%、成交量区 18%（保持原比例，主图整体高500px）
7. **配色引用 colors.js**

### 2.8 `web/src/components/MACDPanel.jsx`（修改）

关键改动：
1. **高度**：140 → 200px
2. **去 inside dataZoom** + 加 slider（与主图范围同步）
3. **去 legend**
4. **标记点改为圆形**：
   ```diff
   - symbol: 'triangle'
   + symbol: 'circle'
   - label: { formatter: '▲'/'▼', fontSize: 10 }
   + label: { formatter: '金叉'/'死叉', fontSize: 16, fontWeight: 700 }
   - symbolSize: 10
   + symbolSize: 10
   - 金叉 color: '#3fb950'（绿）
   + 金叉 color: '#f85149'（红，买入）
   - 死叉 color: '#f85149'（红）
   + 死叉 color: '#2ea043'（绿，卖出）
   ```
5. **支持折叠**：接受 `collapsed` prop，若 collapsed 则返回折叠摘要行（高度32px）
6. **暴露 ref**：改为 forwardRef
7. **DIF/DEA 线颜色**：DIF `#79c0ff`，DEA `#f0c040`（与原型一致）

### 2.9 `web/src/components/RSIPanel.jsx`（修改）

关键改动：
1. **高度**：140 → 200px
2. **去 inside dataZoom** + 加 slider
3. **去 legend**
4. **区域背景色修正**（遵循红涨绿跌）：
   ```diff
   - 超买区（70-100）itemStyle: { color: 'rgba(239,83,80,0.08)' }  // 红底（原来配色错误）
   + 超买区（70-100）itemStyle: { color: 'rgba(46,160,67,0.10)' }   // 绿底（超买=卖出信号=绿）
   - 超卖区（0-30）itemStyle: { color: 'rgba(63,185,80,0.08)' }    // 绿底（原来配色错误）
   + 超卖区（0-30）itemStyle: { color: 'rgba(248,81,73,0.10)' }    // 红底（超卖=买入信号=红）
   ```
5. **参考线颜色修正**：超买参考线改绿，超卖参考线改红
6. **支持折叠** + **暴露 ref**

### 2.10 `web/src/components/KDJPanel.jsx`（修改）

关键改动：
1. **高度**：140 → 200px
2. **去 inside dataZoom** + 加 slider
3. **去 legend**
4. **标记点改为圆形**（同 MACD，配色金叉=红/死叉=绿）
5. **区域背景色修正**：
   ```diff
   - 超买区（80-100）itemStyle: { color: 'rgba(239,83,80,0.08)' }  // 红底
   + 超买区（80-100）itemStyle: { color: 'rgba(46,160,67,0.10)' }   // 绿底
   - 超卖区（0-20）itemStyle: { color: 'rgba(63,185,80,0.08)' }    // 绿底
   + 超卖区（0-20）itemStyle: { color: 'rgba(248,81,73,0.10)' }    // 红底
   ```
6. **支持折叠** + **暴露 ref**
7. **K线颜色**：K线 `#79c0ff`（蓝），D线 `#f0c040`（黄），J线 `#bc8cff`（紫虚线）

### 2.11 `web/src/components/BottomBar.jsx`（修改）

关键改动：
1. **双层结构**：
   - 第一层：收盘价 / 涨跌幅 / PE / PB（始终可见）
   - 第二层：指标标签（RSI/MACD/KDJ/BOLL/MA），可折叠，默认展开
2. **配色修正**：`SignalTag` 颜色已通过修改 `signals.js` 全局生效

### 2.12 `web/src/components/SignalTag.jsx`（修改）

```diff
- padding: '2px 8px'
+ padding: '5px 10px'
- borderRadius: '12px'
+ borderRadius: '6px'
- fontSize: '12px'
+ fontSize: '13px'
+ minWidth: '100px'
+ textAlign: 'center'
```
中性状态时降低透明度（opacity: 0.6）

### 2.13 `web/src/pages/StockAnalysis.jsx`（修改）

关键改动：
1. **引入新组件**：`SignalBanner`、`ChartSidebar`、`useChartSync`、`compositeSignal`
2. **综合信号计算**：在数据加载后调用 `compositeSignal()`
3. **SignalBanner 插入**：顶部导航栏下方、主图上方
4. **图表区域包裹 ChartSidebar**：
   ```jsx
   <div style={{ display: 'flex', marginBottom: 10 }}>
     <MainChart ref={mainRef} bars={bars} indicators={indicators} />
     <ChartSidebar title="..." legendItems={...} guideItems={...} />
   </div>
   ```
5. **折叠状态管理**：
   ```js
   const [collapsed, setCollapsed] = useState(() => {
     const saved = localStorage.getItem('quant_panel_collapse_state')
     return saved ? JSON.parse(saved) : { MACD: false, RSI: false, KDJ: false }
   })
   // 更新时同步 localStorage
   ```
6. **接入 useChartSync**：
   ```js
   const mainRef = useRef(null)
   const macdRef = useRef(null)
   const rsiRef  = useRef(null)
   const kdjRef  = useRef(null)
   useChartSync(mainRef, [macdRef, rsiRef, kdjRef])
   ```
7. **标记点开关**：顶部导航栏增加切换按钮，通过 prop 传入 `MainChart`
8. **面板折叠控制 UI**（参考原型 `.panel-toggle`）：主图下方按钮组

---

## 3. 新增组件 Props 接口设计

### `SignalBanner.jsx`

```ts
interface SignalBannerProps {
  level:  'bullish' | 'bearish' | 'neutral'    // 综合方向
  score:  number                                // 综合得分（-12~+12）
  label:  string                                // 结论文案
  votes:  Array<{
    indicator: string  // 指标名（MACD/RSI/KDJ/BOLL/MA）
    score:     number  // 贡献分
    label:     string  // 展示文案
  }>
}
```

### `ChartSidebar.jsx`

```ts
interface ChartSidebarProps {
  title:        string
  signal?:      'bullish' | 'bearish' | 'neutral'
  signalLabel?: string
  valueItems?:  Array<{
    label: string
    value: string | number
    type?: 'bull' | 'bear' | 'neut'
  }>
  legendItems:  Array<{
    color:  string
    type:   'line' | 'bar' | 'circle' | 'dashed'
    label:  string
  }>
  guideItems:   Array<{
    dotType?: 'bull' | 'bear' | 'neut'
    dotColor?: string
    text:     string
  }>
}
```

---

## 4. 跨图联动方案：`useChartSync` Hook 设计

### 核心思路

**为何不用 `echarts.connect()`**：主图有两个 grid（K线区 xAxisIndex:0 + 成交量区 xAxisIndex:1），`echarts.connect()` 只广播 xAxisIndex:0 的事件，鼠标在成交量柱上悬停时无法触发副图联动。

### 实现

```js
// web/src/hooks/useChartSync.js
import { useEffect } from 'react'

export default function useChartSync(mainRef, subRefs) {
  useEffect(() => {
    // 延迟获取，确保图表已初始化
    const timer = setTimeout(() => {
      const main = mainRef?.current?.getEchartsInstance?.()
      const subs = subRefs
        .map(r => r?.current?.getEchartsInstance?.())
        .filter(Boolean)
      if (!main) return

      // 1. 十字线联动
      const onAxisPointer = (event) => {
        const xInfo = event.axesInfo?.find(a => a.axisDim === 'x')
        if (xInfo == null) return
        const dataIndex = xInfo.value
        if (dataIndex == null) return
        subs.forEach(c => c.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex }))
      }
      main.on('updateAxisPointer', onAxisPointer)

      // 2. 鼠标离开主图 → 清除所有副图 tooltip
      const onMouseLeave = () => {
        subs.forEach(c => c.dispatchAction({ type: 'hideTip' }))
      }
      const mainDom = main.getDom()
      mainDom.addEventListener('mouseleave', onMouseLeave)

      // 3. dataZoom 同步
      const onDataZoom = () => {
        const zoom = main.getOption()?.dataZoom?.[0]
        if (!zoom) return
        subs.forEach(c => c.dispatchAction({
          type: 'dataZoom', start: zoom.start, end: zoom.end
        }))
      }
      main.on('dataZoom', onDataZoom)

      // Cleanup
      return () => {
        main.off('updateAxisPointer', onAxisPointer)
        main.off('dataZoom', onDataZoom)
        mainDom.removeEventListener('mouseleave', onMouseLeave)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [mainRef, subRefs])
}
```

---

## 5. 配色常量抽取方案

### 新建 `src/utils/colors.js`

原则：**所有组件统一从 `colors.js` 导入，不再在组件内硬编码颜色字符串**。

覆盖范围：
- `MainChart.jsx`：K线涨跌色、买卖标记色、MA/BOLL线条色
- `MACDPanel.jsx`：DIF/DEA线色、柱色、金叉/死叉标记色
- `RSIPanel.jsx`：超买/超卖区域色
- `KDJPanel.jsx`：K/D/J线色、超买/超卖区域色
- `SignalBanner.jsx`：横幅背景/边框/文字
- `ChartSidebar.jsx`：标签、色块
- `SignalTag.jsx`：通过 `signals.js`（signals.js 颜色值从 colors.js 引用）
- `BottomBar.jsx`：价格涨跌色

---

## 6. 不改动范围说明

### 后端：零改动
- `api/` 目录下所有文件：不修改任何接口
- `core/indicator_engine.py`：指标计算逻辑不变
- `main.py` / `futu_wrap/` / `db/`：数据采集层不涉及

### 前端不改动
- `web/src/api/client.js`：API 调用层不变，接口与迭代3完全一致
- `web/src/components/StockSelector.jsx`
- `web/src/components/PeriodSelector.jsx`
- `web/src/components/TimeRangeSelector.jsx`
- `web/src/pages/WatchlistPage.jsx`（P2优先级，本次暂不改动）
- `web/vite.config.js` / `package.json`：无新依赖

---

## 7. 建议开发顺序（对齐 PRD §6）

| Step | 模块 | 文件 |
|------|------|------|
| 1 | 配色常量 | `colors.js`（新增） |
| 2 | 综合信号计算 | `compositeSignal.js`（新增）、`signals.js`（修改配色和文案） |
| 3 | 新增组件 | `SignalBanner.jsx`、`ChartSidebar.jsx` |
| 4 | 跨图联动 Hook | `useChartSync.js` |
| 5 | 改造现有组件 | `MainChart.jsx`→`MACDPanel.jsx`→`RSIPanel.jsx`→`KDJPanel.jsx`→`BottomBar.jsx`→`SignalTag.jsx` |
| 6 | 改造主页面 | `StockAnalysis.jsx` |
| 7 | 构建验证 | `cd web && npm run build` |

---

*设计文档由 Dev 输出，2026-03-18*
