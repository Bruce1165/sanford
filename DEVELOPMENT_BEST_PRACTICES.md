# Development Best Practices (CRITICAL)

**Purpose**: Comprehensive software engineering guidelines for NeoTrade2 development  
**Created**: 2026-04-16  
**Status**: Active - Must follow these rules for ALL development work

---

## 🚀 Core Development Principles

### 1. Planning First, Always
**NEVER start coding without a plan**

- **✅ Make development plan before coding**
- **✅ Design data structures and algorithms first**
- **✅ Plan testing approach and validation criteria**
- **✅ Consider edge cases and error handling**
- **✅ Review existing similar code for patterns**

**Risks of skipping planning**:
- ❌ Incomplete implementations
- ❌ Wrong data structures
- ❌ Missing error handling
- ❌ Inconsistent code style

### 2. Pseudocode Before Real Code
**ALWAYS write pseudocode before implementation**

- **✅ Write pseudocode file before implementation**
- **✅ Document algorithm logic and data flow**
- **✅ Define input/output specifications**
- **✅ Plan error handling and edge cases**
- **✅ Keep pseudocode as living documentation**

**Benefits of pseudocode**:
- ✅ Clear algorithm design before implementation
- ✅ Easier to spot logic errors
- ✅ Reference for future maintenance
- ✅ Communication tool for code reviews

### 3. File Corruption Prevention (CRITICAL)
**PREVENT file corruption through systematic measures**

#### Prevention Strategies

**1. Write Operations Safety**
- **✅ Use atomic writes when possible**
- **✅ Write to temporary file first, then rename**
- **✅ Use database transactions for multi-step operations**
- **✅ Validate data before writing**
- **✅ Use file locking when concurrent access is possible**

**Safe write pattern:**
```bash
# WRONG: Direct overwrite (corruption risk if write fails)
echo "new content" > important_file.py

# CORRECT: Write to temp, then atomic rename
echo "new content" > important_file.py.tmp
mv important_file.py.tmp important_file.py
```

**2. Database Operations Safety**
- **✅ Always use WAL mode for SQLite**
- **✅ Use transactions for all multi-step operations**
- **✅ Validate schema before modifications**
- **✅ Use parameterized queries**
- **✅ Enable foreign key constraints**

**Safe database pattern:**
```python
# WRONG: Multiple statements without transaction
cursor.execute("UPDATE table1 SET x=1 WHERE id=1")
cursor.execute("UPDATE table2 SET y=2 WHERE id=1")  # If this fails, table1 is corrupted

# CORRECT: Use transaction
try:
    cursor.execute("BEGIN TRANSACTION")
    cursor.execute("UPDATE table1 SET x=1 WHERE id=1")
    cursor.execute("UPDATE table2 SET y=2 WHERE id=1")
    cursor.execute("COMMIT")
except Exception as e:
    cursor.execute("ROLLBACK")
    raise e
```

**3. Configuration File Safety**
- **✅ Validate JSON/YAML before writing**
- **✅ Preserve comments and formatting**
- **✅ Use configuration management libraries**
- **✅ Test parsing after write**

**Safe config pattern:**
```python
import json

# Read existing config
with open('config.json', 'r') as f:
    config = json.load(f)

# Modify config
config['new_key'] = 'new_value'

# Write with validation
try:
    # Write to temp file first
    with open('config.json.tmp', 'w') as f:
        json.dump(config, f, indent=2)

    # Validate by parsing
    with open('config.json.tmp', 'r') as f:
        json.load(f)  # Will raise exception if invalid

    # Atomic rename
    os.rename('config.json.tmp', 'config.json')

except (json.JSONDecodeError, Exception) as e:
    print(f"Config validation failed: {e}")
    if os.path.exists('config.json.tmp'):
        os.remove('config.json.tmp')
```

**4. File System Safety**
- **✅ Check disk space before large writes**
- **✅ Use proper file permissions**
- **✅ Avoid concurrent writes to same file**
- **✅ Handle file system errors gracefully**

#### Detection Methods

**1. Integrity Checks**
```python
# SQLite integrity check
import sqlite3
conn = sqlite3.connect('database.db')
result = conn.execute("PRAGMA integrity_check;").fetchall()
if result[0][0] != 'ok':
    print("Database corrupted!")

# File checksum verification
import hashlib
def verify_file_integrity(filepath, expected_checksum):
    with open(filepath, 'rb') as f:
        content = f.read()
    actual_checksum = hashlib.sha256(content).hexdigest()
    return actual_checksum == expected_checksum
```

**2. Runtime Validation**
- **✅ Validate data after read operations**
- **✅ Check for NaN/None values in critical data**
- **✅ Verify array/list bounds before access**
- **✅ Add try-catch around critical operations**

**3. Log Monitoring**
```python
# Monitor for file write errors
import logging

logging.basicConfig(filename='file_operations.log', level=logging.ERROR)

def safe_write(filepath, content):
    try:
        with open(filepath, 'w') as f:
            f.write(content)
    except IOError as e:
        logging.error(f"Failed to write {filepath}: {e}")
        raise  # Re-raise to handle at higher level
```

#### Common Corruption Scenarios and Prevention

| Scenario | Prevention | Detection |
|-----------|-------------|------------|
| **Mid-write power failure** | Atomic write pattern | Checksum verification |
| **Disk full** | Check space before write | IOError on write |
| **Concurrent access** | File locking | Write error/locked file |
| **Invalid JSON/YAML** | Validate before write | Parse error on read |
| **Database schema mismatch** | Migration scripts | Integrity check fail |
| **Partial file transfer** | Verify file size/hash | Read error/corruption |

### 4. Backup Before Modifications (CRITICAL)
**NEVER modify files without backup**

#### Backup Principles
- **✅ Backup before EVERY modification**
- **✅ Verify backup integrity before proceeding**
- **✅ Keep backup until all modifications verified**
- **✅ Retain recent 3 backups**
- **✅ Store backups in independent location (not project directory)**

#### Backup Naming Format
Use timestamped format: `filename.backup.YYYYMMDD_HHMMSS.ext`

```bash
# Example: app.py.backup.20260419142030.py
cp path/to/app.py path/to/app.py.backup.20260419142030.py
```

#### Backup Content
Backups must include:
- Complete file content copy
- All database schema modifications
- Index creation/deletion statements
- Key business logic changes

#### Backup Verification
After creating backup, verify:
1. **File integrity check** (sqlite3 integrity for databases)
2. **Syntax validation** (import test for Python)
3. **Functional testing** (run related functionality)

#### Recovery Flow
If corruption detected:
1. Identify corrupted backup (syntax errors, functional issues)
2. Restore from most recent valid backup
3. Verify restored functionality
4. If all backups fail, try earlier backup

#### Automation Recommendations
```bash
# Pre-commit hook for automatic backup
# Consider adding to Git workflow
# Script: backup_and_validate.sh
```

**Complete backup process**:
```bash
# 1. Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/path/to/backups"
cp path/to/file.py $BACKUP_DIR/file.py.backup.$TIMESTAMP.py

# 2. Verify backup
python3 -m py_compile $BACKUP_DIR/file.py.backup.$TIMESTAMP.py || exit 1

# 3. Make modifications
# ... edit file.py ...

# 4. Test modifications
python3 test_file.py || {
    echo "Tests failed, restoring backup"
    cp $BACKUP_DIR/file.py.backup.$TIMESTAMP.py path/to/file.py
    exit 1
}

# 5. After verification, keep backup
# Keep until next successful version verified
```

### 4. English-Only Code
**NO Chinese characters in real code files**

- **✅ English variable names and comments only**
- **✅ Follow existing code style and patterns**
- **✅ Use descriptive variable and function names**
- **✅ Add docstrings to new functions and classes**

**Examples**:
```python
# ✅ CORRECT
def calculate_moving_average(prices, window):
    """Calculate moving average for given price window."""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window

# ❌ WRONG
def 计算移动平均(prices, window):
    """计算给定价格窗口的移动平均。"""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window
```

### 5. Debugging and Problem Solving
**Use debugging messages and tracing**

- **✅ Use debugging messages for tracing execution**
- **✅ Add debug logging for cache/version issues**
- **✅ Document critical points and decision logic**
- **✅ Use print statements for key algorithm steps**
- **✅ STOP if stuck in circular problem solving - ask for help**

**Debugging best practices**:
- Add `print(f"[DEBUG] Current value: {value}")` at key points
- Use `print(f"[DEBUG] Step {step}: {description}")` for algorithm flow
- Document error conditions and recovery strategies
- Log database queries and their results
- Trace external API calls and responses

**When stuck**:
1. **STOP coding** after 15 minutes of no progress
2. **Document current state and problem**
3. **Ask for help** with specific question
4. **Don't keep trying random solutions**

### 6. Log File Management
**Clean up logs after work completion**

- **✅ Clean up log files after each work chunk**
- **✅ Remove temporary/debug logs after verification**
- **✅ Archive old log files periodically**
- **✅ Keep logs structured and searchable**

**Log cleanup process**:
```bash
# Remove temporary debug logs after testing
rm logs/*_debug.log
rm logs/*_temp.log

# Archive old logs quarterly
mv logs/*.log.2026-Q1 logs/archive/2026-Q1/
```

### 7. Real and Professional Approach
**Keep it real and practical**

- **✅ Keep it real - no fictional examples or placeholders**
- **✅ Use actual data and realistic scenarios**
- **✅ Base decisions on facts and requirements**
- **✅ Document assumptions and constraints clearly**
- **✅ Use real market data for testing**

**Anti-patterns to avoid**:
- ❌ Fictional company names or stock codes
- ❌ Placeholder data like "EXAMPLE_STOCK_123"
- ❌ Mocked market scenarios that don't exist
- ❌ Simplified examples that miss real complexity

---

## 📋 Pre-Work Checklist

### Before Starting ANY Development Work

**Claude Code MUST:**

1. **[ ]** Read development best practices (this file)
2. **[ ]** Review project status (`PROJECT_STATUS.md`)
3. **[ ]** Check screener development guide (`scripts/SCREENERS_README.md`)
4. **[ ]** Check regression checklist (`backend/regression_checklist.md`)
5. **[ ]** Understand current configuration (`PROJECT_CONFIG.md`)

### For Screener Development

1. **[ ]** Study existing similar screeners for patterns
2. **[ ]** Review SCREENERS_README.md for screener requirements
3. **[ ]** Design screener algorithm and data flow
4. **[ ]** Plan output format and field requirements
5. **[ ]** Create pseudocode before implementation
6. **[ ]** Plan testing approach (edge cases, error handling)
7. **[ ]** Consider performance implications

### For Bug Fixes or Modifications

1. **[ ]** Read regression checklist for affected areas
2. **[ ]** Backup files before modification
3. **[ ]** Plan fix approach and test strategy
4. **[ ]** Add debug logging if needed
5. **[ ]** Update PROJECT_STATUS.md with changes
6. **[ ]** Run relevant regression checks after fix

### After Completing Development Work

1. **[ ]** Update PROJECT_STATUS.md with completion status
2. **[ ]** Update relevant documentation files
3. **[ ]** Clean up temporary debug logs
4. **[ ]** Delete backup files after verification
5. **[ ]** Run regression checklist for affected areas
6. **[ ]** Document any new patterns discovered

---

## 🎯 Quality Standards

### Code Readability
- **[ ]** Descriptive variable and function names
- **[ ]** Clear docstrings for all functions and classes
- **[ ]** Comments for complex logic only
- **[ ]** Reasonable function length (< 50 lines preferred)
- **[ ] ** Proper error handling with specific error messages

### Data Integrity
- **[ ]** Use `INSERT OR REPLACE` for idempotent database operations
- **[ ]** Validate data before processing
- **[ ]** Handle missing or corrupted data gracefully
- **[ ]** Use transactions for multi-step database operations

### Performance
- **[ ]** Consider database query optimization
- **[ ] ** Avoid N+1 queries where possible
- **[ ] ** Use efficient data structures and algorithms
- **[ ] ** Add pagination for large result sets

### Security
- **[ ]** No hardcoded secrets or credentials
- **[ ]** Validate user inputs at API boundaries
- **[ ] ** Use parameterized queries to prevent SQL injection
- **[ ] ** Proper error handling that doesn't leak information

---

## 🚨 Red Flags - Stop and Ask for Help

**Stop immediately and ask for help if:**

- **Stuck for 15+ minutes** on a problem with no progress
- **Found in circular logic** trying same solutions repeatedly
- **Unable to resolve** after 3+ different approaches
- **Missing critical information** needed to proceed
- **Conflicting requirements** that can't be resolved

**What to provide when asking for help:**
1. Current problem description with steps already tried
2. Relevant code snippets and error messages
3. Expected vs actual behavior
4. Specific question or decision point needed

---

## 📊 Success Criteria

**Development work is complete when:**

1. **[ ]** Code follows development best practices
2. **[ ]** Pseudocode created and followed
3. **[ ]** Backup/restore process followed
4. **[ ]** Debug logging added at critical points
5. **[ ]** English-only code maintained
6. **[ ]** Logs cleaned up after completion
7. **[ ]** Regression checks pass for affected areas
8. **[ ]** Documentation updated (PROJECT_STATUS.md)
9. **[ ] ** Real data used for testing (no placeholders)

---

**Last Updated**: 2026-04-16  
**Version**: 1.0  
**Status**: Active - Must follow these guidelines for ALL development work
