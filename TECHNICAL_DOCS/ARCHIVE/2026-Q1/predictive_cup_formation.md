# Predictive Coffee Cup Formation: Using Multi-Screener Signals

## Overview

This document proposes a paradigm shift in NeoTrade: **predicting coffee cup pattern formation** by combining signals from the existing 11 screeners, rather than merely detecting completed patterns.

## The Break Point

### Current Approach: Reactive Detection
- Screeners detect **completed** patterns
- Coffee cup screener identifies stocks that have already formed a full cup pattern
- Trading occurs **after** pattern formation
- Entry point: Post-breakout or near completion

### Proposed Approach: Predictive Detection
- Combine multiple screeners to detect **forming** patterns
- Predict when a stock is **in the process** of building a coffee cup
- Trading occurs **during** pattern formation
- Entry point: Early in formation, before completion

## Why This Matters

### Investment Impact
- **Earlier entry**: Better prices, larger profit potential
- **Position sizing**: Anticipate moves and size appropriately
- **Complete capture**: Ride the entire move from formation through breakout
- **Competitive advantage**: Most traders only see completed patterns

### System Architecture Impact
- Leverages existing 11 screeners as baseline
- **Extensible**: Can add new screeners if needed for better prediction
- Creates higher-level "meta-screener" that composes existing signals
- Moves from **detection** to **prediction** paradigm

## Coffee Cup Pattern Structure

A complete coffee cup pattern has these phases:

```
Phase 1: Prior Uptrend
- Strong upward movement
- Volume confirmation
- Establishes the "left rim" of the cup

Phase 2: Rounded Consolidation
- Gradual pullback from highs
- U-shaped bottom formation
- Volume drying up during bottom
- Forms the "bowl" of the cup

Phase 3: Right Side Recovery
- Gradual climb back toward left rim
- Volume expansion on up moves
- Tests the "right rim"

Phase 4: Handle Formation
- Shallow pullback (typically 10-15%)
- Low volume
- Consolidation for 3-5 weeks
- Forms the "handle"

Phase 5: Breakout
- Volume surge
- Price breaks above handle and right rim
- Confirms the pattern
```

## Hypothesis: Screener Correlation with Cup Phases

Each of the 11 screeners may detect **sub-components** of cup formation:

### During Phase 1 (Prior Uptrend)
- **20-day breakout screener**: Detects the strong upward movement
- **Main uptrend breakout screener**: Confirms trend strength
- **Volume patterns**: High volume on up moves

### During Phase 2 (Rounded Consolidation)
- **Limit-up double volume bearish screener**: May detect failed breakout attempts
- **Two-board pullback screener**: Detects the gradual pullback
- **Volume contraction**: Decreasing activity during consolidation

### During Phase 3 (Right Side Recovery)
- **20-day breakout screener**: May trigger on partial recoveries
- **Volume patterns**: Increasing volume on up moves
- **Daily hot/cold screener**: May flag stock as "hot" during recovery

### During Phase 4 (Handle Formation)
- **Two-board pullback screener**: Detects the shallow handle pullback
- **Low volume patterns**: Confirming the handle
- **Time-based patterns**: 3-5 week consolidation

### During Phase 5 (Breakout)
- **Coffee cup screener**: Detects the completed pattern
- **20-day breakout screener**: Confirms the breakout
- **Limit-up patterns**: Possible initial surge

## Potential Approaches for Prediction

### 1. Temporal Sequence Analysis
Monitor the **order** in which screeners trigger:
```
Sequence for forming cup:
1. Uptrend screeners fire (breakout, main trend)
2. Pullback screeners fire (two-board, limit-up bearish)
3. Recovery screeners fire (breakout again, volume increase)
4. Handle screeners fire (shallow pullback, low volume)
5. Coffee cup screener fires (pattern complete)
```

**Prediction trigger:** When phases 1-3 complete, predict phase 4 is forming

### 2. Signal Aggregation Scoring
Create a composite score based on which screeners have triggered:
```
Score = (Uptrend signals × w1) + (Consolidation signals × w2) + (Recovery signals × w3) + (Handle signals × w4)

If Score > threshold AND signals appear in correct sequence → Predict cup forming
```

### 3. Machine Learning Pattern Recognition
Train on historical data:
- **Positive examples**: Stocks that successfully formed cups
- **Negative examples**: Stocks with similar screener patterns that didn't form cups
- **Features**: Which screeners triggered, when, and in what order
- **Output**: Probability of cup formation in progress

### 4. State Machine Approach
Model cup formation as a state machine:
```
State 0: No signals
State 1: Uptrend detected (breakout screeners active)
State 2: Consolidation started (pullback screeners active)
State 3: Recovery in progress (breakout screeners active again)
State 4: Handle forming (shallow pullback, low volume)
State 5: Cup completed (coffee cup screener active)

Prediction: States 1-4 indicate cup formation in progress
```

## Technical Implementation

### Data Requirements
- Historical screener results (already in `data/screeners/{name}/{date}.xlsx`)
- Timing of screener triggers (timestamps from `screener_runs` table)
- Stock price/volume data (already in `stock_data.db`)
- **18+ months of historical data** available for backtesting and validation

### Screener Requirements
- **Current screeners**: 11 existing screeners provide baseline signals
- **Additional screeners**: May create new screeners if current ones are insufficient for accurate prediction
- **Flexible architecture**: System supports adding new signal detectors without major refactoring

### New Components Needed
1. **Pattern Prediction Engine**: Combines screener signals
2. **Signal Correlation Analyzer**: Identifies relationships between screeners
3. **Temporal Sequence Tracker**: Monitors order of screener triggers
4. **Prediction Confidence Scorer**: Calculates probability of cup formation

### Integration Points
- **Backend**: Add prediction endpoints to `app.py`
- **Database**: Store predictions in new table (`cup_predictions`)
- **Frontend**: Display forming cups differently from completed cups
- **Monitoring**: Track prediction accuracy over time

## Validation Strategy

### Phase 1: Backtesting
- Run prediction engine on **18+ months of historical data** (not just 6 months)
- Compare predictions against actual cup formations
- Calculate precision, recall, and F1 score
- Test across different market conditions and time periods
- Identify any market regime dependencies

### Phase 2: Paper Trading
- Run predictions live but don't trade
- Track accuracy of predictions
- Refine model parameters

### Phase 3: Limited Deployment
- Trade on high-confidence predictions only
- Monitor performance
- Gradually increase as confidence grows

## Success Metrics

### Prediction Accuracy
- **Precision**: Of stocks predicted to form cups, how many actually do?
- **Recall**: Of all cups that formed, how many were predicted?
- **F1 Score**: Balance of precision and recall
- **Lead Time**: How many days before cup completion is prediction made?

### Investment Performance
- **Entry Price Improvement**: Average price difference vs. post-breakout entry
- **Profit Per Trade**: Performance of trades based on predictions
- **Win Rate**: Percentage of predicted cups that are profitable
- **Risk-Adjusted Returns**: Sharpe ratio, max drawdown

### System Performance
- **False Positive Rate**: How often do we predict cups that don't form?
- **False Negative Rate**: How many forming cups do we miss?
- **Prediction Latency**: Time to generate predictions for 4,663 stocks

## Additional Screener Design Considerations

If analysis of historical data reveals that the current 11 screeners are insufficient for accurate cup prediction, we may need to design new screeners specifically targeting:

### Missing Signal Types
1. **Volume Divergence Screener**: Detect when price consolidates but volume decreases (classic cup bottom)
2. **Shape-Based Screener**: Directly detect U-shaped price action using curve fitting
3. **Time-Based Pattern Screener**: Identify consolidation periods lasting 3-6 months (typical cup duration)
4. **Resistance Test Screener**: Detect when price approaches but respects resistance levels
5. **Handle Formation Screener**: Specifically identify shallow pullbacks after right-side recovery
6. **Trend Strength Screener**: Measure the strength of prior uptrend vs. cup depth ratio
7. **Relative Volume Screener**: Compare volume during different cup phases

### Screener Integration Principles
- New screeners follow the same inheritance pattern from `base_screener.py`
- Results stored in same format (`data/screeners/{name}/{date}.xlsx`)
- Automatically included in prediction engine's signal set
- Can be backtested independently before integration

### Screener Development Process
1. Identify missing signal from backtesting analysis
2. Design screener logic to capture that signal
3. Implement using `base_screener.py` pattern
4. Backtest screener independently to verify signal quality
5. Integrate into prediction engine's feature set
6. Retrain prediction model with new features

## Risk Considerations

### False Positives
- Predicting cup formation when none occurs
- Result: Entering trades on stocks that don't complete the pattern
- Mitigation: High confidence thresholds, paper trading phase

### False Negatives
- Missing forming cups that should have been predicted
- Result: Missing opportunities
- Mitigation: Continuous model improvement, diverse training data

### Overfitting
- Model works on historical data but fails on new data
- Result: Degraded performance over time
- Mitigation: Out-of-sample testing, regular model retraining

### Market Regime Changes
- Market conditions that invalidate pattern relationships
- Result: Predictions become unreliable
- Mitigation: Regime detection, adaptive thresholds

## Next Steps

### Phase 1: Research & Analysis (1-2 weeks)
- [ ] Analyze historical screener results for cup-forming stocks
- [ ] Identify which screeners triggered during cup formation phases
- [ ] Determine temporal sequences of screener triggers
- [ ] Calculate baseline accuracy for simple rule-based approaches

### Phase 2: Prototype Implementation (2-3 weeks)
- [ ] Implement signal aggregation scoring model
- [ ] Create state machine for cup formation tracking
- [ ] Build prediction engine prototype
- [ ] Add backend API endpoints

### Phase 3: Backtesting & Validation (1-2 weeks)
- [ ] Run predictions on **18+ months of historical data**
- [ ] Calculate accuracy metrics (precision, recall, F1)
- [ ] Analyze failed predictions (false positives/negatives)
- [ ] Assess model performance across different market regimes
- [ ] If current screeners insufficient, **design and implement additional screeners**
- [ ] Refine model parameters and feature set

### Phase 4: Paper Trading (2-4 weeks)
- [ ] Deploy predictions in production mode
- [ ] Track accuracy on live data
- [ ] Compare predicted vs. actual cup formations
- [ ] Iterate on model based on results

### Phase 5: Limited Deployment (4-8 weeks)
- [ ] Enable trading on high-confidence predictions (e.g., >80% probability)
- [ ] Monitor investment performance
- [ ] Track prediction accuracy vs. paper trading
- [ ] Scale up gradually as confidence increases

## Conclusion

This predictive approach represents a fundamental shift from **detecting** completed patterns to **anticipating** pattern formation. If successful, it provides:

- Significant competitive advantage in timing
- Better entry prices and larger profit potential
- Deeper understanding of market dynamics through screener correlations
- Foundation for predicting other patterns beyond coffee cups

The key insight is that your existing 11 screeners are already detecting the **building blocks** of cup formation. The opportunity is in recognizing how those building blocks fit together **before** the cup is complete.

If the current 11 screeners prove insufficient for accurate prediction, the system architecture supports adding new specialized screeners to capture additional signals that improve prediction performance.
