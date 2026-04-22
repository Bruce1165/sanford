# Phase Plan - 5-Phase Execution Roadmap

## Overview

This document details the 5-phase execution plan for the Predictive Coffee Cup Formation project.

---

## Phase 1: Research & Analysis (Weeks 1-2)

### Objective
Analyze historical screener results to identify patterns and create labeled dataset for ML training.

### Owner
**Data Analyst Agent**

### Tasks

#### 1.1 Survey Screener Data
- [ ] Verify historical screener data availability (18+ months)
- [ ] Identify data gaps and missing periods
- [ ] Document screener coverage by date
- [ ] Generate data quality report

#### 1.2 Extract Coffee Cup Ground Truth
- [ ] Identify all stocks that formed coffee cup patterns
- [ ] Record formation dates and completion dates
- [ ] Label stocks: `{stock_code, cup_formed: bool, formation_date}`
- [ ] Validate ground truth labels

#### 1.3 Build Control Group Dataset
- [ ] Select stocks that did NOT form coffee cup patterns
- [ ] Match control group by market cap and industry
- [ ] Ensure balanced dataset (50% positive, 50% negative)

#### 1.4 Extract Screener Trigger Sequences
- [ ] For each labeled stock, extract screener triggers over time
- [ ] Identify temporal sequences of screeners triggered
- [ ] Record trigger dates relative to cup formation
- [ ] Calculate trigger frequencies and correlations

#### 1.5 Analyze Temporal Patterns
- [ ] Identify common sequences of screener triggers
- [ ] Calculate time gaps between triggers
- [ ] Determine which screeners are most predictive
- [ ] Visualize temporal patterns

#### 1.6 Calculate Baseline Accuracy
- [ ] Implement simple rule-based prediction (e.g., "if coffee_cup triggered, predict cup")
- [ ] Calculate baseline precision, recall, F1
- [ ] Document baseline performance as reference

#### 1.7 Generate Final Dataset
- [ ] Create labeled dataset: `{stock_code, date, cup_formed, screeners_triggered}`
- [ ] Split into train/test sets (80/20)
- [ ] Save to `output/analysis/dataset_phase1_YYYYMMDD.csv`
- [ ] Generate data dictionary and documentation

### Deliverables
- `output/analysis/dataset_phase1_YYYYMMDD.csv` - Labeled dataset
- `output/analysis/temporal_patterns_phase1_YYYYMMDD.md` - Pattern analysis
- `output/analysis/baseline_accuracy_phase1_YYYYMMDD.md` - Baseline metrics
- `output/analysis/data_quality_report_phase1_YYYYMMDD.md` - Data quality

### Success Criteria
- [ ] Dataset quality score ≥ 8/10 (coverage, accuracy, completeness)
- [ ] Baseline F1 ≥ 0.30 (better than random)
- [ ] 18+ months of data coverage
- [ ] 10,000+ labeled observations

### Gate
**Bruce approval required to proceed to Phase 2**

---

## Phase 2: Prototype Implementation (Weeks 3-5)

### Objective
Build and train a prediction model using the dataset from Phase 1.

### Owner
**ML Engineer Agent**

### Tasks

#### 2.1 Model Architecture Design
- [ ] Review Phase 1 dataset and patterns
- [ ] Choose model type (random forest, XGBoost, neural network, or rule-based)
- [ ] Design feature engineering pipeline
- [ ] Define model hyperparameters

#### 2.2 Feature Engineering
- [ ] Transform screener triggers into features
- [ ] Create temporal features (days since last trigger, trigger sequences)
- [ ] Add stock-level features (market cap, industry, volatility)
- [ ] Normalize and scale features

#### 2.3 Model Implementation
- [ ] Implement prediction model in `research/scripts/predict_cups.py`
- [ ] Implement training pipeline
- [ ] Implement prediction API (run predictions for any date)
- [ ] Add logging and error handling

#### 2.4 Model Training
- [ ] Train model on Phase 1 training set
- [ ] Perform hyperparameter tuning (grid search, random search)
- [ ] Validate on test set
- [ ] Calculate accuracy metrics

#### 2.5 Model Explainability
- [ ] Implement feature importance analysis
- [ ] Generate prediction explanations (why did we predict this stock?)
- [ ] Visualize decision boundaries
- [ ] Document model logic

#### 2.6 Benchmarking
- [ ] Compare against Phase 1 baseline
- [ ] Test alternative models
- [ ] Document performance trade-offs
- [ ] Select best model

### Deliverables
- `output/models/predictor_v1.pkl` - Trained model
- `output/models/model_architecture_phase2_YYYYMMDD.md` - Model design
- `scripts/predict_cups.py` - Prediction API
- `output/analysis/feature_importance_phase2_YYYYMMDD.md` - Feature analysis
- `output/analysis/benchmark_results_phase2_YYYYMMDD.md` - Model comparison

### Success Criteria
- [ ] Model generates predictions for any given date
- [ ] Code coverage ≥ 80%
- [ ] No security vulnerabilities
- [ ] Model outperforms baseline (F1 improvement ≥ 0.10)

### Gate
**Bruce approval required to proceed to Phase 3**

---

## Phase 3: Backtesting & Validation (Weeks 6-7)

### Objective
Validate model performance on historical data and generate accuracy metrics.

### Owner
**Backtest Validator Agent**

### Tasks

#### 3.1 Backtest Setup
- [ ] Define backtest period (18+ months)
- [ ] Set up evaluation framework
- [ ] Define success metrics (precision, recall, F1, lead time)

#### 3.2 Historical Backtesting
- [ ] Run predictions for all historical dates
- [ ] Compare predictions vs. actual cup formations
- [ ] Calculate accuracy metrics by month
- [ ] Track performance over time

#### 3.3 Market Regime Analysis
- [ ] Test performance in bull markets
- [ ] Test performance in bear markets
- [ ] Test performance in sideways markets
- [ ] Identify regime-specific patterns

#### 3.4 Failure Analysis
- [ ] Analyze false positives (predicted but didn't form)
- [ ] Analyze false negatives (formed but not predicted)
- [ ] Identify common failure modes
- [ ] Document lessons learned

#### 3.5 Lead Time Analysis
- [ ] Calculate average lead time (how early predictions occur)
- [ ] Plot lead time distribution
- [ ] Correlate lead time with prediction confidence
- [ ] Document prediction timing characteristics

#### 3.6 Performance Report
- [ ] Generate comprehensive backtest report
- [ ] Document accuracy metrics
- [ ] Visualize performance over time
- [ ] Provide go/no-go recommendation

### Deliverables
- `output/reports/backtest_phase3_YYYYMMDD.md` - Backtest report
- `output/analysis/accuracy_metrics_phase3_YYYYMMDD.csv` - Detailed metrics
- `output/analysis/failure_analysis_phase3_YYYYMMDD.md` - Failure modes
- `output/reports/go_no_go_recommendation_phase3_YYYYMMDD.md` - Phase 4 decision

### Success Criteria
- [ ] Backtest covers 18+ months
- [ ] Precision ≥ 60% OR F1 ≥ 0.55
- [ ] False positive rate ≤ 30%
- [ ] Average lead time ≥ 10 days
- [ ] Performance documented and analyzed

### Gate
**Bruce approval required to proceed to Phase 4**

---

## Phase 4: Paper Trading (Weeks 8-11)

### Objective
Validate model on live data and confirm backtest accuracy matches real performance.

### Owner
**Backtest Validator Agent**

### Tasks

#### 4.1 Deployment Preparation
- [ ] Set up daily prediction pipeline
- [ ] Integrate with existing NeoTrade2 workflow
- [ ] Configure logging and monitoring
- [ ] Test deployment on staging

#### 4.2 Daily Predictions
- [ ] Run predictions daily after market close
- [ ] Store predictions in research database
- [ ] Track prediction confidence scores
- [ ] Monitor prediction volume

#### 4.3 Live Validation
- [ ] Compare predictions vs. actual formations
- [ ] Calculate live accuracy metrics
- [ ] Track performance vs. backtest
- [ ] Identify any drift or degradation

#### 4.4 Performance Tracking
- [ ] Generate weekly performance reports
- [ ] Compare live vs. backtest accuracy
- [ ] Analyze deviations
- [ ] Document lessons learned

#### 4.5 Iteration
- [ ] If accuracy drops significantly, analyze root cause
- [ ] Retrain model if needed
- [ ] Update model version
- [ ] Document changes

### Deliverables
- 4 weeks of live prediction data
- `output/reports/paper_trading_phase4_YYYYMMDD.md` - Performance report
- `output/analysis/live_vs_backtest_phase4_YYYYMMDD.md` - Comparison analysis
- Updated model (if retrained)

### Success Criteria
- [ ] 4 weeks of live data collected
- [ ] Live accuracy matches backtest (±10%)
- [ ] Win rate ≥ 50% on predicted trades
- [ ] No critical issues identified

### Gate
**Bruce approval required to proceed to Phase 5**

---

## Phase 5: Limited Deployment (Weeks 12-19)

### Objective
Enable trading on high-confidence predictions and monitor real investment performance.

### Owner
**Research Lead**

### Tasks

#### 5.1 Trading Setup
- [ ] Define trading strategy (entry, exit, position sizing)
- [ ] Set up risk management (stop loss, position limits)
- [ ] Configure trading execution (manual or automated)
- [ ] Set up performance tracking

#### 5.2 Gradual Rollout
- [ ] Start with small position sizes (1-2 stocks)
- [ ] Scale up as confidence increases
- [ ] Monitor each trade carefully
- [ ] Document trading decisions

#### 5.3 Performance Monitoring
- [ ] Track investment returns
- [ ] Calculate risk-adjusted metrics (Sharpe, drawdown)
- [ ] Compare to benchmark
- [ ] Generate monthly performance reports

#### 5.4 Model Maintenance
- [ ] Retrain model periodically (monthly)
- [ ] Monitor for concept drift
- [ ] Update features if market conditions change
- [ ] Document model changes

#### 5.5 Final Evaluation
- [ ] Evaluate overall project success
- [ ] Document lessons learned
- [ ] Recommend next steps (scale up, retire, iterate)
- [ ] Prepare final project report

### Deliverables
- Live trading performance metrics
- `output/reports/final_evaluation_phase5_YYYYMMDD.md` - Final report
- Trading playbook and risk management rules
- Model maintenance schedule

### Success Criteria
- [ ] Trading performance tracked for 8 weeks
- [ ] Risk-adjusted returns documented
- [ ] No significant drawdowns
- [ ] Project outcomes evaluated

---

## Phase Transition Gates

### Gate Criteria Summary

| Transition | Criteria | Approval |
|-----------|----------|----------|
| Phase 1 → Phase 2 | Dataset quality ≥ 8/10, Baseline F1 ≥ 0.30 | Bruce |
| Phase 2 → Phase 3 | Model outperforms baseline, Code coverage ≥ 80% | Bruce |
| Phase 3 → Phase 4 | Precision ≥ 60% OR F1 ≥ 0.55, FP rate ≤ 30% | Bruce |
| Phase 4 → Phase 5 | 4 weeks live data, Accuracy matches backtest (±10%) | Bruce |
| Phase 5 → Complete | 8 weeks trading, Performance documented | Bruce |

---

## Timeline Summary

| Phase | Duration | Owner | Key Milestone |
|--------|-----------|-------|---------------|
| Phase 1: Research & Analysis | 2 weeks | Data Analyst | Labeled dataset deliverable |
| Phase 2: Prototype Implementation | 3 weeks | ML Engineer | Working prediction model |
| Phase 3: Backtesting & Validation | 2 weeks | Backtest Validator | Accuracy metrics & go/no-go |
| Phase 4: Paper Trading | 4 weeks | Backtest Validator | Live performance validation |
| Phase 5: Limited Deployment | 8 weeks | Research Lead | Production trading |

**Total**: 19 weeks (can overlap phases to reduce to ~14 weeks)

---

**Last Updated**: 2026-04-09
