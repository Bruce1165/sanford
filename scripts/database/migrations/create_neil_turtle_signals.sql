-- Migration: Create neil_turtle_signals table
-- Scope: Neil project only (isolated from lao_ya_tou_* tables)
-- Safety: Non-destructive, idempotent

CREATE TABLE IF NOT EXISTS neil_turtle_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    trade_date DATE NOT NULL,
    task_type TEXT NOT NULL,      -- backfill | daily
    is_entry INTEGER NOT NULL DEFAULT 0,
    is_exit INTEGER NOT NULL DEFAULT 0,
    is_new_entry INTEGER NOT NULL DEFAULT 0,
    entry_n INTEGER NOT NULL,
    exit_n INTEGER NOT NULL,
    entry_price REAL,
    exit_price REAL,
    close_price REAL,
    param_version TEXT NOT NULL,
    param_snapshot TEXT NOT NULL, -- JSON string
    signal_biz_key TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pool_id) REFERENCES neil_stock_pool(id) ON DELETE RESTRICT
);

-- Indexes for daily query and history replay
CREATE UNIQUE INDEX IF NOT EXISTS ux_neil_sig_biz_key
ON neil_turtle_signals(signal_biz_key);

CREATE INDEX IF NOT EXISTS idx_neil_sig_code_date
ON neil_turtle_signals(stock_code, trade_date);

CREATE INDEX IF NOT EXISTS idx_neil_sig_task_date
ON neil_turtle_signals(task_type, trade_date);

CREATE INDEX IF NOT EXISTS idx_neil_sig_new_entry_date
ON neil_turtle_signals(is_new_entry, trade_date);

CREATE INDEX IF NOT EXISTS idx_neil_sig_pool
ON neil_turtle_signals(pool_id);
