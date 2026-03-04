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
                CHECK(status IN ('open','filling','filled','failed')),
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
        # 迁移：为旧版 adjust_factors 表补充 B 列（幂等）
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(adjust_factors)").fetchall()
        }
        if "forward_factor_b" not in existing:
            conn.execute(
                "ALTER TABLE adjust_factors ADD COLUMN forward_factor_b REAL NOT NULL DEFAULT 0"
            )
        if "backward_factor_b" not in existing:
            conn.execute(
                "ALTER TABLE adjust_factors ADD COLUMN backward_factor_b REAL NOT NULL DEFAULT 0"
            )
        conn.commit()
    finally:
        conn.close()
