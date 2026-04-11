# 迭代9 代码审查报告（CR Report）

**文档版本**：v1.0
**日期**：2026-04-11
**作者**：QA
**审查基准**：requirements_iter9.md v1.0 / test_cases_iter9.md v1.0
**结论**：⚠️ **有条件通过，需修复 2 个 P1 问题后建议合并**

---

## 一、审查概况

| 项目 | 内容 |
|------|------|
| 审查文件数 | 7 个（yfinance_wrap 4 + sync_engine 1 + main 1 + settings 1） |
| 变更功能点 | 7 个（3 P0 + 2 P1 + 2 P2） |
| AC 覆盖数 | 白盒验证全部 36+ 条 AC |
| 代码审查通过率 | **71%**（5/7 文件通过，2 个文件有 P1 问题） |
| 发现 P1 问题 | **2 个**（adjust_fetcher 双重 sleep + _refresh_adjust_factors_from_kline 未复用数据） |
| 发现 P2 问题 | 3 个（APP_VERSION 未更新 / turnover_rate 不一致 / calendar_fetcher market 校验过严） |
| 发现 P3 建议 | 2 个（end_plus_one 未使用 / df.iterrows 性能） |

---

## 二、各文件审查结论

---

### 2.1 yfinance_wrap/client.py ✅ 通过

**审查重点**：代理配置（curl_cffi Session 级别）、滑动窗口限频、429 识别

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-yfinance-5 | 请求间隔 ≥ 0.5s | ✅ 通过 | L88-93：`wait_rate_limit()` 先 sleep 固定间隔，再检查滑动窗口 |
| AC-yfinance-10 | 代理配置生效 | ✅ 通过 | L71-86：`_build_session()` 使用 `curl_cffi.requests.Session(proxy=...)` |
| AC-config-3 | 不设 .env 时功能正常 | ✅ 通过 | L54-62：`YFINANCE_PROXY or None` → None 时不传 proxy |
| — | 不污染 os.environ | ✅ 通过 | 全文无 `os.environ` 引用；`_build_session` 仅设 Session 级 proxy |

**白盒验证**：

1. **滑动窗口限频逻辑正确性** ✅
   - `RATE_LIMITS = [(60,60), (360,3600), (8000,86400)]` 与 Yahoo 官方规则一致
   - L97-115：循环检查每个窗口，`cutoff = now - window_seconds`，`popleft()` 清除过期记录
   - 等待计算：`oldest + window_seconds - now + 0.1s`，0.1s 安全余量合理
   - 记录时间戳在限频之后（L118-119），确保包含本次请求

2. **is_rate_limit_error 识别逻辑** ✅
   - L122-128：检查 "429"/"rate limit"/"too many requests"（大小写不敏感）
   - 覆盖 Yahoo 的 YFRateLimitError 和通用 HTTP 429

3. **Session 生命周期** ✅
   - Session 在 `__init__` 中创建（L69），整个生命周期复用
   - 无 `connect()`/`disconnect()`，符合 PRD 设计

**轻微问题**（P3，不阻塞）：
- L153 `request_count` 属性遍历整个 deque，当历史请求量大时 O(n)，但实际场景 n ≤ 8000，可接受

---

### 2.2 yfinance_wrap/kline_fetcher.py ✅ 通过

**审查重点**：fetch 逻辑、429 退避、数据解析、fetch_and_extract_adj_close

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-yfinance-2 | fetch 返回 List[KlineBar] | ✅ 通过 | L44-66：`fetch()` 调用 `_fetch_internal()` 返回 bars |
| AC-yfinance-3 | close 为原始收盘价 | ✅ 通过 | L138：`auto_adjust=False`；L218：`close=float(row["Close"])` |
| AC-yfinance-7 | 1W/1M 支持 | ✅ 通过 | L23-27：`_PERIOD_MAP = {"1D":"1d","1W":"1wk","1M":"1mo"}` |
| AC-yfinance-9 | 不支持 period 抛 ValueError | ✅ 通过 | L113-115 |
| AC-yfinance-8 | turnover/pe/pb/ps 默认值 | ✅ 通过 | L219-225：turnover=0.0, pe/pb/ps/turnover_rate=None |

**白盒验证**：

1. **429 退避策略** ✅
   - L30：`_RATE_LIMIT_BACKOFF = [30, 60, 120]`
   - L145-149：429 使用独立计数器 `rate_limit_retries`，退避索引递增
   - L156-157：普通错误使用 `2 ** attempt` 指数退避（1s→2s→4s）
   - 总重试次数：`max_retries + 1`（含首次），与 client.max_retries 语义一致

2. **end_date +1 天** ✅
   - L121-122：`end_dt = date.fromisoformat(end_date) + timedelta(days=1)`
   - yfinance `end` 是 exclusive，+1 天保证包含 end_date 当天

3. **fetch_and_extract_adj_close 复用** ✅
   - L68-99：返回 `(bars, adj_close_map)`
   - L84-91：优先从 DataFrame 提取 Adj Close
   - L94-97：兜底从 `bar._adj_close` 提取
   - 此 API 为 adjust_fetcher 复用设计，接口合理

4. **_parse_dataframe 解析** ✅
   - L209：`adj_close = row.get("Adj Close", row.get("Close", None))`，Close 作为兜底
   - L227：`bar._adj_close` 保存 Adj Close（6位小数），供复权计算使用
   - L215-218：OHLC 四位小数 round，符合 KlineBar 精度

---

### 2.3 yfinance_wrap/adjust_fetcher.py ⚠️ 有 P1 问题

**审查重点**：复权因子计算精度、kline_fetcher 复用、缓存机制

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-us-adjust-1 | 复权因子写入 adjust_factors | ✅ 通过 | `_compute_factors_from_bars` 和 `_fetch_factors_independent` 均构造 AdjustFactor |
| AC-us-adjust-5 | 幂等更新 | ✅ 通过 | 调用 `adjust_factor_repo.insert_new_only` |
| — | forward_factor 精度 | ✅ 通过 | L229：`round(ratio, 10)` 精度足够 |
| — | factor_source = "yfinance" | ✅ 通过 | L234/199 |

#### 🔴 P1-01：_fetch_factors_independent 双重 sleep（L159-160）

**问题描述**：
```python
# L159-160
time.sleep(wait) if not hasattr(self, '_time') else None
import time; time.sleep(wait)
```

**问题分析**：
1. `hasattr(self, '_time')` 永远为 `False`（`YFinanceAdjustFetcher` 没有 `_time` 属性），所以条件表达式执行 `time.sleep(wait)`
2. 随后 `import time; time.sleep(wait)` 再次 sleep 同样时长
3. **结果**：每次重试都 sleep 两倍的预期时间（如 429 首次重试 sleep 60s 而非 30s）
4. `import time` 应在文件顶部而非循环内部

**严重程度**：P1 — 直接影响重试等待时间，429 场景下退避时间翻倍，严重影响可用性

**修复建议**：
```python
# 文件顶部添加 import time
import time

# 替换 L159-160
time.sleep(wait)
```

#### 🔴 P1-02：_refresh_adjust_factors_from_kline 并未复用已拉取的 K 线数据

**问题描述**：
`SyncEngine._refresh_adjust_factors_from_kline()` 的文档声称"从K线拉取结果中提取复权因子（复用数据，不额外请求）"，但实际调用 `self._yfinance_adjust_fetcher.fetch_factors(stock_code)` 时，`fetch_factors()` 内部会调用 `_extract_factors_via_kline()`，该方法又调用 `self._kline_fetcher.fetch_and_extract_adj_close()`，**发起了全新的 yfinance API 请求**。

**代码路径追踪**：
```
SyncEngine._refresh_adjust_factors_from_kline()
  → YFinanceAdjustFetcher.fetch_factors()
    → _extract_factors_via_kline()
      → self._kline_fetcher.fetch_and_extract_adj_close(stock_code, "1D", DEFAULT_HISTORY_START, today)
        → YFinanceKlineFetcher._fetch_internal()
          → self._client.wait_rate_limit()   ← 新的 API 请求
          → ticker.history(...)               ← 实际网络请求
```

**问题影响**：
- 美股每只股票每次同步时，K线拉取 + 复权因子提取 = **两次独立的全历史请求**，而非预期的一次请求复用
- 请求量翻倍，更容易触发 Yahoo 限频
- 与 `_sync_one` L246 注释"一次请求复用"不符

**根本原因**：
`adjust_fetcher` 的 `cache_adj_close()` 方法存在但从未被调用。`SyncEngine._fetch_and_store()` 拉取 K 线后没有将 Adj Close 数据缓存到 adjust_fetcher。

**修复建议**（两种方案）：

**方案 A（推荐）**：在 `_fetch_and_store` 中缓存 Adj Close
```python
# SyncEngine._fetch_and_store 中，fetch 后缓存 adj_close
bars = self._fetch_klines_paged(stock_code, period, start_date, end_date)
# 新增：如果是美股且 kline_fetcher 有 fetch_and_extract_adj_close，缓存结果
if is_us_stock and hasattr(fetcher, 'fetch_and_extract_adj_close'):
    _, adj_close_map = fetcher.fetch_and_extract_adj_close(stock_code, period, start_date, end_date)
    # 但这样又多发一次请求...
```

实际上方案 A 仍有问题，因为 `_fetch_klines_paged` 调用的是 `fetch()` 而非 `fetch_and_extract_adj_close()`。

**方案 B（更彻底）**：修改 `_fetch_klines_paged` 使其返回额外数据
1. 在 `SyncEngine._sync_one` 美股分支中，直接调用 `kline_fetcher.fetch_and_extract_adj_close()` 替代 `_fetch_and_store` 中的 `fetch()`
2. 或将 `_fetch_and_store` 拆分为 fetch + store 两步，fetch 步骤使用 `fetch_and_extract_adj_close()`
3. 拿到 `adj_close_map` 后调用 `adjust_fetcher.cache_adj_close()` 缓存
4. 后续 `_refresh_adjust_factors_from_kline` 命中缓存，不再发请求

**严重程度**：P1 — 核心优化目标未实现，请求量翻倍

#### 🟡 P2-01：turnover_rate 字段不一致

**问题描述**：
kline_fetcher.py L225 设置 `turnover_rate=None`，但 PRD 第 2.2 节仅提到 `pe_ratio/pb_ratio/ps_ratio = None`，未明确 turnover_rate。与 design_iter9.md 第 4.1.1 节"pe_ratio/pb_ratio/ps_ratio/turnover_rate/last_close = None"一致。

但 KlineBar 中 `turnover` 设为 `0.0`（L219），`turnover_rate` 设为 `None`，语义一致：yfinance 不提供换手率数据。此为 P2 建议，不阻塞。

---

### 2.4 yfinance_wrap/calendar_fetcher.py ✅ 通过（有 P2 建议）

**审查重点**：pandas-market-calendars 集成、timezone 处理

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-us-calendar-2 | 获取 NYSE 交易日历 | ✅ 通过 | L50-51：`mcal.get_calendar("NYSE")` + `nyse.schedule()` |
| AC-us-calendar-3 | 覆盖 DEFAULT_HISTORY_START 至今 | ✅ 通过 | `start_date`/`end_date` 参数传入 |
| AC-us-calendar-4 | A股/港股日历不变 | ✅ 通过 | 仅 market="US" 时激活 |

**白盒验证**：

1. **timezone 处理** ✅
   - L57-61：`schedule.index` 是 tz-naive `DatetimeIndex`，直接 `strftime("%Y-%m-%d")`
   - 之前的 tz_convert bug 已修复（不再尝试 tz_convert）

2. **返回格式与 futu CalendarFetcher 兼容** ✅
   - 返回 `List[str]`（日期字符串列表），与 futu CalendarFetcher.fetch() 返回格式一致

3. **ImportError 提前检查** ✅
   - L23-29：`__init__` 中检查 `pandas_market_calendars` 是否安装，未安装时抛出明确错误

**P2 建议**：
- L45-47：market != "US" 时返回空列表并打印 warning。建议改为 raise ValueError，因为调用方（`_ensure_calendar`）已做了 market 路由，若走到此分支说明逻辑有误，返回空列表可能掩盖问题。

---

### 2.5 core/sync_engine.py ⚠️ 有 P1 问题（与 adjust_fetcher P1-02 关联）

**审查重点**：多数据源路由、美股先拉K线再提取复权因子优化

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-multi-1 | SyncEngine 新增 yfinance fetcher 参数 | ✅ 通过 | L50-52：三个新增参数，默认 None |
| AC-multi-2 | US.* 路由至 yfinance | ✅ 通过 | L668-670：`_get_kline_fetcher()` |
| AC-multi-3 | HK./SH./SZ. 行为不变 | ✅ 通过 | L670：非 US.* 返回 `self._kline_fetcher` |
| AC-us-sync-1 | sync 命令成功拉取美股 | ✅ 通过（代码层面） | L248 + L260 路由逻辑正确 |
| AC-us-calendar-5 | 美股日历自动增量更新 | ✅ 通过 | L299-302：`_ensure_calendar` 按市场路由 |

**白盒验证**：

1. **美股跳过订阅** ✅
   - main.py L266-274：`if subscription_manager:` 条件守卫 + L272 过滤非 US 股票

2. **美股流程顺序优化** ⚠️
   - L248-252：非美股先 `_refresh_adjust_factors`
   - L260-263：拉取 K 线
   - L266-267：美股在 K 线拉取后调用 `_refresh_adjust_factors_from_kline`
   - **问题**：`_refresh_adjust_factors_from_kline` 未复用数据（见 P1-02），导致仍多发一次请求

3. **_fetch_klines_paged 路由** ✅
   - L663-664：调用 `_get_kline_fetcher` 路由，`repair_one` 也使用此方法

4. **_ensure_calendar 路由** ✅
   - L299：`calendar_market == "US"` 且 `_yfinance_calendar_fetcher is not None` 时走 yfinance
   - 其他市场走 `self._calendar_fetcher`（富途）

5. **_refresh_adjust_factors 路由** ✅
   - L322-323：`stock_code.startswith("US.")` 且 `_yfinance_adjust_fetcher is not None` 时走 yfinance

**其他观察**：
- L52：`yfinance_calendar_fetcher` 参数无类型注解，建议补充 `YFinanceCalendarFetcher`（P3）

---

### 2.6 main.py ✅ 通过

**审查重点**：build_dependencies 适配、cmd_sync OpenD 可选、cmd_repair 美股支持

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-multi-4 | build_dependencies 正确组装 | ✅ 通过 | L128-152：enable_yfinance 条件创建 |
| AC-multi-5 | OpenD 未启动时美股正常 | ✅ 通过 | L339-354：OpenD 失败时 has_us → yfinance-only mode |
| AC-multi-6 | A股/港股失败不影响美股 | ✅ 通过 | L343-354：futu_client=None 传入 build_dependencies |
| AC-us-gap-3 | repair 美股数据 | ✅ 通过 | L876-891：is_us_only 跳过 OpenD |

**白盒验证**：

1. **OpenD 可选逻辑** ✅
   - L335-354：首次连接失败时，有美股 → 继续（yfinance-only），无美股 → 退出
   - L348：`futu_client = None`，后续 `build_dependencies` 中所有 Futu 依赖对象都有 `if futu_client` 守卫

2. **yfinance 条件初始化** ✅
   - L132：`if enable_yfinance:` 条件创建 YFinanceClient/KlineFetcher/AdjustFetcher/CalendarFetcher
   - L138-142：proxy=None（空字符串时）的处理正确

3. **_has_us_stocks() 逻辑** ✅
   - L213-227：遍历 watchlist markets，检查 market=="US" + enabled + is_active
   - 异常安全：`except (json.JSONDecodeError, OSError)` 静默返回 False

4. **cmd_repair 美股支持** ✅
   - L876：`is_us_only = args.stock and args.stock.startswith("US.")`
   - L881：`if not is_us_only:` 才尝试连接 OpenD
   - L891：`enable_yfinance=has_us or is_us_only` 确保美股修复时启用 yfinance

5. **subscription_manager 过滤** ✅
   - L272：`futu_stocks = [s for s in active_stocks if not s.stock_code.startswith("US.")]`
   - 美股不参与订阅

---

### 2.7 config/settings.py ✅ 通过

| AC | 验收标准 | 审查结论 | 代码位置 |
|----|---------|---------|---------|
| AC-config-2 | 正确读取配置项 | ✅ 通过 | L81-83：三个变量，类型正确，默认值与 PRD 一致 |

**P2 问题**：
- L88：`APP_VERSION = "v0.8.7-patch"`，未更新为迭代9版本号。应在迭代完成时更新为 `"v0.9.0"` 或 `"v0.9.0-rc1"`

---

## 三、.env.example 审查 ✅ 通过

| AC | 验收标准 | 审查结论 |
|----|---------|---------|
| AC-config-1 | 三个 yfinance 配置项及注释 | ✅ 通过 |
| — | 注释说明代理类型（非大陆IP） | ✅ 通过（L73-76） |
| — | 注释说明代理范围（仅yfinance） | ✅ 通过（L74） |
| — | 注释说明限频规则 | ✅ 通过（L80-82） |
| — | 注释说明退避策略 | ✅ 通过（L86-87） |

---

## 四、问题汇总

### P1 — 必须修复

| 编号 | 文件 | 行号 | 问题描述 | 影响 |
|------|------|------|---------|------|
| P1-01 | adjust_fetcher.py | L159-160 | 双重 sleep：`time.sleep(wait) if not hasattr(self, '_time') else None` + `import time; time.sleep(wait)` | 429 重试退避时间翻倍（30s→60s, 60s→120s），严重影响可用性 |
| P1-02 | sync_engine.py + adjust_fetcher.py | L358 + L117 | `_refresh_adjust_factors_from_kline` 声称复用数据但实际发起新请求 | 每只美股每次同步多发一次全历史请求，优化目标未实现 |

### P2 — 建议修复

| 编号 | 文件 | 行号 | 问题描述 | 影响 |
|------|------|------|---------|------|
| P2-01 | settings.py | L88 | APP_VERSION 未更新（仍为 v0.8.7-patch） | 版本信息不准确 |
| P2-02 | calendar_fetcher.py | L45-47 | market != "US" 时返回空列表，应 raise ValueError | 掩盖路由逻辑错误 |
| P2-03 | kline_fetcher.py | L225 | turnover_rate=None 与 KlineBar 默认值一致但 PRD 未明确 | 文档与代码细微不一致 |

### P3 — 改进建议（不阻塞）

| 编号 | 文件 | 行号 | 问题描述 |
|------|------|------|---------|
| P3-01 | adjust_fetcher.py | L82,114,135 | `end_plus_one` 变量计算后未使用，仅 `today` 被传入 fetch |
| P3-02 | kline_fetcher.py | L202 | `df.iterrows()` 对大 DataFrame 性能较差，建议用向量化操作 |

---

## 五、P1 问题修复建议详细方案

### P1-01 修复方案

将 adjust_fetcher.py L159-160 替换为：

```python
# 文件顶部确保 import time（当前文件无此 import）
import time

# L159-160 替换为：
time.sleep(wait)
```

### P1-02 修复方案

**推荐方案**：在 `_sync_one` 美股分支中，改用 `fetch_and_extract_adj_close` 获取 K 线数据，并缓存 Adj Close 到 adjust_fetcher

修改 `SyncEngine._sync_one` 中美股 1D 周期的 K 线拉取逻辑：

```python
# 在 _fetch_and_store 方法中，增加返回原始 bars 的机制
# 或者在 _sync_one 中对美股 1D 特殊处理
```

具体实现需改两处：

1. **SyncEngine._fetch_and_store** 增加 `return_raw_bars` 参数或拆分为 fetch + store
2. **SyncEngine._sync_one** 美股 1D 分支：调用 `kline_fetcher.fetch_and_extract_adj_close()` 获取 `(bars, adj_close_map)`，缓存 `adj_close_map` 到 `adjust_fetcher.cache_adj_close()`，再执行 store

最小改动方案：在 `_fetch_and_store` 之后、`_refresh_adjust_factors_from_kline` 之前，对美股 1D 周期补一次缓存调用：

```python
if is_us_stock and period == "1D" and self._yfinance_adjust_fetcher is not None:
    # 缓存已拉取数据的 adj_close（复用，但需避免重复请求）
    # 此方案仍需调用 fetch_and_extract_adj_close 一次
    # 更好的方案是改 _fetch_and_store 内部逻辑
```

**注意**：此修复涉及 `_fetch_and_store` 方法重构，需仔细评估对富途路径的回归影响。建议：
- 先修复 P1-01（简单安全）
- P1-02 作为跟进优化，可单独提交

---

## 六、回归风险评估

| 回归项 | 风险等级 | 说明 |
|--------|---------|------|
| A股/港股 K 线同步 | 🟢 低 | 路由逻辑仅影响 US.* 前缀，HK/SH/SZ 走原路径 |
| A股/港股复权因子 | 🟢 低 | `_refresh_adjust_factors` 仅 US.* 分支走 yfinance |
| A股/港股日历 | 🟢 低 | `_ensure_calendar` 仅 market=="US" 走 yfinance |
| A股/港股空洞检测 | 🟢 低 | GapDetector 按 market 字段查询日历，US 日历独立 |
| SubscriptionManager | 🟢 低 | 过滤掉 US.* 股票，不影响富途订阅 |
| repair 命令 | 🟢 低 | is_us_only 逻辑正确隔离 |
| AdjustmentService | 🟢 低 | 未修改复权计算逻辑，仅新增 yfinance 数据源 |

---

## 七、白盒测试覆盖总结

| 测试类别 | 用例数 | 可执行（无代理） | 备注 |
|---------|-------|---------------|------|
| CONFIG 配置项 | 3 | ✅ 全部 | 不需要网络 |
| yfinance_wrap 模块 | 11 | ✅ 6 / ⚠️ 5 需网络 | 需网络：TC-02/03/04/07/08 |
| 多数据源路由 | 7 | ✅ 全部 | 代码审查 + mock |
| 美股K线同步 | 7 | ⚠️ 需网络 | E2E 测试待代理可用后执行 |
| 美股复权因子 | 5 | ⚠️ 需网络 | E2E 测试待代理可用后执行 |
| 美股交易日历 | 6 | ✅ 4 / ⚠️ 2 需网络 | pandas-market-calendars 无需网络 |
| 美股空洞检测 | 6 | ⚠️ 需网络+数据 | 依赖前置同步 |
| 回归测试 | 8 | ✅ 需 OpenD | A股/港股回归 |

**结论**：代码审查和白盒验证已完成，P1-01 可立即修复，P1-02 需方案评审后跟进。端到端测试待代理环境就绪后执行。

---

*文档结束 — 修复 P1 问题后可进入合并评审。*
