# 老鸭头周线 - 鸭鼻孔信号检测

## 算法设计

### 鸭鼻孔检测核心逻辑

```
Input: Weekly price data for a stock (last N weeks, typically 120)

Algorithm Steps:
1. Calculate 3 MAs: MA5, MA10, MA30 (exponential moving averages)
2. Detect MA5 > MA10 > MA30 arrangement (多头排列)
3. Find recent local high point (鸭头顶)
4. Wait for pullback with volume contraction (调整缩量)
5. Detect MA5/MA10 golden cross with small gap (金叉，空隙越小越强)
6. Confirm MA30 support (回踩30周线)
7. Return signal if all conditions met

Output:
- Signal type: "duck_nose_hole"
- Signal date: Week when golden cross occurs
- Signal price: Close price at signal week
- Confidence score: Based on gap size (smaller = higher confidence)
```

### 技术参数

```
MA Periods:
- MA5: 5-week exponential moving average (short-term)
- MA10: 10-week exponential moving average (medium-term)
- MA30: 30-week exponential moving average (long-term support)

Golden Cross Detection:
- MA5 crosses above MA10 (金叉)
- Cross occurs with pullback to MA30 (回踩)
- Gap calculation: (MA5 - MA10) at cross point

Volume Analysis:
- Volume contraction in adjustment phase (缩量)
- Volume expansion at breakout (放量)
- Compare to 5-week average volume

Support Confirmation:
- Price above MA30 at signal week
- MA30 as trend support line

Confidence Scoring:
- Gap size = |MA5 - MA10| at cross point
- Volume contraction depth
- Support distance above MA30
- Score: 0.0 - 1.0 (1.0 = strongest)
```

### 数据流

```
1. Load weekly price data (from DB: daily_prices aggregated to weekly)
2. Filter stocks by market cap (≥40亿 circulating)
3. Calculate EMAs (5,10,30 weeks)
4. Detect MA arrangement (MA5 > MA10 > MA30)
5. Find local high (last 30 weeks)
6. Identify pullback with volume contraction
7. Detect golden cross with gap
8. Validate support above MA30
9. Score and rank matches
10. Return top candidates
```

### 输出字段

```
必填字段:
- code: 股票代码
- name: 股票名称
- signal_date: 信号日期
- signal_price: 信号价格
- ma5, ma10, ma30: 三条均线值
- gap_size: 金叉时的空隙大小
- volume_ratio: 成交量相对5周均量
- confidence: 信号置信度 (0-1.0)
- reason: 信号描述

分析字段:
- recent_high: 最近高点价格
- recent_high_date: 最近高点日期
- pullback_low: 回调低点价格
- trend_strength: 趋势强度评分
```

## 入场信号类型

### 信号一：鸭鼻孔金叉（激进）

**触发条件**:
1. MA5快速金叉MA10（within 2-3 weeks of pullback）
2. 金叉时空隙较小（gap_size < threshold）
3. 回踩30周线支撑
4. 缩量调整后温和放量

**仓位建议**: 3-4成
**止损**: 30周线下方3%，或跌破金叉当周K线实体下沿

**风险级别**: 中高（金叉后的假突破风险）

### 后续信号（待实现）

### 信号二：鸭嘴金叉（稳健）
### 信号三：放量突破鸭头顶（追买）

## 伪代码

```python
# Duck Nose Hole Detection Algorithm

def calculate_emas(prices: List[float]) -> Tuple[float, float, float]:
    """Calculate exponential moving averages for MA5, MA10, MA30"""
    ma5 = ema(prices, period=5)
    ma10 = ema(prices, period=10)
    ma30 = ema(prices, period=30)
    return ma5, ma10, ma30

def detect_bull_arrangement(ma5: List[float], ma10: List[float], ma30: List[float]) -> bool:
    """Check if MA5 > MA10 > MA30 (多头排列)"""
    last_idx = -1
    for i in range(len(ma5)):
        if ma5[i] > ma10[i] > ma30[i]:
            last_idx = i
    return last_idx >= 0

def find_local_high(prices: List[float], window: int = 30) -> Tuple[float, int]:
    """Find local high point in recent window"""
    max_price = max(prices[-window:])
    max_idx = len(prices) - window + prices[-window:].index(max_price)
    return max_price, max_idx

def detect_pullback_with_volume_contraction(
    prices: List[float],
    volumes: List[float],
    ma5: List[float],
    ma10: List[float],
    ma30: List[float],
    high_idx: int
) -> Tuple[int, List[int]]:
    """
    Identify pullback phase after local high with volume contraction

    Returns:
    - pullback_start: Index where pullback starts
    - contraction_period: Indices where volume < avg_volume
    """
    # Find pullback start (price starts declining from high)
    pullback_start = None
    for i in range(high_idx, len(prices)):
        if prices[i] < prices[i-1]:  # Price declining
            pullback_start = i
            break

    if pullback_start is None:
        return None, []

    # Calculate average volume in pullback phase
    pullback_volumes = volumes[pullback_start:]
    avg_volume = sum(pullback_volumes) / len(pullback_volumes)

    # Identify contraction periods (volume < 80% of average)
    contraction_periods = []
    for i in range(pullback_start, len(volumes)):
        if volumes[i] < avg_volume * 0.8:
            contraction_periods.append(i)

    return pullback_start, contraction_periods

def detect_golden_cross_with_gap(
    ma5: List[float],
    ma10: List[float],
    ma30: List[float],
    start_idx: int,
    contraction_periods: List[int],
) -> Optional[Tuple[int, float, float]]:
    """
    Detect MA5 > MA10 golden cross with small gap during contraction

    Returns:
    - cross_idx: Index of golden cross
    - gap_size: Size of gap at cross point
    - cross_price: Price at cross point
    """
    for idx in contraction_periods:
        if idx < len(ma5) - 1 and idx < len(ma10) - 1:
            # Previous: MA5 <= MA10
            prev_ma5_le_ma10 = ma5[idx-1] <= ma10[idx-1]

            # Current: MA5 > MA10 (golden cross)
            curr_ma5_gt_ma10 = ma5[idx] > ma10[idx]

            if prev_ma5_le_ma10 and curr_ma5_gt_ma10:
                # Calculate gap size
                gap_size = ma5[idx] - ma10[idx]

                # Confirm support above MA30
                if ma30[idx] > ma10[idx]:
                    return idx, gap_size, ma10[idx]

    return None

def calculate_confidence(
    gap_size: float,
    volume_expansion: float,
    support_distance: float,
    max_gap: float = 5.0,
) -> float:
    """
    Calculate confidence score based on multiple factors

    Score 0.0 - 1.0 (1.0 = strongest signal)

    Factors:
    1. Gap size (smaller gap = higher confidence, inverse relationship)
    2. Volume expansion (greater expansion = higher confidence)
    3. Support distance above MA30 (further = higher confidence)
    """
    # Factor 1: Gap size (smaller is better, inverted)
    gap_score = 1.0 - min(gap_size / max_gap, 1.0)

    # Factor 2: Volume expansion (0-2 scale)
    vol_score = min(volume_expansion / 2.0, 1.0)

    # Factor 3: Support distance (0-2 scale)
    support_score = min(support_distance / 10.0, 1.0)

    # Weighted average (gap 40%, volume 30%, support 30%)
    confidence = (gap_score * 0.4 + vol_score * 0.3 + support_score * 0.3)

    return round(confidence, 2)

def duck_nose_hole_screen(
    stock_code: str,
    stock_name: str,
    weekly_prices: List[Dict],
    min_data_bars: int = 60
) -> Optional[Dict]:
    """
    Main screening function for duck nose hole signal

    Returns:
    - None if stock doesn't match criteria
    - Dict with signal details if match found
    """
    # Extract data
    prices = [p['close'] for p in weekly_prices]
    volumes = [p['volume'] for p in weekly_prices]
    trade_dates = [p['trade_date'] for p in weekly_prices]

    if len(prices) < min_data_bars:
        return None  # Not enough data

    # Calculate EMAs
    ma5, ma10, ma30 = calculate_emas(prices)

    # Check bull arrangement
    if not detect_bull_arrangement(ma5, ma10, ma30):
        return None  # Not in uptrend

    # Find local high
    recent_high, high_idx = find_local_high(prices, window=30)

    # Detect pullback with volume contraction
    pullback_start, contraction_periods = detect_pullback_with_volume_contraction(
        prices, volumes, ma5, ma10, ma30, high_idx
    )

    if pullback_start is None or not contraction_periods:
        return None  # No valid pullback

    # Detect golden cross with gap
    cross_result = detect_golden_cross_with_gap(
        ma5, ma10, ma30, pullback_start, contraction_periods
    )

    if cross_result is None:
        return None  # No valid golden cross

    cross_idx, gap_size, cross_price = cross_result

    # Confirm price above MA30 at cross point
    if ma30[cross_idx] <= ma10[cross_idx]:
        return None  # Not supported by MA30

    # Calculate volume expansion
    avg_volume = sum(volumes[high_idx:cross_idx]) / (cross_idx - high_idx)
    current_volume = volumes[cross_idx]
    volume_expansion = current_volume / avg_volume if avg_volume > 0 else 1.0

    # Calculate support distance
    support_distance = (ma30[cross_idx] - ma10[cross_idx]) if ma30[cross_idx] > ma10[cross_idx] else 0

    # Calculate confidence
    confidence = calculate_confidence(gap_size, volume_expansion, support_distance)

    # Get signal date and price
    signal_date = trade_dates[cross_idx]
    signal_price = prices[cross_idx]

    return {
        'signal_type': 'duck_nose_hole',
        'signal_date': signal_date,
        'signal_price': signal_price,
        'ma5': ma5[cross_idx],
        'ma10': ma10[cross_idx],
        'ma30': ma30[cross_idx],
        'gap_size': round(gap_size, 2),
        'volume_ratio': round(volume_expansion, 2),
        'confidence': confidence,
        'reason': f'鸭鼻孔金叉，空隙{gap_size:.2f}%，置信度{confidence:.2f}',
        'recent_high': recent_high,
        'recent_high_date': trade_dates[high_idx],
    }

# Data transformation utilities

def daily_to_weekly(daily_data: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily price data to weekly OHLCV
    - Open: First trading day of week
    - High: Max price in week
    - Low: Min price in week
    - Close: Last trading day of week
    - Volume: Sum of daily volumes in week
    """
    if daily_data.empty:
        return pd.DataFrame()

    # Ensure date is datetime
    daily_data = daily_data.copy()
    daily_data['trade_date'] = pd.to_datetime(daily_data['trade_date'])

    # Extract week number
    daily_data['week'] = daily_data['trade_date'].dt.isocalendar().week

    # Aggregate by week
    weekly = daily_data.groupby('week').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'amount': 'sum',
        'pct_change': 'last',
        'trade_date': 'last'
    }).reset_index()

    # Sort by week
    weekly = weekly.sort_values('week')
    return weekly

def ema(data: List[float], period: int) -> List[float]:
    """
    Calculate exponential moving average

    EMA formula: EMA_today = (Price_today × 2) + EMA_yesterday × (period - 1)
                     ---------------------------------------------------
                                        period
    """
    if len(data) < period:
        return []

    emas = []
    multiplier = 2 / (period + 1)
    emas.append(data[0])  # First EMA = first price

    for i in range(1, len(data)):
        ema_today = (data[i] * multiplier) + emas[i-1] * (period - 1) / period
        emas.append(ema_today)

    return emas
```

## 测试验证计划

### 单元测试（Unit Tests）

```
Test 1: calculate_emas()
- Input: Fixed list of prices
- Expected: Correct EMA values
- Verify: First value equals first price
- Verify: EMA smooths price changes

Test 2: detect_bull_arrangement()
- Input: MA5=[5,6,7], MA10=[4,5,6], MA30=[3,4,5]
- Case 1: All MA5 > MA10 > MA30 → True
- Case 2: MA5 not always > MA10 → False
- Case 3: MA30 not always below → False

Test 3: detect_golden_cross_with_gap()
- Input: Golden cross occurs with small gap
- Expected: Return cross index, gap size
- Verify: Cross detected at correct point
- Verify: Gap size calculated correctly
- Verify: MA30 support confirmed

Test 4: confidence calculation
- Input: gap=1.0, vol=1.5, support=5.0
- Expected: Score between 0.0-1.0
- Verify: Weighted average calculation
- Verify: No score exceeds 1.0
```

### 集成测试（Integration Test）

```
Test Case 1: Stock with clear duck nose hole
- Setup: Real stock with known pattern
- Expected: Signal detected, confidence > 0.7
- Verify: Signal date matches expected
- Verify: All MA conditions met

Test Case 2: Stock with weak signal
- Setup: Stock with partial conditions
- Expected: No signal or low confidence
- Verify: Missing conditions reject correctly

Test Case 3: Multiple stocks batch processing
- Setup: 50 stocks with varying conditions
- Expected: Correct signal detection for matching stocks
- Verify: Performance acceptable
```

## 实现检查清单

### 编码前（Pre-Coding Checklist）

- [ ] Pseudocode reviewed and approved
- [ ] Test plan written above
- [ ] Output format defined (signal_type, confidence, etc.)
- [ ] English-only code variables and comments
- [ ] BaseScreener methods understood

### 编码中（Coding Checklist）

- [ ] Backup base_screener.py before modifying
- [ ] Inherit from BaseScreener class
- [ ] Implement screen_stock() method
- [ ] Add debug logging for key algorithm steps
- [ ] Use real data for testing (no placeholders)
- [ ] Handle edge cases (not enough data, invalid input)

### 测试后（Post-Testing Checklist）

- [ ] Unit tests pass for helper functions
- [ ] Integration test with real stock data
- [ ] Signal accuracy verified (compare to visual charts)
- [ ] Performance acceptable (processes 50 stocks in < 30 seconds)
- [ ] Logs cleaned up after verification
- [ ] Backup files deleted after verification complete

---

**Created**: 2026-04-16
**Status**: Pseudocode complete - Ready for coding

'**CRITICAL DATE VALIDATION REQUIRED**:
```
在以下任一步骤中添加日期范围检查：

步骤6（金叉检测）- 信号日期范围验证：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 确保信号日期在合理范围内：│
│    - 信号日期必须 ≥ (当前目标日期 - 90天)且 ≤ 当前目标日期       │
│    - 目的：避免使用 2025 年的历史信号匹配 2026 年的股价     │
│    - 示例：如果当前日期是 2026-04-15，信号日期应在 2025-09-15 到 2026-04-15 范围内  │
│    - 如果信号日期在 2025-04-15 或更早：过滤掉此信号！      │
│    - 验证方法：signal_date >= current_date - timedelta(days=90)       │
│    - 如果信号日期在 2025-04-15 或更早：过滤掉此信号！      │
│                                                             │
└─────────────────────────────────────────────────────────────────┘
```

**原因**：
- 避免历史信号污染：V2 版本测试中发现信号日期为 2025-05-16 等（一年前），这是严重的数据时效性问题
- 提高信号时效性：选股应反映最近的技术形态，而不是历史形态
- 符合实际交易需求：投资者需要的是当前趋势信号，不是历史信号
