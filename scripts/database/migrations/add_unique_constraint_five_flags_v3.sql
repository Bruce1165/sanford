-- Add UNIQUE constraint to lao_ya_tou_five_flags table (v3)

-- Step 1: Create new table with UNIQUE constraint
CREATE TABLE IF NOT EXISTS lao_ya_tou_five_flags_unique (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    screener_id TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    screen_date DATE NOT NULL,
    close_price REAL NOT NULL,
    match_reason TEXT NOT NULL,
    extra_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pool_id, screener_id, screen_date),
    FOREIGN KEY (pool_id) REFERENCES lao_ya_tou_pool(id) ON DELETE RESTRICT
);

-- Step 2: Copy data and remove duplicates
INSERT OR IGNORE INTO lao_ya_tou_five_flags_unique
    (pool_id, screener_id, stock_code, stock_name,
     screen_date, close_price, match_reason, extra_data, created_at)
SELECT
    pool_id, screener_id, stock_code, stock_name,
    screen_date, close_price, match_reason, extra_data, created_at
FROM lao_ya_tou_five_flags;

-- Step 3: Drop old table
DROP TABLE lao_ya_tou_five_flags;

-- Step 4: Rename new table
ALTER TABLE lao_ya_tou_five_flags_unique RENAME TO lao_ya_tou_five_flags;
