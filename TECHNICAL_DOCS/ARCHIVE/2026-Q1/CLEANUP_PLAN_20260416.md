# NeoTrade2 Comprehensive Cleanup Plan
**Date**: 2026-04-16
**Scope**: Documentation deduplication, archive cleanup, cross-project structure unification

---

## 📊 Current State Analysis

### Documentation Structure
- **TECHNICAL_DOCS/**: 50 total .md files (21 active + 28 archived + 1 index)
- **research/**: 15 .md files (predictive cup analysis)
- **STOCKPREDICTION/**: 13 .md files (ML prediction system)
- **archive/**: Well-organized from April 2 cleanup

### Key Issues Identified
1. **Duplicate Coffee Cup Documentation**
   - `11_COFFEE_CUP_PARAMS.md` (255 lines, outdated 2026-04-09)
   - `11_COFFEE_CUP_PARAMS_V4.md` (193 lines, current 2026-04-13)
   - **Action**: Archive old version, keep V4

2. **Overlapping Operations Documentation**
   - `06_OPERATIONS.md` (general operations)
   - `13_FLASK_CPOLAR_SERVICES.md` (specific service management)
   - **Action**: Keep both but clarify scope in titles

3. **Archive Bloat** (28 files in TECHNICAL_DOCS/ARCHIVE/)
   - Historical reports from March 2026
   - Outdated architecture plans
   - Duplicate screener guides
   - **Action**: Move truly historical items to project-level archive, remove duplicates

4. **Cross-Project Documentation Fragmentation**
   - Each subproject has independent documentation
   - No unified index or cross-references
   - **Action**: Create master documentation hub

---

## 🎯 Proposed New Documentation Structure

### Unified Documentation Hierarchy

```
/Users/mac/NeoTrade2/
├── TECHNICAL_DOCS/                    # Master documentation hub
│   ├── 00_START_HERE.md               # Unified entry point
│   ├── 01_MAIN_PROJECT.md             # NeoTrade2 core docs
│   ├── 02_RESEARCH_PROJECTS.md        # Research & STOCKPREDICTION
│   ├── 03_ARCHITECTURE.md            # System architecture
│   ├── 04_API_REFERENCE.md            # Complete API reference
│   ├── 05_OPERATIONS_GUIDE.md        # Unified operations guide
│   ├── 06_DEPLOYMENT.md              # Deployment & services
│   └── PROJECT_INDEX.md               # Cross-project index
├── PROJECTS/                         # Cross-project organization
│   ├── NeoTrade2/                    # Main project (current location)
│   ├── research/                      # Research subproject
│   │   ├── predictive_cup/
│   │   │   ├── TECHNICAL_DOCS/      # Keep local project docs
│   │   │   └── docs/               # Research-specific docs
│   └── STOCKPREDICTION/             # ML prediction project
│       ├── docs/                     # Keep local project docs
│       └── models/
└── ARCHIVES/                         # Unified archival system
    ├── 2026-Q1/                    # Q1 2026 archives
    │   ├── documentation/
    │   ├── reports/
    │   └── analysis/
    ├── 2026-Q2/                    # Q2 2026 archives
    └── historical/                   # Older archives
```

### Documentation Reorganization

#### Phase 1: Active Documentation Consolidation
**Keep in TECHNICAL_DOCS/**:
- `00_START_HERE.md` (update to be unified entry)
- `01_START_SERVER.md` → rename to `01_MAIN_PROJECT.md`
- `02_SYSTEM_CONFIG.md` (keep)
- `03_FLASK_ARCHITECTURE.md` (keep)
- `04_SCREENING_CONFIG.md` (keep)
- `05_DATA_PIPELINE.md` (keep)
- `06_OPERATIONS.md` (keep but update scope)
- `07_MONITORING.md` (keep)
- `08_API_REFERENCE.md` (keep)
- `09_SCREENERS_GUIDE.md` (keep)
- `10_ONEIL_METHODS.md` (keep)
- `11_COFFEE_CUP_PARAMS_V4.md` → `11_COFFEE_CUP_PARAMS.md` (replace old)
- `12_COFFEE_CUP_WIZARD_PLAN.md` (review for relevance)
- `13_FLASK_CPOLAR_SERVICES.md` → `06_DEPLOYMENT.md` (merge/refactor)
- `14_AUTHENTICATION_FIX.md` (archive - historical incident)
- `15_SCREENER_MANAGEMENT.md` (keep)
- `16_SCREENER_DISABLE_20260413.md` (archive - historical)
- `PROJECT_MANAGEMENT_PLAN.md` (review for relevance)

#### Phase 2: Archive Cleanup
**Move to ARCHIVES/2026-Q1/documentation/**:
- All files from `TECHNICAL_DOCS/ARCHIVE/` except:
  - Keep recent incident reports (< 30 days old)
  - Keep architecture references still in use

**Remove completely**:
- Duplicate screener guides
- Outdated requirement documents
- Temporary analysis documents

#### Phase 3: Cross-Project Integration
**Create new unified documents**:
- `PROJECT_INDEX.md` - Master index of all projects
- `02_RESEARCH_PROJECTS.md` - Overview of research & STOCKPREDICTION
- Cross-references between project-specific docs

---

## 🗑️ Files to Remove/Archive

### Immediate Removal Candidates
1. `TECHNICAL_DOCS/11_COFFEE_CUP_PARAMS.md` (outdated)
2. `TECHNICAL_DOCS/14_AUTHENTICATION_FIX.md` (historical)
3. `TECHNICAL_DOCS/16_SCREENER_DISABLE_20260413.md` (historical)
4. `TECHNICAL_DOCS/ARCHIVE/DAILY_REPORT_20260319.md` (historical report)
5. `TECHNICAL_DOCS/ARCHIVE/PROJECT_REQUIREMENTS_V2.md` (outdated)
6. `TECHNICAL_DOCS/ARCHIVE/REQUIREMENTS.md` (outdated)

### Archive Candidates (Move to ARCHIVES/2026-Q1/)
All remaining `TECHNICAL_DOCS/ARCHIVE/` files for historical reference

---

## 🔧 Execution Plan

### Step 1: Backup Current State
```bash
# Create backup before cleanup
mkdir -p ARCHIVES/backup_20260416
cp -r TECHNICAL_DOCS ARCHIVES/backup_20260416/
```

### Step 2: Remove Outdated Documentation
- Delete superseded coffee cup params
- Archive historical incident reports
- Remove outdated requirement documents

### Step 3: Restructure Documentation
- Rename and reorganize active docs
- Create unified entry point
- Add cross-project references

### Step 4: Archive Historical Content
- Move ARCHIVE contents to quarterly archives
- Organize by type (documentation, reports, analysis)

### Step 5: Create Cross-Project Hub
- Add research project overview
- Add STOCKPREDICTION overview
- Create master index

### Step 6: Update All References
- Update internal links in all documentation
- Verify all cross-references work
- Update CLAUDE.md with new structure

---

## ✅ Verification Checklist

After cleanup, verify:
- [ ] All broken internal links are fixed
- [ ] No duplicate content remains
- [ ] Archive is properly organized by quarter
- [ ] Cross-project documentation is accessible
- [ ] All active documentation is up-to-date
- [ ] CLAUDE.md references correct documentation structure
- [ ] User can navigate documentation easily

---

## 📝 Notes

- This plan prioritizes keeping current, active documentation easily accessible
- Historical content is preserved but moved to organized archives
- Cross-project structure provides unified access while maintaining project autonomy
- Quarterly archive organization provides better long-term management

**Prepared by**: Claude Code Assistant
**Date**: 2026-04-16
**Status**: Ready for user verification and execution
