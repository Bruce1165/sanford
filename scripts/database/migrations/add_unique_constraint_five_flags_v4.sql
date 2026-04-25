-- Upgrade lao_ya_tou_five_flags unique key to 4-key dedupe rule (v4)
-- Rule: stock_code + screener_id + screen_date + snapshot_id

CREATE TABLE IF NOT EXISTS lao_ya_tou_five_flags_v4 (
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
    UNIQUE (stock_code, screener_id, screen_date, snapshot_id),
    FOREIGN KEY (pool_id) REFERENCES lao_ya_tou_pool(id) ON DELETE RESTRICT
);

INSERT OR IGNORE INTO lao_ya_tou_five_flags_v4
    (pool_id, snapshot_id, screener_id, stock_code, stock_name,
     screen_date, close_price, match_reason, extra_data, created_at)
SELECT
    pool_id,
    'legacy' AS snapshot_id,
    screener_id,
    stock_code,
    stock_name,
    screen_date,
    close_price,
    match_reason,
    extra_data,
    created_at
FROM lao_ya_tou_five_flags;

DROP TABLE lao_ya_tou_five_flags;
ALTER TABLE lao_ya_tou_five_flags_v4 RENAME TO lao_ya_tou_five_flags;

CREATE INDEX IF NOT EXISTS idx_five_flags_pool ON lao_ya_tou_five_flags(pool_id);
CREATE INDEX IF NOT EXISTS idx_five_flags_snapshot ON lao_ya_tou_five_flags(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_five_flags_screener ON lao_ya_tou_five_flags(screener_id);
CREATE INDEX IF NOT EXISTS idx_five_flags_code ON lao_ya_tou_five_flags(stock_code);
CREATE INDEX IF NOT EXISTS idx_five_flags_date ON lao_ya_tou_five_flags(screen_date);
