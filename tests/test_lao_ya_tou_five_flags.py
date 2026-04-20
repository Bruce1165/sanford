# Import test fixtures
import pytest

# Add scripts directory to path
# scripts directory is in parent directory, so just add database
sys.path.insert(0, 'scripts/database')

from database.lao_ya_tou_pool import LaoYaTouPoolRepository
from database.lao_ya_tou_five_flags import (
    LaoYaTouFiveFlagsRepository,
    DatabaseError,
    ValidationError
)


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Get script directory from test file location
    test_dir = os.path.dirname(__file__)
    migrations_dir = os.path.join(test_dir, '..', 'scripts', 'database', 'migrations')

    # Execute lao_ya_tou_pool migration
    conn = sqlite3.connect(path)
    lao_ya_tou_pool_script = os.path.join(migrations_dir, 'create_lao_ya_tou_pool_table.sql')
    with open(lao_ya_tou_pool_script, 'r') as f:
        conn.executescript(f.read())
    conn.close()

    # Execute lao_ya_tou_five_flags migration
    conn = sqlite3.connect(path)
    lao_ya_tou_five_flags_script = os.path.join(migrations_dir, 'create_lao_ya_tou_five_flags.sql')
    with open(lao_ya_tou_five_flags_script, 'r') as f:
        conn.executescript(f.read())
    conn.close()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def pool_repo(temp_db):
    repository = LaoYaTouPoolRepository(temp_db)
    yield repository
    repository.close()


@pytest.fixture
def flags_repo(temp_db):
    repository = LaoYaTouFiveFlagsRepository(temp_db)
    yield repository
    repository.close()


class TestLaoYaTouFiveFlagsRepository:
    """Test suite for LaoYaTouFiveFlagsRepository"""

    def test_insert_flag_result(self, pool_repo, flags_repo):
        """Test target: Verify single flag result insertion functionality"""
        # Create a pool record first
        pool_id = pool_repo.insert_pool_record(
            stock_code='000001',
            stock_name='平安银行',
            start_date='2026-04-01',
            end_date='2026-04-10',
            file_name='test_pool.xlsx'
        )

        # Insert flag result
        flag_id = flags_repo.insert_flag_result(
            pool_id=pool_id,
            screener_id='screener_001',
            stock_code='000001',
            stock_name='平安银行',
            screen_date='2026-04-01',
            close_price=10.50,
            match_reason='符合老鸭头形态'
        )

        assert flag_id > 0
        # Verify record exists
        flags = flags_repo.get_results_by_pool_id(pool_id)
        assert len(flags) == 1

        # Verify field values
        record = flags[0]
        assert record['pool_id'] == pool_id
        assert record['screener_id'] == 'screener_001'
        assert '平安银行' in record['stock_name']
        assert record['screen_date'] == '2026-04-01'
        assert record['close_price'] == 10.50
        assert record['match_reason'] == '符合老鸭头形态'
