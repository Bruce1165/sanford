# Predictive Coffee Cup Formation - Project Management Plan

## Project Overview

**Objective**: Build a predictive system that detects coffee cup pattern formation before completion by combining signals from existing 11 screeners.

**Approach**: Multi-agent collaborative research with clear roles, responsibilities, and communication mechanisms.

**Timeline**: 10-18 weeks total (5 phases)

---

## Agent Roles & Responsibilities

### 1. Research Lead (PM) - Primary Orchestrator
**Agent**: `planner` or human (Bruce)

**Responsibilities**:
- Overall project timeline management
- Agent coordination and task assignment
- Milestone tracking and reporting
- Risk identification and mitigation
- Cross-phase continuity (ensuring Phase 1 insights flow to Phase 2, etc.)
- Stakeholder communication (Bruce)
- Approval gate management

**Deliverables**:
- Weekly progress reports to Bruce
- Phase completion summaries
- Risk register updates
- Agent performance metrics

---

### 2. Data Analyst Agent
**Agent**: `ecc:python-reviewer` (Python/data analysis expertise) + `tdd-guide` for testing

**Responsibilities**:
- Analyze historical screener results (18+ months)
- Identify which screeners trigger during each cup formation phase
- Extract temporal sequences of screener triggers
- Calculate baseline statistics (trigger frequencies, correlations)
- Create annotated dataset (which stocks formed cups, which didn't)
- Identify data quality issues and gaps

**Deliverables to ML Engineer**:
- Labeled dataset: `{stock_code, date, cup_formed: bool, screeners_triggered: []}`
- Temporal sequence patterns: common orders of screener triggers
- Feature importance analysis: which screeners are most predictive
- Data quality report: gaps, outliers, missing data

**Communication**:
- Updates Research Lead daily with analysis progress
- Weekly formal deliverables via `research/output/analysis/`
- Handoff meeting with ML Engineer at Phase 1 completion

---

### 3. ML Engineer Agent
**Agent**: `python-patterns` + ML expertise

**Responsibilities**:
- Design prediction model architecture (state machine, scoring, or ML)
- Implement prediction engine in `research/scripts/`
- Feature engineering from screener data
- Model training on historical data
- Hyperparameter tuning
- Model explainability (why did we predict this stock?)
- Performance benchmarking

**Deliverables to Backtest Validator**:
- Trained prediction model: `research/output/models/predictor.pkl` or equivalent
- Model architecture document: algorithm choice, features, thresholds
- Prediction API/script: `research/scripts/predict_cups.py --date YYYY-MM-DD`
- Feature documentation: what each input means

**Communication**:
- Updates Research Lead daily with development progress
- Code reviews with Data Analyst (understand the features)
- Weekly progress checkpoints
- Handoff meeting with Backtest Validator at Phase 2 completion

---

### 4. Backtest Validator Agent
**Agent**: `ecc:python-reviewer` + `tdd-guide`

**Responsibilities**:
- Run backtesting on 18+ months of historical data
- Calculate prediction accuracy metrics (precision, recall, F1, lead time)
- Analyze false positives and false negatives
- Test across different market regimes (bull, bear, sideways)
- Validate model generalization (out-of-sample testing)
- Generate performance reports

**Deliverables to Research Lead**:
- Backtest results: `research/output/reports/backtest_phase3_YYYYMMDD.md`
- Accuracy metrics: precision, recall, F1, lead time distribution
- Failure analysis: common reasons for false predictions
- Market regime analysis: performance in different conditions
- Go/no-go recommendation for Phase 4 (Paper Trading)

**Communication**:
- Daily backtest progress updates
- Weekly accuracy reports
- Final validation summary with phase transition recommendation

---

### 5. Documentation Agent
**Agent**: `ecc:doc-updater`

**Responsibilities**:
- Document all research findings
- Maintain `research/README.md` with current status
- Update technical specifications as agents deliver work
- Create user guides for prediction system
- Archive failed approaches (why they didn't work)
- Ensure research outputs are reproducible

**Deliverables**:
- Living documentation in `research/README.md`
- Technical specs: `research/docs/model_architecture.md`
- User guides: `research/docs/how_to_use_predictor.md`
- Research summary: `research/docs/phaseX_summary.md`

**Communication**:
- Continuous updates as other agents deliver work
- Weekly documentation reviews with Research Lead

---

### 6. Code Review Agent (Continuous)
**Agent**: `ecc:python-reviewer` + `ecc:security-reviewer`

**Responsibilities**:
- Review all code written by ML Engineer and Data Analyst
- Ensure no security vulnerabilities (hardcoded credentials, SQL injection)
- Verify code quality, test coverage, error handling
- Check data access patterns (read-only to production DBs)
- Review database schema for research DB

**Communication**:
- Immediate feedback on code submissions
- Weekly code quality reports to Research Lead

---

## Communication Mechanisms

### 1. Daily Standup (Asynchronous)
**Format**: Each agent posts a brief update to `research/output/status/daily_YYYYMMDD.md`

**Content**:
- What I did today
- What I plan to do tomorrow
- Blockers or questions for other agents
- Deliverables ready for handoff

**Timing**: End of each agent's workday

---

### 2. Weekly Deliverable Reviews
**Attendees**: Research Lead + relevant agents

**Format**: Structured review of deliverables against acceptance criteria

**Schedule**:
- Week 1: Data Analyst delivers initial analysis
- Week 2: ML Engineer delivers prediction model
- Week 3: Backtest Validator delivers accuracy metrics
- Weekly thereafter: Progress against milestones

---

### 3. Phase Transition Gates
**Approval Required**: Bruce (stakeholder)

**Gate Criteria**:

#### Phase 1 → Phase 2 (Research → Prototype)
- [ ] Data Analyst delivers labeled dataset with 18+ months coverage
- [ ] Temporal sequence patterns identified
- [ ] Baseline accuracy calculated for rule-based approach
- [ ] Bruce approves: "Proceed to prototype"

#### Phase 2 → Phase 3 (Prototype → Backtest)
- [ ] ML Engineer delivers working prediction model
- [ ] Model generates predictions for any given date
- [ ] Code review passes (security, quality, coverage)
- [ ] Bruce approves: "Ready for backtesting"

#### Phase 3 → Phase 4 (Backtest → Paper Trading)
- [ ] Backtest Validator completes 18+ month backtest
- [ ] Precision ≥ 60% OR F1 ≥ 0.55 (minimum threshold)
- [ ] False positive rate ≤ 30%
- [ ] Analysis of failures documented
- [ ] Bruce approves: "Deploy to paper trading"

#### Phase 4 → Phase 5 (Paper Trading → Live Trading)
- [ ] 4 weeks of live paper trading data
- [ ] Live accuracy matches backtest accuracy (±10%)
- [ ] Win rate ≥ 50% on predicted trades
- [ ] Bruce approves: "Start limited live trading"

---

### 4. Cross-Agent Handoffs
**Format**: Formal handoff meeting + documentation

**Template**:
```
Handoff: [From Agent] → [To Agent]
Date: YYYY-MM-DD
Deliverables:
  - File: path/to/deliverable1
  - File: path/to/deliverable2
Acceptance Criteria:
  - [ ] To Agent has reviewed deliverables
  - [ ] Questions resolved
  - [ ] Ready to proceed to next phase
Signed: [Research Lead]
```

**Documented in**: `research/output/handoffs/handoff_agentA_to_agentB_YYYYMMDD.md`

---

### 5. Risk & Issue Tracking
**Location**: `research/output/risks/risk_register.md`

**Format**:
```markdown
| Risk | Probability | Impact | Owner | Mitigation | Status |
|-------|-------------|---------|--------|------------|--------|
| Model overfits historical data | High | High | ML Engineer | Out-of-sample testing, regularization | Monitoring |
| Data gaps in 18+ months | Medium | Medium | Data Analyst | Gap analysis, alternative sources | Resolved |
| Dashboard performance impact | Low | Medium | Research Lead | Isolated research DB, read-only access | N/A |
```

**Update frequency**: Weekly by Research Lead

---

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
- Historical period: 18 months (2024-09 to 2026-04)
- Cup formations identified: TBD
- Baseline accuracy: TBD
```

---

## Agent Coordination Flow

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

## Escalation Path

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

## Research Constraints (Non-Negotiable)

1. **Dashboard Protection**
   - ❌ No modifications to `backend/app.py`
   - ❌ No restarts of Flask process
   - ❌ No writes to `data/dashboard.db`
   - ✅ Read-only access to `data/stock_data.db`
   - ✅ Read-only access to `data/screeners/`

2. **Isolation**
   - All research code in `research/` directory
   - Separate research database: `research/data/research.db`
   - Git worktree isolation: `research-predictive-cup`
   - No production code modifications without explicit approval

3. **Data Integrity**
   - Never modify `data/stock_data.db` (read-only)
   - Never delete historical screener results
   - Always validate data before processing

---

## Success Metrics (Shared Across Agents)

### Phase Completion Criteria
- Phase 1: Dataset quality score ≥ 8/10 (coverage, accuracy, completeness)
- Phase 2: Model code coverage ≥ 80%, no security vulnerabilities
- Phase 3: Backtest covers 18+ months, accuracy documented
- Phase 4: 4 weeks live data, accuracy within ±10% of backtest
- Phase 5: Trading performance tracked, risk-adjusted returns documented

### Research Quality Metrics
- All code passes security review
- All code has ≥80% test coverage
- All documentation is up-to-date
- All handoffs have acceptance criteria met

---

## Communication to Stakeholder (Bruce)

### Weekly Email Format
```
Subject: Research Progress Update - Week X

Hi Bruce,

Here's this week's progress on Predictive Coffee Cup Formation:

## Phase: [Phase Name] (Week X of Y)

## Completed This Week
- [Task 1] - Done by [Agent]
- [Task 2] - Done by [Agent]

## In Progress
- [Task 3] - Working on [Agent], ETA [date]

## Blockers/Risks
- [Risk description] - Owner: [Agent], Mitigation: [plan]

## Upcoming Deliverables
- [Deliverable] - Due [date]

## Next Review
- [Date]: [Phase completion] review meeting

Best,
Research Lead
```

### Immediate Communications
- **Critical blockers**: Immediate notification to Bruce
- **Dashboard impact**: Immediate notification with mitigation plan
- **Phase transitions**: Formal request for approval

---

## Artifact Management

### Version Control
```
research-predictive-cup/  # Git worktree
├── scripts/              # All scripts versioned
├── models/               # Model checkpoints with version numbers
│   ├── predictor_v1.pkl
│   ├── predictor_v2.pkl
│   └── predictor_final.pkl
└── output/               # Time-stamped reports
    ├── analysis_20260408.md
    ├── backtest_20260415.md
    └── validation_20260422.md
```

### Deliverable Naming Convention
```
{deliverable_type}_{phase}_{date}.{ext}

Examples:
- dataset_phase1_20260408.csv
- model_phase2_20260422.pkl
- backtest_phase3_20240429.md
```

---

## Timeline Summary

| Phase | Duration | Primary Agent | Key Milestone |
|--------|-----------|---------------|---------------|
| Phase 1: Research & Analysis | 2 weeks | Data Analyst | Dataset deliverable |
| Phase 2: Prototype Implementation | 3 weeks | ML Engineer | Working prediction model |
| Phase 3: Backtesting & Validation | 2 weeks | Backtest Validator | Accuracy metrics & go/no-go |
| Phase 4: Paper Trading | 4 weeks | Backtest Validator | Live performance validation |
| Phase 5: Limited Deployment | 8 weeks | Research Lead | Production trading |

**Total**: 19 weeks (can overlap phases to reduce to ~14 weeks)

---

## Next Action

**Research Lead (Now)**:
1. Create git worktree: `git worktree add ../research-predictive-cup -b research/predictive-cup`
2. Set up research directory structure
3. Assign Phase 1 task to Data Analyst Agent
4. Communicate project start to Bruce

**Bruce (Now)**:
1. Review and approve this project management plan
2. Provide any additional constraints or preferences
3. Approve start of Phase 1

---

*This plan is a living document and will be updated as the project evolves.*
