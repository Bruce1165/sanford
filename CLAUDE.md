# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🚨 LIGHTWEIGHT SESSION START VERIFICATION

**⚠️ CRITICAL: Before ANY work, Claude Code MUST complete session start verification!**

**Required Steps:**
1. **[ ]** Complete `/TECHNICAL_DOCS/SESSION_START_VERIFICATION.md` checklist (2 min)
2. **[ ]** Confirm I know WHERE to find each type of guideline
3. **[ ]** Confirm just-in-time reading approach (not all at once)

**📍 Verification File**: `/Users/mac/NeoTrade2/TECHNICAL_DOCS/SESSION_START_VERIFICATION.md`
- **Purpose**: Lightweight check that agent knows WHERE to find guidelines (just-in-time reading)
- **Required**: MUST BE COMPLETED before any development work
- **Key**: Read ONLY relevant guidelines BEFORE starting each task type

**✅ Ready to Work**: After lightweight verification, task-specific guidelines will be read as needed

**Examples of Required Confirmations:**
- ❌ "I have read all documentation" → ✅ "I know documentation structure is in `TECHNICAL_DOCS/` with 4-level semantic hierarchy"
- ❌ "I've reviewed development guidelines" → ✅ "I know development guidelines are in `DEVELOPMENT_BEST_PRACTICES.md` and will read them when starting development work"
- ❌ "I'll follow all guidelines" → ✅ "I will read the relevant guideline file for each task type before starting work"

**🚫 Non-Compliant Responses**: Any response like "Okay" or "I'll try" will be rejected - must include explicit confirmation of WHERE to find guidelines

---

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NeoTrade2 is a local A-share stock trading analytics system for technical analysis and stock screening. The system automatically downloads market data from Baostock, runs 11 technical analysis screeners (O'Neil patterns, limit-up patterns, etc.), and displays results via a password-protected Flask Dashboard.

**Target User**: Bruce (personal investor)
**Market**: China A-share (4,663 stocks)
**Data Source**: Baostock (historical and daily data)

## 📚 Documentation Guidelines (IMPORTANT)

**BEFORE ANY DOCUMENTATION WORK, Claude Code MUST:**

1. **Read Documentation Structure**: `TECHNICAL_DOCS/00_START_HERE.md`
2. **Follow Semantic Organization**: 
   - System level → `TECHNICAL_DOCS/system/`
   - Component level → `TECHNICAL_DOCS/components/[area]/`
   - Specific level → `TECHNICAL_DOCS/components/[area]/specific/`
   - Reference level → `TECHNICAL_DOCS/reference/`

3. **Core Principles**:
   - ✅ **Organize by meaning** (not convenience) - your coffee cup example!
   - ✅ **No duplicates** - search first, link second
   - ✅ **Clean structure** - keep root `TECHNICAL_DOCS/` clean
   - ✅ **Update navigation** - when adding/modifying docs

4. **Quick Reference**: `TECHNICAL_DOCS/QUICK_REFERENCE.md`
5. **Full Guidelines**: `TECHNICAL_DOCS/DOCUMENTATION_MAINTENANCE_GUIDE.md`

**Key Documentation Files**:
- Entry point: `TECHNICAL_DOCS/00_START_HERE.md`
- Quick reference: `TECHNICAL_DOCS/QUICK_REFERENCE.md`
- Full guidelines: `TECHNICAL_DOCS/DOCUMENTATION_MAINTENANCE_GUIDE.md`

**Apply these rules to ALL documentation work**: reading, creating, or updating project docs.

---

## 🔧 Development Guidelines (CRITICAL)

**BEFORE ANY DEVELOPMENT WORK, Claude Code MUST READ:**

**Comprehensive Development Guide**: `/Users/mac/NeoTrade2/DEVELOPMENT_BEST_PRACTICES.md`
- Complete software engineering best practices for ALL development work
- Development planning and pseudocode requirements
- File backup and safety procedures
- Code quality standards (English-only, descriptive names)
- Debugging and problem-solving approaches
- Log file management and cleanup
- Real and professional approach requirements
- Pre-work checklist for starting any development

**Key Guidelines Summary**:
1. ✅ **Planning first** - Make development plan, write pseudocode
2. ✅ **Backup before modifying** - Keep backup until verified
3. ✅ **Update pseudocode** - Keep pseudocode current with implementation
4. ✅ **English-only code** - No Chinese characters in real files
5. ✅ **Debug with messages** - Use print statements for tracing
6. ✅ **Stop when stuck** - Ask for help after 15 minutes circular
7. ✅ **Real data only** - No placeholders or fictional examples
8. ✅ **Clean logs** - Remove temporary debug logs after verification

## 🔒 Code Modification Discipline (CRITICAL)

**These discipline rules MUST be followed for ALL code modifications:**

1. **Backup Before Modification**
   - ✅ **MUST** create a timestamped backup before modifying critical files
   - Use format: `filename.backup.YYYYMMDD_HHMMSS.ext`
   - Keep backup until changes are verified as working

2. **Database Schema Validation**
   - ✅ **MUST** verify schema before modifying database structure or schema-related code
   - Test schema queries directly against database before implementation
   - Validate that tables, columns, and indexes exist as expected

3. **Reference Documentation**
   - ✅ **MUST** reference technical documentation when fixing methods
   - ✅ **MUST** study other working code patterns before implementing changes
   - ✅ Never make assumptions about how code should work

4. **No Scope Expansion**
   - ✅ **MUST NOT** expand scope during a fix
   - Focus on the specific issue being fixed
   - Do not modify unrelated code "while you're at it"

5. **Problem Attribution**
   - ✅ **MUST** verify that problems are caused by recent changes
   - Never assume pre-existing bugs are new issues
   - Problems must be traceable to specific modifications

6. **Isolation Principle**
   - ✅ **IF** other modules work correctly, the problem(s) MUST be caused by local changes
   - Compare behavior before and after modification
   - Test unaffected modules to confirm they still work

**For detailed guidelines and workflows, see**: `/Users/mac/NeoTrade2/DEVELOPMENT_BEST_PRACTICES.md`

---

## Development Commands

### Backend Development

```bash
# Start Flask Dashboard (requires DASHBOARD_PASSWORD env var)
cd backend
python3 app.py --port 8765
# Runs on port 8765, access via Cpolar tunnel

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### Creating New Screeners

```bash
# Development server
cd frontend
npm run dev

# Production build (includes build timestamp)
npm run build

# Lint code
npm run lint
```

### Data Operations

```bash
# Download daily market data (with loop mode)
python3 scripts/fetcher_baostock.py --loop

# Download historical backfill data
python3 scripts/backfill_baostock.py

# Verify data integrity
python3 scripts/verify_data_integrity.py

# Fill data gaps
python3 scripts/fill_data_gaps.py
```

### Screener Operations

```bash
# Run all screeners for a specific date
python3 scripts/run_all_screeners.py --date 2026-04-02

# Run individual screener
python3 screeners/coffee_cup_screener.py --date 2026-04-02

# Test all screeners
python3 scripts/test_all_screeners.py
```

### System Monitoring

```bash
# Daily QA check
python3 scripts/daily_screener_qa.py

# Screener monitoring
python3 scripts/screener_monitor.py

# Data health check
python3 scripts/data_health_check.py

# Trading calendar check
python3 scripts/trading_calendar.py
```

## Architecture

### Data Pipeline Flow

```
Baostock (API)
    ↓
scripts/fetcher_baostock.py (ETL)
    ↓
SQLite: data/stock_data.db (326MB, 4663 stocks)
    ↓
screeners/*_screener.py (11 technical analysis modules)
    ↓
Results: data/screeners/{screener_name}/{date}.xlsx
    ↓
Flask Dashboard (backend/app.py) → React Frontend
```

### Key Components

**Backend (Flask)**
- `backend/app.py` - Flask API server with Basic Auth
- `backend/models.py` - SQLite ORM models (screeners, runs, results, backtests)
- `backend/screeners.py` - Screener discovery and subprocess execution
- Port: 8765
- Authentication: `DASHBOARD_PASSWORD` environment variable

**Frontend (React + TypeScript)**
- `frontend/src/App.tsx` - Main React application
- `frontend/src/pages/` - Dashboard pages (Monitor, etc.)
- Uses: Ant Design, ECharts, Lightweight Charts, Axios
- Vite build system

**Screeners (11 modules)**
All inherit from `screeners/base_screener.py`:
- `coffee_cup_screener.py` - Coffee cup handle pattern
- `jin_feng_huang_screener.py` - Limit-up golden phoenix
- `yin_feng_huang_screener.py` - Limit-up silver phoenix
- `shi_pan_xian_screener.py` - Limit-up test line
- `er_ban_hui_tiao_screener.py` - Two-board pullback
- `zhang_ting_bei_liang_yin_screener.py` - Limit-up double volume bearish
- `breakout_20day_screener.py` - 20-day breakout
- `breakout_main_screener.py` - Main uptrend breakout
- `daily_hot_cold_screener.py` - Daily hot/cold stocks
- `shuang_shou_ban_screener.py` - Double close limit-up
- `ashare_21_screener.py` - A-share 2.1 comprehensive selection

**Data Scripts**
- `scripts/fetcher_baostock.py` - Daily data download from Baostock
- `scripts/download_orchestrator.py` - Download orchestration
- `scripts/backfill_baostock.py` - Historical data backfill
- `scripts/trading_calendar.py` - Trading calendar utilities
- `scripts/database.py` - Database connection utilities

**Cron Tasks**
- `scripts/cron/postmarket_task.py` - Post-market analysis (15:30)
- `scripts/cron/intraday_task.py` - Intraday monitoring tasks

**Monitoring**
- `scripts/daily_screener_qa.py` - Daily QA validation
- `scripts/screener_monitor.py` - Screener health monitoring

### Database Schema

**stock_data.db** (main data)
- `stocks` - Stock basic info (code, name, industry, market_cap, is_delisted)
- `daily_prices` - Daily OHLCV data (code, trade_date, open, high, low, close, volume, amount, turnover, pct_change)

**dashboard.db** (Dashboard backend)
- `screeners` - Screener definitions and metadata
- `screener_runs` - Screener execution records (status, timing, stock counts)
- `screener_results` - Screening results per run
- `stock_price_cache` - Cached price data for charts
- `strategy_backtest_results` - Backtest performance metrics
- `access_logs` - Dashboard access logging
- `access_stats` - Daily visitor statistics

### Configuration

All centralized configuration in `scripts/config.py`:
- Database paths
- Market cap filters (30亿 - 1500亿 circulating cap)
- Stock exclusion rules (ST, delisted, BSE, ETFs)
- Trading calendar settings
- Baostock/AKShare API parameters

**Market Cap Filter**: 3-150 billion yuan (configurable via MARKET_CAP_MIN/MARKET_CAP_MAX)

### Stock Filtering Rules

Applied via `screeners/base_screener.py` StockFilter class:
1. Exclude delisted stocks
2. Exclude Shenzhen indices (399xxx)
3. Exclude Beijing Stock Exchange (43/83/87/88 prefixes)
4. Exclude keywords: 指数, ETF, LOF, REITs, 退, 可转债
5. Exclude ST stocks (*ST, ST, PT)
6. Filter by market cap (30亿-1500亿, configurable)

### Stock Data Characteristics

- **Total Stocks**: 4,663 A-share stocks (after filtering)
- **Data Range**: 2024-09-01 to present (about 6 months)
- **Database Size**: ~326MB (stock_data.db)
- **Daily Records**: ~1.4M rows (4663 stocks × 300 days)

## Deployment & Automation

### Cron/Launchd Setup

Cron tasks configured via macOS LaunchAgents:
- Post-market tasks run daily at 15:30 on weekdays
- Install: `bash scripts/cron/install_cron.sh`
- Scripts in: `scripts/cron/postmarket_task.py`, `scripts/cron/intraday_task.py`

### Dashboard Access

- Local URL: `http://localhost:8765`
- External access: Cpolar tunnel (configured in ~/.cpolar/cpolar.yml)
- Authentication: Basic Auth with `DASHBOARD_PASSWORD` env var
- Password: admin/bruce2024 (check config for current credentials)

### Data Freshness

- Target: T+1 (previous day's closing data)
- Download time: Daily after market close (recommended 15:30+)
- Auto-run: Screeners execute automatically after data download completes

## Important Conventions

### Immutability & Data Handling
- Always use `INSERT OR REPLACE` for idempotent data writes
- Never mutate data objects in place; create new copies
- Progress files (`data/daily_update_progress_v2.json`) enable resume after interruption

### Error Handling
- Comprehensive error handling at all levels (network, database, API)
- Retry logic: 3 attempts with exponential backoff
- Delisted stock handling: 3 consecutive failures marks as delisted
- Database operations: Use WAL mode with timeout=30

### File Organization
- Screeners: Many small modules in `screeners/`, each < 500 lines
- Screener output: `data/screeners/{name}/{date}.xlsx`
- Logs: `logs/` directory with daily rotation
- Config: Centralized in `scripts/config.py`

### Testing
- Test screeners with `scripts/test_all_screeners.py`
- Daily QA with `scripts/daily_screener_qa.py` validates results
- Expected output: 80%+ of screeners should find stocks on trading days

## Troubleshooting

### Common Issues

**Data Download Fails**
- Check Baostock connectivity: `ping www.baostock.com`
- Check progress file: `data/daily_update_progress_v2.json`
- Resume: `python3 scripts/fetcher_baostock.py --loop`

**Database Locked**
- Check for blocking processes: `lsof data/stock_data.db`
- Kill stuck processes: `pkill -f "python3.*screener"`
- Restart Dashboard: `pkill -f "dashboard/app.py"`

**Dashboard 500 Error**
- Check `logs/dashboard.log`
- Verify DASHBOARD_PASSWORD is set
- Check database integrity: `sqlite3 data/dashboard.db "PRAGMA integrity_check;"`

**Screener Returns No Results**
- Verify data exists: `sqlite3 data/stock_data.db "SELECT MAX(trade_date) FROM daily_prices;"`
- Check if target date is a trading day: `python3 scripts/trading_calendar.py`
- Run screener with verbose logging

### Data Recovery

**Rollback to Previous Day**
```bash
# Stop writes
pkill -f "daily_update_screener.py"

# Restore backup
cp data/stock_data.db.bak.$(date +%Y%m%d) data/stock_data.db

# Clear progress
rm data/daily_update_progress_v2.json

# Retry
python3 scripts/fetcher_baostock.py --loop
```

## Key Files Reference

| Path | Purpose |
|------|---------|
| `scripts/config.py` | Central configuration (paths, filters, constants) |
| `screeners/base_screener.py` | Abstract base class for all screeners |
| `backend/app.py` | Flask Dashboard server |
| `backend/models.py` | SQLite ORM models |
| `scripts/fetcher_baostock.py` | Daily data download from Baostock |
| `scripts/trading_calendar.py` | Trading calendar utilities |
| `scripts/daily_screener_qa.py` | Daily QA validation |
| `docs/data_pipeline.md` | Data pipeline documentation |
| `docs/operations_runbook.md` | Operations and troubleshooting guide |

## Notes for Future Work

- **News/LLM Features**: Currently disabled (enable_news=False)
- **Individual Screener Parameters**: Most are hardcoded in config.py, consider making configurable
- **Backtest Results**: schema exists in models.py but not fully implemented
- **Mobile Support**: Frontend has responsive design but could be optimized
