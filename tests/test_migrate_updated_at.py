"""
tests/test_migrate_updated_at.py — 迭代5迁移路径测试

覆盖：
  T-MIGRATE-01：模拟旧库（无 updated_at 列），执行 init_db() 迁移，验证列被正确添加
  T-MIGRATE-02：迁移后执行 upsert_many()，无 OperationalError 抛出

背景：v0.4.0 旧库 kline_data 表无 updated_at 列。
init_db() 须包含迁移块将其补入，否则 upsert_many() 的
`INSERT INTO kline_data (..., updated_at) VALUES (...)` 会抛出 OperationalError。
"""

import os
import sqlite3
import tempfile
import pytest

# ---------------------------------------------------------------------------
# 工具：构造模拟旧版库（v0.4.0，kline_data 无 updated_at 列）
# ---------------------------------------------------------------------------

# 旧版 kline_data DDL（无 updated_at）
OLD_KLINE_DATA_DDL = """
CREATE TABLE kline_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code      TEXT NOT NULL,
    period          TEXT NOT NULL CHECK(period IN ('1D','1W','1M')),
    trade_date      TEXT NOT NULL,
    open            REAL NOT NULL,
    high            REAL NOT NULL,
    low             REAL NOT NULL,
    close           REAL NOT NULL,
    volume          INTEGER NOT NULL,
    turnover        REAL,
    pe_ratio        REAL,
    pb_ratio        REAL,
    ps_ratio        REAL,
    turnover_rate   REAL,
    last_close      REAL,
    is_valid        INTEGER NOT NULL DEFAULT 1 CHECK(is_valid IN (0,1)),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (stock_code, period, trade_date)
);
"""

OLD_STOCKS_DDL = """
CREATE TABLE stocks (
    stock_code  TEXT PRIMARY KEY,
    market      TEXT NOT NULL,
    asset_type  TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    lot_size    INTEGER NOT NULL DEFAULT 1,
    currency    TEXT NOT NULL,
    name        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def make_old_db() -> tuple[sqlite3.Connection, str]:
    """创建模拟 v0.4.0 旧版数据库（kline_data 无 updated_at 列）。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=OFF;")  # 旧库无 FK 强制
    conn.executescript(OLD_STOCKS_DDL + OLD_KLINE_DATA_DDL)
    conn.commit()
    return conn, path


def get_column_names(conn: sqlite3.Connection, table: str) -> set:
    """返回指定表的所有列名集合。"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


# ---------------------------------------------------------------------------
# T-MIGRATE-01：init_db() 迁移后 updated_at 列被正确添加
# ---------------------------------------------------------------------------

class TestMigrateUpdatedAt:

    def setup_method(self):
        self.conn, self.db_path = make_old_db()

    def teardown_method(self):
        self.conn.close()
        os.unlink(self.db_path)

    def test_T_MIGRATE_01_old_db_missing_updated_at(self):
        """前置确认：旧库 kline_data 确实没有 updated_at 列。"""
        cols = get_column_names(self.conn, "kline_data")
        assert "updated_at" not in cols, \
            "旧库不应包含 updated_at 列（测试环境构造错误）"

    def test_T_MIGRATE_01_init_db_adds_updated_at(self):
        """T-MIGRATE-01：对旧库执行 init_db()，验证 updated_at 列被添加。"""
        self.conn.close()  # 释放旧连接，让 init_db 独占
        from db.schema import init_db
        init_db(self.db_path)
        # 重新打开验证
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cols = get_column_names(conn, "kline_data")
            assert "updated_at" in cols, \
                "init_db() 迁移后 kline_data 应包含 updated_at 列"
        finally:
            conn.close()
        self.conn = sqlite3.connect(self.db_path)  # 恢复以备 teardown

    def test_T_MIGRATE_01_init_db_idempotent(self):
        """T-MIGRATE-01 幂等性：对已有 updated_at 的库再次执行 init_db() 不报错。"""
        self.conn.close()
        from db.schema import init_db
        init_db(self.db_path)  # 第一次（迁移）
        init_db(self.db_path)  # 第二次（幂等，不报错）
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cols = get_column_names(conn, "kline_data")
            assert "updated_at" in cols
        finally:
            conn.close()
        self.conn = sqlite3.connect(self.db_path)

    # -----------------------------------------------------------------------
    # T-MIGRATE-02：迁移后 upsert_many() 无 OperationalError
    # -----------------------------------------------------------------------

    def test_T_MIGRATE_02_upsert_after_migration_no_error(self):
        """T-MIGRATE-02：旧库迁移后执行 upsert_many()，不抛出 OperationalError。"""
        self.conn.close()
        from db.schema import init_db
        from db.repositories.kline_repo import KlineRepository
        from models.kline import KlineBar
        # 先插入一条 stock 记录（外键依赖）
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=OFF;")
        conn.commit()
        conn.close()

        init_db(self.db_path)

        repo = KlineRepository(self.db_path)
        bar = KlineBar(
            stock_code="TEST.SZ",
            period="1D",
            trade_date="2026-03-19",
            open=10.0,
            high=11.0,
            low=9.0,
            close=10.5,
            volume=100000,
        )
        try:
            repo.upsert_many([bar])
        except Exception as e:
            pytest.fail(f"迁移后 upsert_many() 不应抛出异常，但得到：{type(e).__name__}: {e}")
        self.conn = sqlite3.connect(self.db_path)

    def test_T_MIGRATE_02_upsert_updates_data_on_old_db(self):
        """T-MIGRATE-02 延伸：迁移后 upsert 覆盖写数据正确。"""
        self.conn.close()
        from db.schema import init_db
        from db.repositories.kline_repo import KlineRepository
        from models.kline import KlineBar

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=OFF;")
        conn.commit()
        conn.close()

        init_db(self.db_path)
        repo = KlineRepository(self.db_path)

        bar_v1 = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=100.0, volume=100000,
        )
        bar_v2 = KlineBar(
            stock_code="TEST.SZ", period="1D", trade_date="2026-03-19",
            open=10.0, high=11.0, low=9.0, close=105.0, volume=200000,
        )
        repo.insert_many([bar_v1])   # 初次写入（半日）
        repo.upsert_many([bar_v2])   # 覆盖写（全日）

        bars = repo.get_bars("TEST.SZ", "1D", "2026-03-19", "2026-03-19")
        assert len(bars) == 1
        assert bars[0].close == 105.0, f"upsert 后 close 应为 105.0，got {bars[0].close}"
        assert bars[0].volume == 200000
        self.conn = sqlite3.connect(self.db_path)

    def test_T_MIGRATE_02_old_data_updated_at_null_after_migration(self):
        """迁移后旧有数据 updated_at 为 NULL（ALTER ADD COLUMN 默认值行为），_row_to_bar 不崩溃。"""
        # 先在旧库写入一条数据（无 updated_at 列）
        self.conn.execute("PRAGMA foreign_keys=OFF;")
        self.conn.execute("""
            INSERT INTO kline_data
                (stock_code, period, trade_date, open, high, low, close, volume, is_valid)
            VALUES ('OLD.SZ', '1D', '2026-01-01', 10, 11, 9, 10.5, 50000, 1)
        """)
        self.conn.commit()
        self.conn.close()

        # 执行迁移
        from db.schema import init_db
        from db.repositories.kline_repo import KlineRepository
        init_db(self.db_path)

        # 查询旧数据，updated_at 应为 NULL，_row_to_bar 不崩溃
        repo = KlineRepository(self.db_path)
        bars = repo.get_bars("OLD.SZ", "1D", "2026-01-01", "2026-01-01")
        assert len(bars) == 1
        assert bars[0].updated_at is None, \
            f"旧数据迁移后 updated_at 应为 None，got: {bars[0].updated_at}"
        self.conn = sqlite3.connect(self.db_path)
