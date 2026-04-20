#!/usr/bin/env python3
"""
3.1% Launch Screener - Pseudocode Version

Time Range: Last 60 trading days

Core Logic (all 4 signals must be satisfied):

Signal 1: Price drop from previous high is between -38.2% and -61.8%
  - Find the most recent high point in the past 60 days
  - Calculate percentage drop from that high
  - Current price drop must be within the range: -38.2% to -61.8%

Signal 2: Volume is between 20% and 30% of the maximum volume
  - Calculate maximum volume in the past 60 days
  - Current day volume must be between 20% and 30% of max volume

Signal 3: 5-day, 10-day, 20-day, 60-day moving averages form consolidation in the past 5-20 trading days
  - Check if 5MA, 10MA, 20MA, 60MA are converging
  - Convergence means: MA values are close to each other (within small percentage range)

Signal 4: Price breaks out all moving averages with volume expansion
  - Current price > all 4 moving averages (5MA, 10MA, 20MA, 60MA)
  - Current volume > 3x of the previous low point volume

Output: Stock is output when all 4 signals are satisfied
"""

# Parameters
LIMIT_DAYS = 60  # Time range: last 60 trading days
SIGNAL_ONE_DROP_MIN = -61.8  # Signal 1: Minimum drop percentage
SIGNAL_ONE_DROP_MAX = -38.2  # Signal 1: Maximum drop percentage
SIGNAL_TWO_VOL_MIN = 0.20  # Signal 2: Minimum volume ratio (20%)
SIGNAL_TWO_VOL_MAX = 0.30  # Signal 2: Maximum volume ratio (30%)
SIGNAL_THREE_MA_PERIOD_MIN = 5  # Signal 3: Minimum MA period
SIGNAL_THREE_MA_PERIOD_MAX = 20  # Signal 3: Maximum MA period
SIGNAL_FOUR_VOL_RATIO = 3.0  # Signal 4: Volume expansion ratio (3x)

# ============== Helper Functions ==============

def calculate_drop_pct(current_price, high_price):
    """
    Calculate percentage drop from high

    Args:
        current_price: Current price
        high_price: Previous high price

    Returns:
        Drop percentage as negative number (-38.2 means -38.2%)
    """
    if high_price <= 0:
        return None
    return ((current_price - high_price) / high_price) * 100

def check_signal_one(df, idx):
    """
    Check Signal 1: Price drop from previous high is between -38.2% and -61.8%

    Args:
        df: Price data
        idx: Index of current day being checked

    Returns:
        True: Signal 1 satisfied
        False: Signal 1 not satisfied
        Dictionary with high_price and drop_pct if satisfied
        None: If previous high not found
    """
    # Need at least 1 day before to have a previous high
    if idx == 0:
        return None

    # Search backwards for the most recent high point in last 60 days (including current day)
    search_start = max(0, idx - LIMIT_DAYS)

    # Find the highest price in the search window
    period_highs = df.iloc[search_start:idx + 1]['high']
    if period_highs.empty:
        return None

    high_price = period_highs.max()
    high_price_idx = period_highs.idxmax() + search_start

    # Calculate drop from that high
    current_price = df.iloc[idx]['close']
    drop_pct = calculate_drop_pct(current_price, high_price)

    # Check if drop is within range -38.2% to -61.8%
    if drop_pct is None:
        return False
    if drop_pct < SIGNAL_ONE_DROP_MIN or drop_pct > SIGNAL_ONE_DROP_MAX:
        return False

    # All conditions satisfied
    return {
        'satisfied': True,
        'high_price': high_price,
        'high_price_idx': high_price_idx,
        'drop_pct': drop_pct
    }

def check_signal_two(df, idx, high_price_idx):
    """
    Check Signal 2: Volume is between 20% and 30% of the maximum volume

    Args:
        df: Price data
        idx: Index of current day being checked
        high_price_idx: Index of the high price (from Signal 1)

    Returns:
        True: Signal 2 satisfied
        False: Signal 2 not satisfied
    """
    # Get current day volume
    current_volume = df.iloc[idx]['amount']

    # Calculate maximum volume in last 60 days before or including current day
    search_start = max(0, idx - LIMIT_DAYS)
    period_volumes = df.iloc[search_start:idx + 1]['amount']

    if period_volumes.empty:
        return False

    max_volume = period_volumes.max()

    # Check if current volume is between 20% and 30% of max volume
    vol_ratio = current_volume / max_volume if max_volume > 0 else 0

    if vol_ratio >= SIGNAL_TWO_VOL_MIN and vol_ratio <= SIGNAL_TWO_VOL_MAX:
        return True
    return False

def calculate_moving_averages(df, end_idx, ma_periods):
    """
    Calculate 5, 10, 20, 60 day moving averages up to end_idx

    Args:
        df: Price data
        end_idx: Index to calculate MAs up to (exclusive)
        ma_periods: List of MA periods [5, 10, 20, 60]

    Returns:
        Dictionary with MA values for each period
    """
    mas = {}

    # Need at least ma_periods[-1] days to calculate
    min_required_days = ma_periods[-1]
    start_idx = max(0, end_idx - min_required_days)

    if start_idx >= end_idx:
        return mas

    for period in ma_periods:
        if end_idx - start_idx < period:
            mas[period] = None
            continue

        period_data = df.iloc[start_idx:end_idx]['close']
        if len(period_data) > 0:
            ma = period_data.mean()
        else:
            ma = None

        mas[period] = ma

    return mas

def check_signal_three(df, idx, mas):
    """
    Check Signal 3: 5MA, 10MA, 20MA, 60MA form consolidation in past 5-20 days

    Args:
        df: Price data
        idx: Index of current day being checked
        mas: Dictionary with MA values {5: ma5, 10: ma10, 20: ma20, 60: ma60}

    Returns:
        True: Signal 3 satisfied
        False: Signal 3 not satisfied
    """
    # Check if all MAs are available
    if mas[5] is None or mas[10] is None or mas[20] is None or mas[60] is None:
        return False

    ma5 = mas[5]
    ma10 = mas[10]
    ma20 = mas[20]
    ma60 = mas[60]

    # Check consolidation: MA values should be close to each other
    # Define convergence threshold (e.g., within 1.5% of each other)
    convergence_pct_threshold = 0.015  # 1.5%

    # Check if 5MA, 10MA, 20MA, 60MA are converging
    pairs = [
        (ma5, ma10),
        (ma5, ma20),
        (ma5, ma60),
        (ma10, ma20),
        (ma10, ma60),
        (ma20, ma60)
    ]

    convergence_count = 0
    for ma1, ma2 in pairs:
        if ma1 is None or ma2 is None:
            continue
        pct_diff = abs(ma1 - ma2) / ma1 if ma1 > 0 else 1
        if pct_diff <= convergence_pct_threshold:
            convergence_count += 1

    # At least 3 pairs should converge (out of 6)
    if convergence_count >= 3:
        return True

    return False

def check_signal_four(df, idx, ma5, ma10, ma20, ma60):
    """
    Check Signal 4: Price breaks out all 4 moving averages with volume expansion

    Args:
        df: Price data
        idx: Index of current day being checked
        ma5: 5-day moving average
        ma10: 10-day moving average
        ma20: 20-day moving average
        ma60: 60-day moving average

    Returns:
        True: Signal 4 satisfied
        False: Signal 4 not satisfied
    """
    row = df.iloc[idx]
    close = row['close']
    volume = row['amount']

    # Condition 1: Price > all 4 moving averages
    if close <= ma5 or close <= ma10 or close <= ma20 or close <= ma60:
        return False

    # Condition 2: Volume expansion to 3x of previous low point
    # Find the previous low point volume
    # Search backwards for a low point before current day
    prev_low_vol = None
    for i in range(idx - 1, -1, -1):
        if df.iloc[i]['low'] < df.iloc[i - 1]['low']:
            # Found a local low point
            prev_low_vol = df.iloc[i]['amount']
            break

    if prev_low_vol is None or prev_low_vol <= 0:
        return False

    # Check if current volume is >= 3x of previous low volume
    if volume < prev_low_vol * SIGNAL_FOUR_VOL_RATIO:
        return False

    # All conditions satisfied
    return True

# ============== Main Screening Logic ==============

def screen_stock(df):
    """
    Screen single stock

    Screening Logic:
    1. Search backwards for Signal 1 (price drop within range)
    2. For each Signal 1 day, check Signal 2 (volume in range)
  3. For each Signal 1 + Signal 2 day, calculate MAs and check Signal 3 (MA consolidation)
  4. For each Signal 1 + Signal 2 + Signal 3 day, check Signal 4 (breakout + volume expansion)
    5. Output result when all 4 signals are satisfied

    Args:
        df: Price data sorted by date (ascending)

    Returns:
        Result dictionary if all 4 signals satisfied, otherwise None
    """
    results = []

    # Search backwards for Signal 1 (price drop from high)
    # Start from idx - 1 to ensure we have previous day data
    for i in range(len(df) - 1, 0, -1):
        # ===== Step 1: Check Signal 1 (price drop) =====
        signal_one_result = check_signal_one(df, i)

        if signal_one_result is None or not signal_one_result['satisfied']:
            continue

        # Record Signal 1 info
        high_price = signal_one_result['high_price']
        high_price_idx = signal_one_result['high_price_idx']
        drop_pct = signal_one_result['drop_pct']

        # ===== Step 2: Check Signal 2 (volume in range) =====
        if not check_signal_two(df, i, high_price_idx):
            continue

        # ===== Step 3: Check Signal 3 (MA consolidation) =====
        # Calculate MAs up to current day (excluding current day for consolidation check)
        mas = calculate_moving_averages(df, i, [5, 10, 20, 60])

        if not check_signal_three(df, i, mas):
            continue

        # ===== Step 4: Check Signal 4 (breakout + volume expansion) =====
        if not check_signal_four(df, i, mas[5], mas[10], mas[20], mas[60]):
            continue

        # ===== All 4 signals satisfied, output result =====
        row = df.iloc[i]

        # Find previous low point volume for output
        prev_low_vol = None
        for j in range(i - 1, -1, -1):
            if df.iloc[j]['low'] < df.iloc[j - 1]['low']:
                prev_low_vol = df.iloc[j]['amount']
                break

        # Calculate max volume since high price day for reference
        period_start = max(0, high_price_idx)
        period_end = i + 1  # exclusive
        max_vol_since_high = df.iloc[period_start:period_end]['amount'].max() if period_end > period_start else 0

        result = {
            'code': df.iloc[i]['code'],
            'name': df.iloc[i]['name'],
            'signal_date': df.iloc[i]['trade_date'].strftime('%Y-%m-%d'),

            # Signal 1 features
            'high_price': round(high_price, 2),
            'high_price_date': df.iloc[high_price_idx]['trade_date'].strftime('%Y-%m-%d'),
            'current_price': round(row['close'], 2),
            'drop_pct': round(drop_pct, 2),

            # Signal 2 features
            'amount': round(row['amount'] / 10000, 2),  # in 10k yuan
            'vol_ratio_max': round(max_vol_since_high / 10000, 2),  # in 10k yuan
            'vol_ratio': round(row['amount'] / max_vol_since_high, 2) if max_vol_since_high > 0 else 0,

            # Signal 3 features
            'ma5': round(mas[5], 2) if mas[5] is not None else None,
            'ma10': round(mas[10], 2) if mas[10] is not None else None,
            'ma20': round(mas[20], 2) if mas[20] is not None else None,
            'ma60': round(mas[60], 2) if mas[60] is not None else None,

            # Signal 4 features
            'close': round(row['close'], 2),
            'low': round(row['low'], 2),
            'volume_10k': round(row['amount'] / 10000, 2),  # in 10k yuan
            'prev_low_vol_10k': round(prev_low_vol / 10000, 2) if prev_low_vol is not None else 0,
            'vol_expansion_ratio': round(row['amount'] / prev_low_vol, 2) if prev_low_vol > 0 else 0,

            'all_signals_confirmed': True
        }

        results.append(result)

    # Return all found results (there could be multiple matches per stock)
    return results if results else None
