-- Migration: Create neil_stock_pool table
-- Scope: Neil project only (isolated from lao_ya_tou_* tables)
-- Safety: Non-destructive, idempotent

CREATE TABLE IF NOT EXISTS neil_stock_pool (
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

-- Indexes for import dedupe and query performance
CREATE UNIQUE INDEX IF NOT EXISTS ux_neil_pool_biz_key
ON neil_stock_pool(pool_biz_key);

CREATE INDEX IF NOT EXISTS idx_neil_pool_code
ON neil_stock_pool(stock_code);

CREATE INDEX IF NOT EXISTS idx_neil_pool_active
ON neil_stock_pool(is_active);

CREATE INDEX IF NOT EXISTS idx_neil_pool_import_batch
ON neil_stock_pool(import_batch_id);

-- Auto-maintain updated_at on updates
CREATE TRIGGER IF NOT EXISTS trg_neil_pool_updated_at
AFTER UPDATE ON neil_stock_pool
FOR EACH ROW
BEGIN
    UPDATE neil_stock_pool
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
