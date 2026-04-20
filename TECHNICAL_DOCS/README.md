# NeoTrade Technical Documentation

**📚 Complete Technical Documentation Hub for NeoTrade Ecosystem**

## 🚀 Quick Start

**New to the NeoTrade ecosystem?** Start with the unified entry point:

**→ [00_START_HERE.md](00_START_HERE.md)**

This is your gateway to all technical documentation, organized by semantic levels for easy navigation.

## 📖 Documentation Structure

### System Level
Located in `system/` - Architecture, deployment, and cross-project concerns
- **[01_project_overview.md](system/01_project_overview.md)** - All projects overview
- **[02_architecture.md](system/02_architecture.md)** - System architecture design
- **[03_deployment.md](system/03_deployment.md)** - Deployment and service management
- **[04_configuration.md](system/04_configuration.md)** - Configuration and authentication

### Component Level
Located in `components/` - Major functional areas and their management

#### Web & API (`components/web_and_api/`)
- **[flask_architecture.md](components/web_and_api/flask_architecture.md)** - Flask backend architecture
- **[api_reference.md](components/web_and_api/api_reference.md)** - Complete API documentation
- **[services.md](components/web_and_api/services.md)** - Service management (Flask & Cpolar)

#### Screeners (`components/screeners/`)
- **[overview.md](components/screeners/overview.md)** - Screener system overview
- **[configuration.md](components/screeners/configuration.md)** - Screener configuration system
- **[management.md](components/screeners/management.md)** - Screener CRUD operations

#### Specific Screeners (`components/screeners/specific/`)
- **[coffee_cup.md](components/screeners/specific/coffee_cup.md)** - Coffee cup screener parameters
- **[o_neil_methods.md](components/screeners/specific/o_neil_methods.md)** - O'Neil methodology
- **[coffee_cup_ui.md](components/screeners/specific/coffee_cup_ui.md)** - Coffee cup wizard integration

#### Data Pipeline (`components/data_pipeline/`)
- **[overview.md](components/data_pipeline/overview.md)** - Data pipeline and sources

#### Monitoring (`components/monitoring/`)
- **[setup.md](components/monitoring/setup.md)** - Monitoring and alerting setup

### Reference Level
Located in `reference/` - Quick reference and troubleshooting
- **[operations_guide.md](reference/operations_guide.md)** - Operations and troubleshooting

### Archive
Located in `ARCHIVE/` - Historical documentation and reports

## 🌟 Cross-Project Integration

### Research Project
**Location**: `../research/predictive_cup/`
**Documentation**: [predictive_cup/TECHNICAL_DOCS/](../research/predictive_cup/TECHNICAL_DOCS/00_START_HERE.md)
**Focus**: Predictive cup formation analysis using agent-based systems

### Prediction Project
**Location**: `../STOCKPREDICTION/`
**Documentation**: [STOCKPREDICTION/docs/](../STOCKPREDICTION/docs/INDEX.md)
**Focus**: Machine learning-based stock prediction system

## 🎯 Find Information Quickly

| I need to... | Look at... |
|---------------|------------|
| Understand the whole system | [00_START_HERE.md](00_START_HERE.md) |
| See project architecture | [system/02_architecture.md](system/02_architecture.md) |
| Deploy or run the system | [system/03_deployment.md](system/03_deployment.md) |
| Configure screeners | [components/screeners/configuration.md](components/screeners/configuration.md) |
| Use the API | [components/web_and_api/api_reference.md](components/web_and_api/api_reference.md) |
| Troubleshoot issues | [reference/operations_guide.md](reference/operations_guide.md) |
| Understand specific screeners | [components/screeners/specific/](components/screeners/specific/) |

## 📝 Documentation Philosophy

This documentation follows a **4-level semantic hierarchy**:

1. **System Level** - Big picture, architecture, deployment
2. **Component Level** - Major functional areas (screeners, data, monitoring)
3. **Specific Level** - Implementation details (individual screeners, algorithms)
4. **Reference Level** - Quick reference, troubleshooting, history

This structure ensures logical navigation from broad concepts to specific details.

## 🔍 Navigation Tips

- **Start here**: Always begin with [00_START_HERE.md](00_START_HERE.md)
- **Follow the hierarchy**: System → Component → Specific → Reference
- **Use search**: Most editors support file search across documentation
- **Check related docs**: Each document references related documentation

## 📞 Getting Help

- **Technical issues**: Check relevant component documentation
- **Architecture questions**: Review [system/02_architecture.md](system/02_architecture.md)
- **API questions**: See [components/web_and_api/api_reference.md](components/web_and_api/api_reference.md)
- **Operations issues**: Consult [reference/operations_guide.md](reference/operations_guide.md)

---

**Last Updated**: 2026-04-16
**Documentation Version**: 2.0 (Semantic Reorganization)

```
research/predictive_cup/
├── README.md                        # This file
├── PROJECT_MANAGEMENT_PLAN.md          # Agent roles & communication
├── scripts/                         # Research scripts
│   ├── analyze_historical_screeners.py  # Phase 1: Historical analysis
│   ├── build_prediction_model.py       # Phase 2: Model development
│   └── backtest_predictor.py         # Phase 3: Validation
├── output/                          # Research outputs
│   ├── analysis/                     # Data analysis results
│   ├── models/                       # Trained prediction models
│   ├── reports/                      # Backtest and validation reports
│   ├── status/                       # Daily agent updates
│   ├── handoffs/                     # Cross-agent handoff docs
│   ├── risks/                        # Risk register
│   └── progress/                     # Progress dashboard
├── docs/                            # Technical documentation
├── data/                            # Research database (writable)
│   └── research.db                  # Research-specific SQLite DB
```

---

## Phase Overview

### Phase 1: Research & Analysis (Weeks 1-2) 🔄 **CURRENT**
**Owner**: Data Analyst Agent

**Tasks**:
- [ ] Analyze historical screener results (18+ months)
- [ ] Identify screeners triggered during cup formation phases
- [ ] Extract temporal sequences of screener triggers
- [ ] Calculate baseline accuracy for rule-based approaches
- [ ] Create labeled dataset: `{stock, date, cup_formed, screeners_triggered}`

**Deliverables**:
- `output/analysis/dataset_phase1_YYYYMMDD.csv`
- `output/analysis/temporal_patterns_phase1_YYYYMMDD.md`
- `output/analysis/baseline_accuracy_phase1_YYYYMMDD.md`

**Gate**: Bruce approval required to proceed to Phase 2

---

### Phase 2: Prototype Implementation (Weeks 3-5)
**Owner**: ML Engineer Agent

**Tasks**:
- [ ] Design prediction model architecture
- [ ] Implement prediction engine
- [ ] Feature engineering from screener data
- [ ] Train model on historical data
- [ ] Model explainability and benchmarking

**Deliverables**:
- `output/models/predictor_v1.pkl`
- `output/models/model_architecture_phase2_YYYYMMDD.md`
- `scripts/predict_cups.py` (prediction API)

**Gate**: Bruce approval required to proceed to Phase 3

---

### Phase 3: Backtesting & Validation (Weeks 6-7)
**Owner**: Backtest Validator Agent

**Tasks**:
- [ ] Run backtesting on 18+ months historical data
- [ ] Calculate accuracy metrics (precision, recall, F1, lead time)
- [ ] Analyze false positives and false negatives
- [ ] Test across different market regimes
- [ ] Generate performance report

**Deliverables**:
- `output/reports/backtest_phase3_YYYYMMDD.md`
- Go/no-go recommendation for Phase 4

**Gate**: Bruce approval required to proceed to Phase 4

---

### Phase 4: Paper Trading (Weeks 8-11)
**Owner**: Backtest Validator Agent

**Tasks**:
- [ ] Deploy predictions in production mode
- [ ] Track accuracy on live data
- [ ] Compare predicted vs. actual cup formations
- [ ] Iterate model based on results

**Deliverables**:
- 4 weeks of live performance data
- Accuracy comparison: live vs. backtest

**Gate**: Bruce approval required to proceed to Phase 5

---

### Phase 5: Limited Deployment (Weeks 12-19)
**Owner**: Research Lead

**Tasks**:
- [ ] Enable trading on high-confidence predictions
- [ ] Monitor investment performance
- [ ] Track prediction accuracy
- [ ] Scale up gradually as confidence increases

**Deliverables**:
- Live trading performance metrics
- Risk-adjusted returns (Sharpe, drawdown)

---

## Safety Constraints

**Non-negotiable**:
- ❌ No modifications to `backend/app.py` (dashboard code)
- ❌ No restarts of Flask process
- ❌ No writes to `data/dashboard.db` (production DB)
- ✅ Read-only access to `data/stock_data.db` (stock prices)
- ✅ Read-only access to `data/screeners/` (historical screener results)
- ✅ All research outputs go to `research/` directory

---

## Data Access

### Read-Only (Production)
- `data/stock_data.db` - Stock price data (OHLCV)
- `data/screeners/{name}/{date}.xlsx` - Historical screener results

### Writable (Research Only)
- `research/data/research.db` - Research database for storing:
  - Labeled dataset
  - Prediction results
  - Backtest metrics
  - Intermediate analysis data

---

## Success Metrics

### Phase Completion Criteria
- **Phase 1**: Dataset quality score ≥ 8/10
- **Phase 2**: Code coverage ≥ 80%, no security vulnerabilities
- **Phase 3**: Backtest covers 18+ months, accuracy documented
- **Phase 4**: 4 weeks live data, accuracy within ±10% of backtest
- **Phase 5**: Trading performance tracked, risk-adjusted returns documented

### Target Prediction Accuracy
- **Precision**: ≥ 60% (of predicted cups, how many actually form?)
- **Recall**: ≥ 50% (of all cups, how many are predicted?)
- **F1 Score**: ≥ 0.55 (balance of precision and recall)
- **Lead Time**: ≥ 10 days average (how early do we predict?)

---

## Current Status

**Last Updated**: 2026-04-08

**Phase**: 1 (Research & Analysis) - Starting

**Progress**: 0%

**Next Action**: Assign Phase 1 task to Data Analyst Agent

---

## Questions?

Contact: Research Lead (Claude) or Stakeholder (Bruce)
