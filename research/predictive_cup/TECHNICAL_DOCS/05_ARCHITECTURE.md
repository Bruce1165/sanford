# System Architecture

## Overview

This document describes the architecture of the Predictive Coffee Cup Formation research system, including data flow, component relationships, and isolation mechanisms.

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NeoTrade2 Production System                    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     Flask Dashboard (Port 8765)                   │    │
│  │  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐  │    │
│  │  │  Web UI       │  │  API Endpoints│  │  Authentication    │  │    │
│  │  │  (React)      │  │  (Flask)      │  │  (Basic Auth)      │  │    │
│  │  └────────────────┘  └──────────────┘  └────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    Production Databases (Read-Only)               │    │
│  │  ┌─────────────────────┐  ┌──────────────────────────────────┐  │    │
│  │  │  stock_data.db      │  │  dashboard.db                    │  │    │
│  │  │  - stocks           │  │  - screeners                     │  │    │
│  │  │  - daily_prices     │  │  - screener_runs                │  │    │
│  │  │  - 6+ months data   │  │  - screener_results             │  │    │
│  │  └─────────────────────┘  └──────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │              Screener Results (Read-Only Excel Files)           │    │
│  │  data/screeners/{screener_name}/{date}.xlsx                     │    │
│  │  - coffee_cup/2026-04-02.xlsx                                   │    │
│  │  - er_ban_hui_tiao/2026-04-03.xlsx                              │    │
│  │  - ... (11 screeners × 300+ trading days)                        │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
                    ┌───────────────────────────────┐
                    │  ISOLATION BOUNDARY           │
                    │  (Read-Only Access Only)      │
                    └───────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                     Research Workspace (Isolated)                       │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    Research Database (Writable)                  │    │
│  │  research/data/research.db                                        │    │
│  │  ┌────────────────┐  ┌──────────────┐  ┌────────────────────┐  │    │
│  │  │  labeled_stocks│  │  predictions │  │  backtest_results  │  │    │
│  │  │  (ground truth)│  │  (model out) │  │  (performance)     │  │    │
│  │  └────────────────┘  └──────────────┘  └────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                      Research Scripts                             │    │
│  │  research/scripts/                                                │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Phase 1: Data Analysis                                      │ │    │
│  │  │  - survey_screener_data.py                                  │ │    │
│  │  │  - run_historical_screeners.py                              │ │    │
│  │  │  - init_research_db.py                                      │ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Phase 2: Model Development (to be created)                  │ │    │
│  │  │  - build_prediction_model.py                                │ │    │
│  │  │  - train_model.py                                           │ │    │
│  │  │  - predict_cups.py                                          │ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Phase 3: Backtesting (to be created)                        │ │    │
│  │  │  - backtest_predictor.py                                   │ │    │
│  │  │  - calculate_metrics.py                                    │ │    │
│  │  │  - analyze_failures.py                                     │ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                      Research Outputs                             │    │
│  │  research/output/                                                 │    │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────────────────────┐   │    │
│  │  │  analysis/   │  │  models/   │  │  reports/               │   │    │
│  │  │  - datasets  │  │  - *.pkl   │  │  - backtest reports     │   │    │
│  │  │  - patterns  │  │  - *.h5    │  │  - validation reports   │   │    │
│  │  │  - metrics   │  │            │  │                        │   │    │
│  │  └──────────────┘  └────────────┘  └────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow

### Phase 1: Research & Analysis

```
Production Data (Read-Only)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Survey Screener Data                                │
│ - Read data/screeners/{name}/{date}.xlsx                    │
│ - Identify data coverage and gaps                           │
│ - Generate data quality report                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Extract Ground Truth                                │
│ - Analyze coffee_cup screener results                       │
│ - Identify cup formations                                   │
│ - Label stocks: {stock, date, cup_formed}                   │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Extract Screener Triggers                           │
│ - For each labeled stock, extract screener triggers         │
│ - Identify temporal sequences                                │
│ - Calculate trigger frequencies                              │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Create Labeled Dataset                              │
│ - Combine ground truth with screener triggers               │
│ - Save to research/output/analysis/dataset_phase1.csv       │
└─────────────────────────────────────────────────────────────┘
    ↓
Research Database (research/data/research.db)
    - labeled_stocks table populated
    - screener_triggers table populated
```

### Phase 2: Model Development

```
Phase 1 Dataset (CSV)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Feature Engineering                                  │
│ - Transform screener triggers into features                  │
│ - Create temporal features (days since last trigger)         │
│ - Add stock-level features (market cap, industry)            │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Model Training                                       │
│ - Train on training set (80% of data)                        │
│ - Validate on test set (20% of data)                         │
│ - Tune hyperparameters                                       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Model Evaluation                                    │
│ - Calculate accuracy metrics (precision, recall, F1)         │
│ - Compare against baseline                                   │
│ - Analyze feature importance                                │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Save Model                                           │
│ - Save to research/output/models/predictor_v1.pkl           │
│ - Document model architecture                                │
│ - Create prediction API (predict_cups.py)                   │
└─────────────────────────────────────────────────────────────┘
```

### Phase 3: Backtesting

```
Trained Model (predictor_v1.pkl)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Historical Prediction                                │
│ - For each historical date, run predictions                 │
│ - Use historical screener triggers as input                 │
│ - Generate predictions for all dates                        │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Compare Predictions vs. Ground Truth               │
│ - Match predictions to actual cup formations                │
│ - Calculate accuracy metrics by month                        │
│ - Analyze false positives/negatives                         │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Market Regime Analysis                              │
│ - Test performance in different market conditions           │
│ - Identify regime-specific patterns                          │
│ - Document performance characteristics                       │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Generate Report                                      │
│ - Create backtest report (markdown)                         │
│ - Provide go/no-go recommendation                           │
│ - Document lessons learned                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schemas

### Production Databases (Read-Only)

#### stock_data.db
```sql
-- Stocks table
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,           -- Stock code (e.g., sh.600000)
    name TEXT,                      -- Stock name
    industry TEXT,                   -- Industry
    market_cap REAL,                 -- Market cap (yuan)
    is_delisted BOOLEAN,             -- Delisted flag
    updated_at TIMESTAMP
);

-- Daily prices table
CREATE TABLE daily_prices (
    id INTEGER PRIMARY KEY,
    code TEXT,                       -- Stock code
    trade_date TEXT,                 -- Trading date (YYYY-MM-DD)
    open REAL,                       -- Opening price
    high REAL,                       -- Highest price
    low REAL,                        -- Lowest price
    close REAL,                      -- Closing price
    volume INTEGER,                  -- Trading volume
    amount REAL,                     -- Trading amount (yuan)
    turnover REAL,                   -- Turnover rate
    pct_change REAL,                 -- Percentage change
    FOREIGN KEY (code) REFERENCES stocks(code)
);

CREATE INDEX idx_daily_prices_code_date ON daily_prices(code, trade_date);
```

#### dashboard.db
```sql
-- Screeners table
CREATE TABLE screeners (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,                -- Screener name
    display_name TEXT,               -- Display name
    description TEXT,
    category TEXT,
    created_at TIMESTAMP
);

-- Screener runs table
CREATE TABLE screener_runs (
    id INTEGER PRIMARY KEY,
    screener_id INTEGER,             -- Reference to screeners
    run_date TEXT,                   -- Run date
    status TEXT,                     -- success, failed, running
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    stock_count INTEGER,             -- Number of stocks found
    error_message TEXT,
    FOREIGN KEY (screener_id) REFERENCES screeners(id)
);

-- Screener results table
CREATE TABLE screener_results (
    id INTEGER PRIMARY KEY,
    run_id INTEGER,                  -- Reference to screener_runs
    stock_code TEXT,                 -- Stock code
    stock_name TEXT,
    signal_strength REAL,            -- Signal strength (0-1)
    trigger_price REAL,              -- Price at trigger
    trigger_date TEXT,               -- Trigger date
    FOREIGN KEY (run_id) REFERENCES screener_runs(id)
);

CREATE INDEX idx_screener_results_run_id ON screener_results(run_id);
CREATE INDEX idx_screener_results_stock_code ON screener_results(stock_code);
```

### Research Database (Writable)

#### research.db
```sql
-- Labeled stocks table (ground truth)
CREATE TABLE labeled_stocks (
    id INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL,
    date TEXT NOT NULL,
    cup_formed BOOLEAN NOT NULL,
    formation_date TEXT,
    completion_date TEXT,
    confidence REAL,                 -- Label confidence (0-1)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, date)
);

CREATE INDEX idx_labeled_stocks_cup_formed ON labeled_stocks(cup_formed);
CREATE INDEX idx_labeled_stocks_date ON labeled_stocks(date);

-- Screener triggers table
CREATE TABLE screener_triggers (
    id INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL,
    screener_name TEXT NOT NULL,
    trigger_date TEXT NOT NULL,
    trigger_price REAL,
    trigger_data JSON,               -- Additional trigger data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, screener_name, trigger_date)
);

CREATE INDEX idx_screener_triggers_stock ON screener_triggers(stock_code);
CREATE INDEX idx_screener_triggers_date ON screener_triggers(trigger_date);

-- Predictions table
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY,
    stock_code TEXT NOT NULL,
    prediction_date TEXT NOT NULL,
    prediction BOOLEAN NOT NULL,     -- True = cup will form
    confidence REAL,                 -- Prediction confidence (0-1)
    model_version TEXT NOT NULL,     -- Model version used
    features JSON,                   -- Feature values used
    lead_time_days INTEGER,          -- Days until formation (if predicted)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_predictions_date ON predictions(prediction_date);
CREATE INDEX idx_predictions_stock ON predictions(stock_code);

-- Backtest results table
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY,
    model_version TEXT NOT NULL,
    backtest_start_date TEXT NOT NULL,
    backtest_end_date TEXT NOT NULL,
    precision REAL,                  -- TP / (TP + FP)
    recall REAL,                     -- TP / (TP + FN)
    f1_score REAL,                   -- 2 * (precision * recall) / (precision + recall)
    lead_time_avg REAL,              -- Average lead time (days)
    lead_time_std REAL,              -- Lead time std deviation
    false_positive_rate REAL,        -- FP / (FP + TN)
    false_negative_rate REAL,        -- FN / (FN + TP)
    total_predictions INTEGER,
    true_positives INTEGER,
    false_positives INTEGER,
    true_negatives INTEGER,
    false_negatives INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model versions table
CREATE TABLE model_versions (
    id INTEGER PRIMARY KEY,
    version TEXT UNIQUE NOT NULL,    -- e.g., v1.0, v1.1
    model_type TEXT,                 -- e.g., random_forest, xgboost
    model_path TEXT,                 -- Path to model file
    architecture JSON,               -- Model architecture details
    training_date_range_start TEXT,
    training_date_range_end TEXT,
    training_precision REAL,
    training_recall REAL,
    training_f1 REAL,
    validation_precision REAL,
    validation_recall REAL,
    validation_f1 REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_model_versions_version ON model_versions(version);
CREATE INDEX idx_model_versions_active ON model_versions(is_active);
```

---

## 🔒 Isolation Mechanisms

### 1. Directory Isolation
```
Production:  /Users/mac/NeoTrade2/
Research:    /Users/mac/NeoTrade2/research/predictive_cup/
```

### 2. Database Isolation
```
Production:  data/stock_data.db, data/dashboard.db
Research:    research/data/research.db
```

### 3. Git Worktree Isolation
```
Main branch:  master (production code)
Worktree:     research-predictive-cup (research code)
```

### 4. Process Isolation
```
Production:  Flask app.py (running continuously)
Research:    Python scripts (run on-demand, no background processes)
```

### 5. Permission Isolation
```
Production:  Read-Only access enforced via code reviews and validation
Research:    Read-Write access in isolated workspace
```

---

## 📡 Component Communication

### Data Flow
```
Production Data (Read-Only)
    ↓ (read operations)
Research Scripts
    ↓ (processing)
Research Database (Writable)
    ↓ (store results)
Analysis Outputs
```

### No Production Impact
- Research scripts never write to production
- No background processes affecting dashboard
- No modification of production code
- Isolated database prevents conflicts

---

## 🎯 Key Design Principles

1. **Isolation First**: Research workspace completely isolated from production
2. **Read-Only Production**: Production data is never modified
3. **Reproducibility**: All research outputs are versioned and documented
4. **Safety**: Multiple layers of protection (code reviews, validation, isolation)
5. **Transparency**: All data flow and decisions are documented

---

## 📚 Related Documents

- [Data Access](03_DATA_ACCESS.md) - How to access data sources
- [Safety Constraints](04_SAFETY_CONSTRAINTS.md) - What you cannot do
- [Phase Plan](02_PHASE_PLAN.md) - Detailed execution phases

---

**Last Updated**: 2026-04-09
