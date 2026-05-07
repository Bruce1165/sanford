-- Migration: Create triple_screen_signals table
-- Scope: Triple-screen project only (isolated from neil_* / lao_ya_tou_* tables)
-- Safety: Non-destructive, idempotent

CREATE TABLE IF NOT EXISTS triple_screen_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    trade_date DATE NOT NULL,
    task_type TEXT NOT NULL,          -- backfill | daily
    trend_ok INTEGER NOT NULL DEFAULT 0,
    timing_ok INTEGER NOT NULL DEFAULT 0,
    entry_ok INTEGER NOT NULL DEFAULT 0,
    is_new_entry INTEGER NOT NULL DEFAULT 0,
    is_exit_ref INTEGER NOT NULL DEFAULT 0,
    entry_lookback_days INTEGER NOT NULL,
    stop_lookback_days INTEGER NOT NULL,
    timing_rsi_threshold REAL NOT NULL,
    entry_price REAL,
    exit_price REAL,
    close_price REAL,
    rsi14 REAL,
    weekly_macd_hist REAL,
    weekly_macd REAL,
    weekly_signal REAL,
    param_version TEXT NOT NULL,
    param_snapshot TEXT NOT NULL,     -- JSON string
    signal_biz_key TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pool_id) REFERENCES triple_screen_pool(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_triple_sig_biz_key
ON triple_screen_signals(signal_biz_key);

CREATE INDEX IF NOT EXISTS idx_triple_sig_code_date
ON triple_screen_signals(stock_code, trade_date);

CREATE INDEX IF NOT EXISTS idx_triple_sig_task_date
ON triple_screen_signals(task_type, trade_date);

CREATE INDEX IF NOT EXISTS idx_triple_sig_new_entry_date
ON triple_screen_signals(is_new_entry, trade_date);

CREATE INDEX IF NOT EXISTS idx_triple_sig_pool
ON triple_screen_signals(pool_id);
