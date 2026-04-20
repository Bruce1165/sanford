-- Migration: Create lao_ya_tou_pool table
-- Date: 2026-04-19

DROP TABLE IF EXISTS lao_ya_tou_pool;
CREATE TABLE lao_ya_tou_pool (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    file_name TEXT NOT NULL,
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed INTEGER DEFAULT 0
);

-- Create indexes for query optimization
-- Index 1: Speed up queries by stock code
CREATE INDEX idx_pool_code ON lao_ya_tou_pool(stock_code);

-- Index 2: Speed up date range queries
CREATE INDEX idx_pool_dates ON lao_ya_tou_pool(start_date, end_date);

-- Index 3: Speed up queries for unprocessed records
CREATE INDEX idx_pool_processed ON lao_ya_tou_pool(processed);
