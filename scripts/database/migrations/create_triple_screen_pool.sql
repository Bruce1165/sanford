-- Migration: Create triple_screen_pool table
-- Scope: Triple-screen project only (isolated from neil_* / lao_ya_tou_* tables)
-- Safety: Non-destructive, idempotent

CREATE TABLE IF NOT EXISTS triple_screen_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_biz_key TEXT NOT NULL UNIQUE,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    source_file TEXT NOT NULL,
    import_batch_id TEXT NOT NULL,
    import_date DATE NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    validation_status TEXT NOT NULL DEFAULT 'valid',
    validation_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_triple_pool_biz_key
ON triple_screen_pool(pool_biz_key);

CREATE INDEX IF NOT EXISTS idx_triple_pool_code
ON triple_screen_pool(stock_code);

CREATE INDEX IF NOT EXISTS idx_triple_pool_active
ON triple_screen_pool(is_active);

CREATE INDEX IF NOT EXISTS idx_triple_pool_import_batch
ON triple_screen_pool(import_batch_id);

CREATE TRIGGER IF NOT EXISTS trg_triple_pool_updated_at
AFTER UPDATE ON triple_screen_pool
FOR EACH ROW
BEGIN
    UPDATE triple_screen_pool
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
