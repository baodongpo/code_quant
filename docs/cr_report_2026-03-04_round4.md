# Code Review Report — Round 4

**审查日期**：2026-03-04
**基准报告**：`docs/cr_report_2026-03-04_round3.md`
**审查范围**：验证第三轮问题修复结果（除新问题 C 外）

---

## 一、第三轮问题修复验证

### 新问题 A：`_fetch_one_page_with_retry` 末尾缺兜底 `raise`
**修复状态**：✅ 正确

`kline_fetcher.py:129` 在循环结束后加入 `raise RuntimeError("unreachable")`，静态分析工具不再报告 missing return。

---

### 新问题 B：增量同步重复拉取最后一天
**修复状态**：✅ 正确

`sync_engine.py:117-120`，`last_sync_date` 取次日作为 `start_date`：

```python
elif meta.get("last_sync_date"):
    last = meta["last_sync_date"]
    y, m, d = last.split("-")
    start_date = (date(int(y), int(m), int(d)) + timedelta(days=1)).strftime("%Y-%m-%d")
```

`timedelta` 已在文件头 `from datetime import date, timedelta` 导入（`:2`），无遗漏。

**注意一个边界情况**：若上次同步日期恰好等于 `today`（即同一天重复运行），`start_date` 会变成明天，`fetch` 请求的 `start > end`。`KlineFetcher.fetch()` 在这种情况下会调用 `get_history_kline(start=明天, end=今天)`，富途 API 会返回空数据，`_fetch_one_page_with_retry` 返回 `[]`，`fetch()` 正常退出返回空列表，整个流程不会报错。行为正确，无需额外处理。

---

### 新问题 D：零值 falsy 过滤
**修复状态**：✅ 正确

`kline_fetcher.py:146-149` 四个字段全部改为 `is not None` 判断：

```python
turnover=float(row["turnover"]) if "turnover" in row and row["turnover"] is not None else None,
pe_ratio=float(row["pe_ratio"]) if "pe_ratio" in row and row["pe_ratio"] is not None else None,
turnover_rate=float(row["turnover_rate"]) if "turnover_rate" in row and row["turnover_rate"] is not None else None,
last_close=float(row["last_close"]) if "last_close" in row and row["last_close"] is not None else None,
```

`pe_ratio=0`、`turnover=0` 等合法零值现在可以正确写入。

---

### 新问题 E：`GapRepository.insert()` 死代码
**修复状态**：✅ 正确

`gap_repo.py` 中 `insert()` 方法已删除，文件仅保留 `get_open_gaps`、`mark_filling`、`mark_filled`、`mark_failed`、`upsert_gaps` 五个方法，无冗余代码。

---

## 二、遗留状态

| # | 状态 | 说明 |
|---|------|------|
| 新问题 C | **已知限制，保留** | 重试消耗双倍限频配额，已在 `rate_limiter.py` 注释中说明，watchlist 较小时无实际影响 |
| Q3 | **待联调** | `core/adjustment_service.py:89-93` 前复权因子累乘语义，需联调确认 |

---

## 三、本轮全量扫描结果

经过三轮迭代修复，未发现新问题。代码整体质量已达到可联调状态。

**联调前建议确认的唯一事项**：Q3，取一只有历史除权记录的股票（如 `SH.600519`），比对 `AdjustmentService.get_adjusted_klines()` 输出与富途 App 前复权价格，确认 `forward_factor` 语义后决定是否需要修改 `_calc_forward_multiplier`。
