# 迭代9 代码审查报告 V2（CR Report — P1/P2 修复验证）

**文档版本**：v2.0
**日期**：2026-04-11
**作者**：QA
**审查基准**：cr_iter9.md v1.0 发现的 P1/P2 问题修复
**结论**：✅ **通过，所有 P1/P2 问题已正确修复，无新问题引入**

---

## 一、审查概况

| 项目 | 内容 |
|------|------|
| 审查范围 | 上一轮 CR 发现的 2 个 P1 + 2 个 P2 问题修复验证 |
| 修改文件数 | 4 个（adjust_fetcher / sync_engine / calendar_fetcher / settings） |
| P1 修复验证 | ✅ 2/2 通过 |
| P2 修复验证 | ✅ 2/2 通过 |
| 新问题引入 | 无 P0/P1/P2 级别新问题 |
| 回归风险 | 🟢 低 — 富途路径完全不受影响 |

---

## 二、逐项修复验证

---

### 2.1 P1-01：adjust_fetcher.py 双重 sleep ✅ 已修复

**原问题**：L159-160 双重 `time.sleep(wait)` 导致 429 退避时间翻倍

**修复内容**：
1. `import time` 移至文件顶部（L18）✅
2. 删除 L159 条件表达式 `time.sleep(wait) if not hasattr(self, '_time') else None` ✅
3. 删除 L160 行内 `import time;`，仅保留 `time.sleep(wait)` ✅

**白盒验证**：
- 修复后 `_fetch_factors_independent` 重试退避时间：attempt=0→30s, attempt=1→60s, attempt=2→120s
- 与 kline_fetcher 的 `_RATE_LIMIT_BACKOFF = [30, 60, 120]` 一致 ✅
- `import time` 在文件顶部，不再循环内重复 import ✅
- `_time` 属性引用已移除，消除了死代码 ✅

**结论**：✅ 修复完整正确

---

### 2.2 P1-02：_refresh_adjust_factors_from_kline 未复用已拉取数据 ✅ 已修复

**原问题**：`fetch_factors()` 即使有缓存也调用 `_extract_factors_via_kline` 发起新 API 请求

**修复内容**：

#### 修复点 1：sync_engine.py `_fetch_and_store` 美股 1D 路径改用 `fetch_and_extract_adj_close`

```python
# L597-608
is_us_stock = stock_code.startswith("US.") and self._yfinance_kline_fetcher is not None
if is_us_stock and period == "1D" and self._yfinance_adjust_fetcher is not None:
    bars, adj_close_map = self._yfinance_kline_fetcher.fetch_and_extract_adj_close(...)
    if adj_close_map:
        close_map = {bar.trade_date: bar.close for bar in bars if bar.close}
        self._yfinance_adjust_fetcher.cache_adj_close(
            stock_code, period, start_date, end_date, adj_close_map, close_map,
        )
else:
    bars = self._fetch_klines_paged(stock_code, period, start_date, end_date)
```

**白盒验证**：

1. **数据流追踪（美股 1D 周期）** ✅
   ```
   _sync_one
     → _fetch_and_store (美股1D分支)
       → kline_fetcher.fetch_and_extract_adj_close()  ← 唯一 API 请求
       → cache_adj_close(adj_close_map + close_map)   ← 缓存写入
       → bars 正常走 validate + insert/upsert 逻辑
     → _refresh_adjust_factors_from_kline
       → adjust_fetcher.fetch_factors()
         → _find_cached_adj_close() → 命中缓存（adj_close + close 都有）
         → 直接计算因子 → 零 API 请求  ✅
   ```

2. **close_map 可靠性** ✅
   - `bar.close` 类型为 `float`（KlineBar dataclass 定义）
   - `bar.close` 在 kline_fetcher 中 `round(float(row["Close"]), 4)` — 4 位小数
   - `adj_close_map` 在 `fetch_and_extract_adj_close` 中 `float(row["Adj Close"])` — 原始精度
   - ratio = adj_close / close 精度足够（与原 `_compute_factors_from_bars` 使用 `bar.close` 一致）
   - `{bar.trade_date: bar.close for bar in bars if bar.close}` — `if bar.close` 正确过滤 close=0 的情况

3. **富途路径回归** ✅
   - 非美股或非 1D 周期走 `else` 分支 → `_fetch_klines_paged()` → 行为与修复前完全一致
   - 美股 1W/1M 周期：条件 `period == "1D"` 不满足，走 `_fetch_klines_paged` → 不缓存
   - `_refresh_adjust_factors_from_kline` 内 `if period != "1D": return` — 1W/1M 直接跳过，不冲突

4. **缓存结构变更向后兼容** ✅
   - `_adj_close_cache` 仅在 `adjust_fetcher.py` 内部使用
   - 所有读取点（`_find_cached_adj_close`、`cache_adj_close`）已同步更新
   - 无外部代码直接访问 `_adj_close_cache`

#### 修复点 2：adjust_fetcher.py 缓存结构 + fetch_factors 缓存命中逻辑

```python
# cache_adj_close 缓存结构
self._adj_close_cache[key] = {
    "adj_close": adj_close_map,
    "close": close_map or {},
}

# fetch_factors 缓存命中
if cached and cached.get("adj_close") and cached.get("close"):
    # 直接用缓存计算因子，零 API 请求
```

**白盒验证**：

1. **缓存命中条件** ✅
   - `cached.get("adj_close")` — 非 None 且非空 dict 时为 truthy
   - `cached.get("close")` — 同上
   - 当 `close_map` 为空 dict（close_map 未提供）时，`cached.get("close")` 返回 `{}`，为 falsy → 走 kline_fetcher 路径
   - 这是正确行为：没有 close 数据时无法直接计算 ratio

2. **缓存命中计算逻辑与 `_compute_factors_from_bars` 一致性** ✅
   - 缓存路径：`ratio = adj_close / close_map.get(trade_date)`
   - `_compute_factors_from_bars`：`ratio = adj_close_map.get(bar.trade_date) / bar.close`
   - 两者语义等价（close_map 来自 `bar.close`，adj_close_map 来自 DataFrame）
   - `abs(ratio - 1.0) > 1e-6` 阈值一致
   - AdjustFactor 字段一致：forward_factor/forward_factor_b/backward_factor/backward_factor_b/factor_source

3. **边界情况** ✅
   - `close == 0`：缓存路径 `if close is None or close == 0: continue` ✅
   - `close_map.get(trade_date)` 返回 None（日期不匹配）：`if close is None` 捕获 ✅
   - 缓存 key 匹配：`_find_cached_adj_close` 检查 `sc == stock_code and sd <= start_date and ed >= end_date` — 与 SyncEngine 传入的参数一致 ✅

**结论**：✅ 修复完整正确，核心优化目标已实现（美股1D同步仅需一次API请求）

---

### 2.3 P2-01：APP_VERSION 未更新 ✅ 已修复

**原问题**：`APP_VERSION = "v0.8.7-patch"`

**修复**：`APP_VERSION = "v0.9.0"`

**验证**：config/settings.py L88 ✅

---

### 2.4 P2-02：calendar_fetcher market!=US 返回空列表 ✅ 已修复

**原问题**：market != "US" 时返回空列表 + warning，可能掩盖路由逻辑错误

**修复**：改为 `raise ValueError(f"YFinanceCalendarFetcher only supports market='US', got '{market}'")`

**白盒验证**：

1. **调用方守卫** ✅
   - `_ensure_calendar` L304：`if calendar_market == "US" and self._yfinance_calendar_fetcher is not None:`
   - 仅当 `calendar_market == "US"` 时才调用 `yfinance_calendar_fetcher.fetch()`
   - 非美市场走 `else` 分支 → 富途 `calendar_fetcher.fetch()`
   - `calendar_market` 来自 `A_STOCK_CALENDAR_MARKET if market == "A" else market`
   - 可能值：US / HK / SH / SZ — 与 `_ensure_calendar(stock.market, ...)` 的 `stock.market` 一致

2. **ValueError 传播** ✅
   - `_ensure_calendar` 无 try/except 包裹 → ValueError 会向上传播
   - `_sync_one` 调用 `_ensure_calendar` 无 try/except → 继续向上
   - 最终由 `cmd_sync` 顶层捕获，表现为单股同步失败而非静默返回空数据
   - 这比返回空列表更安全：fail-fast 而非静默错误

3. **repair_one 路径** ✅
   - repair_one 也调用 `_ensure_calendar`，同样的路由守卫

**结论**：✅ 修复正确，路由守卫已到位，ValueError 不会在正常流程中触发

---

## 三、遗留问题（P3，不阻塞）

| 编号 | 文件 | 行号 | 描述 | 状态 |
|------|------|------|------|------|
| P3-01 | adjust_fetcher.py | L88, L140 | `end_plus_one` 计算后未使用（仅 L161 处使用） | 遗留，不影响功能 |
| P3-02 | kline_fetcher.py | L202 | `df.iterrows()` 对大 DataFrame 性能较差 | 遗留，建议向量化优化 |

---

## 四、回归风险评估

| 回归项 | 风险等级 | 说明 |
|--------|---------|------|
| A股/港股 K 线同步 | 🟢 低 | `_fetch_and_store` 非美股路径走 `_fetch_klines_paged`，完全不变 |
| A股/港股复权因子 | 🟢 低 | `_refresh_adjust_factors` 仅 US.* 分支走 yfinance |
| A股/港股日历 | 🟢 低 | `_ensure_calendar` 仅 market=="US" 走 yfinance，ValueError 不会触发 |
| 美股 1W/1M 同步 | 🟢 低 | `_fetch_and_store` 条件 `period == "1D"` 不满足时走原路径 |
| 美股 1D 缓存未命中 | 🟢 低 | 缓存为空时 fallback 到 `_extract_factors_via_kline`，行为与修复前一致 |

---

## 五、最终结论

**✅ 所有 P1/P2 问题已正确修复，建议合并。**

- P1-01：双重 sleep 已修复，429 退避时间恢复正常
- P1-02：数据复用已实现，美股 1D 同步仅需一次 API 请求
- P2-01：APP_VERSION 已更新至 v0.9.0
- P2-02：calendar_fetcher 改为 fail-fast，路由守卫到位
- 无新 P0/P1/P2 问题引入
- 富途路径回归风险低

---

*文档结束 — 修复验证通过，可进入合并评审。*
