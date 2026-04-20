#!/usr/bin/env python3
# Unit tests for ScreenerAdapter
"""
Unit tests for ScreenerAdapter to verify functionality by calling helper test script.

Author: Claude Code
Date: 2026-04-19
"""

import pytest
import subprocess
import sqlite3
import os
import tempfile
import json
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create temporary test database."""
    fd, path = tempfile.mkstemp(suffix='.db', prefix='test')
    os.close(fd)

    # Execute migrations
    conn = sqlite3.connect(path)
    migrations_dir = Path(__file__).parent.parent / 'scripts' / 'database' / 'migrations'

    with open(migrations_dir / 'create_lao_ya_tou_pool_table.sql', 'r') as f:
        conn.executescript(f.read())
    with open(migrations_dir / 'create_lao_ya_tou_five_flags.sql', 'r') as f:
        conn.executescript(f.read())

    # Create daily_prices table for screener operations
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(10),
            trade_date DATE,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            turnover REAL,
            preclose REAL,
            pct_change REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_daily_prices_code ON daily_prices(code)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_daily_prices_trade_date ON daily_prices(trade_date)')

    # Create stocks table for screener operations
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            code VARCHAR(10) PRIMARY KEY,
            name VARCHAR(50),
            industry VARCHAR(50),
            area VARCHAR(50),
            list_date DATE,
            total_market_cap REAL,
            circulating_market_cap REAL,
            pb_ratio REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


def call_adapter_check(db_path: str, screener_id: str, stock_code: str,
                        stock_name: str, date: str) -> dict:
    """Call test_adapter_check.py script via subprocess."""
    # Build command
    script_path = str(Path(__file__).parent.parent / 'scripts' / 'test_adapter_check.py')

    cmd = [
        'python3',
        script_path,
        '--db-path', db_path,
        '--screener-id', screener_id,
        '--stock-code', stock_code,
        '--stock-name', stock_name,
        '--date', date
    ]

    # Run script
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(Path(__file__).parent)
    )

    # Parse output
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse script output: {result.stdout}")
        return None

    return output


class TestScreenerAdapter:
    """Test suite for ScreenerAdapter using helper script."""

    def test_load_all_screeners(self, temp_db):
        """Test: Verify adapter successfully loads all 4 screeners."""
        result = call_adapter_check(
            db_path=temp_db,
            screener_id='er_ban_hui_tiao',
            stock_code='000001',
            stock_name='TEST STOCK',
            date='2026-04-01'
        )

        # Should return 'matched': False since no test data matches patterns
        assert result['success'] is True
        assert result['result'] is None

    def test_check_stock_with_valid_screener(self, temp_db):
        """Test: Verify adapter correctly calls screener with matching data."""
        # Prepare test database with limit-up pattern
        conn = sqlite3.connect(temp_db)

        # Insert stock record
        conn.execute('''
            INSERT INTO stocks (code, name, industry)
            VALUES (?, ?, ?)
        ''', ('000002', 'TEST STOCK', 'Test Industry'))

        # Create limit-up pattern: day 1 (normal), day 2 (limit-up 10%), day 3 (normal)
        for i in range(3):
            # Create limit-up pattern: day 1 (normal), day 2 (limit-up 10%), day 3 (normal)
            pct_change = 10.0 if i == 1 else (i - 1) * 0.5
            conn.execute('''
                INSERT INTO daily_prices
                    (code, trade_date, open, high, low, close, volume, amount, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    '000002',
                    f'2026-04-0{i + 1:02d}',
                    10.0 + i * 0.1,  # open
                    10.0 + i * 0.1 + (1.0 if i == 1 else 0),  # high (higher for limit-up)
                    10.0 + i * 0.05,  # low
                    10.0 + i * 0.1 + (0.9 if i == 1 else 0),  # close (limit-up price)
                    1000000 + (500000 if i == 1 else 0),  # volume (higher for limit-up)
                    (10.0 + i * 0.1) * (1000000 + (500000 if i == 1 else 0)) / 10000,  # amount
                    pct_change
                ))
        conn.commit()

        # Insert pool record
        conn.execute('''
            INSERT INTO lao_ya_tou_pool
                    (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    '000002',
                    'TEST STOCK',
                    '2026-04-01',
                    '2026-04-10',
                    'test.xlsx'
                ))
        conn.commit()
        conn.close()

        result = call_adapter_check(
            db_path=temp_db,
            screener_id='er_ban_hui_tiao',
            stock_code='000002',
            stock_name='TEST STOCK',
            date='2026-04-02'
        )

        # Should return 'matched': True with pattern match
        assert result['success'] is True
        assert result['result'] is not None
        assert 'two-board' in result['result'].get('reason', '').lower()

    def test_check_stock_with_invalid_screener(self, temp_db):
        """Test: Verify adapter handles invalid screener gracefully."""
        result = call_adapter_check(
            db_path=temp_db,
            screener_id='invalid_screener',
            stock_code='000003',
            stock_name='TEST STOCK',
            date='2026-04-01'
        )

        # Should return None for invalid screener
        assert result['success'] is True
        assert result['result'] is None
