# 迭代7 测试方案（Test Plan）

**版本**: v7.0
**日期**: 2026-03-23
**编写**: QA 工程师
**覆盖范围**: BUG-crosshair（跨图十字线联动修复）+ FEAT-vpa-defender（量价共振复合指标）

---

## 1. 测试策略

| 层级 | 方法 | 工具 |
|------|------|------|
| 后端算法 | 单元测试 + 手工验算 | pytest / 手动计算 |
| API 接口 | 接口调用验证 | curl / 浏览器 /api/docs |
| 前端交互 | 手动测试 + 视觉检查 | Chrome DevTools |
| 回归 | 现有功能不受影响 | 手动 + API 对比 |

---

## 2. BUG-crosshair 测试用例

### TC-C1：主图 hover → 副图联动（验收 C-1）

| 项 | 内容 |
|----|------|
| 前置条件 | 打开个股分析页，MACD/RSI/KDJ 至少两个展开 |
| 操作 | 鼠标在主图 K 线区域左右移动 |
| 预期 | 所有展开副图同步显示同日纵向虚线 + 对应日期 tooltip |
| 额外检查 | 主图成交量区 hover 也能触发副图联动 |

### TC-C2：副图 hover → 主图联动（验收 C-2）

| 项 | 内容 |
|----|------|
| 前置条件 | 主图 + MACD/RSI/KDJ 均展开 |
| 操作 | 鼠标在 MACD 面板上左右移动 |
| 预期 | 主图（K 线区 + 成交量区）显示同日纵向虚线 + tooltip（含 OHLCV 数据） |
| 变体 | 分别在 RSI、KDJ 面板重复验证，确保每个副图都能触发主图联动 |

### TC-C3：副图 hover → 其他副图联动（验收 C-3）

| 项 | 内容 |
|----|------|
| 前置条件 | MACD + RSI + KDJ 全部展开 |
| 操作 | 鼠标在 MACD 面板移动 |
| 预期 | RSI 和 KDJ 面板均同步显示同日纵向虚线 + tooltip |
| 变体 | hover RSI → 检查 MACD + KDJ；hover KDJ → 检查 MACD + RSI |

### TC-C4：纵线样式验证（验收 C-4）

| 项 | 内容 |
|----|------|
| 操作 | hover 任意图表，观察纵向虚线样式 |
| 预期-样式 | 虚线 `type: 'dashed'` |
| 预期-颜色 | `#8b949e` |
| 预期-层级 | 纵线渲染在最顶层，不被 K 线蜡烛、成交量柱、MACD 柱等遮挡 |
| 验证方式 | Chrome DevTools 检查 canvas 渲染或 ECharts option 中 axisPointer 配置 |

### TC-C5：鼠标离开 → 全部隐藏（验收 C-5）

| 项 | 内容 |
|----|------|
| 操作-1 | 鼠标从主图移出到页面空白区域 |
| 预期-1 | 所有图表 tooltip 和纵线均消失 |
| 操作-2 | 鼠标从 MACD 副图移出到页面空白区域 |
| 预期-2 | 主图和其他副图 tooltip 和纵线均消失 |
| 操作-3 | 鼠标从一个副图快速移到另一个副图 |
| 预期-3 | 无残留 tooltip，新图表正常显示纵线 |

### TC-C6：折叠后重建联动（验收 C-6）

| 项 | 内容 |
|----|------|
| 操作-1 | 折叠 MACD 面板 |
| 操作-2 | hover RSI 面板 |
| 预期-2 | 主图 + KDJ 联动正常（MACD 已折叠，不参与） |
| 操作-3 | 展开 MACD 面板 |
| 操作-4 | hover MACD 面板 |
| 预期-4 | 主图 + RSI + KDJ 均联动（MACD 重新加入同步链） |
| 注意 | 无需刷新页面，全程操作 |

### TC-C7：dataZoom 回归验证（验收 C-7）

| 项 | 内容 |
|----|------|
| 操作-1 | 拖动主图底部 slider 缩放时间范围 |
| 预期-1 | 所有展开副图同步缩放 |
| 操作-2 | 拖动某副图底部 slider |
| 预期-2 | 主图和其他副图同步缩放 |
| 操作-3 | 连续快速拖动不同图表的 slider |
| 预期-3 | 无死循环卡顿，同步正确 |

### TC-C8：边界-仅展开一个副图

| 项 | 内容 |
|----|------|
| 前置 | 折叠 RSI + KDJ，仅保留 MACD 展开 |
| 操作 | hover MACD |
| 预期 | 主图联动正常，无报错 |

### TC-C9：边界-所有副图均折叠

| 项 | 内容 |
|----|------|
| 前置 | 折叠所有副图 |
| 操作 | hover 主图 |
| 预期 | 主图自身十字线正常，无 JS 报错（console 检查） |

---

## 3. FEAT-vpa-defender 后端测试用例

### 3.1 ATR 算法正确性

#### TC-V-ATR1：ATR 基本计算验证（验收 V-1）

**手工验算数据（5 根 bar，period=3 以简化验算）**：

```
Bar 0: H=12, L=10, C=11
Bar 1: H=13, L=10, C=12, TR = max(13-10, |13-11|, |10-11|) = max(3,2,1) = 3
Bar 2: H=14, L=11, C=13, TR = max(14-11, |14-12|, |11-12|) = max(3,2,1) = 3
Bar 3: H=13, L=10, C=10, TR = max(13-10, |13-13|, |10-13|) = max(3,0,3) = 3
Bar 4: H=11, L= 9, C= 9, TR = max(11-9, |11-10|, |9-10|) = max(2,1,1) = 2
```

| Bar | TR | ATR(3) |
|-----|-----|--------|
| 0 | - (第一根 TR 视实现而定) | None |
| 1 | 3 | None |
| 2 | 3 | SMA(TR[0..2], 3) — 取决于 bar 0 的 TR 定义 |
| 3 | 3 | 有效值 |
| 4 | 2 | 有效值 |

**验证点**：
- 前 `period - 1` 个位置为 None
- 从第 `period - 1` 个位置开始有有效浮点值
- 值与 SMA(TR, period) 手算一致（误差 < 0.01）

#### TC-V-ATR2：ATR 第一根 bar 的 close(i-1) 处理

| 项 | 内容 |
|----|------|
| 验证 | 第 0 根 bar 的 TR 计算是否使用 `close(0)` 自身作为 `close(i-1)` |
| 预期 | TR(0) = high(0) - low(0)（因为 |high-close| 和 |low-close| 均 ≤ high-low） |

#### TC-V-ATR3：ATR 数据不足

| 项 | 内容 |
|----|------|
| 输入 | bars 数量 < ATR_Period (22) |
| 预期 | 返回全 None 列表 |

### 3.2 OBV 算法正确性

#### TC-V-OBV1：OBV 基本计算（验收 V-2）

**手工验算数据**：

```
Bar 0: C=10, V=1000   → OBV = 0
Bar 1: C=11, V=2000   → 11>10 → OBV = 0 + 2000 = 2000
Bar 2: C=10, V=1500   → 10<11 → OBV = 2000 - 1500 = 500
Bar 3: C=10, V=3000   → 10==10 → OBV = 500
Bar 4: C=12, V=2500   → 12>10 → OBV = 500 + 2500 = 3000
```

**验证点**：
- OBV[0] == 0
- OBV[1] == 2000
- OBV[2] == 500
- OBV[3] == 500（close 不变时 OBV 不变）
- OBV[4] == 3000

#### TC-V-OBV2：OBV 单根 bar

| 项 | 内容 |
|----|------|
| 输入 | 仅 1 根 bar |
| 预期 | OBV = [0] |

#### TC-V-OBV3：OBV 所有 close 相同

| 项 | 内容 |
|----|------|
| 输入 | 5 根 bar，close 全为 10 |
| 预期 | OBV = [0, 0, 0, 0, 0] |

### 3.3 Stop_Line 算法正确性

#### TC-V-SL1：Stop_Line 只升不降（验收 V-3）

**验证方法**：对 API 返回的 `stop_line` 序列，遍历所有非 None 值，断言 `stop_line[i] >= stop_line[i-1]`。

#### TC-V-SL2：Stop_Line 计算逻辑

**手工验算（period=3, multi=2.0 简化）**：

```
假设前3根 bar 后 ATR=3.0
running_max_close = max(close[0..2]) = 13
Stop_Line(2) = 13 - 2.0 * 3.0 = 7.0
```

下一根 bar close=15，新的 running_max_close=15，ATR=2.5：
```
candidate = 15 - 2.0 * 2.5 = 10.0
Stop_Line(3) = max(7.0, 10.0) = 10.0 — 上升
```

下一根 bar close=12，running_max_close 仍=15，ATR=2.8：
```
candidate = 15 - 2.0 * 2.8 = 9.4
Stop_Line(4) = max(10.0, 9.4) = 10.0 — 保持不降
```

#### TC-V-SL3：Stop_Line 前 period-1 个为 None

| 项 | 内容 |
|----|------|
| 验证 | stop_line[:ATR_Period-1] 全为 None |
| 预期 | 前 21 个值为 None（ATR_Period=22） |

### 3.4 四象限信号正确性

#### TC-V-SIG1：信号判断逻辑（验收 V-4）

| 条件 | 预期信号 | 预期标签 |
|------|---------|---------|
| close=50, stop_line=45, obv=200, obv_ma=150 | 1 | 共振主升浪 |
| close=50, stop_line=45, obv=100, obv_ma=150 | 2 | 顶背离预警 |
| close=40, stop_line=45, obv=100, obv_ma=150 | 3 | 破位断头铡 |
| close=40, stop_line=45, obv=200, obv_ma=150 | 4 | 底背离吸筹 |

#### TC-V-SIG2：数据不足时信号为 None

| 项 | 内容 |
|----|------|
| 条件 | stop_line 或 obv_ma20 为 None（前 21 根 bar） |
| 预期 | signal[i] = None |

#### TC-V-SIG3：边界值 close == stop_line

| 项 | 内容 |
|----|------|
| 条件 | close == stop_line（恰好等于） |
| 预期 | 进入 `close <= stop_line` 分支（状态3或状态4） |

#### TC-V-SIG4：边界值 obv == obv_ma20

| 项 | 内容 |
|----|------|
| 条件 | OBV == OBV_MA20 且 close > stop_line |
| 预期 | 进入 `OBV <= OBV_MA20` 分支 → 信号 = 2（顶背离预警） |

### 3.5 calc_vpa_defender 综合测试

#### TC-V-CALC1：返回值结构

| 项 | 内容 |
|----|------|
| 验证 | 返回 dict 包含 4 个键：`stop_line`, `obv`, `obv_ma20`, `signal` |
| 验证 | 每个序列长度 == len(bars) |

#### TC-V-CALC2：空 bars 输入

| 项 | 内容 |
|----|------|
| 输入 | bars = [] |
| 预期 | 返回空结构，不抛异常 |

#### TC-V-CALC3：bars 数量恰好等于 ATR_Period

| 项 | 内容 |
|----|------|
| 输入 | 恰好 22 根 bar |
| 预期 | stop_line 最后一个位置有值，其余为 None |

### 3.6 IndicatorResult 集成

#### TC-V-IR1：VPA_DEFENDER 字段存在

| 项 | 内容 |
|----|------|
| 验证 | `IndicatorResult` dataclass 新增 `VPA_DEFENDER: Dict[str, List]` 字段，默认 `{}` |
| 验证 | `calculate_all()` 返回结果中 `VPA_DEFENDER` 包含 4 个子序列 |

#### TC-V-IR2：signals 包含 VPA_DEFENDER

| 项 | 内容 |
|----|------|
| 验证 | `indicator_result.signals` 包含 `"VPA_DEFENDER"` 键 |
| 映射 | 信号1 → "bullish"，信号2 → "neutral"，信号3 → "bearish"，信号4 → "neutral" |

#### TC-V-IR3：不影响 calc_composite_signal

| 项 | 内容 |
|----|------|
| 验证 | `calc_composite_signal()` 函数体未改动 |
| 验证 | 传入包含 VPA_DEFENDER 的 signals dict 时，composite 结果与不含时一致 |

---

## 4. FEAT-vpa-defender API 测试用例

### TC-V-API1：GET /api/kline 包含 VPA_DEFENDER（验收 V-5）

```bash
curl "http://localhost:8000/api/kline?code=HK.00700&period=1D"
```

| 验证项 | 预期 |
|--------|------|
| `indicators.VPA_DEFENDER` 存在 | 是 |
| `indicators.VPA_DEFENDER.stop_line` | List，长度 == bars 数量 |
| `indicators.VPA_DEFENDER.obv` | List，长度 == bars 数量 |
| `indicators.VPA_DEFENDER.obv_ma20` | List，长度 == bars 数量 |
| `indicators.VPA_DEFENDER.signal` | List，长度 == bars 数量 |

### TC-V-API2：GET /api/kline signals 包含 VPA_DEFENDER（验收 V-6）

| 验证项 | 预期 |
|--------|------|
| `signals.VPA_DEFENDER` | 值为 "bullish" / "bearish" / "neutral" 之一 |

### TC-V-API3：GET /api/indicators 包含 VPA_DEFENDER（验收 V-7）

```bash
curl "http://localhost:8000/api/indicators"
```

| 验证项 | 预期 |
|--------|------|
| indicators 列表中含 name="VPA_DEFENDER" 条目 | 是 |
| label = "量价共振防守" | 是 |
| type = "panel" | 是 |
| params 含 atr_period=22, atr_multi=3.0, obv_ma_period=20 | 是 |

### TC-V-API4：kline_service.py VPA_DEFENDER 透传

| 验证项 | 预期 |
|--------|------|
| `kline_service.py` 的 indicators dict 新增 `"VPA_DEFENDER": indicator_result.VPA_DEFENDER` | 代码检查 |

### TC-V-API5：无数据时 VPA_DEFENDER 不影响空响应

| 项 | 内容 |
|----|------|
| 输入 | code 对应股票无 K 线数据 |
| 预期 | 返回 `indicators: {}, signals: {}` 不报错 |

---

## 5. FEAT-vpa-defender 前端测试用例

### TC-V-FE1：面板正常渲染（验收 V-8）

| 项 | 内容 |
|----|------|
| 位置 | KDJ 副图下方 |
| 高度 | 200px（DevTools 验证） |
| 画布 | 独立 ECharts 实例 |

### TC-V-FE2：三条曲线可见（验收 V-9）

| 曲线 | 颜色 | 线型 | Y 轴 |
|------|------|------|------|
| Stop_Line | 红色 `#ef5350` | 实线 2px | 左 Y 轴（价格） |
| OBV | 蓝色 `#42a5f5` | 实线 1px | 右 Y 轴（OBV） |
| OBV_MA20 | 橙色 `#ffa726` | 虚线 1px | 右 Y 轴（OBV） |

### TC-V-FE3：信号色带/标签（验收 V-10）

| 项 | 内容 |
|----|------|
| 色带 | X 轴区域底部色带，颜色对应信号状态 |
| 颜色映射 | 绿=共振主升浪, 黄=顶背离预警, 红=破位警示, 灰白=底部观察 |
| 标签 | 面板标题行右侧显示最新信号文字，颜色匹配 |

### TC-V-FE4：tooltip 信息完整（验收 V-11）

| 项 | 内容 |
|----|------|
| 操作 | hover VPA-Defender 面板 |
| 预期内容 | 日期、防守线值、OBV 值、OBV 均线值、信号文字 |
| 格式 | 数值合理格式化（OBV 带千分位等） |

### TC-V-FE5：新手解释浮层（验收 V-12）

| 项 | 内容 |
|----|------|
| 触发 | 点击面板标题栏 [?] 图标 |
| 默认状态 | 隐藏 |
| 浮层内容 | 包含防守线/OBV/OBV均线/四种状态含义的通俗解释 |
| **禁止文字** | 不含"买入"、"卖出"、"持有"、"清仓"、"建仓"等投资指令词汇 |
| 关闭 | 可关闭/收起 |

### TC-V-FE6：折叠/展开（验收 V-13）

| 项 | 内容 |
|----|------|
| 按钮 | 副图折叠控制按钮组含 "VPA" 按钮 |
| 折叠 | 点击后面板折叠，仅显示标题栏 |
| 展开 | 再次点击后面板展开 |
| 持久化 | 刷新页面后折叠状态保留（localStorage 检查） |
| localStorage key | `quant_panel_collapse_state` 包含 `VPA` 键 |

### TC-V-FE7：跨图联动（验收 V-14）

| 项 | 内容 |
|----|------|
| 十字线-1 | hover VPA 面板 → 主图 + MACD/RSI/KDJ 同步纵线 + tooltip |
| 十字线-2 | hover 主图 → VPA 面板同步纵线 + tooltip |
| dataZoom | 拖动任意图表 slider → VPA 面板同步缩放；拖动 VPA slider → 其他图表同步 |
| 鼠标离开 | 离开 VPA 面板 → 所有图表 tooltip 消失 |

### TC-V-FE8：双 Y 轴布局

| 项 | 内容 |
|----|------|
| 左 Y 轴 | 价格单位，对应 Stop_Line |
| 右 Y 轴 | OBV 单位，对应 OBV + OBV_MA20 |
| 验证 | 两轴刻度独立，不互相干扰 |

### TC-V-FE9：禁止滚轮缩放

| 项 | 内容 |
|----|------|
| 操作 | 在 VPA 面板上滚动鼠标滚轮 |
| 预期 | 图表不缩放（无 `type: 'inside'` 的 dataZoom） |

---

## 6. 回归测试用例

### TC-REG1：MACD/RSI/KDJ 面板数据不变（验收 V-15）

| 项 | 内容 |
|----|------|
| 方法 | 对同一股票同一时间范围，对比迭代7前后 API 返回的 `indicators.MACD`/`RSI`/`KDJ` 数据 |
| 预期 | 数值完全一致 |

### TC-REG2：MA/BOLL/MAVOL 数据不变（验收 V-15）

| 项 | 内容 |
|----|------|
| 方法 | 对比 `indicators.MA`/`BOLL`/`MAVOL` |
| 预期 | 数值完全一致 |

### TC-REG3：现有 signals 不变（验收 V-15）

| 项 | 内容 |
|----|------|
| 方法 | 对比 `signals.BOLL`/`MACD`/`RSI`/`KDJ`/`MA`/`MAVOL` |
| 预期 | 完全一致（新增 `VPA_DEFENDER` 键不影响旧键） |

### TC-REG4：综合信号不变（验收 V-16）

| 项 | 内容 |
|----|------|
| 方法 | 访问 `/api/watchlist/summary`，对比每只股票的 `signals.composite` |
| 预期 | 完全一致 |
| 代码检查 | `calc_composite_signal()` 函数体未改动 |

### TC-REG5：现有面板视觉回归

| 项 | 内容 |
|----|------|
| 验证 | MACD/RSI/KDJ 面板高度仍为 200px，折叠/展开正常 |
| 验证 | 主图 K 线 + 成交量显示正常 |
| 验证 | 标记点开关功能正常 |

### TC-REG6：Watchlist 总览页回归

| 项 | 内容 |
|----|------|
| 验证 | Watchlist 页面加载正常 |
| 验证 | 多空分组逻辑不变（VPA_DEFENDER 不参与 composite） |

---

## 7. Code Review 检查清单

### 7.1 `core/indicator_engine.py` 新增方法

| 检查项 | 说明 |
|--------|------|
| `atr()` 签名 | `atr(high, low, close, period=22) -> List[Optional[float]]` |
| `atr()` 第一根 TR | 使用 close(0) 自身作为 close(i-1) |
| `atr()` 前 period-1 为 None | 边界正确 |
| `atr()` SMA 计算 | 使用简单移动平均，与 PRD 公式一致 |
| `obv()` 签名 | `obv(close, volume) -> List[float]` |
| `obv()` OBV(0)=0 | 初始值正确 |
| `obv()` 三分支 | close>prev: +vol, close<prev: -vol, close==prev: 不变 |
| `calc_vpa_defender()` 返回结构 | 4 个键，序列长度 == len(bars) |
| Stop_Line 只升不降 | 维护 running_max_close，取 max(prev_stop, new_stop) |
| 信号判断优先级 | close<=stop_line 时进入状态3/4 分支，而非状态1/2 |
| 信号映射 | 1→bullish, 2→neutral, 3→bearish, 4→neutral |
| `IndicatorResult` 新字段 | `VPA_DEFENDER: Dict[str, List] = field(default_factory=dict)` |
| `calculate_all()` 集成 | 调用 `calc_vpa_defender(bars)` 并存入结果 |
| 无副作用 | 所有方法纯函数，无 IO，无数据库写入 |
| 无交易指令 | 注释和文档中无买卖操作指令词汇 |

### 7.2 `web/src/components/VPADefenderPanel.jsx`

| 检查项 | 说明 |
|--------|------|
| forwardRef | 使用 `React.forwardRef` 暴露 ECharts 实例 |
| 面板高度 | 200px |
| 双 Y 轴 | 左轴价格（Stop_Line），右轴 OBV |
| 三条曲线配色 | Stop_Line=#ef5350, OBV=#42a5f5, OBV_MA20=#ffa726(dashed) |
| 信号色带 | 底部 4px 色带，颜色映射正确 |
| 最新信号标签 | 标题栏右侧，颜色匹配 |
| [?] 浮层 | 默认隐藏，点击展开，内容通俗 |
| **禁止文字检查** | 浮层中不含"买入""卖出""持有""清仓""建仓" |
| 无滚轮缩放 | dataZoom 无 `type: 'inside'` |
| tooltip 格式 | 日期+防守线+OBV+OBV均线+信号 |
| 折叠逻辑 | 与 MACD/RSI/KDJ 面板一致 |
| 配色引用 | 使用 `utils/colors.js` 统一配色 |

### 7.3 `web/src/hooks/useChartSync.js`

| 检查项 | 说明 |
|--------|------|
| vpaRef 加入 subRefs | VPA ref 参与联动链 |
| 副图 → 主图联动 | 所有副图注册 `updateAxisPointer` 事件，反向 dispatchAction 到主图 |
| 副图 → 副图联动 | 任意副图 hover 时广播到其他副图 |
| mouseleave 注册 | 所有图表 DOM 注册 mouseleave，广播 hideTip |
| 互斥标志 | 十字线同步使用 syncing 标志防止循环触发 |
| dataZoom 不受影响 | 现有 dataZoom 双向联动代码逻辑不变或兼容 |
| cleanup 完整 | 所有事件监听器在 cleanup 中正确移除 |
| collapsed 依赖 | VPA 折叠状态变化时 effect 重新执行 |

---

## 8. 测试执行优先级

| 优先级 | 测试范围 | 说明 |
|--------|---------|------|
| P0 | TC-C1~C7 | BUG-crosshair 是交互修复，必须优先验证 |
| P0 | TC-V-ATR1, TC-V-OBV1, TC-V-SL1, TC-V-SIG1 | 核心算法正确性 |
| P1 | TC-V-API1~API3 | API 接口验证 |
| P1 | TC-V-FE1~FE7 | 前端面板验证 |
| P1 | TC-REG1~REG6 | 回归验证 |
| P2 | 边界用例 (TC-C8~C9, TC-V-ATR3, TC-V-OBV2~3, TC-V-SIG2~4) | 边界条件 |
| CR | 7.1~7.3 | Code Review（Dev 代码完成后执行） |
