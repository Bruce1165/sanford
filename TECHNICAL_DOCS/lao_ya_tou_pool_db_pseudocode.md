# Lao Ya Tou Pool System - DB Migration Pseudocode

## Purpose
Create database tables to support stock pool system where:
1. LYT screener builds/updates pool daily
2. 5 other screeners run against pool
3. Track screening results and signal changes

## Existing Tables
- `stocks` - PK: code (VARCHAR(10)), has name, industry, etc.

## New Tables

### 1. screener_types
Maps screener names to IDs for foreign key references.

```sql
CREATE TABLE screener_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,      -- 'lao_ya_tou', 'er_ban_hui_tiao', etc.
    display_name VARCHAR(100) NOT NULL,       -- '老鸭头周线', '二板回调', etc.
    description TEXT,
    is_pool_builder INTEGER DEFAULT 0,         -- 1 = LYT (builds pool), 0 = runs against pool
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Initial data for 6 screeners
INSERT INTO screener_types (code, display_name, is_pool_builder) VALUES
('lao_ya_tou', '老鸭头周线', 1),
('er_ban_hui_tiao', '二板回调', 0),
('shi_pan_xian', '涨停试盘线', 0),
('jin_feng_huang', '金凤凰', 0),
('yin_feng_huang', '银凤凰', 0),
('zhang_ting_bei_liang_yin', '涨停倍量阴', 0);
```

### 2. lao_ya_tou_pool
Current state of stocks in LYT pool. One row per stock in pool.

```sql
CREATE TABLE lao_ya_tou_pool (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    entry_date DATE NOT NULL,                 -- When stock first entered pool
    current_signal VARCHAR(20) NOT NULL,      -- 'signal_1', 'signal_2', 'signal_3'
    last_screened_date DATE NOT NULL,           -- Last LYT screener run that found this stock
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
);

CREATE INDEX idx_pool_current_signal ON lao_ya_tou_pool(current_signal);
CREATE INDEX idx_pool_entry_date ON lao_ya_tou_pool(entry_date);
```

### 3. lao_ya_tou_signal_history
Track signal type changes for pool stocks.

```sql
CREATE TABLE lao_ya_tou_signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(10) NOT NULL,
    old_signal VARCHAR(20),                      -- NULL if new entry
    new_signal VARCHAR(20) NOT NULL,
    change_date DATE NOT NULL,
    changed_by_screener VARCHAR(50) NOT NULL,  -- Which LYT run detected the change
    notes TEXT,
    FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
);

CREATE INDEX idx_signal_history_code ON lao_ya_tou_signal_history(code);
CREATE INDEX idx_signal_history_date ON lao_ya_tou_signal_history(change_date DESC);
```

### 4. pool_screening_results
Unified table for screening results from all 6 screeners.

```sql
CREATE TABLE pool_screening_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_id INTEGER NOT NULL,
    code VARCHAR(10) NOT NULL,
    screen_date DATE NOT NULL,                -- When screener ran
    signal_type VARCHAR(50),                   -- Signal found (nullable - may not find)
    score REAL,                               -- Confidence/score from screener
    price REAL,                                -- Closing price at detection
    stop_loss REAL,                           -- Stop loss level (if applicable)
    position_size VARCHAR(20),                  -- Position size suggestion
    action VARCHAR(50),                        -- Recommended action (if applicable)
    reason TEXT,                               -- Detailed reason/description
    extra_json TEXT,                            -- Additional screener-specific data
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screener_id) REFERENCES screener_types(id),
    FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
);

CREATE INDEX idx_pool_screener_date ON pool_screening_results(screener_id, screen_date DESC);
CREATE INDEX idx_pool_code_date ON pool_screening_results(code, screen_date DESC);
CREATE INDEX idx_pool_screener_code_date ON pool_screening_results(screener_id, code, screen_date DESC);
```

## Views

### v_pool_status
Current pool state with stock info.

```sql
CREATE VIEW v_pool_status AS
SELECT
    p.code,
    p.name,
    p.entry_date,
    p.current_signal,
    p.last_screened_date,
    p.last_updated,
    s.industry,
    s.area,
    s.circulating_market_cap
FROM lao_ya_tou_pool p
JOIN stocks s ON p.code = s.code
ORDER BY p.entry_date DESC;
```

### v_pool_signal_history
Signal change history with screener display names.

```sql
CREATE VIEW v_pool_signal_history AS
SELECT
    h.id,
    h.code,
    h.old_signal,
    h.new_signal,
    h.change_date,
    h.changed_by_screener,
    h.notes,
    p.name
FROM lao_ya_tou_signal_history h
JOIN stocks p ON h.code = p.code
ORDER BY h.change_date DESC;
```

### v_pool_daily_screening_summary
Daily summary of which screeners found which pool stocks.

```sql
CREATE VIEW v_pool_daily_screening_summary AS
SELECT
    r.screen_date,
    r.code,
    s.name,
    st.code AS screener_code,
    st.display_name AS screener_name,
    r.signal_type,
    r.score,
    r.price,
    r.action,
    r.reason
FROM pool_screening_results r
JOIN stocks s ON r.code = s.code
JOIN screener_types st ON r.screener_id = st.id
ORDER BY r.screen_date DESC, r.code, r.screener_id;
```

### v_stock_all_screeners
Get all screening results for a specific stock across all screeners.

```sql
CREATE VIEW v_stock_all_screeners AS
SELECT
    s.code,
    s.name,
    p.current_signal,
    p.entry_date,
    r.screen_date,
    st.display_name AS screener_name,
    r.signal_type,
    r.score,
    r.price,
    r.action,
    r.reason
FROM lao_ya_tou_pool p
JOIN stocks s ON p.code = s.code
LEFT JOIN pool_screening_results r ON p.code = r.code
LEFT JOIN screener_types st ON r.screener_id = st.id
WHERE p.code IN (SELECT code FROM lao_ya_tou_pool)
ORDER BY r.screen_date DESC;
```

### v_pool_size_over_time
Track pool size (number of stocks) over time.

```sql
CREATE VIEW v_pool_size_over_time AS
SELECT
    entry_date,
    current_signal,
    COUNT(*) AS count
FROM lao_ya_tou_pool
GROUP BY entry_date, current_signal
ORDER BY entry_date DESC;
```

## Migration Script Flow

```
Step 1: Check if tables exist
Step 2: Create screener_types table
Step 3: Insert initial screener types data
Step 4: Create lao_ya_tou_pool table
Step 5: Create lao_ya_tou_signal_history table
Step 6: Create pool_screening_results table
Step 7: Create indexes
Step 8: Create views
Step 9: Verify tables created
```
