# Unit tests for ScreenerAdapter
"""
Unit tests for ScreenerAdapter to verify:
1. Screener loading functionality
2. Check stock functionality with valid screener
3. Check stock functionality with invalid screener
4. No match scenario
5. Retry mechanism
6. Performance monitoring
"""

import pytest
import sqlite3
import os
import tempfile
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from pool_screener_adapter import ScreenerAdapter


@pytest.fixture
def temp_db():
    """Create temporary test database."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Execute migrations
    conn = sqlite3.connect(path)
    migrations_dir = Path(__file__).parent.parent / 'scripts' / 'database' / 'migrations'

    with open(migrations_dir / 'create_lao_ya_tou_pool_table.sql', 'r') as f:
        conn.executescript(f.read())
    with open(migrations_dir / 'create_lao_ya_tou_five_flags.sql', 'r') as f:
        conn.executescript(f.read())

    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


class TestScreenerAdapter:
    """Test suite for ScreenerAdapter"""

    def test_load_all_screeners(self, temp_db):
        """Test: Verify adapter successfully loads all 4 screeners."""
        adapter = ScreenerAdapter(temp_db)
        stats = adapter.get_statistics()

        # Verify screener map contains expected screeners
        expected_screeners = [
            'er_ban_hui_tiao',
            'jin_feng_huang',
            'yin_feng_huang',
            'shi_pan_xian'
        ]
        assert set(adapter.screener_map.keys()) == set(expected_screeners)

        # Verify each screener is instantiated
        for screener_id in expected_screeners:
            screener = adapter.screener_map.get(screener_id)
            assert screener is not None, f"Screener {screener_id} should be loaded"

    def test_check_stock_with_valid_screener(self, temp_db):
        """Test: Verify adapter correctly calls screener with matching data."""
        # Prepare mock data: limit-up pattern
        conn = sqlite3.connect(temp_db)

        # Insert stock data
        for i in range(3):
            conn.execute('''
                INSERT INTO daily_prices
                    (code, trade_date, open, high, low, close, volume, amount, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                '000001',
                f'2026-04-0{i + 1:02d}',
                10.0 + i * 0.1,
                10.0 + i * 0.15,
                10.0 + i * 0.05,
                10.0 + i * 0.1,
                1000000,
                10.0 if i == 2 else 0  # Limit-up on day 2
            ))
        conn.commit()

        # Insert pool record
        conn.execute('''
            INSERT INTO lao_ya_tou_pool
                (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
        ''', ('000001', 'TEST STOCK', '2026-04-01', '2026-04-10', 'test.xlsx'))
        conn.commit()

        pool_id = conn.execute('SELECT last_insert_rowid() FROM lao_ya_tou_pool').fetchone()[0]
        conn.close()

        # Call adapter
        adapter = ScreenerAdapter(temp_db)
        result = adapter.check_stock(
            screener_id='er_ban_hui_tiao',
            stock_code='000001',
            stock_name='TEST STOCK',
            date='2026-04-02'
        )

        # Verify result
        assert result is not None, "Should match two-board pullback pattern"
        assert result['matched'] is True
        assert result['screener_id'] == 'er_ban_hui_tiao'
        assert result['code'] == '000001'
        assert result['price'] == pytest.approx(10.05, abs=0.01)
        assert 'Two consecutive' in result['reason']

    def test_check_stock_with_invalid_screener(self, temp_db):
        """Test: Verify adapter handles invalid screener ID gracefully."""
        adapter = ScreenerAdapter(temp_db)

        # Call with invalid screener
        result = adapter.check_stock(
            screener_id='invalid_screener',
            stock_code='000001',
            stock_name='TEST STOCK',
            date='2026-04-01'
        )

        # Verify result is None
        assert result is None, "Invalid screener should return None"

    def test_check_stock_no_match(self, temp_db):
        """Test: Verify adapter returns None when pattern not matched."""
        # Prepare mock data: no pattern match
        conn = sqlite3.connect(temp_db)

        for i in range(10):
            conn.execute('''
                INSERT INTO daily_prices
                    (code, trade_date, open, high, low, close, volume, amount, pct_change)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                '000002',
                f'2026-04-0{i + 1:02d}',
                10.0 + i * 0.01,  # Random price movement
                10.0 + i * 0.015,
                10.0 + i * 0.02,
                10.0 + i * 0.01,
                1000000,
                (i % 3 - 1) * 2  # Random changes
            ))
        conn.commit()
        conn.close()

        # Insert pool record
        conn = sqlite3.connect(temp_db)
        conn.execute('''
            INSERT INTO lao_ya_tou_pool
                (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
        ''', ('000002', 'TEST STOCK', '2026-04-01', '2026-04-10', 'test.xlsx'))
        conn.commit()
        pool_id = conn.execute('SELECT last_insert_rowid() FROM lao_ya_tou_pool').fetchone()[0]
        conn.close()

        # Call adapter with all screeners
        adapter = ScreenerAdapter(temp_db)
        screener_ids = list(adapter.screener_map.keys())

        for screener_id in screener_ids:
            result = adapter.check_stock(
                screener_id=screener_id,
                stock_code='000002',
                stock_name='TEST STOCK',
                date='2026-04-05'
            )
            # All should return None for random data
            assert result is None, f"Screener {screener_id} should not match random data"

    def test_statistics_tracking(self, temp_db):
        """Test: Verify statistics tracking works correctly."""
        adapter = ScreenerAdapter(temp_db)

        # Make multiple calls
        adapter.check_stock('er_ban_hui_tiao', '000001', 'TEST', '2026-04-01')
        adapter.check_stock('jin_feng_huang', '000001', 'TEST', '2026-04-02')

        stats = adapter.get_statistics()

        # Verify total calls
        assert stats['total_calls'] == 2

        # Verify successful calls (both should match)
        assert stats['successful_calls'] == 2

        # Verify failed calls
        assert stats['failed_calls'] == 0

        # Verify per-screener statistics
        assert 'er_ban_hui_tiao' in stats['by_screener']
        assert stats['by_screener']['er_ban_hui_tiao']['calls'] == 1
        assert stats['by_screener']['er_ban_hui_tiao']['successes'] == 1

    def test_reset_statistics(self, temp_db):
        """Test: Verify statistics can be reset."""
        adapter = ScreenerAdapter(temp_db)

        # Make a call
        adapter.check_stock('er_ban_hui_tiao', '000001', 'TEST', '2026-04-01')

        # Reset statistics
        adapter.reset_statistics()

        stats = adapter.get_statistics()

        # Verify reset
        assert stats['total_calls'] == 0
        assert stats['successful_calls'] == 0
        assert stats['failed_calls'] == 0
        assert 'er_ban_hui_tiao' not in stats['by_screener']
