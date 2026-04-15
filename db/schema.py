import sqlite3
import os


CREATE_STOCKS = """
CREATE TABLE IF NOT EXISTS stocks (
    stock_code      TEXT PRIMARY KEY,
    market          TEXT NOT NULL CHECK(market IN ('HK','US','A')),
    asset_type      TEXT NOT NULL CHECK(asset_type IN ('stock','ETF')),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    lot_size        INTEGER NOT NULL DEFAULT 1,
    currency        TEXT NOT NULL CHECK(currency IN ('HKD','USD','CNY')),
    name            TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_STOCKS_IDX = """
CREATE INDEX IF NOT EXISTS idx_stocks_active ON stocks(is_active);
"""

CREATE_KLINE_DATA = """
CREATE TABLE IF NOT EXISTS kline_data (
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
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (stock_code, period, trade_date),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);
"""

CREATE_KLINE_IDX = """
CREATE INDEX IF NOT EXISTS idx_kline_stock_period_date
    ON kline_data(stock_code, period, trade_date);
"""

CREATE_ADJUST_FACTORS = """
CREATE TABLE IF NOT EXISTS adjust_factors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code       TEXT NOT NULL,
    ex_date          TEXT NOT NULL,
    forward_factor   REAL NOT NULL,          -- 乘法系数 A
    forward_factor_b REAL NOT NULL DEFAULT 0, -- 加法偏移 B
    backward_factor  REAL NOT NULL,
    backward_factor_b REAL NOT NULL DEFAULT 0,
    factor_source    TEXT NOT NULL DEFAULT 'futu',
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (stock_code, ex_date),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);
"""

CREATE_ADJUST_IDX = """
CREATE INDEX IF NOT EXISTS idx_factors_stock_date
    ON adjust_factors(stock_code, ex_date);
"""

CREATE_TRADING_CALENDAR = """
CREATE TABLE IF NOT EXISTS trading_calendar (
    market          TEXT NOT NULL CHECK(market IN ('HK','US','SH','SZ')),
    trade_date      TEXT NOT NULL,
    is_trading_day  INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (market, trade_date)
);
"""

CREATE_CALENDAR_IDX = """
CREATE INDEX IF NOT EXISTS idx_calendar_trading
    ON trading_calendar(market, trade_date)
    WHERE is_trading_day = 1;
"""

CREATE_SYNC_METADATA = """
CREATE TABLE IF NOT EXISTS sync_metadata (
    stock_code      TEXT NOT NULL,
    period          TEXT NOT NULL CHECK(period IN ('1D','1W','1M')),
    first_sync_date TEXT,
    last_sync_date  TEXT,
    last_sync_ts    TEXT,
    sync_status     TEXT NOT NULL DEFAULT 'pending'
                    CHECK(sync_status IN ('pending','running','success','failed','partial')),
    rows_fetched    INTEGER DEFAULT 0,
    rows_inserted   INTEGER DEFAULT 0,
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (stock_code, period),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);
"""

CREATE_DATA_GAPS = """
CREATE TABLE IF NOT EXISTS data_gaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code  TEXT NOT NULL,
    period      TEXT NOT NULL CHECK(period IN ('1D','1W','1M')),
    gap_start   TEXT NOT NULL,
    gap_end     TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    filled_at   TEXT,
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open','filling','filled','failed','no_data')),
    skip_reason TEXT,
    UNIQUE (stock_code, period, gap_start, gap_end),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);
"""

CREATE_DATA_GAPS_IDX = """
CREATE INDEX IF NOT EXISTS idx_gaps_open
    ON data_gaps(stock_code, period)
    WHERE status = 'open';
"""

CREATE_SUBSCRIPTION_STATUS = """
CREATE TABLE IF NOT EXISTS subscription_status (
    stock_code      TEXT NOT NULL,
    period          TEXT NOT NULL CHECK(period IN ('1D','1W','1M')),
    is_subscribed   INTEGER NOT NULL DEFAULT 0 CHECK(is_subscribed IN (0,1)),
    subscribed_at   TEXT,
    unsubscribed_at TEXT,
    PRIMARY KEY (stock_code, period),
    FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
);
"""

ALL_DDLS = [
    CREATE_STOCKS,
    CREATE_STOCKS_IDX,
    CREATE_KLINE_DATA,
    CREATE_KLINE_IDX,
    CREATE_ADJUST_FACTORS,
    CREATE_ADJUST_IDX,
    CREATE_TRADING_CALENDAR,
    CREATE_CALENDAR_IDX,
    CREATE_SYNC_METADATA,
    CREATE_DATA_GAPS,
    CREATE_DATA_GAPS_IDX,
    CREATE_SUBSCRIPTION_STATUS,
]


def init_db(db_path: str) -> None:
    """初始化数据库，创建所有表和索引。"""
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        for ddl in ALL_DDLS:
            conn.execute(ddl)
        # 迁移：为旧版 stocks 表补充 name 列（幂等）
        stocks_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(stocks)").fetchall()
        }
        if "name" not in stocks_cols:
            try:
                conn.execute("ALTER TABLE stocks ADD COLUMN name TEXT")
                # SQLite DDL（ALTER TABLE）会隐式提交，name 列添加后已持久化。
                # 函数末尾 conn.commit() 主要用于 commit 后续 DML 操作（如有）。
            except sqlite3.OperationalError:
                pass  # 并发 init_db 时已由其他进程添加，忽略

        # 迁移：为旧版 adjust_factors 表补充 B 列（幂等）
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(adjust_factors)").fetchall()
        }
        if "forward_factor_b" not in existing:
            try:
                conn.execute(
                    "ALTER TABLE adjust_factors ADD COLUMN forward_factor_b REAL NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # 并发 init_db 时已由其他进程添加，忽略
        if "backward_factor_b" not in existing:
            try:
                conn.execute(
                    "ALTER TABLE adjust_factors ADD COLUMN backward_factor_b REAL NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # 并发 init_db 时已由其他进程添加，忽略
        if "factor_source" not in existing:
            try:
                conn.execute(
                    "ALTER TABLE adjust_factors ADD COLUMN factor_source TEXT NOT NULL DEFAULT 'futu'"
                )
            except sqlite3.OperationalError:
                pass  # 并发 init_db 时已由其他进程添加，忽略

        # 迁移：为旧版 kline_data 表补充 pb_ratio / ps_ratio 列（幂等）
        kline_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(kline_data)").fetchall()
        }
        for col, ddl in [
            ("pb_ratio",   "ALTER TABLE kline_data ADD COLUMN pb_ratio REAL"),
            ("ps_ratio",   "ALTER TABLE kline_data ADD COLUMN ps_ratio REAL"),
            ("updated_at", "ALTER TABLE kline_data ADD COLUMN updated_at TEXT"),
        ]:
            if col not in kline_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # 并发场景，已由其他进程添加

        # 迁移：为旧版 data_gaps 表补充 skip_reason 列，并更新 CHECK 约束（幂等）
        gaps_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(data_gaps)").fetchall()
        }
        if "skip_reason" not in gaps_cols:
            try:
                conn.execute("ALTER TABLE data_gaps ADD COLUMN skip_reason TEXT")
            except sqlite3.OperationalError:
                pass  # 并发场景，已由其他进程添加

        # 迁移：更新 data_gaps 表的 CHECK 约束以支持 'no_data' 状态
        # SQLite 不支持直接修改 CHECK 约束，需要重建表
        # 检查当前约束是否包含 'no_data'
        gaps_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='data_gaps'"
        ).fetchone()
        if gaps_schema and gaps_schema[0]:
            current_schema = gaps_schema[0]
            if "'no_data'" not in current_schema:
                # 需要重建表以更新 CHECK 约束
                logger = __import__('logging').getLogger(__name__)
                logger.info("Migrating data_gaps table: adding 'no_data' status to CHECK constraint")
                # 暂时禁用外键约束
                conn.execute("PRAGMA foreign_keys=OFF;")
                conn.executescript("""
                    -- 备份现有数据
                    CREATE TABLE IF NOT EXISTS data_gaps_backup AS SELECT * FROM data_gaps;

                    -- 删除旧表
                    DROP TABLE data_gaps;

                    -- 创建新表（包含 no_data 状态）
                    CREATE TABLE data_gaps (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code  TEXT NOT NULL,
                        period      TEXT NOT NULL CHECK(period IN ('1D','1W','1M')),
                        gap_start   TEXT NOT NULL,
                        gap_end     TEXT NOT NULL,
                        detected_at TEXT NOT NULL DEFAULT (datetime('now')),
                        filled_at   TEXT,
                        status      TEXT NOT NULL DEFAULT 'open'
                                    CHECK(status IN ('open','filling','filled','failed','no_data')),
                        skip_reason TEXT,
                        UNIQUE (stock_code, period, gap_start, gap_end),
                        FOREIGN KEY (stock_code) REFERENCES stocks(stock_code)
                    );

                    -- 恢复数据
                    INSERT INTO data_gaps (id, stock_code, period, gap_start, gap_end, detected_at, filled_at, status, skip_reason)
                    SELECT id, stock_code, period, gap_start, gap_end, detected_at, filled_at, status, skip_reason FROM data_gaps_backup;

                    -- 删除备份表
                    DROP TABLE data_gaps_backup;
                """)
                # 重建索引
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_gaps_open
                        ON data_gaps(stock_code, period)
                        WHERE status = 'open';
                """)
                # 重新启用外键约束
                conn.execute("PRAGMA foreign_keys=ON;")
                logger.info("data_gaps table migration complete: 'no_data' status added")

        conn.commit()
    finally:
        conn.close()
