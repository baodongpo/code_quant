# PRD — 迭代 v0.8.3-feat：纵轴名称与多轴展示方案

**文档版本**：v1.0  
**日期**：2026-03-25  
**作者**：PM  
**状态**：草稿，待老板审阅确认  

---

## 一、背景与目标

### 1.1 背景

系统当前已完成 v0.8.1 迭代，Web 前端包含 5 个图表面板（主图 + MACD/RSI/KDJ/VPA-Defender 四个副图）。老板在使用过程中发现以下两个体验问题，本迭代针对性解决。

### 1.2 目标

| 编号 | 问题 | 目标 |
|------|------|------|
| P1 | 纵轴只显示数字，用户无法快速判断该轴含义 | 在不破坏现有宽度布局的前提下，为每个纵轴添加轴名称/单位标识 |
| P2 | 未来若新增与现有量纲不兼容的指标，无法再挂载第三 Y 轴 | 设计可扩展的多轴方案，明确规范后续新增指标的挂载策略 |

### 1.3 硬性约束（不可破坏）

- `grid.left: 60, grid.right: 60` 固定宽度（迭代8裁定，不得修改）
- `yAxis axisLabel.width: 52` 固定标签宽度（迭代8对齐修复结果）
- ECharts（echarts-for-react）框架内实现，不引入其他图表库
- 不增加 yAxisIndex 超出各面板当前上限（VPA 已用 0 和 1，不新增第三轴）
- 禁止任何买卖指令或投资建议内容

---

## 二、现状分析

### 2.1 各面板 Y 轴使用清单

#### 主图（MainChart.jsx）

| 轴位置 | gridIndex | yAxisIndex | 挂载系列 | 量纲 | 当前名称 |
|--------|-----------|------------|---------|------|---------|
| 左轴（grid[0]） | 0 | 0 | K线蜡烛、MA5/MA20/MA60、BOLL三轨 | 价格（元） | 无 |
| 左轴（grid[1]） | 1 | 1 | 成交量柱、MAVOL5/MAVOL10 | 成交量（股） | 无 |

> 注意：主图的成交量子图（grid[1]）使用独立 grid，其 Y 轴（yAxisIndex:1）在视觉上位于成交量子图的左侧，并非右侧。主图整体无右 Y 轴。

**现状问题**：用户无法直观区分上方大图和下方小图分别代表"价格"还是"量"，悬停 tooltip 虽有说明但平时不可见。

---

#### MACD 副图（MACDPanel.jsx）

| 轴位置 | yAxisIndex | 挂载系列 | 量纲 | 当前名称 |
|--------|------------|---------|------|---------|
| 左轴 | 0 | DIF 线、DEA 线、MACD 柱 | MACD 无量纲数值（通常在 -1 ~ +1 之间浮动） | 无 |

**现状问题**：用户不清楚纵轴数字的含义，也无法判断 0 轴线的语义（多空分水岭）。

---

#### RSI 副图（RSIPanel.jsx）

| 轴位置 | yAxisIndex | 挂载系列 | 量纲 | 当前名称 |
|--------|------------|---------|------|---------|
| 左轴 | 0 | RSI14 | 0~100 无量纲百分比 | 无（但 formatter 已将 70/30 刻度替换为"超买70"/"超卖30"文字） |

**现状问题**：已有 formatter 部分缓解，但整体轴含义仍不明确，"超买70"/"超卖30"标签较长，10px 字体下可能被截断（width:52 约 5~6 个中文字符）。

---

#### KDJ 副图（KDJPanel.jsx）

| 轴位置 | yAxisIndex | 挂载系列 | 量纲 | 当前名称 |
|--------|------------|---------|------|---------|
| 左轴 | 0 | K 线、D 线、J 线 | -10 ~ 110 无量纲，固定范围 | 无 |

**现状问题**：K/D/J 三条线量纲相同，无多轴问题；但轴名称缺失，新手不理解纵轴含义。

---

#### VPA-Defender 副图（VPADefenderPanel.jsx）

| 轴位置 | yAxisIndex | 挂载系列 | 量纲 | 当前名称 |
|--------|------------|---------|------|---------|
| 左轴 | 0 | 收盘价、防守线、阻力线 | 价格（元） | 无 |
| 右轴 | 1 | OBV、OBV均线 | OBV 能量累计（股，通常为千万~亿量级） | 无（但右轴 formatter 已做万/亿换算） |

**现状问题**：
1. 左轴和右轴各自无名称，用户不理解双轴关系
2. 右轴虽有万/亿 formatter，但缺少"OBV"标识，用户不知道右侧数字代表什么
3. **这是唯一一个已用满左右两轴的面板**，是问题二的直接触发场景

---

### 2.2 问题一详细分析：为何缺名称

当前代码中，所有 `yAxis` 配置均未设置 `name` 字段。ECharts 的 `yAxis.name` 属性默认展示在轴线顶端（`nameLocation: 'end'`），位于 `grid.top` 所预留的空白区域内。

当前各面板 `grid.top` 值如下：

| 面板 | grid.top | 可用空间 |
|------|---------|---------|
| 主图 K 线区 | 28px | 充裕 |
| 主图成交量区 | 74%（相对定位） | 充裕 |
| MACD | 20px | 偏小 |
| RSI | 20px | 偏小 |
| KDJ | 20px | 偏小 |
| VPA | 20px | 偏小 |

副图 top 仅 20px，若在此放置轴名称，会与图表内容重叠或被截断。需要将名称放置在合适位置，或微调展示策略。

---

### 2.3 问题二详细分析：多轴扩展瓶颈

ECharts 支持在同一图表中配置多个 Y 轴（`yAxis` 数组），最常见的是左右各一（`position: 'left'` 和 `position: 'right'`）。

**当前瓶颈**：
- `left: 60` 和 `right: 60` 各分配 60px 给轴刻度区域
- 每个轴的 `axisLabel.width: 52`，加上轴线/刻度线本身约 8px，恰好用满 60px
- 若新增第三 Y 轴，ECharts 需要额外宽度偏移（`offset` 属性），这将挤占图表绘图区宽度
- 固定 `left: 60` 无法容纳第三轴，强行新增会导致轴标签被截断或溢出

**未来可能触发该问题的场景**（供参考，非本次迭代实现）：
- VPA 面板新增"成交额"（元，量纲与价格和 OBV 均不同）
- 新建面板同时展示资金流入/流出与换手率（量纲不同）

---

## 三、方案设计

### 3.1 问题一：轴名称/单位显示方案

#### 方案选项

**方案 A：ECharts `yAxis.name` 属性（原生轴标题）**

在 yAxis 配置中增加 `name` 字段，利用 ECharts 内置的轴名称渲染机制。

```js
yAxis: {
  name: '价格(元)',
  nameLocation: 'end',      // 轴名出现在轴线顶端（默认）
  nameGap: 6,               // 名称与轴末端的间距
  nameTextStyle: {
    color: C.textMuted,
    fontSize: 10,
    align: 'right',         // 右对齐，贴近轴线区域
  },
  // ...其余不变
}
```

优点：
- ECharts 原生支持，实现成本最低
- 名称随图表自适应，无需额外 HTML 层
- `nameLocation: 'end'` 将名称置于轴顶，恰好利用 `grid.top` 的空白区域
- 不占用轴标签宽度（name 与 axisLabel 渲染在不同位置）

缺点：
- 副图 `grid.top: 20` 时，轴名与图表内顶部数据点可能有视觉拥挤感
- 需要控制名称文字长度（建议不超过 6 个字符，约 60px）

**方案 B：面板标题行中嵌入轴名说明**

在各面板标题行（已有 `MACD(12,26,9)` 等文字）中，在右侧添加轴单位说明文字，如 `左轴：元 | 右轴：OBV`。

优点：
- 不修改 ECharts 配置，实现简单
- 副图标题行已有剩余空间

缺点：
- 文字与轴视觉上不直接关联，用户需要"对应"阅读
- 当面板折叠时信息丢失
- 对双轴面板（VPA）能清晰说明，但对单轴面板稍显多余

**方案 C：轴标签 formatter 颜色编码**

将左轴标签渲染为一种颜色（如浅蓝），右轴标签渲染为另一种颜色（如浅橙），从视觉上区分两轴含义，配合 tooltip 中已有的轴名说明。

优点：
- 视觉区分度高，适合双轴面板
- 不增加任何文字内容

缺点：
- 仅适用于双轴面板，单轴面板无意义
- 颜色差异在暗色主题下需仔细调校
- 不能传递"这是价格"、"这是OBV"等语义信息

---

#### 推荐方案：方案 A（ECharts `yAxis.name`）+ 方案 C 颜色辅助（仅 VPA 双轴）

**推荐理由**：
1. 方案 A 语义最清晰，一行配置即可，ECharts 原生渲染无兼容风险
2. 对于副图 `top:20` 的拥挤问题，可将 `nameLocation` 改为 `'start'`（即轴线底端），将轴名放到图表底部，避免与顶部数据点冲突
3. VPA 双轴面板额外增加颜色区分，强化左右轴对应关系

**具体实施规格**：

| 面板 | 轴 | name 文字 | nameLocation | 颜色 |
|------|----|-----------|-------------|------|
| 主图 K线区 | 左轴(price) | `'元'` | `'end'`（顶端，top:28 有空间） | C.textMuted |
| 主图成交量区 | 左轴(vol) | `'万股'` | `'end'` | C.textMuted |
| MACD | 左轴 | `'MACD'` | `'end'` | C.textMuted |
| RSI | 左轴 | `'RSI'` | `'end'` | C.textMuted |
| KDJ | 左轴 | `'KDJ'` | `'end'` | C.textMuted |
| VPA | 左轴(price) | `'元'` | `'end'` | `#42a5f5`（蓝，对应OBV线色） → 改用 C.textMuted 保持统一 |
| VPA | 右轴(OBV) | `'OBV'` | `'end'` | `#ffa726`（橙，对应OBV均线色） |

> **注**：VPA 右轴名称颜色使用 OBV 系列的颜色（橙 `#ffa726`），形成"轴名颜色 = 系列颜色"的视觉关联，帮助用户快速配对。VPA 左轴使用 `C.textMuted` 保持统一风格。

**nameGap 与字体规格统一**：

```js
nameTextStyle: {
  color: C.textMuted,    // 或右轴特殊颜色
  fontSize: 10,
  fontWeight: 500,
  padding: [0, 0, 0, 0],
}
nameGap: 4
nameLocation: 'end'
```

**RSI 轴标签 formatter 调整**：

当前 RSI 轴 formatter 将 `70` 渲染为 `'超买70'`、`30` 渲染为 `'超卖30'`，共 4 个中文字符+数字，在 `width:52` 约束下可能截断。建议简化：

- `70` → `'超买'`（2字+数字在标签内，数字显示在轴刻度格中）
- 或恢复纯数字 `70` / `30`，依赖轴名 `'RSI'` + 面板标题中的说明传递语义

本次推荐保持现有 formatter 逻辑，仅在 `'超买70'` / `'超卖30'` 之间做截断验证测试，如有截断则改为 `'▲70'` / `'▼30'`（仅 3~4 字符，宽度安全）。

---

### 3.2 问题二：超过 2 个量纲轴的解决方案

#### 备选方案分析

**方案一：ECharts 第三 Y 轴 + `offset` 偏移**

ECharts 支持通过 `offset` 属性将多个同侧 Y 轴错位展示，例如同侧左/左+偏移60/右 形成三轴。

```js
yAxis: [
  { position: 'left' },               // 主左轴
  { position: 'left', offset: 60 },   // 第二左轴，向左偏移60px
  { position: 'right' },              // 右轴
]
```

优点：
- ECharts 原生支持，数据读取最直观

缺点：
- **与 `grid.left: 60` 硬性约束直接冲突**：第二左轴偏移 60px 意味着 grid.left 需要增加到 120px，否则轴标签溢出至图表可视区之外
- 视觉上三轴刻度叠加，暗色主题下极难区分
- 用户理解成本高，背离"新手友好"设计原则
- **本方案不推荐，与迭代8裁定的 left:60/right:60 约束不兼容，不得采用**

---

**方案二：颜色编码刻度线（Color-coded Axis Labels）**

在双轴基础上，将右轴的刻度标签颜色与对应系列颜色保持一致，左轴同理。当存在"量纲上兼容但视觉上需区分"的多条曲线时，通过颜色关联而非独立轴来传递归属关系。

例如：VPA 左轴文字颜色 = 防守线红色（`#ef5350`），右轴文字颜色 = OBV 蓝色（`#42a5f5`）。

优点：
- 不需要任何布局变更，零宽度代价
- 视觉关联自然，与图例颜色统一

缺点：
- 仅解决"用户分不清哪条线对应哪个轴"的问题，不解决"第三量纲无法显示刻度"的根本问题
- 若两条曲线量纲相差悬殊（如价格10元 vs OBV 5亿），颜色区分也无法帮助用户读取第三维的精确值

**适用场景**：同一侧两轴，或单轴多系列的视觉增强。本次 VPA 面板即适用此方案（已在推荐方案中结合）。

---

**方案三：Tooltip 替代轴显示（隐藏次轴，悬停读值）**

将数量超出 2 的量纲曲线的轴设置为不显示（`axisLabel.show: false`，`axisLine.show: false`），这些系列仍挂载到某一 yAxis 以获得正确的数据映射，但轴刻度完全通过 tooltip 呈现。

```js
// 第三量纲系列挂载到右轴，但右轴不显示刻度
yAxis[1]: {
  show: false,          // 隐藏整个轴
  // 或只隐藏标签：
  axisLabel: { show: false },
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { show: false },
}
```

tooltip formatter 中为该系列补充单位说明，如 `成交额: 12.3亿元`。

优点：
- **完全不占用宽度**，100% 兼容 `left:60/right:60` 约束
- ECharts 仍能正确计算该系列的位置/缩放
- Tooltip 已被用户建立阅读习惯（现有面板 tooltip 均有完整数据）
- 对于辅助参考性质的第三维数据，精确刻度价值有限，tooltip 已足够

缺点：
- 用户必须悬停才能获得第三量纲的精确值，无法"扫一眼"
- 若第三维是主要观察指标（而非辅助），体验较差

**适用场景**：第三量纲为辅助/参考性指标，不需要频繁精确读值时。

---

**方案四：新建独立面板（拆分策略）**

当新增指标与现有面板中任何量纲均不相容，且用户确实需要轴刻度时，强制拆分为新的独立 200px 副图面板，而非在现有面板内新增轴。

优点：
- **根本解决量纲冲突**，每个面板最多双轴，规范清晰
- 与现有系统设计哲学一致（每种指标体系独立面板）
- 无任何布局约束挑战

缺点：
- 面板数量增加，页面总高度增长
- 某些指标本身设计上就是"辅助当前面板"而非"独立指标"，强制分离反而割裂语义

**适用场景**：新增的第三维指标本身具有独立分析价值（如单独的换手率面板、资金流向面板）。

---

#### 推荐方案及决策树

**推荐组合**：方案三（Tooltip 替代）+ 方案四（拆分面板），根据新增指标性质二选一，禁止采用方案一（第三轴 offset）。

**决策树**（适用于未来新增指标时）：

```
新增指标 X 的量纲是否与现有面板任一轴相容？
  ├─ 是（量纲相同或接近）→ 直接挂载到现有轴，颜色区分即可
  └─ 否（量纲不同）
        ├─ X 是辅助参考指标（不需要精确读轴值）？
        │     └─ 是 → 方案三：挂 yAxis[1] 但隐藏右轴刻度，tooltip 说明
        └─ X 是主要观察指标（需要精确轴刻度）？
              └─ 是 → 方案四：新建独立副图面板
```

**补充说明**：
- VPA 面板目前已用满双轴（左=价格，右=OBV），是唯一满载面板
- 若未来 VPA 需新增"成交额"：成交额量纲为"元"，与左轴价格量纲类别相同但数值相差悬殊（价格 10 元 vs 成交额 10 亿元） → 建议**方案三**：成交额系列挂右轴但隐藏右轴刻度（OBV 右轴仍可显示），tooltip 展示成交额数值
- 若需要为成交额单独呈现轴刻度 → 建议**方案四**：新建"成交分析"面板

---

## 四、各面板具体改动点

### 4.1 主图（MainChart.jsx）

**yAxis[0]（K线价格轴）**：
- 新增 `name: '元'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`

**yAxis[1]（成交量轴）**：
- 新增 `name: '万股'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`

> 注：主图 grid.top: 28（K线区）有充足空间，轴名不会遮挡内容。

---

### 4.2 MACD 副图（MACDPanel.jsx）

**yAxis[0]**：
- 新增 `name: 'MACD'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`

> 注：MACD 面板 grid.top: 20，轴名置于顶端，字号 10px 高度约 12px，与 top:20 的空间基本不冲突。如出现遮挡，可将 grid.top 调整为 24（仅本面板），或改用 `nameLocation: 'start'`（轴线底端）。

---

### 4.3 RSI 副图（RSIPanel.jsx）

**yAxis[0]**：
- 新增 `name: 'RSI'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`
- **axisLabel formatter 调整**：验证 `'超买70'`（4字符约40px）在 `width:52` 下是否截断；若截断改为 `'▲70'` / `'▼30'`（约3字符30px，安全）

---

### 4.4 KDJ 副图（KDJPanel.jsx）

**yAxis[0]**：
- 新增 `name: 'KDJ'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`

---

### 4.5 VPA-Defender 副图（VPADefenderPanel.jsx）

**yAxis[0]（左轴，价格）**：
- 新增 `name: '元'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: C.textMuted, fontSize: 10 }`

**yAxis[1]（右轴，OBV）**：
- 新增 `name: 'OBV'`
- 新增 `nameLocation: 'end'`
- 新增 `nameGap: 4`
- 新增 `nameTextStyle: { color: '#ffa726', fontSize: 10 }`（橙色，与 OBV 均线颜色一致，形成视觉关联）

> VPA 面板是唯一双轴面板，通过右轴名称颜色 `#ffa726` 与系列颜色关联，帮助用户快速建立"右侧数字 = OBV"的映射关系。

---

### 4.6 新增：多轴策略规范文档（注释层面）

在 VPADefenderPanel.jsx 顶部注释块中补充一段多轴策略说明（注释，非用户可见内容）：

```js
/**
 * 【多轴策略规范 v0.8.3】
 * 本面板已使用满双轴（left=价格，right=OBV）。
 * 若未来需要新增第三量纲指标：
 *   - 辅助性指标（不需精确轴刻度）→ 挂 yAxisIndex:1，隐藏右轴标签，tooltip说明
 *   - 主要性指标（需精确轴刻度）→ 新建独立副图面板，禁止在此面板追加第三轴
 * 禁止使用 yAxis offset 方案（与 grid.left:60 约束冲突）。
 */
```

---

## 五、实施范围和优先级

### 5.1 本次迭代必做（P0）

| 编号 | 内容 | 涉及文件 |
|------|------|---------|
| FEAT-axis-name-main | 主图价格轴和成交量轴添加轴名 `'元'`、`'万股'` | MainChart.jsx |
| FEAT-axis-name-macd | MACD 面板添加轴名 `'MACD'` | MACDPanel.jsx |
| FEAT-axis-name-rsi | RSI 面板添加轴名 `'RSI'`，验证并修复 formatter 截断 | RSIPanel.jsx |
| FEAT-axis-name-kdj | KDJ 面板添加轴名 `'KDJ'` | KDJPanel.jsx |
| FEAT-axis-name-vpa | VPA 面板左轴添加 `'元'`，右轴添加彩色 `'OBV'` | VPADefenderPanel.jsx |
| DOC-multi-axis-rule | VPADefenderPanel.jsx 顶部注释补充多轴策略规范 | VPADefenderPanel.jsx |

### 5.2 本次迭代可选（P1，视工时决定）

| 编号 | 内容 | 说明 |
|------|------|------|
| OPT-axis-color-vpa-left | VPA 左轴 axisLabel 颜色与防守线颜色关联（`#ef5350`） | 增强左右轴视觉区分，与右轴 OBV 橙色形成对称；但可能影响暗色主题可读性，需评估 |
| OPT-grid-top-adjust | MACD/RSI/KDJ 面板 `grid.top` 从 20 调整为 24，给轴名预留更多空间 | 仅在实测发现轴名遮挡问题时执行；属于轻微布局微调，不影响横向对齐 |

### 5.3 后续迭代规划（P2，本次不做）

| 编号 | 内容 | 说明 |
|------|------|------|
| FUTURE-vol-unit | 主图成交量轴单位从"万股"自适应切换（万股/亿股） | 不同市值股票成交量量级差异大，自适应单位体验更好；本次固定"万股"已够用 |
| FUTURE-multi-axis-tooltip | 当某系列无对应轴刻度时，tooltip 中补充单位标注 | 为方案三的 tooltip 替代策略做规范化封装 |
| FUTURE-watchlist-vpa-col | Watchlist 页面新增 VPA 信号独立列 | 已在迭代7裁定记录中标注为后续评估项 |

---

## 六、验收标准（Acceptance Criteria）

### AC-01：主图轴名称可见性

- [ ] 主图 K 线区左轴顶端显示 `元` 字样，字色与现有轴标签一致（`C.textMuted`），字号 10px
- [ ] 主图成交量区左轴顶端显示 `万股` 字样，样式同上
- [ ] 轴名不遮挡任何 K 线蜡烛图或成交量柱
- [ ] 主图 `grid.left: 60` 和 `grid.right: 60` 数值不变

### AC-02：MACD 轴名称

- [ ] MACD 面板左轴顶端显示 `MACD` 字样
- [ ] 字号 10px，颜色 `C.textMuted`
- [ ] 轴名不遮挡 MACD 柱/DIF/DEA 曲线

### AC-03：RSI 轴名称及 formatter 截断修复

- [ ] RSI 面板左轴顶端显示 `RSI` 字样
- [ ] 在当前 `width: 52` 约束下，`70` 对应的轴标签文字完整显示，不出现省略号（`...`）
- [ ] `30` 对应的轴标签文字完整显示，不出现省略号

### AC-04：KDJ 轴名称

- [ ] KDJ 面板左轴顶端显示 `KDJ` 字样
- [ ] 字号 10px，颜色 `C.textMuted`

### AC-05：VPA-Defender 双轴名称及颜色

- [ ] VPA 面板左轴顶端显示 `元` 字样，颜色 `C.textMuted`
- [ ] VPA 面板右轴顶端显示 `OBV` 字样，颜色 `#ffa726`（橙色，与 OBV 均线颜色一致）
- [ ] 左右轴名称均不遮挡收盘价/防守线/阻力线/OBV/OBV均线曲线

### AC-06：宽度布局约束

- [ ] 所有面板的 `grid.left` 仍为 60，`grid.right` 仍为 60（在 ECharts option 中可验证）
- [ ] 所有面板的 `yAxis axisLabel.width` 仍为 52
- [ ] 浏览器实际渲染中，各面板 Y 轴内容区宽度对齐，无错位（与迭代8 BUG-align 修复结果一致）

### AC-07：多轴策略规范注释

- [ ] VPADefenderPanel.jsx 顶部注释中包含多轴策略规范说明（禁止 offset 方案 + 决策树文字）
- [ ] 注释内容不含任何买卖指令

### AC-08：Tooltip 内容不受影响

- [ ] 所有面板的 tooltip formatter 功能正常，悬停仍能显示完整数值（本次改动不触及 tooltip 逻辑）

### AC-09：新手说明浮层内容不受影响

- [ ] 各面板 `[?]` 新手说明浮层内容、展开/折叠行为不受本次改动影响

### AC-10：全面板视觉回归

- [ ] 日K/周K/月K 三个周期切换后，轴名称均正常显示
- [ ] 切换股票后，轴名称均正常显示
- [ ] 图表 dataZoom 拖动后，轴名称位置不漂移

---

## 七、附录：ECharts `yAxis.name` 关键配置参考

```js
yAxis: {
  // 必填字段
  name: 'OBV',                    // 轴名称文字
  nameLocation: 'end',            // 'start'=底端 | 'middle'=居中 | 'end'=顶端（默认）
  nameGap: 4,                     // 名称与轴末端的像素间距
  nameTextStyle: {
    color: '#ffa726',             // 名称文字颜色
    fontSize: 10,                 // 字号，与 axisLabel 一致
    fontWeight: 500,
    align: 'center',              // ECharts 默认已处理，通常无需指定
  },
  // 已有字段（不变）
  scale: true,
  axisLabel: { color: C.textMuted, fontSize: 10, width: 52, overflow: 'truncate' },
  axisLine: { lineStyle: { color: C.axisLine } },
  // ...
}
```

**nameLocation 选择建议**：
- 主图（grid.top:28）→ `'end'`（顶端，28px 够用）
- 副图（grid.top:20）→ `'end'`（顶端，10px 字号约 12px 高，基本可容纳；如遮挡则改 `'start'`）
- 双轴面板（VPA）→ 左轴 `'end'`，右轴 `'end'`，两侧均在顶端，视觉对称

**轴名不计入 axisLabel.width 约束**：ECharts 的 `yAxis.name` 渲染在轴线顶/底端（取决于 nameLocation），与刻度标签（axisLabel）渲染位置不同，不受 `axisLabel.width: 52` 约束。轴名文字会渲染在 grid 外的 padding 区域内，因此理论上不影响图表内容区宽度。

---

*文档结束。待老板确认范围后，Dev 可按本文档开始实施。*
