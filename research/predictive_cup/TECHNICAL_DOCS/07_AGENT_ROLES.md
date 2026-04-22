# Agent Roles & Responsibilities

## Overview

This document defines the roles, responsibilities, and coordination mechanisms for the multi-agent collaborative research approach.

---

## 🤖 Agent Roles

### 1. Research Lead (Project Manager)

**Primary Agent**: `planner` or human (Bruce)

**Responsibilities**:
- Overall project timeline management
- Agent coordination and task assignment
- Milestone tracking and reporting
- Risk identification and mitigation
- Cross-phase continuity (ensuring Phase 1 insights flow to Phase 2, etc.)
- Stakeholder communication (Bruce)
- Approval gate management
- Go/no-go decision support

**Deliverables**:
- Weekly progress reports to Bruce
- Phase completion summaries
- Risk register updates
- Agent performance metrics
- Project timeline adjustments

**Communication**:
- Daily: Brief status check with active agents
- Weekly: Formal progress report to Bruce
- Phase transitions: Approval requests and go/no-go recommendations
- Emergencies: Immediate notification to Bruce

**Key Skills**:
- Project management
- Risk assessment
- Stakeholder communication
- Decision-making
- Timeline optimization

---

### 2. Data Analyst Agent

**Primary Agent**: `ecc:python-reviewer` + `tdd-guide`

**Responsibilities**:
- Analyze historical screener results (7+ months)
- Identify which screeners trigger during each cup formation phase
- Extract temporal sequences of screener triggers
- Calculate baseline statistics (trigger frequencies, correlations)
- Create annotated dataset (which stocks formed cups, which didn't)
- Identify data quality issues and gaps
- Perform exploratory data analysis
- Generate data quality reports

**Deliverables to ML Engineer**:
- Labeled dataset: `{stock_code, date, cup_formed: bool, screeners_triggered: []}`
- Temporal sequence patterns: common orders of screener triggers
- Feature importance analysis: which screeners are most predictive
- Data quality report: gaps, outliers, missing data
- Baseline performance metrics for rule-based approaches

**Deliverables**:
- `output/analysis/dataset_phase1_YYYYMMDD.csv` - Labeled dataset
- `output/analysis/temporal_patterns_phase1_YYYYMMDD.md` - Pattern analysis
- `output/analysis/baseline_accuracy_phase1_YYYYMMDD.md` - Baseline metrics
- `output/analysis/data_quality_report_phase1_YYYYMMDD.md` - Data quality

**Communication**:
- Daily: Update Research Lead with analysis progress
- Weekly: Formal deliverables via `research/output/analysis/`
- Phase completion: Handoff meeting with ML Engineer

**Key Skills**:
- Python data analysis (pandas, numpy, sqlite3)
- Statistical analysis
- Pattern recognition
- Data visualization
- Database querying

---

### 3. ML Engineer Agent

**Primary Agent**: `python-patterns` + ML expertise

**Responsibilities**:
- Design prediction model architecture (state machine, scoring, or ML)
- Implement prediction engine in `research/scripts/`
- Feature engineering from screener data
- Model training on historical data
- Hyperparameter tuning
- Model explainability (why did we predict this stock?)
- Performance benchmarking
- Model versioning and management

**Deliverables to Backtest Validator**:
- Trained prediction model: `research/output/models/predictor.pkl` or equivalent
- Model architecture document: algorithm choice, features, thresholds
- Prediction API/script: `research/scripts/predict_cups.py --date YYYY-MM-DD`
- Feature documentation: what each input means
- Model version metadata

**Deliverables**:
- `output/models/predictor_v1.pkl` - Trained model
- `output/models/model_architecture_phase2_YYYYMMDD.md` - Model design
- `scripts/predict_cups.py` - Prediction API
- `output/analysis/feature_importance_phase2_YYYYMMDD.md` - Feature analysis
- `output/analysis/benchmark_results_phase2_YYYYMMDD.md` - Model comparison

**Communication**:
- Daily: Update Research Lead with development progress
- Weekly: Progress checkpoints
- Code reviews: With Data Analyst (understand the features)
- Phase completion: Handoff meeting with Backtest Validator

**Key Skills**:
- Machine learning (scikit-learn, XGBoost, or similar)
- Feature engineering
- Model evaluation
- Python programming
- Code quality and testing

---

### 4. Backtest Validator Agent

**Primary Agent**: `ecc:python-reviewer` + `tdd-guide`

**Responsibilities**:
- Run backtesting on 7+ months of historical data
- Calculate prediction accuracy metrics (precision, recall, F1, lead time)
- Analyze false positives and false negatives
- Test across different market regimes (bull, bear, sideways)
- Validate model generalization (out-of-sample testing)
- Generate performance reports
- Provide go/no-go recommendations

**Deliverables to Research Lead**:
- Backtest results: `research/output/reports/backtest_phase3_YYYYMMDD.md`
- Accuracy metrics: precision, recall, F1, lead time distribution
- Failure analysis: common reasons for false predictions
- Market regime analysis: performance in different conditions
- Go/no-go recommendation for Phase 4 (Paper Trading)

**Deliverables**:
- `output/reports/backtest_phase3_YYYYMMDD.md` - Backtest report
- `output/analysis/accuracy_metrics_phase3_YYYYMMDD.csv` - Detailed metrics
- `output/analysis/failure_analysis_phase3_YYYYMMDD.md` - Failure modes
- `output/reports/go_no_go_recommendation_phase3_YYYYMMDD.md` - Phase 4 decision

**Communication**:
- Daily: Backtest progress updates
- Weekly: Accuracy reports
- Phase completion: Final validation summary with phase transition recommendation

**Key Skills**:
- Backtesting frameworks
- Statistical analysis
- Performance metrics calculation
- Market regime analysis
- Report generation

---

### 5. Documentation Agent

**Primary Agent**: `ecc:doc-updater`

**Responsibilities**:
- Document all research findings
- Maintain `research/README.md` with current status
- Update technical specifications as agents deliver work
- Create user guides for prediction system
- Archive failed approaches (why they didn't work)
- Ensure research outputs are reproducible
- Maintain TECHNICAL_DOCS/ folder structure

**Deliverables**:
- Living documentation in `research/README.md`
- Technical specs: `research/docs/model_architecture.md`
- User guides: `research/docs/how_to_use_predictor.md`
- Research summary: `research/docs/phaseX_summary.md`
- Updated TECHNICAL_DOCS/ files as project evolves

**Communication**:
- Continuous: Updates as other agents deliver work
- Weekly: Documentation reviews with Research Lead
- Phase transitions: Comprehensive phase documentation

**Key Skills**:
- Technical writing
- Documentation organization
- User guide creation
- Knowledge management

---

### 6. Code Review Agent (Continuous)

**Primary Agent**: `ecc:python-reviewer` + `ecc:security-reviewer`

**Responsibilities**:
- Review all code written by ML Engineer and Data Analyst
- Ensure no security vulnerabilities (hardcoded credentials, SQL injection)
- Verify code quality, test coverage, error handling
- Check data access patterns (read-only to production DBs)
- Review database schema for research DB
- Provide immediate feedback on code submissions
- Weekly code quality reports to Research Lead

**Deliverables**:
- Code review comments and approvals
- Security audit reports
- Code quality metrics (coverage, complexity)
- Weekly code quality reports

**Communication**:
- Immediate: Feedback on code submissions
- Weekly: Code quality reports to Research Lead
- As needed: Security alerts

**Key Skills**:
- Security review
- Code quality assessment
- Python best practices
- Test coverage verification
- SQL injection prevention

---

## 🔄 Communication Mechanisms

### 1. Daily Standup (Asynchronous)

**Format**: Each agent posts a brief update to `research/output/status/daily_YYYYMMDD.md`

**Content**:
- What I did today
- What I plan to do tomorrow
- Blockers or questions for other agents
- Deliverables ready for handoff

**Timing**: End of each agent's workday

**Template**:
```markdown
# Daily Status - [Agent Name]

**Date**: YYYY-MM-DD
**Agent**: [Agent Name]

## Today's Work
- [Task 1]: Description
- [Task 2]: Description

## Tomorrow's Plan
- [Task 1]: Description
- [Task 2]: Description

## Blockers / Questions
- [Blocker or question for other agent]

## Deliverables Ready
- [File path]: Description
```

### 2. Weekly Deliverable Reviews

**Attendees**: Research Lead + relevant agents

**Format**: Structured review of deliverables against acceptance criteria

**Schedule**:
- Week 1: Data Analyst delivers initial analysis
- Week 2: ML Engineer delivers prediction model
- Week 3: Backtest Validator delivers accuracy metrics
- Weekly thereafter: Progress against milestones

### 3. Phase Transition Gates

**Approval Required**: Bruce (stakeholder)

**Gate Criteria**:

#### Phase 1 → Phase 2 (Research → Prototype)
- [ ] Data Analyst delivers labeled dataset with 7+ months coverage
- [ ] Temporal sequence patterns identified
- [ ] Baseline accuracy calculated for rule-based approach
- [ ] Bruce approves: "Proceed to prototype"

#### Phase 2 → Phase 3 (Prototype → Backtest)
- [ ] ML Engineer delivers working prediction model
- [ ] Model generates predictions for any given date
- [ ] Code review passes (security, quality, coverage)
- [ ] Bruce approves: "Ready for backtesting"

#### Phase 3 → Phase 4 (Backtest → Paper Trading)
- [ ] Backtest Validator completes 7+ month backtest
- [ ] Precision ≥ 60% OR F1 ≥ 0.55 (minimum threshold)
- [ ] False positive rate ≤ 30%
- [ ] Analysis of failures documented
- [ ] Bruce approves: "Deploy to paper trading"

#### Phase 4 → Phase 5 (Paper Trading → Live Trading)
- [ ] 4 weeks of live paper trading data
- [ ] Live accuracy matches backtest accuracy (±10%)
- [ ] Win rate ≥ 50% on predicted trades
- [ ] Bruce approves: "Start limited live trading"

### 4. Cross-Agent Handoffs

**Format**: Formal handoff meeting + documentation

**Template**:
```markdown
# Handoff: [From Agent] → [To Agent]

**Date**: YYYY-MM-DD
**From**: [Agent Name]
**To**: [Agent Name]

## Deliverables
- [File: path/to/deliverable1]: Description
- [File: path/to/deliverable2]: Description

## Acceptance Criteria
- [ ] To Agent has reviewed deliverables
- [ ] Questions resolved
- [ ] Ready to proceed to next phase

## Notes
[Any additional context or instructions]

**Signed**: [Research Lead]
```

**Documented in**: `research/output/handoffs/handoff_agentA_to_agentB_YYYYMMDD.md`

### 5. Risk & Issue Tracking

**Location**: `research/output/risks/risk_register.md`

**Format**:
```markdown
| Risk | Probability | Impact | Owner | Mitigation | Status |
|-------|-------------|---------|--------|------------|--------|
| [Risk description] | High/Medium/Low | High/Medium/Low | [Agent] | [Mitigation plan] | Active/Monitoring/Resolved |
```

**Update frequency**: Weekly by Research Lead

### 6. Progress Dashboard

**Location**: `research/output/progress/README.md` (updated daily)

**Visual Progress**:
```markdown
# Progress Dashboard - Week X of Y

## Phase 1: Research & Analysis
- [x] Data Analyst: Historical screener analysis
- [x] Data Analyst: Temporal pattern identification
- [ ] ML Engineer: Review Data Analyst deliverables
- [ ] Research Lead: Approve Phase 1 completion

**Overall Progress**: 40%

## Key Metrics
- Stocks analyzed: 4,663
- Historical period: 7 months (2024-09 to 2026-04)
- Cup formations identified: TBD
- Baseline accuracy: TBD
```

---

## 🎯 Agent Coordination Flow

### Phase 1: Research & Analysis (Weeks 1-2)
```
Day 1: Research Lead → Data Analyst: "Start Phase 1"
Week 1: Data Analyst works independently
Day 5: Data Analyst → Research Lead: "Week 1 analysis complete"
Week 1: Code Review Agent reviews Data Analyst code
Week 2: Data Analyst → Documentation Agent: "Update docs with findings"
Week 2: Data Analyst → ML Engineer: "Dataset handoff"
Week 2: Research Lead → Bruce: "Phase 1 ready for review"
```

### Phase 2: Prototype Implementation (Weeks 3-5)
```
Week 3: ML Engineer reviews Data Analyst deliverables
Week 3-4: ML Engineer implements prediction model
Week 4: Code Review Agent reviews ML Engineer code
Week 4: ML Engineer → Documentation Agent: "Update model docs"
Week 5: ML Engineer → Backtest Validator: "Model handoff"
Week 5: Research Lead → Bruce: "Phase 2 ready for review"
```

### Phase 3: Backtesting & Validation (Weeks 6-7)
```
Week 6: Backtest Validator runs backtests
Week 6: Backtest Validator → Research Lead: "Daily progress"
Week 7: Backtest Validator completes analysis
Week 7: Backtest Validator → Documentation Agent: "Update reports"
Week 7: Research Lead → Bruce: "Phase 3 complete, ready for Phase 4?"
```

---

## 🚨 Escalation Path

### 1. Agent Blocker
**Agent → Research Lead**: "Blocked on X, need help from Y"
**Research Lead**: Escalate to appropriate agent or Bruce

### 2. Technical Disagreement
**Format**: Split role review - 3 agents review independently
**Agents**: Data Analyst, ML Engineer, Backtest Validator
**Decision**: Research Lead makes final call with Bruce input

### 3. Timeline Risk
**Research Lead → Bruce**: "Phase X at risk, options are: A, B, C"
**Bruce**: Approves mitigation plan

### 4. Dashboard Impact Concern
**Any Agent → Research Lead**: "This change might affect dashboard"
**Research Lead → Bruce**: Immediate assessment, pause if needed

---

## 📊 Success Metrics by Agent

### Research Lead
- On-time milestone delivery (±1 week)
- Risk identification and mitigation
- Stakeholder satisfaction
- Phase transition approvals

### Data Analyst
- Dataset quality score ≥ 8/10
- Baseline F1 ≥ 0.30
- 7+ months data coverage
- 10,000+ labeled observations

### ML Engineer
- Model outperforms baseline (F1 improvement ≥ 0.10)
- Code coverage ≥ 80%
- No security vulnerabilities
- Model generates predictions for any date

### Backtest Validator
- Precision ≥ 60% OR F1 ≥ 0.55
- False positive rate ≤ 30%
- Average lead time ≥ 10 days
- Comprehensive failure analysis

### Documentation Agent
- All deliverables documented
- TECHNICAL_DOCS/ up to date
- User guides created
- Research reproducibility ensured

### Code Review Agent
- 100% code reviewed before commit
- Zero security vulnerabilities in production
- Code quality metrics met
- Immediate feedback provided

---

## 📞 Contact Points

### For This Session
- **Research Lead**: Primary point of contact
- **Active Agent**: Currently working on phase tasks
- **Bruce**: Stakeholder for approvals

### Escalation
1. Agent → Research Lead (first point)
2. Research Lead → Bruce (if needed)
3. Emergency: Direct communication with Bruce

---

**Last Updated**: 2026-04-09
**Version**: v1.0
