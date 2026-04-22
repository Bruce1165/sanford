# Safety Constraints - Non-Negotiable Rules

## ⚠️ CRITICAL: READ BEFORE ANY WORK

These safety constraints are **non-negotiable**. Violating them will result in immediate project termination.

---

## 🚫 What You CANNOT Do (Strictly Forbidden)

### 1. Dashboard Protection

#### Absolutely Forbidden
- ❌ **NEVER** modify `backend/app.py` (any line, any change)
- ❌ **NEVER** restart the Flask process
- ❌ **NEVER** write to `data/dashboard.db`
- ❌ **NEVER** modify production database schema
- ❌ **NEVER** change Flask routes or endpoints
- ❌ **NEVER** alter authentication logic
- ❌ **NEVER** modify frontend code that affects dashboard

#### Why?
The dashboard is a **production system** serving live trading decisions. Any modification could:
- Break the dashboard for Bruce (user)
- Corrupt trading data
- Cause financial loss
- Require emergency recovery

### 2. Production Data Protection

#### Absolutely Forbidden
- ❌ **NEVER** write to `data/stock_data.db`
- ❌ **NEVER** delete or modify Excel files in `data/screeners/`
- ❌ **NEVER** alter stock price data
- ❌ **NEVER** modify screener result files
- ❌ **NEVER** delete historical data
- ❌ **NEVER** create new files in `data/` (except `research/` subdirectory)

#### Why?
Production data is the **single source of truth** for:
- Historical stock prices (6+ months)
- Screener results (all historical runs)
- Trading decisions
- Performance tracking

Modifying it compromises data integrity.

### 3. Production Screener Protection

#### Absolutely Forbidden
- ❌ **NEVER** modify screener Python files in `screeners/` directory
- ❌ **NEVER** change screener logic or parameters
- ❌ **NEVER** alter `screeners/base_screener.py`
- ❌ **NEVER** modify screener configuration in `config/screeners/`
- ❌ **NEVER** interfere with daily screener runs

#### Why?
Screeners are **production code** that:
- Run automatically every trading day
- Generate signals for trading decisions
- Must be reliable and consistent
- Bruce relies on for daily operations

### 4. System Stability

#### Absolutely Forbidden
- ❌ **NEVER** run resource-intensive operations during market hours
- ❌ **NEVER** cause system-wide slowdowns
- ❌ **NEVER** consume excessive CPU/RAM
- ❌ **NEVER** block Flask requests
- ❌ **NEVER** interfere with cron jobs

#### Why?
The system must remain **responsive** for:
- Dashboard access
- Daily data downloads
- Screener executions
- Real-time monitoring

---

## ✅ What You CAN Do (Allowed Activities)

### 1. Research Workspace (Fully Writable)

#### Allowed
- ✅ Write to `research/data/research.db` (isolated research database)
- ✅ Create files in `research/output/` (analysis, models, reports)
- ✅ Modify scripts in `research/scripts/` (research code only)
- ✅ Update documentation in `research/TECHNICAL_DOCS/`
- ✅ Create new research tools and utilities

#### Why?
This is an **isolated workspace** designed for:
- Experimentation
- Model development
- Analysis
- Documentation

### 2. Production Data (Read-Only Access)

#### Allowed
- ✅ Read `data/stock_data.db` (stock prices)
- ✅ Read Excel files in `data/screeners/` (historical screener results)
- ✅ Query production databases (SELECT only)
- ✅ Analyze data in memory
- ✅ Save analysis results to `research/`

#### Why?
Read access provides the **data needed** for:
- Historical analysis
- Pattern recognition
- Model training
- Backtesting

Without compromising data integrity.

### 3. Code Quality

#### Allowed
- ✅ Write tests for research code
- ✅ Perform code reviews
- ✅ Follow best practices (80% coverage, security)
- ✅ Document all changes
- ✅ Use version control (research worktree)

#### Why?
Ensures **code quality** and **reproducibility**.

---

## 🔒 Access Control Summary

### Production System (Read-Only)

| Component | Access | Reason |
|-----------|--------|--------|
| `backend/app.py` | ❌ Read-Only | Production dashboard |
| `data/dashboard.db` | ❌ Read-Only | Production data |
| `data/stock_data.db` | ❌ Read-Only | Historical prices |
| `data/screeners/` | ❌ Read-Only | Screener results |
| `screeners/*.py` | ❌ Read-Only | Production code |
| `config/screeners/` | ❌ Read-Only | Production config |

### Research Workspace (Read-Write)

| Component | Access | Reason |
|-----------|--------|--------|
| `research/data/research.db` | ✅ Read-Write | Isolated research DB |
| `research/output/` | ✅ Read-Write | Analysis results |
| `research/scripts/` | ✅ Read-Write | Research code |
| `research/TECHNICAL_DOCS/` | ✅ Read-Write | Documentation |

---

## 🛡️ Enforcement Mechanisms

### 1. Code Review Gate
- All code changes must pass security review
- `ecc:security-reviewer` agent checks for violations
- Reviewer verifies no production code modifications

### 2. Automated Checks
```python
# Example: Pre-commit hook to check for forbidden paths
FORBIDDEN_PATHS = [
    'backend/app.py',
    'data/dashboard.db',
    'data/stock_data.db',
    'data/screeners/',
    'screeners/'
]

def check_file_access(file_path):
    """Raise error if trying to access forbidden path"""
    for forbidden in FORBIDDEN_PATHS:
        if file_path.startswith(forbidden):
            raise PermissionError(f"Access forbidden: {file_path}")
```

### 3. Git Worktree Isolation
- Research work in separate git worktree: `research-predictive-cup`
- Prevents accidental commits to main branch
- Isolates research code from production

### 4. Daily Status Checks
- Verify dashboard is running
- Check production database integrity
- Confirm no unauthorized modifications

---

## 🚨 What to Do If You Accidentally Violate a Constraint

### Immediate Actions
1. **STOP** whatever you're doing immediately
2. **ASSESS** the impact (what did you modify?)
3. **RESTORE** from backup if possible
4. **REPORT** to Research Lead and Bruce immediately
5. **DOCUMENT** what happened and why

### Recovery Procedures

#### If you modified `backend/app.py`
```bash
# Restore from version control
cd /Users/mac/NeoTrade2
git checkout backend/app.py

# Restart Flask if needed
pkill -f "python.*app.py"
cd backend
python3 app.py --port 8765
```

#### If you wrote to `data/stock_data.db`
```bash
# Restore from backup (if available)
cp data/stock_data.db.bak.$(date +%Y%m%d) data/stock_data.db

# Or restore from git (if committed)
git checkout data/stock_data.db
```

#### If you modified screener files
```bash
# Restore from version control
git checkout screeners/

# Restart any affected services
pkill -f "screener"
```

---

## 📋 Safety Checklist

### Before Any Code Execution
- [ ] I am NOT modifying `backend/app.py`
- [ ] I am NOT writing to `data/dashboard.db`
- [ ] I am NOT writing to `data/stock_data.db`
- [ ] I am NOT modifying files in `data/screeners/`
- [ ] I am NOT modifying screener Python files
- [ ] I am writing to `research/` directory only
- [ ] I have read-only access to production data
- [ ] I am not interfering with dashboard
- [ ] I am not consuming excessive resources

### Before Any Git Commit
- [ ] Review all changed files
- [ ] Confirm no production code modified
- [ ] Confirm no production data modified
- [ ] Commit message is clear
- [ ] Code has been reviewed

---

## 🔍 Monitoring

### Daily Checks
1. Dashboard is accessible at `http://localhost:8765/`
2. Flask process is running (`ps aux | grep app.py`)
3. Production databases are intact (`sqlite3 data/dashboard.db "PRAGMA integrity_check;"`)
4. No unauthorized modifications (`git status`)

### Weekly Checks
1. Review all git commits for the week
2. Verify research code quality (coverage, security)
3. Check database sizes and growth
4. Review risk register

---

## 📚 Related Documents

- [Data Access](03_DATA_ACCESS.md) - How to safely access data
- [Risk Register](08_RISK_REGISTER.md) - Risks related to safety violations
- [Agent Roles](07_AGENT_ROLES.md) - Who is responsible for what

---

## 📞 Emergency Contacts

### If You Accidentally Violate a Constraint
1. **Research Lead**: Immediate notification
2. **Bruce**: Notification if dashboard is affected
3. **System Recovery**: Restore from backup

---

**Remember**: These constraints exist to protect production systems and data. Violating them compromises the entire NeoTrade2 system. Always think twice before modifying anything outside the `research/` directory.

---

**Last Updated**: 2026-04-09
**Status**: ACTIVE - Enforce Strictly
