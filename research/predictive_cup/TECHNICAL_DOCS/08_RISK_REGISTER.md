# Risk Register

**Last Updated**: 2026-04-09
**Status**: Active Monitoring

---

## Active Risks

| Risk ID | Risk | Probability | Impact | Owner | Mitigation | Status |
|---------|------|-------------|---------|--------|------------|---------|
| R001 | Model overfits historical data | High | High | ML Engineer | Out-of-sample testing, regularization, cross-validation | ⚠️ Monitoring |
| R002 | Insufficient screener signals for prediction | Medium | High | Data Analyst | Analyze signal coverage, design new screeners if needed | ⚠️ Monitoring |
| R003 | False positive rate too high for trading | Medium | High | Backtest Validator | Set high confidence threshold, paper trading phase | ⚠️ Monitoring |
| R004 | 7+ months data insufficient for model training | Low | Medium | Research Lead | Proceed with available data, re-evaluate after Phase 3 | ✅ Accepted |
| R005 | Dashboard performance impact | Low | Medium | Research Lead | Isolated research DB, read-only access to production | ✅ N/A |

---

## Retired Risks

| Risk ID | Risk | Resolution Date | How Resolved |
|---------|------|-----------------|--------------|
| R101 | Dashboard interference | 2026-04-08 | Isolated workspace created, read-only access enforced |
| R102 | Data gaps in 18+ months | 2026-04-09 | Historical screener data generated (1,856 runs, 7+ months available) |

---

## Risk Details

### R001: Model Overfits Historical Data

**Description**: The prediction model may learn patterns specific to the historical period that don't generalize to future market conditions.

**Probability**: High (>50%)
**Impact**: High (Delays project by >2 weeks or compromises accuracy significantly)

**Owner**: ML Engineer

**Mitigation**:
- Use out-of-sample testing (train on early data, test on recent data)
- Implement regularization (L1/L2, dropout for neural networks)
- Use cross-validation (k-fold, time-series split)
- Limit model complexity (number of features, tree depth)
- Monitor for overfitting during training (train vs. validation loss)

**Monitoring**:
- Track train vs. validation accuracy gap
- If gap > 10%, simplify model
- Use early stopping if applicable

**Contingency**:
- If overfitting persists, switch to simpler model (logistic regression vs. random forest)
- Reduce number of features
- Increase regularization strength

---

### R002: Insufficient Screener Signals for Prediction

**Description**: Existing 11 screeners may not provide enough predictive signals to accurately predict coffee cup formations.

**Probability**: Medium (20-50%)
**Impact**: High (Compromises accuracy significantly)

**Owner**: Data Analyst

**Mitigation**:
- Analyze signal coverage during Phase 1
- Identify which screeners are most predictive
- Consider temporal combinations (sequences of screeners)
- If signals insufficient, design new screeners based on insights

**Monitoring**:
- Track feature importance from Phase 2 model
- If top features have low importance, signal may be insufficient
- Analyze prediction confidence scores

**Contingency**:
- If signals insufficient, pivot to price-based features (OHLCV, technical indicators)
- Extend Phase 1 to discover additional patterns
- Consider alternative prediction approaches (unsupervised learning, anomaly detection)

---

### R003: False Positive Rate Too High for Trading

**Description**: Model may predict too many false positives (predicts cup formation that doesn't happen), leading to poor trading performance.

**Probability**: Medium (20-50%)
**Impact**: High (Compromises accuracy significantly)

**Owner**: Backtest Validator

**Mitigation**:
- Set high confidence threshold for predictions (e.g., only predict if confidence > 0.8)
- Use precision-focused evaluation metrics
- Implement paper trading phase to validate false positive rate
- Analyze false positive patterns to identify common causes

**Monitoring**:
- Track false positive rate during backtesting
- Target: FPR ≤ 30%
- If FPR > 30%, increase confidence threshold

**Contingency**:
- If FPR consistently > 30%, retrain model with focus on precision
- Add negative examples to training data
- Consider ensemble methods (combine multiple models)

---

### R004: 7+ Months Data Insufficient for Model Training

**Description**: 7+ months of historical data (currently available) may be insufficient to train a robust prediction model that generalizes well.

**Probability**: Low (<20%)
**Impact**: Medium (Delays project by 1-2 weeks or requires rework)

**Owner**: Research Lead

**Mitigation**:
- Proceed with available 7+ months of data
- Re-evaluate data sufficiency after Phase 3 backtesting
- If insufficient, extend data collection period

**Monitoring**:
- Track model performance on out-of-sample data
- If performance degrades significantly on recent data, may be insufficient

**Contingency**:
- If data insufficient, extend Phase 1 to collect more data
- Adjust success metrics for smaller dataset
- Consider transfer learning from similar patterns

**Status**: ✅ Accepted - Proceeding with 7+ months data, will re-evaluate after Phase 3

---

### R005: Dashboard Performance Impact

**Description**: Research operations (large data queries, model training) may impact dashboard performance.

**Probability**: Low (<20%)
**Impact**: Medium (Delays project by 1-2 weeks or requires rework)

**Owner**: Research Lead

**Mitigation**:
- Isolated research database (separate from production)
- Read-only access to production databases
- No background processes during market hours
- Resource limits on research operations

**Monitoring**:
- Monitor dashboard response time
- Check for slow queries in production databases
- Verify Flask process stability

**Contingency**:
- If dashboard impacted, pause research operations
- Optimize queries or reduce data volume
- Run resource-intensive operations overnight

**Status**: ✅ N/A - Isolation mechanisms in place, monitoring active

---

## Risk Definitions

### Probability Levels
- **High**: >50% chance of occurring
- **Medium**: 20-50% chance
- **Low**: <20% chance

### Impact Levels
- **High**: Delays project by >2 weeks or compromises accuracy significantly
- **Medium**: Delays project by 1-2 weeks or requires rework
- **Low**: Minor delay or easily workable

### Status Levels
- **⚠️ Monitoring**: Risk is being watched, no action needed yet
- **🔄 Active**: Mitigation in progress
- **✅ Resolved**: Risk has been addressed
- **✅ N/A**: Risk no longer applicable (mitigations in place)
- **📋 Retired**: Risk was retired (not applicable)

---

## Escalation Process

### If a Risk Materializes
1. **Agent** notifies Research Lead immediately
2. **Research Lead** assesses impact and updates risk register
3. **Research Lead** proposes mitigation options to Bruce
4. **Bruce** approves mitigation plan
5. **Agent** implements mitigation
6. **Risk register** updated with resolution

### Risk Review Schedule
- **Weekly**: Research Lead reviews active risks
- **Phase Transitions**: Full risk assessment before proceeding
- **Monthly**: Bruce reviews risk register with Research Lead

---

## Risk Trends

### High-Priority Risks (Attention Required)
- **R001: Model Overfits** - High probability, high impact
- **R002: Insufficient Signals** - Medium probability, high impact
- **R003: High False Positive Rate** - Medium probability, high impact

### Low-Priority Risks (Monitoring)
- **R004: Insufficient Data** - Low probability, medium impact (accepted)
- **R005: Dashboard Impact** - Low probability, medium impact (mitigated)

---

## Mitigation Effectiveness

### Successful Mitigations
- ✅ **R101: Dashboard Interference** - Resolved via isolation mechanisms
- ✅ **R102: Data Gaps** - Resolved via historical screener generation (1,856 runs)

### Ongoing Mitigations
- ⚠️ **R001: Model Overfitting** - Out-of-sample testing planned (Phase 3)
- ⚠️ **R002: Insufficient Signals** - Signal coverage analysis planned (Phase 1)
- ⚠️ **R003: High FPR** - Confidence threshold strategy planned (Phase 3)

---

## Risk by Phase

### Phase 1: Research & Analysis
- **R002**: Insufficient screener signals (will be analyzed)
- **R004**: Insufficient data (7+ months available, will be validated)

### Phase 2: Prototype Implementation
- **R001**: Model overfitting (will be monitored during training)

### Phase 3: Backtesting & Validation
- **R001**: Model overfitting (out-of-sample testing)
- **R003**: High false positive rate (will be measured)

### Phase 4: Paper Trading
- **R003**: High false positive rate (will be validated on live data)

### Phase 5: Limited Deployment
- **R003**: High false positive rate (trading impact)
- **R001**: Model overfitting (performance drift over time)

---

## Risk Communication

### To Bruce (Stakeholder)
- **Weekly**: Summary of active risks and mitigation status
- **Immediately**: If high-impact risk materializes
- **Phase Transitions**: Full risk assessment for go/no-go decision

### To Agents
- **Daily**: Risk awareness through project updates
- **As Needed**: Specific risk assignments and mitigation tasks
- **Weekly**: Risk register updates

---

## Lessons Learned

### From Retired Risks
1. **Data Generation**: Historical screener data generation (1,856 runs) successfully resolved data gap
2. **Isolation**: Read-only access and isolated workspace prevented dashboard interference

### To Be Applied
1. **Early Validation**: Validate data sufficiency early (Phase 1) to avoid later surprises
2. **Monitoring**: Continuous monitoring of model performance to detect overfitting early
3. **Thresholds**: Set conservative confidence thresholds to control false positive rate

---

## Risk Register Maintenance

### Update Frequency
- **Weekly**: Research Lead updates status and adds new risks
- **Phase Transitions**: Comprehensive risk review
- **As Needed**: Immediate update if new risk identified or existing risk materializes

### Archive Policy
- Risks retired for >30 days moved to ARCHIVE/
- Maintain history of all risks for lessons learned
- Annual review of risk register structure

---

## Quick Reference

### Risk Summary
- **Active Risks**: 5
- **High Priority**: 3 (R001, R002, R003)
- **Low Priority**: 2 (R004, R005)
- **Retired Risks**: 2 (R101, R102)

### Top 3 Risks to Monitor
1. **R001**: Model Overfits (High probability, high impact)
2. **R002**: Insufficient Signals (Medium probability, high impact)
3. **R003**: High FPR (Medium probability, high impact)

### Next Risk Review
- **Date**: 2026-04-16 (next week)
- **Owner**: Research Lead
- **Attendees**: All agents, Bruce

---

**Last Updated**: 2026-04-09
**Next Review**: 2026-04-16
