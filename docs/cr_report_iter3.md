# 迭代3 Code Review 报告

**日期**：2026-03-18
**Reviewer**：QA
**Review 范围**：I1~I10 全部模块（IndicatorEngine / API / 前端面板 / B-1 修复 / adjustment_service 遗留修复）
**PRD 版本**：requirements_iter3.md v3.1
**设计文档**：design_iter3.md v1.0

---

## P0（必须修复，阻塞发布）

> 本次 CR 未发现 P0 级问题。

---

## P1（应当修复，影响功能正确性）

### [P1-01] `adjustment_service.py`：`_mark_adjusted` 丢失 `pb_ratio` / `ps_ratio` 字段

- **文件**：`core/adjustment_service.py` L140–158
- **问题描述**：
  Dev 已在 `_apply_adjustment`（L111–137）中补全了 `pb_ratio` 和 `ps_ratio` 字段的传递，但同文件内的 `_mark_adjusted` 方法（无复权事件时调用路径）**仍缺少这两个字段**。

  ```python
  # _mark_adjusted（当前代码）
  return KlineBar(
      ...
      pe_ratio=bar.pe_ratio,
      # pb_ratio=bar.pb_ratio  ← 缺失！
      # ps_ratio=bar.ps_ratio  ← 缺失！
      turnover_rate=bar.turnover_rate,
      ...
  )
  ```

  由于 `KlineBar` dataclass 定义了 `pb_ratio: Optional[float] = None` / `ps_ratio: Optional[float] = None`，未传参时默认 `None`，导致对**无复权事件的股票**（如尚未经历过拆送股/分红的新股，或美股新上市标的），`/api/kline` 响应中 `bars[i].pb_ratio` 和 `bars[i].ps_ratio` 会错误地返回 `null`，即使数据库中已有有效数值。

- **影响范围**：`/api/kline` 的 bars 数据、`/api/watchlist/summary` 中 `pb_ratio` 字段，以及底部信息条 PB 显示。PRD §5.2 明确要求 `pb_ratio` 和 `ps_ratio` 字段。
- **修复建议**：在 `_mark_adjusted` 中补全这两个字段：
  ```python
  pb_ratio=bar.pb_ratio,
  ps_ratio=bar.ps_ratio,
  ```

---

## P2（建议优化，不阻塞发布）

### [P2-01] `RSIPanel.jsx`：`visualMap` 对一维数据配置了 `dimension: 1` 可能不生效

- **文件**：`web/src/components/RSIPanel.jsx` L52–65
- **问题描述**：
  代码中配置了一个 `visualMap`（`type: 'piecewise'`，`dimension: 1`），意图根据 RSI 值对折线进行分段着色（超买红/中性蓝/超卖绿）。然而，RSI series 数据为一维标量数组，ECharts 中 `dimension: 1` 会尝试访问每个数据点的第二个维度（即 `[x, y]` 格式中的 y），一维数组无此维度，分段着色不会生效。

  ```jsx
  visualMap: [{
    type: 'piecewise',
    dimension: 1,     // 一维数据不存在 dimension 1
    seriesIndex: 0,
    pieces: [...]
  }]
  ```

  **注意**：PRD 要求的区间背景色已通过 `markArea` 正确实现（L72–88），功能验收点已满足。此 P2 仅影响 RSI 折线本身的分段颜色，不影响背景区域着色。

- **修复建议**：如需折线分段着色，需将 series data 改为 `[[index, value], ...]` 格式并保持 `dimension: 1`；或移除此 `visualMap`（markArea 已满足 PRD 要求），改为统一单色折线。

---

### [P2-02] `KDJPanel.jsx`：markArea 超买/超卖边界超出 PRD 规定范围

- **文件**：`web/src/components/KDJPanel.jsx` L87–101
- **问题描述**：
  PRD §4.2 及验收标准 §11 第6条明确："KDJ 面板 80~100 区域为浅红背景，0~20 为浅绿背景"。
  当前实现为：
  - 超买区：`yAxis: 80` → `yAxis: 110`（超出到 110，超出 PRD 上界 100）
  - 超卖区：`yAxis: -10` → `yAxis: 20`（下界为 -10，超出 PRD 下界 0）

  Y 轴范围设为 `[-10, 110]` 以容纳 J 值超出 [0, 100] 的情况是合理的，但 "超买" 背景色语义上应标注 80~100，而非 80~110；"超卖" 背景色应标注 0~20，而非 -10~20。目前 J 值超出 100 的区域被标红但并非 KDJ 超买定义范围，可能造成视觉误导。

- **修复建议**：将 markArea 边界改回：
  ```jsx
  // 超买区：80 ~ 100
  [{ yAxis: 80, ... }, { yAxis: 100 }]
  // 超卖区：0 ~ 20
  [{ yAxis: 0, ... }, { yAxis: 20 }]
  ```
  Y 轴 `min: -10, max: 110` 保持不变，J 值仍能完整显示。

---

### [P2-03] `indicator_engine.py`：BOLL 使用总体标准差（ddof=0），与部分参考平台（TradingView）有微小偏差

- **文件**：`core/indicator_engine.py` L172
- **问题描述**：
  ```python
  variance = sum((x - avg) ** 2 for x in window) / n  # 总体标准差
  ```
  代码使用总体标准差（除以 n），与 Wind、同花顺、通达信等 A 股主流行情平台保持一致，**符合国内量化惯例**。但 TradingView 等平台默认使用样本标准差（除以 n-1），与上述平台结果有微小偏差。

- **建议**：维持现状（总体标准差）。在代码注释中补充说明：
  ```python
  # 使用总体标准差（ddof=0），与 Wind/通达信/同花顺保持一致
  # TradingView 默认使用样本标准差（ddof=1），如对标请修改为 / (n-1)
  ```

---

## 通过项（明确列出已通过的关键检查点）

### 1. IndicatorEngine 计算公式验证

| 指标 | 检查点 | 结论 |
|------|--------|------|
| MA | `sum(close[i-n:i]) / n`，前 n-1 个为 None | ✅ 通过 |
| EMA | `k = 2/(n+1)`，种子值 = MA(n) 算术均值 | ✅ 通过 |
| MACD | DIF=EMA(12)-EMA(26)，DEA 种子=首9个DIF算术均值，MACD柱=(DIF-DEA)×2 | ✅ 通过 |
| BOLL | 中轨=MA(20)，上下轨=中轨±2×STD(20)（总体标准差） | ✅ 通过（P2-03 注） |
| RSI | Wilder 平滑 `(avg*(n-1)+gain)/n`，`result[n]` 索引正确，前n位为None | ✅ 通过 |
| KDJ | 初始 K=D=50，RSV公式正确，K/D 平滑系数 2/3:1/3 | ✅ 通过 |
| MAVOL | MA(volume, n) for n in [5,10,20] | ✅ 通过 |

### 2. 信号判断逻辑（逐条对照 PRD §4.2）

| 指标 | 信号条件 | 结论 |
|------|--------|------|
| BOLL | price>upper→BEARISH，price<lower→BULLISH | ✅ 通过 |
| MACD | 金叉→BULLISH，死叉→BEARISH，持续方向正确 | ✅ 通过 |
| RSI | >70→BEARISH，<30→BULLISH，30~70→NEUTRAL | ✅ 通过 |
| KDJ | K>D且K<20→BULLISH，K<D且K>80→BEARISH，其余NEUTRAL | ✅ 通过 |
| MA | MA5>MA20>MA60→BULLISH，MA5<MA20<MA60→BEARISH | ✅ 通过 |
| MAVOL | vol>mavol5×1.5→VOLUME_HIGH，vol<mavol5×0.5→VOLUME_LOW | ✅ 通过 |

### 3. 综合信号判断（Watchlist 总览页，PRD §4.3）

```
偏多：MACD==bullish AND 50≤RSI≤70 AND KDJ!=bearish  ✅ 通过
偏空：MACD==bearish AND RSI<50 AND KDJ!=bullish      ✅ 通过
其余：neutral                                          ✅ 通过
```

### 4. API 响应结构（PRD §5.2）

- `/api/kline` 响应含 `stock_code / period / adj_type / bars / indicators / signals` ✅
- `bars` 含 `date / open / high / low / close / volume / turnover / pe_ratio / pb_ratio / ps_ratio` ✅（P1-01 仅影响无复权因子股票）
- `indicators` 含 PRD §5.2 全部字段，设计文档扩展了 `MAVOL` ✅
- `signals` 对象为设计文档扩展，结构与设计文档一致 ✅

### 5. 只读约束

- 全局 `grep` 对 `api/` 目录执行 `INSERT|UPDATE|DELETE` 搜索，**结果为空** ✅
- `kline_service.py` 注释明确："严格只读：不调用任何 Repository 写入方法" ✅
- 前复权通过 `AdjustmentService.get_adjusted_klines()` 透传，不写库 ✅

### 6. B-1 修复（main.py）

- `_is_connection_error()` 函数 L47–60 使用 `isinstance(e, (ConnectionError, TimeoutError, OSError))` 优先判断 ✅
- 字符串关键词匹配作为 fallback（应对富途 SDK 包装通用 Exception 的情况）✅
- `rate_limiter.py` 已有 `type(e).__name__` 检测，B-1 修复主要聚焦 main.py，符合设计文档说明 ✅

### 7. 前端核心功能

- RSI 区间背景：70~100 浅红（markArea），0~30 浅绿（markArea），含30/70参考线 ✅
- KDJ 区间背景：80~100 浅红（markArea），0~20 浅绿（markArea），含20/80参考线 ✅（边界见 P2-02）
- MACD 金叉▲/死叉▼交叉点标记（markPoint）✅
- KDJ 金叉/死叉交叉点标记（markPoint）✅
- 信号标签颜色：`SignalTag` 组件 `COLOR_MAP` 绿/红/灰/橙映射正确 ✅
- 60 秒自动刷新：`setInterval(loadData, 60_000)` in `StockAnalysis.jsx` L76–78 ✅
- Watchlist 总览页信号列颜色、综合信号、行点击跳转 ✅

### 8. 迭代2遗留修复（pb_ratio/ps_ratio）

- `_apply_adjustment` 已补充 `pb_ratio=bar.pb_ratio` / `ps_ratio=bar.ps_ratio` ✅
- 注：`_mark_adjusted` 仍有遗漏，见 P1-01

---

## 总结

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 | 0 | 无阻塞发布问题 |
| P1 | 1 | `_mark_adjusted` 缺失 pb_ratio/ps_ratio，影响无复权因子股票的 API 数据正确性 |
| P2 | 3 | visualMap 一维数据配置、KDJ markArea 边界超范围、BOLL STD 类型说明 |

**建议**：修复 P1-01 后即可发布。P2 建议在本迭代内一并处理（改动量极小），P2-03 仅需补充注释。

---

---

## 复查记录（v1.1）

**复查日期**：2026-03-18
**复查结论**：全部 P1/P2 问题已正确修复，复查通过。

| 编号 | 修复内容 | 复查结论 |
|------|--------|--------|
| P1-01 | `_mark_adjusted` 补充 `pb_ratio=bar.pb_ratio, ps_ratio=bar.ps_ratio` | ✅ 已确认，两条复权路径现在完全对称 |
| P2-01 | `RSIPanel.jsx` 整个 `visualMap` 段落已移除 | ✅ 已确认，代码干净，无冗余配置 |
| P2-02 | `KDJPanel.jsx` markArea 超买上界 `110→100`，超卖下界 `-10→0` | ✅ 已确认，符合 PRD 80~100 / 0~20 规范 |
| P2-03 | `indicator_engine.py` L172 添加注释 `# 总体标准差（国内布林带惯例）` | ✅ 已确认 |

**最终结论：迭代3代码复查通过，可进入产品验收阶段。**

---

*CR 报告 v1.1，2026-03-18，QA（v1.0 初版 → v1.1 复查通过）*
