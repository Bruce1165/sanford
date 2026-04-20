# Strategic Decisions Log

**Purpose**: Track important strategic decisions affecting NeoTrade2 project architecture and development approach  
**Created**: 2026-04-16  
**Status**: Active - Add new strategic decisions as they're made

---

## Decision 001: Multi-Screener Architecture & Future Combination Layer

**Date**: 2026-04-16  
**Context**: Analyzing 3 PDF documents about 老鸭头周线 and 杯柄形 strategies

### Decision

**Screeners will be developed with independent testability NOW, designed for future combination layer LATER**

### Rationale

**1. Current Phase - Independent Development**
- Team needs to see quick, positive results at each step
- Each screener must be individually backtestable
- Small solid steps → immediate validation
- Modular architecture → easy to debug and maintain

**2. Future Phase - Combination Layer**
- Multiple screeners output standardized results
- Ensemble/voting layer can aggregate signals
- Cross-validation between strategies
- Confidence scoring based on historical success rates

### Implications

**Technical Requirements:**
1. All screeners inherit from `base_screener.py`
2. Consistent output format across all screeners:
   ```
   {
     "signal_type": "duck_nose" | "duck_beak" | "duck_breakout" | "cup_handle_breakout",
     "confidence": float (0-1),
     "entry_price": float,
     "stop_loss": float,
     "target_price": float,
     "timestamp": datetime,
     "screener_name": string
   }
   ```
3. Signal type and confidence tracking mandatory
4. Independent test data sets for backtesting

**Development Workflow:**
1. Create prototype for single signal (e.g., duck nose hole detection)
2. Visualize/chart the detected pattern → quick team validation
3. Add second signal → validate interaction
4. Complete screener → full backtest
5. Repeat for next screener

**Team Benefits:**
- ✅ Incremental progress visible at each step
- ✅ Fail fast if approach wrong
- ✅ Parallel development possible (different team members on different screeners)
- ✅ Historical performance comparison between strategies
- ✅ Clear foundation for combination layer later

### Trade-offs

**Pros:**
- Fast time-to-first-result (days vs weeks)
- Clear separation of concerns
- Easy to disable/enable specific strategies
- Independent backtesting and optimization

**Cons:**
- Requires orchestration layer to run multiple screeners
- More code files to maintain
- Initial implementation doesn't show combination benefits

### Dependencies

- Base screener infrastructure (`base_screener.py`) must support standardized output
- Data fetching must support both weekly and daily timeframes
- Visualization tools needed for pattern validation

---

## Strategic Decision Log Template

```
Decision XXX: [Title]

**Date**: YYYY-MM-DD
**Context**: What triggered this decision

**Decision**:
[The decision made]

**Rationale**:
1. Reason 1
2. Reason 2
...

**Implications**:
- Technical Requirement 1
- Technical Requirement 2
...

**Trade-offs**:
**Pros**:
- ✓ Pro 1
- ✓ Pro 2
...

**Cons**:
- ✗ Con 1
- ✗ Con 2
...

**Dependencies**:
- [List of requirements or assumptions]
```

---

**Last Updated**: 2026-04-16
