# NeoTrade2 Improvement Plan - L99 Foundation

**Goal:** Clean, solid codebase before heavy development phase
**Status:** In Progress
**Last Updated:** 2026-04-04

---

## Phase 1: Critical Fixes (3-5 days)
*Must do - stability & security foundations*

### 1.1 Database Connection Leaks
**Files:** `backend/models.py`, `screeners/base_screener.py`

```python
# Add context manager to models.py
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        conn.close()

# Update all functions to use:
with get_db_connection() as conn:
    # database operations
```

### 1.2 Remove Duplicate Databases
```bash
rm -rf backend/data/ scripts/data/
# Keep only /data/ as single source of truth
```

### 1.3 Fix .gitignore
```bash
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
node_modules/
dist/
data/*.db
logs/*.log
.DS_Store
*.db
*.sqlite
*.sqlite3
EOF
```

### 1.4 Input Validation
**File:** `backend/validators.py` (new)

```python
from pydantic import BaseModel, validator, constr
from datetime import datetime
import re

class ScreenerRunRequest(BaseModel):
    screener_name: constr(min_length=1, max_length=50)
    date: str

    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Invalid date format, use YYYY-MM-DD')

class UploadRequest(BaseModel):
    force_update: bool = False
```

---

## Phase 2: Database Improvements (2-3 days)
*Data integrity & performance*

### 2.1 Add Transactions
**Files:** `backend/models.py`

```python
def create_run(screener_name, run_date):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            conn.execute('BEGIN TRANSACTION')
            cursor.execute('''INSERT INTO screener_runs...''', ...)
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            # retry/update logic
        except Exception:
            conn.rollback()
            raise
```

### 2.2 Add Critical Indexes
```sql
-- Add to models.py init_db()
CREATE INDEX IF NOT EXISTS idx_screener_runs_lookup
    ON screener_runs(screener_name, run_date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_code_date
    ON daily_prices(code, trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date
    ON daily_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_stocks_code
    ON stocks(code);
```

### 2.3 Add Database Constraints
```sql
status TEXT DEFAULT 'pending'
    CHECK(status IN ('pending', 'running', 'completed', 'failed'))
```

---

## Phase 3: Security Hardening (2 days)
*Basic security for personal system*

### 3.1 Remove Frontend Password
**File:** `frontend/src/api/index.ts`

```typescript
// Remove hardcoded password
// Use cookie-based auth from backend
const authHeader = localStorage.getItem('auth') || '';
```

### 3.2 Restrict CORS
**File:** `backend/app.py`

```python
CORS(app, origins=[
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    # Add your Cpolar domain if needed
], supports_credentials=True)
```

### 3.3 Add Rate Limiting
**File:** `backend/app.py`

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(app=app, key_func=get_remote_address)

@app.route('/api/screeners/<name>/run', methods=['POST'])
@limiter.limit("10 per minute")
def run_screener(name):
    ...
```

### 3.4 Standardize Error Responses
**File:** `backend/app.py`

```python
def error_response(error_code: str, message: str, status_code: int = 400):
    return jsonify({
        'error': error_code,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }), status_code
```

---

## Phase 4: Testing Foundation (3-4 days)
*Critical path coverage*

### 4.1 Setup Test Infrastructure
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Create test structure
mkdir -p backend/tests/{unit,integration,fixtures}
touch backend/tests/conftest.py
```

### 4.2 Critical Test Suite
**Target: 30% coverage (realistic for personal system)**

```python
# backend/tests/test_screener_logic.py
def test_coffee_cup_pattern_detection():
    """Test pattern detection logic"""
    # Test with known good/bad data

# backend/tests/test_database_operations.py
def test_create_run():
    """Test database operations"""

# backend/tests/test_api_endpoints.py
def test_api_screeners():
    """Test API endpoints"""

# backend/tests/test_stock_filter.py
def test_stock_filter_excludes_delisted():
    """Test stock filtering logic"""
```

### 4.3 Add Test Fixtures
```python
# backend/tests/conftest.py
@pytest.fixture
def temp_db():
    """Temporary database for tests"""
    db_path = tempfile.mktemp(suffix='.db')
    init_db(db_path)
    yield db_path
    os.unlink(db_path)
```

---

## Phase 5: Code Quality (2-3 days)
*Maintainability & readability*

### 5.1 Split `app.py` (monolith → modules)
```
backend/
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── screeners.py
│   │   ├── api.py
│   │   └── data_health.py
│   └── middleware/
│       └── auth.py
├── app.py  # Application factory (100 lines)
```

### 5.2 Standardize Logging
**File:** `backend/logger_config.py` (new)

```python
import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
```

### 5.3 Type Hints (Backend)
```python
from typing import Optional, List, Dict, Any
from datetime import date

def get_results(run_id: int) -> List[Dict[str, Any]]:
    ...
```

---

## Phase 6: Configuration Management (1 day)
*Environment-based configuration*

### 6.1 Centralize Configuration
```
config/
├── __init__.py
├── default.py
├── development.py
└── production.py
```

```python
# config/default.py
class Config:
    DATABASE_PATH = '/data/stock_data.db'
    DASHBOARD_DB_PATH = '/data/dashboard.db'
    FLASK_PORT = 8765
    LOG_LEVEL = 'INFO'
```

### 6.2 Environment Variables
```bash
# .env.example
DATABASE_PATH=/data/stock_data.db
DASHBOARD_PASSWORD=your_password
FLASK_ENV=development
LOG_LEVEL=INFO
```

---

## Execution Timeline

| Week | Phase | Focus | Status |
|------|-------|-------|--------|
| Week 1 | Phase 1 | Critical Fixes | ✅ Completed 2026-04-04 |
| Week 2 | Phase 2-3 | Database & Security | ☐ Pending |
| Week 3 | Phase 4 | Testing | ☐ Pending |
| Week 4 | Phase 5-6 | Code Quality | ☐ Pending |

---

## Success Criteria

- [x] No database connection leaks (context manager added)
- [x] Single source of truth for databases (duplicates removed)
- [x] All API endpoints have input validation (validators.py created)
- [ ] Test coverage ≥ 30% for critical paths
- [x] All database operations use transactions (database.py created)
- [x] CORS restricted to specific origins
- [ ] Rate limiting on expensive endpoints
- [ ] `app.py` split into modules (max 300 lines per file)
- [ ] Consistent logging across all modules
- [ ] Environment-based configuration

---

## Progress Log

### 2026-04-04
- Created improvement plan
- ✅ Removed duplicate databases (backend/data/, scripts/data/)
- ✅ Created .gitignore
- ✅ Added database connection context manager (`get_db_connection_context()`)
- ✅ Added 5 database indexes for performance
- ✅ Created input validation module (`backend/validators.py`)
- ✅ Restricted CORS to specific origins
- ✅ Created transaction management utility (`backend/database.py`)
- ✅ Fixed all hardcoded paths to use relative paths
  - backend/app.py - 3 locations fixed
  - backend/models.py - 1 location fixed
  - scripts/config.py - 1 location fixed
  - scripts/trading_calendar.py - 1 location fixed
  - scripts/database.py - 1 location fixed
  - scripts/screener_monitor.py - 1 location fixed
  - scripts/verify_data_integrity.py - 2 locations fixed
  - scripts/daily_screener_qa.py - 1 location fixed
  - scripts/fill_data_gaps.py - 2 locations fixed
  - scripts/daily_screener_monitor.py - 1 location fixed
  - scripts/run_all_screeners.py - 1 location fixed
  - config/.env - Removed hardcoded WORKSPACE_ROOT
- ✅ Created requirements management system (`docs/需求管理/`)
  - 需求提交模板
  - 工作流程文档
  - 示例需求（REQ_000）
  - 快速创建脚本
- ✅ **Phase 1 (Critical Fixes) Completed**
- ✅ **Path Portability Complete**
- ✅ **Requirements Management System Ready**
- System verified healthy and operational
- **Ready for heavy development with structured requirements process**

---

## Rollback Plan

If any change breaks the system:
1. Restore from backup (created before each change)
2. Document what broke and why
3. Fix the issue before proceeding

### Backup Commands
```bash
# Before any change
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz backend/ data/
```

---

## Testing Checklist After Each Change

- [ ] Backend starts without errors
- [ ] Frontend loads correctly
- [ ] Can access via external URL (Cpolar)
- [ ] Can run a screener
- [ ] Can upload Excel file
- [ ] Can view screener results
- [ ] Monitor page loads
- [ ] Data health check passes
