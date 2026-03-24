# AI 量化辅助决策系统 - 迭代7产品需求文档（PRD）

**版本**: v7.0
**日期**: 2026-03-23
**范围**: 跨图十字线联动修复、VPA-Defender 量价共振复合指标
**前置**: 迭代1~5 均已完成（tag `v0.5.1-fix`），迭代6 待规划（与本迭代无依赖）

---

## 1. 迭代7目标

**主题：跨图联动体验修复 + 量价共振复合指标**

| 迭代 | 目标 |
|------|------|
| 迭代1 | 能跑、能采数据 |
| 迭代2 | 能持续运行、服务器无人值守 |
| 迭代3 | 能看、能分析——技术指标可视化辅助决策 |
| 迭代4 | 能更全、更稳、更主动——基本面数据/容灾/归档/告警 |
| 迭代5 | 更可靠、更易用、更安全——写入可靠性修复、信息密度提升、局域网开放访问 |
| **迭代7** | **更精准的交互体验 + 更深度的量价分析维度** |

**核心价值主张**：
1. **修复跨图十字线联动缺陷**（BUG-crosshair）：鼠标 hover 副图时主图及其他副图无十字线同步，交互体验割裂，修复后全图实现纵向虚线全局联动。
2. **新增 VPA-Defender 量价共振复合指标**（FEAT-vpa-defender）：融合 ATR 吊灯止损线与平滑 OBV 资金流，以四象限信号直观展示量价关系，帮助散户识别机构隐蔽出货、确认趋势共振、划定动态防守底线。

---

## 2. 需求范围与优先级

| 编号 | 需求标题 | 优先级 | 涉及层 | 说明 |
|------|---------|--------|--------|------|
| BUG-crosshair | 跨图十字线纵轴全局联动修复 | **P0** | 前端 | 交互体验 BUG，所有用户可感知 |
| FEAT-vpa-defender | VPA-Defender 量价共振复合指标 | **P1** | 后端+前端 | 新增复合指标，涉及算法计算+API+前端面板 |

**优先级说明**：
- **P0**：交互体验 BUG，影响现有功能的使用质量，必须优先修复
- **P1**：新增功能，本迭代核心交付物

---

## 3. BUG-crosshair：跨图十字线纵轴全局联动修复

### 3.1 问题现象

**复现步骤**：
1. 打开个股分析页，确保 MACD / RSI / KDJ 副图至少有一个处于展开状态
2. 将鼠标从主图区域移动到任意副图区域（如 MACD 面板）
3. 在副图上左右移动鼠标

**预期行为**：
- 主图和所有展开的副图均显示同一根纵向虚线（与 hover 位置的日期对齐），各自的 tooltip 浮层同步显示对应日期的数据

**实际行为**：
- 副图内部有十字线显示，但主图和其他副图**无任何纵向虚线响应**
- 仅当鼠标在主图上时，副图才会同步显示 tooltip（单向联动）

**根因分析**：
- 当前 `useChartSync.js` 仅注册了主图的 `updateAxisPointer` 事件（第 54 行 `main.on('updateAxisPointer', onAxisPointer)`），副图触发 hover 时不会反向通知主图和其他副图
- `mouseleave` 事件也仅注册在主图 DOM 上（第 61 行），副图的鼠标离开事件未处理

### 3.2 目标效果

1. **全局纵向虚线联动**：鼠标 hover 到**任意图表**（主图 / MACD / RSI / KDJ）时，所有已展开的图表均同步显示同一根纵向虚线
2. **纵线样式统一**：虚线样式（`type: 'dashed'`），颜色与现有十字线一致（`#8b949e`）
3. **纵线渲染层级**：纵线需渲染在最顶层（z-index 最高），不被 K 线蜡烛、成交量柱、MACD 柱等图形遮挡
4. **tooltip 双向同步**：hover 副图时，主图的 tooltip 浮层也同步显示对应日期的 OHLCV 数据
5. **鼠标离开任意图表**：所有图表的 tooltip 和纵线均隐藏
6. **折叠兼容**：副图折叠/展开后，联动关系自动重建（沿用现有 `collapsed` 依赖数组机制）

### 3.3 实现方向建议

**方案 A（推荐）：扩展现有 `useChartSync.js`**
- 对所有副图也注册 `updateAxisPointer` 事件，副图 hover 时反向 `dispatchAction({ type: 'showTip' })` 到主图和其他副图
- 对所有图表 DOM 注册 `mouseleave` 事件，鼠标离开时广播 `hideTip` 到其余所有图表
- 使用互斥标志防止循环触发（与现有 dataZoom 同步的 `syncing` 模式一致）

**方案 B：`echarts.connect()` + group**
- 为所有图表实例设置相同的 `group`，使用 `echarts.connect(groupId)` 自动联动
- 注意：主图包含两个 grid（K线区 + 成交量区），`echarts.connect()` 在成交量区域可能存在已知兼容性问题（现有代码注释已记录此问题），需验证是否已在新版 ECharts 中修复

**建议 Dev 优先尝试方案 A**，因为与现有架构一致、可控性更强。

### 3.4 影响范围

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `web/src/hooks/useChartSync.js` | 修改 | 核心修复：副图 → 主图反向联动 |
| `web/src/components/MACDPanel.jsx` | 可能微调 | 确认 axisPointer 配置兼容 |
| `web/src/components/RSIPanel.jsx` | 可能微调 | 同上 |
| `web/src/components/KDJPanel.jsx` | 可能微调 | 同上 |

### 3.5 验收标准

| # | 验收项 | 验证方式 |
|---|--------|---------|
| AC-1 | 鼠标 hover 主图 → 所有展开副图同步显示纵向虚线和 tooltip | 手动测试 |
| AC-2 | 鼠标 hover 任意副图 → 主图和其他展开副图同步显示纵向虚线和 tooltip | 手动测试 |
| AC-3 | 纵向虚线为 dashed 样式，颜色 `#8b949e`，不被图形元素遮挡 | 视觉检查 |
| AC-4 | 鼠标离开任意图表 → 所有图表的 tooltip 和纵线均隐藏 | 手动测试 |
| AC-5 | 副图折叠后再展开，联动关系自动重建，无需刷新页面 | 手动测试 |
| AC-6 | dataZoom 滑动条双向联动不受影响（回归验证） | 手动测试 |

---

## 4. FEAT-vpa-defender：量价共振与动态防守系统（VPA-Defender）

### 4.1 设计理念

VPA-Defender（Volume-Price Analysis + Dynamic Defender）是一个面向散户中低频波段操作的复合指标系统。核心思想：

- **不预测未来，专注"确认当下"与"底线防守"**
- 用**平滑 OBV** 识别机构缓慢出货（量变先于价变）
- 用 **ATR 吊灯止损线**划定无条件防守底线（趋势反转的客观信号）
- 两者结合形成**四象限信号矩阵**，帮助用户快速判断当前所处市场状态

> **边界声明**：本指标为数据辅助分析工具，所有信号描述均为市场状态观测，不构成任何买入、卖出、持有的投资建议或操作指令。

### 4.2 输入参数

| 参数名 | 默认值 | 含义 |
|--------|--------|------|
| `ATR_Period` | 22 | ATR 计算周期（约一个自然月交易日），过滤单周噪音 |
| `ATR_Multi` | 3.0 | 止损容忍乘数（3 倍 ATR 定性为趋势反转，容忍日常 1.5~2 倍洗盘波动） |
| `OBV_MA_Period` | 20 | OBV 平滑均线周期，过滤单日成交量噪音 |

**所需数据字段**：`high`、`low`、`close`、`volume`（均已在 `kline_data` 表中存在，无需新增数据库字段或表）

### 4.3 核心算法

#### 4.3.1 ATR（Average True Range，平均真实波幅）

```
TR(i) = max(
    high(i) - low(i),
    |high(i) - close(i-1)|,
    |low(i)  - close(i-1)|
)

ATR(i) = SMA(TR, ATR_Period)
       = sum(TR[i-ATR_Period+1 : i+1]) / ATR_Period
```

- 第一根 bar 的 `close(i-1)` 使用 `last_close` 字段（如可用）或 `close(0)` 自身
- 前 `ATR_Period - 1` 个位置 ATR 值为 `None`（数据不足）

#### 4.3.2 ATR 动态防守线（吊灯止损 Chandelier Exit）

```
Stop_Line(i) = max(close[0:i+1]) - ATR_Multi × ATR(i)
```

即：**历史最高收盘价**减去 3 倍 ATR。

**关键特性**：
- Stop_Line **只升不降**——随价格创新高自动上移，价格回调时保持不动
- 实现时需维护一个 `running_max_close` 变量，逐 bar 取 `max(running_max_close, close[i])`
- 前 `ATR_Period - 1` 个位置 Stop_Line 值为 `None`

#### 4.3.3 OBV（On-Balance Volume，能量潮）

```
OBV(0) = 0
OBV(i) = OBV(i-1) + volume(i)    if close(i) > close(i-1)
OBV(i) = OBV(i-1) - volume(i)    if close(i) < close(i-1)
OBV(i) = OBV(i-1)                if close(i) == close(i-1)
```

- OBV 从第 1 根 bar 开始有值（第 0 根 OBV = 0）
- `close(i-1)` 可使用上一根 bar 的 close，或 `last_close` 字段

#### 4.3.4 OBV 平滑均线

```
OBV_MA20(i) = SMA(OBV, OBV_MA_Period)
            = sum(OBV[i-OBV_MA_Period+1 : i+1]) / OBV_MA_Period
```

- 前 `OBV_MA_Period - 1` 个位置为 `None`
- 复用 `IndicatorEngine.ma()` 方法的逻辑（对 OBV 序列做 SMA）

### 4.4 四象限信号定义

| 状态 | 条件 | 含义 | 标签 | 颜色 |
|------|------|------|------|------|
| 状态1 | `close > Stop_Line` 且 `OBV > OBV_MA20` | 共振主升浪：价格在防守线上方，资金持续流入 | 共振主升浪 | 绿色（`#26a69a`） |
| 状态2 | `close > Stop_Line` 且 `OBV <= OBV_MA20` | 顶背离预警：价格仍强但资金开始流出（机构隐蔽出货特征） | 顶背离预警 | 黄色（`#ffd54f`） |
| 状态3 | `close <= Stop_Line`（无论 OBV） | 破位断头铡：价格跌破动态防守线，趋势可能反转 | 破位警示 | 红色（`#ef5350`） |
| 状态4 | `close <= Stop_Line` 且 `OBV > OBV_MA20` | 底背离吸筹：价格弱势但资金悄然流入，观察区 | 底部观察 | 灰白色（`#b0bec5`） |

**信号优先级**：状态3 的 `close <= Stop_Line` 条件优先于 OBV 判断——即 `close <= Stop_Line` 时，如果 `OBV > OBV_MA20` 则为状态4，否则为状态3。

**判断逻辑伪代码**：
```python
if close > stop_line:
    if obv > obv_ma20:
        signal = 1  # 共振主升浪
    else:
        signal = 2  # 顶背离预警
else:  # close <= stop_line
    if obv > obv_ma20:
        signal = 4  # 底背离吸筹
    else:
        signal = 3  # 破位断头铡
```

当 `Stop_Line` 或 `OBV_MA20` 为 `None`（数据不足）时，信号为 `None`，前端不展示信号标签。

### 4.5 后端实现范围

#### 4.5.1 新增方法：`core/indicator_engine.py`

在 `IndicatorEngine` 类中新增以下静态方法：

| 方法 | 签名 | 说明 |
|------|------|------|
| `atr` | `atr(high, low, close, period=22) -> List[Optional[float]]` | 计算 ATR 序列 |
| `obv` | `obv(close, volume) -> List[float]` | 计算 OBV 序列（从 0 开始） |
| `calc_vpa_defender` | `calc_vpa_defender(bars, atr_period=22, atr_multi=3.0, obv_ma_period=20) -> Dict[str, List]` | 综合计算入口 |

**`calc_vpa_defender` 返回值**：
```python
{
    "stop_line": List[Optional[float]],   # ATR 动态防守线序列
    "obv":       List[float],             # OBV 序列
    "obv_ma20":  List[Optional[float]],   # OBV 平滑均线序列
    "signal":    List[Optional[int]],     # 四象限信号序列（1/2/3/4 或 None）
}
```

#### 4.5.2 集成到 `calculate_all`

- 在 `IndicatorEngine.calculate_all()` 中调用 `calc_vpa_defender(bars)` 并将结果存入 `IndicatorResult`
- `IndicatorResult` dataclass 新增 `VPA_DEFENDER` 字段：`VPA_DEFENDER: Dict[str, List] = field(default_factory=dict)`

#### 4.5.3 信号纳入综合信号

- VPA-Defender 的最新信号需要在 signals 字典中新增 `"VPA_DEFENDER"` 键
- 信号值映射：状态1 → `"bullish"`，状态2 → `"neutral"`（预警但未破位），状态3 → `"bearish"`，状态4 → `"neutral"`（观察区）
- **不影响现有综合信号（composite signal）的计算逻辑**——VPA-Defender 信号独立展示，不参与 `calc_composite_signal()` 函数

#### 4.5.4 API 响应扩展

**`GET /api/kline?code=...&period=...`** 响应的 `indicators` 字段新增：

```json
{
  "indicators": {
    "MA": {...},
    "BOLL": {...},
    "MACD": {...},
    "RSI": {...},
    "KDJ": {...},
    "MAVOL": {...},
    "VPA_DEFENDER": {
      "stop_line": [null, null, ..., 45.67, 46.12, ...],
      "obv":       [0, 100000, 250000, ...],
      "obv_ma20":  [null, null, ..., 180000, 195000, ...],
      "signal":    [null, null, ..., 1, 1, 2, 3, ...]
    }
  },
  "signals": {
    ...existing signals...,
    "VPA_DEFENDER": "bullish"
  }
}
```

**`GET /api/indicators`** 指标清单新增：
```json
{
  "name":   "VPA_DEFENDER",
  "label":  "量价共振防守",
  "type":   "panel",
  "params": {"atr_period": 22, "atr_multi": 3.0, "obv_ma_period": 20}
}
```

**`GET /api/kline` 的 `kline_service.py`** 中 `indicators` 字典新增 `"VPA_DEFENDER": indicator_result.VPA_DEFENDER`。

### 4.6 前端展示范围

#### 4.6.1 新增组件：`VPADefenderPanel.jsx`

**独立副图面板**，与 MACD / RSI / KDJ 平级，不与主图或其他副图共用画布。

**面板规格**（遵循迭代裁定规范）：

| 属性 | 值 |
|------|-----|
| 面板高度 | **200px**（与其他副图统一） |
| 画布类型 | ECharts 独立实例（非与主图共享） |
| 支持折叠 | 是（与 MACD/RSI/KDJ 折叠逻辑一致，localStorage 持久化） |
| forwardRef | 是（暴露 ECharts 实例给 useChartSync） |
| 禁止滚轮缩放 | 是（仅保留底部 slider dataZoom） |
| 配色引用 | `utils/colors.js` 统一配色 |

#### 4.6.2 面板内展示内容

**双 Y 轴布局**：
- 左 Y 轴：价格轴，绘制 **Stop_Line**（ATR 动态防守线）
- 右 Y 轴：OBV 轴，绘制 **OBV** 和 **OBV_MA20**

**三条曲线**：

| 曲线 | 颜色 | 线型 | 说明 |
|------|------|------|------|
| Stop_Line | 红色（`#ef5350`） | 实线，宽度 2px | ATR 动态防守线（只升不降） |
| OBV | 蓝色（`#42a5f5`） | 实线，宽度 1px | 原始 OBV 能量潮 |
| OBV_MA20 | 橙色（`#ffa726`） | 虚线（dashed），宽度 1px | OBV 20日平滑均线 |

**信号状态展示**：
- 在 X 轴区域绘制**背景色块条**（或底部色带），颜色对应当日信号状态（绿/黄/红/灰白），高度约 4px
- 面板标题行右侧显示**最新一日的信号标签**（如 `共振主升浪`），颜色与状态对应

**tooltip 悬停浮层**：
```
2026-03-21
防守线: 45.67
OBV: 2,350,000
OBV均线: 2,180,000
信号: 共振主升浪
```

#### 4.6.3 新手解释浮层

**遵循迭代4+裁定规范**：面板标题栏包含 **[?] 图标**，点击展开解释浮层，默认隐藏。

**浮层内容**（通俗语言，不含任何买卖操作指令）：

---

**VPA-Defender 量价共振防守指标**

这个指标帮助你同时观察"价格趋势"和"资金流向"两个维度：

**防守线（红色实线）**：基于价格波动幅度计算的动态参考线。它会随着价格创新高而自动上移，但绝不会下降。当价格跌破这条线时，意味着波动幅度已经超出了正常范围。

**OBV 能量潮（蓝色线）**：通过成交量的累计变化，观察资金的流入流出方向。当它持续上升时，说明伴随上涨的成交量大于伴随下跌的成交量。

**OBV 均线（橙色虚线）**：OBV 的 20 日平均值，用来过滤单日波动噪音，判断资金流向的中期趋势。

**四种状态含义**：
- 绿色（共振主升浪）：价格在防守线上方，且资金持续流入——量价配合良好
- 黄色（顶背离预警）：价格仍在防守线上方，但资金已开始流出——量价出现分歧
- 红色（破位警示）：价格跌破防守线——趋势可能发生变化
- 灰色（底部观察）：价格在防守线下方，但资金开始流入——可能正在酝酿变化

---

#### 4.6.4 页面集成

- **位置**：在 KDJ 副图下方新增 VPA-Defender 面板
- **折叠控制**：在现有副图折叠按钮组中新增 `VPA` 按钮，支持独立折叠/展开
- **useChartSync 集成**：新增 `vpaRef`，加入 `subRefs` 数组，参与跨图联动
- **折叠状态持久化**：`localStorage` 的折叠状态对象新增 `VPA` 键，默认展开

### 4.7 影响范围总览

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `core/indicator_engine.py` | 修改 | 新增 `atr()`、`obv()`、`calc_vpa_defender()` 方法 |
| `core/indicator_engine.py` | 修改 | `IndicatorResult` dataclass 新增 `VPA_DEFENDER` 字段 |
| `core/indicator_engine.py` | 修改 | `calculate_all()` 中集成 VPA-Defender 计算 |
| `api/services/kline_service.py` | 修改 | `indicators` 字典新增 `VPA_DEFENDER` |
| `api/routes/indicators.py` | 修改 | 指标清单新增 VPA_DEFENDER 条目 |
| `web/src/components/VPADefenderPanel.jsx` | **新增** | VPA-Defender 独立副图面板 |
| `web/src/pages/StockAnalysis.jsx` | 修改 | 集成 VPADefenderPanel、折叠控制、ref |
| `web/src/hooks/useChartSync.js` | 修改 | 新增 `vpaRef` 到联动链 |

---

## 5. 验收标准汇总

### 5.1 BUG-crosshair 验收

| # | 验收项 | 通过条件 |
|---|--------|---------|
| C-1 | 主图 hover → 副图联动 | 所有展开副图显示同日纵向虚线 + tooltip |
| C-2 | 副图 hover → 主图联动 | 主图显示同日纵向虚线 + tooltip |
| C-3 | 副图 hover → 其他副图联动 | 其他展开副图显示同日纵向虚线 + tooltip |
| C-4 | 纵线样式一致 | dashed、颜色 `#8b949e`、不被遮挡 |
| C-5 | 鼠标离开 → 全部隐藏 | 离开任意图表后所有 tooltip/纵线消失 |
| C-6 | 折叠后重建联动 | 折叠再展开副图，联动自动恢复 |
| C-7 | dataZoom 回归 | 滑动条双向联动不受影响 |

### 5.2 FEAT-vpa-defender 验收

| # | 验收项 | 通过条件 |
|---|--------|---------|
| V-1 | 后端 ATR 计算正确 | 对已知数据手工验算 ATR(22) 前 3 个有效值一致（误差 < 0.01） |
| V-2 | 后端 OBV 计算正确 | 对已知数据手工验算 OBV 前 5 个值完全一致 |
| V-3 | 后端 Stop_Line 只升不降 | 遍历返回的 stop_line 序列，确认非 None 值单调不减 |
| V-4 | 后端四象限信号正确 | 抽取 3~5 个 bar 手工验证信号与算法定义一致 |
| V-5 | API 响应包含 VPA_DEFENDER | `GET /api/kline?code=...&period=1D` 返回 `indicators.VPA_DEFENDER` 含 4 个子序列 |
| V-6 | API signals 包含 VPA_DEFENDER | `signals.VPA_DEFENDER` 返回有效值（bullish/bearish/neutral） |
| V-7 | 指标清单包含 VPA_DEFENDER | `GET /api/indicators` 返回列表中包含 `VPA_DEFENDER` 条目 |
| V-8 | 前端面板正常渲染 | VPADefenderPanel 在 KDJ 下方显示，高度 200px |
| V-9 | 三条曲线可见 | Stop_Line（红）、OBV（蓝）、OBV_MA20（橙虚线）均可见且数据正确 |
| V-10 | 信号色带/标签 | 面板底部或标题栏显示当日信号状态颜色和文字 |
| V-11 | tooltip 信息完整 | hover 显示防守线、OBV、OBV 均线、信号文字 |
| V-12 | 新手解释浮层 | [?] 图标可点击，浮层内容通俗、**不含任何买卖指令文字** |
| V-13 | 折叠/展开 | VPA 面板可独立折叠/展开，状态 localStorage 持久化 |
| V-14 | 跨图联动 | VPA 面板参与全局十字线联动和 dataZoom 联动 |
| V-15 | 不影响现有指标 | MACD/RSI/KDJ/MA/BOLL/MAVOL 指标数据和信号不变（回归） |
| V-16 | 不影响综合信号 | Watchlist 页面的 composite signal 计算逻辑不变 |

---

## 6. 约束与边界

1. **禁止交易指令**：所有信号描述、新手解释浮层中严禁出现"买入"、"卖出"、"持有"、"清仓"、"建仓"等投资操作指令词汇。信号仅描述市场状态观测。
2. **Stop_Line 不叠加主图**：防守线仅在 VPA-Defender 独立副图中展示，不绘制到主图 K 线画布上。
3. **不改数据库**：所有计算基于 `kline_data` 表现有字段（high / low / close / volume），无需新增表或列。
4. **参数暂不支持用户自定义**：ATR_Period=22、ATR_Multi=3.0、OBV_MA_Period=20 为硬编码默认值，后续迭代可考虑开放配置。
5. **综合信号独立**：VPA-Defender 信号不参与 `calc_composite_signal()` 函数计算，不影响 Watchlist 总览页的多空分组。

---

## 7. 非功能性要求

- **性能**：VPA-Defender 计算复杂度为 O(n)（n 为 bar 数量），与现有指标一致，不会显著增加 API 响应时间
- **向后兼容**：现有 API 消费者如果忽略 `VPA_DEFENDER` 字段，不受任何影响
- **浏览器兼容**：与现有前端一致（Chrome / Safari / Firefox 最新版）
