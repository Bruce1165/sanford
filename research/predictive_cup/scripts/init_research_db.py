#!/usr/bin/env python3
"""
Initialize research database for Predictive Coffee Cup Formation project.

This database stores:
- Labeled dataset for training
- Prediction results
- Backtest metrics
- Intermediate analysis data
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '../data/research.db')


def create_database():
    """Create research database with all necessary tables."""

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable WAL mode for concurrent reads
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')
    cursor.execute('PRAGMA busy_timeout=30000')

    # 1. Labeled dataset table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS labeled_dataset (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            observation_date DATE NOT NULL,
            cup_formed BOOLEAN NOT NULL,
            cup_completion_date DATE,
            screeners_triggered TEXT NOT NULL,  -- JSON array of screener names
            temporal_sequence TEXT,              -- JSON array of [screener, trigger_date] objects
            features_json TEXT,                 -- JSON object of all features
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, observation_date)
        )
    ''')

    # 2. Prediction results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            prediction_date DATE NOT NULL,
            cup_formed_probability REAL NOT NULL,
            predicted_phase INTEGER,              -- 0-5 based on state machine
            model_version TEXT NOT NULL,
            features_contributing TEXT,             -- JSON: which features drove prediction
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, prediction_date, model_version)
        )
    ''')

    # 3. Backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            prediction_date DATE NOT NULL,
            predicted_cup BOOLEAN NOT NULL,
            actual_cup BOOLEAN NOT NULL,
            lead_time_days INTEGER,               -- How many days before completion
            is_true_positive BOOLEAN,              -- predicted=cup, actual=cup
            is_false_positive BOOLEAN,             -- predicted=cup, actual=not cup
            is_false_negative BOOLEAN,             -- predicted=not cup, actual=cup
            is_true_negative BOOLEAN,              -- predicted=not cup, actual=not cup
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Backtest summary metrics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS backtest_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id TEXT NOT NULL UNIQUE,
            model_version TEXT NOT NULL,
            test_period_start DATE NOT NULL,
            test_period_end DATE NOT NULL,
            total_stocks_tested INTEGER NOT NULL,
            true_positives INTEGER NOT NULL,
            false_positives INTEGER NOT NULL,
            true_negatives INTEGER NOT NULL,
            false_negatives INTEGER NOT NULL,
            precision REAL NOT NULL,
            recall REAL NOT NULL,
            f1_score REAL NOT NULL,
            accuracy REAL NOT NULL,
            avg_lead_time_days REAL,
            confidence_interval_95_lower REAL,
            confidence_interval_95_upper REAL,
            market_regime TEXT,                 -- bull, bear, sideways
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Screener temporal patterns table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_temporal_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,            -- e.g., "uptrend_to_consolidation"
            screener_sequence TEXT NOT NULL,        -- JSON: ordered list of screeners
            occurrence_count INTEGER NOT NULL,
            success_rate REAL,                     -- % of times this led to cup formation
            typical_duration_days REAL,
            sample_stocks TEXT,                    -- JSON: example stocks
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Feature importance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feature_importance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            importance_score REAL NOT NULL,
            feature_type TEXT,                     -- screener, derived, market_condition
            ranking INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_version, feature_name)
        )
    ''')

    # 7. Analysis cache table (for storing intermediate results)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            cache_data TEXT NOT NULL,              -- JSON blob
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')

    # 8. Research logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_level TEXT NOT NULL,              -- INFO, WARNING, ERROR
            component TEXT NOT NULL,               -- which agent/script
            message TEXT NOT NULL,
            details TEXT,                         -- JSON with additional context
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_labeled_dataset_date ON labeled_dataset(observation_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_labeled_dataset_cup ON labeled_dataset(cup_formed)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_results_backtest ON backtest_results(backtest_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_research_logs_created ON research_logs(created_at)')

    conn.commit()
    conn.close()

    print(f"✅ Research database initialized: {DB_PATH}")
    print("📊 Tables created:")
    print("   - labeled_dataset")
    print("   - predictions")
    print("   - backtest_results")
    print("   - backtest_metrics")
    print("   - screener_temporal_patterns")
    print("   - feature_importance")
    print("   - analysis_cache")
    print("   - research_logs")


if __name__ == '__main__':
    create_database()
