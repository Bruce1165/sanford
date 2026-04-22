# Risk Register - Predictive Coffee Cup Formation

**Last Updated**: 2026-04-08

---

## Active Risks

| Risk | Probability | Impact | Owner | Mitigation | Status |
|-------|-------------|---------|--------|------------|---------|
| Model overfits historical data | High | High | ML Engineer | Out-of-sample testing, regularization, cross-validation | Monitoring |
| Data gaps in 18+ months | Medium | Medium | Data Analyst | Gap analysis, identify missing periods, alternative sources | TBD |
| Insufficient screener signals for prediction | Medium | High | Data Analyst | Analyze signal coverage, design new screeners if needed | TBD |
| Dashboard performance impact | Low | Medium | Research Lead | Isolated research DB, read-only access to production | N/A |
| False positive rate too high for trading | Medium | High | Backtest Validator | Set high confidence threshold, paper trading phase | TBD |

---

## Retired Risks

| Risk | Resolution Date | How Resolved |
|-------|-----------------|--------------|
| Dashboard interference | 2026-04-08 | Isolated workspace created, read-only access enforced |

---

## Risk Definitions

**Probability**:
- High: >50% chance of occurring
- Medium: 20-50% chance
- Low: <20% chance

**Impact**:
- High: Delays project by >2 weeks or compromises accuracy significantly
- Medium: Delays project by 1-2 weeks or requires rework
- Low: Minor delay or easily workable

**Status**:
- Monitoring: Risk is being watched, no action needed yet
- Active: Mitigation in progress
- Resolved: Risk has been addressed
- Retired: Risk no longer applicable

---

## Escalation Process

If a risk materializes:
1. Agent notifies Research Lead immediately
2. Research Lead assesses impact and updates risk register
3. Research Lead proposes mitigation options to Bruce
4. Bruce approves mitigation plan
5. Agent implements mitigation
6. Risk register updated
