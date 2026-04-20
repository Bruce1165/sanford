# Monitoring Pool System Design

## Overview

The Monitoring area (right side of Dashboard) needs to display:
1. **LYT Pool Status** - The stock pool built by Lao Ya Tou Zhou Xian (LYT) screener
2. **Pool Screeners Results** - Results from 5 screeners running against the pool

## Database Schema

### LYT Pool Table (`lao_ya_tou_pool`)

```sql
CREATE TABLE lao_ya_tou_pool (
    code VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    entry_date DATE NOT NULL,
    current_signal VARCHAR(20) NOT NULL,
    last_screened_date DATE NOT NULL,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (code) REFERENCES stocks(code)
);
```

**Key Fields:**
- `code` - Stock code (primary key)
- `name` - Stock name
- `entry_date` - Date when stock entered pool
- `current_signal` - Current signal type (Signal 1, Signal 2, Signal 3)
- `last_screened_date` - Last date when stock was screened
- `last_updated` - Timestamp of last update

### Pool Screening Results Table (`pool_screening_results`)

```sql
CREATE TABLE pool_screening_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_id INTEGER NOT NULL,
    code VARCHAR(10) NOT NULL,
    screen_date DATE NOT NULL,
    signal_type VARCHAR(50),
    score REAL,
    price REAL,
    stop_loss REAL,
    position_size VARCHAR(20),
    action VARCHAR(50),
    reason TEXT,
    extra_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (screener_id) REFERENCES screener_types(id),
    FOREIGN KEY (code) REFERENCES stocks(code)
);
```

**Key Fields:**
- `screener_id` - References screener type (LYT=1, others=2-6)
- `code` - Stock code
- `screen_date` - Date of screening
- `signal_type` - Type of signal detected
- `score` - Confidence score
- `price` - Stock price at screening
- `stop_loss` - Stop loss price
- `position_size` - Recommended position size
- `action` - Trading action recommendation
- `reason` - Signal reason/description
- `extra_json` - Additional details (JSON)
- `created_at` - When result was created

### Screener Types Table (`screener_types`)

```sql
CREATE TABLE screener_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_pool_builder INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Expected Screener Types:**
- `lao_ya_tou_zhou_xian_screener` (id=1, is_pool_builder=1) - LYT (builds pool)
- `er_ban_hui_tiao_screener` (id=2, is_pool_builder=0) - Two-board pullback
- `shi_pan_xian_screener` (id=3, is_pool_builder=0) - Limit-up test line
- `jin_feng_huang_screener` (id=4, is_pool_builder=0) - Limit-up golden phoenix
- `yin_feng_huang_screener` (id=5, is_pool_builder=0) - Limit-up silver phoenix
- `zhang_ting_bei_liang_yin_screener` (id=6, is_pool_builder=0) - Limit-up double volume bearish

## API Design

### 1. Get LYT Pool Status

**Endpoint:** `GET /api/monitor/lyt-pool`

**Response:**
```typescript
interface LytPoolStatus {
  pool_size: number;           // Total stocks in pool
  signal_distribution: {
    signal_1: number;          // Count of Signal 1 stocks
    signal_2: number;          // Count of Signal 2 stocks
    signal_3: number;          // Count of Signal 3 stocks
  };
  recent_entries: Array<{
    code: string;
    name: string;
    entry_date: string;
    current_signal: string;
    last_screened_date: string;
  }>;
  recent_updates: Array<{
    code: string;
    name: string;
    old_signal: string | null;
    new_signal: string;
    change_date: string;
  }>;
  last_update: string;         // Timestamp of last pool update
}
```

**Query:**
```sql
-- Pool size
SELECT COUNT(*) FROM lao_ya_tou_pool;

-- Signal distribution
SELECT current_signal, COUNT(*) as count
FROM lao_ya_tou_pool
GROUP BY current_signal;

-- Recent entries (last 10)
SELECT code, name, entry_date, current_signal, last_screened_date
FROM lao_ya_tou_pool
ORDER BY entry_date DESC
LIMIT 10;

-- Recent updates (signal changes, last 10)
SELECT code, name, current_signal as new_signal
FROM lao_ya_tou_pool
WHERE last_updated > DATE('now', '-7 days')
ORDER BY last_updated DESC
LIMIT 10;
```

### 2. Get Pool Screener Results

**Endpoint:** `GET /api/monitor/pool-screeners`

**Response:**
```typescript
interface PoolScreenerResult {
  screener_id: number;
  screener_code: string;
  display_name: string;
  last_run_date: string | null;
  pool_hits: number;           // Stocks found from pool
  recent_hits: Array<{
    code: string;
    name: string;
    signal_type: string;
    score: number;
    price: number;
    position_size: string;
    action: string;
    screen_date: string;
  }>;
  summary: {
    total_pool_stocks: number;
    processed: number;
    errors: number;
    hits: number;
  } | null;
}

interface PoolScreenersResponse {
  lyt: {
    last_run_date: string | null;
    pool_size: number;          // Current pool size
    signal_distribution: {
      signal_1: number;
      signal_2: number;
      signal_3: number;
    };
  };
  pool_screeners: PoolScreenerResult[];
}
```

**Query for Single Screener:**
```sql
-- Get screener info
SELECT id, code, display_name
FROM screener_types
WHERE id = ?;

-- Get recent pool hits (last 20)
SELECT r.code, s.name, r.signal_type, r.score, r.price,
       r.position_size, r.action, r.screen_date
FROM pool_screening_results r
JOIN stocks s ON r.code = s.code
WHERE r.screener_id = ?
ORDER BY r.screen_date DESC, r.created_at DESC
LIMIT 20;

-- Get last run summary (from screener_runs or calculate from results)
SELECT MAX(screen_date) as last_run_date
FROM pool_screening_results
WHERE screener_id = ?;
```

## Frontend Component Design

### Component Structure

```
MonitoringArea/
├── LytPoolStatus.tsx          # LYT pool overview
├── PoolScreenersList.tsx        # Pool screeners results
└── index.tsx                   # Main container
```

### LytPoolStatus Component

**Display:**
- Pool size card (large number)
- Signal distribution chart (pie chart or bar chart)
  - Signal 1 (激进买点) - color: #FF6B6B (orange)
  - Signal 2 (核心主买) - color: #22C55E (green)
  - Signal 3 (加速追买) - color: #3B82F6 (blue)
- Recent entries list (last 10 stocks)
  - Code, name, entry date, current signal
  - Color code by signal type
- Recent updates list (signal changes, last 10)
  - Code, name, old signal → new signal, change date

**Layout:**
```
┌────────────────────────────────────────────┐
│  LYT POOL STATUS                          │
├────────────────────────────────────────────┤
│  Pool Size: 125                         │
│                                          │
│  Signal Distribution:                     │
│  ┌─────────────────────────────┐          │
│  │ Signal 1: 45 ████████████   │          │
│  │ Signal 2: 62 ███████████████ │          │
│  │ Signal 3: 18 ████            │          │
│  └─────────────────────────────┘          │
│                                          │
│  Recent Entries (10)                     │
│  ┌─────────────────────────────┐          │
│  │ 000001 平安银行 Signal 2  │          │
│  │ 000002 万科A    Signal 1  │          │
│  └─────────────────────────────┘          │
├────────────────────────────────────────────┤
│  Recent Updates (10)                       │
│  ┌─────────────────────────────┐          │
│  │ 000001 平安  Signal 1→2   │          │
│  │ 000003 万科   Signal 3→1   │          │
│  └─────────────────────────────┘          │
└────────────────────────────────────────────┘
```

### PoolScreenersList Component

**Display:**
- 5 screener cards, one for each pool screener
- Each card shows:
  - Screener name
  - Last run date
  - Pool hits count (stock found from pool)
  - Recent hits list (last 10)
  - Summary stats (processed, pool size, hits, errors)

**Layout:**
```
┌────────────────────────────────────────────┐
│  POOL SCREENERS                          │
├────────────────────────────────────────────┤
│                                          │
│  ┌─────────────────────────────┐          │
│  │ 二板回跳                        │          │
│  │ Last Run: 2026-04-16 15:30    │          │
│  │ Pool Hits: 8                       │          │
│  └─────────────────────────────┘          │
│                                          │
│  ┌─────────────────────────────┐          │
│  │ 涨停试盘线                     │          │
│  │ Last Run: 2026-04-16 15:35    │          │
│  │ Pool Hits: 12                      │          │
│  └─────────────────────────────┘          │
│                                          │
│  ┌─────────────────────────────┐          │
│  │ 涨停金凤                         │          │
│  │ ...                               │          │
│  └─────────────────────────────┘          │
└────────────────────────────────────────────┘
```

## Refresh Strategy

- Auto-refresh every 60 seconds
- Manual refresh button
- Real-time update when screener runs complete (via WebSocket or polling)

## Color Scheme

- **Signal 1:** #FF6B6B (orange) - 激进买点・鸭鼻孔缩量金叉
- **Signal 2:** #22C55E (green) - 核心主买・鸭嘴开口金叉
- **Signal 3:** #3B82F6 (blue) - 加速追买・放量突破鸭头前高
- **Background:** #0a0f1e
- **Card Background:** #111827
- **Text Primary:** #60a5fa
- **Text Secondary:** #e5e7eb
- **Border:** #1e2d3d

## Data Types

```typescript
// LYT Pool Status
interface LytPoolStatus {
  pool_size: number;
  signal_distribution: {
    signal_1: number;
    signal_2: number;
    signal_3: number;
  };
  recent_entries: PoolStock[];
  recent_updates: SignalChange[];
  last_update: string;
}

interface PoolStock {
  code: string;
  name: string;
  entry_date: string;
  current_signal: 'signal_1' | 'signal_2' | 'signal_3';
  last_screened_date: string;
}

interface SignalChange {
  code: string;
  name: string;
  old_signal: 'signal_1' | 'signal_2' | 'signal_3' | null;
  new_signal: 'signal_1' | 'signal_2' | 'signal_3';
  change_date: string;
}

// Pool Screener Results
interface PoolScreenerResult {
  screener_id: number;
  screener_code: string;
  display_name: string;
  last_run_date: string | null;
  pool_hits: number;
  recent_hits: PoolScreenerHit[];
  summary: ScreenerRunSummary | null;
}

interface PoolScreenerHit {
  code: string;
  name: string;
  signal_type: string;
  score: number;
  price: number;
  position_size: 'conservative' | 'moderate' | 'aggressive';
  action: string;
  screen_date: string;
}

interface ScreenerenerRunSummary {
  pool_size: number;
  processed: number;
  errors: number;
  hits: number;
}

// Combined Response
interface PoolMonitoringResponse {
  lyt: LytPoolStatus;
  pool_screeners: PoolScreenerResult[];
}
```

## Implementation Priority

1. **Phase 1: Backend API**
   - Create `GET /api/monitor/lyt-pool` endpoint
   - Create `GET /api/monitor/pool-screeners` endpoint
   - Query data from stock_data.db

2. **Phase 2: Frontend Components**
   - Create `LytPoolStatus.tsx` component
   - Create `PoolScreenersList.tsx` component
   - Create main `index.tsx` container

3. **Phase 3: Integration**
   - Replace existing Monitoring area
   - Add auto-refresh mechanism
   - Test data flow
