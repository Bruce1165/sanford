# Session Start Verification System

**Purpose**: Lightweight session start to ensure Claude Code knows WHERE to find guidelines (just-in-time reading)  
**Created**: 2026-04-16  
**Updated**: 2026-04-16 (Selective approach to prevent context overflow)  
**Status**: Active - Must be completed for each new session

---

## 🚀 Lightweight Session Start

**CRITICAL: Claude Code MUST complete this verification checklist BEFORE any work**

### 📍 I Know Where to Find Guidelines

**[ ]** Read `TECHNICAL_DOCS/00_START_HERE.md` (entry point only - 2 min)
   - Purpose: Understand documentation ecosystem structure
   - Confirm: 4-level semantic hierarchy (system/component/specific/reference)

**[ ]** Confirm Development Workflow Understanding
   - "I know development guidelines are in `/Users/mac/NeoTrade2/DEVELOPMENT_BEST_PRACTICES.md`"
   - "I know screener guide is in `/Users/mac/NeoTrade2/scripts/SCREENERS_README.md`"
   - "I know regression checklist is in `/Users/mac/NeoTrade2/backend/regression_checklist.md`"
   - "I know project config/status are in `/Users/mac/NeoTrade2/PROJECT_CONFIG.md` and `PROJECT_STATUS.md`"

**[ ]** Confirm Just-in-Time Reading Approach
   - "I will read ONLY relevant guidelines BEFORE starting each specific task type"
   - "I will NOT read all guidelines at session start (prevent context overflow)"

---

## 📋 What to Read When (Just-in-Time Lookup)

**BEFORE starting any work, identify task type and read ONLY relevant guidelines:**

### Documentation Work
- Read: `TECHNICAL_DOCS/QUICK_REFERENCE.md` (decision trees, placement rules)
- If complex: `TECHNICAL_DOCS/DOCUMENTATION_MAINTENANCE_GUIDE.md`

### New Screener Development
- Read: `DEVELOPMENT_BEST_PRACTICES.md` (planning, pseudocode, backup, testing)
- Read: `scripts/SCREENERS_README.md` (screener-specific workflows)

### Code Modification
- Read: `DEVELOPMENT_BEST_PRACTICES.md` (backup procedures, English-only code)

### Testing/Validation
- Read: `backend/regression_checklist.md` (testing procedures)

### Configuration Changes
- Read: `PROJECT_CONFIG.md` (port setup, database paths)
- Read: `PROJECT_STATUS.md` (active components, known issues)

---

## ✅ Completion Criteria

**Session start verification is COMPLETE when:**

- [ ] Entry point read and documentation structure understood
- [ ] I know WHERE to find each type of guideline
- [ ] I confirm just-in-time reading approach (not all at once)

**Claude Code is ready! Task-specific guidelines will be read when work is assigned.**

---

**Last Updated**: 2026-04-16  
**Version**: 1.0 - Mandatory session start verification  
**Status**: Active - Must be completed for each new session
