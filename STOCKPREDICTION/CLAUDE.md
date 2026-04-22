# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Research Objective

**Goal**: Predict stocks with potential to rise 20%+ within the next 21-34 trading days.

**Target**: China A-share stocks (data sourced from NeoTrade2 project)

**Output**: Prediction model documentation + prediction results

**Research Methodology**: Plan → Implement → Verify → Optimize → Loop

## Data Source

Primary data comes from NeoTrade2 project (READ-ONLY):
- **Database**: `/Users/mac/NeoTrade2/data/stock_data.db` (SQLite)
- **Tables**:
  - `stocks`: Stock basic info (code, name, industry, market_cap, is_delisted)
  - `daily_prices`: Daily OHLCV data (trade_date, open, high, low, close, volume, amount, turnover, pct_change)
- **Stock Count**: ~4,663 A-share stocks (filtered)
- **Data Range**: 2024-09-01 to present (~6 months)
- **Data Size**: ~326MB, ~1.4M daily records

**CRITICAL**: Never write to NeoTrade2 directories. All operations are READ-ONLY.

## Project Structure

```
STOCKPREDICTION/
├── data/               # Local database and intermediate results
│   ├── labels.db       # Labeled training data (generated via backtest)
│   ├── features.db     # Computed features/indicators
│   ├── screener_scores.db  # Scores from NeoTrade2 screeners (as features)
│   └── predictions.db  # Prediction results
├── models/             # Trained models and model code
│   ├── feature_engine.py      # Feature engineering (TA-Lib indicators)
│   ├── label_generator.py     # Backtest-based label generation
│   ├── screener_wrapper.py    # Wrapper to run NeoTrade2 screeners as features
│   └── predictor.py           # Main prediction model
├── notebooks/           # Jupyter notebooks for exploration
├── scripts/            # Utility scripts
│   ├── backtest_labels.py     # Generate training labels
│   ├── compute_features.py    # Feature computation
│   ├── collect_screener_scores.py  # Run screeners and collect results
│   ├── train_model.py         # Model training
│   ├── predict.py             # Daily prediction
│   └── backtest_model.py      # Model performance backtest
├── logs/               # Training/prediction logs
├── reports/            # Model performance reports
└── dashboard/          # Optional UI for results visualization
```

## Key Development Commands

```bash
# Step 1: Generate Labels (Backtest to find 20%+ winners)
python scripts/backtest_labels.py --lookback 120 --target_horizon 21,34 --target_gain 0.20

# Step 2: Compute Technical Features
python scripts/compute_features.py --date 2026-04-14

# Step 3: Collect Screener Scores from NeoTrade2
python scripts/collect_screener_scores.py --date 2026-04-14

# Step 4: Train Model
python scripts/train_model.py --model xgboost --cv 5

# Step 5: Daily Prediction
python scripts/predict.py --date 2026-04-14 --model models/latest.pkl

# Step 6: Backtest Model Performance
python scripts/backtest_model.py --model models/latest.pkl --start_date 2024-12-01 --end_date 2026-03-31
```

## Technical Approach

### 1. Problem Formulation
This is a **binary classification** problem:
- **Positive class**: Stock rises 20%+ within 21-34 trading days
- **Negative class**: Stock does not meet the target
- **Features**: Multi-source features
- **Label**: Generated via historical backtest (look-forward approach)

### 2. Feature Engineering (Multi-Source)

#### A. Technical Indicators (from OHLCV)
- **Trend**: MA(5,10,20,60), EMA, MACD
- **Momentum**: RSI, ROC, Stochastic
- **Volume**: OBV, Volume MA, Turnover
- **Volatility**: ATR, Bollinger Bands
- **Price Patterns**: Recent N-day returns, rolling statistics

#### B. Screener Signals (from NeoTrade2)
Run existing screeners and use their results as binary/categorical features:
- `coffee_cup_screener`: Coffee cup handle pattern
- `jin_feng_huang_screener`: Limit-up golden phoenix
- `yin_feng_huang_screener`: Limit-up silver phoenix
- `breakout_20day_screener`: 20-day breakout
- `breakout_main_screener`: Main uptrend breakout
- `ashare_21_screener`: A-share 2.1 comprehensive selection
- ... and others

**Implementation**: Import and run screeners from NeoTrade2, capture hit/miss results as features (0/1 or score)

#### C. Market/Industry Relative Performance
- **Relative to Market Index**: Stock return - Index return (SSE Composite, SZSE Component)
- **Relative to Industry**: Stock return - Industry index return
- **Sector Rotation**: Sector momentum vs market

**Index Data Sources**:
- SSE Composite (000001.SH)
- SZSE Component (399001.SZ)
- Industry indices (from NeoTrade2 or external)

### 3. Label Generation Strategy
Use historical backtest to generate ground truth labels:
```
For each stock and each trading day:
  - Look forward 21-34 trading days
  - Calculate max gain: max(close[t+1:t+34]) / close[t] - 1
  - Label = 1 if max_gain >= 20%, else 0
```

**Important**: Label generation must respect time ordering - train on past data, predict for future.

### 4. Model Selection
- **Baseline**: Logistic Regression (establish baseline performance)
- **Tree-based**: XGBoost / LightGBM (handle non-linear patterns, feature importance)
- **Ensemble**: Combine multiple models
- **Interpretability**: SHAP values for feature importance

### 5. Validation Strategy
- **Time-series CV**: Walk-forward validation (NOT random shuffle)
- **Metrics**: Precision@K (top K predictions), Recall, F1, AUC
- **Backtest**: Simulate trading strategy based on predictions

## NeoTrade2 Screener Integration

The screener wrapper (`models/screener_wrapper.py`) will:
1. Import screeners from `/Users/mac/NeoTrade2/screeners/`
2. Run each screener for a given date
3. Return results as features (binary hit/miss, scores, patterns)

```python
# Example usage
from models.screener_wrapper import ScreenerFeatureCollector

collector = ScreenerFeatureCollector(
    db_path="/Users/mac/NeoTrade2/data/stock_data.db",
    screeners=[
        'coffee_cup_screener',
        'jin_feng_huang_screener',
        'breakout_20day_screener',
        # ... more screeners
    ]
)

features = collector.collect_features(date="2026-04-14")
# Returns: DataFrame with columns like:
# code, coffee_cup_hit, jin_feng_huang_hit, breakout_20day_hit, ...
```

## Data Access Pattern

```python
import sqlite3
from pathlib import Path

# Connect to NeoTrade2 database (READ-ONLY)
DB_PATH = Path("/Users/mac/NeoTrade2/data/stock_data.db")

def get_stock_data(code, start_date, end_date):
    """Fetch OHLCV data for a stock - READ ONLY"""
    with sqlite3.connect(DB_PATH, readonly=True) as conn:
        df = pd.read_sql_query("""
            SELECT trade_date, open, high, low, close,
                   volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """, conn, params=(code, start_date, end_date))
    return df

def get_industry_index(industry_code, start_date, end_date):
    """Fetch industry index data - from external source or NeoTrade2 if available"""
    # Implementation depends on data source
    pass
```

## Important Constraints

1. **NO MODIFICATION TO NeoTrade2**: All operations are READ-ONLY
2. **No Data Leakage**: Features must only use data available at prediction time
3. **Time Respect**: Training data must precede test data
4. **Realistic**: Use only data that would be available in real trading
5. **Stock Filtering**: Apply same filters as NeoTrade2 (exclude ST, delisted, BSE, ETFs)

## External Data Sources (Optional)

If NeoTrade2 data is insufficient, fetch from:
- **Market Indices**: AKShare, Tushare
- **Industry/Sector Data**: Same sources
- **Fundamental**: Financial ratios, earnings (optional)
- **Sentiment**: News, social (optional)

## Research Workflow (PDCA Loop)

### Plan
1. Define research question and success metrics
2. Design feature set (technical + screener + market relative)
3. Plan data splits and validation strategy

### Implement
1. Generate labels via backtest
2. Compute technical features
3. Collect screener scores as features
4. Compute market/industry relative features
5. Train model

### Verify
1. Evaluate on hold-out period
2. Analyze feature importance (SHAP)
3. Check for overfitting/leakage
4. Generate performance report

### Optimize
1. Tune hyperparameters
2. Add/remove features
3. Try different models
4. Adjust label criteria

### Loop
Repeat with improved parameters until target performance met

## Success Metrics

- **Precision@50**: Among top 50 predictions, how many actually rise 20%+?
- **Hit Rate**: Overall accuracy of positive predictions
- **Average Return**: Average return of predicted stocks
- **Win Rate**: Percentage of predictions that meet the 20% target

## Notes

- This is an iterative research project - expect multiple cycles
- Focus on out-of-sample performance, not in-sample
- Document all experiments for reproducibility
- The screener features should complement, not replace, technical indicators
- Market/industry relative performance is key to context-aware prediction
