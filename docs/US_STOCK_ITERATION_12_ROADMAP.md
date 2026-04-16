# 迭代12：美股周K/月K支持实现方案

## 🎯 目标

扩展美股数据源支持，从当前**仅日K**扩展到**日/周/月K**，同时保持系统稳定性和成本效益。

---

## 📊 方案对比与选择

### 方案A：多源按周期路由（推荐）

**核心思想**：不同周期使用不同数据源
- 1D：AkShare（免费、稳定）
- 1W/1M：富途（OpenD需可用）

**优势**：
- ✅ 充分利用现有富途能力
- ✅ 保留 AkShare 日K 的稳定性
- ✅ 降低新增成本
- ✅ 易于回滚

**劣势**：
- ⚠️ 代码路由复杂度增加
- ⚠️ 需要富途 OpenD 连接可用
- ⚠️ 复权处理需要统一（跨源数据标准化）

**成本**：中等（需修改路由逻辑）

---

### 方案B：启用 yfinance 全量替代（备选）

**核心思想**：将 AkShare 替换为 yfinance，获得完整日周月K

**优势**：
- ✅ 支持完整日周月K
- ✅ 代码改动最小
- ✅ 复权因子内置

**劣势**：
- ❌ 需要 VPN 或 HTTP 代理（中国环境）
- ❌ 429 限频严格（需要特殊处理）
- ❌ 稳定性较低

**成本**：低（仅修改配置+初始化）

---

### 方案C：启用富途全量替代（备选）

**核心思想**：美股完全转向富途，不再使用 AkShare

**优势**：
- ✅ 支持完整日周月K
- ✅ 与 A股/港股 统一接口
- ✅ 复权因子一致处理

**劣势**：
- ❌ 需要富途 OpenD 连接
- ❌ 无法在美股独立运行
- ❌ 失去免费的 AkShare

**成本**：低（改动少）

---

## 🔧 推荐方案：方案A 详细实现

### 第1步：配置层扩展

**文件**：`config/settings.py`

```python
# 在第97行后添加：

# ============================================================
# 美股数据源按周期配置（迭代12新增）
# ============================================================
US_STOCK_SOURCES_BY_PERIOD = {
    "1D": "akshare",    # 日K：免费稳定，东方财富数据源
    "1W": "futu",       # 周K：富途 OpenD（需确保连接可用）
    "1M": "futu",       # 月K：富途 OpenD（需确保连接可用）
}

# 美股数据源可用性配置（用于健康检查）
US_STOCK_SOURCE_HEALTH_CHECK = os.getenv("US_STOCK_SOURCE_HEALTH_CHECK", "true").lower() == "true"
```

**对应 .env 配置**：

```env
# .env 文件添加（可选）
# 美股按周期数据源配置示例（JSON格式）
# US_STOCK_SOURCES_BY_PERIOD='{"1D":"akshare","1W":"futu","1M":"futu"}'

# 是否启用美股数据源健康检查
# US_STOCK_SOURCE_HEALTH_CHECK=true
```

---

### 第2步：同步引擎路由修改

**文件**：`core/sync_engine.py`

#### 2.1 修改 `_get_kline_fetcher()` 方法

**当前代码**（第682-689行）：

```python
def _get_kline_fetcher(self, stock_code: str):
    """按市场码返回对应的 K线 Fetcher。
    
    迭代11：美股使用 AkShare（支持日K前复权），其他使用富途。
    """
    if stock_code.startswith("US.") and self._akshare_kline_fetcher is not None:
        return self._akshare_kline_fetcher
    return self._kline_fetcher
```

**修改为**（支持按周期路由）：

```python
def _get_kline_fetcher(self, stock_code: str, period: str = None):
    """按市场码+周期返回对应的 K线 Fetcher。
    
    迭代12：美股按周期选源：
      - 1D: AkShare（免费稳定）
      - 1W/1M: 富途 OpenD（周K/月K能力）
      其他市场: 富途 OpenD
    """
    from config.settings import US_STOCK_SOURCES_BY_PERIOD
    
    # 美股特殊处理
    if stock_code.startswith("US."):
        # 若未指定周期，默认 1D
        target_period = period or "1D"
        
        # 查询周期对应的数据源
        source = US_STOCK_SOURCES_BY_PERIOD.get(target_period, "akshare")
        
        if source == "akshare" and self._akshare_kline_fetcher is not None:
            logger.debug(
                "[%s][%s] routing to AkShare kline fetcher",
                stock_code, target_period
            )
            return self._akshare_kline_fetcher
        elif source == "futu":
            logger.debug(
                "[%s][%s] routing to Futu kline fetcher",
                stock_code, target_period
            )
            return self._kline_fetcher
    
    # 非美股或美股无可用源，使用富途
    return self._kline_fetcher
```

#### 2.2 修改调用处

**当前代码**（第612行）：

```python
bars = self._fetch_klines_paged(stock_code, period, start_date, end_date)
```

**保持不变**，因为 `_fetch_klines_paged` 会调用 `_get_kline_fetcher`：

```python
def _fetch_klines_paged(
    self, stock_code: str, period: str, start_date: str, end_date: str
) -> list:
    """拉取K线（分页/单次，取决于数据源）。
    
    迭代12：按市场码+周期路由 Fetcher。
    """
    # ← 修改这里：传入 period 参数
    fetcher = self._get_kline_fetcher(stock_code, period)  # 新增 period 参数
    return fetcher.fetch(stock_code, period, start_date, end_date)
```

---

### 第3步：前端组件修改

**文件**：`web/src/components/PeriodSelector.jsx`

#### 当前代码（第14-17行）：

```jsx
export default function PeriodSelector({ value, onChange, stockCode }) {
  // 美股仅支持日K，过滤掉周K和月K
  const isUS = stockCode?.startsWith('US.')
  const periods = isUS ? PERIODS.filter(p => p.value === '1D') : PERIODS
```

#### 修改为（支持全部周期）：

```jsx
export default function PeriodSelector({ value, onChange, stockCode }) {
  // 迭代12：美股支持日周月K（后端多源路由）
  const isUS = stockCode?.startsWith('US.')
  // 美股现在支持全部周期，无需过滤
  const periods = PERIODS  // 不再条件过滤
  
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {periods.map(p => (
        <button
          key={p.value}
          onClick={() => onChange(p.value)}
          // ... 样式代码保持不变
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}
```

**简化方案**（更保守）：

如果希望保持一定的兼容性，可以只在后端提示用户美股周K/月K可能数据延迟：

```jsx
export default function PeriodSelector({ value, onChange, stockCode, warnings }) {
  const isUS = stockCode?.startsWith('US.')
  const periods = PERIODS  // 全部显示
  
  return (
    <div style={{ display: 'flex', gap: 4, position: 'relative' }}>
      {periods.map(p => {
        const isUSWeeklyOrMonthly = isUS && (p.value === '1W' || p.value === '1M')
        return (
          <div key={p.value} style={{ position: 'relative' }}>
            <button
              onClick={() => onChange(p.value)}
              style={{
                // ... 基础样式
                opacity: isUSWeeklyOrMonthly ? 0.7 : 1,  // 降低美股周月K透明度
              }}
              title={isUSWeeklyOrMonthly ? "US Weekly/Monthly: Futu data" : ""}
            >
              {p.label}
            </button>
            {isUSWeeklyOrMonthly && (
              <span style={{ fontSize: 10, color: '#999' }}>*</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

---

### 第4步：AkShare 仅日K 检查（防护）

**文件**：`akshare_wrap/kline_fetcher.py`（无需改动）

保留现有的周期检查：

```python
def fetch(self, stock_code: str, period: str, start_date: str, end_date: str) -> List[KlineBar]:
    if period not in self.SUPPORTED_PERIODS:  # ["1D"]
        raise ValueError(
            f"AkShare US stock only supports daily K-line. "
            f"Requested period: {period}, supported: {self.SUPPORTED_PERIODS}"
        )
```

这个检查确保 AkShare 不会收到 1W/1M 请求（已由路由层过滤）。

---

### 第5步：测试覆盖

**测试用例**：

```python
# tests/test_iter12_us_weekly_monthly.py

import pytest
from core.sync_engine import SyncEngine
from models.stock import Stock

def test_us_daily_routes_to_akshare():
    """美股日K应路由到 AkShare"""
    stock = Stock(stock_code="US.AAPL", market="US", ...)
    
    fetcher = sync_engine._get_kline_fetcher("US.AAPL", "1D")
    assert isinstance(fetcher, AkShareKlineFetcher)

def test_us_weekly_routes_to_futu():
    """美股周K应路由到富途"""
    fetcher = sync_engine._get_kline_fetcher("US.AAPL", "1W")
    assert isinstance(fetcher, KlineFetcher)  # 富途

def test_us_monthly_routes_to_futu():
    """美股月K应路由到富途"""
    fetcher = sync_engine._get_kline_fetcher("US.AAPL", "1M")
    assert isinstance(fetcher, KlineFetcher)  # 富途

def test_hk_stock_always_uses_futu():
    """港股应始终使用富途"""
    for period in ["1D", "1W", "1M"]:
        fetcher = sync_engine._get_kline_fetcher("HK.0700", period)
        assert isinstance(fetcher, KlineFetcher)

def test_akshare_rejects_non_daily():
    """AkShare 应拒绝非日K请求"""
    with pytest.raises(ValueError, match="only supports daily"):
        fetcher = AkShareKlineFetcher(client)
        fetcher.fetch("US.AAPL", "1W", "2024-01-01", "2024-12-31")
```

---

## 📋 实现检查清单

- [ ] **配置层**
  - [ ] 在 `config/settings.py` 添加 `US_STOCK_SOURCES_BY_PERIOD` 配置
  - [ ] 在 `.env.example` 中记录新配置项
  - [ ] 验证配置读取正确

- [ ] **后端路由**
  - [ ] 修改 `sync_engine._get_kline_fetcher()` 支持 period 参数
  - [ ] 修改 `sync_engine._fetch_klines_paged()` 传入 period
  - [ ] 在 `_sync_one()` 中确认 period 参数流传正确
  - [ ] 验证 AkShare 仅处理 1D，其他周期正确降级

- [ ] **前端UI**
  - [ ] 修改 `PeriodSelector.jsx` 移除美股周K/月K过滤
  - [ ] 测试按钮展示和选中状态
  - [ ] 验证不同市场的周期选项正确显示

- [ ] **复权数据处理**
  - [ ] 确认富途周K/月K 的复权因子能否统一处理
  - [ ] 验证 AkShare 日K（前复权）与富途周K（原始未复权）数据一致性
  - [ ] 如有差异，在上层应用做好标准化

- [ ] **测试验证**
  - [ ] 单元测试：路由逻辑
  - [ ] 集成测试：完整同步流程
  - [ ] 端到端测试：前端选择 → 后端同步 → 数据验证
  - [ ] 压力测试：多股票并行同步

- [ ] **监控和日志**
  - [ ] 添加日志记录数据源选择决策
  - [ ] 添加指标统计各周期的请求分布
  - [ ] 配置告警：某数据源不可用时

- [ ] **文档更新**
  - [ ] 更新 README.md 美股支持情况
  - [ ] 更新 .env.example 说明
  - [ ] 更新本迭代分析文档

---

## 🚨 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|--------|
| 富途连接不稳定 | 周K/月K拉取失败 | 实现多源降级（周K失败→日K补偿） |
| AkShare/富途数据不一致 | 用户迷惑 | 明确标注数据源，添加警告 |
| 前端显示混乱 | 用户体验差 | 充分测试各市场的周期组合 |
| 复权因子跨源计算错误 | 数据失真 | 统一在上层做复权标准化 |

---

## 🔄 回滚计划

如迭代12出现问题，回滚步骤：

```bash
# 1. 恢复配置
git checkout config/settings.py

# 2. 恢复后端路由
git checkout core/sync_engine.py

# 3. 恢复前端
git checkout web/src/components/PeriodSelector.jsx

# 4. 重新启动同步
# 系统会自动降级到迭代11状态（美股仅日K）
```

---

## 📈 迭代12 成功指标

- ✅ 美股 1D/1W/1M 数据完整可拉取
- ✅ 前端周期选择器正常工作
- ✅ 复权数据标准化一致
- ✅ 性能无明显退化（限频依然有效）
- ✅ 代码覆盖率 ≥ 80%
- ✅ 零数据一致性问题

---

## 📝 附录：迭代12后的架构

### 路由决策树

```
同步请求：stock_code, period, start, end
  │
  ├─ 美股（US.*）?
  │  ├─ YES
  │  │  ├─ period == "1D"?
  │  │  │  ├─ YES → AkShare（日K前复权）✅
  │  │  │  └─ NO  → 富途（周K/月K原始未复权）✅
  │  │  └─
  │  └─ NO → 富途（日K/周K/月K）
```

### 数据流向

```
前端选股+周期
  ↓
PeriodSelector（迭代12: 显示日周月K）
  ↓
StockChart 组件
  ↓
API GET /klines?stock=US.AAPL&period=1W
  ↓
SyncEngine._fetch_klines_paged()
  ↓
_get_kline_fetcher(stock, period)  ← 新增period参数
  │
  ├─ period="1W" → return FutuKlineFetcher
  └─
  ↓
FutuKlineFetcher.fetch(...)
  ↓
数据库 KLINE_BAR 表（1W 粒度）
  ↓
API 返回数据
  ↓
前端图表渲染
```

### 配置示例

```python
# config/settings.py 迭代12 配置
US_STOCK_SOURCES_BY_PERIOD = {
    "1D": "akshare",    # 稳定、免费、前复权
    "1W": "futu",       # 周K完整能力
    "1M": "futu",       # 月K完整能力
}

# 也支持全量 AkShare（如 yfinance 升级）
# US_STOCK_SOURCES_BY_PERIOD = {
#     "1D": "yfinance",
#     "1W": "yfinance",
#     "1M": "yfinance",
# }
```

