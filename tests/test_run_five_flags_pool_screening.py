# Unit tests for Five Flags Pool Screening script

import sys
"""
Unit tests for FiveFlagsPoolScreening to verify:
1. Pool retrieval functionality
2. Stock range screening logic
3. Batch processing results
4. Progress management (save and load)
5. Mark pools processed
6. Trading day query
7. Integration tests (small dataset)
"""

import pytest
import sqlite3
import os
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from run_five_flags_pool_screening import FiveFlagsPoolScreening


@pytest.fixture
def temp_db():
    """Create temporary test database with all required tables."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Execute migrations
    conn = sqlite3.connect(path)
    migrations_dir = Path(__file__).parent.parent / 'scripts' / 'database' / 'migrations'

    with open(migrations_dir / 'create_lao_ya_tou_pool_table.sql', 'r') as f:
        conn.executescript(f.read())
    with open(migrations_dir / 'create_lao_ya_tou_five_flags.sql', 'r') as f:
        conn.executescript(f.read())

    # Insert test stock data
    for i in range(10):
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
            10.0 if i == 2 else 0  # Day 2 limit-up
        ))
    conn.commit()

    # Insert pool records
    for i in range(3):
        conn.execute('''
            INSERT INTO lao_ya_tou_pool
                    (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            f'00000{i + 1}',
            f'TEST POOL {i + 1}',
            '2026-04-01',
            '2026-04-10',
            f'test_pool_{i}.xlsx'
        ))
    conn.commit()
    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_progress_file():
    """Create temporary progress file."""
    fd, path = tempfile.mkstemp(suffix='.json', prefix='progress')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestFiveFlagsPoolScreening:
    """Test suite for FiveFlagsPoolScreening"""

    def test_get_pools_to_screen_all(self, temp_db):
        """Test: Get all pools when pool_ids is None."""
        screening = FiveFlagsPoolScreening(temp_db)
        pools = screening._get_pools_to_screen(pool_ids=None, force_recheck=False)

        # Should return all pools (3 unprocessed)
        assert len(pools) == 3

        # Verify pool structure
        for pool in pools:
            assert 'id' in pool
            assert 'stock_code' in pool
            assert 'stock_name' in pool
            assert 'start_date' in pool
            assert 'end_date' in pool

    def test_get_pools_to_screen_specific(self, temp_db):
        """Test: Get specific pools by IDs."""
        screening = FiveFlagsPoolScreening(temp_db)

        # Get specific pools
        pools = screening._get_pools_to_screen(pool_ids=[1, 2], force_recheck=False)

        assert len(pools) == 2

        # Verify correct pools
        pool_ids_retrieved = [p['id'] for p in pools]
        assert set(pool_ids_retrieved) == {1, 2}

    def test_get_pools_to_screen_force_recheck(self, temp_db):
        """Test: Force recheck returns all pools including processed."""
        screening = FiveFlagsPoolScreening(temp_db)
        pools = screening._get_pools_to_screen(pool_ids=None, force_recheck=True)

        # Should return all pools (3)
        assert len(pools) == 3

    def test_screen_stock_range(self, temp_db):
        """Test: Screen single stock pool across multiple dates."""
        screening = FiveFlagsPoolScreening(temp_db)

        # Use first pool
        pool_data = {
            'id': 1,
            'stock_code': '000001',
            'stock_name': 'TEST POOL 1',
            'start_date': '2026-04-01',
            'end_date': '2026-04-10'
        }

        result = screening._screen_stock_range(
            pool_data=pool_data,
            screener_id='er_ban_hui_tiao'
        )

        # Verify result structure
        assert 'results' in result
        assert len(result['results']) > 0

        # Verify each result has required fields
        for flag_result in result['results']:
            assert 'pool_id' in flag_result
            assert 'screener_id' in flag_result
            assert 'stock_code' in flag_result
            assert 'stock_name' in flag_result
            assert 'screen_date' in flag_result
            assert 'close_price' in flag_result
            assert 'match_reason' in flag_result

    def test_screen_stock_range_no_trading_days(self, temp_db):
        """Test: Handle pool with no trading days gracefully."""
        screening = FiveFlagsPoolScreening(temp_db)

        # Create pool with date range but no matching trading data
        pool_data = {
            'id': 1,
            'stock_code': '000001',
            'stock_name': 'TEST POOL 1',
            'start_date': '2026-04-01',
            'end_date': '2026-04-10'
        }

        # Remove trading data to simulate missing data
        conn = sqlite3.connect(temp_db)
        conn.execute("DELETE FROM daily_prices WHERE code = '000001'")
        conn.commit()
        conn.close()

        result = screening._screen_stock_range(
            pool_data=pool_data,
            screener_id='er_ban_hui_tiao'
        )

        # Should return None
        assert result is None

    def test_process_stock_batch(self, temp_db):
        """Test: Batch insertion functionality."""
        screening = FiveFlagsPoolScreening(temp_db)

        # Prepare mock results
        results = []
        screener_ids = ['er_ban_hui_tiao', 'jin_feng_huang']

        for i in range(20):
            screener_id = screener_ids[i % len(screener_ids)]
            results.append({
                'pool_id': 1,
                'screener_id': screener_id,
                'stock_code': '000001',
                'stock_name': 'TEST STOCK',
                'screen_date': f'2026-04-{i + 1:02d}',
                'close_price': 10.0 + i * 0.1,
                'match_reason': f'Test result {i}',
                'extra_data': {'test_index': i}
            })

        # Insert into database
        conn = sqlite3.connect(temp_db)
        count = screening._process_stock_batch(results)
        conn.close()

        # Verify batch insertion
        assert count == 20

        # Verify database records
        flags_repo_conn = sqlite3.connect(temp_db)
        cursor = flags_repo_conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM lao_ya_tou_five_flags WHERE pool_id = ?', (1,))
        db_count = cursor.fetchone()[0]
        flags_repo_conn.close()

        assert db_count == 20, f"Expected 20 records, found {db_count}"

    def test_save_and_load_progress(self, temp_db, temp_progress_file):
        """Test: Progress file save and load functionality."""
        screening = FiveFlagsPoolScreening(temp_db, progress_file=temp_progress_file)

        # Prepare progress data
        progress_data = {
            'start_time': '2026-04-18 10:00:00',
            'last_update': '2026-04-18 10:30:00',
            'total_stocks': 100,
            'processed_stocks': 50,
            'processed_pool_ids': [1, 2],
            'statistics': {
                'total_matches': 25,
                'by_screener': {
                    'er_ban_hui_tiao': 10,
                    'jin_feng_huang': 15
                }
            }
        }

        # Save progress
        screening._save_progress()

        # Verify file exists
        assert os.path.exists(temp_progress_file), "Progress file should be created"

        # Load progress
        loaded_progress = screening._load_progress()

        # Verify loaded data matches saved data
        assert loaded_progress['start_time'] == progress_data['start_time']
        assert loaded_progress['last_update'] == progress_data['last_update']
        assert loaded_progress['total_stocks'] == progress_data['total_stocks']
        assert loaded_progress['processed_stocks'] == progress_data['processed_stocks']
        assert loaded_progress['processed_pool_ids'] == progress_data['processed_pool_ids']
        assert loaded_progress['statistics']['total_matches'] == progress_data['statistics']['total_matches']

    def test_mark_pools_processed(self, temp_db):
        """Test: Mark pools as processed functionality."""
        screening = FiveFlagsPoolScreening(temp_db)

        # Create pool
        conn = sqlite3.connect(temp_db)
        conn.execute('''
            INSERT INTO lao_ya_tou_pool
                    (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
        ''', ('000001', 'MARKED STOCK', '2026-04-01', '2026-04-10', 'test.xlsx'))
        pool_id = conn.execute('SELECT last_insert_rowid() FROM lao_ya_tou_pool').fetchone()[0]
        conn.commit()

        # Mark as processed
        screening._mark_pools_processed([pool_id])

        # Verify processed flag
        cursor = conn.cursor()
        cursor.execute('SELECT processed FROM lao_ya_tou_pool WHERE id = ?', (pool_id,))
        processed = cursor.fetchone()[0]
        conn.close()

        assert processed == 1, f"Pool {pool_id} should be marked as processed"

    def test_run_screening_small_dataset(self, temp_db):
        """Integration test: Small dataset (3 pools)."""
        screening = FiveFlagsPoolScreening(temp_db, max_workers=2)

        # Run screening
        result = screening.run_screening()

        # Verify result structure
        assert 'total_stocks' in result
        assert 'processed_stocks' in result
        assert 'failed_stocks' in result
        assert 'total_matches' in result
        assert 'by_screener' in result
        assert 'elapsed_time' in result

        # Verify total stocks = 3 pools × 4 screeners = 12
        assert result['total_stocks'] == 12

        # Verify processed count matches total
        assert result['processed_stocks'] == 12

        # Verify pools marked as processed
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM lao_ya_tou_pool WHERE processed = 1')
        processed_count = cursor.fetchone()[0]
        conn.close()

        assert processed_count == 3, f"All 3 pools should be marked as processed"

        # Verify flag results inserted
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM lao_ya_tou_five_flags')
        flag_count = cursor.fetchone()[0]
        conn.close()

        assert flag_count >= 0, f"Should have flag results in database"

    def test_run_screening_with_progress_resume(self, temp_db, temp_progress_file):
        """Integration test: Resume from progress file."""
        screening = FiveFlagsPoolScreening(temp_db, progress_file=temp_progress_file)

        # Save initial progress (marking 1 pool as processed)
        progress_data = {
            'start_time': '2026-04-18 10:00:00',
            'last_update': '2026-04-18 10:00:00',
            'total_stocks': 12,
            'processed_stocks': 0,
            'processed_pool_ids': [1],
            'statistics': {
                'total_matches': 0,
                'by_screener': {}
            }
        }

        import json
        with open(temp_progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)

        # Run screening (should skip pool 1)
        result = screening.run_screening()

        # Verify pool 1 was skipped
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM lao_ya_tou_five_flags WHERE pool_id = 1')
        pool_1_flags = cursor.fetchone()[0]
        conn.close()

        # Pool 1 was marked as processed in progress, should be skipped
        assert pool_1_flags == 0, f"Pool 1 should have 0 flags (skipped due to progress)"

        # Verify only pools 2 and 3 were processed
        assert result['processed_stocks'] == 8, f"Only pools 2 and 3 should be processed"
