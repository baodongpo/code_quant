# 迭代8.1-patch 测试用例文档

**文档版本**：v1.0
**日期**：2026-03-24
**作者**：QA
**基于需求**：requirements_iter8.md v1.3 §七（FEAT-resistance）、§八（FEAT-legend-toggle）
**测试范围**：空仓阻力线指标 + 图例按钮化交互

---

## 一、概述

### 1.1 迭代8.1-patch 变更范围

| 功能点 ID | 类型 | 简述 | 影响文件 |
|-----------|------|------|---------|
| FEAT-resistance | FEAT | VPA 副图新增空仓阻力线（橙黄曲线，只降不升） | `core/indicator_engine.py`、`api/services/kline_service.py`（透传自动生效）、`web/src/components/VPADefenderPanel.jsx` |
| FEAT-legend-toggle | FEAT | ChartSidebar 图例条目升级为可交互按钮，点击切换 ECharts series 显隐 | `web/src/components/ChartSidebar.jsx`、`web/src/pages/StockAnalysis.jsx`、`web/src/components/MACDPanel.jsx`、`web/src/components/RSIPanel.jsx`、`web/src/components/KDJPanel.jsx`、`web/src/components/VPADefenderPanel.jsx` |

### 1.2 测试策略说明

1. **测试分层**：
   - **代码审查（静态）**：算法实现、数据结构字段定义、seriesName 映射关系，通过阅读源码确认
   - **浏览器人工验收（Runtime）**：视觉效果、交互行为、ECharts 曲线显隐，需在浏览器中实际操作
   - **DevTools 辅助**：Network 面板验证 API 响应字段；Console 监控 JS 报错；Elements 面板取色

2. **Dev 关键实现细节（测试时须特别关注）**：
   - **API 透传**：`kline_service.py` 使用整体字典透传（`indicator_result.VPA_DEFENDER`），新字段 `resistance_line` 自动包含在响应中，**无需额外修改透传逻辑**
   - **切换股票重置**：ChartSidebar 通过 `key={xxx-sidebar-${code}}` 实现，切换股票时组件重新挂载，`activeMap` 自动重置为全 active
   - **折叠展开 inactive 同步**：`togglePanel` 展开时有 `setTimeout(80ms)` 后重新调用 `dispatchAction`，确保 ECharts 实例稳定后再恢复 inactive 状态

3. **执行顺序**：FEAT-resistance（后端→API→前端）→ FEAT-legend-toggle（各面板→交叉场景→回归）

4. **回归重点**：VPA 折叠展开正常、crosshair 十字线联动不受影响、防守线显示不受阻力线影响

---

## 二、FEAT-resistance 测试用例

### 2.1 后端算法验证

> **验证方式**：代码审查 + 可选 Python REPL 单元测试

---

**TC-resistance-BE-01**：`running_min_close` 只降不升特性

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `running_min_close` 在迭代过程中只追踪历史最低收盘价，遇到更低价格下移，遇到更高价格时保持不变 |
| 验证方式 | **代码审查** |
| 审查要点 | 在 `core/indicator_engine.py` 的 `calc_vpa_defender` 方法中，找到阻力线计算段：<br>1. 确认存在 `running_min_close = close[0]` 初始化语句<br>2. 确认循环体内使用 `running_min_close = min(running_min_close, close[i])`（而非 `max`）<br>3. 对比防守线使用 `running_max_close = max(...)`，两者互为镜像 |
| 预期结果 | 代码中 `running_min_close` 使用 `min()` 更新，确保只降不升 |
| 失败判定 | 使用了 `max()` 更新 `running_min_close`；或与防守线逻辑混淆 |

---

**TC-resistance-BE-02**：候选值计算公式正确

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证阻力线候选值 = `running_min_close + atr_multi × ATR[i]`，是防守线公式的对称镜像 |
| 验证方式 | **代码审查** |
| 审查要点 | 找到阻力线 candidate 计算行：<br>1. 公式为 `candidate = running_min_close + atr_multi * atr_series[i]`（加号，而非防守线的减号）<br>2. 使用相同参数 `atr_multi=3.0`，无新增参数<br>3. ATR 序列复用已有 `atr_series`，未重复计算 ATR |
| 预期结果 | 候选值公式为加法，复用 `atr_multi` 和 `atr_series`，无新增参数 |
| 失败判定 | 公式使用减号；或重复计算了 ATR；或引入了新的参数变量 |

---

**TC-resistance-BE-03**：`resistance_line` 只降不升约束

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证约束逻辑：`resistance_line[i]` 若大于上一根值，则保持上一根值（"只降不升"） |
| 验证方式 | **代码审查** |
| 审查要点 | 在约束循环中（通常紧跟 candidate 计算段）：<br>1. 确认判断条件为 `if resistance_line[i] > resistance_line[i-1]`（大于时回退，而非防守线的小于时回退）<br>2. 确认赋值为 `resistance_line[i] = resistance_line[i-1]`（保持上一根）<br>3. 确认约束循环从 `range(1, size)` 开始（第0根无需约束）<br>4. 确认仅在两者均非 None 时执行约束 |
| 预期结果 | 约束逻辑为"候选值上涨则回退到上一根值"，与防守线"候选值下降则回退"完全对称 |
| 失败判定 | 约束条件方向错误（用 `<` 代替 `>`）；或 None 值处理缺失 |

---

**TC-resistance-BE-04**：ATR 数据不足时返回 `None`（前期空值填充）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 ATR 计算期（前 `atr_period=22` 根）`resistance_line` 对应位置为 `None`，不产生异常值 |
| 验证方式 | **代码审查 + 可选 Python REPL** |
| 审查要点 | 1. candidate 计算前有 `if atr_series[i] is not None:` 条件守卫<br>2. `resistance_line` 初始化为 `[None] * size`，前期未被赋值位置保持 `None` |
| REPL 验证步骤 | ```python<br>from core.indicator_engine import IndicatorEngine<br>from models.kline import KlineBar<br># 构造少于 22 根的 bars（模拟数据不足场景）<br>bars = [KlineBar(trade_date=f'2024-01-{i+1:02d}', open=10, high=10.5, low=9.5, close=10+i*0.1, volume=1000) for i in range(10)]<br>result = IndicatorEngine.calc_vpa_defender(bars)<br>print(result['resistance_line'])  # 期望全为 None<br>``` |
| 预期结果 | `resistance_line` 序列前 22 根为 `None`，首个非 None 值出现在第 22 根之后 |
| 失败判定 | 前期出现非 None 的数值；或出现 `NaN`、`Infinity` 等异常浮点值 |

---

**TC-resistance-BE-05**：返回字典包含 `resistance_line` 字段

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `calc_vpa_defender` 返回字典新增 `"resistance_line"` 键，原有四个键不受影响 |
| 验证方式 | **代码审查 + 可选 Python REPL** |
| 审查要点 | 方法末尾 `return` 语句中：<br>1. 包含 `"resistance_line": resistance_line`（新增）<br>2. 原有 `"stop_line"`、`"obv"`、`"obv_ma20"`、`"signal"` 四个键仍存在<br>3. 键的顺序不影响功能，但字段名拼写须正确（`resistance_line` 全小写下划线） |
| REPL 验证步骤 | ```python<br>result = IndicatorEngine.calc_vpa_defender(bars)  # 使用足够长的 bars<br>assert 'resistance_line' in result<br>assert 'stop_line' in result      # 原有字段不受影响<br>assert len(result['resistance_line']) == len(bars)<br>``` |
| 预期结果 | 返回字典有 5 个键：`stop_line`、`obv`、`obv_ma20`、`signal`、`resistance_line`；`resistance_line` 长度与 bars 一致 |
| 失败判定 | 缺少 `resistance_line` 键；或原有键被误删 |

---

**TC-resistance-BE-06**：`resistance_line` 数值合理性（阻力线多数情况在防守线上方）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证阻力线与防守线的上下关系：在价格震荡上涨区间，阻力线（追踪历史最低价上方）多数时候应高于防守线（追踪历史最高价下方） |
| 验证方式 | **可选 Python REPL（需真实数据库数据）** |
| REPL 验证步骤 | ```python<br>from config.settings import DB_PATH<br>from db.repositories.kline_repo import KlineRepository<br>from core.indicator_engine import IndicatorEngine<br>repo = KlineRepository(DB_PATH)<br>bars = repo.get_bars('HK.00700', '1D', '2023-01-01', '2024-01-01')<br>result = IndicatorEngine.calc_vpa_defender(bars)<br>r = result['resistance_line']<br>s = result['stop_line']<br>pairs = [(r[i], s[i]) for i in range(len(r)) if r[i] is not None and s[i] is not None]<br>above_count = sum(1 for ri, si in pairs if ri > si)<br>print(f"阻力线 > 防守线 占比: {above_count/len(pairs)*100:.1f}%")  # 期望 > 50%<br>``` |
| 预期结果 | 在趋势稳定的历史数据中，`resistance_line > stop_line` 的比例显著高于 50%，形成"上有阻力、下有支撑"的通道效果 |
| 备注 | 本用例为合理性验证，非严格边界断言。若比例偏低，需检查算法参数或数据质量 |

---

**TC-resistance-BE-07**：`resistance_line` 类型与 `stop_line` 格式一致

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `resistance_line` 序列中每个元素为 `float` 或 `None`，无字符串、整数或 NaN |
| 验证方式 | **代码审查 + 可选 REPL** |
| 审查要点 | 1. 赋值语句为 `resistance_line[i] = round(candidate, 6)`（带 `round` 保留6位小数，与 `stop_line` 相同精度）<br>2. 无类型转换错误（如 `str(...)` 包裹）|
| REPL 验证步骤 | ```python<br>non_none = [v for v in result['resistance_line'] if v is not None]<br>assert all(isinstance(v, float) for v in non_none), "存在非 float 元素"<br>import math<br>assert all(not math.isnan(v) for v in non_none), "存在 NaN 值"<br>``` |
| 预期结果 | 所有非 None 元素为 `float` 类型，无 NaN/Infinity |
| 失败判定 | 出现非 float 类型值、NaN 或 Infinity |

---

### 2.2 API 透传验证

> **验证方式**：浏览器 Network 面板或 curl 命令

---

**TC-resistance-API-01**：API 响应中 `resistance_line` 字段存在

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `/api/kline` 响应中 `indicators.VPA_DEFENDER` 字典包含 `resistance_line` 字段 |
| 验证方式 | **Runtime — Network 面板 / curl** |
| 操作步骤 | **方法A（浏览器 DevTools）**：<br>1. 打开 StockAnalysis 页面，选择任意股票<br>2. 打开 DevTools → Network 面板<br>3. 刷新或切换股票，找到 `/api/kline?code=...` 请求<br>4. 查看 Response → `indicators` → `VPA_DEFENDER` 对象<br>5. 确认包含 `resistance_line` 键<br><br>**方法B（curl）**：<br>`curl "http://localhost:8000/api/kline?code=HK.00700&period=1D" \| python3 -m json.tool \| grep -A2 "resistance_line"` |
| 预期结果 | `indicators.VPA_DEFENDER.resistance_line` 为 JSON 数组，元素为数值或 `null` |
| 失败判定 | 响应中 `VPA_DEFENDER` 无 `resistance_line` 键；或字段拼写错误（如 `resistanceLine`）|

---

**TC-resistance-API-02**：`resistance_line` 与 `stop_line` 格式完全一致

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `resistance_line` 数组长度、null 分布与 `stop_line` 格式保持一致 |
| 验证方式 | **Runtime — Network 面板 / curl** |
| 操作步骤 | 1. 获取 `/api/kline` 完整响应<br>2. 取出 `indicators.VPA_DEFENDER.stop_line` 和 `indicators.VPA_DEFENDER.resistance_line` 两个数组<br>3. 在 Console 中运行：<br>```js<br>const vpa = response.indicators.VPA_DEFENDER<br>console.log('stop_line长度:', vpa.stop_line.length)<br>console.log('resistance_line长度:', vpa.resistance_line.length)<br>console.log('stop_line前25个:', vpa.stop_line.slice(0,25))<br>console.log('resistance_line前25个:', vpa.resistance_line.slice(0,25))<br>``` |
| 预期结果 | - `resistance_line` 与 `stop_line` 数组长度相同（等于 `bars` 数组长度）<br>- 前期（约前22根）两者均为 `null`<br>- 非 null 元素均为浮点数，无字符串 |
| 失败判定 | 两数组长度不一致；或 `resistance_line` 元素类型与 `stop_line` 不一致 |

---

**TC-resistance-API-03**：原有 VPA 字段不受影响（回归）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证新增 `resistance_line` 字段后，原有 `stop_line`、`obv`、`obv_ma20`、`signal` 字段仍正常存在且数值未变化 |
| 验证方式 | **代码审查 + Runtime Network 面板** |
| 操作步骤 | 1. 查看 API 响应，确认 `indicators.VPA_DEFENDER` 包含全部5个字段<br>2. 对比迭代前后（若有记录）`stop_line` 数值，确认未因引入 `resistance_line` 计算而改变 |
| 预期结果 | `VPA_DEFENDER` 对象含：`stop_line`、`obv`、`obv_ma20`、`signal`、`resistance_line` 五个字段，缺一不可 |
| 失败判定 | 原有任意字段消失；或 `stop_line` 数值与迭代前不一致 |

---

### 2.3 前端渲染验证

> **验证方式**：浏览器 Runtime 人工验收

#### 前置条件

- 前端开发服务器已启动，VPA-Defender 副图正常显示
- watchlist 中至少有一只历史数据超过 60 根的股票（确保阻力线有足够数据）
- VPA-Defender 副图处于**展开状态**

---

**TC-resistance-FE-01**（对应 AC-resistance-1）：橙黄阻力线在 VPA 副图左 Y 轴显示

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 VPA 副图左 Y 轴新增橙黄色阻力线曲线，与蓝色防守线、灰色收盘价共三条曲线同轴显示 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 打开 StockAnalysis 页面，选择历史数据充足的股票（如 HK.00700）<br>2. 展开 VPA-Defender 副图<br>3. 观察副图左 Y 轴价格区域中的曲线数量和颜色：<br>   - 灰色细线（收盘价）<br>   - 蓝色实线（防守线）<br>   - **橙黄色实线（阻力线，新增）** |
| 预期结果 | 左 Y 轴显示**三条**曲线：灰色收盘价 + 蓝色防守线 + 橙黄色阻力线。右 Y 轴仍显示 OBV 相关曲线，不受影响 |
| 失败判定 | 找不到橙黄色曲线；或橙黄曲线绑定到右 Y 轴（OBV 轴）而非左 Y 轴 |

---

**TC-resistance-FE-02**（对应 AC-resistance-2）：阻力线"只降不升"视觉验证

| 项目 | 内容 |
|------|------|
| 测试目的 | 视觉验证阻力线在价格持续下跌阶段随之下移，在价格反弹时保持水平不上升 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 选择一只近期经历明显下跌后反弹的股票<br>2. 找到下跌阶段对应的阻力线走势：应随价格下移<br>3. 找到下跌后价格反弹阶段：阻力线应保持水平（不随价格上涨而上移）<br>4. 对比防守线（只升不降）与阻力线（只降不升）的走势特征 |
| 预期结果 | - 价格创新低时：阻力线下移<br>- 价格反弹时：阻力线保持水平（"只降不升"特性可见）<br>- 与防守线"只升不降"形成视觉上的对称趋势 |
| 失败判定 | 阻力线在价格反弹时也跟随上升（说明约束逻辑错误）；或阻力线与防守线走势相同（说明数据计算混淆）|

---

**TC-resistance-FE-03**（对应 AC-resistance-3）：阻力线与防守线"上下夹击"通道形态

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证多数情况下防守线在下、阻力线在上，形成价格通道 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 选择一只历史数据较长的股票（建议 1 年以上日K数据）<br>2. 展开 VPA 副图，观察阻力线（橙黄）和防守线（蓝色）的相对位置<br>3. 调整 dataZoom 到不同时间段，检查通道是否持续 |
| 预期结果 | 在股票历史价格运行期间，大多数时段橙黄阻力线位于蓝色防守线**上方**，形成视觉通道效果；极少数极端区间（如剧烈崩盘）可能出现交叉 |
| 失败判定 | 阻力线长期位于防守线下方（说明算法对称性错误） |

---

**TC-resistance-FE-04**（对应 AC-resistance-4）：hover tooltip 显示"阻力线"数值

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证鼠标悬停时 tooltip 显示阻力线当日数值，标注为"阻力线" |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 鼠标悬停在 VPA 副图的图表区<br>2. 观察弹出的 tooltip 内容<br>3. 在阻力线有数值的位置（非前期 null 区域）验证 |
| 预期结果 | tooltip 中出现"阻力线: xxx.xx"格式的文字（具体数值为当日计算值），标签为"阻力线" |
| 失败判定 | tooltip 中无阻力线数值条目；或标签错误（如"resistance_line"英文字段名） |

---

**TC-resistance-FE-05**（对应 AC-resistance-4 补充）：tooltip 前期 null 区间不显示阻力线

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 ATR 计算期（前 22 根，阻力线为 null）对应位置的 tooltip 不显示阻力线数值 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 将 dataZoom 调整到数据最早期区间<br>2. 鼠标悬停在前 22 根 K 线对应位置<br>3. 检查 tooltip 内容 |
| 预期结果 | 阻力线为 null 时，tooltip 中无"阻力线"条目（不显示"阻力线: null"或"阻力线: undefined"等异常文字） |
| 失败判定 | tooltip 中出现"阻力线: null"、"阻力线: NaN"或空白占位符 |

---

**TC-resistance-FE-06**（对应 AC-resistance-5）：HELP_ITEMS 说明浮层包含阻力线条目

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 VPA [?] 说明浮层中新增阻力线说明条目，颜色橙黄，图标为横实线，说明文案不含买卖指令 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 点击 VPA 副图顶部 [?] 按钮展开说明浮层<br>2. 检查是否有以"橙黄"或"空仓阻力线"相关的说明条目<br>3. 观察该条目前的图标形状和颜色<br>4. 阅读说明文案，检查是否含买卖指令 |
| 预期结果 | - 说明浮层中存在阻力线说明条目<br>- 条目前图标为**橙黄色横实线**（`iconType: 'line'`，颜色 `#ffa726`）<br>- 说明文案中含"只降不升"、"历史最低价"等描述性文字<br>- **不含**"买入"、"卖出"、"建仓"等操作指令 |
| 失败判定 | 找不到阻力线说明条目；图标颜色不为橙黄；文案含操作指令 |

---

**TC-resistance-FE-07**（对应 AC-resistance-6）：ChartSidebar 图例包含阻力线条目

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 VPA 副图右侧 ChartSidebar 图例区域新增阻力线图例（橙黄横实线 + "阻力线"文字） |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 VPA-Defender 副图<br>2. 查看右侧 ChartSidebar 的图例区域（横线 + 文字组合）<br>3. 确认存在"阻力线"图例条目<br>4. 对比阻力线图例颜色（橙黄 `#ffa726`）与防守线图例颜色（蓝色），两者应可区分 |
| 预期结果 | ChartSidebar 图例区域显示：收盘价 / 防守线 / OBV / OBV均线 / **阻力线**（新增），共5条图例；阻力线图例为橙黄色横实线 |
| 失败判定 | 图例无阻力线条目；或颜色与防守线颜色相同 |

---

**TC-resistance-FE-08**（对应 AC-resistance-7）：折叠/展开后阻力线正常渲染

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 VPA 副图折叠后再展开，阻力线曲线正常渲染，无数据丢失或闪烁 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 确认 VPA 副图展开且阻力线正常显示（橙黄曲线可见）<br>2. 点击折叠按钮，VPA 副图收起为折叠条<br>3. 点击展开按钮，VPA 副图重新展开<br>4. 检查阻力线曲线是否正常渲染，与折叠前一致 |
| 预期结果 | 展开后橙黄阻力线正常显示，无闪烁、无数据丢失、无"空白"段 |
| 失败判定 | 展开后找不到阻力线曲线；或曲线出现异常断线、闪烁 |

---

**TC-resistance-FE-09**（对应 AC-resistance-8）：多市场股票均可正常计算（回归）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 A股、港股、美股各类股票阻力线均可正常计算，不出现全 null 序列或异常值 |
| 验证方式 | **Runtime — 切换不同股票验证** |
| 操作步骤 | 1. 从 watchlist 中分别选择 A股（SH./SZ. 前缀）、港股（HK. 前缀）各一只（如有美股则也测试）<br>2. 对每只股票展开 VPA 副图<br>3. 检查阻力线是否正常显示（非全图空白） |
| 预期结果 | 每只股票的 VPA 副图均能正常显示阻力线（在 ATR 计算期之后），无全序列空白情况 |
| 失败判定 | 某类市场股票阻力线全为 null（图表无橙黄曲线）；或出现 JS 报错 |

---

## 三、FEAT-legend-toggle 测试用例

### 3.1 ChartSidebar 按钮状态验证

> **验证方式**：代码审查 + Runtime 人工验收

---

**TC-toggle-UI-01**（对应 AC-legend-toggle-1 前半段）：有 `seriesName` 的条目渲染为可点击按钮

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 legendItems 中带 `seriesName` 字段的条目渲染为 `<button>`，光标为 `pointer` |
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | 在 `ChartSidebar.jsx` 中：<br>1. legendItems 渲染逻辑对 `item.seriesName` 是否存在进行分支判断<br>2. 有 `seriesName` 的条目使用 `<button>` 元素（或含 `cursor: 'pointer'` 的可点击 div）<br>3. 无 `seriesName` 的条目仍为 `<div>`（纯展示，`cursor` 非 `pointer`） |
| Runtime 操作步骤 | 1. 展开 MACD 副图，查看右侧 ChartSidebar 图例区<br>2. 将鼠标依次悬停在各图例条目上：<br>   - DIF、DEA、柱(正)、柱(负) → 光标应变为**手型**（pointer）<br>   - 金叉、死叉 → 光标应保持**箭头型**（不可点击）<br>3. 对 RSI、KDJ、VPA 重复相同检查 |
| 预期结果 | 有 `seriesName` 的条目悬停时光标为 `pointer`；无 `seriesName` 的条目悬停时光标不变为 `pointer` |
| 失败判定 | 金叉/死叉条目出现 pointer 光标；或 DIF/DEA 条目无 pointer 光标 |

---

**TC-toggle-UI-02**（对应 AC-legend-toggle-1 后半段）：无 `seriesName` 的条目不响应点击

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证金叉/死叉/超买区/超卖区等纯展示条目点击后无任何响应（既无视觉变化，也不触发 ECharts action） |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 MACD 副图<br>2. 点击右侧 ChartSidebar 中的"金叉"图例条目<br>3. 观察：ChartSidebar 内金叉条目是否有样式变化（删除线/半透明）<br>4. 观察：MACD 图中任何曲线是否有显隐变化<br>5. 打开 DevTools Console，确认无 JS 错误<br>6. 对 RSI 超买区/超卖区、KDJ 金叉/死叉重复上述步骤 |
| 预期结果 | 点击后：无任何视觉样式变化、无 ECharts series 显隐变化、Console 无报错 |
| 失败判定 | 点击后出现删除线样式；或 ECharts 图表曲线发生变化；或 Console 报错 |

---

**TC-toggle-UI-03**（对应 AC-legend-toggle-4）：inactive 状态视觉样式（删除线 + 半透明）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证点击可切换图例后，active → inactive 视觉样式变化明确：文字出现删除线，图标和文字变为半透明 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 MACD 副图<br>2. 点击右侧 ChartSidebar 中"DIF"图例条目（首次点击，active → inactive）<br>3. 观察条目样式变化：<br>   - "DIF"文字是否出现**删除线**（`text-decoration: line-through`）<br>   - 条目整体是否变为**半透明**（`opacity` 降低，约 0.35）<br>   - LegendMark 图标是否同样半透明<br>4. 再次点击（inactive → active），确认样式恢复正常 |
| 预期结果 | inactive 状态：文字有删除线，条目整体（含图标）明显变暗/半透明；active 状态：样式完全恢复，无删除线，正常不透明 |
| 失败判定 | inactive 样式无变化；或只有文字半透明但图标不变；或删除线仅在文字出现而图标颜色不变 |

---

**TC-toggle-UI-04**（对应 AC-legend-toggle-7）：默认加载时所有图例为 active 状态

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证页面初次加载时，所有面板图例按钮均为 active 状态（全部曲线显示），不影响当前默认渲染行为 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 强制刷新页面（Ctrl+Shift+R）<br>2. 等待所有图表加载完毕<br>3. 逐一检查 MACD / RSI / KDJ / VPA 四个副图的 ChartSidebar 图例区<br>4. 确认所有图例条目均为正常样式（无删除线，正常不透明） |
| 预期结果 | 所有图例条目处于 active 状态，视觉无删除线、无半透明；ECharts 图表中所有曲线正常显示 |
| 失败判定 | 任意图例条目在初始加载时呈现 inactive 样式（删除线/半透明）；或某条曲线初始为隐藏状态 |

---

### 3.2 ECharts 曲线显隐切换验证

---

**TC-toggle-CHART-01**（对应 AC-legend-toggle-2）：点击图例，对应曲线立即消失/重现

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证点击可切换图例后，ECharts 图表中对应 series 曲线立即隐藏；再次点击后重新显示 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | **MACD 面板**：<br>1. 展开 MACD 副图，确认 DIF 曲线可见（紫/蓝折线）<br>2. 点击 ChartSidebar 中"DIF"图例（active → inactive）<br>3. 立即观察 MACD 图：DIF 曲线是否消失<br>4. 再次点击"DIF"图例（inactive → active）<br>5. 确认 DIF 曲线重新出现<br><br>**其他验证**（至少选 2 个不同面板）：<br>- RSI：点击"RSI(14)"图例，RSI 曲线消失/重现<br>- KDJ：点击"K线"图例，K 曲线消失/重现<br>- VPA：点击"防守线"图例，蓝色防守线消失/重现 |
| 预期结果 | 每次点击 active → inactive 后，对应曲线在图表中**立即**消失；再次点击 inactive → active 后，曲线**立即**重现 |
| 失败判定 | 点击后曲线无变化；或延迟较长时间后才消失；或曲线消失后再次点击无法恢复 |

---

**TC-toggle-CHART-02**（对应 AC-legend-toggle-3）：切换一条 series 不影响其他曲线

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证隐藏某一曲线时，同面板其他曲线的显示状态不受影响 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 KDJ 副图，确认 K、D、J 三条曲线均可见<br>2. 点击"J线"图例，隐藏 J 曲线<br>3. 验证：K 线和 D 线仍然可见，无任何变化<br>4. 点击"K线"图例，隐藏 K 曲线<br>5. 验证：D 线仍然可见 |
| 预期结果 | 每次只有被点击图例对应的曲线消失，其他曲线不受影响 |
| 失败判定 | 点击"J线"后 K 线或 D 线也消失/变化 |

---

**TC-toggle-CHART-03**（对应 AC-legend-toggle-5）：MACD 柱正/柱负共用 seriesName 联动切换

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证"柱(正)"和"柱(负)"两个图例条目共用 `seriesName: 'MACD柱'`，点击任意一个时两个条目同步切换 inactive，MACD 柱 series 整体隐藏 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | **测试联动切换**：<br>1. 展开 MACD 副图，确认红色柱（正）和绿色柱（负）均可见<br>2. 点击 ChartSidebar 中"柱(正)"图例条目<br>3. 验证：<br>   - "柱(正)"条目变为 inactive 样式（删除线 + 半透明）<br>   - "柱(负)"条目**同步**变为 inactive 样式（两者联动）<br>   - MACD 图中所有柱状线（正负均）消失<br>4. 再次点击"柱(负)"图例条目（此时为 inactive 状态）<br>5. 验证：两个条目均恢复 active 样式，MACD 柱重新显示 |
| 预期结果 | 点击"柱(正)"或"柱(负)"任意一个，两个条目同步切换 inactive/active 状态，MACD 柱 series 整体响应 |
| 失败判定 | 只有被点击的条目切换状态，另一条目未联动；或 MACD 柱部分消失（只有正柱或只有负柱消失） |

---

**TC-toggle-CHART-04**：KDJ `seriesName` 与 `label` 不一致的映射验证

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 KDJ 图例中 label（"K线"/"D线"/"J线"）与 ECharts series name（"K"/"D"/"J"）的正确映射——点击"K线"图例后，ECharts 中名为"K"的 series 被隐藏 |
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | 在 `StockAnalysis.jsx` 的 `kdjSidebarLegend` 数组中：<br>1. 确认 `{ label: 'K线', seriesName: 'K' }`（label 与 seriesName 不同）<br>2. 确认 `{ label: 'D线', seriesName: 'D' }`<br>3. 确认 `{ label: 'J线', seriesName: 'J' }`<br>4. `KDJPanel.jsx` 中 ECharts legend data 包含 `'K'`、`'D'`、`'J'`（与 series name 对应，不含"线"字） |
| Runtime 操作步骤 | 1. 展开 KDJ 副图<br>2. 点击"K线"图例（label 含"线"字）<br>3. 观察 KDJ 图中蓝色 K 曲线是否消失<br>4. 确认 D 线和 J 线不受影响 |
| 预期结果 | 点击"K线"后，ECharts 中 K（蓝色）曲线消失；D 线和 J 线仍可见 |
| 失败判定 | 点击"K线"后图表无变化（说明 seriesName 映射错误，仍使用"K线"而非"K"去查找 series）|

---

### 3.3 折叠展开后状态保持验证

---

**TC-toggle-PERSIST-01**（对应 AC-legend-toggle-6）：折叠前隐藏的曲线展开后仍为隐藏

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证副图折叠后再展开，ECharts 图表中 inactive 的 series 自动恢复隐藏状态，ChartSidebar 图例按钮的 inactive 样式保持 |
| 验证方式 | **Runtime 人工验收** |
| 背景说明 | Dev 实现中：ChartSidebar 的 `activeMap` 为 React state，折叠时不销毁（视觉状态保持）；展开时 ECharts 实例重建（`notMerge: true`），需通过 `setTimeout(80ms)` 后重新 `dispatchAction` 来恢复 inactive 的 series 隐藏状态 |
| 操作步骤 | 1. 展开 MACD 副图<br>2. 点击"DIF"图例，隐藏 DIF 曲线（确认 DIF 消失，"DIF"图例变为 inactive 样式）<br>3. 点击折叠按钮，MACD 副图折叠为折叠条<br>4. 点击展开按钮，MACD 副图重新展开<br>5. **等待约 100ms 后**观察：<br>   a. ChartSidebar 中"DIF"图例是否仍为 inactive 样式（删除线 + 半透明）<br>   b. MACD 图中 DIF 曲线是否仍为隐藏状态 |
| 预期结果 | 展开后：ChartSidebar 中"DIF"图例保持 inactive 样式；MACD 图中 DIF 曲线仍为隐藏状态（经约 80ms 延迟后自动恢复）|
| 失败判定 | 展开后 DIF 曲线重新出现（ECharts 状态重置但未同步）；或"DIF"图例恢复为 active 样式（React state 被重置） |

---

**TC-toggle-PERSIST-02**（对应 AC-legend-toggle-6 扩展）：多条 inactive 状态折叠后展开均保持

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证同时有多条 series 为 inactive 时，折叠/展开后全部状态均正确恢复 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 KDJ 副图<br>2. 依次点击"K线"和"J线"图例，隐藏 K 曲线和 J 曲线（D 线保持可见）<br>3. 确认当前状态：K、J 消失，D 可见；"K线"、"J线"为 inactive，"D线"为 active<br>4. 折叠 KDJ 副图，再展开<br>5. 等待约 100ms 后观察 |
| 预期结果 | 展开后：K 曲线和 J 曲线仍为隐藏；D 曲线仍可见；ChartSidebar 中"K线"、"J线"保持 inactive 样式，"D线"保持 active 样式 |
| 失败判定 | 展开后任意一条的状态未正确恢复 |

---

**TC-toggle-PERSIST-03**（对应 AC-legend-toggle-8）：切换股票后图例状态重置为全 active

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证切换股票后，所有面板图例恢复全 active 状态，不保留上一只股票的 inactive 记录 |
| 验证方式 | **Runtime 人工验收** |
| 背景说明 | Dev 实现：通过 `key={xxx-sidebar-${code}}` 使 ChartSidebar 在切换股票时重新挂载，`activeMap` 自动重置为全 active |
| 操作步骤 | 1. 选择股票 A，展开 MACD 副图<br>2. 点击"DEA"图例，隐藏 DEA 曲线（inactive 状态）<br>3. 从股票下拉菜单切换到股票 B<br>4. 切换后等待 K 线数据加载完毕<br>5. 检查 MACD 副图右侧 ChartSidebar：所有图例是否均恢复为 active 状态<br>6. 检查 MACD 图：DEA 曲线是否重新可见 |
| 预期结果 | 切换股票后，所有图例按钮恢复 active 样式（无删除线），所有曲线重新显示 |
| 失败判定 | 切换股票后，上一只股票的 inactive 状态（DEA 图例删除线）仍存在；或 DEA 曲线仍为隐藏 |

---

### 3.4 四个面板独立验证

---

**TC-toggle-PANEL-01**：MACD 面板图例可切换项完整性

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 MACD 面板 legendItems 中可切换条目和纯展示条目的完整配置 |
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | `StockAnalysis.jsx` 中 `macdSidebarLegend`（或同名数组）：<br>- `{ label: 'DIF',    seriesName: 'DIF'    }` ✅ 可切换<br>- `{ label: 'DEA',    seriesName: 'DEA'    }` ✅ 可切换<br>- `{ label: '柱(正)', seriesName: 'MACD柱' }` ✅ 可切换，联动柱(负)<br>- `{ label: '柱(负)', seriesName: 'MACD柱' }` ✅ 可切换，联动柱(正)<br>- `{ label: '金叉'  }` ❌ 无 seriesName，纯展示<br>- `{ label: '死叉'  }` ❌ 无 seriesName，纯展示<br><br>`MACDPanel.jsx` option 中：<br>- `legend: { show: false, data: ['DIF', 'DEA', 'MACD柱'] }` 已注册 series |
| Runtime 操作步骤 | 1. 依次点击 DIF、DEA、柱(正)，验证三者均可切换<br>2. 点击金叉、死叉，验证均无响应 |
| 预期结果 | MACD 面板：4 个可切换条目（DIF/DEA/柱(正)/柱(负)），2 个纯展示条目（金叉/死叉） |
| 失败判定 | 任意可切换条目无法点击；或金叉/死叉响应了点击 |

---

**TC-toggle-PANEL-02**：RSI 面板图例可切换项完整性

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 RSI 面板 legendItems 中可切换条目和纯展示条目的完整配置 |
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | `StockAnalysis.jsx` 中 `rsiSidebarLegend`（或同名数组）：<br>- `{ label: 'RSI(14)', seriesName: 'RSI14' }` ✅ 可切换<br>- `{ label: '超买区(卖)' }` ❌ 无 seriesName，纯展示<br>- `{ label: '超卖区(买)' }` ❌ 无 seriesName，纯展示<br><br>`RSIPanel.jsx` option 中：`legend: { show: false, data: ['RSI14'] }` 已注册 |
| Runtime 操作步骤 | 1. 点击"RSI(14)"图例，验证 RSI 曲线消失<br>2. 点击超买区/超卖区图例，验证无响应 |
| 预期结果 | RSI 面板：1 个可切换条目（RSI(14)），2 个纯展示条目（超买区/超卖区） |
| 失败判定 | RSI(14) 点击后 RSI 曲线无变化；或超买/超卖区响应了点击 |

---

**TC-toggle-PANEL-03**：KDJ 面板图例可切换项完整性

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 KDJ 面板 legendItems 中可切换条目和纯展示条目完整，seriesName 与 label 不一致的映射正确 |
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | `StockAnalysis.jsx` 中 `kdjSidebarLegend`（或同名数组）：<br>- `{ label: 'K线', seriesName: 'K' }` ✅ 可切换（label≠seriesName，需 seriesName 字段映射）<br>- `{ label: 'D线', seriesName: 'D' }` ✅ 可切换<br>- `{ label: 'J线', seriesName: 'J' }` ✅ 可切换<br>- `{ label: '金叉' }` ❌ 纯展示<br>- `{ label: '死叉' }` ❌ 纯展示<br><br>`KDJPanel.jsx` option 中：`legend: { show: false, data: ['K', 'D', 'J'] }` 已注册（注意 series name 无"线"字） |
| Runtime 操作步骤 | 1. 点击"K线"图例，验证 K 曲线消失（D/J 不受影响）<br>2. 点击"D线"图例，验证 D 曲线消失<br>3. 点击"J线"图例，验证 J 曲线消失<br>4. 点击金叉/死叉，验证无响应 |
| 预期结果 | KDJ 面板：3 个可切换条目（K/D/J 线），2 个纯展示条目（金叉/死叉）；label 与 seriesName 不一致时通过 seriesName 正确映射 |
| 失败判定 | 点击"K线"后 ECharts 找不到名为"K线"的 series（应使用 `seriesName:'K'`），导致曲线无变化 |

---

**TC-toggle-PANEL-04**：VPA 面板图例可切换项完整性（含阻力线）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 VPA 面板 legendItems 中所有条目（含 iter8.1-patch 新增的阻力线）均可切换，且 seriesName 与 label 完全一致（无需额外映射）|
| 验证方式 | **代码审查 + Runtime 人工验收** |
| 代码审查要点 | `StockAnalysis.jsx` 中 `vpaSidebarLegend`（或同名数组）：<br>- `{ label: '收盘价', seriesName: '收盘价' }` ✅<br>- `{ label: '防守线', seriesName: '防守线' }` ✅<br>- `{ label: 'OBV',   seriesName: 'OBV'   }` ✅<br>- `{ label: 'OBV均线', seriesName: 'OBV均线' }` ✅<br>- `{ label: '阻力线', seriesName: '阻力线' }` ✅ **新增**<br><br>`VPADefenderPanel.jsx` option 中：`legend: { show: false, data: ['收盘价', '防守线', 'OBV', 'OBV均线', '阻力线'] }` 已注册（含新增阻力线） |
| Runtime 操作步骤 | 1. 展开 VPA 副图，确认阻力线（橙黄）可见<br>2. 点击"阻力线"图例，验证橙黄曲线消失（防守线/OBV 不受影响）<br>3. 点击"防守线"图例，验证蓝色防守线消失<br>4. 点击"OBV均线"图例，验证橙色虚线消失<br>5. 再次点击各图例，验证曲线均恢复 |
| 预期结果 | VPA 面板：5 个可切换条目（收盘价/防守线/OBV/OBV均线/阻力线），无纯展示条目；所有条目 label 与 seriesName 一致，切换正常 |
| 失败判定 | 阻力线图例无法点击切换；或点击后其他曲线也消失；或 VPA legend data 未包含"阻力线" |

---

### 3.5 交叉场景与回归验证

---

**TC-toggle-REG-01**（对应 AC-legend-toggle-9）：曲线隐藏后 crosshair 联动不报错

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证隐藏某条曲线后，useChartSync 的跨图十字线联动正常工作，无 JS 错误 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开所有副图<br>2. 隐藏 MACD 的 DIF 曲线（点击"DIF"图例）<br>3. 鼠标悬停在 K 线主图上，触发跨图十字线联动<br>4. 观察 MACD、RSI、KDJ、VPA 副图是否正常出现同步竖线<br>5. 打开 DevTools Console，观察是否有 JS 错误（如"Cannot read properties of undefined"等）<br>6. 再隐藏 KDJ 的 J 线，重复上述联动测试 |
| 预期结果 | 无论哪条曲线被隐藏，跨图 crosshair 联动均正常（竖线正确出现，无报错） |
| 失败判定 | 隐藏曲线后 crosshair 联动失效；或 Console 出现 JS 错误 |

---

**TC-toggle-REG-02**（对应 AC-legend-toggle-10）：折叠展开按钮与图例切换独立运作

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证折叠/展开按钮功能不受图例切换状态影响，两者独立运作 |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 展开 RSI 副图<br>2. 点击"RSI(14)"图例，隐藏 RSI 曲线（inactive 状态）<br>3. 点击 ChartSidebar 右上角折叠按钮（`∧`），副图折叠<br>4. 确认折叠正常（收为折叠条）<br>5. 点击折叠条展开按钮（`∨`），副图展开<br>6. 验证：`∧`/`∨` 按钮功能均正常，无被图例 inactive 状态干扰 |
| 预期结果 | 即使图例有 inactive 状态，折叠/展开按钮仍正常工作；折叠展开后 inactive 状态保持（见 TC-toggle-PERSIST-01）|
| 失败判定 | 有 inactive 图例时折叠/展开按钮无响应；或报 JS 错误 |

---

**TC-toggle-REG-03**：所有面板图例初始不影响现有默认渲染（回归）

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证新增 ECharts `legend: { show: false, data: [...] }` 配置后，图表原有渲染效果不受影响（包括曲线颜色、线宽、tooltip 格式等） |
| 验证方式 | **Runtime 人工验收** |
| 操作步骤 | 1. 强制刷新页面<br>2. 逐一检查 MACD / RSI / KDJ / VPA 四个副图：<br>   - 各曲线颜色与迭代前一致<br>   - 曲线线宽正常<br>   - hover tooltip 内容正常<br>   - 无多余 legend 图例 UI 出现（`show: false` 应保证不渲染） |
| 预期结果 | 四个副图视觉效果与 iter8.0 版本一致，无任何因新增 `legend` 配置而引起的视觉变化 |
| 失败判定 | 图表顶部出现 ECharts 默认 legend 图例 UI；或曲线颜色/样式发生变化 |

---

## 四、测试环境要求

### 4.1 浏览器

| 浏览器 | 版本要求 | 优先级 |
|--------|---------|--------|
| Chrome / Chromium | 最新稳定版（≥ 120） | 主测浏览器（P0）|
| Safari（macOS）| 最新稳定版 | 次测浏览器（P1）|

### 4.2 服务启动

| 服务 | 启动命令 |
|------|---------|
| FastAPI 后端 | `./env_quant/bin/uvicorn api.main:app --reload --port 8000` |
| React 前端（开发模式）| `cd web && npm run dev`（访问 http://localhost:5173）|
| 富途 OpenD | **可不运行**（测试仅读取已有数据库，无需实时数据）|

### 4.3 测试数据最低要求

| 条件 | 要求 |
|------|------|
| Watchlist 股票数 | ≥ 2 只（至少 1 只港股，用于 VPA 信号多样性；A股用于回归） |
| 历史 K 线数据 | 每只股票 ≥ 60 根日K（确保 ATR22 + OBV_MA20 均有足够计算窗口）|
| 数据时间跨度 | ≥ 1 年历史数据（便于观察阻力线"只降不升"特性） |
| VPA 信号多样性 | 最好含不同四象限信号的历史区间（便于 TC-resistance-FE-03 通道验证） |

---

## 五、验证方式汇总

### 5.1 代码审查用例（静态验证，不需运行环境）

| 用例 ID | 验证要点 |
|---------|---------|
| TC-resistance-BE-01 | `running_min_close = min(...)` 使用 min 更新 |
| TC-resistance-BE-02 | 候选值公式为加法 `+ atr_multi * ATR` |
| TC-resistance-BE-03 | 约束条件 `> prev` 时保持上一根（对称防守线 `< prev` 逻辑）|
| TC-resistance-BE-04 | `if atr_series[i] is not None` 守卫 + `[None]*size` 初始化 |
| TC-resistance-BE-05 | 返回字典新增 `"resistance_line"` 键，原有4键保留 |
| TC-resistance-BE-07 | 赋值含 `round(..., 6)` 保精度 |
| TC-toggle-UI-01（审查部分）| ChartSidebar.jsx 按 `seriesName` 有无分支渲染 |
| TC-toggle-CHART-04（审查部分）| `kdjSidebarLegend` 含 `seriesName: 'K'`（非 `'K线'`）|
| TC-toggle-PANEL-01 至 04（审查部分）| 各面板 legend.data 注册、seriesName 映射配置 |

### 5.2 Runtime 人工验收用例（需浏览器运行环境）

| 优先级 | 用例 ID | 验证要点 |
|--------|---------|---------|
| P0 | TC-resistance-FE-01 | 橙黄阻力线曲线可见（左Y轴） |
| P0 | TC-resistance-FE-04 | hover tooltip 含"阻力线"数值 |
| P0 | TC-resistance-API-01 | API 响应含 resistance_line 字段 |
| P0 | TC-toggle-UI-03 | inactive 样式（删除线 + 半透明）视觉正确 |
| P0 | TC-toggle-CHART-01 | 点击图例曲线立即消失/重现 |
| P0 | TC-toggle-CHART-03 | MACD 柱正/负联动切换 |
| P0 | TC-toggle-PERSIST-01 | 折叠展开后 inactive 状态保持（80ms 延迟同步）|
| P0 | TC-toggle-PERSIST-03 | 切换股票后状态重置（key 机制） |
| P1 | TC-resistance-FE-02 | 阻力线"只降不升"视觉验证 |
| P1 | TC-resistance-FE-03 | 阻力线与防守线通道形态 |
| P1 | TC-resistance-FE-06 | HELP_ITEMS 含阻力线说明条目 |
| P1 | TC-resistance-FE-07 | ChartSidebar 图例含阻力线条目 |
| P1 | TC-resistance-FE-08 | 折叠展开后阻力线正常渲染 |
| P1 | TC-toggle-PANEL-04 | VPA 面板阻力线图例可切换 |
| P1 | TC-toggle-REG-01 | 曲线隐藏后 crosshair 联动不报错 |
| P2 | TC-resistance-FE-09 | 多市场股票阻力线均可计算 |
| P2 | TC-toggle-REG-03 | 新增 legend 配置不影响原有渲染 |

---

## 六、风险说明

### 6.1 折叠展开 80ms 延迟的时序风险

**风险**：TC-toggle-PERSIST-01 的核心验证依赖 `setTimeout(80ms)` 后的 dispatchAction 同步。若运行环境较慢（低端机或 Safari 下），80ms 可能不够，导致 ECharts 实例尚未稳定就执行 dispatchAction，测试出现偶发性失败。

**缓解**：
- 测试时等待 200ms 再观察结果（人工操作足够等待）
- 若出现偶发失败，可在 DevTools Performance 面板中观察 ECharts 重建耗时，判断是否为时序问题

### 6.2 阻力线与防守线视觉相近性（TC-resistance-FE-03）

**风险**：阻力线橙黄（`#ffa726`）与 OBV均线（也是橙色 `#ffa726`）颜色相同，在双Y轴场景中可能引起混淆——阻力线绑定左Y轴（价格轴），OBV均线绑定右Y轴（OBV轴），两者虽颜色相同但量纲不同。

**缓解**：
- 通过 hover tooltip 区分（分别标注"阻力线"和"OBV均线"）
- **代码审查确认**：PRD 要求阻力线为 `#ffa726` 实线，OBV均线为 `#ffa726` 虚线（`type: 'dashed'`），线型不同可视觉区分
- 若 Dev 实现中两者均为实线，应上报 PM 确认是否需要调整阻力线颜色

> ⚠️ **待 Dev 确认**：`VPADefenderPanel.jsx` 中阻力线线型是否与 OBV均线（虚线）有所区分（PRD §7.6 要求阻力线为实线宽 1.5，OBV均线为虚线）。若混淆，需补充一条额外测试用例。

### 6.3 `kline_service.py` 自动透传依赖字典结构

**风险**：Dev 说明 `kline_service.py` 通过整体透传 `indicator_result.VPA_DEFENDER` 字典实现自动包含 `resistance_line`，无需修改透传代码。但如果后端字段名拼写与前端读取不一致（如后端 `resistance_line` vs 前端读 `resistanceLine`），会导致前端数据为 undefined 但不报错。

**缓解**：TC-resistance-API-01 明确验证 API 响应字段名；TC-resistance-FE-01 验证前端渲染，两者均通过则链路正常。

### 6.4 VPA `legend.data` 须包含"阻力线"

**风险**：ECharts `dispatchAction('legendToggleSelect')` 需要 legend 组件中有对应 series name 的注册才能生效。若 `VPADefenderPanel.jsx` 的 `legend.data` 数组未添加"阻力线"，则点击"阻力线"图例按钮将无效果（曲线不消失）。

**缓解**：TC-toggle-PANEL-04 的代码审查部分专门核查 `legend.data` 包含"阻力线"字段。

---

*文档结束 — 共 36 个测试用例（FEAT-resistance：16 个，FEAT-legend-toggle：20 个）。如有疑问请联系 QA 或 PM。*
