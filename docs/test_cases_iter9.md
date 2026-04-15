# 迭代9 测试用例文档

**文档版本**：v1.0
**日期**：2026-04-11
**作者**：QA
**基于需求**：requirements_iter9.md v1.0
**测试范围**：yfinance 美股数据源接入（多数据源路由 + 美股K线同步 + 美股复权 + 美股交易日历 + 美股空洞检测）

---

## 一、概述

### 1.1 迭代9变更范围

| 功能点 ID | 类型 | 简述 | 优先级 | 影响文件 |
|-----------|------|------|--------|---------|
| FEAT-yfinance | FEAT | 新增 yfinance_wrap/ 模块（Client + KlineFetcher + AdjustFetcher） | P0 | yfinance_wrap/*.py（新建）, requirements.txt |
| FEAT-multi-source | FEAT | SyncEngine 按市场码路由数据源（US→yfinance, HK/SH/SZ→futu） | P0 | core/sync_engine.py, main.py, config/settings.py |
| FEAT-us-sync | FEAT | 美股K线增量同步（日K/周K/月K） | P0 | core/sync_engine.py, yfinance_wrap/kline_fetcher.py |
| FEAT-us-adjust | FEAT | 美股复权因子获取与前复权计算 | P1 | yfinance_wrap/adjust_fetcher.py, core/sync_engine.py |
| FEAT-us-calendar | FEAT | 美股交易日历获取（pandas-market-calendars） | P1 | yfinance_wrap/calendar_fetcher.py（新建）, core/sync_engine.py, main.py, requirements.txt |
| FEAT-us-gap | FEAT | 美股空洞检测与修复 | P2 | core/gap_detector.py, core/sync_engine.py, main.py |
| CONFIG | CONFIG | .env 新增 yfinance 相关配置项 | P2 | config/settings.py, .env.example |

### 1.2 测试策略说明

1. **测试分层**：
   - **自动化白盒测试（Python pytest）**：yfinance_wrap 模块单元测试、SyncEngine 路由逻辑、GapDetector 美股适配、配置项读取
   - **端到端 CLI 验证**：`python main.py sync/check-gaps/repair/stats` 对美股的实际执行效果
   - **代码审查**：yfinance_wrap 代码规范、SyncEngine 路由逻辑正确性、市场码映射完整性

2. **测试环境要求**（详见第四章）：
   - 需要网络连接访问 Yahoo Finance（或配置代理）
   - 需要 `yfinance` 和 `pandas-market-calendars` 依赖已安装
   - 需要 watchlist.json 中配置美股股票

3. **执行顺序建议**（与开发顺序对应）：
   CONFIG → FEAT-yfinance → FEAT-multi-source → FEAT-us-sync → FEAT-us-adjust → FEAT-us-calendar → FEAT-us-gap

4. **回归重点**：A股/港股同步流程不受影响、富途 OpenD 不启动时美股可独立同步、现有空洞检测逻辑不变

5. **核心约束**：本迭代涉及所有美股相关代码，**严禁任何自动交易/下单/报价逻辑**

---

## 二、各功能点测试用例

---

### 2.1 CONFIG：.env 新增 yfinance 相关配置项

#### 前置条件

- 项目代码已更新，`config/settings.py` 包含新增配置项

---

**TC-config-01**（对应 AC-config-1）：.env.example 包含三个 yfinance 配置项

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 .env.example 新增 YFINANCE_PROXY、YFINANCE_REQUEST_INTERVAL、YFINANCE_MAX_RETRIES 三个配置项及注释说明 |
| 操作步骤 | 1. 打开 `.env.example` 文件<br>2. 搜索 `YFINANCE_PROXY`，确认存在且有注释说明<br>3. 搜索 `YFINANCE_REQUEST_INTERVAL`，确认默认值注释为 `0.5`<br>4. 搜索 `YFINANCE_MAX_RETRIES`，确认默认值注释为 `3` |
| 预期结果 | 三个配置项均存在于 `.env.example`，注释说明清晰（含用途、默认值、示例） |
| 失败判定 | 缺少任一配置项，或注释说明缺失/错误 |

---

**TC-config-02**（对应 AC-config-2）：config/settings.py 正确读取配置项

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 settings.py 正确从环境变量读取三个配置项并提供合理默认值 |
| 操作步骤 | 1. 打开 `config/settings.py`<br>2. 确认存在 `YFINANCE_PROXY` 变量，默认值为空字符串<br>3. 确认存在 `YFINANCE_REQUEST_INTERVAL` 变量，默认值为 `0.5`（float）<br>4. 确认存在 `YFINANCE_MAX_RETRIES` 变量，默认值为 `3`（int） |
| 预期结果 | 三个变量均存在，类型正确，默认值与 PRD 一致 |
| 失败判定 | 任一变量缺失、类型错误或默认值不一致 |
| 白盒验证 | 在 Python REPL 中：`from config.settings import YFINANCE_PROXY, YFINANCE_REQUEST_INTERVAL, YFINANCE_MAX_RETRIES; assert isinstance(YFINANCE_REQUEST_INTERVAL, float); assert isinstance(YFINANCE_MAX_RETRIES, int)` |

---

**TC-config-03**（对应 AC-config-3）：不配置 .env 时 yfinance 功能正常工作

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证使用默认配置值（无 .env 覆盖）时 yfinance 功能不报错 |
| 操作步骤 | 1. 确保 `.env` 中不包含 `YFINANCE_*` 配置项（或临时注释掉）<br>2. 执行 `./env_quant/bin/python -c "from config.settings import YFINANCE_PROXY, YFINANCE_REQUEST_INTERVAL, YFINANCE_MAX_RETRIES; print(YFINANCE_PROXY, YFINANCE_REQUEST_INTERVAL, YFINANCE_MAX_RETRIES)"`<br>3. 验证输出为空字符串 + 0.5 + 3 |
| 预期结果 | 配置值均为默认值，不抛出异常 |
| 失败判定 | 导入报错，或默认值与预期不符 |

---

### 2.2 FEAT-yfinance：新增 yfinance_wrap/ 模块

#### 前置条件

- `yfinance` 依赖已安装到 `env_quant/`
- 网络可访问 Yahoo Finance（或通过代理）

---

**TC-yfinance-01**（对应 AC-yfinance-1）：yfinance_wrap/ 包结构完整

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 yfinance_wrap/ 包包含四个必要模块 |
| 操作步骤 | 1. 检查 `yfinance_wrap/__init__.py` 是否存在<br>2. 检查 `yfinance_wrap/client.py` 是否存在<br>3. 检查 `yfinance_wrap/kline_fetcher.py` 是否存在<br>4. 检查 `yfinance_wrap/adjust_fetcher.py` 是否存在<br>5. 验证 `__init__.py` 导出 YFinanceClient / YFinanceKlineFetcher / YFinanceAdjustFetcher |
| 预期结果 | 四个文件均存在，`__init__.py` 正确导出三个类名 |
| 失败判定 | 缺少任一文件，或导出类名不正确 |
| 白盒验证 | `./env_quant/bin/python -c "from yfinance_wrap import YFinanceClient, YFinanceKlineFetcher, YFinanceAdjustFetcher; print('OK')"` |

---

**TC-yfinance-02**（对应 AC-yfinance-2）：YFinanceKlineFetcher.fetch() 返回 List[KlineBar]

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFinanceKlineFetcher 的 fetch 方法返回正确的 KlineBar 列表 |
| 操作步骤 | 1. 在 Python REPL 中执行：<br>```python<br>from yfinance_wrap.client import YFinanceClient<br>from yfinance_wrap.kline_fetcher import YFinanceKlineFetcher<br>client = YFinanceClient()<br>fetcher = YFinanceKlineFetcher(client)<br>bars = fetcher.fetch("US.AAPL", "1D", "2024-01-02", "2024-01-31")<br>```<br>2. 检查 `bars` 类型为 `list`<br>3. 检查每个元素类型为 `KlineBar`<br>4. 检查字段完整性 |
| 预期结果 | - `len(bars) > 0`<br>- 每个 bar 的 `stock_code == "US.AAPL"`<br>- `trade_date`/`open`/`high`/`low`/`close`/`volume` 字段完整且类型正确<br>- `trade_date` 格式为 `YYYY-MM-DD` |
| 失败判定 | 返回空列表、字段缺失、类型错误、stock_code 不正确 |

---

**TC-yfinance-03**（对应 AC-yfinance-3）：返回 KlineBar 中 close 为原始收盘价

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 fetch 返回的 close 字段为原始收盘价（非前复权价），volume 单位为股 |
| 操作步骤 | 1. 调用 `fetcher.fetch("US.AAPL", "1D", "2024-01-02", "2024-01-31")`<br>2. 获取任意一条 bar<br>3. 用 yfinance 直接验证：`import yfinance as yf; df = yf.Ticker("AAPL").history(start="2024-01-02", end="2024-01-31", auto_adjust=False)`<br>4. 对比同一天的 Close 值（非 Adj Close）和 Volume 值 |
| 预期结果 | - bar.close == df 同一天的 Close 值（原始收盘价）<br>- bar.close != df 同一天的 Adj Close 值（前复权价，AAPL 有拆股历史应不同）<br>- bar.volume 与 yfinance Volume 值一致（单位为股） |
| 失败判定 | close 等于 Adj Close（说明使用了 auto_adjust=True）；volume 单位非股 |

---

**TC-yfinance-04**（对应 AC-yfinance-4）：YFinanceAdjustFetcher 获取复权因子

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFinanceAdjustFetcher 能获取 AAPL 的拆股/股息记录并转换为 adjust_factors 格式 |
| 操作步骤 | 1. 在 Python REPL 中执行：<br>```python<br>from yfinance_wrap.client import YFinanceClient<br>from yfinance_wrap.adjust_fetcher import YFinanceAdjustFetcher<br>client = YFinanceClient()<br>fetcher = YFinanceAdjustFetcher(client)<br>factors = fetcher.fetch_factors("US.AAPL")<br>```<br>2. 检查 `factors` 类型为 `list`<br>3. 检查每个元素类型为 `AdjustFactor`<br>4. 检查字段：`stock_code == "US.AAPL"`, `ex_date` 格式为 `YYYY-MM-DD`, `forward_factor` 为 float |
| 预期结果 | - `len(factors) > 0`（AAPL 有历史除权事件）<br>- `factors[0].stock_code == "US.AAPL"`<br>- `factors[0].ex_date` 为有效日期字符串<br>- `factors[0].forward_factor` 为正浮点数<br>- `factors[0].factor_source == "yfinance"` |
| 失败判定 | 返回空列表、类型错误、字段缺失、factor_source 不为 "yfinance" |

---

**TC-yfinance-05**（对应 AC-yfinance-5）：请求间隔 ≥ 0.5 秒

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFinanceClient 内置请求间隔控制，默认 ≥ 0.5 秒 |
| 操作步骤 | 1. 记录连续两次 API 调用的时间戳：<br>```python<br>import time<br>from yfinance_wrap.client import YFinanceClient<br>client = YFinanceClient()<br>start = time.time()<br>client._request("AAPL", "1d", "2024-01-02", "2024-01-05")  # 第一次<br>client._request("MSFT", "1d", "2024-01-02", "2024-01-05")  # 第二次<br>elapsed = time.time() - start<br>assert elapsed >= 0.5<br>```<br>2. 或检查代码中 `time.sleep(YFINANCE_REQUEST_INTERVAL)` 是否存在于请求方法中 |
| 预期结果 | 两次连续请求间隔 ≥ 0.5 秒 |
| 失败判定 | 间隔 < 0.5 秒，或代码中无 sleep 调用 |
| 白盒验证 | AST 检查 YFinanceClient 中包含 `time.sleep` 调用，且参数引用 `YFINANCE_REQUEST_INTERVAL` |

---

**TC-yfinance-06**（对应 AC-yfinance-6）：yfinance 依赖已添加到 requirements.txt

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 requirements.txt 包含 yfinance 依赖 |
| 操作步骤 | 1. 打开 `requirements.txt`<br>2. 搜索 `yfinance` |
| 预期结果 | `requirements.txt` 中包含 `yfinance` 行 |
| 失败判定 | 缺少 yfinance 依赖 |

---

**TC-yfinance-07**（补充）：KlineFetcher 对 1W/1M 周期的支持

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFinanceKlineFetcher 支持 1W 和 1M 周期 |
| 操作步骤 | 1. 调用 `fetcher.fetch("US.AAPL", "1W", "2024-01-01", "2024-06-30")`<br>2. 调用 `fetcher.fetch("US.AAPL", "1M", "2024-01-01", "2024-12-31")`<br>3. 检查返回的 KlineBar 列表不为空，且 period 字段正确 |
| 预期结果 | - 1W 返回 bar 的 `period == "1W"`<br>- 1M 返回 bar 的 `period == "1M"`<br>- trade_date 分别对应周K/月K的日期格式 |
| 失败判定 | 返回空列表或抛出 ValueError("Unsupported period") |

---

**TC-yfinance-08**（补充）：KlineBar 中 turnover/pe_ratio/pb_ratio/ps_ratio 默认值

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 yfinance 返回的 KlineBar 中 yfinance 不提供的字段正确设为默认值 |
| 操作步骤 | 1. 调用 `fetcher.fetch("US.AAPL", "1D", "2024-01-02", "2024-01-05")`<br>2. 检查任一 bar 的以下字段 |
| 预期结果 | - `turnover == 0`（或 None，需确认 PRD 规范：PRD 说"设为 0"）<br>- `pe_ratio is None`<br>- `pb_ratio is None`<br>- `ps_ratio is None` |
| 失败判定 | turnover 非 0/None；pe_ratio/pb_ratio/ps_ratio 不为 None |

---

**TC-yfinance-09**（补充）：不支持的 period 抛出 ValueError

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证传入不支持的 period 值时抛出 ValueError |
| 操作步骤 | 1. 执行 `fetcher.fetch("US.AAPL", "1H", "2024-01-02", "2024-01-05")` |
| 预期结果 | 抛出 `ValueError`，消息包含 "Unsupported period" 或类似描述 |
| 失败判定 | 不抛出异常，或抛出非 ValueError 类型的异常 |

---

**TC-yfinance-10**（补充）：代理配置生效

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFINANCE_PROXY 配置能正确传递给 yfinance 请求 |
| 操作步骤 | 1. 在 `.env` 中设置 `YFINANCE_PROXY=http://127.0.0.1:7890`<br>2. 重新加载配置<br>3. 检查 YFinanceClient 是否使用代理（代码审查或代理日志验证） |
| 预期结果 | YFinanceClient 构造时读取 YFINANCE_PROXY 并设置到 yfinance 请求的 proxy 参数 |
| 失败判定 | 代理配置未被读取或未传递给 yfinance |
| 备注 | 不需要实际代理服务器，仅验证配置传递链路 |

---

**TC-yfinance-11**（补充）：网络异常时优雅处理

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 yfinance 请求失败时（网络异常、Yahoo 限频）的异常处理 |
| 操作步骤 | 1. 通过 mock 模拟 yfinance 请求异常：<br>```python<br>from unittest.mock import patch<br>with patch("yfinance.Ticker.history", side_effect=Exception("429 Too Many Requests")):<br>    bars = fetcher.fetch("US.AAPL", "1D", "2024-01-02", "2024-01-05")<br>```<br>2. 或断网后执行 fetch |
| 预期结果 | - 不崩溃，抛出可控异常或返回空列表<br>- 日志中记录错误信息<br>- 重试逻辑按 YFINANCE_MAX_RETRIES 次数执行 |
| 失败判定 | 未捕获异常导致进程崩溃 |

---

### 2.3 FEAT-multi-source：多数据源路由架构

#### 前置条件

- FEAT-yfinance 模块已实现
- SyncEngine 已修改支持多数据源路由

---

**TC-multi-01**（对应 AC-multi-1）：SyncEngine 新增 yfinance fetcher 参数

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 SyncEngine 构造函数新增 yfinance_kline_fetcher 和 yfinance_adjust_fetcher 参数 |
| 操作步骤 | 1. 检查 `core/sync_engine.py` 的 `SyncEngine.__init__` 签名<br>2. 确认新增 `yfinance_kline_fetcher` 参数（默认 None）<br>3. 确认新增 `yfinance_adjust_fetcher` 参数（默认 None）<br>4. 确认现有富途参数（kline_fetcher, adjust_factor_fetcher 等）签名不变 |
| 预期结果 | - 新增两个可选参数<br>- 现有参数顺序和类型不变<br>- 默认值为 None，不破坏现有调用 |
| 失败判定 | 缺少新增参数；现有参数被移除或顺序改变 |
| 白盒验证 | AST 检查 SyncEngine.__init__ 参数列表包含 yfinance_kline_fetcher 和 yfinance_adjust_fetcher |

---

**TC-multi-02**（对应 AC-multi-2）：US. 前缀股票路由至 yfinance fetcher

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 stock_code 以 "US." 开头时，K线和复权拉取走 yfinance fetcher |
| 操作步骤 | 1. 代码审查 `_get_kline_fetcher("US.AAPL")` 返回 `self._yfinance_kline_fetcher`<br>2. 代码审查 `_get_adjust_fetcher("US.AAPL")` 返回 `self._yfinance_adjust_fetcher`<br>3. 或通过 mock 验证：<br>```python<br>engine._yfinance_kline_fetcher = mock_yf_fetcher<br>engine._kline_fetcher = mock_futu_fetcher<br>result = engine._get_kline_fetcher("US.AAPL")<br>assert result is mock_yf_fetcher<br>``` |
| 预期结果 | US. 前缀股票正确路由至 yfinance fetcher |
| 失败判定 | 路由到 futu fetcher，或抛出异常 |

---

**TC-multi-03**（对应 AC-multi-3）：HK./SH./SZ. 前缀股票行为不变

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 A股/港股股票仍走富途 fetcher，行为与迭代8完全一致 |
| 操作步骤 | 1. 代码审查 `_get_kline_fetcher("HK.00700")` 返回 `self._kline_fetcher`<br>2. 代码审查 `_get_kline_fetcher("SH.600519")` 返回 `self._kline_fetcher`<br>3. 代码审查 `_get_adjust_fetcher("HK.00700")` 返回 `self._adjust_factor_fetcher` |
| 预期结果 | HK./SH./SZ. 前缀股票均路由至富途 fetcher |
| 失败判定 | 任何 A股/港股代码被错误路由至 yfinance |

---

**TC-multi-04**（对应 AC-multi-4）：build_dependencies() 正确组装 yfinance 依赖

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 main.py 的 build_dependencies() 函数正确组装 yfinance 依赖 |
| 操作步骤 | 1. 打开 `main.py`<br>2. 检查 `build_dependencies()` 函数是否创建 YFinanceClient / YFinanceKlineFetcher / YFinanceAdjustFetcher<br>3. 检查 SyncEngine 构造时是否传入 yfinance fetcher 参数<br>4. 检查是否仅当 watchlist 中存在 US.* 股票时才初始化 yfinance 相关对象 |
| 预期结果 | - build_dependencies 中有 yfinance 依赖组装逻辑<br>- SyncEngine 接收新参数<br>- 条件初始化：无美股时不创建 yfinance 对象（或创建但不影响功能） |
| 失败判定 | 未组装 yfinance 依赖；SyncEngine 未接收新参数 |

---

**TC-multi-05**（对应 AC-multi-5）：富途 OpenD 未启动时美股同步正常

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 yfinance 不依赖富途 OpenD 连接 |
| 操作步骤 | 1. 确保富途 OpenD 未运行<br>2. 在 watchlist.json 中只保留美股股票<br>3. 执行 `./env_quant/bin/python main.py sync`<br>4. 观察是否成功拉取美股K线数据 |
| 预期结果 | 美股K线数据成功拉取并写入数据库，不依赖富途 OpenD 连接 |
| 失败判定 | 因 OpenD 未连接导致美股同步失败 |
| 备注 | 需要网络可访问 Yahoo Finance |

---

**TC-multi-06**（对应 AC-multi-6）：富途 OpenD 未启动时 A股/港股失败不影响美股同步

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证两个数据源的独立性——一个失败不影响另一个 |
| 操作步骤 | 1. 确保 watchlist.json 中同时包含美股和港股/A股<br>2. 确保富途 OpenD 未运行<br>3. 执行 `./env_quant/bin/python main.py sync`<br>4. 观察美股是否成功同步，A股/港股是否优雅报错而不影响美股 |
| 预期结果 | - 美股同步成功<br>- A股/港股同步失败，但错误被捕获记录<br>- 美股流程不因 A股/港股失败而中断 |
| 失败判定 | A股/港股失败导致美股同步被跳过或中断 |

---

**TC-multi-07**（补充）：美股跳过 CalendarFetcher 和 SubscriptionManager

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股同步时不调用富途 CalendarFetcher 和 SubscriptionManager |
| 操作步骤 | 1. 代码审查 `_sync_one` 方法，确认美股跳过 `_ensure_calendar`（使用 yfinance 日历替代）<br>2. 代码审查确认美股跳过 `subscription_manager.sync_subscriptions`<br>3. 或通过 mock 验证美股同步流程中 CalendarFetcher.fetch 未被调用 |
| 预期结果 | 美股同步路径不调用富途 CalendarFetcher 和 SubscriptionManager |
| 失败判定 | 美股同步时仍调用富途日历或订阅接口 |
| 白盒验证 | AST 检查 _sync_one 或 _run_full_sync 中有市场码判断，US 股票跳过日历/订阅步骤 |

---

### 2.4 FEAT-us-sync：美股K线增量同步

#### 前置条件

- FEAT-yfinance 和 FEAT-multi-source 已实现
- watchlist.json 中已配置美股（如 `US.AAPL`）
- 网络可访问 Yahoo Finance

---

**TC-us-sync-01**（对应 AC-us-sync-1）：sync 命令成功拉取美股日K/周K/月K

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `python main.py sync` 能成功拉取美股三种周期的K线数据 |
| 操作步骤 | 1. 在 watchlist.json 中添加 `US.AAPL`（确保 stocks 表有该记录）<br>2. 执行 `./env_quant/bin/python main.py sync`<br>3. 观察日志输出，确认 AAPL 的 1D/1W/1M 同步均有进展<br>4. 检查同步是否完成（无 FAILED 状态） |
| 预期结果 | - 三种周期均成功同步<br>- 日志中出现 `[US.AAPL][1D]`、`[US.AAPL][1W]`、`[US.AAPL][1M]` 的同步完成信息 |
| 失败判定 | 任一周期同步失败（FAILED），或 yfinance 请求异常未捕获 |

---

**TC-us-sync-02**（对应 AC-us-sync-2）：美股K线数据正确写入 kline_data 表

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股K线数据正确写入数据库 |
| 操作步骤 | 1. 执行 sync 成功后<br>2. 查询数据库：<br>```sql<br>SELECT * FROM kline_data WHERE stock_code = 'US.AAPL' AND period = '1D' ORDER BY trade_date DESC LIMIT 5;<br>```<br>3. 检查字段完整性 |
| 预期结果 | - 记录存在，`stock_code = 'US.AAPL'`<br>- `trade_date` 格式为 `YYYY-MM-DD`<br>- `open`/`high`/`low`/`close`/`volume` 均为有效数值（close > 0）<br>- `turnover` 为 0 或 NULL（PRD 规范）<br>- `pe_ratio`/`pb_ratio`/`ps_ratio` 为 NULL |
| 失败判定 | 数据缺失、字段为 NULL（除 yfinance 不提供的字段外）、数值异常 |

---

**TC-us-sync-03**（对应 AC-us-sync-3）：美股 sync_metadata 正确更新

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股同步后 sync_metadata 表状态正确 |
| 操作步骤 | 1. 执行 sync 成功后<br>2. 查询：<br>```sql<br>SELECT * FROM sync_metadata WHERE stock_code = 'US.AAPL';<br>```<br>3. 检查每个周期的记录 |
| 预期结果 | - 三个周期（1D/1W/1M）均有记录<br>- `sync_status = 'success'`<br>- `last_sync_date` 为今天或最近交易日<br>- `rows_fetched > 0`<br>- `first_sync_date` 为首次同步的起始日 |
| 失败判定 | 缺少记录、状态不为 success、last_sync_date 异常 |

---

**TC-us-sync-04**（对应 AC-us-sync-4）：增量同步仅拉取新数据

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证第二次 sync 只拉取增量数据，不重复拉取已有数据 |
| 操作步骤 | 1. 第一次执行 sync，记录 US.AAPL 1D 的 `rows_fetched` 值<br>2. 第二次执行 sync（间隔一天以上，确保有新交易日）<br>3. 对比第二次的 `rows_fetched` 值 |
| 预期结果 | - 第二次 `rows_fetched` 远小于第一次（仅增量数据）<br>- `sync_metadata.last_sync_date` 更新为新的同步日期<br>- 数据库中历史数据不被覆盖 |
| 失败判定 | 第二次拉取量与第一次相当（说明做了全量拉取） |

---

**TC-us-sync-05**（对应 AC-us-sync-5）：stats 命令正确显示美股同步状态

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `python main.py stats` 命令能显示美股股票信息 |
| 操作步骤 | 1. 确保数据库中有美股同步记录<br>2. 执行 `./env_quant/bin/python main.py stats`<br>3. 查看终端输出是否包含 US.AAPL |
| 预期结果 | - stats 输出包含 US.AAPL 股票<br>- 同步状态显示正确（success/pending/failed） |
| 失败判定 | 美股股票未出现在 stats 输出中，或状态显示异常 |

---

**TC-us-sync-06**（对应 AC-us-sync-6）：美股与A股/港股在同一数据库中共存

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证多市场数据在 kline_data 表中共存不冲突 |
| 操作步骤 | 1. 确保数据库中同时有 US.AAPL 和 HK.00700 的K线数据<br>2. 查询：<br>```sql<br>SELECT stock_code, period, COUNT(*) FROM kline_data WHERE stock_code IN ('US.AAPL', 'HK.00700') GROUP BY stock_code, period;<br>```<br>3. 对比各股票各周期的数据条数 |
| 预期结果 | - 两只股票的数据均完整存在<br>- UNIQUE 约束 (stock_code, period, trade_date) 不冲突<br>- 查询一只股票的数据不包含另一只的数据 |
| 失败判定 | 数据混淆、UNIQUE 冲突报错 |

---

**TC-us-sync-07**（对应 AC-us-sync-7）：yfinance 请求失败时优雅处理

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证网络异常或 Yahoo 限频时同步流程不崩溃 |
| 操作步骤 | 1. 通过 mock 模拟 yfinance 异常：<br>```python<br>from unittest.mock import patch<br>with patch("yfinance_wrap.kline_fetcher.YFinanceKlineFetcher.fetch", side_effect=Exception("429 Too Many Requests")):<br>    # 执行 sync_one<br>```<br>2. 或临时断网后执行 sync |
| 预期结果 | - 异常被捕获，记录到 sync_metadata（status=failed）<br>- 错误日志包含异常信息<br>- 不影响其他股票的同步<br>- 不崩溃 |
| 失败判定 | 未捕获异常导致进程退出 |

---

### 2.5 FEAT-us-adjust：美股复权因子获取与前复权计算

#### 前置条件

- FEAT-us-sync 已实现
- 美股K线数据已同步

---

**TC-us-adjust-01**（对应 AC-us-adjust-1）：美股复权因子写入 adjust_factors 表

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股股票的复权因子正确写入 adjust_factors 表 |
| 操作步骤 | 1. 执行 sync 成功后<br>2. 查询：<br>```sql<br>SELECT * FROM adjust_factors WHERE stock_code = 'US.AAPL' ORDER BY ex_date LIMIT 10;<br>```<br>3. 检查记录 |
| 预期结果 | - 存在 AAPL 的复权因子记录<br>- `ex_date` 为有效日期<br>- `forward_factor` 为正浮点数（AAPL 有拆股历史，应有 factor < 1.0 的记录）<br>- `factor_source = 'yfinance'` |
| 失败判定 | 无记录、字段异常、factor_source 不为 yfinance |

---

**TC-us-adjust-02**（对应 AC-us-adjust-2）：AdjustmentService 返回美股前复权数据

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 AdjustmentService.get_adjusted_klines() 对美股股票返回前复权数据 |
| 操作步骤 | 1. 在 Python REPL 中：<br>```python<br>from core.adjustment_service import AdjustmentService<br>from db.repositories.kline_repo import KlineRepository<br>from db.repositories.adjust_factor_repo import AdjustFactorRepository<br>kline_repo = KlineRepository(DB_PATH)<br>adj_repo = AdjustFactorRepository(DB_PATH)<br>svc = AdjustmentService(kline_repo, adj_repo)<br>result = svc.get_adjusted_klines("US.AAPL", "1D", "2024-01-02", "2024-06-30", adj_type="qfq")<br>```<br>2. 检查返回结果 |
| 预期结果 | - 返回 `List[KlineBar]`<br>- `is_adjusted = True`<br>- `adjust_type = "qfq"`<br>- 前复权收盘价 ≤ 原始收盘价（AAPL 有拆股历史） |
| 失败判定 | 返回空列表、is_adjusted=False、adjust_type 不为 qfq |

---

**TC-us-adjust-03**（对应 AC-us-adjust-3）：前复权收盘价与 yfinance Adj Close 误差 < 0.1%

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证项目计算的前复权价与 yfinance Adj Close 一致性 |
| 操作步骤 | 1. 获取 yfinance 的 Adj Close 值：<br>```python<br>import yfinance as yf<br>df = yf.Ticker("AAPL").history(start="2024-01-02", end="2024-06-30", auto_adjust=False)<br>```<br>2. 获取项目前复权数据（同上 TC-us-adjust-02）<br>3. 逐日比对 `bar.close`（前复权价）与 `Adj Close`<br>4. 计算误差：`abs(bar.close - adj_close) / adj_close * 100` |
| 预期结果 | - 所有交易日的误差 < 0.1%<br>- 大部分交易日误差 < 0.01% |
| 失败判定 | 任一交易日误差 ≥ 0.1% |

---

**TC-us-adjust-04**（对应 AC-us-adjust-4）：A股/港股复权计算不受影响

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股复权因子接入后，A股/港股的前复权计算结果不变 |
| 操作步骤 | 1. 在迭代9代码变更前，记录 HK.00700 某段日期的前复权收盘价<br>2. 迭代9代码变更后，再次获取同一日期范围的 HK.00700 前复权收盘价<br>3. 逐日对比 |
| 预期结果 | 两份数据完全一致，无变化 |
| 失败判定 | 任一日期的前复权价发生变化 |
| 备注 | 这是关键回归测试，确保 AdjustmentService 逻辑未被修改 |

---

**TC-us-adjust-05**（对应 AC-us-adjust-5）：美股复权因子幂等更新

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证多次执行 sync 后，adjust_factors 表不产生重复记录 |
| 操作步骤 | 1. 第一次执行 sync，查询 adjust_factors 中 US.AAPL 的记录数 N<br>2. 第二次执行 sync<br>3. 再次查询 US.AAPL 的记录数 |
| 预期结果 | 第二次执行后记录数仍为 N（或略有增加，因有新除权事件），不产生重复 |
| 失败判定 | 同一 ex_date 出现多条记录 |

---

### 2.6 FEAT-us-calendar：美股交易日历获取

#### 前置条件

- `pandas-market-calendars` 依赖已安装

---

**TC-us-calendar-01**（对应 AC-us-calendar-1）：pandas-market-calendars 依赖已添加

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 requirements.txt 包含 pandas-market-calendars 依赖 |
| 操作步骤 | 1. 打开 `requirements.txt`<br>2. 搜索 `pandas-market-calendars` |
| 预期结果 | `requirements.txt` 中包含 `pandas-market-calendars` 行 |
| 失败判定 | 缺少该依赖 |

---

**TC-us-calendar-02**（对应 AC-us-calendar-2）：YFinanceCalendarFetcher 获取 NYSE 交易日历

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 YFinanceCalendarFetcher 能获取 NYSE 交易日历并写入 trading_calendar 表 |
| 操作步骤 | 1. 执行 sync 后，查询：<br>```sql<br>SELECT * FROM trading_calendar WHERE market = 'US' ORDER BY trade_date LIMIT 10;<br>```<br>2. 检查记录 |
| 预期结果 | - 存在 market='US' 的交易日历记录<br>- `trade_date` 格式为 YYYY-MM-DD<br>- `is_trading_day` 字段正确（周末=0，工作日=1 或 0 取决于美国节假日） |
| 失败判定 | 无 US 市场日历数据，或 is_trading_day 值异常 |

---

**TC-us-calendar-03**（对应 AC-us-calendar-3）：交易日历覆盖范围正确

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股交易日历覆盖 DEFAULT_HISTORY_START 至今 |
| 操作步骤 | 1. 查询：<br>```sql<br>SELECT MIN(trade_date), MAX(trade_date) FROM trading_calendar WHERE market = 'US';<br>```<br>2. 确认 MIN(trade_date) ≤ DEFAULT_HISTORY_START（2000-01-01）<br>3. 确认 MAX(trade_date) ≥ 今天 |
| 预期结果 | 日历覆盖范围从 2000 年到当前日期 |
| 失败判定 | 覆盖范围不足 |

---

**TC-us-calendar-04**（对应 AC-us-calendar-4）：A股/港股日历获取逻辑不变

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 A股/港股日历仍走富途 CalendarFetcher |
| 操作步骤 | 1. 代码审查 `_ensure_calendar` 方法，确认 A股/港股仍使用 `self._calendar_fetcher`（富途）<br>2. 确认美股使用 `YFinanceCalendarFetcher` |
| 预期结果 | 市场路由逻辑正确，A股→SH日历（富途），港股→HK日历（富途），美股→US日历（yfinance/pandas-market-calendars） |
| 失败判定 | A股/港股日历请求被错误路由至 yfinance |

---

**TC-us-calendar-05**（对应 AC-us-calendar-5）：sync 执行时美股日历自动增量更新

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 sync 流程中美股日历增量更新 |
| 操作步骤 | 1. 删除 trading_calendar 中 market='US' 的部分数据（模拟不完整）<br>2. 执行 sync<br>3. 查询 US 日历覆盖范围是否已补全 |
| 预期结果 | 日历缺失部分被自动补充 |
| 失败判定 | 日历未被补充，或空洞检测因日历缺失而跳过 |

---

**TC-us-calendar-06**（补充）：NYSE 休市日正确标记

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股日历中美国法定节假日被正确标记为非交易日 |
| 操作步骤 | 1. 查询美国独立日（7月4日）附近的交易日历：<br>```sql<br>SELECT * FROM trading_calendar WHERE market = 'US' AND trade_date BETWEEN '2024-07-01' AND '2024-07-08' ORDER BY trade_date;<br>```<br>2. 确认 2024-07-04（独立日）为 `is_trading_day = 0` |
| 预期结果 | 7月4日及美国法定节假日被正确标记为非交易日 |
| 失败判定 | 独立日被标记为交易日 |

---

### 2.7 FEAT-us-gap：美股空洞检测与修复

#### 前置条件

- FEAT-us-calendar 已实现
- 美股交易日历数据已写入数据库

---

**TC-us-gap-01**（对应 AC-us-gap-1）：check-gaps 检测美股空洞

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `python main.py check-gaps --stock US.AAPL` 能正确检测美股空洞 |
| 操作步骤 | 1. 确保 US 市场交易日历已存在<br>2. 手动删除 kline_data 中 US.AAPL 某几天的数据（模拟空洞）：<br>```sql<br>DELETE FROM kline_data WHERE stock_code = 'US.AAPL' AND period = '1D' AND trade_date IN ('2024-03-15', '2024-03-18');<br>```<br>3. 执行 `./env_quant/bin/python main.py check-gaps --stock US.AAPL --period 1D`<br>4. 查看终端输出和日志 |
| 预期结果 | - 终端输出显示 US.AAPL 有空洞<br>- `data_gaps` 表中新增 status=open 的记录<br>- 空洞日期与删除的交易日匹配 |
| 失败判定 | 未检测到空洞，或检测到错误的空洞日期 |

---

**TC-us-gap-02**（对应 AC-us-gap-2）：check-gaps 全量检测覆盖多市场

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `python main.py check-gaps`（不指定股票）能同时检测 A股/港股/美股空洞 |
| 操作步骤 | 1. 确保数据库中有 A股、港股、美股的K线数据<br>2. 执行 `./env_quant/bin/python main.py check-gaps`<br>3. 查看终端输出 |
| 预期结果 | - 终端输出中包含所有市场股票的检测结果<br>- 各市场的日历查询正确（A股→SH，港股→HK，美股→US） |
| 失败判定 | 美股股票被跳过，或日历查询使用了错误的市场码 |

---

**TC-us-gap-03**（对应 AC-us-gap-3）：repair 修复美股K线数据

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 `python main.py repair --date 2024-03-15 --stock US.AAPL` 能修复美股数据 |
| 操作步骤 | 1. 确保数据库中 US.AAPL 2024-03-15 的数据缺失<br>2. 执行 `./env_quant/bin/python main.py repair --date 2024-03-15 --stock US.AAPL --period 1D`<br>3. 查询修复后的数据 |
| 预期结果 | - repair 命令成功执行<br>- kline_data 中 US.AAPL 2024-03-15 的数据已补充<br>- 终端输出 fetched=1, upserted=1 |
| 失败判定 | repair 失败、数据未补充、或报错 |

---

**TC-us-gap-04**（对应 AC-us-gap-4）：美股空洞修复流程与A股/港股一致

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股空洞修复走 yfinance 拉取 → upsert 覆盖 → 更新 gap 状态 |
| 操作步骤 | 1. 确保 data_gaps 表中有 US.AAPL 的 open 状态空洞<br>2. 执行 `./env_quant/bin/python main.py sync`<br>3. 观察 sync 日志中空洞修复流程<br>4. 查询 data_gaps 表中空洞状态变化 |
| 预期结果 | - sync 过程中 _heal_gaps 对美股空洞执行修复<br>- 修复成功后 gap 状态变为 filled<br>- 修复数据通过 yfinance 拉取并 upsert 写入 |
| 失败判定 | 美股空洞修复走富途 fetcher，或 gap 状态未更新 |

---

**TC-us-gap-05**（补充）：GapDetector market 提取逻辑适配 US 前缀

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证 GapDetector 中 stock_code → market 的映射逻辑支持 US. 前缀 |
| 操作步骤 | 1. 代码审查 `gap_detector.py` 的 `detect_gaps` 方法<br>2. 确认 `US.AAPL` → `market = "US"` 的映射逻辑存在<br>3. 确认 `A_STOCK_CALENDAR_MARKET` 映射不误处理 US 前缀 |
| 预期结果 | - `US.` 前缀提取为 `market = "US"`<br>- `calendar_market = "US"`<br>- 日历查询使用 `market='US'` |
| 失败判定 | US. 被映射为 "A" 或其他错误值 |

---

**TC-us-gap-06**（补充）：美股空洞 no_data 标记

| 项目 | 内容 |
|------|------|
| 测试目的 | 验证美股空洞修复时，若 yfinance 返回空数据，gap 被标记为 no_data |
| 操作步骤 | 1. 手动插入一个未来日期的美股空洞（如 2030-01-02）<br>2. 执行 sync<br>3. 观察 gap 处理结果 |
| 预期结果 | - yfinance 返回空数据<br>- gap 被标记为 `no_data`（skip_reason 包含 "api_no_data"）<br>- 下次 sync 不再重复尝试该空洞 |
| 失败判定 | gap 保持 open 状态被反复尝试 |

---

## 三、白盒测试策略

### 3.1 yfinance_wrap 模块白盒测试

#### 3.1.1 YFinanceClient 测试

| 测试项 | 测试方法 | 覆盖目标 |
|--------|---------|---------|
| 初始化默认配置 | 单元测试：无 .env 时默认值验证 | YFINANCE_PROXY=""、interval=0.5、retries=3 |
| 初始化自定义配置 | 单元测试：设置环境变量后验证 | 代理地址、间隔、重试次数生效 |
| 请求间隔控制 | 单元测试：mock time.sleep + 计时 | 确认 sleep(YFINANCE_REQUEST_INTERVAL) 被调用 |
| 重试机制 | 单元测试：mock 连续失败 | 确认重试 YFINANCE_MAX_RETRIES 次后抛出异常 |
| 代理传递 | 代码审查 | 确认 proxy 参数传递给 yfinance download/Ticker |

#### 3.1.2 YFinanceKlineFetcher 测试

| 测试项 | 测试方法 | 覆盖目标 |
|--------|---------|---------|
| fetch 接口签名 | 单元测试 | 与 futu KlineFetcher.fetch() 参数兼容 |
| DataFrame → KlineBar 转换 | 单元测试：构造 mock DataFrame | 字段映射正确性（Date→trade_date, Open→open 等） |
| auto_adjust=False | 单元测试：验证 close 为原始价 | 确认使用 Close 而非 Adj Close |
| turnover 默认值 | 单元测试 | 确认 turnover=0 或 None |
| pe/pb/ps 默认值 | 单元测试 | 确认 pe_ratio/pb_ratio/ps_ratio=None |
| period 映射 | 单元测试 | "1D"→"1d"、"1W"→"1wk"、"1M"→"1mo" |
| 不支持 period | 单元测试 | 传入 "1H" 抛出 ValueError |
| 空数据返回 | 单元测试：mock 返回空 DataFrame | 返回空列表，不崩溃 |
| 网络异常处理 | 单元测试：mock Exception | 重试 + 最终抛出或返回空 |

#### 3.1.3 YFinanceAdjustFetcher 测试

| 测试项 | 测试方法 | 覆盖目标 |
|--------|---------|---------|
| fetch_factors 返回类型 | 单元测试 | 返回 List[AdjustFactor] |
| forward_factor 计算 | 单元测试：构造已知 Adj Close/Close | `forward_factor = Adj Close / Close` 精度验证 |
| 无除权事件 | 单元测试：Adj Close == Close 的股票 | 返回空列表或 factor=1.0 不写入 |
| factor_source 字段 | 单元测试 | 确认 factor_source="yfinance" |
| 与 futu AdjustFactor 格式兼容 | 单元测试 | 确认字段名、类型与富途 AdjustFactor 一致 |
| forward_factor_b 默认值 | 单元测试 | yfinance 无加法偏移，forward_factor_b=0.0 |
| backward_factor 默认值 | 单元测试 | yfinance 无后复权，backward_factor=1.0 / backward_factor_b=0.0 |

### 3.2 SyncEngine 路由逻辑白盒测试

| 测试项 | 测试方法 | 覆盖目标 |
|--------|---------|---------|
| _get_kline_fetcher 路由 | 单元测试：传入不同 stock_code | US.* → yfinance, HK.* → futu, SH.* → futu, SZ.* → futu |
| _get_adjust_fetcher 路由 | 单元测试：同上 | 同上 |
| yfinance_fetcher 为 None 时 | 单元测试：不传 yfinance_fetcher | US.* 股票跳过或抛出清晰错误 |
| _fetch_klines_paged 路由 | 代码审查 | 确认调用 _get_kline_fetcher 而非直接用 self._kline_fetcher |
| repair_one 路由 | 代码审查 | 确认 repair 对美股走 yfinance fetcher |
| _ensure_calendar 美股路径 | 代码审查 | 美股日历走 YFinanceCalendarFetcher |
| _refresh_adjust_factors 美股路径 | 代码审查 | 美股复权因子走 YFinanceAdjustFetcher |
| _sync_one 美股跳过订阅 | 代码审查 | 美股不调用 SubscriptionManager |

### 3.3 GapDetector 美股适配白盒测试

| 测试项 | 测试方法 | 覆盖目标 |
|--------|---------|---------|
| market 提取 US. 前缀 | 单元测试 | "US.AAPL" → market="US" |
| calendar_market 映射 | 单元测试 | market="US" → calendar_market="US"（不经 A_STOCK_CALENDAR_MARKET 转换） |
| detect_gaps 查询 US 日历 | 单元测试：mock calendar_repo | 确认查询 market='US' 的交易日 |
| _group_consecutive 对美股数据 | 单元测试 | 美股交易日连续性判断正确 |
| no_data 排除逻辑 | 单元测试 | 美股 no_data 日期被正确排除 |

### 3.4 路径覆盖要点

以下为关键路径覆盖清单，确保白盒测试覆盖所有分支：

1. **SyncEngine._sync_one** 的市场码分支：
   - force_full + US 股票（美股全量同步）
   - is_reactivated + US 股票
   - 增量 + US 股票
   - force_full + HK 股票（现有路径，回归）
   - 增量 + HK 股票（现有路径，回归）

2. **SyncEngine._fetch_and_store** 的路由路径：
   - US 股票 → yfinance fetcher → KlineBar 写入
   - HK 股票 → futu fetcher → KlineBar 写入（回归）

3. **SyncEngine._heal_gaps** 的市场码分支：
   - US 股票空洞 → yfinance 拉取 → insert_many
   - US 股票空洞 → yfinance 返回空 → mark_no_data
   - HK 股票空洞 → futu 拉取（回归）

4. **YFinanceAdjustFetcher.fetch_factors** 的数据路径：
   - 有除权事件的股票（AAPL）
   - 无除权事件的股票（假设）
   - 网络异常路径

---

## 四、回归测试用例

> 本迭代修改了 SyncEngine、main.py、config/settings.py 等核心文件，必须确保 A股/港股功能不受影响。

---

### 4.1 A股/港股同步流程回归

**TC-reg-sync-01**：A股/港股全量同步不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 确保 watchlist 中有 A股和港股<br>2. 确保富途 OpenD 已启动<br>3. 执行 `./env_quant/bin/python main.py sync`<br>4. 检查 A股/港股同步日志和数据 | A股/港股同步流程与迭代8完全一致，无新增错误日志 |

**TC-reg-sync-02**：A股/港股增量同步不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 第二次执行 sync<br>2. 检查 A股/港股增量同步行为 | 增量拉取逻辑不变，last_sync_date 正确推进 |

### 4.2 复权计算回归

**TC-reg-adjust-01**：A股/港股前复权价格不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 获取 HK.00700 前复权数据<br>2. 与迭代8版本的数据对比 | 前复权收盘价完全一致 |

### 4.3 空洞检测回归

**TC-reg-gap-01**：A股/港股 check-gaps 不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 执行 `./env_quant/bin/python main.py check-gaps`<br>2. 检查 A股/港股空洞检测结果 | 检测逻辑不变，结果与迭代8一致 |

**TC-reg-gap-02**：A股/港股 repair 不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 执行 `./env_quant/bin/python main.py repair --date <date> --stock HK.00700 --period 1D`<br>2. 检查修复流程 | repair 走富途 fetcher，流程不变 |

### 4.4 日历管理回归

**TC-reg-cal-01**：A股/港股日历增量更新不变

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 删除部分 HK 日历数据<br>2. 执行 sync<br>3. 检查日历是否被补全 | A股/港股日历仍走富途 CalendarFetcher 增量补充 |

### 4.5 配置项回归

**TC-reg-config-01**：现有配置项不受影响

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 检查 config/settings.py 中所有现有变量 | OPEND_HOST/PORT、DB_PATH、RATE_LIMIT_*、WEB_* 等变量不变 |

### 4.6 API/Web 回归

**TC-reg-api-01**：Web 界面查看 A股/港股数据正常

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 启动 Web 服务<br>2. 在浏览器中查看 A股/港股的K线图 | 图表正常渲染，指标计算不变 |

**TC-reg-api-02**：API 接口返回 A股/港股数据正常

| 操作步骤 | 预期结果 |
|---------|---------|
| 1. 请求 `/api/stocks`<br>2. 请求 `/api/kline/HK.00760/1D` | 返回格式不变 |

---

## 五、测试环境要求

### 5.1 Python 环境

| 条件 | 要求 |
|------|------|
| Python 版本 | 3.10（env_quant 虚拟环境） |
| yfinance | 已安装到 env_quant |
| pandas-market-calendars | 已安装到 env_quant |
| 其他依赖 | requirements.txt 中所有包已安装 |

### 5.2 网络环境

| 条件 | 要求 |
|------|------|
| Yahoo Finance 访问 | 需要能访问 finance.yahoo.com（国内可能需要代理） |
| 代理配置 | 如在国内，需配置 YFINANCE_PROXY |
| 富途 OpenD | 回归测试需要启动，纯美股测试不需要 |

### 5.3 测试数据最低要求

| 条件 | 要求 |
|------|------|
| 美股股票 | watchlist.json 中至少配置 1 只美股（建议 US.AAPL） |
| A股/港股股票 | watchlist.json 中至少配置 1 只 A股或港股（回归测试用） |
| 数据库 | 空 DB 或已有数据的 DB 均可（测试会写入数据） |

### 5.4 watchlist.json 配置示例

```json
{
  "markets": [
    {
      "market": "US",
      "enabled": true,
      "stocks": [
        {
          "stock_code": "US.AAPL",
          "asset_type": "STOCK",
          "lot_size": 1,
          "currency": "USD",
          "name": "Apple Inc.",
          "is_active": true
        }
      ]
    }
  ]
}
```

---

## 六、风险说明

### 6.1 yfinance 网络依赖风险

| 风险 | 缓解 |
|------|------|
| Yahoo Finance API 不可用（国内网络受限） | 支持代理配置；mock 测试覆盖核心逻辑 |
| Yahoo 限频导致 429 错误 | 内置请求间隔 + 重试机制 + 代理切换 |
| yfinance 返回格式变更 | 单元测试中使用 mock DataFrame 验证解析逻辑 |

### 6.2 数据精度风险

| 风险 | 缓解 |
|------|------|
| forward_factor 浮点精度问题 | 误差验收标准 < 0.1%；与 yfinance Adj Close 交叉验证 |
| 周K/月K日期格式差异 | yfinance 周K/月K返回的 trade_date 格式需与项目 KlineBar 格式对齐 |

### 6.3 市场码映射风险

| 风险 | 缓解 |
|------|------|
| US. 前缀到 market="US" 映射遗漏 | 白盒测试覆盖所有市场码路径（US/HK/SH/SZ/A） |
| GapDetector 日历查询 market 值不一致 | 确认 US → "US" 映射与 trading_calendar 表中 market 值一致 |

### 6.4 依赖冲突风险

| 风险 | 缓解 |
|------|------|
| pandas-market-calendars 与现有 pandas 版本冲突 | 安装后运行 `./env_quant/bin/python -c "import pandas_market_calendars"` 验证 |
| yfinance 与现有依赖冲突 | 安装后运行完整测试套件验证 |

---

*文档结束 — 如有疑问请联系 QA 或 PM。*
