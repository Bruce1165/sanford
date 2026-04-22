# Project Overview - Predictive Coffee Cup Formation

## Objective

Build a predictive system that detects coffee cup pattern formation **before completion** by combining signals from the existing 11 technical analysis screeners in NeoTrade2.

---

## 🎯 Why This Project?

### Current State
- NeoTrade2 has 11 technical analysis screeners (breakout patterns, O'Neil methods, etc.)
- Screeners identify patterns **after** they form
- No predictive capability to detect patterns **before** completion

### Desired State
- Predict coffee cup formations 10+ days in advance
- Use combination of screener signals as early warning indicators
- Enable proactive trading decisions
- Improve risk-adjusted returns

---

## 📊 Project Scope

### In Scope
- Focus on **coffee cup pattern** (杯柄形态) prediction
- Use existing 11 screeners as signal sources
- Historical analysis on 18+ months of data
- Multi-agent collaborative research approach
- Isolated research workspace (no production code changes)

### Out of Scope
- Real-time trading automation (Phase 5 only)
- Pattern detection from scratch (use existing screeners)
- Multi-pattern prediction (single pattern focus)
- Production dashboard modifications

---

## 🎯 Success Metrics

### Prediction Accuracy Targets
| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Precision** | ≥ 60% | Of predicted cups, how many actually form? |
| **Recall** | ≥ 50% | Of all cups, how many are predicted? |
| **F1 Score** | ≥ 0.55 | Balance of precision and recall |
| **Lead Time** | ≥ 10 days | How early can we predict? |
| **False Positive Rate** | ≤ 30% | How many wrong predictions? |

### Trading Performance Targets (Phase 5)
- Win rate ≥ 50% on predicted trades
- Risk-adjusted returns (Sharpe ratio) documented
- Maximum drawdown controlled

---

## 🗂️ Data Sources

### Production Data (Read-Only)
- **Stock Prices**: `data/stock_data.db` - 6+ months OHLCV data (4,663 stocks)
- **Screener Results**: `data/screeners/{name}/{date}.xlsx` - Historical screener outputs

### Research Data (Writable)
- **Research Database**: `research/data/research.db` - Isolated research workspace
- **Labeled Datasets**: `research/output/analysis/` - Training/test data
- **Models**: `research/output/models/` - Trained prediction models

---

## 🤖 Approach

### Multi-Agent Collaboration
- **Research Lead**: Orchestration, stakeholder communication
- **Data Analyst**: Historical analysis, pattern identification
- **ML Engineer**: Model development, feature engineering
- **Backtest Validator**: Accuracy validation, performance metrics
- **Documentation Agent**: Maintain docs, create guides
- **Code Review Agent**: Security, quality, test coverage

### Phase-Based Execution
1. **Phase 1** (2 weeks): Research & Analysis
2. **Phase 2** (3 weeks): Prototype Implementation
3. **Phase 3** (2 weeks): Backtesting & Validation
4. **Phase 4** (4 weeks): Paper Trading
5. **Phase 5** (8 weeks): Limited Deployment

### Safety-First Design
- Isolated research workspace
- Read-only access to production data
- No dashboard code modifications
- Separate research database
- Git worktree isolation

---

## 📅 Timeline Overview

```
Week 1-2   ████████░░░░░░░░░░░░░  Phase 1: Research & Analysis
Week 3-5   ░░░░░░░░░░░░░░░░░░░░  Phase 2: Prototype Implementation
Week 6-7   ░░░░░░░░░░░░░░░░░░░░  Phase 3: Backtesting & Validation
Week 8-11  ░░░░░░░░░░░░░░░░░░░░  Phase 4: Paper Trading
Week 12-19 ░░░░░░░░░░░░░░░░░░░░  Phase 5: Limited Deployment
```

**Total Duration**: 10-18 weeks (can overlap phases to reduce to ~14 weeks)

---

## 🎓 Background Knowledge

### Coffee Cup Pattern (杯柄形态)
A bullish continuation pattern characterized by:
- **Cup**: Rounded bottom (U-shape) after a decline
- **Handle**: Small consolidation before breakout
- **Volume**: Low during formation, high on breakout
- **Duration**: Cup forms over weeks/months

### Existing Screeners in NeoTrade2
1. `coffee_cup` - Cup handle pattern (target pattern)
2. `er_ban_hui_tiao` - Two-board pullback
3. `jin_feng_huang` - Limit-up golden phoenix
4. `yin_feng_huang` - Limit-up silver phoenix
5. `shi_pan_xian` - Limit-up test line
6. `zhang_ting_bei_liang_yin` - Limit-up double volume bearish
7. `breakout_20day` - 20-day breakout
8. `breakout_main` - Main uptrend breakout
9. `daily_hot_cold` - Daily hot/cold stocks
10. `shuang_shou_ban` - Double close limit-up
11. `ashare_21` - A-share 2.1 comprehensive selection

### Hypothesis
Certain screeners trigger **before** cup formation completes, providing early signals. By analyzing temporal sequences of screener triggers, we can predict cup formations in advance.

---

## 🔑 Key Assumptions

1. **Screener Signals Precede Patterns**: Some screeners will trigger before cup formation
2. **Temporal Patterns Exist**: There are discoverable sequences of screener triggers
3. **Historical Data is Representative**: Past patterns will repeat in future
4. **Combination is Better**: Multiple screeners together provide better predictions than any single screener
5. **6+ Months Sufficient**: Available historical data (6+ months) is enough for initial model training

---

## 📈 Success Definition

### Project Success
- [ ] Prediction model achieves target metrics (Precision ≥ 60%, Recall ≥ 50%)
- [ ] Backtest validates model on 18+ months data
- [ ] Paper trading confirms accuracy matches backtest (±10%)
- [ ] Live trading demonstrates positive risk-adjusted returns

### Failure Criteria
- [ ] Cannot achieve baseline accuracy > random guessing
- [ ] Model overfits historical data (poor generalization)
- [ ] False positive rate > 30% in backtesting
- [ ] No clear temporal patterns in screener triggers

---

## 📚 Related Documents

- [Phase Plan](02_PHASE_PLAN.md) - Detailed 5-phase breakdown
- [Data Access](03_DATA_ACCESS.md) - How to access data sources
- [Safety Constraints](04_SAFETY_CONSTRAINTS.md) - What you cannot do
- [Current Status](06_CURRENT_STATUS.md) - Where we are now
- [Risk Register](08_RISK_REGISTER.md) - Active risks and mitigations

---

**Last Updated**: 2026-04-09
**Version**: v1.0
