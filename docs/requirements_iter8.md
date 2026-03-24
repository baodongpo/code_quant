# 迭代8需求文档 — UI 体验优化（Y轴对齐 + 说明浮层重构 + 折叠按钮重构 + emoji修复 + check-gaps日志增强 + 说明图标统一 + VPA配色修正）

**文档版本**：v1.3
**日期**：2026-03-24
**状态**：待研发启动
**作者**：PM（产品经理）
**变更记录**：
- v1.0（2026-03-24）— 初版，含 BUG-emoji / BUG-align / FEAT-guide-top / FEAT-collapse-btn
- v1.1（2026-03-24）— BUG-emoji AC 补充写法规范要求；新增 FEAT-check-gaps-log；主图 [?] 确认不在本迭代；README 路线图已同步更新
- v1.2（2026-03-24）— 新增 FEAT-guide-icon（说明浮层图标与图例一致）；新增 BUG-vpa-color（破位警示颜色改为绿色）
- v1.3（2026-03-24）— 新增第七章：FEAT-resistance 空仓阻力线延期决策（延期至 iter8.1-patch）；CLAUDE.md 路线图已同步更新

---

## 一、迭代背景与目标

### 背景

v0.7.1-patch 完成后，Web 前端的 K 线分析页（StockAnalysis）在以下六个方面存在体验缺陷：

1. **Y 轴不对齐**：各副图横向宽度不一致，导致日期坐标与主图错位，十字线联动时纵轴无法对齐。
2. **说明浮层位置混乱**：`[?]` 按钮分散在右侧 ChartSidebar 和 VPA 面板顶部两个地方，MACD/RSI/KDJ 没有顶部入口，用户体验不一致。
3. **折叠按钮语义错误**：折叠按钮放在图表内部，但点击后会收起整行（包含右侧说明栏），用户认知成本高。
4. **VPA 折叠展开按钮乱码**：折叠后展开按钮显示为字面量字符串 `\u2228`，非期望的 `∨`。
5. **说明浮层图标形状不统一**：说明浮层每条说明前固定用圆点，右侧图例用线/虚线/圆/方块等形状，两者形状不一致，信息传达割裂。
6. **VPA 破位警示配色错误**：破位警示（价格跌破防守线）属于卖出/下跌方向，应为绿色，但当前为红色，违反 A股红涨绿跌规范。

### 目标

在不改变任何后端逻辑、不触碰综合信号计算、不影响 useChartSync 跨图联动的前提下，对前端 React 组件进行 UI 层重构，使页面：
- 各图表内容区横向严格对齐
- 说明浮层统一从各面板顶部 `[?]` 按钮展开，图标与右侧图例形状一致
- 折叠/展开控制统一归位到右侧 ChartSidebar
- VPA 相关乱码彻底消除，破位警示配色符合 A股规范

---

## 二、功能点详细说明

---

### P0 — BUG-emoji：VPA 折叠展开按钮乱码及写法规范统一

#### 2.1 问题根因

`VPADefenderPanel.jsx` 折叠状态（第 90 行）的展开按钮写法：

```jsx
>\u2228</button>
```

此处 `\u2228` 是 JSX 文本内容（非 JavaScript 字符串表达式），React 直接渲染为字面量字符串 `\u2228`，而非 Unicode 字符 `∨`，**造成线上乱码 BUG**。

展开状态（第 329 行）折叠按钮写法：

```jsx
>{'\u2227'}</button>
```

此处用了 JS 表达式 `{'\u2227'}`，实际渲染为 `∧`，**功能正常但写法与其他组件不统一**，存在维护隐患。

对比三个已正确实现的组件：
- `MACDPanel.jsx`：展开按钮 `>∨</button>`，折叠按钮 `>∧</button>`（直接 Unicode 字符）✅
- `RSIPanel.jsx`：同上 ✅
- `KDJPanel.jsx`：同上 ✅

#### 2.2 期望行为

- 折叠后的展开按钮：显示 `∨`
- 展开后的折叠按钮：显示 `∧`
- **写法规范**：JSX 文本中直接书写 Unicode 字符（`∨`/`∧`），禁止使用 escape 序列（`\u2228`）和 JS 表达式（`{'\u2227'}`），与 MACDPanel / RSIPanel / KDJPanel 写法完全统一

#### 2.3 验收标准（AC）

- [ ] AC-emoji-1：VPA 副图折叠状态下，展开按钮文字为 `∨`，不出现 `\u2228` 字面量。
- [ ] AC-emoji-2：VPA 副图展开状态下，折叠按钮文字为 `∧`，不出现 `\u2227` 字面量，**写法为直接 Unicode 字符（与 MACD/RSI/KDJ 相同），不使用 JS 表达式 `{'\u2227'}`**。
- [ ] AC-emoji-3：按钮点击功能正常，能正确展开/折叠。
- [ ] AC-emoji-4：代码评审时，两处修改均使用直接 Unicode 字符书写，无 escape 序列和 JS 表达式包裹。

#### 2.4 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/VPADefenderPanel.jsx` | 第 90 行 `\u2228` → `∨`；第 329 行 `{'\u2227'}` → `∧` |

---

### P0 — BUG-align：各图表 Y 轴与内容区横向宽度不一致

#### 2.5 问题根因

各图表 ECharts 配置中 `grid.left / grid.right` 取值不统一：

| 组件 | grid.left | grid.right | containLabel |
|------|-----------|------------|--------------|
| MainChart（K线主图） | 16 | 16 | true |
| MainChart（成交量子图）| 16 | 16 | true |
| MACDPanel | 16 | 16 | true |
| RSIPanel | 16 | 16 | true |
| KDJPanel | 16 | 16 | true |
| VPADefenderPanel | 60 | 60 | false（双Y轴，固定） |

`containLabel: true` 的含义是：`grid.left/right` 为 Y 轴标签外边界距容器边缘的距离，ECharts 会在此基础上自动向内收缩留出标签空间。由于各图 Y 轴标签宽度随数据变化（如 MACD 的 `0.0231` vs KDJ 的 `80`），最终绘图内容区的真实左边界像素值各不相同，导致：

- 各图 X 轴日期刻度错位
- 十字线联动时纵向辅助线位置偏移

#### 2.6 期望行为

所有图表（MainChart 双子图 + MACD + RSI + KDJ + VPA）的绘图内容区左右边界像素值一致，即 X 轴日期坐标在垂直方向上完全对齐。

#### 2.7 实现方案

**方案：废弃 `containLabel: true`，改用统一固定 `grid.left` / `grid.right` 值，同时为 Y 轴标签设置 `width` 固定宽度。**

具体参数（与 VPA 现有双 Y 轴固定值拉齐）：

```js
// 所有图表统一使用：
grid: { left: 60, right: 60, ... }
// 同时去掉 containLabel: true（或设为 false）
// Y 轴 axisLabel 设置 width: 52（确保标签在 60px 内不溢出）
yAxis: {
  axisLabel: {
    width: 52,
    overflow: 'truncate',  // 极端情况截断，不换行
    ...
  }
}
```

**说明**：
- 左侧 60px 已足够容纳 MACD 四位小数标签（约 7 字符 × 7px ≈ 49px）
- VPADefenderPanel 双 Y 轴 `left: 60, right: 60` 已验证可用，各图与其对齐最为稳妥
- MainChart 有两个 grid，均需同步修改

#### 2.8 验收标准（AC）

- [ ] AC-align-1：切换至任意股票/周期，主图 K 线区、成交量区、MACD、RSI、KDJ、VPA 的绘图内容区左边界在浏览器开发者工具 Computed 中偏差 ≤ 2px。
- [ ] AC-align-2：hover 时各图十字线纵轴辅助线（竖线）在垂直方向上肉眼可见地对齐（无明显错位）。
- [ ] AC-align-3：日期标签无截断、无换行，显示正常。
- [ ] AC-align-4：VPADefenderPanel 右侧 OBV 轴数值标签（亿/万）无溢出。
- [ ] AC-align-5：折叠任意副图后重新展开，对齐效果不变。

#### 2.9 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/MainChart.jsx` | K 线 grid 和成交量 grid 均改为 `left:60, right:60`，去掉 `containLabel:true`，Y 轴 axisLabel 加 `width:52` |
| `web/src/components/MACDPanel.jsx` | grid 改 `left:60, right:60`，去掉 `containLabel`，Y 轴 axisLabel 加 `width:52` |
| `web/src/components/RSIPanel.jsx` | 同上 |
| `web/src/components/KDJPanel.jsx` | 同上 |
| `web/src/components/VPADefenderPanel.jsx` | 已为 `left:60, right:60`，仅需确认右轴 axisLabel `width` 与统一值一致 |

---

### P1 — FEAT-guide-top：说明浮层 `[?]` 统一移至各面板顶部

#### 2.10 现状

| 组件 | [?] 位置 | 说明内容 |
|------|---------|--------|
| MainChart | ChartSidebar 标题行右侧 | guideItems（布林带/均线说明） |
| MACDPanel | ChartSidebar 标题行右侧 | guideItems（金叉死叉说明） |
| RSIPanel | ChartSidebar 标题行右侧 | guideItems（超买超卖说明） |
| KDJPanel | ChartSidebar 标题行右侧 | guideItems（金叉死叉说明） |
| VPADefenderPanel | **面板顶部标题行（VPADefenderPanelInner）** | HELP_ITEMS（内嵌） |
| VPA ChartSidebar | ChartSidebar 标题行右侧 | vpaSidebarGuide（重复） |

问题：VPA 存在两套说明入口；MACD/RSI/KDJ/主图说明藏在右侧 Sidebar，用户不易发现。

#### 2.11 期望行为

**目标布局**：

```
┌─────────────────────────────────────────────┬────────────────┐
│  [面板标题] [信号标签]         [?] [折叠∧]  │  ChartSidebar  │
│  ─────────────────────────────────────────  │  ─────────     │
│  [说明浮层（可选展开）]                      │  当前值        │
│  ─────────────────────────────────────────  │  信号标签      │
│  ECharts 图表区域                           │  ──────        │
│                                             │  图例（色块）  │
│                                             │  ← 无[?]按钮 → │
└─────────────────────────────────────────────┴────────────────┘
```

**规则**：
1. 所有副图面板（MACD / RSI / KDJ / VPA）的 `[?]` 按钮统一放在各自面板顶部标题行的右侧（紧靠折叠按钮左侧）。
2. 右侧 ChartSidebar **移除 `[?]` 按钮和 guideItems 渲染逻辑**，仅保留：当前值（valueItems）、信号标签（signal）、图例（legendItems）。
3. 各面板内部的说明浮层展开后，颜色图标（色点/线条）与右侧 ChartSidebar 图例中对应项颜色保持完全一致。
4. **主图（K线区）`[?]` 入口不在本迭代范围内**（已由老板确认）。主图 ChartSidebar 的 [?] 及 guideItems 延后至下一迭代处理。

> **已确认（2026-03-24）**：主图（K 线区）[?] 说明按钮不纳入本迭代，下迭代再规划。

#### 2.12 各面板说明浮层内容来源

说明浮层内容复用 StockAnalysis.jsx 中已定义的 `guideItems` / `vpaSidebarGuide` 数组，下沉到各面板组件内部（以 props 方式传入或直接内置）：

| 面板 | 内容来源 | 迭代7 现状 |
|------|---------|-----------|
| MACD | `macdSidebarGuide`（StockAnalysis.jsx L217） | 无顶部 [?]，需新增 |
| RSI | `rsiSidebarGuide`（StockAnalysis.jsx L227） | 无顶部 [?]，需新增 |
| KDJ | `kdjSidebarGuide`（StockAnalysis.jsx L240） | 无顶部 [?]，需新增 |
| VPA | `HELP_ITEMS`（VPADefenderPanel.jsx L30）/ `vpaSidebarGuide`（StockAnalysis.jsx L253） | 已有顶部 [?]，ChartSidebar 也有，需去掉 ChartSidebar 的 |
| MainChart | `mainSidebarGuide`（StockAnalysis.jsx L199） | **本迭代不处理**，延后 |

> **说明内容一致性**：VPA 面板内部 `HELP_ITEMS` 与 `vpaSidebarGuide` 内容基本一致但措辞略有差异，统一以面板内部版本为准，ChartSidebar 版本废弃。

#### 2.13 验收标准（AC）

- [ ] AC-guide-1：MACD 面板标题行有 `[?]` 按钮，点击展开说明浮层，内容包含"金叉""死叉""MACD 柱"三条说明。
- [ ] AC-guide-2：RSI 面板标题行有 `[?]` 按钮，点击展开说明浮层，内容包含"超买""超卖""中性区间"三条说明。
- [ ] AC-guide-3：KDJ 面板标题行有 `[?]` 按钮，点击展开说明浮层，内容包含"金叉""死叉""J 线"三条说明。
- [ ] AC-guide-4：VPA 面板标题行 `[?]` 按钮保留，功能不变；右侧 ChartSidebar 不再出现 `[?]` 按钮和说明文案区块。
- [ ] AC-guide-5：所有面板默认加载时说明浮层均为隐藏状态（collapsed = false of showHelp）。
- [ ] AC-guide-6：说明浮层颜色圆点与右侧 ChartSidebar 图例色块颜色一一对应，无出入。
- [ ] AC-guide-7：ChartSidebar 组件中 `guideItems` prop 仍保留接口定义（避免 props type 报错），但渲染逻辑注释或删除；或将 `guideItems` 标记为 deprecated。
- [ ] AC-guide-8：说明文案严禁包含买卖操作指令（继承 CLAUDE.md 迭代裁定规范）。

#### 2.14 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/MACDPanel.jsx` | MACDPanelInner 标题行新增 `[?]` 按钮 + showHelp 状态 + 说明浮层 |
| `web/src/components/RSIPanel.jsx` | RSIPanelInner 同上 |
| `web/src/components/KDJPanel.jsx` | KDJPanelInner 同上 |
| `web/src/components/VPADefenderPanel.jsx` | [?] 位置不变；确认说明内容与 vpaSidebarGuide 一致 |
| `web/src/components/ChartSidebar.jsx` | 移除 guideItems 展开逻辑和 `[?]` 按钮；保留 `guideItems` prop 接口（不 breaking change）|
| `web/src/pages/StockAnalysis.jsx` | 调整各 ChartSidebar 调用，去掉 guideItems prop 传入（可选：继续传不传均可，取决于 ChartSidebar 是否保留接口渲染） |

> ⚠️ **注意**：`MainChart.jsx` 不在本功能点改动范围内（主图 [?] 已确认延后）。

---

### P1 — FEAT-collapse-btn：折叠按钮统一移至 ChartSidebar 右上角

#### 2.15 现状

折叠按钮当前位置：

| 状态 | 按钮位置 | 按钮字符 |
|------|---------|--------|
| 展开时（MACDPanelInner 等） | 图表区标题行右端 `marginLeft: auto` | `∧` |
| 折叠时（各 Panel 折叠态 div） | 折叠条右端 `marginLeft: auto` | `∨` |

问题：
- 折叠按钮在图表区（左侧 `flex: 1` 区域），但折叠操作会收起整行（包含右侧 ChartSidebar），按钮位置与影响范围不匹配。
- 用户视觉上不知道折叠按钮会同时收起右侧说明栏。

#### 2.16 期望行为

**展开状态**：

```
┌─────────────────────────────────────────────┬────────────────┐
│  [面板标题] [信号标签]            [?]        │  ChartSidebar  │
│                                             │                │
│  ECharts 图表区域                           │  ...内容...    │
│                                             │             [∧]│  ← 折叠按钮在 Sidebar 右上角
└─────────────────────────────────────────────┴────────────────┘
```

**折叠状态**（整行收为 32px 条）：

```
┌─────────────────────────────────────────────────────────────┐
│  [面板标题] [信号标签]                                  [∨] │
└─────────────────────────────────────────────────────────────┘
```

**规则**：
1. 展开态：折叠按钮（`∧`）放在 ChartSidebar 内部右上角，通过 `position: absolute; top: 8px; right: 8px` 或 flex 布局实现。
2. 折叠态：展开按钮（`∨`）保持在折叠条右端（现有位置不变），与 MACD/RSI/KDJ 当前折叠态一致。
3. ChartSidebar 新增 `onToggle` prop（function，可选），当传入时渲染折叠按钮。
4. 各副图 Panel 组件（MACDPanelInner / RSIPanelInner / KDJPanelInner / VPADefenderPanelInner）标题行**移除**折叠按钮，`onToggle` prop 仍接收但仅在折叠态使用（展开按钮在折叠条上，不受影响）。
5. 折叠行为逻辑不变：整行（图表 + ChartSidebar）一起收缩，由 StockAnalysis.jsx `collapsed` state 控制。

#### 2.17 验收标准（AC）

- [ ] AC-collapse-1：MACD/RSI/KDJ/VPA 四个副图，展开状态下折叠按钮（`∧`）显示在右侧 ChartSidebar 区域内，不在图表区标题行。
- [ ] AC-collapse-2：点击 ChartSidebar 内折叠按钮，整行（图表 + Sidebar）正确收缩为 32px 折叠条。
- [ ] AC-collapse-3：折叠条右端展开按钮（`∨`）位置和功能不变，点击后正确展开整行。
- [ ] AC-collapse-4：图表区标题行（展开态）不再出现折叠按钮，标题行仅包含：指标名称、信号标签、`[?]` 按钮。
- [ ] AC-collapse-5：折叠状态持久化到 localStorage 的逻辑不受影响。
- [ ] AC-collapse-6：顶部"显示副图"按钮组（MACD/RSI/KDJ/VPA 快捷切换按钮）功能不受影响。

#### 2.18 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/ChartSidebar.jsx` | 新增 `onToggle` prop；在 Sidebar 右上角渲染折叠按钮（`∧`，当 `onToggle` 存在时显示） |
| `web/src/components/MACDPanel.jsx` | MACDPanelInner 标题行移除折叠按钮；`onToggle` prop 保留（折叠态仍需用） |
| `web/src/components/RSIPanel.jsx` | 同上 |
| `web/src/components/KDJPanel.jsx` | 同上 |
| `web/src/components/VPADefenderPanel.jsx` | VPADefenderPanelInner 标题行移除折叠按钮；`[?]` 按钮保留在原位 |
| `web/src/pages/StockAnalysis.jsx` | 各副图展开态的 `ChartSidebar` 调用新增 `onToggle={() => togglePanel('XXX')}` prop |

---

### P1 — FEAT-check-gaps-log：check-gaps 日志日期展示增强

#### 2.19 背景

`main.py` 的 `cmd_check_gaps` 函数在日志和终端输出中显示空洞日期时，直接使用数据库中存储的 `trade_date` 字段值。对于周K和月K，`trade_date` 并非自然周/月的起始日，用户难以直接判断对应哪一周或哪一个月：

- **周K**：`trade_date` 为该周最后一个交易日（通常为周五，如 `2020-02-07`），对用户来说更直观的是「哪一周」而非具体周末日期
- **月K**：`trade_date` 为该月第一个交易日（实测规律，如 `2020-02-03`），但用户习惯以 `2020-02` 或 `2020-02-01` 来表达哪一个月

#### 2.20 期望行为

日志和终端输出中，空洞日期展示方式按周期做转换：

| 周期 | 当前显示 | 期望显示 | 转换规则 |
|------|---------|---------|---------|
| 1D | `2020-02-03` | `2020-02-03`（不变）| 原样输出 |
| 1W | `2020-02-07`（周五）| `2020-02-03`（当周周一）| `date - timedelta(days=date.weekday())` |
| 1M | `2020-02-03`（月初第一交易日）| `2020-02-01` | 截取年月后补 `-01` |

**日志输出示例（期望）**：

```
[1D] Found 3 gap(s): [2020-02-03~2020-02-05]
[1W] Found 2 gap(s): [2020-02-03~2020-02-03, 2020-03-09~2020-03-09]
[1M] Found 1 gap(s): [2020-02-01~2020-02-01]
```

> 注：日期转换只影响日志展示，**不影响**实际写入 `data_gaps` 表的 `trade_date` 值（数据库存储保持原样不变）。

#### 2.21 实现方案

在 `main.py` 的 `cmd_check_gaps` 函数内新增辅助函数 `_format_gap_date(date_str: str, period: str) -> str`：

```python
from datetime import datetime, timedelta

def _format_gap_date(date_str: str, period: str) -> str:
    if period == '1D':
        return date_str
    elif period == '1W':
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        monday = d - timedelta(days=d.weekday())
        return monday.strftime('%Y-%m-%d')
    elif period == '1M':
        return date_str[:7] + '-01'
    return date_str
```

调用位置：在现有日志格式化语句（约 L607-L617 处）中，对 `gaps` 列表的 `s`（start）和 `e`（end）分别调用 `_format_gap_date(s, period)` 和 `_format_gap_date(e, period)` 后再拼接字符串。

**改动范围**：仅 `main.py`，`cmd_check_gaps` 函数内部，不涉及 `GapDetector`、`GapRepository` 及任何其他模块。

#### 2.22 验收标准（AC）

- [ ] AC-gaps-log-1：执行 `check-gaps --period 1D`，日志中空洞日期格式为 `YYYY-MM-DD`，与数据库 `trade_date` 一致。
- [ ] AC-gaps-log-2：执行 `check-gaps --period 1W`，日志中空洞日期为该周**周一**日期（如 trade_date=`2020-02-07` 则日志显示 `2020-02-03`）。
- [ ] AC-gaps-log-3：执行 `check-gaps --period 1M`，日志中空洞日期为 `YYYY-MM-01` 格式（如 trade_date=`2020-02-03` 则日志显示 `2020-02-01`）。
- [ ] AC-gaps-log-4：`data_gaps` 表中写入的 `start_date` / `end_date` 值**不受影响**，仍为原始 `trade_date` 格式。
- [ ] AC-gaps-log-5：终端打印的汇总输出（Summary 部分）中，空洞计数和"Persisted to DB"数量与原逻辑一致，不因格式化引入 bug。
- [ ] AC-gaps-log-6：不传 `--period` 时默认检测全部三个周期，各周期分别按对应规则输出日期，无混淆。

#### 2.23 影响文件

| 文件 | 修改内容 |
|------|---------|
| `main.py` | `cmd_check_gaps` 函数内新增 `_format_gap_date` 辅助函数，修改日志格式化行 |

---

### P1 — FEAT-guide-icon：说明浮层图标形状与右侧图例保持一致

#### 2.24 背景

当前各面板说明浮层（`[?]` 展开后的每条说明条目）前面固定渲染一个 `7×7px` 的圆点（`borderRadius: '50%'`）。而右侧 ChartSidebar 图例使用 `LegendMark` 组件，支持四种形状：

| 图例 `type` | 渲染形状 | 含义示例 |
|------------|---------|---------|
| `line` | 横实线（18×2px）| DIF 线、防守线 |
| `dashed` | 横虚线 | DEA 线、OBV 均线、J 线 |
| `circle` | 小圆（8×8px）| 金叉/死叉标记点 |
| `bar` | 小方块（10×10px）| MACD 柱、超买超卖区背景 |
| `dot`（兜底）| 圆点（保持现有）| 无对应图例的通用说明 |

用户阅读说明浮层时，圆点与右侧图例形状不一致，造成认知割裂，难以将说明与图表中的线条/标记对应起来。

#### 2.25 期望行为

说明浮层每条说明条目前的图标，**形状与右侧 ChartSidebar 图例中对应项的 `type` 一致**，颜色与 `dotColor` / `color` 保持不变。

示例对应关系（MACD 面板）：

| 说明条目 | 对应图例 type | 期望图标形状 |
|---------|-------------|-----------|
| DIF 线说明 | `line` | 横实线 |
| DEA 线说明 | `line` | 横实线 |
| MACD 柱说明 | `bar` | 小方块 |
| 金叉说明 | `circle` | 小圆 |
| 死叉说明 | `circle` | 小圆 |

#### 2.26 实现方案

**数据结构扩展**：在每条说明数据对象中新增可选字段 `iconType`：

```js
// 现有结构（guideItems / HELP_ITEMS）
{ dotColor: '#xxx', text: '...' }

// 扩展后结构
{ dotColor: '#xxx', iconType: 'line'|'dashed'|'circle'|'bar'|'dot', text: '...' }
// iconType 缺省时兜底为 'dot'（保持现有圆点渲染）
```

**渲染逻辑**：说明浮层的图标渲染从固定圆点改为根据 `iconType` 分支：
- `'line'`：渲染与 LegendMark `type='line'` 相同的横实线（`18×2px`，颜色取 `dotColor`）
- `'dashed'`：渲染与 LegendMark `type='dashed'` 相同的横虚线
- `'circle'`：渲染与 LegendMark `type='circle'` 相同的小圆（`8×8px`）
- `'bar'`：渲染与 LegendMark `type='bar'` 相同的小方块（`10×10px`）
- `'dot'` / 缺省：保持原有 `7×7px` 圆点

**涉及说明数据的修改位置**：

| 位置 | 涉及说明数组 |
|------|------------|
| `VPADefenderPanel.jsx` `HELP_ITEMS` | 防守线 → `line`；OBV 线 → `line`；OBV 均线 → `dashed`；四象限说明 → `dot`（无对应图例） |
| `StockAnalysis.jsx` `macdSidebarGuide` | 金叉/死叉 → `circle`；MACD 柱 → `bar` |
| `StockAnalysis.jsx` `rsiSidebarGuide` | RSI 线 → `line`；超买区/超卖区背景说明 → `bar` |
| `StockAnalysis.jsx` `kdjSidebarGuide` | 金叉/死叉 → `circle`；J 线说明 → `dashed` |
| `StockAnalysis.jsx` `mainSidebarGuide` | 主图说明（本迭代不处理主图 [?]，但数据字段可先加上，不影响渲染） |

**复用优先**：如果 `ChartSidebar.jsx` 中的 `LegendMark` 组件已导出或可提取，建议说明浮层直接引用 `LegendMark`（而非重复实现），保证图形完全一致。

#### 2.27 依赖关系

**本功能点依赖 FEAT-guide-top 完成后才能完整体现**：说明浮层迁移至各面板顶部后，图标与右侧图例的对应关系在视觉上才明显。建议开发顺序排在 FEAT-guide-top 之后。

若 FEAT-guide-top 尚未合并，FEAT-guide-icon 可提前在 `ChartSidebar.jsx` 的现有 `guideItems` 渲染逻辑中实现，验收时以各面板顶部说明浮层为准。

#### 2.28 验收标准（AC）

- [ ] AC-guide-icon-1：MACD 说明浮层中，DIF/DEA 说明前为横实线图标，金叉/死叉说明前为小圆图标，MACD 柱说明前为小方块图标。
- [ ] AC-guide-icon-2：RSI 说明浮层中，RSI 曲线说明前为横实线图标，超买/超卖区间说明前为小方块图标。
- [ ] AC-guide-icon-3：KDJ 说明浮层中，K/D 线说明前为横实线图标，J 线说明前为横虚线图标，金叉/死叉说明前为小圆图标。
- [ ] AC-guide-icon-4：VPA 说明浮层中，防守线说明前为横实线图标，OBV 说明前为横实线图标，OBV 均线说明前为横虚线图标，四象限说明前为圆点（无对应图例，兜底）。
- [ ] AC-guide-icon-5：图标颜色与右侧图例对应条目颜色相同，无出入。
- [ ] AC-guide-icon-6：未指定 `iconType`（兜底）的说明条目仍以圆点渲染，不报错。

#### 2.29 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/VPADefenderPanel.jsx` | `HELP_ITEMS` 各条目补充 `iconType` 字段；说明浮层渲染逻辑改为按 `iconType` 分支 |
| `web/src/components/MACDPanel.jsx` | （FEAT-guide-top 完成后）说明浮层渲染逻辑改为按 `iconType` 分支 |
| `web/src/components/RSIPanel.jsx` | 同上 |
| `web/src/components/KDJPanel.jsx` | 同上 |
| `web/src/components/ChartSidebar.jsx` | `guideItems` 渲染逻辑改为按 `iconType` 分支（或兜底仍用圆点） |
| `web/src/pages/StockAnalysis.jsx` | `macdSidebarGuide` / `rsiSidebarGuide` / `kdjSidebarGuide` 各条目补充 `iconType` 字段 |

---

### P1 — BUG-vpa-color：VPA 破位警示颜色改为绿色（A股红涨绿跌规范）

#### 2.30 问题根因

`VPADefenderPanel.jsx` 中 `SIGNAL_CONFIG` 的四象限配色：

```js
const SIGNAL_CONFIG = {
  1: { emoji: '🟢', label: '共振主升浪', color: '#26a69a' },  // teal 绿，多头上涨
  2: { emoji: '🟡', label: '顶背离预警', color: '#ffd54f' },  // 黄色，观察
  3: { emoji: '🔴', label: '破位警示',   color: '#ef5350' },  // ← 当前红色，应为绿色
  4: { emoji: '⚪', label: '底部观察',   color: '#b0bec5' },  // 灰色，观察
}
```

破位警示（信号3）含义：**价格跌破防守线**，属于下跌/卖出方向。依据项目统一的 **A股红涨绿跌规范**（见 CLAUDE.md 迭代裁定 2026-03-18）：
- 买入/上涨方向 → 红色系
- 卖出/下跌方向 → 绿色系

当前破位警示为红色 `#ef5350`，与"下跌/卖出=绿色"规范相悖，需改为绿色。

同时 `HELP_ITEMS` 第6条及 `StockAnalysis.jsx` `vpaSidebarGuide` 中对应颜色圆点也需同步更新。

#### 2.31 期望配色

| 信号 | 含义 | 方向 | 期望颜色 | 色值 |
|------|------|------|---------|------|
| 共振主升浪（1）| 量价配合良好，上涨趋势 | 多头上涨 | teal 绿 | `#26a69a`（不变）|
| 顶背离预警（2）| 量价分歧，待观察 | 中性 | 黄色 | `#ffd54f`（不变）|
| 破位警示（3）| 价格跌破防守线 | 空头下跌 | **卖出绿** | `#2ea043` |
| 底部观察（4）| 资金开始流入，待确认 | 中性 | 灰色 | `#b0bec5`（不变）|

> **颜色区分说明**：共振主升浪的 teal `#26a69a` 为偏蓝的青绿（多头色），破位警示的 `#2ea043` 为纯绿（与项目卖出信号色 `C.sell` 接近），视觉上有明显差异，不会造成混淆。

#### 2.32 修改内容

**`VPADefenderPanel.jsx`**：

1. `SIGNAL_CONFIG[3]`：
   - `emoji`：`'🔴'` → `'🟢'`（注意：与信号1共振主升浪的 `'🟢'` 使用相同 emoji，依靠 label 和 color 区分）
   - `color`：`'#ef5350'` → `'#2ea043'`

2. `HELP_ITEMS` 第6条（破位警示说明）：
   - `color`：`'#ef5350'` → `'#2ea043'`
   - `text`：`'<b>红色（破位警示）</b>...'` → `'<b>绿色（破位警示）</b>...'`

**`StockAnalysis.jsx`**：

3. `vpaSidebarGuide` 第4条（破位警示，约 L259）：
   - `dotColor`：`'#ef5350'` → `'#2ea043'`
   - `text`：`'<b>红色（破位警示）</b>...'` → `'<b>绿色（破位警示）</b>...'`

> 信号色带（`markArea`）颜色由 `SIGNAL_CONFIG[3].color` 动态生成（`${cfg.color}30`），修改 `SIGNAL_CONFIG` 后自动跟随，**无需单独修改**。

#### 2.33 验收标准（AC）

- [ ] AC-vpa-color-1：VPA 副图信号色带中，破位警示区间颜色为绿色系（`#2ea04330` 半透明），不再为红色。
- [ ] AC-vpa-color-2：折叠条的信号 badge（`sigCfg.color`）破位警示为绿色 `#2ea043`。
- [ ] AC-vpa-color-3：展开状态面板标题行的信号 badge 破位警示为绿色。
- [ ] AC-vpa-color-4：说明浮层 `[?]` 中破位警示说明条目的颜色圆点为绿色，文案更新为"绿色（破位警示）"。
- [ ] AC-vpa-color-5：右侧 ChartSidebar（或迁移后的面板说明浮层）vpaSidebarGuide 中破位警示颜色圆点同步为绿色。
- [ ] AC-vpa-color-6：共振主升浪（teal `#26a69a`）与破位警示（`#2ea043`）在 UI 中视觉可区分，不造成混淆。

#### 2.34 影响文件

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/VPADefenderPanel.jsx` | `SIGNAL_CONFIG[3]` emoji/color 修改；`HELP_ITEMS[5]` color/text 修改 |
| `web/src/pages/StockAnalysis.jsx` | `vpaSidebarGuide` 第4条 dotColor/text 修改 |

---

## 三、实现优先级

| 优先级 | ID | 功能点 | 原因 |
|--------|-----|--------|-----|
| P0 | BUG-emoji | VPA 乱码修复 + 写法规范统一 | 现网 BUG，影响基本可用性，改动最小（2 行代码） |
| P0 | BUG-align | Y 轴对齐 | 影响所有图表阅读体验和十字线联动准确性，与指标联动核心功能强相关 |
| P1 | BUG-vpa-color | VPA 破位警示颜色修正 | 配色规范 BUG，改动极小（3处颜色值+文案），独立不与其他功能交叉 |
| P1 | FEAT-check-gaps-log | check-gaps 日志日期展示增强 | 仅改 main.py 单函数，独立改动，不与前端功能点交叉 |
| P1 | FEAT-guide-top | 说明浮层移顶部 | 交互规范统一，改动中等，不阻塞其他功能 |
| P1 | FEAT-collapse-btn | 折叠按钮重构 | 交互语义修正，改动中等，依赖 FEAT-guide-top 完成后（避免同时改 Panel 标题行产生冲突） |
| P1 | FEAT-guide-icon | 说明浮层图标与图例形状统一 | 视觉一致性，依赖 FEAT-guide-top 完成后体现效果 |

> **建议开发顺序**：BUG-emoji → BUG-align → BUG-vpa-color → FEAT-check-gaps-log → FEAT-guide-top → FEAT-collapse-btn → FEAT-guide-icon
>
> 注：BUG-vpa-color 和 FEAT-check-gaps-log 改动文件不重叠，可与 BUG-align 并行（若团队人力允许）。FEAT-guide-icon 必须在 FEAT-guide-top 合并后再开发。

---

## 四、影响文件汇总

| 文件路径 | 涉及功能点 |
|---------|-----------|
| `web/src/components/VPADefenderPanel.jsx` | BUG-emoji、BUG-align、BUG-vpa-color、FEAT-guide-top、FEAT-collapse-btn、FEAT-guide-icon |
| `web/src/components/MACDPanel.jsx` | BUG-align、FEAT-guide-top、FEAT-collapse-btn、FEAT-guide-icon |
| `web/src/components/RSIPanel.jsx` | BUG-align、FEAT-guide-top、FEAT-collapse-btn、FEAT-guide-icon |
| `web/src/components/KDJPanel.jsx` | BUG-align、FEAT-guide-top、FEAT-collapse-btn、FEAT-guide-icon |
| `web/src/components/MainChart.jsx` | BUG-align（仅 grid 对齐，**不含 FEAT-guide-top**） |
| `web/src/components/ChartSidebar.jsx` | FEAT-guide-top、FEAT-collapse-btn、FEAT-guide-icon |
| `web/src/pages/StockAnalysis.jsx` | BUG-vpa-color（vpaSidebarGuide 文案/色值）、FEAT-guide-top（guideItems 传参调整）、FEAT-collapse-btn（onToggle 传参新增）、FEAT-guide-icon（各 guideItems 补充 iconType）|
| `main.py` | FEAT-check-gaps-log（`cmd_check_gaps` 函数内新增日期转换辅助函数） |

**不涉及改动**：
- `api/` 所有后端文件（纯前端 UI 重构及 CLI 日志增强）
- `core/indicator_engine.py`（指标计算逻辑不变）
- `core/gap_detector.py`（空洞检测逻辑不变）
- `web/src/hooks/useChartSync.js`（跨图联动逻辑不变）
- `web/src/utils/colors.js`（配色不变）
- `web/src/utils/compositeSignal.js`（综合信号不变）

---

## 五、风险说明

### R1 — BUG-align 固定 grid.left 可能导致标签截断

**风险**：某些股票（如 A 股高价股，收盘价 > 10000 元）的 Y 轴标签字符数较多，60px 不一定够用。

**缓解**：
- 设置 `axisLabel.width: 52, overflow: 'truncate'` 截断极端情况
- 或将 `grid.left` 适当放大到 70px（各图统一，对齐要求满足即可）
- Dev 可根据实际渲染效果在 55–70px 之间调整，**关键是所有图表用同一个值**

### R2 — FEAT-guide-top 说明内容下沉后与 ChartSidebar guideItems 出现双份

**风险**：如果只移除 ChartSidebar 的 [?] 渲染而不同步清理 `guideItems` prop 传入，代码冗余但功能正常。

**缓解**：StockAnalysis.jsx 中的 `guideItems` 传入调用可以暂不清除（作为 dead props 保留），待验收确认后的下个迭代一并清理。**不影响验收标准**。

### R3 — FEAT-collapse-btn 改变折叠按钮位置后 ChartSidebar 布局变化

**风险**：ChartSidebar 当前 `justifyContent: center`（纵向居中），加入折叠按钮后需改为从顶部排列，可能影响现有 valueItems / legendItems 垂直分布视觉效果。

**缓解**：
- 折叠按钮使用 `position: absolute; top: 8px; right: 8px` 定位，不影响 Sidebar 内容区 flex 布局
- ChartSidebar 容器 `position: relative` 以支持 absolute 子元素

### R4 — 各功能点并行开发产生合并冲突

**风险**：BUG-align 和 FEAT-guide-top 都需要修改 MACDPanelInner / RSIPanelInner / KDJPanelInner，若并行开发易冲突。

**缓解**：严格按优先级顺序串行开发（BUG-emoji → BUG-align → BUG-vpa-color → FEAT-check-gaps-log → FEAT-guide-top → FEAT-collapse-btn → FEAT-guide-icon），每个功能点 PR 合并后再开始下一个。BUG-vpa-color 和 FEAT-check-gaps-log 改动文件不重叠，可与 BUG-align 同步并行。

### R5 — BUG-vpa-color 破位警示与共振主升浪 emoji 相同

**风险**：修改后 SIGNAL_CONFIG[1]（共振主升浪）和 SIGNAL_CONFIG[3]（破位警示）均使用 `🟢`，折叠条 badge 仅凭 emoji 无法区分。

**缓解**：两个信号的 `color` 值不同（`#26a69a` vs `#2ea043`），badge 背景色和文字颜色均由 `color` 决定，视觉上 teal 青绿与纯绿有明显差异；加之 badge 同时展示 `label` 文字（"共振主升浪" / "破位警示"），用户不会混淆。**emoji 相同是可接受的设计折衷**。

### R6 — FEAT-guide-icon 依赖 FEAT-guide-top，两者顺序不能颠倒

**风险**：FEAT-guide-icon 在各面板 Panel 组件中实现图标渲染，但 MACD/RSI/KDJ 的说明浮层是在 FEAT-guide-top 中才新增的，若 FEAT-guide-icon 先于 FEAT-guide-top 实现，则无法在三个面板中验证效果。

**缓解**：开发顺序严格保证 FEAT-guide-top 合并后再开始 FEAT-guide-icon。FEAT-guide-icon 在 VPADefenderPanel（已有说明浮层）中可单独先验证，不阻塞整体进度。

---

## 六、不在本迭代范围内的事项

- **主图（K线区）`[?]` 说明浮层入口**（已由老板确认，延后至下一迭代）
- 任何后端 API 变更
- Watchlist 页面 VPA 信号列新增（已在 CLAUDE.md 裁定记录中标注"待评估"）
- 综合信号计算逻辑调整
- 新增技术指标
- 移动端适配
- 指标参数配置化（如 MACD 的 12/26/9 改为用户可调）
- VPA 四象限信号纳入综合信号计算（CLAUDE.md 裁定：两套信号体系独立并存）

---

*文档结束 — 如需补充验收测试用例或原型草图，请联系 PM。*

---

## 七、延期决策 — FEAT-resistance（空仓阻力线）

> **本章节记录 2026-03-24 PM 对"阻力线新需求"的评估结论。**
> 老板提出在 VPA 指标图（VPADefenderPanel）新增"空仓阻力线"，与防守线配合观察。

### 7.1 防守线算法回顾（参照基准）

当前 `core/indicator_engine.py` 中 `calc_vpa_defender` 的 Stop_Line（防守线）实现步骤：

1. 计算 `ATR(22)`（平均真实波幅，SMA 版）
2. 维护滚动累计最高收盘价 `running_max_close`（每根 bar 更新）
3. 候选值：`candidate = running_max_close - atr_multi × ATR[i]`
4. "**只升不降**"约束：`stop_line[i] = max(candidate, stop_line[i-1])`

含义：追踪历史最高价下方 ATR 倍数距离，每当价格创新高时线上移，下跌时不下降——作为多头持仓的动态止损参考。

---

### 7.2 阻力线算法设计（对称镜像）

**设计原则**：与防守线完全对称——防守线追踪最高价"下方"，阻力线追踪最低价"上方"；防守线"只升不降"，阻力线"**只降不升**"。

**算法步骤**（伪代码）：

```python
# 维护滚动累计最低收盘价
running_min_close = close[0]

for i in range(size):
    running_min_close = min(running_min_close, close[i])   # 只降不升
    if atr_series[i] is not None:
        candidate = running_min_close + atr_multi * atr_series[i]
        resistance_line[i] = candidate

# "只降不升"约束
for i in range(1, size):
    if resistance_line[i] is not None and resistance_line[i-1] is not None:
        if resistance_line[i] > resistance_line[i-1]:
            resistance_line[i] = resistance_line[i-1]
```

**参数复用**：ATR 周期 `atr_period=22`、倍数 `atr_multi=3.0` 与防守线保持一致，无需新增参数。

**经济含义**：

| 防守线（stop_line）| 阻力线（resistance_line）|
|------------------|------------------------|
| 追踪历史最高价，向上追高 | 追踪历史最低价，向下追低 |
| 价格创新高时上移 | 价格创新低时下移 |
| 跌回时不下降（保护多头利润）| 反弹时不上移（标定空头压力位）|
| 多头持仓时"最低要守的位置" | 空仓/空头时"最高阻力参考位置" |

---

### 7.3 涉及改动评估

| 层级 | 改动内容 | 复杂度 |
|------|---------|--------|
| 后端 `core/indicator_engine.py` | `calc_vpa_defender` 新增 `resistance_line` 序列计算（约 15 行）；返回字典新增 `"resistance_line"` 字段 | 低 |
| 后端 `api/` 路由/服务 | `kline_service` 透传新字段 `resistance_line`（与 `stop_line` 同结构，无需新增路由） | 极低 |
| 前端 `VPADefenderPanel.jsx` | 左 Y 轴新增阻力线曲线（橙黄色，与防守线蓝色区分）；`HELP_ITEMS` 新增一条阻力线说明 | 低 |
| 四象限信号 | **不调整**（见 §7.4）| 无需改动 |

整体实现复杂度：**低**。

---

### 7.4 四象限信号是否更新

**结论：本次不更新四象限信号。**

理由：
1. 四象限信号语义已经过老板确认并在 CLAUDE.md 裁定（2026-03-23）中写明"VPA-Defender 不参与综合信号计算"；修改信号逻辑需要单独的老板口头确认，不应在此次附带改动。
2. 阻力线作为纯视觉辅助线，**先上线观察**——让用户在真实股票上感受阻力线与防守线的配合效果，再决定是否纳入信号判断。
3. 若未来需要纳入，可新增"第五象限/六象限"判断维度（价格是否突破阻力线），作为独立迭代评估。

---

### 7.5 纳入迭代 8 的决策

**结论：延期至 iter8.1-patch，不纳入当前迭代 8。**

> ✅ **2026-03-24 老板口头确认，同意延期至 iter8.1-patch。** （正式裁定，优先级高于 PRD 文字）

**理由**：

1. **迭代边界清晰性**：当前迭代 8 范围已由老板确认为"UI 体验优化"（§一 目标）。§四 影响文件汇总明确写明 `core/indicator_engine.py` **不在本迭代改动范围内**。在交付窗口尾声插入后端指标引擎改动，违背迭代边界。

2. **并行开发风险**：现有 7 个功能点（BUG-emoji → FEAT-guide-icon）正在并行开发中，部分功能点（FEAT-guide-top / FEAT-guide-icon）涉及 `VPADefenderPanel.jsx`，在同一个迭代内叠加对 `VPADefenderPanel.jsx` 的前端扩展（新增阻力线曲线），会提高合并冲突概率。

3. **算法清晰、实现不复杂**：虽然实现简单，但越是简单的改动越应该在独立、安静的迭代中交付，避免被其他 PR 噪音掩盖测试覆盖。

**iter8.1-patch 范围（建议）**：仅含 FEAT-resistance，可作为单独 PR 快速交付，不等待迭代 9。

---

### 7.6 iter8.1-patch 完整需求说明（待老板确认后启动）

> ⚠️ **以下为 PM 预起草内容，需老板口头确认范围后方可交研发执行。**

#### §3 FEAT-resistance：VPA 副图新增空仓阻力线

**功能描述**：在 VPADefenderPanel 左 Y 轴（价格轴）新增"空仓阻力线"曲线，与现有防守线配合，形成"上有阻力、下有支撑"的双线通道视图。

---

**后端改动 — `core/indicator_engine.py`**

1. `calc_vpa_defender` 方法新增 `resistance_line` 序列计算（复用已有 `atr_series`，无需新增参数）。
2. 返回字典新增 `"resistance_line"` 键，类型与 `stop_line` 相同（`List[Optional[float]]`）。
3. 同步更新 `IndicatorResult.VPA_DEFENDER` 注释（无类型变更，dict 结构天然支持新增键）。

**算法**（详见 §7.2）：
- `running_min_close` 追踪历史最低收盘价（只降不升）
- `resistance_line[i] = running_min_close + 3.0 × ATR[i]`
- "只降不升"约束：若候选值 > 上一根值，保持上一根值

---

**后端改动 — `api/` 路由/服务**

`api/services/kline_service.py`（或对应透传逻辑）：将 `vpa_defender` 返回字典中的 `resistance_line` 字段透传至 API 响应，与 `stop_line` 并列。

**新字段**：`resistance_line: List[float | null]`（与 `stop_line` 字段格式完全一致）

无需新增路由，无需修改 API schema 文档结构（JSON 键新增向下兼容）。

---

**前端改动 — `web/src/components/VPADefenderPanel.jsx`**

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

**四象限信号**：**不变**。阻力线仅作为视觉参考曲线，不参与 `signal_series` 计算，不影响综合信号。（若后续使用一段时间后老板决定纳入信号，作为独立迭代另行规划。）

---

**验收标准（AC）**：

- [ ] AC-resistance-1：VPA 副图左 Y 轴展示橙黄色阻力线，与蓝色防守线、灰色收盘价共三条曲线同轴显示。
- [ ] AC-resistance-2：阻力线在价格持续下跌阶段随之下移，在价格反弹时保持水平（不上移），视觉验证"只降不升"特性。
- [ ] AC-resistance-3：阻力线与防守线"上下夹击"形态正常——多数情况下防守线在下、阻力线在上，形成价格通道。
- [ ] AC-resistance-4：hover 浮层（tooltip）显示阻力线当日数值，标注为"阻力线"。
- [ ] AC-resistance-5：`[?]` 说明浮层中新增阻力线说明条目，颜色为橙黄，说明文案不含买卖指令。
- [ ] AC-resistance-6：右侧 ChartSidebar 图例新增阻力线（橙黄横实线 + "阻力线"文字）。
- [ ] AC-resistance-7：VPA 折叠/展开后阻力线正常渲染，不出现闪烁或数据丢失。
- [ ] AC-resistance-8：各股票（A股/港股/美股）阻力线均可正常计算，不出现全 null 序列或异常值。

---

**影响文件**：

| 文件 | 修改内容 |
|------|---------|
| `core/indicator_engine.py` | `calc_vpa_defender` 新增 `resistance_line` 序列计算（约 15 行）；返回字典新增 `"resistance_line"` 字段 |
| `api/services/kline_service.py`（或透传层） | 透传 `resistance_line` 字段至 API 响应 |
| `web/src/components/VPADefenderPanel.jsx` | 新增橙黄阻力线曲线；`HELP_ITEMS` 新增说明条目；`legendItems` 新增图例 |

**不涉及改动**：
- 其他副图组件（MACD/RSI/KDJ）
- `useChartSync.js`（联动逻辑不变）
- 综合信号（`compositeSignal.js`、`calc_composite_signal`）
- 四象限 `signal_series` 计算逻辑

---

*§3 FEAT-resistance 章节结束 — 待老板确认 iter8.1-patch 范围后启动。*

---

## 八、迭代8.1-patch 附加需求 — FEAT-legend-toggle：图例按钮化（点击切换曲线显示/隐藏）

> **文档版本**：v1.0（2026-03-24）
> **作者**：PM
> ⚠️ **需老板口头确认后方可启动研发，不得提前分配任务或开始实现。**

---

### 8.1 功能描述

将各指标副图面板（MACD / RSI / KDJ / VPA-Defender）右侧 ChartSidebar 中的 **图例条目（legendItems）升级为可交互按钮**。用户点击图例条目，可实时切换对应指标曲线的显示或隐藏，同一指标面板中其他曲线不受影响。

**典型用户场景**：
- 用户只想看 DIF 线和 DEA 线的金叉/死叉，隐藏 MACD 柱，让零轴线更清晰
- 用户在 KDJ 面板中隐藏波动剧烈的 J 线，只看 K/D 两线趋势
- 用户在 VPA-Defender 面板中隐藏 OBV 均线，只看 OBV 原始波动

---

### 8.2 各 Panel 的 ECharts Series Name 与 legendItems label 对应关系

调研结论（2026-03-24 读取源码）：

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

### 8.3 推荐技术方案

**方案：React State 驱动 series visibility（Option B — 最简化，数据流清晰）**

#### 8.3.1 数据结构扩展

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

#### 8.3.2 ChartSidebar 改动

新增 `onLegendToggle: (seriesName: string) => void` prop（可选）。

legendItems 渲染逻辑按 `seriesName` 是否存在分支：
- **有 `seriesName`**：渲染为 `<button>` 样式，内部维护 `activeMap: { [seriesName]: boolean }` 状态（初始全为 true，`useReducer` 或 `useState` 管理）
  - active 样式：正常颜色（现有样式不变）
  - inactive 样式：文字 `textDecoration: 'line-through'`，LegendMark 和文字 `opacity: 0.35`，背景微灰
  - 点击时切换 activeMap 对应 seriesName 的布尔值，并调用 `onLegendToggle(seriesName)`
  - **注意**：同一 `seriesName`（如 `'MACD柱'`）可能对应多个 legendItems，点击任意一个后，所有该 seriesName 的条目 activeMap 状态同步切换
- **无 `seriesName`**：保持当前纯展示 `<div>` 渲染，不响应点击

折叠按钮 `onToggle` prop 逻辑不变，与本功能正交。

#### 8.3.3 StockAnalysis 改动（各层 Panel 连接）

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

#### 8.3.4 各 Panel option 改动（ECharts legend 注册）

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

#### 8.3.5 折叠后再展开的状态保持

**问题**：Panel 展开时 ECharts 实例重建（`notMerge: true`），`dispatchAction` 产生的 legend 选中状态会被重置，导致用户折叠前已隐藏的 series 在展开后又重新显示，与 ChartSidebar 的 activeMap 视觉状态不一致。

**解决方案**：
- ChartSidebar 的 `activeMap` 是 React state，折叠展开不会重置（组件始终挂载），视觉状态保持。
- Panel 展开后（ECharts 实例刚挂载），需将当前 activeMap 中值为 `false` 的 series 重新 dispatchAction 一次。
- 实现方式：在 `useEffect` 中监听 `collapsed` 从 `true → false` 的变化，展开后遍历 activeMap，对所有 inactive series 调用 `dispatchAction('legendToggleSelect')`。
- **具体位置**：可在 StockAnalysis.jsx 中，每个 panel 展开时触发同步逻辑；或在 ChartSidebar 新增 `onPanelExpand()` 回调，由 ChartSidebar 主动通知父组件做同步。

建议用 `onPanelExpand` 回调方式（职责更清晰），StockAnalysis 中在 `togglePanel('MACD')` 时若变更为展开，随即遍历当前 activeMap 同步 dispatchAction。

---

### 8.4 验收标准（AC）

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

### 8.5 影响文件列表

| 文件 | 修改内容 |
|------|---------|
| `web/src/components/ChartSidebar.jsx` | legendItems 渲染逻辑：有 `seriesName` 的条目改为 `<button>`；新增 `activeMap` state（`useState`）；新增 `onLegendToggle` prop；inactive 样式（删除线+半透明）|
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

> ⚠️ **启动限制**：本节 FEAT-legend-toggle 需老板口头确认范围后方可安排研发执行，不得在确认前提前分配任务或开始编码。建议与 FEAT-resistance（空仓阻力线）一并纳入 iter8.1-patch 统一规划。

*§8 FEAT-legend-toggle 章节结束 — 2026-03-24 PM 完成调研，待老板确认后启动。*
