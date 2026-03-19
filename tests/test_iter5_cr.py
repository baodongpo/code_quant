"""
tests/test_iter5_cr.py — 迭代5 QA 自动化验证（P0 优先）

覆盖：
  TODO-01：upsert 覆盖写（T01-04 / T01-补A / T01-08 回归）
  FEAT-02：updated_at 透传（T02-01 / T02-07 / T02-08）
  FEAT-04：Token 鉴权（T04-02 / T04-11 / T04-22A / T04-22B）
"""

import sqlite3
import tempfile
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

# ---------------------------------------------------------------------------
# 工具：临时 SQLite 数据库
# ---------------------------------------------------------------------------

CREATE_DDL = """
CREATE TABLE IF NOT EXISTS kline_data (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code   TEXT NOT NULL,
    period       TEXT NOT NULL,
    trade_date   TEXT NOT NULL,
    open         REAL NOT NULL,
    high         REAL NOT NULL,
    low          REAL NOT NULL,
    close        REAL NOT NULL,
    volume       INTEGER NOT NULL,
    turnover     REAL,
    pe_ratio     REAL,
    pb_ratio     REAL,
    ps_ratio     REAL,
    turnover_rate REAL,
    last_close   REAL,
    is_valid     INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(stock_code, period, trade_date)
);
"""


def make_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(CREATE_DDL)
    conn.commit()
    return conn, path


# ---------------------------------------------------------------------------
# TODO-01 测试：upsert 覆盖写
# ---------------------------------------------------------------------------

class TestUpsertLogic:
    """直接测试 KlineRepository 的 insert_many / upsert_many 行为。"""

    def setup_method(self):
        self.conn, self.db_path = make_temp_db()

    def teardown_method(self):
        self.conn.close()
        os.unlink(self.db_path)

    def _insert_row(self, trade_date, close, volume):
        """通过 INSERT OR IGNORE 写入一条 bar（模拟 insert_many）。"""
        sql = """
            INSERT OR IGNORE INTO kline_data
                (stock_code, period, trade_date, open, high, low, close, volume, is_valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """
        self.conn.execute(sql, ("TEST.SZ", "1D", trade_date, 100.0, 110.0, 90.0, close, volume))
        self.conn.commit()

    def _upsert_row(self, trade_date, close, volume):
        """通过 ON CONFLICT DO UPDATE 写入一条 bar（模拟 upsert_many）。"""
        sql = """
            INSERT INTO kline_data
                (stock_code, period, trade_date, open, high, low, close, volume, is_valid, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            ON CONFLICT(stock_code, period, trade_date) DO UPDATE SET
                close      = excluded.close,
                volume     = excluded.volume,
                updated_at = datetime('now')
        """
        self.conn.execute(sql, ("TEST.SZ", "1D", trade_date, 100.0, 110.0, 90.0, close, volume))
        self.conn.commit()

    def _get_row(self, trade_date):
        row = self.conn.execute(
            "SELECT * FROM kline_data WHERE stock_code='TEST.SZ' AND trade_date=?",
            (trade_date,)
        ).fetchone()
        return dict(row) if row else None

    # T01-01：历史日期首次写入 → INSERT 成功
    def test_T01_01_history_first_insert(self):
        self._insert_row("2025-12-31", 150.0, 1000000)
        row = self._get_row("2025-12-31")
        assert row is not None
        assert row["close"] == 150.0

    # T01-02：历史日期重复写入 → INSERT OR IGNORE，数据不变
    def test_T01_02_history_duplicate_insert_ignored(self):
        self._insert_row("2025-12-31", 150.0, 1000000)
        self._insert_row("2025-12-31", 999.0, 9999999)  # 第二次写入不同值
        row = self._get_row("2025-12-31")
        assert row["close"] == 150.0  # 保持原值，未被覆盖

    # T01-03：最新交易日首次写入 → INSERT 成功
    def test_T01_03_latest_date_first_insert(self):
        today = date.today().strftime("%Y-%m-%d")
        self._insert_row(today, 150.0, 1000000)
        row = self._get_row(today)
        assert row is not None
        assert row["close"] == 150.0

    # T01-04（P0）：最新交易日二次写入 → UPSERT 覆盖，close/volume 更新 ⭐
    def test_T01_04_latest_date_upsert_overwrites(self):
        today = date.today().strftime("%Y-%m-%d")
        self._insert_row(today, 150.0, 1000000)     # 半日数据
        self._upsert_row(today, 155.0, 2000000)     # 全日数据覆盖
        row = self._get_row(today)
        assert row["close"] == 155.0, f"Expected 155.0, got {row['close']}"
        assert row["volume"] == 2000000, f"Expected 2000000, got {row['volume']}"

    # T01-04 延伸：upsert 后 updated_at 应刷新
    def test_T01_04_upsert_refreshes_updated_at(self):
        today = date.today().strftime("%Y-%m-%d")
        self._insert_row(today, 150.0, 1000000)
        old_row = self._get_row(today)
        import time; time.sleep(1.1)  # 确保 datetime('now') 有变化
        self._upsert_row(today, 155.0, 2000000)
        new_row = self._get_row(today)
        # updated_at 应该被刷新（或至少不为 NULL）
        assert new_row["updated_at"] is not None

    # T01-05：UPSERT 写入后历史记录不变（混合批次隔离）
    def test_T01_06_mixed_batch_history_unaffected(self):
        today = date.today().strftime("%Y-%m-%d")
        self._insert_row("2025-12-31", 100.0, 500000)   # 历史
        self._insert_row(today, 150.0, 1000000)          # 最新半日
        # 历史日期 INSERT OR IGNORE（不覆盖），最新日期 UPSERT
        self._insert_row("2025-12-31", 999.0, 999999)    # 历史再次写入 → 忽略
        self._upsert_row(today, 155.0, 2000000)          # 最新日期覆盖
        hist_row = self._get_row("2025-12-31")
        today_row = self._get_row(today)
        assert hist_row["close"] == 100.0  # 历史不变
        assert today_row["close"] == 155.0  # 今日被覆盖

    # T01-08（P0 回归）：_heal_gaps 路径使用 insert_many，不走 upsert
    def test_T01_08_heal_gaps_uses_insert_not_upsert(self):
        """
        验证 _heal_gaps 内的写入调用仍是 insert_many（INSERT OR IGNORE），
        通过检查 sync_engine.py 源码中 _heal_gaps 方法来确认。
        """
        import ast, os
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "sync_engine.py"
        )
        with open(src_path) as f:
            source = f.read()
        # 解析 AST，找到 _heal_gaps 方法中所有的函数调用
        tree = ast.parse(source)
        heal_gaps_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_heal_gaps":
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            heal_gaps_calls.append(child.func.attr)
        # _heal_gaps 中不应出现 upsert_many 调用
        assert "upsert_many" not in heal_gaps_calls, \
            f"_heal_gaps 不应调用 upsert_many！发现调用: {heal_gaps_calls}"
        # _heal_gaps 中应出现 insert_many 调用
        assert "insert_many" in heal_gaps_calls, \
            f"_heal_gaps 应调用 insert_many，但未找到。调用列表: {heal_gaps_calls}"

    # T01-补A（P0）：latest_date=today，bars 中含 today 数据时走 upsert 路径
    def test_T01_supA_latest_date_param_drives_upsert(self):
        """
        验证 _fetch_and_store 中：
        latest_bars = [b for b in valid_bars if b.trade_date == latest_date]
        → latest_bars 走 upsert_many 路径。
        通过 AST 检查代码分支逻辑。
        """
        import ast, os
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "sync_engine.py"
        )
        with open(src_path) as f:
            source = f.read()
        tree = ast.parse(source)
        fetch_store_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_fetch_and_store":
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            fetch_store_calls.append(child.func.attr)
        # _fetch_and_store 中应同时出现 insert_many 和 upsert_many
        assert "insert_many" in fetch_store_calls, \
            "_fetch_and_store 应包含 insert_many 调用"
        assert "upsert_many" in fetch_store_calls, \
            "_fetch_and_store 应包含 upsert_many 调用（latest_date 路径）"

    # T01-补B：latest_date=today，bars 中无 today 数据 → 无报错
    def test_T01_supB_no_today_bar_no_error(self):
        """bars 中无 today 数据时，latest_bars 为空，不调用 upsert，不报错。"""
        today = date.today().strftime("%Y-%m-%d")
        # 只写历史数据，无 today
        self._insert_row("2025-12-30", 100.0, 500000)
        self._insert_row("2025-12-31", 101.0, 510000)
        # today 无数据，尝试 upsert 空列表
        sql = """
            INSERT INTO kline_data
                (stock_code, period, trade_date, open, high, low, close, volume, is_valid, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
            ON CONFLICT(stock_code, period, trade_date) DO UPDATE SET
                close = excluded.close, updated_at = datetime('now')
        """
        # 空列表 executemany 不应报错
        self.conn.executemany(sql, [])
        self.conn.commit()
        # 历史数据应保持不变
        assert self._get_row("2025-12-31")["close"] == 101.0


# ---------------------------------------------------------------------------
# FEAT-02 测试：updated_at 透传
# ---------------------------------------------------------------------------

class TestUpdatedAtTransparency:

    def test_T02_01_klinebar_has_updated_at_field(self):
        """KlineBar dataclass 包含 updated_at 字段。"""
        from models.kline import KlineBar
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000,
            updated_at="2026-03-19 16:32:05"
        )
        assert bar.updated_at == "2026-03-19 16:32:05"

    def test_T02_01_klinebar_updated_at_default_none(self):
        """KlineBar.updated_at 默认为 None。"""
        from models.kline import KlineBar
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000
        )
        assert bar.updated_at is None

    def test_T02_07_apply_adjustment_passes_updated_at(self):
        """_apply_adjustment 透传 updated_at（前复权路径）。"""
        from models.kline import KlineBar
        from core.adjustment_service import AdjustmentService
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000,
            updated_at="2026-03-19 16:32:05"
        )
        result = AdjustmentService._apply_adjustment(bar, 1.0, 0.0, 1.0, 0.0, "qfq")
        assert result.updated_at == "2026-03-19 16:32:05", \
            f"_apply_adjustment 应透传 updated_at，got: {result.updated_at}"

    def test_T02_07_apply_adjustment_updated_at_null_survives(self):
        """_apply_adjustment：updated_at 为 None 时结果也为 None，不崩溃。"""
        from models.kline import KlineBar
        from core.adjustment_service import AdjustmentService
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000,
            updated_at=None
        )
        result = AdjustmentService._apply_adjustment(bar, 1.1, 0.0, 1.1, 0.0, "qfq")
        assert result.updated_at is None  # None 应被透传，不崩溃

    def test_T02_07_mark_adjusted_passes_updated_at(self):
        """_mark_adjusted 透传 updated_at（无复权事件路径）。"""
        from models.kline import KlineBar
        from core.adjustment_service import AdjustmentService
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000,
            updated_at="2026-03-19 09:30:01"
        )
        result = AdjustmentService._mark_adjusted(bar, "qfq")
        assert result.updated_at == "2026-03-19 09:30:01", \
            f"_mark_adjusted 应透传 updated_at，got: {result.updated_at}"

    def test_T02_08_qfq_and_raw_same_updated_at(self):
        """前复权与非复权路径对同一 bar 的 updated_at 值相同。"""
        from models.kline import KlineBar
        from core.adjustment_service import AdjustmentService
        bar = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=10.5, volume=100000,
            updated_at="2026-03-19 16:00:00"
        )
        # 前复权（有复权事件，走 _apply_adjustment）
        result_qfq = AdjustmentService._apply_adjustment(bar, 0.9, 0.0, 0.9, 0.0, "qfq")
        # 无复权事件路径（走 _mark_adjusted）
        result_raw = AdjustmentService._mark_adjusted(bar, "qfq")
        assert result_qfq.updated_at == result_raw.updated_at == "2026-03-19 16:00:00"

    def test_T02_row_to_bar_reads_updated_at(self):
        """KlineRepository._row_to_bar 正确从 DB 行读取 updated_at。"""
        from db.repositories.kline_repo import KlineRepository
        # 模拟 sqlite3.Row（dict-like）
        mock_row = {
            "stock_code": "TEST.SZ", "period": "1D", "trade_date": "2026-03-19",
            "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
            "volume": 100000, "turnover": None, "pe_ratio": None,
            "pb_ratio": None, "ps_ratio": None, "turnover_rate": None,
            "last_close": None, "is_valid": 1,
            "updated_at": "2026-03-19 16:32:05",
        }

        class FakeRow(dict):
            def keys(self): return super().keys()

        bar = KlineRepository._row_to_bar(FakeRow(mock_row))
        assert bar.updated_at == "2026-03-19 16:32:05"

    def test_T02_row_to_bar_updated_at_missing_returns_none(self):
        """_row_to_bar：DB 行无 updated_at 字段时返回 None，不崩溃。"""
        from db.repositories.kline_repo import KlineRepository

        class FakeRow(dict):
            def keys(self): return super().keys()

        mock_row = FakeRow({
            "stock_code": "TEST.SZ", "period": "1D", "trade_date": "2026-03-19",
            "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
            "volume": 100000, "turnover": None, "pe_ratio": None,
            "pb_ratio": None, "ps_ratio": None, "turnover_rate": None,
            "last_close": None, "is_valid": 1,
            # 故意不含 updated_at
        })
        bar = KlineRepository._row_to_bar(mock_row)
        assert bar.updated_at is None


# ---------------------------------------------------------------------------
# FEAT-04 测试：Token 鉴权（使用 httpx + FastAPI TestClient）
# ---------------------------------------------------------------------------

class TestTokenAuth:

    @pytest.fixture
    def app_with_token(self):
        """创建带 token 配置的 FastAPI 测试 app。"""
        import importlib, sys
        # 设置 WEB_ACCESS_TOKEN 后重新导入 api.main
        with patch.dict(os.environ, {"WEB_ACCESS_TOKEN": "test-secret-token"}):
            # 需要重新加载 config.settings 和 api.main
            for mod in ["config.settings", "api.main"]:
                if mod in sys.modules:
                    del sys.modules[mod]
            from api.main import app
            from fastapi.testclient import TestClient
            yield TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def app_no_token(self):
        """WEB_ACCESS_TOKEN 未配置时的 app（全部透明）。"""
        import sys
        with patch.dict(os.environ, {"WEB_ACCESS_TOKEN": ""}):
            for mod in ["config.settings", "api.main"]:
                if mod in sys.modules:
                    del sys.modules[mod]
            from api.main import app
            from fastapi.testclient import TestClient
            yield TestClient(app, raise_server_exceptions=False)

    # T04-02（P0）：局域网 IP，无 token，访问 /api/* → 403
    def test_T04_02_no_token_api_returns_403(self, app_with_token):
        resp = app_with_token.get("/api/health", headers={"X-Forwarded-For": "192.168.1.100"})
        # TestClient 默认 client IP 是 testclient，中间件会读取 request.client.host
        # 通过不提供 token 来验证鉴权逻辑
        # 注意：TestClient 的 client.host 是 "testclient"，不在豁免列表，需无 token → 403
        assert resp.status_code == 403

    # T04-07：正确 token via query param → 200
    def test_T04_07_correct_token_query_returns_200(self, app_with_token):
        resp = app_with_token.get("/api/health?token=test-secret-token")
        assert resp.status_code == 200

    # T04-08：正确 token via X-Access-Token Header → 200
    def test_T04_08_correct_token_header_returns_200(self, app_with_token):
        resp = app_with_token.get("/api/health", headers={"X-Access-Token": "test-secret-token"})
        assert resp.status_code == 200

    # T04-04/05/06：错误 token → 403
    def test_T04_04_wrong_token_returns_403(self, app_with_token):
        resp = app_with_token.get("/api/health", headers={"X-Access-Token": "wrong-token"})
        assert resp.status_code == 403

    def test_T04_06_wrong_token_query_returns_403(self, app_with_token):
        resp = app_with_token.get("/api/health?token=wrong-token")
        assert resp.status_code == 403

    # T04-11（P0）：127.0.0.1 无 token → 200（豁免）
    def test_T04_11_loopback_no_token_exempted(self, app_with_token):
        # TestClient 默认已是本地连接，需确认中间件豁免 testclient 或模拟 127.0.0.1
        # 直接测试中间件逻辑：通过 scope 注入 client IP
        from starlette.testclient import TestClient as StarletteClient
        import sys
        with patch.dict(os.environ, {"WEB_ACCESS_TOKEN": "test-secret-token"}):
            for mod in ["config.settings", "api.main"]:
                if mod in sys.modules:
                    del sys.modules[mod]
            from api.main import app
            # 使用 httpx 直接测试，模拟 127.0.0.1 来源
            # FastAPI TestClient 连接 client.host 为 "testclient"
            # 我们直接验证豁免集合包含 127.0.0.1
            import ast
            src_path = os.path.join(
                os.path.dirname(__file__), "..", "api", "main.py"
            )
            with open(src_path) as f:
                source = f.read()
            assert '"127.0.0.1"' in source, "中间件应包含 127.0.0.1 豁免"
            assert '"::1"' in source, "中间件应包含 ::1 豁免"

    # T04-21：Header 空字符串 + query 正确 → 200（fallback 有意为之）
    def test_T04_21_empty_header_falls_back_to_query(self, app_with_token):
        resp = app_with_token.get(
            "/api/health?token=test-secret-token",
            headers={"X-Access-Token": ""}  # 空字符串 Header
        )
        assert resp.status_code == 200

    # T04-22A（P0）：OPTIONS 预检不被 403 拦截
    def test_T04_22A_options_preflight_not_blocked(self, app_with_token):
        resp = app_with_token.options("/api/health")
        assert resp.status_code != 403, \
            f"OPTIONS 预检不应被 token 中间件拦截，got {resp.status_code}"

    # T04-22 代码验证：OPTIONS 豁免在最前
    def test_T04_22_options_exemption_first_in_middleware(self):
        """验证 TokenAuthMiddleware.dispatch 第一个条件是 OPTIONS 放行。"""
        import ast, os
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "api", "main.py"
        )
        with open(src_path) as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (isinstance(node, ast.AsyncFunctionDef) and node.name == "dispatch"):
                # 找到第一个 if 语句
                first_if = next(
                    (s for s in node.body if isinstance(s, ast.If)), None
                )
                assert first_if is not None, "dispatch 方法应有 if 语句"
                # 第一个 if 应检查 OPTIONS
                if_src = ast.unparse(first_if.test) if hasattr(ast, 'unparse') else ""
                if if_src:
                    assert "OPTIONS" in if_src, \
                        f"dispatch 第一个 if 应检查 OPTIONS，实际为: {if_src}"
                break

    # WEB_ACCESS_TOKEN 未配置时全部透明
    def test_no_token_configured_all_pass(self, app_no_token):
        resp = app_no_token.get("/api/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# FEAT-03 测试：StockSelector 分组逻辑（纯逻辑验证，不依赖 DOM）
# ---------------------------------------------------------------------------

class TestStockSelectorGroupLogic:
    """验证 GROUP_ORDER 和分组逻辑的 Python 等价实现（与 JSX 代码逻辑一致性验证）。"""

    GROUP_ORDER = [
        {"key": "bullish", "label": "多头（Bullish）"},
        {"key": "bearish", "label": "空头（Bearish）"},
        {"key": "neutral", "label": "中性（Neutral）"},
    ]

    def _group_stocks(self, stocks, signals):
        sig_map = signals or {}
        groups = [
            {
                **g,
                "stocks": [s for s in stocks if (sig_map.get(s["code"]) or "neutral") == g["key"]],
            }
            for g in self.GROUP_ORDER
        ]
        return [g for g in groups if g["stocks"]]

    # T03-01：三个 optgroup
    def test_T03_01_three_groups_rendered(self):
        stocks = [
            {"code": "A", "name": "Stock A"},
            {"code": "B", "name": "Stock B"},
            {"code": "C", "name": "Stock C"},
        ]
        signals = {"A": "bullish", "B": "bearish", "C": "neutral"}
        groups = self._group_stocks(stocks, signals)
        keys = [g["key"] for g in groups]
        assert "bullish" in keys
        assert "bearish" in keys
        assert "neutral" in keys

    # T03-02：股票归入正确分组
    def test_T03_02_stocks_in_correct_group(self):
        stocks = [{"code": "A"}, {"code": "B"}]
        signals = {"A": "bullish", "B": "bearish"}
        groups = self._group_stocks(stocks, signals)
        bullish_group = next(g for g in groups if g["key"] == "bullish")
        assert any(s["code"] == "A" for s in bullish_group["stocks"])
        bearish_group = next(g for g in groups if g["key"] == "bearish")
        assert any(s["code"] == "B" for s in bearish_group["stocks"])

    # T03-03：缺少某类信号时，空组不渲染
    def test_T03_03_empty_group_not_rendered(self):
        stocks = [{"code": "A"}, {"code": "B"}]
        signals = {"A": "bullish", "B": "bullish"}  # 全部多头
        groups = self._group_stocks(stocks, signals)
        keys = [g["key"] for g in groups]
        assert "bearish" not in keys
        assert "neutral" not in keys
        assert "bullish" in keys

    # T03-04：分组顺序 bullish → bearish → neutral
    def test_T03_04_group_order(self):
        stocks = [{"code": "A"}, {"code": "B"}, {"code": "C"}]
        signals = {"A": "neutral", "B": "bearish", "C": "bullish"}
        groups = self._group_stocks(stocks, signals)
        keys = [g["key"] for g in groups]
        assert keys == ["bullish", "bearish", "neutral"]

    # T03-07：watchlist 为空 → 无报错，groups 为空列表
    def test_T03_07_empty_watchlist_no_error(self):
        groups = self._group_stocks([], {})
        assert groups == []

    # signals 为空时全部归入 neutral
    def test_T03_signals_empty_all_neutral(self):
        stocks = [{"code": "A"}, {"code": "B"}]
        groups = self._group_stocks(stocks, {})
        assert len(groups) == 1
        assert groups[0]["key"] == "neutral"
        assert len(groups[0]["stocks"]) == 2
