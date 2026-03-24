# 迭代8 变更报告（CR Report）

**文档版本**：v1.0
**日期**：2026-03-24
**作者**：QA
**审查基准**：requirements_iter8.md v1.2 / test_cases_iter8.md v1.0
**结论**：✅ **全部通过，建议合并**

---

## 一、审查概况

| 项目 | 内容 |
|------|------|
| 审查文件数 | 8 个 |
| 变更功能点 | 7 个（2 个 P0 BUG + 1 个 P1 BUG + 1 个 P1 FEAT-CLI + 3 个 P1 FEAT-UI） |
| AC 覆盖数 | 全部 36 条 AC（BUG-emoji×4 + BUG-align×5 + BUG-vpa-color×6 + FEAT-check-gaps-log×6 + FEAT-guide-top×8 + FEAT-collapse-btn×6 + FEAT-guide-icon×6）|
| 代码审查通过率 | **100%**（8/8 文件全部通过） |
| 发现阻塞问题 | 0 |
| 发现轻微问题 | 0 |

---

## 二、各变更点审查结论

---

### 2.1 BUG-emoji：VPA 折叠/展开按钮乱码修复 ✅ 通过

**审查文件**：`web/src/components/VPADefenderPanel.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-emoji-1 | 折叠态展开按钮显示 `∨`，不出现 `\u2228` 字面量 | ✅ 通过 | L99：`>∨</button>`，直接 Unicode 字符 |
| AC-emoji-2 | 展开态折叠按钮显示 `∧`，写法为直接 Unicode 字符（与 MACD/RSI/KDJ 相同） | ✅ 通过 | 折叠按钮已迁至 ChartSidebar（`>∧</button>`），写法一致 |
| AC-emoji-3 | 按钮点击功能正常，能正确展开/折叠 | ✅ 通过 | collapsed state 正确驱动渲染分支 |
| AC-emoji-4 | 代码中两处修改均使用直接 Unicode 字符，无 escape 序列和 JS 表达式包裹 | ✅ 通过 | 全文搜索无 `\u2228`、`\u2227`、`{'\u2227'}` 字样 |

**修复细节**：
- 原 L90 `\u2228` → 现 L99 直接字符 `∨`（JSX 文本）
- 原 L329 `{'\u2227'}` → 折叠按钮迁移至 ChartSidebar，统一使用 `∧`
- 与 MACDPanel/RSIPanel/KDJPanel 写法完全一致，规范统一 ✅

---

### 2.2 BUG-align：各图表 Y 轴与内容区横向宽度对齐 ✅ 通过

**审查文件**：`MainChart.jsx` / `MACDPanel.jsx` / `RSIPanel.jsx` / `KDJPanel.jsx` / `VPADefenderPanel.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-align-1 | 各图绘图内容区左边界偏差 ≤ 2px | ✅ 通过 | 所有图均使用 `left: 60, right: 60`（详见下表） |
| AC-align-2 | hover 时各图十字线纵轴辅助线垂直方向对齐 | ✅ 通过（代码层面） | grid 统一值确保对齐，runtime 需人工验证 |
| AC-align-3 | 日期标签无截断、无换行 | ✅ 通过 | `axisLabel: { width: 52, overflow: 'truncate' }` 各图均已添加 |
| AC-align-4 | VPA 右侧 OBV 轴数值标签无溢出 | ✅ 通过 | VPA 右侧 yAxis 同步添加 `width: 52, overflow: 'truncate'` |
| AC-align-5 | 折叠任意副图后重新展开，对齐效果不变 | ✅ 通过（代码层面） | ECharts 选项为静态配置，折叠/展开不修改 grid 值 |

**各文件 grid 配置汇总**：

| 组件 | grid.left | grid.right | containLabel | axisLabel.width |
|------|-----------|------------|--------------|-----------------|
| MainChart（K线区） | 60 | 60 | 无（已移除） | 52 |
| MainChart（成交量区）| 60 | 60 | 无（已移除） | 52 |
| MACDPanel | 60 | 60 | 无（已移除） | 52 |
| RSIPanel | 60 | 60 | 无（已移除） | 52 |
| KDJPanel | 60 | 60 | 无（已移除） | 52 |
| VPADefenderPanel | 60 | 60 | false（原有，不变） | 52（左右 yAxis 均设置）|

> ✅ 所有图表完全统一，消除了原来因 `containLabel: true` + 动态标签宽度导致的内容区错位问题。

---

### 2.3 BUG-vpa-color：VPA 破位警示颜色修正 ✅ 通过

**审查文件**：`VPADefenderPanel.jsx` / `StockAnalysis.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-vpa-color-1 | 破位警示色带颜色为绿色系（`#2ea04330`）| ✅ 通过 | `SIGNAL_CONFIG[3].color = '#2ea043'`，markArea 用 `${cfg.color}30` 自动生成半透明值 |
| AC-vpa-color-2 | 折叠条信号 badge 破位警示为绿色 `#2ea043` | ✅ 通过 | `sigCfg.color` 由 SIGNAL_CONFIG 动态取值，自动跟随 |
| AC-vpa-color-3 | 展开状态面板标题行 badge 破位警示为绿色 | ✅ 通过 | 同上 |
| AC-vpa-color-4 | 说明浮层 [?] 中破位警示颜色圆点为绿色，文案含"绿色（破位警示）" | ✅ 通过 | `HELP_ITEMS[5].color = '#2ea043'`，text 已更新为"绿色（破位警示）" |
| AC-vpa-color-5 | vpaSidebarGuide 中破位警示颜色同步为绿色 | ✅ 通过 | `StockAnalysis.jsx L259: dotColor: '#2ea043'`，text 已更新 |
| AC-vpa-color-6 | 共振主升浪（`#26a69a`）与破位警示（`#2ea043`）视觉可区分 | ✅ 通过（代码层面） | 两个色值差异明显（teal 青绿 vs 纯绿），runtime 需人工肉眼确认 |

**颜色变更前后对比**：

| 信号 | 变更前 | 变更后 | 符合规范 |
|------|--------|--------|---------|
| SIGNAL_CONFIG[3].color | `#ef5350`（红） | `#2ea043`（卖出绿） | ✅ A股红涨绿跌 |
| SIGNAL_CONFIG[3].emoji | `🔴` | `🟢` | ✅ emoji 与颜色对应 |
| HELP_ITEMS[5].color | `#ef5350` | `#2ea043` | ✅ |
| HELP_ITEMS[5].text | "红色（破位警示）" | "绿色（破位警示）" | ✅ |
| vpaSidebarGuide[3].dotColor | `#ef5350` | `#2ea043` | ✅ |
| vpaSidebarGuide[3].text | "红色（破位警示）" | "绿色（破位警示）" | ✅ |

---

### 2.4 FEAT-check-gaps-log：check-gaps 日志日期展示增强 ✅ 通过

**审查文件**：`main.py`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-gaps-log-1 | 1D 日期格式为 `YYYY-MM-DD`，与数据库一致 | ✅ 通过 | `_format_gap_date(d, '1D')` 原样返回 |
| AC-gaps-log-2 | 1W 日期转换为当周周一 | ✅ 通过 | `d - timedelta(days=d.weekday())`（weekday() 0=周一，正确） |
| AC-gaps-log-3 | 1M 日期转换为 `YYYY-MM-01` | ✅ 通过 | `date_str[:7] + '-01'`，字符串截取，简洁正确 |
| AC-gaps-log-4 | 数据库写入值不受影响 | ✅ 通过 | 转换函数仅用于日志格式化字符串，`upsert_gaps` 调用前的原始 `s/e` 变量未被修改 |
| AC-gaps-log-5 | 汇总输出数量与日志一致，无 bug | ✅ 通过 | 计数逻辑独立于格式化，仅对展示字符串调用 `_format_gap_date` |
| AC-gaps-log-6 | 不传 `--period` 时三周期各自正确输出 | ✅ 通过 | 函数接收 `period` 参数，每个周期独立调用，无混淆 |

**关键代码审查**：

```python
# main.py — _format_gap_date（L614-L629 附近）
def _format_gap_date(date_str: str, period: str) -> str:
    if period == '1D':
        return date_str                                    # ✅ 原样
    elif period == '1W':
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        monday = d - timedelta(days=d.weekday())           # ✅ 周五→周一
        return monday.strftime('%Y-%m-%d')
    elif period == '1M':
        return date_str[:7] + '-01'                        # ✅ 月初
    return date_str                                        # ✅ 兜底

# 日志格式化调用（L631-L635 附近）
gap_strs = [
    f"{_format_gap_date(s, period)}~{_format_gap_date(e, period)}"
    for s, e in gaps
]
```

> ✅ 实现与需求文档 §2.21 给出的参考代码完全一致，逻辑正确。

---

### 2.5 FEAT-guide-top：说明浮层 [?] 统一移至各面板顶部 ✅ 通过

**审查文件**：`MACDPanel.jsx` / `RSIPanel.jsx` / `KDJPanel.jsx` / `VPADefenderPanel.jsx` / `ChartSidebar.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-guide-1 | MACD 面板标题行有 [?]，说明含"金叉""死叉""MACD 柱" | ✅ 通过 | `MACDPanel.jsx` L233-249，HELP_ITEMS 含对应条目 |
| AC-guide-2 | RSI 面板标题行有 [?]，说明含"超买""超卖""中性区间" | ✅ 通过 | `RSIPanel.jsx` L199-214，HELP_ITEMS 含对应条目 |
| AC-guide-3 | KDJ 面板标题行有 [?]，说明含"金叉""死叉""J 线" | ✅ 通过 | `KDJPanel.jsx` L257-272，HELP_ITEMS 含对应条目 |
| AC-guide-4 | VPA 顶部 [?] 保留；ChartSidebar 不再有 [?] 和说明文案 | ✅ 通过 | VPA [?] 在面板顶部保留；ChartSidebar 已移除 guideItems 渲染逻辑 |
| AC-guide-5 | 默认加载时说明浮层均为隐藏 | ✅ 通过 | 各 Panel 的 `showHelp` 初始值均为 `false` |
| AC-guide-6 | 说明浮层颜色圆点与右侧图例颜色一一对应 | ✅ 通过（代码层面） | HELP_ITEMS 中 `color`/`dotColor` 值与 ECharts series 颜色来源一致 |
| AC-guide-7 | ChartSidebar 的 `guideItems` prop 接口保留（不 breaking） | ✅ 通过 | ChartSidebar 保留 prop 接口定义，渲染逻辑已注释/移除 |
| AC-guide-8 | 说明文案不含买卖操作指令 | ✅ 通过 | 全部文案为指标解释性描述，无"买入"/"卖出"/"建仓"等词 |

**各面板说明内容审查**：

| 面板 | 说明条目数 | 关键词覆盖 | 无操作指令 |
|------|----------|----------|----------|
| MACD | 6 条 | 金叉 ✅ / 死叉 ✅ / MACD 柱 ✅ | ✅ |
| RSI | 4 条 | 超买 ✅ / 超卖 ✅ / 中性区间 ✅ | ✅ |
| KDJ | 5 条 | 金叉 ✅ / 死叉 ✅ / J 线 ✅ | ✅ |
| VPA | 7 条 | 防守线 ✅ / OBV ✅ / 四象限 ✅ | ✅ |

---

### 2.6 FEAT-collapse-btn：折叠按钮统一移至 ChartSidebar 右上角 ✅ 通过

**审查文件**：`ChartSidebar.jsx` / `MACDPanel.jsx` / `RSIPanel.jsx` / `KDJPanel.jsx` / `VPADefenderPanel.jsx` / `StockAnalysis.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-collapse-1 | 展开状态折叠按钮（`∧`）在 ChartSidebar 区域，不在图表区标题行 | ✅ 通过 | ChartSidebar.jsx L62-78：`position: absolute, top: 8, right: 8` |
| AC-collapse-2 | 点击 ChartSidebar 折叠按钮，整行正确收缩为 32px 折叠条 | ✅ 通过 | `onToggle` prop 回调触发 StockAnalysis 的 collapsed state |
| AC-collapse-3 | 折叠条右端展开按钮（`∨`）位置和功能不变 | ✅ 通过 | 各 Panel 折叠态仍在折叠条右端渲染 `∨` 展开按钮 |
| AC-collapse-4 | 图表区标题行展开态仅含：指标名称、信号标签、[?] 按钮 | ✅ 通过 | 各 PanelInner 标题行已移除折叠按钮，仅保留名称+信号+[?] |
| AC-collapse-5 | 折叠状态 localStorage 持久化逻辑不受影响 | ✅ 通过 | `collapsed` state 管理逻辑在 StockAnalysis 层，未被修改 |
| AC-collapse-6 | 顶部"显示副图"快捷按钮功能不受影响 | ✅ 通过 | 顶部按钮触发 `togglePanel()` 函数，与 ChartSidebar `onToggle` 共享同一 state |

**ChartSidebar 折叠按钮实现审查**：

```jsx
// ChartSidebar.jsx（关键片段）
// - onToggle prop 存在时渲染折叠按钮（∧）
// - position: absolute; top: 8px; right: 8px
// - 容器已设置 position: relative
{onToggle && (
  <button onClick={onToggle} style={{ position: 'absolute', top: 8, right: 8, ... }}>
    ∧
  </button>
)}
```

> ✅ 符合需求 §2.16 规则1：`position: absolute; top: 8px; right: 8px`，不影响 Sidebar 内容区 flex 布局。

**StockAnalysis.jsx onToggle 传递审查**：

| 副图 | 折叠态传递 | 展开态传递 |
|------|----------|----------|
| MACD ChartSidebar | ✅ L451 | ✅ L456 |
| RSI ChartSidebar | ✅ L484 | ✅ L489 |
| KDJ ChartSidebar | ✅ L516 | ✅ L521 |
| VPA ChartSidebar | ✅ L550 | ✅ L555 |

> ✅ 所有 8 处调用均正确传入 `onToggle={() => togglePanel('XXX')}`，无遗漏。

---

### 2.7 FEAT-guide-icon：说明浮层图标形状与右侧图例保持一致 ✅ 通过

**审查文件**：`VPADefenderPanel.jsx` / `MACDPanel.jsx` / `RSIPanel.jsx` / `KDJPanel.jsx` / `ChartSidebar.jsx` / `StockAnalysis.jsx`

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-guide-icon-1 | MACD 浮层：DIF/DEA=实线，金叉/死叉=小圆，MACD 柱=方块 | ✅ 通过 | MACDPanel HELP_ITEMS：`line/line/bar/circle/circle` |
| AC-guide-icon-2 | RSI 浮层：RSI 曲线=实线，超买/超卖区间=方块 | ✅ 通过 | RSIPanel HELP_ITEMS：`line/bar/bar/...` |
| AC-guide-icon-3 | KDJ 浮层：K/D=实线，J=虚线，金叉/死叉=小圆 | ✅ 通过 | KDJPanel HELP_ITEMS：`line/line/dashed/circle/circle` |
| AC-guide-icon-4 | VPA 浮层：防守线=实线，OBV=实线，OBV均线=虚线，四象限=圆点（兜底）| ✅ 通过 | VPADefenderPanel HELP_ITEMS：`line/line/dashed/dot/dot/dot/dot` |
| AC-guide-icon-5 | 图标颜色与右侧图例颜色相同 | ✅ 通过（代码层面） | `iconType` 和 `color`/`dotColor` 均与 ECharts series 颜色来源同步 |
| AC-guide-icon-6 | 未指定 `iconType` 的说明条目兜底为圆点，不报错 | ✅ 通过 | `ChartSidebar.jsx` LegendMark：`type` 缺省时走 `dot` 分支，不抛异常 |

**iconType 配置对照表（代码实际 vs 需求期望）**：

| 面板 | 说明条目 | 需求期望 | 代码实际 | 结论 |
|------|---------|---------|---------|------|
| MACD | DIF 线 | `line` | `line` | ✅ |
| MACD | DEA 线 | `line` | `line` | ✅ |
| MACD | MACD 柱 | `bar` | `bar` | ✅ |
| MACD | 金叉 | `circle` | `circle` | ✅ |
| MACD | 死叉 | `circle` | `circle` | ✅ |
| RSI | RSI 曲线 | `line` | `line` | ✅ |
| RSI | 超买区间 | `bar` | `bar` | ✅ |
| RSI | 超卖区间 | `bar` | `bar` | ✅ |
| KDJ | K 线 | `line` | `line` | ✅ |
| KDJ | D 线 | `line` | `line` | ✅ |
| KDJ | J 线 | `dashed` | `dashed` | ✅ |
| KDJ | 金叉 | `circle` | `circle` | ✅ |
| KDJ | 死叉 | `circle` | `circle` | ✅ |
| VPA | 防守线 | `line` | `line` | ✅ |
| VPA | OBV 线 | `line` | `line` | ✅ |
| VPA | OBV 均线 | `dashed` | `dashed` | ✅ |
| VPA | 四象限（×4）| `dot`（兜底）| `dot` | ✅ |

**LegendMark 组件审查（ChartSidebar.jsx L144-L194）**：

| iconType | 渲染尺寸 | 样式 | 符合需求 |
|----------|---------|------|---------|
| `line` | 18×2px | 实线 | ✅ |
| `dashed` | 18×2px | 虚线（border-style: dashed）| ✅ |
| `circle` | 8×8px | 圆形（borderRadius: 50%）| ✅ |
| `bar` | 10×10px | 方块 | ✅ |
| `dot`（兜底）| 7×7px | 圆点（borderRadius: 50%）| ✅ |

---

## 三、不在本迭代范围的项目（确认未被误改）

| 项目 | 确认结论 |
|------|---------|
| 主图（K线区）[?] 说明浮层 | ✅ 未改动，`MainChart.jsx` 无 showHelp 逻辑 |
| 后端 API 文件（`api/`）| ✅ 未改动 |
| `core/indicator_engine.py` | ✅ 未改动 |
| `core/gap_detector.py` | ✅ 未改动 |
| `web/src/hooks/useChartSync.js` | ✅ 未改动 |
| 综合信号计算（`compositeSignal.js`）| ✅ 未改动 |
| VPA 四象限信号纳入综合信号 | ✅ 未改动（遵守迭代裁定 2026-03-23）|

---

## 四、回归测试评估（代码层面）

| 回归场景 | 代码层面评估 | Runtime 建议 |
|---------|------------|-------------|
| 十字线跨图联动 | `useChartSync.js` 未改动，BUG-align 统一 grid 后对齐应更精确 | ✅ 建议 runtime 人工验证 TC-reg-crosshair-* |
| dataZoom 滑动条联动 | `useChartSync.js` 未改动，不受本次修改影响 | ✅ 低风险 |
| 折叠状态 localStorage 持久化 | `collapsed` state 管理逻辑在 StockAnalysis 层未改动；折叠按钮从 Panel 迁移到 ChartSidebar 不影响 state 本身 | ✅ 建议 runtime 验证 TC-reg-localstorage-* |
| 60 秒自动刷新 | 自动刷新逻辑未改动 | ✅ 低风险 |

---

## 五、风险评估

| 风险 ID | 描述 | 等级 | 处置 |
|--------|------|------|------|
| R-align | BUG-align 固定 `grid.left: 60` 的截断风险（高价股 Y 轴标签溢出）| 低 | `axisLabel.width: 52, overflow: 'truncate'` 已兜底，极端情况截断不换行 |
| R-vpa-color | 两种绿色（`#26a69a` vs `#2ea043`）视觉可区分性 | 低 | 色差明显（teal 青绿 vs 纯绿），且 badge 有文字 label 辅助区分；建议 runtime 人工验收 |
| R-merge | FEAT-guide-top / FEAT-collapse-btn / FEAT-guide-icon 均改动 Panel 标题行 | 低 | 均已合并到同一提交，无遗留合并冲突；代码审查确认功能完整 |

---

## 六、审查结论

**结论：✅ 全部通过，迭代8代码实现完整，符合 requirements_iter8.md v1.2 所有 AC 要求。**

| 功能点 | 优先级 | 审查结论 |
|--------|--------|---------|
| BUG-emoji | P0 | ✅ 通过 |
| BUG-align | P0 | ✅ 通过 |
| BUG-vpa-color | P1 | ✅ 通过 |
| FEAT-check-gaps-log | P1 | ✅ 通过 |
| FEAT-guide-top | P1 | ✅ 通过 |
| FEAT-collapse-btn | P1 | ✅ 通过 |
| FEAT-guide-icon | P1 | ✅ 通过 |

**待 Runtime 人工验收项**（代码审查无法覆盖的视觉类 AC）：
1. TC-align-02：十字线纵向对齐肉眼验证
2. TC-vpa-color-06：两种绿色视觉可区分性确认
3. TC-reg-crosshair-*：跨图十字线联动 runtime 验证
4. TC-reg-localstorage-*：localStorage 持久化 runtime 验证

建议在目标机完成以上 runtime 验收后打 tag `v0.8.0`。

---

*文档结束*
*审查人：QA*
*日期：2026-03-24*
