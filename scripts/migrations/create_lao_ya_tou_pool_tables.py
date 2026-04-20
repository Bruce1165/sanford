"""
Database Migration: Create Lao Ya Tou Pool Tables

Creates tables and views for stock pool system.
Run this script once to initialize the pool schema.
"""

import sqlite3
import sys
from pathlib import Path

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

# Import DB_PATH from config
import config
DB_PATH = config.DB_PATH


def create_screener_types_table(conn):
    """Create screener_types table with initial data."""
    query = """
        CREATE TABLE IF NOT EXISTS screener_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) UNIQUE NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            description TEXT,
            is_pool_builder INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """
    conn.execute(query)

    # Insert initial data for 6 screeners
    screeners = [
        ('lao_ya_tou', '老鸭头周线', 1, 'Builds and manages LYT stock pool'),
        ('er_ban_hui_tiao', '二板回调', 0, 'Two-board pullback pattern'),
        ('shi_pan_xian', '涨停试盘线', 0, 'Limit-up test line pattern'),
        ('jin_feng_huang', '金凤凰', 0, 'Limit-up golden phoenix pattern'),
        ('yin_feng_huang', '银凤凰', 0, 'Limit-up silver phoenix pattern'),
        ('zhang_ting_bei_liang_yin', '涨停倍量阴', 0, 'Limit-up double volume bearish pattern'),
    ]

    for screener_code, display_name, is_builder, description in screeners:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO screener_types (code, display_name, is_pool_builder, description) VALUES (?, ?, ?, ?)",
                (screener_code, display_name, is_builder, description)
            )
        except Exception as e:
            print(f"Error inserting screener {screener_code}: {e}")


def create_lao_ya_tou_pool_table(conn):
    """Create lao_ya_tou_pool table."""
    query = """
        CREATE TABLE IF NOT EXISTS lao_ya_tou_pool (
            code VARCHAR(10) PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            entry_date DATE NOT NULL,
            current_signal VARCHAR(20) NOT NULL,
            last_screened_date DATE NOT NULL,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
        );
    """
    conn.execute(query)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pool_current_signal ON lao_ya_tou_pool(current_signal)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pool_entry_date ON lao_ya_tou_pool(entry_date)")


def create_lao_ya_tou_signal_history_table(conn):
    """Create lao_ya_tou_signal_history table."""
    query = """
        CREATE TABLE IF NOT EXISTS lao_ya_tou_signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(10) NOT NULL,
            old_signal VARCHAR(20),
            new_signal VARCHAR(20) NOT NULL,
            change_date DATE NOT NULL,
            changed_by_screener VARCHAR(50) NOT NULL,
            notes TEXT,
            FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
        );
    """
    conn.execute(query)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_history_code ON lao_ya_tou_signal_history(code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_history_date ON lao_ya_tou_signal_history(change_date DESC)")


def create_pool_screening_results_table(conn):
    """Create pool_screening_results table."""
    query = """
        CREATE TABLE IF NOT EXISTS pool_screening_results (
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
            FOREIGN KEY (code) REFERENCES stocks(code) ON UPDATE CASCADE
        );
    """
    conn.execute(query)

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pool_screener_date ON pool_screening_results(screener_id, screen_date DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pool_code_date ON pool_screening_results(code, screen_date DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pool_screener_code_date ON pool_screening_results(screener_id, code, screen_date DESC)")


def create_views(conn):
    """Create views for easy data access."""

    # v_pool_status: Current pool state with stock info
    conn.execute("DROP VIEW IF EXISTS v_pool_status")
    view_query = """
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
    """
    conn.execute(view_query)

    # v_pool_signal_history: Signal change history
    conn.execute("DROP VIEW IF EXISTS v_pool_signal_history")
    view_query = """
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
    """
    conn.execute(view_query)

    # v_pool_daily_screening_summary: Daily screening results
    conn.execute("DROP VIEW IF EXISTS v_pool_daily_screening_summary")
    view_query = """
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
    """
    conn.execute(view_query)

    # v_stock_all_screeners: All screening results for a stock
    conn.execute("DROP VIEW IF EXISTS v_stock_all_screeners")
    view_query = """
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
    """
    conn.execute(view_query)

    # v_pool_size_over_time: Pool size tracking
    conn.execute("DROP VIEW IF EXISTS v_pool_size_over_time")
    view_query = """
        CREATE VIEW v_pool_size_over_time AS
        SELECT
            entry_date,
            current_signal,
            COUNT(*) AS count
        FROM lao_ya_tou_pool
        GROUP BY entry_date, current_signal
        ORDER BY entry_date DESC;
    """
    conn.execute(view_query)


def run_migration():
    """Run complete migration."""
    print(f"Starting migration for LYT pool system...")
    print(f"Database: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Create tables
        print("Creating screener_types table...")
        create_screener_types_table(conn)

        print("Creating lao_ya_tou_pool table...")
        create_lao_ya_tou_pool_table(conn)

        print("Creating lao_ya_tou_signal_history table...")
        create_lao_ya_tou_signal_history_table(conn)

        print("Creating pool_screening_results table...")
        create_pool_screening_results_table(conn)

        # Create views
        print("Creating views...")
        create_views(conn)

        # Commit
        conn.commit()

        # Verify
        print("\nVerifying tables...")
        cursor = conn.cursor()

        for table in ['screener_types', 'lao_ya_tou_pool', 'lao_ya_tou_signal_history', 'pool_screening_results']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} rows")

        # Verify views
        print("\nVerifying views...")
        for view in ['v_pool_status', 'v_pool_signal_history', 'v_pool_daily_screening_summary',
                     'v_stock_all_screeners', 'v_pool_size_over_time']:
            cursor.execute(f"SELECT COUNT(*) FROM {view}")
            count = cursor.fetchone()[0]
            print(f"  {view}: {count} rows")

        conn.close()

        print("\nMigration completed successfully!")

    except Exception as e:
        print(f"Error during migration: {e}")
        if 'conn' in locals():
            conn.close()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
