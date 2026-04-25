-- Migration: Create lao_ya_tou_five_flags table
-- Date: 2026-04-19

DROP TABLE IF EXISTS lao_ya_tou_five_flags;

CREATE TABLE lao_ya_tou_five_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    snapshot_id TEXT NOT NULL DEFAULT 'legacy',
    screener_id TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    screen_date DATE NOT NULL,
    close_price REAL NOT NULL,
    match_reason TEXT NOT NULL,
    extra_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pool_id) REFERENCES lao_ya_tou_pool(id) ON DELETE RESTRICT
);

CREATE INDEX idx_five_flags_pool ON lao_ya_tou_five_flags(pool_id);
CREATE INDEX idx_five_flags_snapshot ON lao_ya_tou_five_flags(snapshot_id);
CREATE INDEX idx_five_flags_screener ON lao_ya_tou_five_flags(screener_id);
CREATE INDEX idx_five_flags_code ON lao_ya_tou_five_flags(stock_code);
CREATE INDEX idx_five_flags_date ON lao_ya_tou_five_flags(screen_date);
