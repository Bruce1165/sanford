-- Add unique constraint to prevent duplicate screening results
-- A stock should only be matched once per screener per day

ALTER TABLE lao_ya_tou_five_flags
ADD CONSTRAINT unique_pool_screener_date
UNIQUE (pool_id, screener_id, screen_date);
