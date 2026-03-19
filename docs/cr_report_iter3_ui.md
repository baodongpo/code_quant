# 迭代3.5 UI 优化 — Code Review 报告

**日期**：2026-03-18
**Reviewer**：QA
**Review 范围**：迭代3.5 全部12个前端文件
**PRD 版本**：requirements_iter3_ui.md v3.5
**设计文档**：design_iter3_ui.md v1.0
**构建状态**：✅ `npm run build` 通过（built in 1.52s）

---

## P0（必须修复，阻塞发布）

> 本次 CR 未发现 P0 级阻塞问题。

---

## P1（应当修复，影响功能正确性）

### [P1-01] `useChartSync.js`：cleanup 函数从未被 React 执行，导致事件监听器泄漏

- **文件**：`web/src/hooks/useChartSync.js` L15–66
- **问题描述**：

  `useEffect` 的清理函数在 `setTimeout` 的回调内部 `return`，而非从 `useEffect` 直接返回。React 只调用从 `useEffect` 函数体直接返回的函数作为清理。`setTimeout` 回调内部的 `return` 返回值被 `setTimeout` 丢弃，React 永远无法接收到它。

  ```js
  useEffect(() => {
    const timer = setTimeout(() => {
      // ...绑定 main.on('updateAxisPointer', ...)
      // ...绑定 main.on('dataZoom', ...)
      // ...绑定 mainDom.addEventListener('mouseleave', ...)

      return () => {            // ← 此处返回值被 setTimeout 丢弃，React 从未调用
        main.off(...)
        mainDom.removeEventListener(...)
      }
    }, 300)

    return () => clearTimeout(timer)  // ← 只能取消未到期的 timer，无法清理已注册的监听器
  }, [mainRef, ...subRefs])
  ```

  **实际影响**：
  1. 每次副图折叠/展开（触发 `subRefs` 变化，effect 重跑）都会在 ECharts 实例上叠加新监听器，旧监听器从未移除
  2. 组件卸载时（如切换路由），`updateAxisPointer`/`dataZoom`/`mouseleave` 监听器仍滞留在已销毁的 ECharts 实例上
  3. 联动事件会被触发多次，频繁切换折叠状态后可能出现鬼影十字线或控制台报错

- **修复建议**：将监听器注册逻辑提取到 `setTimeout` 外，或使用 ref 存储清理函数后在外层 cleanup 中调用：

  ```js
  useEffect(() => {
    let cleanup = null
    const timer = setTimeout(() => {
      const main = mainRef?.current?.getEchartsInstance?.()
      if (!main) return
      const subs = subRefs.map(r => r?.current?.getEchartsInstance?.()).filter(Boolean)

      const onAxisPointer = (event) => { /* ... */ }
      const onDataZoom    = () => { /* ... */ }
      const onMouseLeave  = () => { /* ... */ }
      const mainDom = main.getDom()

      main.on('updateAxisPointer', onAxisPointer)
      main.on('dataZoom', onDataZoom)
      mainDom.addEventListener('mouseleave', onMouseLeave)

      // 存储清理函数
      cleanup = () => {
        main.off('updateAxisPointer', onAxisPointer)
        main.off('dataZoom', onDataZoom)
        mainDom.removeEventListener('mouseleave', onMouseLeave)
      }
    }, 300)

    return () => {
      clearTimeout(timer)
      cleanup?.()              // ← 确保清理函数被执行
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mainRef, ...subRefs])
  ```

---

### [P1-02] 副图高度与 PRD 验收标准不一致（MACD/RSI/KDJ 均为 200px，应为 180/160/160px）

- **文件**：
  - `web/src/components/MACDPanel.jsx` L247：`style={{ height: 200 }}`
  - `web/src/components/RSIPanel.jsx` L215：`style={{ height: 200 }}`
  - `web/src/components/KDJPanel.jsx` L272：`style={{ height: 200 }}`
- **问题描述**：

  PRD §3.2.1 和 P0 验收标准第 10 条明确规定：

  | 面板 | PRD 要求高度 | 代码实际高度 |
  |------|------------|------------|
  | MACD | **180px** | 200px ❌ |
  | RSI  | **160px** | 200px ❌ |
  | KDJ  | **160px** | 200px ❌ |

  设计文档 design_iter3_ui.md 将三者统一写为 "140 → 200px"，与 PRD 验收标准不符。PRD 为最终需求基准，测试方案 TC-F2-02 将按 PRD 数值验收。

- **修复建议**：按 PRD 调整三个面板高度：
  ```jsx
  // MACDPanel.jsx
  style={{ height: 180 }}

  // RSIPanel.jsx
  style={{ height: 160 }}

  // KDJPanel.jsx
  style={{ height: 160 }}
  ```

---

### [P1-03] 副图信号标签绝对定位遮挡图表，违反 PRD §3.2.2"文档流内"要求

- **文件**：
  - `web/src/components/MACDPanel.jsx` L212–224
  - `web/src/components/RSIPanel.jsx` L180–192
  - `web/src/components/KDJPanel.jsx` L239–251
- **问题描述**：

  PRD §3.2.2 明确要求信号标签的显示位置从"副图绝对定位右上角"改为"**副图标题栏右侧（文档流内，不遮挡图表内容）**"。但代码中信号标签仍以绝对定位叠于图表画布之上：

  ```jsx
  <div style={{
    position: 'absolute',   // ← 绝对定位，浮于图表上
    top: 8, left: 12,
    zIndex: 10,
    ...
  }}>
    <span>MACD(12,26,9)</span>
    <SignalTag ... />         {/* ← 浮于图表，可能遮挡最左侧数据 */}
  </div>
  ```

  虽然 `ChartSidebar` 中也展示了信号标签（文档流内），但图表本身的绝对定位浮层未按 PRD 移除。测试用例 TC-F3-12 将验证"标签位于副图标题栏文档流内，不以绝对定位浮于图表上方遮挡内容"。

  此外，当前实现造成**同一信号标签在一个面板中出现两次**（浮层 + 侧边栏），信息冗余。

- **修复建议**：移除各副图内的绝对定位标题浮层中的 `SignalTag`，改为仅在 `ChartSidebar` 中展示（该处已在文档流内）。折叠按钮可保留在绝对定位浮层（不含 SignalTag），或移至面板外部统一管理。

---

## P2（建议优化，不阻塞发布）

### [P2-01] `KDJPanel.jsx`：markArea 超买/超卖边界与 PRD 规定范围不一致（回归上轮 P2-02）

- **文件**：`web/src/components/KDJPanel.jsx` L193–206
- **问题描述**：

  上轮 CR（cr_report_iter3.md P2-02）已明确修复：超买上界 110→100，超卖下界 -10→0，符合 PRD "80~100 / 0~20" 规定。本迭代代码使用了更大范围：

  ```js
  // 超买区（80~120）
  [{ yAxis: 80 }, { yAxis: 120 }],  // ← 超出 PRD 规定的 100 上界
  // 超卖区（-20~20）
  [{ yAxis: -20 }, { yAxis: 20 }],  // ← 超出 PRD 规定的 0 下界
  ```

  Y 轴设为 `min: -10, max: 110` 以容纳 J 值超界，但 markArea 背景语义应与 PRD 中 KDJ 定义范围（80~100 / 0~20）一致。120 和 -20 超出 Y 轴显示范围，ECharts 会截断，视觉效果上与100/-0~0大致相同，但语义不准确，可能对用户产生误导。

- **修复建议**：
  ```js
  [{ yAxis: 80 }, { yAxis: 100 }],   // 超买区
  [{ yAxis: 0  }, { yAxis: 20  }],   // 超卖区
  ```
  Y 轴 `min: -10, max: 110` 保持不变，J 值仍可完整显示。

---

### [P2-02] `SignalBanner.jsx`：未显示股票名称/周期/日期上下文

- **文件**：`web/src/components/SignalBanner.jsx`、`web/src/pages/StockAnalysis.jsx` L296–302
- **问题描述**：

  PRD §3.1.2 UI 原型描述及原型 HTML 均展示了综合看板顶部应包含当前股票名称、代码、周期、日期等上下文：

  ```
  📊 技术面综合参考      贵州茅台 SH.600519   日K · 2026-03-18
  ```

  当前 `SignalBanner` 组件不接受也不展示股票名称、周期、日期。用户在综合看板上无法确认该信号对应的是哪只股票、哪个周期，信息可读性受影响。

- **修复建议**：`SignalBanner` 增加可选 Props `stockName`、`period`、`date`，在看板标题区展示。`StockAnalysis.jsx` 传入对应值。

---

### [P2-03] `SignalTag.jsx`：中性透明度 0.7，PRD 要求 0.6

- **文件**：`web/src/components/SignalTag.jsx` L36
- **问题描述**：

  ```js
  opacity: isNeutral ? 0.7 : 1,  // PRD 规定应为 0.6
  ```

  PRD §3.2.2 明确："状态为'中性'时……透明度降低 0.6（减少视觉干扰）"，代码为 0.7，视觉差异轻微但与规范不符。

- **修复建议**：
  ```js
  opacity: isNeutral ? 0.6 : 1,
  ```

---

### [P2-04] `compositeSignal.js`：MA 排列评分使用 MA5/MA20/MA60，与 PRD 示例（MA5/MA10/MA20）轻微偏差

- **文件**：`web/src/utils/compositeSignal.js` L73–87、L196–206
- **问题描述**：

  PRD §3.1.1 评分表：
  > MA5 > MA10 > MA20（多头排列）→ +2

  代码使用 MA5/MA20/MA60（与后端实际返回字段一致）进行排列判断，逻辑上合理，但与 PRD 文案中的 MA10 参数名不一致，且降级到仅有 MA5/MA20 时改为 ±1 分（非 PRD 定义内）。

  后端 indicator_engine.py 返回的是 MA5/MA20/MA60，并非 MA10，属于 PRD 文案笔误。建议确认后在 PRD 中修正该参数名，消除文档歧义。

- **修复建议**：维持现有 MA5/MA20/MA60 实现（与后端数据一致），在 PRD 上补注说明 MA10 为笔误，实际使用 MA20。

---

### [P2-05] `MainChart.jsx`：markPoint 的 `tooltip.formatter` 字符串在 `trigger: 'axis'` 模式下可能不生效

- **文件**：`web/src/components/MainChart.jsx` L83–85、L107–109
- **问题描述**：

  图表配置了 `tooltip.trigger: 'axis'`，且为 K线 series 下的 `markPoint.data` 每项设置了独立 `tooltip.formatter` 字符串。ECharts 中 `trigger: 'axis'` 会拦截鼠标悬停事件，优先展示轴触发型 tooltip，item-level tooltip formatter 通常**不会被渲染**。

  测试用例 TC-F3-09"悬停标记点时 Tooltip 显示事件类型、数值、免责声明"可能不通过。

  ```js
  tooltip: {
    formatter: `<b>📅 ${dates[i]}</b><br/>MACD 金叉信号...`,  // 可能不生效
  },
  ```

- **修复建议**：在 K线 series 的 `tooltip.formatter` 函数中，检测当前 `dataIndex` 是否为标记点触发的事件（ECharts v5 支持 `params.componentType === 'markPoint'`），并返回对应的标记点说明内容。或将图表整体 `trigger` 改为支持 item tooltip 的配置（注意需保持轴联动不受影响）。

---

## 通过项

### 1. 配色一致性（买=红/卖=绿）全局正确

| 检查点 | 结论 |
|--------|------|
| `colors.js` 配色常量定义（buy/sell/overbought/oversold） | ✅ 红买绿卖，与原型一致 |
| `signals.js` SIGNAL_COLORS 红买绿卖调换 | ✅ bullish→红，bearish→绿 |
| `signals.js` SIGNAL_LABELS 文案通俗化 | ✅ 展示具体指标名和数值 |
| `RSIPanel.jsx` 超买区绿底/超卖区红底 | ✅ 修正正确 |
| `KDJPanel.jsx` 超买区绿底/超卖区红底 | ✅ 修正正确 |
| `MACDPanel.jsx` 金叉红圈/死叉绿圈 | ✅ 遵循红买绿卖 |
| `SignalBanner.jsx` bullish=红系/bearish=绿系 | ✅ 与原型一致 |
| `BottomBar.jsx` 涨/跌颜色使用 C.candleUp/candleDown | ✅ 正确 |

### 2. 综合信号算法（compositeSignal.js）

| 评分规则 | 实现 | 结论 |
|---------|------|------|
| MACD 金叉（最近3根）+3 | `calcMACDScore` 检测最近 max(1, n-3) 到 n-1 范围 | ✅ 通过 |
| MACD 多头持续 +2 / 空头持续 -2 | `getLatest(dif) > getLatest(dea)` | ✅ 通过 |
| RSI 分区评分（20-30:+2, <20:+1, 30-50:+1, 50-70:+2, >70:-1）| `calcRSIScore` | ✅ 通过 |
| KDJ 金叉低位(K<30)+2 / 中位+1 | `calcKDJScore` break 找最近交叉 | ✅ 通过 |
| KDJ 死叉高位(K>70)-2 / 中位-1 | 同上 | ✅ 通过 |
| BOLL 价格<下轨+2 / >上轨-2 | `calcBOLLScore` | ✅ 通过 |
| BOLL 上方1/3+1 / 下方1/3-1 | `pos > 2/3 → +1`，`pos < 1/3 → -1` | ✅ 通过 |
| 综合结论映射（≥5:bullish, ≥2:bullish, ≥-1:neutral, ≥-4:bearish, else:bearish）| `getConclusion` | ✅ 通过 |
| `getLatest` 正确获取数组末尾非 null 值 | 从末尾反向查找 | ✅ 通过 |
| 空数据防御（dif/dea/rsi14 为空时返回 0）| 各函数有 length 检查 | ✅ 通过 |

### 3. 主图买卖标记点（MainChart.jsx）

| 检查点 | 结论 |
|--------|------|
| MACD 金叉检测算法（dif[i-1]<=dea[i-1] && dif[i]>dea[i]）| ✅ 正确 |
| 买标记：红圈（C.buy + C.buyBg）、位于 K 线低点 `*0.998`、`买▲` 17px 加粗 | ✅ 符合设计文档 |
| 卖标记：绿圈（C.sell + C.sellBg）、位于 K 线高点 `*1.002`、`卖▼` 17px 加粗 | ✅ 符合设计文档 |
| 密度保护：同一 K 线只标记一次（`markedIdx.has(i)` 检查）| ✅ 通过 |
| `showMarkers` prop 控制显示/隐藏，默认开启 | ✅ 通过 |
| 使用 `forwardRef` 暴露 ref | ✅ 正确 |

### 4. 滚轮缩放禁用

| 检查点 | 结论 |
|--------|------|
| `MainChart.jsx` 仅有 slider，无 `type: 'inside'` | ✅ 通过 |
| `MACDPanel.jsx` 仅有 slider | ✅ 通过 |
| `RSIPanel.jsx` 仅有 slider | ✅ 通过 |
| `KDJPanel.jsx` 仅有 slider | ✅ 通过 |

### 5. 副图折叠功能（StockAnalysis.jsx）

| 检查点 | 结论 |
|--------|------|
| localStorage 读取：`loadCollapseState()` 中 `JSON.parse` 带 try/catch | ✅ 安全 |
| 折叠状态写入：`togglePanel` 中每次更新同步写 localStorage | ✅ 正确 |
| 初始状态：`useState(loadCollapseState)` 懒初始化模式 | ✅ 正确 |
| 折叠 key：`quant_panel_collapse_state`（符合 PRD 非功能需求）| ✅ 通过 |
| 折叠后显示 32px 摘要行（面板标题 + 信号标签 + 展开按钮）| ✅ 实现 |

### 6. 跨图联动核心逻辑

| 检查点 | 结论 |
|--------|------|
| 使用 `updateAxisPointer` 而非 `echarts.connect()` | ✅ 正确设计 |
| `axesInfo.find(a => a.axisDim === 'x')` 获取 x 轴信息（兼容 K线区 + 成交量区）| ✅ 通过 |
| `dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex })` 同步副图 | ✅ 通过 |
| `mouseleave` → `hideTip` 清除所有副图浮窗 | ✅ 通过 |
| `dataZoom` 事件 → 同步副图 dataZoom 范围 | ✅ 通过 |
| 注册前 300ms 延迟确保图表初始化（`setTimeout 300`）| ✅ 合理 |

### 7. SignalTag 样式升级

| 检查点 | 结论 |
|--------|------|
| fontSize: `13px`（≥ PRD 要求 13px）| ✅ 通过 |
| minWidth: `100px` | ✅ 通过 |
| borderRadius: `6px`（PRD 要求 6px）| ✅ 通过 |
| padding: `5px 10px`（PRD 要求 5px 10px）| ✅ 通过 |
| textAlign: `center` | ✅ 通过 |
| 中性时 opacity 降低（0.7，P2-03 已标注）| ⚠️ 见 P2-03 |

### 8. 免责声明

| 检查点 | 结论 |
|--------|------|
| `SignalBanner.jsx` 底部免责声明常驻，无关闭按钮 | ✅ 通过 |
| 文字涵盖"不构成任何形式的投资建议"及"风险自负" | ✅ 通过 |
| 主图 markPoint tooltip 含"⚠️ 技术指标参考，非投资建议"（见 P2-05 关于能否显示的疑问）| ⚠️ 见 P2-05 |
| `compositeSignal.js` 文件头严禁交易逻辑声明 | ✅ 通过 |

### 9. 错误状态/加载状态（StockAnalysis.jsx）

| 检查点 | 结论 |
|--------|------|
| 接口失败显示错误横幅 + 重试按钮 | ✅ 通过（L275–291）|
| 首次加载中显示骨架屏（4个占位块，高度 500/200/200/200）| ✅ 通过（L476–499）|
| 无数据时显示友好提示文案（含 "至少需要60个交易日"）| ✅ 通过（L468–470）|
| 加载中显示 ⏳ 指示器 | ✅ 通过（L257）|

### 10. BottomBar 双层结构

| 检查点 | 结论 |
|--------|------|
| 第一层（收盘价/涨跌/PE/PB）始终可见 | ✅ 通过 |
| 第二层（指标标签）可折叠，默认展开 | ✅ 通过 |
| 两层间分割线 | ✅ 通过 |
| 折叠/展开按钮文案"折叠指标 ∧"/"展开指标 ∨" | ✅ 通过 |
| RSI/MACD/KDJ/BOLL/MA 五项指标标签 | ✅ 通过 |

### 11. 只读约束

- `StockAnalysis.jsx` 只调用 `fetchKline` / `fetchStocks`，无任何写操作 ✅
- 所有新增文件（compositeSignal.js、SignalBanner.jsx 等）均不含 API 写操作 ✅
- 无任何下单/报价逻辑，严格只读 ✅

---

## 总结

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 | 0 | 无阻塞发布问题 |
| P1 | 3 | 联动监听器泄漏、副图高度不符、信号标签绝对定位 |
| P2 | 5 | KDJ markArea 边界、横幅缺上下文、透明度 0.7≠0.6、MA 参数偏差、markPoint tooltip 问题 |

**建议**：P1-01（监听器泄漏）和 P1-02（高度不符）需修复后方可发布；P1-03（信号标签定位）若 ChartSidebar 已在文档流中展示，可接受当前实现作为临时方案，但需在下版本中清理冗余绝对定位层。P2 建议本迭代一并处理（改动量极小）。

---

## 响应式专项 CR（追加，2026-03-18）

> 应老板追加验收要求，对5个响应式布局检查点进行专项核查。
>
> **核查范围**：`web/src/pages/StockAnalysis.jsx`、`web/src/components/ChartSidebar.jsx`、`web/index.html`

---

### 检查点 1：宽屏自适应（图表区域随窗口拉伸）

**结论：✅ 通过，图表区域可随窗口正确拉伸**

- `StockAnalysis.jsx` 图表外层容器无固定 `width`，使用 `padding: '12px 20px'`，宽度随父级 `100%` 拉伸
- 每个图表行 `<div style={{ display: 'flex', ... }}>` 无 `maxWidth` 约束
- `MainChart.jsx`、`MACDPanel.jsx`、`RSIPanel.jsx`、`KDJPanel.jsx` 内层均使用 `flex: 1, minWidth: 0`，可无限向右拉伸 ✅
- `ChartSidebar.jsx` 使用 `width: 200, minWidth: 200`，固定宽度，**不随宽度拉伸**（见下方 P2-06）

---

### 检查点 2：ECharts resize 响应

**结论：✅ 通过，无需手动绑定 window.resize**

- 项目使用 `echarts-for-react`（`ReactECharts`），该库通过 **`ResizeObserver` 监听 DOM 容器尺寸变化**并自动调用 `echartsInstance.resize()`，无需手动绑定 `window.addEventListener('resize', ...)`
- `notMerge={true}` 配置确保 option 更新时不残留旧配置，不影响 resize 行为
- 副图折叠/展开采用**条件渲染**（`collapsed ? <折叠摘要> : <完整面板>`），展开时组件重新挂载，ECharts 实例从当前容器宽度初始化，无截断风险 ✅
- 折叠状态下 ECharts 实例不存在（组件卸载），无 resize 泄漏问题 ✅

---

### 检查点 3：侧边说明栏宽度合理性（1920px+ 超宽屏）

**结论：⚠️ 有改进空间，建议 P2 处理**

`ChartSidebar.jsx` 当前实现：
```jsx
<div style={{
  width:    200,
  minWidth: 200,
  // 无 maxWidth
  ...
}}>
```

| 视口宽度 | 图表区宽度（扣除侧边栏 200px + padding 40px）| 侧边栏占比 |
|---------|------------------------------------------|---------|
| 1440px | ≈ 1200px | 14% |
| 1920px | ≈ 1680px | 11% |
| 2560px | ≈ 2320px | 8% |

超宽屏（>1920px）侧边栏视觉偏窄，文字密度相对显得更高，但不影响核心功能。参见 **[P2-06]**。

---

### 检查点 4：最小宽度保底

**结论：❌ 缺失，存在布局压缩风险，建议 P2 处理**

- `web/index.html` `body` 样式无 `min-width` 属性
- `StockAnalysis.jsx` 根容器仅设 `minHeight: '100vh'`，无 `minWidth`
- `ChartSidebar` 有 `minWidth: 200`，图表区有 `minWidth: 0`（即可压缩至 0px）

当浏览器窗口收窄至 < 750px 时：
- 图表区会被压缩至极小（约 750 - 200 - 40 = 510px，再窄则 < 500px）
- ECharts 在容器极窄时绘制效果严重降级，X 轴日期重叠
- topbar 元素换行后多行堆叠，视觉混乱

参见 **[P2-07]**。

---

### 检查点 5：topbar 窄屏换行行为

**结论：✅ 主体换行正常，⚠️ 右侧工具栏内层缺 flexWrap**

- topbar 外层已设 `flexWrap: 'wrap'`，各子元素（Logo、StockSelector、PeriodSelector、TimeRangeSelector、右侧工具栏）在空间不足时会正确换行到下一行 ✅
- `StockSelector` 下拉 `minWidth: 180`，`PeriodSelector` 和 `TimeRangeSelector` 均为 flex 布局，各自元素有 `whiteSpace: 'nowrap'` 防止文字错断 ✅

**但存在一处问题**：

右侧工具栏容器（`marginLeft: 'auto'`）自身无 `flexWrap`:
```jsx
<div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
  <button>标记点 开</button>      {/* ~80px */}
  <span>⏳ 加载中...</span>       {/* ~60px */}
  <span>更新: 15:32:08</span>    {/* ~90px */}
  <Link>Watchlist总览 →</Link>   {/* ~100px */}
</div>
```

该 `div` 在 topbar 中会以 `marginLeft: auto` 挤占整行右侧，当剩余空间不足时整体换行到第二行，但换行后自身内部的4个子元素若仍放不下也**不会再次换行**（无 `flexWrap`），在 900~1024px 视口宽度下可能发生子元素溢出出界。参见 **[P2-08]**。

---

### 响应式专项新增问题

#### [P2-06] `ChartSidebar.jsx`：缺 `maxWidth` 约束，超宽屏（>1920px）视觉偏窄

- **文件**：`web/src/components/ChartSidebar.jsx` L41–51
- **问题描述**：

  侧边说明栏 `width: 200, minWidth: 200`，无 `maxWidth`。在 2560px 超宽屏下，200px 侧边栏仅占总宽的约 8%，视觉权重过低，侧边说明文字相对图表显得更小更密。

  PRD §F4 侧边说明栏要求宽度 200px（桌面浏览器），未强制规定超宽屏适配，但改进有意义。

- **修复建议**：增加响应式 `maxWidth`，在超宽屏时适度放宽说明栏：
  ```jsx
  // 方案一：简单增加 maxWidth
  <div style={{
    width:    200,
    minWidth: 200,
    maxWidth: 280,   // 超宽屏允许最大 280px
    ...
  }}>

  // 方案二（更佳）：使用百分比 + 约束
  <div style={{
    width:    '14%',
    minWidth: 160,
    maxWidth: 280,
    ...
  }}>
  ```

---

#### [P2-07] `StockAnalysis.jsx` / `index.html`：缺 `min-width` 保底，极窄屏图表压缩至 0

- **文件**：`web/index.html` L9、`web/src/pages/StockAnalysis.jsx` L212
- **问题描述**：

  无任何最小宽度约束，极窄视口（< 600px）下图表区 `flex: 1, minWidth: 0` 会被压缩至接近 0px，ECharts 在此情况下绘制结果严重失真（坐标轴标签重叠、蜡烛图不可见）。

  项目定位为桌面浏览器个人工具，移动端不做要求，但应设置合理的最小宽度保证桌面最小化窗口下不破坏布局。

- **修复建议（任选一种）**：

  方案一：`index.html` 全局样式追加：
  ```css
  body { min-width: 900px; }
  ```

  方案二：`StockAnalysis.jsx` 根容器追加：
  ```jsx
  <div style={{ minHeight: '100vh', minWidth: 900, background: C.chartBg, color: C.text }}>
  ```

  900px 以下允许横向滚动条出现，布局不变形。

---

#### [P2-08] `StockAnalysis.jsx`：topbar 右侧工具栏内层缺 `flexWrap`，900~1024px 可能溢出

- **文件**：`web/src/pages/StockAnalysis.jsx` L238
- **问题描述**：

  ```jsx
  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
    // 标记点按钮 + 加载状态 + 更新时间 + Watchlist 链接
    // 无 flexWrap
  </div>
  ```

  topbar 外层已有 `flexWrap: 'wrap'`，但右侧工具栏 `div` 自身无 `flexWrap`。在 900~1024px 视口宽度下，工具栏会整体换行到第二行，若该行宽度仍不足（如恰好 900px），内部4个子元素（共约 330px）**无法再换行**，`marginLeft: 'auto` 也会使 Watchlist 链接被推出视口右侧。

- **修复建议**：
  ```jsx
  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10,
    flexWrap: 'wrap', justifyContent: 'flex-end' }}>
  ```

---

### 响应式专项小结

| 检查点 | 结论 |
|--------|------|
| 1. 宽屏自适应（图表区域拉伸）| ✅ 通过，MainChart 等组件均 `flex:1` |
| 2. ECharts resize 响应 | ✅ 通过，ReactECharts 内置 ResizeObserver |
| 3. 侧边说明栏超宽屏 | ⚠️ P2-06：缺 `maxWidth`，超宽屏偏窄 |
| 4. 最小宽度保底 | ⚠️ P2-07：缺 `min-width: 900px`，极窄屏图表压缩失真 |
| 5. topbar 换行行为 | ⚠️ P2-08：右侧工具栏内层无 `flexWrap`，窄屏可能溢出 |

**响应式专项新增 P2 缺陷 3 条（P2-06 / P2-07 / P2-08），均不影响正常桌面使用，建议本迭代顺带处理。**

---

## 总结（更新版）

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 | 0 | 无阻塞发布问题 |
| P1 | 3 | 联动监听器泄漏、副图高度不符、信号标签绝对定位 |
| P2 | 8 | KDJ markArea 边界、横幅缺上下文、透明度 0.7≠0.6、MA 参数偏差、markPoint tooltip、侧边栏缺 maxWidth、缺 min-width 保底、topbar 内层缺 flexWrap |

**建议**：P1-01（监听器泄漏）和 P1-02（高度不符）需修复后方可发布；P1-03（信号标签定位）可接受当前实现作为临时方案。P2（含响应式3条）建议本迭代一并处理，改动量极小。

---

*CR 报告 v1.1，2026-03-18，QA（v1.0 初版 → v1.1 追加响应式专项）*

---

## 复查记录 v1.2（2026-03-18，Dev 提交第二轮修复后）

> **复查范围**：P1-01 / P1-02 / P1-03 三项 P1 缺陷 + 响应式专项是否新增 P0/P1

---

### [复查] P1-01：useChartSync cleanup 泄漏修复

**结论：✅ 已修复，通过复查**

读取 `web/src/hooks/useChartSync.js`，确认修复内容：

- L18：`let cleanup = null` 在 `setTimeout` 外部声明 ✅
- L60–64：`cleanup = () => { main.off(...); mainDom.removeEventListener(...) }` 在 `setTimeout` 内部赋值 ✅
- L68–71：`return () => { clearTimeout(timer); cleanup?.() }` 从 `useEffect` 函数体直接返回，React 可正确调用 ✅

三个监听器（`updateAxisPointer`、`dataZoom`、`mouseleave`）的清理函数均已纳入 React cleanup 机制，副图折叠/展开及路由切换时不再发生事件监听器叠加泄漏。

---

### [复查] P1-02：副图高度与 PRD 不一致

**结论：❌ 未修复，P1-02 仍存在**

读取三个面板文件，高度均未调整：

| 文件 | 代码高度 | PRD 要求高度 | 修复结论 |
|------|---------|------------|---------|
| `MACDPanel.jsx` L246 | `style={{ height: 200 }}` | 180px | ❌ 未修复 |
| `RSIPanel.jsx` L214 | `style={{ height: 200 }}` | 160px | ❌ 未修复 |
| `KDJPanel.jsx` L273 | `style={{ height: 200 }}` | 160px | ❌ 未修复 |

各文件头注释仍保留"高度 140 → 200px"说明，确认 Dev 本轮未调整此项。P1-02 继续阻塞发布。

**需 Dev 重新修复**：
```jsx
// MACDPanel.jsx L246
style={{ height: 180 }}

// RSIPanel.jsx L214
style={{ height: 160 }}

// KDJPanel.jsx L273
style={{ height: 160 }}
```

---

### [复查] P1-03：副图 position:absolute 绝对定位层 SignalTag 删除

**结论：✅ 已修复，三个面板均通过复查**

| 文件 | 绝对定位 div 内容 | SignalTag | 修复结论 |
|------|----------------|---------|---------|
| `MACDPanel.jsx` L212–223（MACDPanelInner） | 仅 `<span>MACD(12,26,9)</span>` + 注释 | 已删除 ✅ | ✅ 通过 |
| `RSIPanel.jsx` L180–191（RSIPanelInner） | 仅 `<span>RSI(14)</span>` | 已删除 ✅ | ✅ 通过 |
| `KDJPanel.jsx` L239–250（KDJPanelInner） | 仅 `<span>KDJ(9)</span>` | 已删除 ✅ | ✅ 通过 |

三个面板均已添加注释：`{/* 面板标题行（仅标题文字，信号标签由 ChartSidebar 统一展示，避免重复） */}`，明确说明 SignalTag 已移至 ChartSidebar，不再重复显示。

注意：折叠状态（collapsed=true 分支）的摘要行中 SignalTag 保留（MACDPanel L42、RSIPanel L47、KDJPanel L51），这是合理的——折叠时侧边栏不存在，摘要行显示信号标签属于正常设计，**不属于缺陷**。

---

### [复查] 响应式专项是否新增 P0/P1

**结论：✅ 无新增 P0/P1**

响应式专项 3 条缺陷（P2-06 / P2-07 / P2-08）均为 P2 级别，未随本轮修复引入新 P0 或 P1 问题，不阻塞发布。

---

### 复查总结

| 缺陷 | 本轮复查结论 | 当前状态 |
|------|------------|---------|
| P1-01 useChartSync cleanup 泄漏 | ✅ 已修复 | 关闭 |
| P1-02 副图高度 MACD/RSI/KDJ 均为 200px | ❌ **未修复** | 持续阻塞 |
| P1-03 三个面板绝对定位 SignalTag | ✅ 已修复 | 关闭 |
| 响应式专项 P0/P1 | ✅ 无 P0/P1 | — |

**本轮 CR 结论**：P1-02（副图高度）未修复，发布仍被阻塞。需 Dev 将 MACDPanel height 改为 180px、RSIPanel / KDJPanel height 改为 160px，重新提交后方可进行第三轮复查。

---

*CR 报告 v1.2，2026-03-18，QA（v1.2 追加第二轮复查记录）*

---

## 复查记录 v1.3（2026-03-18，Dev 提交第三轮修复后）

> **复查范围**：
> 1. 补充确认 P1-01 / P1-03 复查结论（已在 v1.2 记录，此处集中确认）
> 2. P2-06 / P2-07 / P2-08 响应式修复验证

---

### P1 复查结论（集中确认）

| 缺陷 | 结论 | 说明 |
|------|------|------|
| **P1-01** useChartSync cleanup 泄漏 | ✅ **已修复，通过** | `let cleanup = null` 在 setTimeout 外声明，内部赋值，`cleanup?.()` 在 useEffect return 中正确执行 |
| **P1-02** 副图高度 MACD/RSI/KDJ 均为 200px | ✅ **裁定关闭（非 Bug）** | 200px 系老板在原型评审中明确确认的正确值；PRD 中 MACD=180/RSI=160/KDJ=160 为 PM 文档笔误。代码保持 200px 不变，Dev 已在 `docs/design_iter3_ui.md` 加注记说明，裁定操作完全正确。 |
| **P1-03** 三个面板绝对定位 SignalTag | ✅ **已修复，通过** | MACDPanelInner / RSIPanelInner / KDJPanelInner 绝对定位浮层内 SignalTag 已删除，仅保留标题文字 |

---

### [复查] P2-06：ChartSidebar 响应式宽度

**结论：✅ 已修复，通过复查**

读取 `web/src/components/ChartSidebar.jsx` L41–51，确认修复内容：

```jsx
<div style={{
  width:    '14%',    // ✅ 改为百分比，随视口自适应
  minWidth: 200,      // ✅ 保留最小宽度
  maxWidth: 280,      // ✅ 新增最大宽度，超宽屏不会过度拉伸
  ...
}}>
```

采用设计建议中的"方案二（更佳）"，`width: '14%'` + `minWidth: 200` + `maxWidth: 280`，响应式布局正确，超宽屏下侧边栏视觉合理。

---

### [复查] P2-07：index.html body min-width

**结论：✅ 已修复，通过复查**

读取 `web/index.html` L9–10，确认修复内容：

```css
body { font-family: ...; background: #0d1117; color: #e6edf3; min-width: 900px; }
```

`min-width: 900px` 已写入 body 样式，窗口收窄至 900px 以下将出现横向滚动条，不再破坏布局。

---

### [复查] P2-08：topbar 右侧工具栏 flexWrap

**结论：✅ 已修复，通过复查**

读取 `web/src/pages/StockAnalysis.jsx` L238，确认修复内容：

```jsx
<div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10,
              flexWrap: 'wrap', justifyContent: 'flex-end' }}>
```

`flexWrap: 'wrap'` 和 `justifyContent: 'flex-end'` 均已添加，与 P2-08 修复建议完全一致。900~1024px 视口宽度下工具栏子元素可正确换行，不再出现溢出出界问题。

---

### 最终 CR 汇总

| 级别 | 总数 | 状态 |
|------|------|------|
| **P0** | 0 | — 无 P0 问题 |
| **P1** | 3 | P1-01 ✅ 已修复关闭 / P1-02 ✅ 裁定关闭 / P1-03 ✅ 已修复关闭 |
| **P2** | 8 | P2-01~P2-05 遗留（不阻塞）/ P2-06 ✅ / P2-07 ✅ / P2-08 ✅ |

**发布阻塞状态**：**无阻塞项。**

> **P1-02 裁定说明**（team-lead 裁定，2026-03-18）：副图高度 200px 为老板在原型评审中明确确认的正确值。PRD §3.2.1 中 MACD=180px / RSI=160px / KDJ=160px 系 PM 撰写文档时的笔误，已在 `docs/design_iter3_ui.md` v1.1 中加注说明。代码保持 200px 不改，本条以「裁定关闭」结案，不阻塞发布。

**最终结论**：✅ **本轮 CR 通过，无阻塞项，可进入完整测试执行。**

---

*CR 报告 v1.4，2026-03-18，team-lead（v1.4 修正 P1-02 状态为裁定关闭，更新最终结论）*
