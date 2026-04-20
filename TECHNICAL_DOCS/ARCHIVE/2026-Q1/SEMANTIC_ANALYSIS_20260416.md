# Semantic Documentation Analysis
**Date**: 2026-04-16
**Purpose**: Analyze documentation by semantic meaning and design proper hierarchy

---

## 🧠 Semantic Levels Framework

### Level 1: Project/System Level
**Scope**: Entire NeoTrade2 ecosystem, cross-project concerns
**Audience**: System architects, project leads, new team members
**Content**: Architecture, deployment, project overview, cross-project integration

### Level 2: Component/Subsystem Level  
**Scope**: Major functional areas (screeners, data pipeline, monitoring, API)
**Audience**: Component developers, system operators
**Content**: Component overviews, configuration, management, operations

### Level 3: Specific Implementation Level
**Scope**: Individual implementations within components
**Audience**: Feature developers, maintainers
**Content**: Specific screener details, individual algorithms, concrete configurations

### Level 4: Reference/Utility Level
**Scope**: Quick reference, troubleshooting, historical info
**Audience**: All users (developers, operators, analysts)
**Content**: API specs, troubleshooting guides, incident reports, historical records

---

## 📊 Current Documentation Semantic Analysis

### Active Documentation Files (TECHNICAL_DOCS/)

| File | Semantic Level | Primary Subject | Parent Category | Current Issues |
|------|----------------|-----------------|-----------------|----------------|
| 00_START_HERE.md | L1 | Navigation | System | Good entry point, needs cross-project links |
| 01_START_SERVER.md | L1 | Deployment | System | Specific to main project, needs L1 clarification |
| 02_SYSTEM_CONFIG.md | L1 | Configuration | System | Good, but scope unclear (main vs all projects) |
| 03_FLASK_ARCHITECTURE.md | L2 | Web/API | Components | Flask-specific, should be under web component |
| 04_SCREENING_CONFIG.md | L2 | Screeners | Components | L2 screener management, good placement |
| 05_DATA_PIPELINE.md | L2 | Data | Components | L2 data pipeline, good placement |
| 06_OPERATIONS.md | L4 | Operations | Reference | Mix of L2 monitoring and L4 troubleshooting |
| 07_MONITORING.md | L2 | Monitoring | Components | L2 monitoring component, good placement |
| 08_API_REFERENCE.md | L4 | API Reference | Reference | L4 API documentation, good placement |
| 09_SCREENERS_GUIDE.md | L2 | Screeners | Components | L2 screener overview, good placement |
| 10_ONEIL_METHODS.md | L3 | Trading Methods | Specific | L3 technical methodology, could be L2/L3 |
| 11_COFFEE_CUP_PARAMS_V4.md | L3 | Coffee Cup Screener | Specific | ✅ CORRECT: L3 specific screener |
| 11_COFFEE_CUP_PARAMS.md | L3 | Coffee Cup Screener | Specific | ❌ DUPLICATE: Outdated version |
| 12_COFFEE_CUP_WIZARD_PLAN.md | L3 | Coffee Cup UI | Specific | L3 specific feature plan |
| 13_FLASK_CPOLAR_SERVICES.md | L2 | Deployment | Components | L2 service management, good placement |
| 14_AUTHENTICATION_FIX.md | L4 | Incident | Reference | L4 historical incident, should be archived |
| 15_SCREENER_MANAGEMENT.md | L2 | Screeners | Components | L2 screener CRUD operations, good placement |
| 16_SCREENER_DISABLE_20260413.md | L4 | Incident | Reference | L4 historical change log, should be archived |
| PROJECT_MANAGEMENT_PLAN.md | L1 | Project Mgmt | System | L1 project planning, good placement |

### Research Project Documentation

| File | Semantic Level | Primary Subject | Notes |
|------|----------------|-----------------|-------|
| 00_START_HERE.md | L1 | Research Entry | Research-specific entry point |
| 01_PROJECT_OVERVIEW.md | L1 | Research Overview | L1 research project scope |
| 02_PHASE_PLAN.md | L1 | Research Planning | L1 project phases |
| 03_DATA_ACCESS.md | L2 | Data Component | L2 data access for research |
| 04_SAFETY_CONSTRAINTS.md | L1 | Project Rules | L1 research safety guidelines |
| 05_ARCHITECTURE.md | L2 | Research Architecture | L2 research system design |
| 06_CURRENT_STATUS.md | L1 | Project Status | L1 current research state |
| 07_AGENT_ROLES.md | L2 | Research Components | L2 agent system components |
| 08_RISK_REGISTER.md | L4 | Reference | L4 risk tracking |

### STOCKPREDICTION Project Documentation

| File | Semantic Level | Primary Subject | Notes |
|------|----------------|-----------------|-------|
| INDEX.md | L1 | Prediction Entry | Prediction-specific entry point |
| DATA_MODEL.md | L2 | Data Component | L2 data structure |
| DATA_PIPELINE.md | L2 | Data Component | L2 prediction data flow |
| MODEL_ARCHITECTURE.md | L2 | ML Component | L2 model design |
| FEATURE_ENGINEERING.md | L2 | ML Component | L2 feature design |
| TRAINING_PIPELINE.md | L2 | ML Component | L2 training process |
| PREDICTION_PIPELINE.md | L2 | ML Component | L2 inference process |
| API_REFERENCE.md | L4 | API Reference | L4 prediction API |
| DEVELOPMENT_GUIDE.md | L1 | Development | L1 dev setup |
| DEPLOYMENT_GUIDE.md | L1 | Deployment | L1 prediction deployment |
| PERIODIC_SELECTION_THEORY.md | L3 | Trading Theory | L3 specific methodology |
| CHINESE_A_STOCK_CYCLE_THEORY.md | L3 | Trading Theory | L3 domain knowledge |
| IMPLEMENTATION_PLAN.md | L1 | Planning | L1 implementation roadmap |
| RESEARCH_PLAN.md | L1 | Research Planning | L1 research approach |

---

## 🏗️ Proposed Semantic Hierarchy Structure

### Unified NeoTrade Ecosystem Documentation

```
TECHNICAL_DOCS/
├── 00_START_HERE.md                    # L1: Unified ecosystem entry point
├── system/                              # L1: System-level documentation
│   ├── 01_project_overview.md          # All projects overview
│   ├── 02_architecture.md              # System architecture
│   ├── 03_deployment.md               # Deployment across all projects
│   └── 04_configuration.md            # System-wide configuration
├── components/                          # L2: Component-level documentation  
│   ├── web_and_api/
│   │   ├── flask_architecture.md       # Flask backend
│   │   ├── api_reference.md          # API documentation
│   │   └── services.md              # Flask & Cpolar services
│   ├── screeners/
│   │   ├── overview.md               # General screener concepts
│   │   ├── configuration.md          # Screener config system
│   │   ├── management.md             # CRUD operations
│   │   └── specific/                # L3: Specific screeners
│   │       ├── coffee_cup.md        # Coffee cup details
│   │       ├── o_neil_methods.md   # O'Neil methodology
│   │       ├── jin_feng_huang.md   # Other specific screeners...
│   │       └── ...
│   ├── data_pipeline/
│   │   ├── overview.md               # Data flow overview
│   │   ├── sources.md               # Data sources (Baostock, etc.)
│   │   ├── processing.md            # Data processing
│   │   └── quality.md              # Data quality & validation
│   ├── monitoring/
│   │   ├── setup.md                 # Monitoring setup
│   │   ├── alerts.md               # Alert configuration
│   │   └── dashboards.md            # Dashboard configuration
│   └── ml_prediction/               # STOCKPREDICTION component
│       ├── overview.md               # ML system overview
│       ├── model_architecture.md     # Model design
│       ├── feature_engineering.md    # Feature design
│       ├── training_pipeline.md      # Training process
│       └── prediction_pipeline.md    # Inference process
├── research/                            # Research project documentation
│   ├── 01_overview.md                # Research project overview
│   ├── 02_phases.md                  # Research phases
│   ├── 03_architecture.md            # Research system design
│   ├── 04_data_access.md            # Research data access
│   ├── 05_agent_system.md           # Agent components
│   └── 06_safety_constraints.md     # Research safety rules
└── reference/                           # L4: Reference and utility
    ├── operations_guide.md            # Operations & troubleshooting
    ├── incident_history.md           # Historical incidents
    ├── change_log.md                # System changes
    └── glossary.md                 # Terminology reference
```

---

## 🔄 File Mapping to New Structure

### Current → New Structure Mapping

**System Level (L1)**
- `00_START_HERE.md` → `00_START_HERE.md` (enhanced with cross-project nav)
- `02_SYSTEM_CONFIG.md` → `system/04_configuration.md`
- `PROJECT_MANAGEMENT_PLAN.md` → `system/01_project_overview.md`

**Component Level (L2)**  
- `03_FLASK_ARCHITECTURE.md` → `components/web_and_api/flask_architecture.md`
- `13_FLASK_CPOLAR_SERVICES.md` → `components/web_and_api/services.md`
- `08_API_REFERENCE.md` → `components/web_and_api/api_reference.md`
- `04_SCREENING_CONFIG.md` → `components/screeners/configuration.md`
- `09_SCREENERS_GUIDE.md` → `components/screeners/overview.md`
- `15_SCREENER_MANAGEMENT.md` → `components/screeners/management.md`
- `05_DATA_PIPELINE.md` → `components/data_pipeline/overview.md`
- `07_MONITORING.md` → `components/monitoring/setup.md`

**Specific Level (L3)**
- `11_COFFEE_CUP_PARAMS_V4.md` → `components/screeners/specific/coffee_cup.md`
- `10_ONEIL_METHODS.md` → `components/screeners/specific/o_neil_methods.md`
- `12_COFFEE_CUP_WIZARD_PLAN.md` → `components/screeners/specific/coffee_cup_ui.md`

**Reference Level (L4)**
- `06_OPERATIONS.md` → `reference/operations_guide.md`
- `14_AUTHENTICATION_FIX.md` → `reference/incident_history.md`
- `16_SCREENER_DISABLE_20260413.md` → `reference/change_log.md`

**Research Project (Preserve Structure)**
- Keep existing structure under `research/` directory
- Create cross-reference from main `00_START_HERE.md`

**STOCKPREDICTION Project (Integrate as Component)**
- Move core docs to `components/ml_prediction/`
- Keep project-specific files in original location

---

## 🎯 Key Improvements from Semantic Reorganization

### 1. **Clear Subject Hierarchy**
- **System → Component → Specific** progression makes sense
- Easy to navigate from broad to detailed
- Separation of concerns is clear

### 2. **Logical Grouping**
- All screener-related content in one place
- All data pipeline content in one place  
- All web/API content in one place
- ML prediction integrated as component

### 3. **Audience Clarity**
- L1 for architects/leads (big picture)
- L2 for developers/operators (working knowledge)
- L3 for feature developers (implementation details)
- L4 for everyone (reference & troubleshooting)

### 4. **Reduced Confusion**
- Coffee cup params clearly under specific screeners
- No more wondering where to find screener vs. system info
- Clear boundaries between component and implementation details

### 5. **Scalable Structure**
- Easy to add new screeners (just add to `specific/`)
- Easy to add new components (add new directory)
- Maintains clarity as system grows

---

## ❓ Questions for User Verification

1. **Does this 4-level semantic hierarchy make sense** for your documentation needs?
2. **Should STOCKPREDICTION be integrated as a component** or kept separate?
3. **Should individual screener docs be under `specific/`** or keep independent files?
4. **Any missing semantic categories** you'd expect to see?
5. **Is the current L4 reference structure adequate** or needs reorganization?

---

**Prepared by**: Claude Code Assistant  
**Date**: 2026-04-16  
**Status**: Ready for user feedback and refinement
