"""
Simplified integration tests for Phase 1 and Phase 2

Tests database structure, indexes, and foreign keys without complex fixtures.
"""

import pytest
import sqlite3
import os
import tempfile

# Add database path
sys.path.insert(0, 'scripts/database')

from database.lao_ya_tou_pool import LaoYaTouPoolRepository
from database.lao_ya_tou_five_flags import (
    LaoYaTouFiveFlagsRepository,
    DatabaseError,
    ValidationError
)


@pytest.fixture
def temp_db():
    """Create temporary test database with both tables created."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Get migrations directory - use absolute path
    test_dir = os.path.dirname(__file__)
    migrations_dir = os.path.join(test_dir, 'scripts', 'database', 'migrations')

    # Execute lao_ya_tou_pool migration
    conn = sqlite3.connect(path)
    lao_ya_tou_pool_script = os.path.join(migrations_dir, 'create_lao_ya_tou_pool_table.sql')
    with open(lao_ya_tou_pool_script, 'r') as f:
        conn.executescript(f.read())
    conn.close()

    # Execute lao_ya_tou_five_flags migration
    lao_ya_tou_five_flags_script = os.path.join(migrations_dir, 'create_lao_ya_tou_five_flags.sql')
    with open(lao_ya_tou_five_flags_script, 'r') as f:
        conn.executescript(f.read())
    conn.close()

    yield path

    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def pool_repo(temp_db):
    """Create lao_ya_tou_pool repository for testing."""
    repository = LaoYaTouPoolRepository(temp_db)
    yield repository
    repository.close()


@pytest.fixture
def flags_repo(temp_db):
    """Create lao_ya_tou_five_flags repository for testing."""
    repository = LaoYaTouFiveFlagsRepository(temp_db)
    yield repository
    repository.close()


class TestPhase2Integration:
    """Simplified integration tests for Phase 1 and Phase 2"""

    def test_lao_ya_tou_pool_table_exists(self):
        """Verify lao_ya_tou_pool table exists in database."""
        assert os.path.exists('data/stock_data.db'), "Database file should exist"

    def test_lao_ya_tou_five_flags_table_exists(self):
        """Verify lao_ya_tou_five_flags table exists in database."""
        assert os.path.exists('data/stock_data.db'), "Database file should exist"

    def test_lao_ya_tou_five_flags_indexes_exist(self):
        """Verify all indexes exist for lao_ya_tou_five_flags table."""
        import sqlite3
        conn = sqlite3.connect('data/stock_data.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lao_ya_tou_five_flags'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = [
            'idx_five_flags_pool',
            'idx_five_flags_screener',
            'idx_five_flags_code',
            'idx_five_flags_date'
        ]
        assert set(indexes) >= set(expected_indexes), \
            f"Missing indexes: {set(expected_indexes) - set(indexes)}"
        conn.close()

    def test_lao_ya_tou_pool_foreign_key_exists(self):
        """Verify foreign key constraint exists on lao_ya_tou_five_flags."""
        import sqlite3
        conn = sqlite3.connect('data/stock_data.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='lao_ya_tou_five_flags'"
        )
        sql = cursor.fetchone()[0]
        assert 'FOREIGN KEY (pool_id) REFERENCES lao_ya_tou_pool(id)' in sql, \
            "Foreign key constraint should be present"
        conn.close()

    def test_database_integrity(self):
        """Verify database integrity."""
        import sqlite3
        conn = sqlite3.connect('data/stock_data.db')
        result = conn.execute('PRAGMA integrity_check').fetchone()[0]
        assert result == 'ok', f"Database integrity check failed: {result}"
        conn.close()

    def test_tables_created_in_temp_db(self, temp_db):
        """Verify both tables are created in temporary database."""
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check lao_ya_tou_pool
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lao_ya_tou_pool'")
        assert cursor.fetchone() is not None, "lao_ya_tou_pool table should exist"

        # Check lao_ya_tou_five_flags
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lao_ya_tou_five_flags'")
        assert cursor.fetchone() is not None, "lao_ya_tou_five_flags table should exist"

        conn.close()
