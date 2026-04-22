# Data Access Guide

## Overview

This document explains how to access data sources for the research project, including read-only constraints and safe data handling practices.

---

## 📊 Data Sources

### 1. Production Data (Read-Only Only)

#### Stock Price Data
- **Path**: `data/stock_data.db`
- **Type**: SQLite Database
- **Access**: Read-Only
- **Contents**: 6+ months of OHLCV data for 4,663 A-share stocks
- **Schema**:
  - `stocks` - Stock basic info (code, name, industry, market_cap, is_delisted)
  - `daily_prices` - Daily OHLCV data (code, trade_date, open, high, low, close, volume, amount, turnover, pct_change)

**Example Query**:
```python
import sqlite3

conn = sqlite3.connect('data/stock_data.db', readonly=True)
cursor = conn.cursor()

# Get price data for a stock
cursor.execute("""
    SELECT trade_date, open, high, low, close, volume, pct_change
    FROM daily_prices
    WHERE code = 'sh.600000'
    ORDER BY trade_date DESC
    LIMIT 100
""")
rows = cursor.fetchall()
```

#### Screener Results
- **Path**: `data/screeners/{screener_name}/{date}.xlsx`
- **Type**: Excel Files
- **Access**: Read-Only
- **Contents**: Historical screener outputs (stocks identified by each screener)
- **Format**: Each file contains list of stocks that matched the screener criteria on that date

**Example Reading**:
```python
import pandas as pd
from pathlib import Path

# Read screener results for a specific date
screener_name = 'coffee_cup'
date = '2026-04-02'
file_path = Path(f'data/screeners/{screener_name}/{date}.xlsx')

if file_path.exists():
    df = pd.read_excel(file_path)
    stocks = df['code'].tolist()  # Get list of stock codes
```

### 2. Research Data (Writable)

#### Research Database
- **Path**: `research/data/research.db`
- **Type**: SQLite Database
- **Access**: Read-Write (Research Only)
- **Purpose**: Store research-specific data (labels, predictions, metrics)
- **Schema**:
  - `labeled_stocks` - Ground truth labels (stock, date, cup_formed)
  - `screener_triggers` - Historical screener triggers by stock/date
  - `predictions` - Model predictions
  - `backtest_results` - Backtest performance metrics
  - `model_versions` - Model version history

**Example Writing**:
```python
import sqlite3

conn = sqlite3.connect('research/data/research.db')
cursor = conn.cursor()

# Create table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS labeled_stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        date TEXT NOT NULL,
        cup_formed BOOLEAN NOT NULL,
        formation_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code, date)
    )
""")

# Insert labeled data
cursor.execute("""
    INSERT OR REPLACE INTO labeled_stocks
    (stock_code, date, cup_formed, formation_date)
    VALUES (?, ?, ?, ?)
""", ('sh.600000', '2026-04-02', True, '2026-04-15'))

conn.commit()
conn.close()
```

#### Analysis Outputs
- **Path**: `research/output/analysis/`
- **Type**: CSV, JSON, Markdown files
- **Access**: Read-Write
- **Contents**: Analysis results, datasets, reports

**Example**:
```python
import pandas as pd

# Save labeled dataset
df = pd.DataFrame({
    'stock_code': ['sh.600000', 'sz.000001'],
    'date': ['2026-04-02', '2026-04-02'],
    'cup_formed': [True, False]
})
df.to_csv('research/output/analysis/dataset_phase1_20260409.csv', index=False)
```

#### Trained Models
- **Path**: `research/output/models/`
- **Type**: .pkl, .h5, .json files
- **Access**: Read-Write
- **Contents**: Trained ML models, model checkpoints

**Example**:
```python
import pickle

# Save trained model
with open('research/output/models/predictor_v1.pkl', 'wb') as f:
    pickle.dump(model, f)

# Load model
with open('research/output/models/predictor_v1.pkl', 'rb') as f:
    model = pickle.load(f)
```

---

## ⚠️ Critical Access Rules

### What You CAN Do ✅

#### Production Data (Read-Only)
- ✅ Query `data/stock_data.db` for stock price data
- ✅ Read Excel files in `data/screeners/`
- ✅ Analyze and process data in memory
- ✅ Save analysis results to `research/` directory

#### Research Data (Writable)
- ✅ Write to `research/data/research.db`
- ✅ Create files in `research/output/`
- ✅ Modify scripts in `research/scripts/`
- ✅ Update documentation in `research/TECHNICAL_DOCS/`

### What You CANNOT Do ❌

#### Production Data (Strictly Read-Only)
- ❌ Write to `data/stock_data.db`
- ❌ Modify Excel files in `data/screeners/`
- ❌ Delete production data
- ❌ Create new files in `data/` (except `research/` subdirectory)

#### Production System
- ❌ Modify `backend/app.py`
- ❌ Restart Flask process
- ❌ Write to `data/dashboard.db`
- ❌ Modify production screeners in `screeners/` directory

---

## 🔒 Safe Data Access Patterns

### Pattern 1: Read-Only Database Connection
```python
# Safe: Read-only connection
import sqlite3

conn = sqlite3.connect('data/stock_data.db', uri=True, isolation_level=None)
conn.execute('PRAGMA query_only = ON')  # Enforce read-only
conn.execute('PRAGMA journal_mode = WAL')  # Faster reads

try:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stocks LIMIT 10")
    results = cursor.fetchall()
finally:
    conn.close()
```

### Pattern 2: Safe Excel Reading
```python
# Safe: Read Excel without modification
import pandas as pd
from pathlib import Path

excel_path = Path('data/screeners/coffee_cup/2026-04-02.xlsx')

if excel_path.exists():
    # Read-only, no write operations
    df = pd.read_excel(excel_path)
    # Process in memory...
else:
    print(f"File not found: {excel_path}")
```

### Pattern 3: Research Database Writing
```python
# Safe: Write to isolated research database
import sqlite3
from pathlib import Path

# Ensure research directory exists
Path('research/data').mkdir(parents=True, exist_ok=True)

# Write to research DB (safe)
conn = sqlite3.connect('research/data/research.db')
cursor = conn.cursor()

# Create table if not exists
cursor.execute("""
    CREATE TABLE IF NOT EXISTS analysis_results (
        id INTEGER PRIMARY KEY,
        stock_code TEXT,
        analysis_date TEXT,
        result_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Insert results
cursor.execute("""
    INSERT INTO analysis_results (stock_code, analysis_date, result_json)
    VALUES (?, ?, ?)
""", ('sh.600000', '2026-04-09', '{"pattern": "cup"}'))

conn.commit()
conn.close()
```

---

## 📁 File Path Reference

### Absolute Paths
```
/Users/mac/NeoTrade2/
├── data/
│   ├── stock_data.db              # READ-ONLY (production)
│   ├── dashboard.db               # READ-ONLY (production)
│   └── screeners/                 # READ-ONLY (production)
│       ├── coffee_cup/
│       ├── er_ban_hui_tiao/
│       └── ...
└── research/
    └── predictive_cup/
        ├── data/
        │   └── research.db         # WRITABLE (research only)
        ├── output/
        │   ├── analysis/           # WRITABLE
        │   ├── models/             # WRITABLE
        │   └── reports/            # WRITABLE
        └── scripts/                # WRITABLE
```

### Relative Paths (from project root)
```
data/stock_data.db                 # Production stock prices (read-only)
data/screeners/                    # Screener results (read-only)
research/predictive_cup/data/research.db  # Research DB (writable)
research/predictive_cup/output/    # Research outputs (writable)
```

---

## 🛡️ Data Integrity Checks

### Before Processing
```python
def validate_production_data_access():
    """Ensure we're not accidentally writing to production data"""
    import os

    # Check if we're trying to write to production
    forbidden_paths = [
        'data/stock_data.db',
        'data/dashboard.db',
        'data/screeners/',
        'backend/app.py'
    ]

    for path in forbidden_paths:
        if os.path.exists(path):
            # Check if we have write permissions
            if os.access(path, os.W_OK):
                raise PermissionError(f"Write access detected on production data: {path}")
```

### Safe File Operations
```python
def safe_read_csv(filepath):
    """Safely read CSV file"""
    from pathlib import Path

    path = Path(filepath)

    # Validate path is not in production data
    if path.is_relative_to('data/stock_data.db'):
        raise ValueError("Cannot write to production database")

    if path.is_relative_to('data/dashboard.db'):
        raise ValueError("Cannot write to production database")

    if path.is_relative_to('data/screeners/'):
        raise ValueError("Cannot modify screener results")

    # Safe to read
    return pd.read_csv(path)
```

---

## 🔍 Debugging Data Access Issues

### Issue: Database Locked
```python
# Error: sqlite3.OperationalError: database is locked

# Solution: Use WAL mode and read-only connection
conn = sqlite3.connect('data/stock_data.db', uri=True)
conn.execute('PRAGMA journal_mode = WAL')
conn.execute('PRAGMA query_only = ON')
```

### Issue: File Not Found
```python
# Error: FileNotFoundError

# Solution: Check file exists before reading
from pathlib import Path

file_path = Path('data/screeners/coffee_cup/2026-04-02.xlsx')
if not file_path.exists():
    print(f"Screener data not found: {file_path}")
    # Handle missing data gracefully
```

### Issue: Permission Denied
```python
# Error: PermissionError

# Solution: Check if you're trying to write to production
import os

if os.access('data/stock_data.db', os.W_OK):
    raise PermissionError("Attempting to write to production data!")
```

---

## 📚 Related Documents

- [Safety Constraints](04_SAFETY_CONSTRAINTS.md) - Detailed safety rules
- [Current Status](06_CURRENT_STATUS.md) - Data availability status
- [Risk Register](08_RISK_REGISTER.md) - Data-related risks

---

**Last Updated**: 2026-04-09
