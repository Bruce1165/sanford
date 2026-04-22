# Screener Comparison Analysis

**Date**: 2026-04-12
**Analysis Period**: September 2024 - May 26, 2025
**Purpose**: Understand why coffee cup screener found 0 formations vs. why other screeners find patterns

---

## Screener Definitions

### 1. er_ban_hui_tiao (二板回调) - Two-Board Pullback

**Core Logic**: Three-signal confirmation required

**Signal 1: Two Consecutive Limit-Up Boards (二连涨停板)**
- Two consecutive limit-up boards within 34 days
- First board pct_change ≥ 9.9%
- Second board pct_change can be negative (allowing pullback)
- First board trading amount ≥ 2x previous day's amount
- Second board trading amount < first board's amount (prevents excessive size)

**Signal 2: Pullback Protection (回调不破首板开盘价)**
- Two-board after: lowest price in 14 days ≥ first board open price
- Allows for correction/pullback while maintaining bullish trend
- 14-day window prevents old data from interfering

**Signal 3: Startup Confirmation (启动确认)**
- Single day up (pct_change > 0)
- Yang line: close > open
- Amount on T-day = maximum since first board day
- High price = maximum since T-day
- Within 14-day window

**Pattern Characteristics**:
- **Type**: Momentum/Strong trend following
- **Speed**: Fast (2-3 consecutive days)
- **Volume**: Significant volume on limit-up days
- **Risk**: High (limit-up stocks can gap down)
- **Exit**: 监控出场 (not automatic)

---

### 2. breakout_20day (20天突破) - 20-Day Breakout

**Core Logic**: Consolidation + Breakout

**Box Consolidation Criteria**:
- 横盘箱体 ≥ 7 days (default, adjustable)
- Box defined by upper/lower edges (箱体上沿/箱体下沿)

**Breakout Conditions**:
- Breakout high = max(box upper edge / 200-day MA)
- Box upper edge = max of recent 7-day highs (箱体上沿)
- 200-day MA serves as resistance reference
- Breakout day volume ≥ 1.5x of recent 5-day average
- Maximum 2.0x to prevent false breakout from volume spikes

**Stand Above Breakout**:
- Close > breakout price (confirmed, not false breakout)
- Close > open (yang line) OR big yang candle (large body)
- Optional: Sector strength check (sector strong > market)

**Monitoring/Exit Conditions**:
- Close < breakout low (跌破突破位) - stop monitoring
- Long upper shadow on breakout day (放量长上影) - profit taking signal
- High turnover on breakout day (高位高换手不涨停) - distribute profit

**Pattern Characteristics**:
- **Type**: Consolidation + Momentum
- **Speed**: Medium (7+ days consolidation, then breakout)
- **Volume**: Volume surge on breakout confirms validity
- **Risk**: Medium (false breakout possible, volume surge helps mitigate)
- **Timeframe**: 20-day lookback period

**Parameters**:
- `consolidation_days`: 7 (default, 3-21 range)
- `volume_breakout_min`: 1.5x
- `volume_breakout_max`: 2.0x
- `min_breakout_pct`: 3%
- `max_breakout_pct`: 7%
- `lookback_days`: 20
- `min_body_pct`: 2%

---

## Historical Results Comparison (Sept 2024 - May 2025)

### er_ban_hui_tiao Results

**Sample Output** (2025-05-20):
| Stock | Pattern | Details |
|-------|---------|---------|
| 420 吉林化纤 | 二板回调 | 1. 连续涨停 (2025-05-15, 2025-05-16) |
| 565 三峡水利 | 二板回调 | 1. 连续涨停 (2025-05-06, 2025-05-07) |

**Stocks Found**: 57 stocks

**Pattern Focus**: Strong, fast momentum moves

### breakout_20day Results

**Sample Output** (2025-05-26):
| Stock | Pattern | Details |
|-------|---------|---------|
| 600 建投能源 | 突破 | 7天横盘后突破，放量1.71x |

**Stocks Found**: 9 stocks

**Pattern Focus**: Consolidation patterns followed by breakout

---

## Key Differences: Why They Find Stocks, Coffee Cup Doesn't

### 1. Pattern Type Difference

| Aspect | Coffee Cup | er_ban_hui_tiao | breakout_20day |
|---------|-----------|-----------------|----------------|
| **Timeframe** | 60-250 days (2-5 months) | 14 days | 7 days |
| **Formation Speed** | Slow (gradual) | Fast (2-3 days) | Medium (7 days) |
| **Price Action** | U-shaped formation | Rapid upward moves | Sideways then breakout |
| **Volume Pattern** | Low volume during handle | High volume on limit-up | Volume surge on breakout |

### 2. Market Condition Requirements

| Screener | Bullish Requirement | Trend Requirement |
|---------|------------------|-------------------|----------------|
| Coffee Cup | MA50 > MA150 > MA200 (uptrend) | MA200 must be rising | 7 months of data |
| er_ban_hui_tiao | None (any 2-day pct_change) | None (allows pullback) | 34 days |
| breakout_20day | None | Close > open (yang line) | 7 days |

### 3. Sept 2024 - May 2025 Context

**Market Conditions**: Unknown without deeper analysis, but based on limited data (Sept 2024 - May 2025 only).

**Why Coffee Cup Found 0**:
1. **Timeframe too long**: 60-250 days is a very long pattern. Market may not have had stable 7+ month formations
2. **Strict criteria**: Cup depth 20-50%, U-shape 30-70%, handle volume < 85%, MA alignment, RS score ≥ 85 is very restrictive
3. **Market volatility**: The period may have been too volatile (not conducive to smooth cup formations)
4. **Price data limitation**: Only ~9 months available vs. 7 months minimum required

**Why Other Screeners Found Patterns**:
1. **Shorter timeframe**: 7-14 days is more achievable in volatile market
2. **Pattern simplicity**: Momentum and breakout are simpler patterns that occur frequently
3. **No formation requirement**: They identify signal points (limit-up, breakout) not complex formations
4. **Flexible criteria**: er_ban_hui_tiao has no MA trend requirement; breakout_20day requires minimal body candle (2%)

---

## Why Zero Coffee Cup Formations: Root Cause Analysis

### Primary Cause: Pattern Definition Mismatch

The O'Neil CANSLIM coffee cup criteria as implemented is designed for:
- **Long-term stable uptrends** (7+ months, MA50 > MA150 > MA200)
- **Smooth price action** (gradual formation, not volatile)
- **Specific volume patterns** (low volume in handle, controlled breakout)

**Market Reality (Sept 2024 - May 2025)**:
- Likely volatile or sideways (not smooth uptrend)
- Fast, sharp moves instead of gradual formations
- Less predictable, more chaotic

**Other Screeners Succeed Because**:
- They target the **market reality** of this period
- er_ban_hui_tiao: Finds sharp momentum moves that actually occurred
- breakout_20day: Finds consolidation + breakout that actually occurred
- They don't require perfect uptrends or smooth formations

---

## Recommendations

### For Coffee Cup Screener

**Option A: Relax Criteria for Volatile Markets**
```python
# Suggested adjustments for Chinese A-share market
CUP_PERIOD_MIN = 30        # From 60 (shorter timeframe)
CUP_DEPTH_MIN = 0.15     # From 20% (shallower cups)
HANDLE_VOLUME_RATIO = 0.95     # From 85% (less strict)
# Remove or relax:
# - U-shape 30-70% → 20-80% (allow more cup shapes)
# - MA200 rising requirement → Optional for weak trends
# - RS score ≥ 85 → ≥ 75 for emerging markets
```

**Option B: Market Regime Detection**
- Implement market trend detection before applying coffee cup criteria
- Skip coffee cup search in downtrending or highly volatile periods
- Only search in neutral to moderately bullish conditions

**Option C: Use Alternative Target Patterns**
- Target patterns that actually occur in the market
- Examples: 20-day breakout, two-board momentum
- These have proven ground truth (results exist)

### For Algorithm Verification

**Recommended Approach**:
1. **Use alternative target**: Use `er_ban_hui_tiao` or `breakout_20day` results as ground truth
2. **Correlation analysis**: Analyze which OTHER screeners trigger BEFORE these patterns form
3. **Lead time calculation**: Determine how early screeners fire relative to target pattern formation
4. **Feature engineering**: Extract temporal sequences, trigger density, screener co-occurrence

**Data Available**:
- `er_ban_hui_tiao`: 161 files (Sept 2024 - May 2025)
- `breakout_20day`: 143 files (Sept 2024 - May 2025)
- Both: ~300 screener runs across 8+ months

**Next Steps**:
1. Load all er_ban_hui_tiao and breakout_20day results for Sept 2024 - May 2025
2. Label stocks by whether they appeared in either screener (positive cases)
3. Analyze screener triggers BEFORE positive cases
4. Identify lead times: how early did screeners fire?
5. Build feature matrix and train prediction model

---

## Summary

**Finding**: Coffee cup pattern (as currently defined) is **not compatible** with Chinese A-share market dynamics in Sept 2024 - May 2025 period.

**Evidence**:
- Coffee cup screener: 0 formations found (strict criteria don't match market reality)
- er_ban_hui_tiao: 57 formations found (matches sharp momentum moves)
- breakout_20day: 9 formations found (matches consolidation + breakout)

**Recommendation**: Use `er_ban_hui_tiao` or `breakout_20day` as ground truth target. Their patterns actually occurred and provide meaningful ground truth for training predictive algorithms.

---

**Last Updated**: 2026-04-12
