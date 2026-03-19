# AI 量化辅助决策系统 - 迭代5产品需求文档（PRD）

**版本**: v5.0
**日期**: 2026-03-19
**范围**: 数据写入可靠性修复、K线悬停信息增强、下拉菜单信号分组、局域网访问鉴权
**前置**: 迭代1~4 均已完成，HEAD commit `57a9c12`，tag `v0.4.0`

---

## 1. 迭代5目标

**主题：稳定性加固 + 用户体验提升**

| 迭代 | 目标 |
|------|------|
| 迭代1 | 能跑、能采数据 |
| 迭代2 | 能持续运行、服务器无人值守 |
| 迭代3 | 能看、能分析——技术指标可视化辅助决策 |
| 迭代4 | 能更全、更稳、更主动——基本面数据/容灾/归档/告警 |
| **迭代5** | **更可靠、更易用、更安全——写入可靠性修复、信息密度提升、局域网开放访问** |

**核心价值主张**：
1. **修复关键数据可靠性漏洞**：进程意外中断后当日最新 K 线数据将可在下次同步时被覆盖更新，不再被"INSERT OR IGNORE"永久跳过，保证当日数据的完整性。
2. **提升 K 线图信息密度**：悬停浮层新增数据更新时间戳，帮助用户判断当前数据是盘中实时数据还是收盘最终数据，避免基于过期盘中数据做错误判断。
3. **优化股票选择体验**：首页下拉菜单按综合信号（多头/空头/中性）分组，帮助用户快速锁定感兴趣方向的股票，减少无效翻查。
4. **开放局域网安全访问**：支持家庭局域网内手机/平板查看 K 线图表，同时通过 Token 鉴权防止意外暴露。

---

## 2. 需求范围与优先级

| 编号 | 需求标题 | 优先级 | 涉及层 | 说明 |
|------|---------|--------|--------|------|
| TODO-01 | sync 最新交易日 upsert 写入 | **P0** | 后端/数据层 | 数据可靠性 BUG，影响当日数据准确性 |
| FEAT-02 | K 线悬停浮层增加数据更新时间 | **P1** | 后端+前端 | 用户体验增强，需后端透传新字段 |
| FEAT-03 | 下拉菜单按综合信号分组 | **P1** | 前端 | 纯前端改动，无后端依赖 |
| FEAT-04 | 局域网访问 + Token 鉴权 | **P1** | 后端+前端 | 安全功能，涉及中间件和前端 Token 管理 |

**优先级说明**：
- **P0**：数据正确性 BUG，必须优先修复，阻塞生产使用
- **P1**：功能增强，提升日常使用质量，本迭代全部实现
- **P2**：本迭代无 P2 需求

---

## 3. TODO-01：sync 最新交易日 upsert 写入

### 3.1 需求背景

**问题复现路径**：
1. 当日（例如：2026-03-19）数据同步启动，拉取到半日 K 线数据（如 12:00 前的盘中快照），写入 `kline_data` 表
2. 同步进程在盘中途中意外退出（断电、手动 kill、OpenD 断连等）
3. 当日下午收盘后，用户重启同步进程
4. 由于 `SyncEngine` 历史增量逻辑使用 `INSERT OR IGNORE`，当日日期的记录已存在，**全部跳过**
5. 结果：`kline_data` 中该股票当日记录**永久停留在盘中半日快照**，收盘价、最终成交量等数据永远不会被更新

**影响范围**：
- 受影响的是"最新一个交易日"的 K 线记录（往往也是用户最关心的数据）
- 技术指标（MACD/RSI/KDJ 等）均以 `close` 为基础，当日 `close` 错误将导致指标计算偏差
- 告警规则（迭代4）依赖当日 K 线数据，亦受影响

### 3.2 功能描述（用户视角）

用户重启同步进程后，当日股票的 K 线数据能够自动更新为最新的完整数据（收盘后为最终收盘数据，盘中为最新实时快照），而不是停留在上次中断时的快照状态。

### 3.3 技术方案说明

区分两种写入场景：

| 场景 | 判断依据 | 写入策略 |
|------|---------|---------|
| **历史日期**（早于最新交易日的所有日期）| `time_key < 最新交易日` | 保持现有 `INSERT OR IGNORE`（历史数据不变） |
| **最新交易日**（当天或最近一个已收盘交易日）| `time_key == 最新交易日` | 改为 `INSERT OR REPLACE`（upsert 覆盖写） |

**最新交易日的判定逻辑**：
- 定义为「拉取到的 K 线数据中，`time_key` 最大（最晚）的那一条记录所在日期」
- 或由 `trading_calendar` 表查询「当前日期或最近已过的交易日」
- 两种判定方式均可，取较宽松者（即：只要是最近一个交易日都用 upsert）

**`kline_data.updated_at` 字段**：
- 现有表结构中如无 `updated_at` 字段，本次迁移时新增
- upsert 写入时，`updated_at` 更新为当前时间戳（UTC，格式 `YYYY-MM-DD HH:MM:SS`）
- 历史 INSERT OR IGNORE 写入保持原有 `fetched_at` 不变（`updated_at` 在 INSERT 时等于 `fetched_at`，后续 REPLACE 时才更新）

### 3.4 交互说明

- 此需求无前端交互变更
- `updated_at` 字段为 FEAT-02 的数据基础，需同步实现

### 3.5 数据库 Schema 变更

`kline_data` 表新增字段（迁移兼容）：

```sql
-- 新增 updated_at 字段（已有行默认取 fetched_at 值）
ALTER TABLE kline_data ADD COLUMN updated_at TEXT;
UPDATE kline_data SET updated_at = fetched_at WHERE updated_at IS NULL;
```

迁移方式：在 `db/schema.py` 的 `init_db()` 函数中，检测字段是否存在，不存在则执行 `ALTER TABLE ADD COLUMN`（不重建表，向后兼容）。

### 3.6 验收标准

| # | 验收条件 |
|---|---------|
| AC-01 | 模拟盘中半日数据写入（手动构造 14:00 的 close 价格写入 `kline_data`）→ 停止同步 → 重新执行 sync → 验证该日记录的 `close` 字段已被覆盖为新拉取的值 |
| AC-02 | 历史日期（非最新交易日）的 K 线记录，`INSERT OR IGNORE` 行为不变，不发生数据覆写 |
| AC-03 | `kline_data` 表中每条记录均有 `updated_at` 值，upsert 写入后 `updated_at` 时间戳较 `fetched_at` 更晚 |
| AC-04 | 迭代1/2/3/4 的全部验收标准不受影响（无回归） |

### 3.7 注意事项

- `INSERT OR REPLACE` 在 SQLite 中是先删后插，`id`（autoincrement 主键）会改变。需确认 `kline_data` 表的主键机制，若有外键关联则需评估影响（当前设计无外键关联，可安全替换）
- 幂等性保障：同一天的同步多次执行，结果应收敛为最新一次拉取的数据，不出现重复行
- `updated_at` 字段的 `migrate` 子命令：`python main.py migrate` 已在 v0.4.0 实现，本次迁移逻辑追加到该流程中

---

## 4. FEAT-02：K 线图悬停浮层增加数据更新时间

### 4.1 需求背景

当前 K 线图 tooltip（鼠标悬停浮层）显示：日期、开盘价、收盘价、最高价、最低价、成交量等信息。

**用户痛点**：
- 盘中实时同步一次后，用户无从判断当前图表数据是盘中快照还是收盘终值
- 当日 K 线数据存在"半日数据"情况时（TODO-01 修复前的遗留数据，或 TODO-01 修复后盘中查看），tooltip 无任何时间戳提示

**价值**：增加"数据更新时间"后，用户可直观判断数据新鲜度，避免将盘中快照误判为收盘最终数据，提高决策可靠性。

### 4.2 功能描述（用户视角）

在 K 线图任意蜡烛上悬停时，tooltip 浮层末尾新增一行：

```
数据更新：2026-03-19 16:32:05
```

显示该 K 线条目最近一次写入/更新的时间（即 `kline_data.updated_at`）。收盘后同步完整的 K 线，该时间戳通常在当日 15:30~18:00 之间；若数据为盘中快照（进程意外中断后重启，处于盘中时段），则时间戳在交易时段内，用户可据此判断数据完整性。

### 4.3 交互说明

#### 后端变更

**`/api/kline/{code}` 接口返回字段扩展**：

在 `bars` 数组的每个对象中，新增 `updated_at` 字段：

```json
{
  "bars": [
    {
      "time_key": "2026-03-19",
      "open": 1820.0,
      "close": 1838.5,
      "high": 1845.0,
      "low": 1815.0,
      "volume": 2340000,
      "updated_at": "2026-03-19 16:32:05"
    }
  ]
}
```

- 若 `updated_at` 字段为 NULL（历史旧数据迁移前遗留），API 返回 `null`，前端不显示该行
- `updated_at` 格式：`YYYY-MM-DD HH:MM:SS`（北京时间，与数据库存储一致）

#### 前端变更（`web/src/components/MainChart`）

在 ECharts tooltip 的 `formatter` 中，追加更新时间行：

```
日期：2026-03-19
开盘：1820.0  收盘：1838.5
最高：1845.0  最低：1815.0
成交量：234.0万手
─────────────────
数据更新：2026-03-19 16:32:05   ← 新增
```

- 当 `updated_at` 为 `null` 时，不显示"数据更新"行（不出现"null"字样）
- 仅在主图（K 线蜡烛图）tooltip 中显示，副图（MACD/RSI/KDJ）的 tooltip 不需要添加此字段
- 时间显示精度：精确到秒（`YYYY-MM-DD HH:MM:SS`）

### 4.4 验收标准

| # | 验收条件 |
|---|---------|
| AC-01 | 调用 `/api/kline/SH.600519` API，返回的 `bars` 中每个对象包含 `updated_at` 字段，值为有效时间字符串或 `null` |
| AC-02 | 在 Web 页面悬停 K 线蜡烛条，tooltip 末尾显示"数据更新：YYYY-MM-DD HH:MM:SS" |
| AC-03 | 对于 `updated_at` 为 `null` 的历史数据，tooltip 中不出现"数据更新"行 |
| AC-04 | 副图（MACD/RSI/KDJ）的 tooltip 不受影响，不出现 `updated_at` 字段 |
| AC-05 | 同步完成后（TODO-01 upsert），当日最新 K 线的 `updated_at` 时间戳在 tooltip 中正确展示 |

### 4.5 注意事项

- 本需求依赖 TODO-01 中 `kline_data.updated_at` 字段的新增，两者应同迭代实现
- 不在历史所有 K 线上强制显示时间（旧数据 `updated_at` 为 null 时不显示），避免显示大量"null"误导用户
- API 层使用 `AdjustmentService` 封装，需确认 `updated_at` 字段在动态前复权计算后的透传路径（`updated_at` 无需参与复权计算，直接原样透传即可）

---

## 5. FEAT-03：首页股票下拉菜单按综合信号分组

### 5.1 需求背景

当前首页（`/`）股票选择下拉菜单，将 watchlist 中所有股票平铺罗列，配色已在迭代4实现（多头红色、空头绿色字体）。

**用户痛点**：
- 关注股票增多后，下拉菜单变长，难以快速找到特定方向的股票
- 用户习惯先确定"今天想看多头方向还是空头方向"，再在对应分组中挑选具体股票
- 即使有颜色区分，视觉上仍需逐条扫描，认知负担较高

**价值**：按综合信号分组后（多头/空头/中性），用户可直接跳转到感兴趣方向的分组，减少视觉扫描成本，提升选股效率。

### 5.2 功能描述（用户视角）

首页股票下拉菜单（`<select>` 元素）按综合信号将股票分为三组，使用 HTML 原生 `<optgroup>` 实现：

```
┌─ 🔴 多头（Bullish）─────────────────
│   SH.600519 贵州茅台
│   HK.00700  腾讯控股
├─ 🟢 空头（Bearish）─────────────────
│   SZ.000858 五粮液
├─ ⚖️ 中性（Neutral）─────────────────
│   SH.600036 招商银行
│   US.AAPL   苹果
└─────────────────────────────────────
```

- 分组标签名称：
  - `🔴 多头（Bullish）`（红色系，A股红涨配色）
  - `🟢 空头（Bearish）`（绿色系，A股绿跌配色）
  - `⚖️ 中性（Neutral）`（默认色）
- 无信号（API 未返回综合信号数据）的股票归入"中性"分组

### 5.3 交互说明

#### 数据来源

综合信号（bullish/bearish/neutral）已由现有 `/api/watchlist/summary` 接口提供，每只股票包含 `overall_signal` 字段。

无需新增后端 API。

#### 前端实现（`web/src/pages/StockAnalysis`）

将原有 `<option>` 平铺渲染，改为三个 `<optgroup>` 分组渲染：

```jsx
<select>
  <optgroup label="🔴 多头（Bullish）">
    {bullishStocks.map(s => <option key={s.code} value={s.code}>{s.code} {s.name}</option>)}
  </optgroup>
  <optgroup label="🟢 空头（Bearish）">
    {bearishStocks.map(s => <option key={s.code} value={s.code}>{s.code} {s.name}</option>)}
  </optgroup>
  <optgroup label="⚖️ 中性（Neutral）">
    {neutralStocks.map(s => <option key={s.code} value={s.code}>{s.code} {s.name}</option>)}
  </optgroup>
</select>
```

#### 配色规范（延续迭代4裁定）

| 分组 | option 字体颜色 | 说明 |
|------|--------------|------|
| 多头（Bullish）| 红色（`#e74c3c` 或系统红）| A股红涨配色 |
| 空头（Bearish）| 绿色（`#27ae60` 或系统绿）| A股绿跌配色 |
| 中性（Neutral）| 默认文字色 | 无信号方向 |

> **注意**：`<optgroup>` 的 `label` 属性在各浏览器中样式限制较多，颜色配置以 `<option>` 的 CSS `color` 属性为主，组标题颜色视浏览器支持程度兼容处理。

#### 分组顺序约定

- 固定顺序：多头 → 空头 → 中性
- 若某分组为空（如当日无空头信号股票），该 `<optgroup>` 不渲染（不出现空的分组标签）

#### 边界处理

- 页面初始加载时，`/api/watchlist/summary` 尚未返回，下拉菜单暂时展示所有股票（平铺，不分组），待数据加载完成后重新渲染为分组视图
- watchlist 为空时，下拉菜单显示"暂无关注股票"提示
- 若某股票在 `/api/watchlist/summary` 中无 `overall_signal` 字段或字段值为 null，归入中性分组

### 5.4 验收标准

| # | 验收条件 |
|---|---------|
| AC-01 | 首页下拉菜单显示三个分组（多头/空头/中性），分组内股票按原有顺序排列 |
| AC-02 | 各分组内股票的字体颜色符合配色规范（多头红色、空头绿色、中性默认） |
| AC-03 | 空分组不显示（如无空头股票，则无"空头"组标签） |
| AC-04 | 切换股票功能不受影响（选择任意股票后，K 线图正确更新） |
| AC-05 | 页面初次加载时，分组数据未就绪时不出现白屏或报错 |

### 5.5 注意事项

- `<optgroup>` 为 HTML 原生元素，无需第三方组件库，直接在 JSX 中使用
- 迭代4已实现 option 红绿字体颜色配置，本次需确认 optgroup 分组后颜色配置是否沿用原有实现方式（class 或 style），不回归
- 不引入自定义下拉组件（如 react-select），维持原生 `<select>`，保持简洁性

---

## 6. FEAT-04：局域网访问 + Token 鉴权

### 6.1 需求背景

当前 Web 服务绑定 `127.0.0.1:8000`，只能在本机浏览器访问。

**用户需求**：
- 在书房电脑采集数据的同时，希望能在客厅沙发上用手机/iPad 查看 K 线图
- 家庭局域网内多设备访问（电脑、手机、平板），无需每次到书房开浏览器
- 局域网内开放访问的同时，防止意外暴露（如 VLAN 穿透、误配端口转发），希望有基础的 Token 校验保护

**约束**：
- 纯个人工具，无多用户需求，Token 为静态固定值（无动态登录）
- 本机回环地址（`127.0.0.1`）访问豁免鉴权，保证本地开发调试和内部服务调用不受影响
- 前端静态页面和 API 接口统一鉴权

### 6.2 功能描述（用户视角）

**开启局域网访问后**（在 `.env` 配置 `WEB_HOST=0.0.0.0` 和 `WEB_ACCESS_TOKEN=你的密钥`）：

1. **首次访问**：在手机浏览器输入 `http://192.168.1.100:8000/?token=你的密钥`，页面正常加载
2. **后续访问**：手机浏览器记住了 token（存入 localStorage），直接访问 `http://192.168.1.100:8000/` 也能正常显示，无需每次带 token 参数
3. **Token 错误**：输入错误 token 时，返回 403 页面，提示"访问未授权"
4. **本机访问**：`http://127.0.0.1:8000/` 永远不需要 token，开发调试不受影响

### 6.3 交互说明

#### 后端：FastAPI 中间件鉴权

在 `api/main.py` 中新增 `TokenAuthMiddleware`（ASGI 中间件）：

**鉴权规则矩阵**：

| 请求来源 IP | `WEB_ACCESS_TOKEN` 配置状态 | 是否需要鉴权 |
|------------|--------------------------|------------|
| `127.0.0.1`（本机回环） | 任意 | **豁免**，直接放行 |
| `::1`（IPv6 本机） | 任意 | **豁免**，直接放行 |
| 其他局域网 IP | 未配置（空值）| **豁免**，视为未开启鉴权 |
| 其他局域网 IP | 已配置（非空值）| **需要鉴权** |

**Token 传递方式（支持任一方式）**：

| 请求类型 | Token 传递方式 | 优先级 |
|---------|--------------|--------|
| 前端页面请求（`text/html`）| URL query param `?token=<值>` | 主要方式 |
| API 请求（`application/json`）| 请求头 `X-Access-Token: <值>` | 首选 |
| API 请求（降级方式）| URL query param `?token=<值>` | 兼容方式 |

**鉴权中间件伪代码**：

```
TokenAuthMiddleware.dispatch(request):
    if client_ip in (127.0.0.1, ::1):
        return await call_next(request)   # 本机豁免

    if WEB_ACCESS_TOKEN is empty:
        return await call_next(request)   # 未配置 token，不启用鉴权

    token = request.headers.get("X-Access-Token") \
            or request.query_params.get("token")

    if token == WEB_ACCESS_TOKEN:
        return await call_next(request)   # 鉴权通过

    # 鉴权失败
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(403_page_html, status_code=403)
    else:
        return JSONResponse({"detail": "Unauthorized"}, status_code=403)
```

#### 前端：Token 持久化管理

在 `web/src/` 新增 `utils/auth.ts`（或 `auth.js`）模块：

**Token 存取逻辑**：

1. **页面加载时**：检查 URL 中是否有 `?token=<值>`
   - 有：将 token 存入 `localStorage['access_token']`，从 URL 中移除 token 参数（避免 token 出现在浏览器历史记录中），然后继续加载页面
   - 无：从 `localStorage['access_token']` 取出已存 token

2. **所有 API 请求**：在请求头中自动附加 `X-Access-Token: <token值>`（通过全局 axios/fetch 拦截器或统一 `apiClient` 封装）

3. **token 为空时**：不附加鉴权 header，正常发请求（兼容本机访问和未配置鉴权场景）

4. **403 响应处理**：收到 403 时，前端显示友好提示（如弹出提示"访问已过期或未授权，请检查访问链接中的 token 参数"）

**403 错误页面设计**（后端返回的 HTML）：

```
┌─────────────────────────────────────────┐
│                                         │
│    🔒  访问未授权                        │
│                                         │
│    请在 URL 中附加正确的访问令牌：         │
│    http://[IP]:8000/?token=你的密钥      │
│                                         │
│    如需帮助，请联系系统管理员。            │
│                                         │
└─────────────────────────────────────────┘
```

#### 配置项（`.env` 新增）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_HOST` | `127.0.0.1` | Web 服务监听地址。改为 `0.0.0.0` 开放局域网访问 |
| `WEB_ACCESS_TOKEN` | `（空）` | 访问令牌。留空则不启用鉴权，填写任意字符串启用 |

> **安全说明**：`WEB_ACCESS_TOKEN` 不等于"生产级安全"，仅作为个人工具的基础防护。不建议通过公网访问此服务。

#### `.env.example` 新增示例

```dotenv
# ===== 迭代5新增配置 =====

# --- 局域网访问 ---
# 改为 0.0.0.0 开放局域网访问，默认 127.0.0.1 仅本机
WEB_HOST=127.0.0.1

# 访问令牌（留空不启用鉴权，填写后所有非本机访问均需此 token）
WEB_ACCESS_TOKEN=
```

#### 启动方式更新

生产模式启动命令更新（`deploy/start.sh` 和文档）：

```bash
# 读取 .env 中的 WEB_HOST，默认 127.0.0.1
WEB_HOST=${WEB_HOST:-127.0.0.1}
./env_quant/bin/uvicorn api.main:app --host ${WEB_HOST} --port 8000
```

### 6.4 验收标准

| # | 验收条件 |
|---|---------|
| AC-01 | 配置 `WEB_HOST=0.0.0.0`，`WEB_ACCESS_TOKEN=test123` 后，在同一局域网内手机浏览器访问 `http://[服务器IP]:8000/?token=test123`，页面正常加载 |
| AC-02 | 手机浏览器加载后，localStorage 中存有 `access_token` 值，后续刷新页面（不带 token 参数）仍可正常访问 |
| AC-03 | 使用错误 token 访问 `http://[服务器IP]:8000/?token=wrong`，返回 403 页面，显示友好错误提示 |
| AC-04 | 访问 `http://127.0.0.1:8000/`（本机回环，不带 token）时，页面正常加载，不出现 403 |
| AC-05 | `WEB_ACCESS_TOKEN` 留空时，任意 IP 均可不带 token 访问，行为与迭代4相同 |
| AC-06 | API 请求（`/api/kline/SH.600519`）在携带正确 `X-Access-Token` header 时返回 200，不携带时从局域网访问返回 403 |
| AC-07 | URL 中的 token 参数在存入 localStorage 后，从地址栏消失（不出现在浏览器历史记录中） |
| AC-08 | `WEB_HOST` 默认值为 `127.0.0.1`，未配置时服务仅本机可访问，与迭代4行为相同 |

### 6.5 注意事项

- `WEB_HOST` 变量需在 `config/settings.py` 中读取，并通过 `deploy/start.sh` 传递给 uvicorn 的 `--host` 参数
- 客户端 IP 的获取需处理反向代理场景（如 nginx），应读取 `X-Forwarded-For` 头（仅信任已知代理），不过本工具通常直接暴露，直接读 `request.client.host` 即可
- IPv6 本机地址 `::1` 应与 `127.0.0.1` 同等豁免
- 静态文件（前端 `dist/`）在生产模式下由 FastAPI StaticFiles 挂载，中间件对静态文件请求同样生效（页面加载需带 token）
- token 传递到 URL 后，浏览器书签会带 token，这是预期行为（个人工具可接受）；从 URL 移除 token 只是为了防止 token 在浏览器历史记录中大量堆积

---

## 7. 不做什么（Out of Scope）

| 不做 | 原因 |
|------|------|
| 自动交易、下单、报价 | 系统核心约束，严禁 |
| 动态 token 登录（用户名/密码） | 个人工具，静态 token 已足够 |
| HTTPS/SSL 证书 | 局域网场景风险可控，HTTPS 配置复杂度高，超出本迭代范围 |
| 多用户 token 管理 | 个人工具，单一 token 足够 |
| 历史 K 线 `updated_at` 批量回填（精确时间） | 历史数据无法追溯真实入库时间，null 值不显示处理已足够 |
| 副图（MACD/RSI/KDJ）tooltip 增加 `updated_at` | 副图与主图共享同一交易日数据，主图已显示足够信息，副图重复显示价值低 |
| `<optgroup>` 自定义样式（颜色/字体）| 浏览器对 optgroup 样式支持极差，仅保证 option 字体颜色，不强制要求 optgroup label 样式 |
| 基本面数据、备用数据源、归档、告警推送 | 这些是迭代4内容，迭代5不涉及 |

---

## 8. 依赖关系

```
TODO-01（updated_at 字段新增）
    ↓ 依赖（数据基础）
FEAT-02（tooltip 显示 updated_at）

FEAT-03（下拉分组）
    ← 无外部依赖，纯前端改动

FEAT-04（鉴权）
    ← 后端中间件 + 前端 auth.ts，相互独立
```

TODO-01 与 FEAT-02 存在依赖关系，应先实现 TODO-01；其他三项可并行开发。

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| `INSERT OR REPLACE` 改变主键 ID，影响下游查询 | 低 | 中 | 当前设计中 `kline_data` 无外键依赖，影响可控；开发前确认 |
| 浏览器对 `<optgroup>` 颜色样式支持不一致 | 高 | 低 | 降级方案：组标题用 emoji 区分（已设计），option 颜色已有方案，不强依赖 optgroup 颜色 |
| 局域网 IP 变化导致已存 token 失效 | 低 | 低 | token 存入 localStorage 与 IP 无关，IP 变化只影响浏览器书签地址，token 值不失效 |
| 客户端 IP 获取在 Docker/代理环境下异常 | 低 | 中 | 当前部署为直接 uvicorn，无代理，直接读 `request.client.host` 即可 |
| `ALTER TABLE ADD COLUMN` 在大数据量时慢 | 低 | 低 | SQLite `ADD COLUMN` 为元数据操作，无论数据量大小均为常数时间，无风险 |

---

## 10. 数据库变更汇总

| 表名 | 操作 | 变更内容 |
|------|------|---------|
| `kline_data` | **新增字段** | `updated_at TEXT`（可为 null，已有行迁移时填充为 `fetched_at` 值） |
| 其余 7 张表 | 无变更 | — |

迁移方式：在 `python main.py migrate` 子命令中追加迁移步骤，向后兼容，不重建表，不影响现有数据。

---

## 11. 配置项汇总（`.env.example` 增量）

```dotenv
# ===== 迭代5新增配置 =====

# --- FEAT-04：局域网访问 ---
# Web 服务监听地址，改为 0.0.0.0 开放局域网，默认 127.0.0.1 仅本机
WEB_HOST=127.0.0.1
# 访问令牌（留空不启用鉴权），建议设置为随机字符串（如 openssl rand -hex 16）
WEB_ACCESS_TOKEN=
```

---

## 12. 非功能需求

| 项目 | 要求 | 说明 |
|------|------|------|
| 鉴权中间件性能 | 每次请求增加 < 1ms 延迟 | 仅做字符串比较和 IP 判断，无数据库查询 |
| `updated_at` 字段存储 | UTC 时间，`YYYY-MM-DD HH:MM:SS` 格式 | 与现有 `fetched_at` 格式一致 |
| 局域网延迟 | 页面加载 < 2 秒（同一局域网 100Mbps） | 无新的大数据量 API 调用 |
| 迁移向后兼容 | `ALTER TABLE ADD COLUMN` 不影响现有数据 | 已有行 `updated_at` 从 null 更新为 `fetched_at` 值 |
| 虚拟环境 | 本迭代无新增第三方依赖 | 无需 `pip install` 新包 |

---

## 13. 验收标准汇总

### TODO-01 验收
- AC-01：重启同步后最新交易日数据被覆盖更新（upsert 生效）
- AC-02：历史日期数据不受影响（INSERT OR IGNORE 保持）
- AC-03：`updated_at` 字段正确维护

### FEAT-02 验收
- AC-01~AC-05：tooltip 正确显示/隐藏更新时间戳

### FEAT-03 验收
- AC-01~AC-05：下拉菜单三分组正确渲染、配色正确

### FEAT-04 验收
- AC-01~AC-08：局域网访问、鉴权、豁免、Token 持久化全链路通过

### 通用回归验收
- 迭代1/2/3/4 的所有验收标准继续通过，无回归

---

## 14. 开发建议顺序

1. **TODO-01**（数据层，后端）：最高优先级，先修复数据可靠性问题，并为 FEAT-02 打下基础
2. **FEAT-02**（后端 API + 前端 tooltip）：依赖 TODO-01 完成后启动
3. **FEAT-04**（后端中间件 + 前端 auth.ts）：与 FEAT-02 并行开发，独立无依赖
4. **FEAT-03**（纯前端）：最简单，可与上述任意需求并行开发

---

*文档由 PM 输出，版本 v5.0，2026-03-19*
*核心决策：①TODO-01 采用"按日期区分写入策略"，历史日期 INSERT OR IGNORE，最新交易日 INSERT OR REPLACE，精准修复问题且不影响历史数据；②FEAT-02 `updated_at` 为 null 时不显示，避免界面出现 null 字样；③FEAT-03 使用 HTML 原生 `<optgroup>`，不引入自定义下拉组件；④FEAT-04 本机回环豁免鉴权，`WEB_ACCESS_TOKEN` 为空时不启用鉴权，默认行为与前序迭代完全兼容*
