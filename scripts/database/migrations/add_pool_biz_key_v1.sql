-- Add pool_biz_key for idempotent pool ingestion (v1)

ALTER TABLE lao_ya_tou_pool ADD COLUMN pool_biz_key TEXT;

-- Backfill legacy rows with deterministic placeholder keys.
UPDATE lao_ya_tou_pool
SET pool_biz_key = 'legacy_' || id
WHERE pool_biz_key IS NULL OR TRIM(pool_biz_key) = '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_pool_biz_key_unique
ON lao_ya_tou_pool(pool_biz_key);
