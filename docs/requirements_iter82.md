# PRD v0.8.2-patch — 副图图例图标缺失修复

**版本**：v1.0
**日期**：2026-03-25
**作者**：PM
**状态**：已确认，可启动研发

---

## 1. 问题描述

各指标副图（MACD / RSI / KDJ / VPA-Defender）右侧 ChartSidebar 中，部分图例条目的图标（由 `LegendMark` 组件渲染）显示为通用方块，而非预期的柱形图标，与图表中对应系列（柱状图）的视觉形态不匹配，用户感知为"图标缺失"或"图标形状不对"。

---

## 2. 根因分析

### 2.1 `LegendMark` 支持的 type 枚举

`web/src/components/ChartSidebar.jsx` 中 `LegendMark` 组件当前实现如下：

| type 值    | 渲染方式              | 是否有专属分支 |
|------------|----------------------|---------------|
| `'line'`   | 18×2px 实线横条       | ✅ 有         |
| `'dashed'` | 18px 宽虚线横条       | ✅ 有         |
| `'circle'` | 8×8px 圆形            | ✅ 有         |
| `'dot'`    | 7×7px 小圆形          | ✅ 有         |
| `'bar'`    | **fallback 方块（10×10px，borderRadius:2）** | ❌ **无专属分支** |

**根因**：`LegendMark` 缺少对 `type='bar'` 的专门渲染分支。当传入 `type='bar'` 时，组件直接走 fallback，渲染为 10×10 的通用方块，而非竖向柱形图标，与图表中柱状图（bar series）的视觉形态不匹配。

### 2.2 受影响的 legendItems 条目

#### MACD 副图（`StockAnalysis.jsx` 中 `macdSidebarLegend`）

```js
{ color: C.macdBarPos, type: 'bar', label: '柱(正)', seriesName: 'MACD柱' },  // ❌ bar → fallback 方块
{ color: C.macdBarNeg, type: 'bar', label: '柱(负)', seriesName: 'MACD柱' },  // ❌ bar → fallback 方块
```

#### RSI 副图（`StockAnalysis.jsx` 中 `rsiSidebarLegend`）

```js
{ color: C.sell, type: 'bar', label: '超买区(卖)' },  // ❌ bar → fallback 方块
{ color: C.buy,  type: 'bar', label: '超卖区(买)' },  // ❌ bar → fallback 方块
```

#### KDJ 副图（`kdjSidebarLegend`）

```js
{ color: C.kLine, type: 'line',   label: 'K线' },   // ✅ 无问题
{ color: C.dLine, type: 'line',   label: 'D线' },   // ✅ 无问题
{ color: C.jLine, type: 'dashed', label: 'J线' },   // ✅ 无问题
{ color: C.buy,   type: 'circle', label: '金叉' },  // ✅ 无问题
{ color: C.sell,  type: 'circle', label: '死叉' },  // ✅ 无问题
```

#### VPA-Defender 副图（`vpaSidebarLegend`）

```js
{ color: '#8b949e', type: 'line',   ... },  // ✅ 无问题
{ color: '#ef5350', type: 'line',   ... },  // ✅ 无问题
{ color: '#ff7043', type: 'line',   ... },  // ✅ 无问题
{ color: '#42a5f5', type: 'line',   ... },  // ✅ 无问题
{ color: '#ffa726', type: 'dashed', ... },  // ✅ 无问题
```

### 2.3 受影响的 HELP_ITEMS（说明浮层图标）

#### MACDPanel.jsx

```js
{ iconType: 'bar', color: C.macdBarPos, text: 'MACD 柱（正）...' },  // ❌ bar → fallback 方块
{ iconType: 'bar', color: C.macdBarNeg, text: 'MACD 柱（负）...' },  // ❌ bar → fallback 方块
```

#### RSIPanel.jsx

```js
{ iconType: 'bar', color: C.sell, text: '超买区...' },  // ❌ bar → fallback 方块
{ iconType: 'bar', color: C.buy,  text: '超卖区...' },  // ❌ bar → fallback 方块
```

#### KDJPanel.jsx — **无问题**，全部使用 `line`/`dashed`/`circle`，均有专属分支。

#### VPADefenderPanel.jsx — **无问题**，全部使用 `line`/`dashed`/`dot`，均有专属分支。

### 2.4 影响汇总

| 副图 | 受影响条目数 | 位置 |
|------|------------|------|
| MACD | 2（legendItems）+ 2（HELP_ITEMS） | ChartSidebar 图例 + 说明浮层 |
| RSI  | 2（legendItems）+ 2（HELP_ITEMS） | ChartSidebar 图例 + 说明浮层 |
| KDJ  | 0 | — |
| VPA  | 0 | — |

---

## 3. 修复方案

### 方案（唯一推荐）：在 `LegendMark` 中新增 `bar` 类型专属渲染分支

**修改文件**：`web/src/components/ChartSidebar.jsx`

**位置**：`LegendMark` 函数中，在 `dot` 分支之后、fallback 之前，新增以下分支：

```js
if (type === 'bar') {
  return (
    <span style={{
      width:        6,
      height:       12,
      borderRadius: 1,
      background:   color,
      flexShrink:   0,
      display:      'inline-block',
    }} />
  )
}
```

**渲染效果**：6×12px 竖向矩形，视觉上类似柱状图中的柱形，与 ECharts bar series 图例形态一致。

**不修改其他文件**：`StockAnalysis.jsx` 中 `legendItems` 的 `type: 'bar'` 字段定义正确，`MACDPanel.jsx` / `RSIPanel.jsx` 中 `HELP_ITEMS` 的 `iconType: 'bar'` 字段定义正确，均无需更改——修复 `LegendMark` 本体即可自动修复所有受影响条目。

---

## 4. 影响文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `web/src/components/ChartSidebar.jsx` | **修改**（小） | `LegendMark` 函数新增 `bar` 类型分支，约 9 行代码 |

---

## 5. 不涉及文件（确认无需修改）

- `web/src/pages/StockAnalysis.jsx`：`legendItems` 的 `type` 字段均正确，无需修改
- `web/src/components/MACDPanel.jsx`：`HELP_ITEMS` 的 `iconType` 字段均正确，无需修改
- `web/src/components/RSIPanel.jsx`：同上
- `web/src/components/KDJPanel.jsx`：无受影响条目
- `web/src/components/VPADefenderPanel.jsx`：无受影响条目
- 所有后端文件：本次修复纯前端问题

---

## 6. 验收标准（AC）

### AC-01：MACD 副图 ChartSidebar 图例
- [ ] `柱(正)` 条目：图标显示为竖向柱形（非方块），颜色为正柱色（`C.macdBarPos`）
- [ ] `柱(负)` 条目：图标显示为竖向柱形（非方块），颜色为负柱色（`C.macdBarNeg`）
- [ ] `DIF` / `DEA` 条目：图标为实线横条，无变化（回归）
- [ ] `金叉` / `死叉` 条目：图标为圆形，无变化（回归）

### AC-02：RSI 副图 ChartSidebar 图例
- [ ] `超买区(卖)` 条目：图标显示为竖向柱形（非方块），颜色为卖出色（`C.sell`）
- [ ] `超卖区(买)` 条目：图标显示为竖向柱形（非方块），颜色为买入色（`C.buy`）
- [ ] `RSI(14)` 条目：图标为实线横条，无变化（回归）

### AC-03：MACD 说明浮层（点击 [?] 展开后）
- [ ] `MACD 柱（正）` 条目：图标显示为竖向柱形（非方块）
- [ ] `MACD 柱（负）` 条目：图标显示为竖向柱形（非方块）
- [ ] 其他条目（DIF 实线、DEA 实线、金叉圆形、死叉圆形）：图标无变化（回归）

### AC-04：RSI 说明浮层（点击 [?] 展开后）
- [ ] `超买区（RSI > 70）` 条目：图标显示为竖向柱形（非方块）
- [ ] `超卖区（RSI < 30）` 条目：图标显示为竖向柱形（非方块）
- [ ] 其他条目：图标无变化（回归）

### AC-05：KDJ 副图（回归验证）
- [ ] K线 / D线 / J线 / 金叉 / 死叉 图例图标均正常显示，与修复前一致

### AC-06：VPA-Defender 副图（回归验证）
- [ ] 收盘价 / 防守线 / 阻力线 / OBV / OBV均线 图例图标均正常显示，与修复前一致

### AC-07：主图（回归验证）
- [ ] 主图 ChartSidebar 图例图标均正常显示，无任何副作用（主图 legendItems 不含 `bar` 类型，但需确认 fallback 行为未被意外影响）

---

## 7. 开发工作量估算

| 项目 | 估算 |
|------|------|
| 代码改动行数 | ~9 行（新增 `bar` 分支） |
| 开发时间 | 15 分钟 |
| 测试时间 | 30 分钟（手工验证各副图） |
| 风险等级 | 低（纯新增分支，不影响其他 type 的渲染逻辑） |

---

## 8. 备注

- **本 patch 仅修改前端渲染逻辑，无后端变更，无数据库变更，无 API 变更。**
- 修复完成后请打 tag `v0.8.2-patch`，并同步更新 `config/settings.py` 中的 `APP_VERSION` 硬编码值。
- 本 patch 不影响 FEAT-legend-toggle（图例点击切换）功能，`bar` 类型的 MACD 柱条目点击切换逻辑无需修改。
