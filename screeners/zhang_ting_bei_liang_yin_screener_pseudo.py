#!/usr/bin/env python3
"""
Zhang Ting Bei Liang Yin Screener - Pseudocode Version

Time Range: Last 14 trading days

Signal 1: A limit-up day with yang line where body length is 3x or more of lower shadow length
  - Define this day as Day T

Signal 2: On the day after Day T, stock opens high and closes as yin line,
  - Yin line body length is 2x or more of (upper shadow + lower shadow) combined length

Signal 2.5: Price Protection - After Day T, the low price of ANY trading day
  - Must NOT be lower than the open price of Day T

Signal 3: On the day after Day T (which is Signal 2 day),
  - Trading amount is 2x or more of the previous trading day (which is Day T)

Signal 4: After Day T, find a single day (define this day as Day X)
  - Trading amount is less than 0.5x of Signal 2 day's amount

Signal 5: After Day X, find a single day that:
  - Closes up (pct_change > 0)
  - Is a yang line (close > open)
  - Trading amount is 2x or more of previous day's amount
  - This day is confirmed as launch signal

Output: Stock is output when ALL 6 signals are satisfied
"""

# Parameters
LIMIT_DAYS = 14  # Time range: last 14 trading days
LIMIT_UP_THRESHOLD = 9.9  # Limit-up threshold
SIGNAL_ONE_BODY_RATIO = 3.0  # Signal 1: body/lower_shadow ratio
SIGNAL_TWO_BODY_RATIO = 2.0  # Signal 2: body/(upper+lower_shadow) ratio
SIGNAL_THREE_VOLUME_RATIO = 2.0  # Signal 3: amount ratio (signal2/signal1)
SIGNAL_FOUR_VOLUME_RATIO = 0.5  # Signal 4: amount ratio (day_x/signal2)
SIGNAL_FIVE_VOLUME_RATIO = 2.0  # Signal 5: amount ratio (launch_day/previous_day)

# ============== Helper Functions ==============

def is_limit_up(pct_change):
    """Check if it's a limit-up day (pct_change >= 9.9%)"""
    return pct_change >= LIMIT_UP_THRESHOLD

def check_price_protection(df, signal_one_idx):
    """
    Check Signal 2.5 (Price Protection): After Day T, the low price of ANY trading day
    must NOT be lower than the open price of Day T

    Args:
        df: Price data
        signal_one_idx: Index of Day T (Signal 1)

    Returns:
        True: Price protection passed (no breakdown)
        False: Price protection failed (breakdown occurred)
    """
    t_day_open = df.iloc[signal_one_idx]['open']

    # Check all trading days after Day T
    for i in range(signal_one_idx + 1, len(df)):
        if df.iloc[i]['low'] < t_day_open:
            return False  # Breakdown found, price protection failed

    return True  # No breakdown, price protection passed

# ============== Signal Check Functions ==============

def check_signal_one(df, idx):
    """
    Check Signal 1: A limit-up day with yang line where body length is 3x or more of lower shadow length

    Args:
        idx: Candidate day index

    Returns:
        True: Signal 1 satisfied
        False: Not satisfied
    """
    row = df.iloc[idx]

    # 1. Limit-up (pct_change >= 9.9%)
    if not is_limit_up(row['pct_change']):
        return False

    # 2. Yang line (close > open)
    if row['close'] <= row['open']:
        return False

    # 3. Body length is 3x or more of lower shadow length
    # Body length = close - open
    # Lower shadow length = open - low
    body_length = row['close'] - row['open']
    lower_shadow = row['open'] - row['low']

    if lower_shadow <= 0:
        return False

    if body_length < lower_shadow * SIGNAL_ONE_BODY_RATIO:
        return False

    return True


def check_signal_two(df, idx):
    """
    Check Signal 2: On the day after Day T, stock opens high and closes as yin line,
    and yin line body length is 2x or more of (upper shadow + lower shadow) combined length

    Args:
        idx: Index of Day T (Signal 1)

    Returns:
        True: Signal 2 satisfied (idx+1 day meets conditions)
        False: Not satisfied
    """
    # Day after Day T
    next_idx = idx + 1
    if next_idx >= len(df):
        return False

    row = df.iloc[next_idx]
    prev_row = df.iloc[idx]

    # 1. Open high (open > previous close)
    if row['open'] <= prev_row['close']:
        return False

    # 2. Yin line (close < open)
    if row['close'] >= row['open']:
        return False

    # 3. Yin line body length is 2x or more of (upper + lower shadow) combined length
    # Yin body length = open - close
    # Upper shadow length = high - open
    # Lower shadow length = close - low
    body_length = row['open'] - row['close']
    upper_shadow = row['high'] - row['open']
    lower_shadow = row['close'] - row['low']

    total_shadow = upper_shadow + lower_shadow

    if total_shadow <= 0:
        return False

    if body_length < total_shadow * SIGNAL_TWO_BODY_RATIO:
        return False

    return True


def check_signal_three(df, signal_one_idx):
    """
    Check Signal 3: On the day after Day T (which is Signal 2 day),
    trading amount is 2x or more of the previous trading day (which is Day T)

    Args:
        signal_one_idx: Index of Day T (Signal 1)

    Returns:
        True: Signal 3 satisfied
        False: Not satisfied
    """
    signal_two_idx = signal_one_idx + 1  # Day after Day T

    if signal_two_idx >= len(df):
        return False

    # Day T amount
    signal_one_amount = df.iloc[signal_one_idx]['amount']

    # Day after T amount
    signal_two_amount = df.iloc[signal_two_idx]['amount']

    # Signal 2 amount > Signal 1 amount * 2
    return signal_two_amount > signal_one_amount * SIGNAL_THREE_VOLUME_RATIO


def find_signal_four(df, signal_one_idx):
    """
    Find Signal 4: After Day T, find a single day (define this day as Day X)
    where trading amount is less than 0.5x of Signal 2 day's amount

    Args:
        signal_one_idx: Index of Day T (Signal 1)

    Returns:
        Index of Day X, or None if not found
    """
    signal_two_idx = signal_one_idx + 1  # Day after Day T

    if signal_two_idx >= len(df):
        return None

    # Signal 2 day amount
    signal_two_amount = df.iloc[signal_two_idx]['amount']

    # Threshold: 0.5x of Signal 2 amount
    threshold = signal_two_amount * SIGNAL_FOUR_VOLUME_RATIO

    # Start searching from day after Signal 2 (i.e., from Day T+2)
    for i in range(signal_two_idx + 1, len(df)):
        if df.iloc[i]['amount'] < threshold:
            return i  # Found Day X

    return None  # Day X not found


def find_signal_five(df, signal_four_idx):
    """
    Find Signal 5: After Day X, find a single day that closes up with yang line
    and has sequential amount 2x or more of previous day

    Args:
        signal_four_idx: Index of Day X (Signal 4)

    Returns:
        Index of launch day, or None if not found
    """
    if signal_four_idx < 0 or signal_four_idx >= len(df):
        return None

    # Start searching from day after Day X
    for i in range(signal_four_idx + 1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]

        # 1. Closes up (pct_change > 0)
        if row['pct_change'] <= 0:
            continue

        # 2. Yang line (close > open)
        if row['close'] <= row['open']:
            continue

        # 3. Sequential amount 2x or more
        # Amount > previous day amount * 2
        if row['amount'] <= prev_row['amount'] * SIGNAL_FIVE_VOLUME_RATIO:
            continue

        return i  # Found launch day

    return None  # Launch day not found

# ============== Main Screening Logic ==============

def screen_stock(df):
    """
    Screen single stock

    Screening Logic:
    1. Iterate backwards to find day satisfying Signal 1 (Day T)
    2. Check Signal 2 (day after Day T)
    3. Check Signal 3 (Signal 2 amount > Signal 1 amount * 2)
    4. Find Signal 4 (Day X: after Day T, amount < Signal 2 amount * 0.5)
    5. Find Signal 5 (Launch day: after Day X, close up + yang line + amount 2x)
    6. Check Signal 2.5 (Price Protection: after Day T, low >= Day T open)
    7. Output result when all 6 signals are satisfied

    Returns:
        Result dictionary if all signals satisfied, otherwise None
    """
    # Search backwards for Signal 1 (ensure within 14 days)
    for i in range(len(df) - 1, -1, -1):

        # ===== Step 1: Check Signal 1 (Day T) =====
        if not check_signal_one(df, i):
            continue

        signal_one_idx = i

        # Check if Signal 1 date is within 14 days
        latest_date = df.iloc[-1]['trade_date']
        signal_one_date = df.iloc[signal_one_idx]['trade_date']
        days_since = (latest_date - signal_one_date).days

        if days_since > LIMIT_DAYS:
            continue  # Outside 14-day range

        # ===== Step 2: Check Signal 2 (day after Day T) =====
        if not check_signal_two(df, signal_one_idx):
            continue

        signal_two_idx = signal_one_idx + 1

        # ===== Step 3: Check Signal 3 (Signal 2 amount > Signal 1 * 2) =====
        if not check_signal_three(df, signal_one_idx):
            continue

        # ===== Step 4: Find Signal 4 (Day X) =====
        signal_four_idx = find_signal_four(df, signal_one_idx)
        if signal_four_idx is None:
            continue

        # ===== Step 5: Find Signal 5 (Launch day) =====
        signal_five_idx = find_signal_five(df, signal_four_idx)
        if signal_five_idx is None:
            continue

        # ===== Step 6: Check Signal 2.5 (Price Protection) =====
        if not check_price_protection(df, signal_one_idx):
            continue

        # ===== Step 7: All 6 signals satisfied, output result =====
        signal_one = df.iloc[signal_one_idx]
        signal_two = df.iloc[signal_two_idx]
        signal_four = df.iloc[signal_four_idx]
        signal_five = df.iloc[signal_five_idx]

        # Calculate K-line features
        s1_body = signal_one['close'] - signal_one['open']
        s1_lower = signal_one['open'] - signal_one['low']
        s1_ratio = s1_body / s1_lower if s1_lower > 0 else 0

        s2_body = signal_two['open'] - signal_two['close']
        s2_upper = signal_two['high'] - signal_two['open']
        s2_lower = signal_two['close'] - signal_two['low']
        s2_ratio = s2_body / (s2_upper + s2_lower) if (s2_upper + s2_lower) > 0 else 0

        return {
            'signal_one_idx': signal_one_idx,
            'signal_two_idx': signal_two_idx,
            'signal_four_idx': signal_four_idx,
            'signal_five_idx': signal_five_idx,

            # Signal 1 features
            's1_date': signal_one['trade_date'],
            's1_open': signal_one['open'],
            's1_close': signal_one['close'],
            's1_low': signal_one['low'],
            's1_body_ratio': s1_ratio,
            's1_amount': signal_one['amount'],

            # Signal 2 features
            's2_date': signal_two['trade_date'],
            's2_open': signal_two['open'],
            's2_close': signal_two['close'],
            's2_high': signal_two['high'],
            's2_low': signal_two['low'],
            's2_body_ratio': s2_ratio,
            's2_amount': signal_two['amount'],

            # Signal 3: Amount ratio
            'amount_ratio_s2_s1': signal_two['amount'] / signal_one['amount'],

            # Signal 4: Day X low volume
            's4_date': signal_four['trade_date'],
            's4_amount': signal_four['amount'],
            'di_liang_ratio': signal_four['amount'] / signal_two['amount'],

            # Signal 5: Launch day
            's5_date': signal_five['trade_date'],
            's5_close': signal_five['close'],
            's5_pct_change': signal_five['pct_change'],
            's5_amount': signal_five['amount'],
            's5_amount_ratio': signal_five['amount'] / df.iloc[signal_five_idx - 1]['amount'],

            'all_signals_confirmed': True
        }

    return None  # Stock does not meet all conditions
