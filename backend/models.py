#!/usr/bin/env python3
"""
Dashboard Database Models
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Dict, List

# Use the dashboard database
DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"

@contextmanager
def get_db_connection_context():
    """Get database connection with automatic cleanup - use for new code"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database tables"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Screener definitions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screeners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            file_path TEXT NOT NULL,
            config TEXT,  -- JSON config
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Screener runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT NOT NULL,
            run_date DATE NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            stocks_found INTEGER DEFAULT 0,
            UNIQUE(screener_name, run_date)
        )
    ''')
    
    # Screener results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            close_price REAL,
            turnover REAL,
            pct_change REAL,
            extra_data TEXT,  -- JSON for screener-specific data
            FOREIGN KEY (run_id) REFERENCES screener_runs(id) ON DELETE CASCADE
        )
    ''')
    
    # Stock price data cache for charts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_price_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date DATE NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL,
            UNIQUE(stock_code, trade_date)
        )
    ''')
    
    # Strategy backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_version TEXT NOT NULL,
            screener_name TEXT NOT NULL,
            params TEXT NOT NULL,  -- JSON encoded parameters
            train_start DATE NOT NULL,
            train_end DATE NOT NULL,
            total_return REAL DEFAULT 0,
            sharpe_ratio REAL DEFAULT 0,
            max_drawdown REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            profit_factor REAL DEFAULT 0,
            calmar_ratio REAL DEFAULT 0,
            volatility REAL DEFAULT 0,
            avg_trade_return REAL DEFAULT 0,
            avg_hold_days REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            git_commit TEXT,
            parent_version TEXT  -- Previous generation for lineage
        )
    ''')
    
    # Strategy trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL,
            trade_date DATE NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            action TEXT NOT NULL,  -- BUY, SELL
            price REAL NOT NULL,
            shares INTEGER,
            position_value REAL,
            realized_pnl REAL,
            realized_pnl_pct REAL,
            hold_days INTEGER,
            exit_reason TEXT,  -- target_hit, stop_loss, timeout, end_of_data
            FOREIGN KEY (backtest_id) REFERENCES strategy_backtest_results(id) ON DELETE CASCADE
        )
    ''')
    
    # Experiment configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS experiment_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT NOT NULL,
            param_space TEXT NOT NULL,  -- JSON: parameter ranges and constraints
            mutation_strategy TEXT DEFAULT 'gaussian',  -- gaussian, grid, random
            population_size INTEGER DEFAULT 10,
            elite_ratio REAL DEFAULT 0.2,
            mutation_rate REAL DEFAULT 0.3,
            crossover_rate REAL DEFAULT 0.5,
            max_generations INTEGER DEFAULT 100,
            early_stop_patience INTEGER DEFAULT 20,
            target_sharpe REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Access log table for visitor statistics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            user_agent TEXT,
            request_path TEXT,
            access_date DATE NOT NULL,
            access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Access statistics summary (daily aggregation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date DATE UNIQUE NOT NULL,
            daily_count INTEGER DEFAULT 0,
            unique_ips INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ========== Strategy Tables ==========

    # Strategy definitions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            file_path TEXT,
            config_json TEXT,
            version TEXT DEFAULT 'v1.0.0',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Strategy runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            run_date DATE NOT NULL,
            status TEXT DEFAULT 'pending',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            config_snapshot TEXT,
            stocks_analyzed INTEGER DEFAULT 0,
            signals_found INTEGER DEFAULT 0,
            error_message TEXT,
            UNIQUE(strategy_name, run_date),
            FOREIGN KEY (strategy_name) REFERENCES strategies(name)
        )
    ''')

    # Strategy signals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            signal_type TEXT NOT NULL,
            signal_strength REAL,
            signal_reason TEXT,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            risk_reward_ratio REAL,
            confidence_score REAL,
            extra_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES strategy_runs(id) ON DELETE CASCADE
        )
    ''')

    # Strategy performance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            run_id INTEGER NOT NULL,
            total_signals INTEGER DEFAULT 0,
            buy_signals INTEGER DEFAULT 0,
            sell_signals INTEGER DEFAULT 0,
            watch_signals INTEGER DEFAULT 0,
            avg_signal_strength REAL,
            avg_confidence REAL,
            top_stocks TEXT,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_name) REFERENCES strategies(name),
            FOREIGN KEY (run_id) REFERENCES strategy_runs(id)
        )
    ''')

    # ========== Screener Config Tables ==========

    # Screener configs table (current config)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            config_json TEXT NOT NULL,
            config_schema TEXT NOT NULL,
            current_version TEXT DEFAULT 'v1.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Screener config history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_config_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT NOT NULL,
            version TEXT NOT NULL,
            config_json TEXT NOT NULL,
            config_schema TEXT NOT NULL,
            change_summary TEXT,
            changed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (screener_name) REFERENCES screener_configs(screener_name)
        )
    ''')

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screener_runs_lookup ON screener_runs(screener_name, run_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screener_results_run_id ON screener_results(run_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_price_cache_lookup ON stock_price_cache(stock_code, trade_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_date ON access_logs(access_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_access_logs_ip_date ON access_logs(ip_address, access_date)')

    # Strategy indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_runs_lookup ON strategy_runs(strategy_name, run_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_signals_run ON strategy_signals(run_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_signals_code ON strategy_signals(stock_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_signals_type ON strategy_signals(signal_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy ON strategy_performance(strategy_name)')

    # Screener config indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screener_configs_name ON screener_configs(screener_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screener_config_history_name ON screener_config_history(screener_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_screener_config_history_version ON screener_config_history(screener_name, version)')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_stock_db_connection():
    """Get stock data database connection"""
    stock_db_path = DB_PATH.parent / "stock_data.db"
    conn = sqlite3.connect(stock_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

# Screener operations
def get_all_screeners():
    """Get all registered screeners"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_screener(name):
    """Get screener by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def register_screener(name, display_name, description, file_path, config=None):
    """Register or update a screener"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    config_json = json.dumps(config) if config else None
    
    cursor.execute('''
        INSERT INTO screeners (name, display_name, description, file_path, config)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = excluded.display_name,
            description = excluded.description,
            file_path = excluded.file_path,
            config = excluded.config,
            updated_at = CURRENT_TIMESTAMP
    ''', (name, display_name, description, file_path, config_json))
    
    conn.commit()
    conn.close()

def delete_screener(name):
    """Delete a screener from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM screeners WHERE name = ?', (name,))
    conn.commit()
    conn.close()

def update_screener(name, display_name=None, description=None):
    """Update screener metadata"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if display_name is not None:
        updates.append('display_name = ?')
        params.append(display_name)
    
    if description is not None:
        updates.append('description = ?')
        params.append(description)
    
    if updates:
        updates.append('updated_at = CURRENT_TIMESTAMP')
        query = f"UPDATE screeners SET {', '.join(updates)} WHERE name = ?"
        params.append(name)
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()

# Screener run operations
def create_run(screener_name, run_date):
    """Create a new screener run record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO screener_runs (screener_name, run_date, status, started_at)
            VALUES (?, ?, 'running', CURRENT_TIMESTAMP)
        ''', (screener_name, run_date))
        run_id = cursor.lastrowid
        conn.commit()
        return run_id
    except sqlite3.IntegrityError:
        # Already exists, update status
        cursor.execute('''
            UPDATE screener_runs 
            SET status = 'running', started_at = CURRENT_TIMESTAMP, 
                completed_at = NULL, error_message = NULL, stocks_found = 0
            WHERE screener_name = ? AND run_date = ?
        ''', (screener_name, run_date))
        conn.commit()
        
        cursor.execute('''
            SELECT id FROM screener_runs WHERE screener_name = ? AND run_date = ?
        ''', (screener_name, run_date))
        run_id = cursor.fetchone()[0]
        
        # Clear old results
        cursor.execute('DELETE FROM screener_results WHERE run_id = ?', (run_id,))
        conn.commit()
        return run_id
    finally:
        conn.close()

def complete_run(run_id, stocks_found=0, error_message=None):
    """Mark a run as completed or failed"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status = 'failed' if error_message else 'completed'
    
    cursor.execute('''
        UPDATE screener_runs 
        SET status = ?, completed_at = CURRENT_TIMESTAMP, 
            stocks_found = ?, error_message = ?
        WHERE id = ?
    ''', (status, stocks_found, error_message, run_id))
    
    conn.commit()
    conn.close()

def get_run(screener_name, run_date):
    """Get run by screener and date"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM screener_runs WHERE screener_name = ? AND run_date = ?
    ''', (screener_name, run_date))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_runs(screener_name=None, limit=50):
    """Get historical runs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if screener_name:
        cursor.execute('''
            SELECT * FROM screener_runs 
            WHERE screener_name = ?
            ORDER BY run_date DESC
            LIMIT ?
        ''', (screener_name, limit))
    else:
        cursor.execute('''
            SELECT * FROM screener_runs 
            ORDER BY run_date DESC
            LIMIT ?
        ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Results operations
def save_result(run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_data=None):
    """Save a screener result"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    extra_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else None
    
    cursor.execute('''
        INSERT INTO screener_results 
        (run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_json))
    
    conn.commit()
    conn.close()

def get_results(run_id):
    """Get results for a run, joined with stocks table for PE/PB/market_cap/industry"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Try to find the stock_data.db path for joining
    import os
    # Use relative path: models.py is in backend/, so parent is NeoTrade2 root
    WORKSPACE_ROOT = Path(__file__).parent.parent
    stock_db = str(WORKSPACE_ROOT / 'data' / 'stock_data.db')

    cursor.execute('''
        SELECT * FROM screener_results WHERE run_id = ?
    ''', (run_id,))

    rows = cursor.fetchall()
    conn.close()

    # Build lookup from stock_data.db if available
    stock_info = {}
    if stock_db:
        try:
            import sqlite3 as _sqlite3
            sconn = _sqlite3.connect(stock_db)
            sconn.row_factory = _sqlite3.Row
            scursor = sconn.cursor()
            scursor.execute('''
                SELECT code, name, industry, pe_ratio, pb_ratio,
                       total_market_cap, circulating_market_cap
                FROM stocks
            ''')
            for srow in scursor.fetchall():
                stock_info[srow['code']] = dict(srow)
            sconn.close()
        except Exception as e:
            print(f'WARN: Could not join stocks table: {e}')

    results = []
    for row in rows:
        d = dict(row)
        if d.get('extra_data'):
            d['extra_data'] = json.loads(d['extra_data'])
        # Enrich with stock fundamental data
        code = d.get('stock_code', '')
        if code in stock_info:
            s = stock_info[code]
            d['industry']             = s.get('industry', '–')
            d['pe_ratio']             = s.get('pe_ratio')
            d['pb_ratio']             = s.get('pb_ratio')
            d['total_market_cap']     = s.get('total_market_cap')
            d['circulating_market_cap'] = s.get('circulating_market_cap')
        results.append(d)
    return results

def get_results_by_date(screener_name, run_date):
    """Get results by screener and date"""
    run = get_run(screener_name, run_date)
    if not run:
        return None

    results = get_results(run['id'])
    return {
        'results': results,
        'stocks_found': run.get('stocks_found', 0)
    }

# Stock price cache operations
def cache_stock_prices(stock_code, df):
    """Cache stock price data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO stock_price_cache 
            (stock_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_code,
            row['trade_date'].strftime('%Y-%m-%d') if hasattr(row['trade_date'], 'strftime') else row['trade_date'],
            row['open'], row['high'], row['low'], row['close'],
            row.get('volume', 0), row.get('amount', 0)
        ))
    
    conn.commit()
    conn.close()

def get_cached_prices(stock_code, days=60):
    """Get cached prices for a stock"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM stock_price_cache 
        WHERE stock_code = ?
        ORDER BY trade_date DESC
        LIMIT ?
    ''', (stock_code, days))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Access log operations
def log_access(ip_address, user_agent, request_path):
    """Log a single access"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
        INSERT INTO access_logs (ip_address, user_agent, request_path, access_date)
        VALUES (?, ?, ?, ?)
    ''', (ip_address, user_agent, request_path, today))
    
    conn.commit()
    conn.close()

def update_daily_stats():
    """Update daily access statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Count today's accesses (excluding local IPs)
    cursor.execute('''
        SELECT COUNT(*) as total_count, COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date = ? 
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (today,))
    
    row = cursor.fetchone()
    daily_count = row['total_count']
    unique_ips = row['unique_ips']
    
    # Upsert daily stats
    cursor.execute('''
        INSERT INTO access_stats (stat_date, daily_count, unique_ips)
        VALUES (?, ?, ?)
        ON CONFLICT(stat_date) DO UPDATE SET
            daily_count = excluded.daily_count,
            unique_ips = excluded.unique_ips,
            updated_at = CURRENT_TIMESTAMP
    ''', (today, daily_count, unique_ips))
    
    conn.commit()
    conn.close()

def get_access_stats():
    """Get access statistics for today and this month (count unique IPs only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    
    # Today's unique IP count (each IP counted once per day)
    cursor.execute('''
        SELECT COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date = ?
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (today,))
    
    today_row = cursor.fetchone()
    
    # This month's unique IP count
    cursor.execute('''
        SELECT COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date >= ?
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (first_day_of_month,))
    
    month_row = cursor.fetchone()
    conn.close()
    
    return {
        'today': {
            'date': today,
            'unique_visitors': today_row['unique_ips']
        },
        'this_month': {
            'start_date': first_day_of_month,
            'end_date': today,
            'unique_visitors': month_row['unique_ips']
        }
    }

# ========== Strategy Operations ==========

def get_all_strategies():
    """Get all registered strategies"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategies ORDER BY category, name")
    rows = cursor.fetchall()
    conn.close()
    strategies = []
    for row in rows:
        d = dict(row)
        if d.get('config_json'):
            d['config_json'] = json.loads(d['config_json'])
        strategies.append(d)
    return strategies

def get_strategy(name):
    """Get strategy by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategies WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if d.get('config_json'):
            d['config_json'] = json.loads(d['config_json'])
        return d
    return None

def register_strategy(name, display_name, description, category, file_path, config=None, version='v1.0.0'):
    """Register or update a strategy"""
    conn = get_db_connection()
    cursor = conn.cursor()

    config_json = json.dumps(config) if config else None

    cursor.execute('''
        INSERT INTO strategies (name, display_name, description, category, file_path, config_json, version)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = excluded.display_name,
            description = excluded.description,
            category = excluded.category,
            file_path = excluded.file_path,
            config_json = excluded.config_json,
            version = excluded.version,
            updated_at = CURRENT_TIMESTAMP
    ''', (name, display_name, description, category, file_path, config_json, version))

    conn.commit()
    conn.close()

def delete_strategy(name):
    """Delete a strategy from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM strategies WHERE name = ?', (name,))
    conn.commit()
    conn.close()

def update_strategy(name, display_name=None, description=None, category=None, config=None, is_active=None):
    """Update strategy metadata"""
    conn = get_db_connection()
    cursor = conn.cursor()

    updates = []
    params = []

    if display_name is not None:
        updates.append('display_name = ?')
        params.append(display_name)

    if description is not None:
        updates.append('description = ?')
        params.append(description)

    if category is not None:
        updates.append('category = ?')
        params.append(category)

    if config is not None:
        updates.append('config_json = ?')
        params.append(json.dumps(config))

    if is_active is not None:
        updates.append('is_active = ?')
        params.append(is_active)

    if updates:
        updates.append('updated_at = CURRENT_TIMESTAMP')
        query = f"UPDATE strategies SET {', '.join(updates)} WHERE name = ?"
        params.append(name)
        cursor.execute(query, params)
        conn.commit()

    conn.close()

# Strategy run operations
def create_strategy_run(strategy_name, run_date, config_snapshot=None):
    """Create a new strategy run record"""
    conn = get_db_connection()
    cursor = conn.cursor()

    config_json = json.dumps(config_snapshot) if config_snapshot else None

    try:
        cursor.execute('''
            INSERT INTO strategy_runs (strategy_name, run_date, status, started_at, config_snapshot)
            VALUES (?, ?, 'running', CURRENT_TIMESTAMP, ?)
        ''', (strategy_name, run_date, config_json))
        run_id = cursor.lastrowid
        conn.commit()
        return run_id
    except sqlite3.IntegrityError:
        # Already exists, update status
        cursor.execute('''
            UPDATE strategy_runs
            SET status = 'running', started_at = CURRENT_TIMESTAMP,
                completed_at = NULL, error_message = NULL, stocks_analyzed = 0, signals_found = 0
            WHERE strategy_name = ? AND run_date = ?
        ''', (strategy_name, run_date))
        conn.commit()

        cursor.execute('''
            SELECT id FROM strategy_runs WHERE strategy_name = ? AND run_date = ?
        ''', (strategy_name, run_date))
        run_id = cursor.fetchone()[0]

        # Clear old signals and performance
        cursor.execute('DELETE FROM strategy_signals WHERE run_id = ?', (run_id,))
        cursor.execute('DELETE FROM strategy_performance WHERE run_id = ?', (run_id,))
        conn.commit()
        return run_id
    finally:
        conn.close()

def complete_strategy_run(run_id, stocks_analyzed=0, signals_found=0, error_message=None):
    """Mark a strategy run as completed or failed"""
    conn = get_db_connection()
    cursor = conn.cursor()

    status = 'failed' if error_message else 'completed'

    cursor.execute('''
        UPDATE strategy_runs
        SET status = ?, completed_at = CURRENT_TIMESTAMP,
            stocks_analyzed = ?, signals_found = ?, error_message = ?
        WHERE id = ?
    ''', (status, stocks_analyzed, signals_found, error_message, run_id))

    conn.commit()
    conn.close()

def get_strategy_run(strategy_name, run_date):
    """Get strategy run by strategy name and date"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM strategy_runs WHERE strategy_name = ? AND run_date = ?
    ''', (strategy_name, run_date))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        if d.get('config_snapshot'):
            d['config_snapshot'] = json.loads(d['config_snapshot'])
        return d
    return None

def get_strategy_runs(strategy_name=None, limit=50):
    """Get strategy run history"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if strategy_name:
        cursor.execute('''
            SELECT * FROM strategy_runs
            WHERE strategy_name = ?
            ORDER BY run_date DESC
            LIMIT ?
        ''', (strategy_name, limit))
    else:
        cursor.execute('''
            SELECT * FROM strategy_runs
            ORDER BY run_date DESC
            LIMIT ?
        ''', (limit,))

    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        if d.get('config_snapshot'):
            d['config_snapshot'] = json.loads(d['config_snapshot'])
        results.append(d)
    return results

# Strategy signal operations
def save_strategy_signal(run_id, stock_code, stock_name, signal_type, signal_strength=None,
                        signal_reason=None, entry_price=None, stop_loss=None, take_profit=None,
                        risk_reward_ratio=None, confidence_score=None, extra_data=None):
    """Save a strategy signal"""
    conn = get_db_connection()
    cursor = conn.cursor()

    extra_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else None

    cursor.execute('''
        INSERT INTO strategy_signals
        (run_id, stock_code, stock_name, signal_type, signal_strength, signal_reason,
         entry_price, stop_loss, take_profit, risk_reward_ratio, confidence_score, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, stock_code, stock_name, signal_type, signal_strength, signal_reason,
          entry_price, stop_loss, take_profit, risk_reward_ratio, confidence_score, extra_json))

    conn.commit()
    conn.close()

def get_strategy_signals(run_id):
    """Get signals for a strategy run"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM strategy_signals WHERE run_id = ? ORDER BY signal_strength DESC', (run_id,))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        if d.get('extra_data'):
            d['extra_data'] = json.loads(d['extra_data'])
        results.append(d)
    return results

def get_strategy_signals_by_date(strategy_name, run_date):
    """Get strategy signals by strategy name and date"""
    run = get_strategy_run(strategy_name, run_date)
    if not run:
        return None
    return get_strategy_signals(run['id'])

# Strategy performance operations
def save_strategy_performance(strategy_name, run_id, total_signals=0, buy_signals=0,
                              sell_signals=0, watch_signals=0, avg_signal_strength=None,
                              avg_confidence=None, top_stocks=None):
    """Save strategy performance statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    top_stocks_json = json.dumps(top_stocks, ensure_ascii=False) if top_stocks else None

    cursor.execute('''
        INSERT INTO strategy_performance
        (strategy_name, run_id, total_signals, buy_signals, sell_signals, watch_signals,
         avg_signal_strength, avg_confidence, top_stocks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (strategy_name, run_id, total_signals, buy_signals, sell_signals, watch_signals,
          avg_signal_strength, avg_confidence, top_stocks_json))

    conn.commit()
    conn.close()

def get_strategy_performance(strategy_name, run_date):
    """Get strategy performance by strategy name and date"""
    run = get_strategy_run(strategy_name, run_date)
    if not run:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM strategy_performance WHERE run_id = ?', (run['id'],))
    row = cursor.fetchone()
    conn.close()

    if row:
        d = dict(row)
        if d.get('top_stocks'):
            d['top_stocks'] = json.loads(d['top_stocks'])
        return d
    return None

# ========== Screener Config Operations ==========

def get_screener_config(screener_name: str) -> Optional[Dict]:
    """获取筛选器当前配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM screener_configs WHERE screener_name = ?
    ''', (screener_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        # Parse JSON fields from database
        try:
            d['config_json'] = json.loads(d['config_json'])
        except Exception as e:
            print(f"[DEBUG get_screener_config] Failed to parse config_json: {e}")

        try:
            d['config_schema'] = json.loads(d['config_schema'])
        except Exception as e:
            print(f"[DEBUG get_screener_config] Failed to parse config_schema: {e}")
        return d
    return None

def save_screener_config(screener_name: str, config: Dict, schema: Dict, change_summary: str = '', changed_by: str = 'system') -> str:
    """保存筛选器配置（自动备份旧版本）"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Convert config and schema to JSON for storage
    config_json = json.dumps(config, ensure_ascii=False) if config else '{}'
    schema_json = json.dumps(schema, ensure_ascii=False) if schema else '{}'

    # 检查是否已存在
    existing = get_screener_config(screener_name)

    if existing:
        # 备份旧版本到历史表
        cursor.execute('''
            INSERT INTO screener_config_history
            (screener_name, version, config_json, config_schema, change_summary, changed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            screener_name,
            existing['current_version'],
            json.dumps(existing['config_json'], ensure_ascii=False),
            json.dumps(existing['config_schema'], ensure_ascii=False),
            '自动备份: ' + change_summary,
            changed_by
        ))

        # 生成新版本号
        old_version = existing['current_version']
        # 简单版本号递增：v1.0 -> v1.1
        if old_version.startswith('v'):
            try:
                version_num = float(old_version[1:])
                new_version = f"v{version_num + 0.1:.1f}"
            except:
                new_version = f"{old_version}.1"
        else:
            new_version = f"{old_version}.1"

        # 更新当前配置
        cursor.execute('''
            UPDATE screener_configs
            SET display_name = ?, description = ?, category = ?,
                config_json = ?, config_schema = ?, current_version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE screener_name = ?
        ''', (
            config.get('display_name', ''),
            config.get('description', ''),
            config.get('category', ''),
            config_json,
            schema_json,
            new_version,
            screener_name
        ))

        conn.commit()
        conn.close()
        return new_version
    else:
        # 创建新配置
        new_version = 'v1.0'
        cursor.execute('''
            INSERT INTO screener_configs
            (screener_name, display_name, description, category, config_json, config_schema, current_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            screener_name,
            config.get('display_name', screener_name),
            config.get('description', ''),
            config.get('category', '未分类'),
            config_json,
            schema_json,
            new_version
        ))

        conn.commit()
        conn.close()
        return new_version

def get_screener_config_versions(screener_name: str, limit: int = 10) -> List[Dict]:
    """获取筛选器配置版本历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM screener_config_history
        WHERE screener_name = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (screener_name, limit))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        d['config_json'] = json.loads(d['config_json'])
        results.append(d)
    return results

def rollback_screener_config(screener_name: str, target_version: str) -> bool:
    """回滚筛选器配置到指定版本"""
    # 获取目标版本配置
    versions = get_screener_config_versions(screener_name, limit=100)
    target_config = None
    for v in versions:
        if v['version'] == target_version:
            target_config = v
            break

    if not target_config:
        return False

    # 获取当前配置并备份
    current = get_screener_config(screener_name)
    if current:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO screener_config_history
            (screener_name, version, config_json, config_schema, change_summary, changed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            screener_name,
            current['current_version'],
            json.dumps(current['config_json'], ensure_ascii=False),
            json.dumps(current['config_schema'], ensure_ascii=False),
            f"回滚前的版本",
            'system'
        ))
        conn.commit()
        conn.close()

    # 恢复目标版本到当前配置
    new_version = save_screener_config(
        screener_name,
        target_config['config_json'],
        target_config['config_schema'],
        change_summary=f"回滚到 {target_version}",
        changed_by='system'
    )

    return True

def get_all_screener_configs() -> List[Dict]:
    """获取所有筛选器配置列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT screener_name, display_name, category, current_version, updated_at
        FROM screener_configs
        ORDER BY category, display_name
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == '__main__':
    init_db()
