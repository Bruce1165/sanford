#!/usr/bin/env python3
"""
Er Ban Hui Tiao Screener - Pseudocode Version

Time Range: Last 14 trading days

Signal 1: Two consecutive limit-up boards, and:
  - First limit-up board (define this day as Day T) amount is >= previous day amount * 2
  - Second limit-up day amount < first limit-up day amount
  - Do NOT allow 3 or more consecutive limit-up boards (skip if found)

Signal 2: After the two consecutive limit-up boards from Signal 1,
  the low price of ANY trading day must NOT be lower than Day T open price

Signal 3: After the two consecutive limit-up boards from Signal 1, find a single day (define as Day X) that:
  - Closes up (close > previous day close)
  - Is a yang line (close > open)
  - Amount is maximum since Day T
  - High price is highest since Day T
  - Day X is confirmed as launch signal

Output: Stock is output when all 3 signals are satisfied
"""

# Parameters
LIMIT_DAYS = 14  # Time range: last 14 trading days
LIMIT_UP_THRESHOLD = 9.9  # Limit-up threshold
FIRST_BOARD_VOLUME_RATIO = 2.0  # Signal 1: first board amount / previous day amount ratio

# ============== Helper Functions ==============

def is_limit_up(pct_change):
    """Check if it's a limit-up day (pct_change >= 9.9%)"""
    return pct_change >= LIMIT_UP_THRESHOLD

# ============== Signal Check Functions ==============

def find_signal_one(df):
    """
    Find Signal 1: Two consecutive limit-up boards, and:
    - First board (Day T) amount >= previous day amount * 2
    - Second board amount < first board amount
    - Skip if 3 or more consecutive limit-ups found

    Args:
        df: Price data

    Returns:
        Dictionary with:
        {
            'first_idx': First board index (Day T),
            'second_idx': Second board index,
            'first_open': Day T open price,
            'first_amount': Day T amount,
            'second_amount': Second board amount
        }
        or None if not found
    """
    if len(df) < 3:  # Need at least previous day + two consecutive boards
        return None

    # Search backwards, i is first board index
    for i in range(len(df) - 2, 0, -1):

        # Check two consecutive limit-ups (i and i+1)
        first_pct = df.iloc[i]['pct_change'] or 0
        second_pct = df.iloc[i + 1]['pct_change'] or 0

        if not (is_limit_up(first_pct) and is_limit_up(second_pct)):
            continue

        # Check for 3 or more consecutive limit-ups (i+2 also limit-up)
        if i + 2 < len(df):
            third_pct = df.iloc[i + 2]['pct_change'] or 0
            if is_limit_up(third_pct):
                continue  # Skip, found 3 consecutive limit-ups

        # Check first board amount >= previous day amount * 2
        first_amount = df.iloc[i]['amount']
        prev_amount = df.iloc[i - 1]['amount']

        if prev_amount <= 0 or first_amount < prev_amount * FIRST_BOARD_VOLUME_RATIO:
            continue

        # Check second board amount < first board amount
        second_amount = df.iloc[i + 1]['amount']

        if second_amount >= first_amount:
            continue

        # All Signal 1 conditions satisfied
        return {
            'first_idx': i,
            'second_idx': i + 1,
            'first_open': df.iloc[i]['open'],
            'first_amount': first_amount,
            'second_amount': second_amount
        }

    return None  # Signal 1 not found


def check_signal_two(df, signal_one_idx):
    """
    Check Signal 2: After the two consecutive limit-up boards from Signal 1,
    the low price of ANY trading day must NOT be lower than Day T open price

    Args:
        df: Price data
        signal_one_idx: Index of Day T (first board)

    Returns:
        True: Signal 2 satisfied (price protection passed)
        False: Signal 2 failed (breakdown found)
    """
    first_open = df.iloc[signal_one_idx]['open']
    second_idx = signal_one_idx + 1

    # Check all trading days after the two consecutive limit-ups (from second_idx+1 to end)
    for i in range(second_idx + 1, len(df)):
        if df.iloc[i]['low'] < first_open:
            return False  # Breakdown found, Signal 2 failed

    return True  # No breakdown, Signal 2 passed


def find_signal_three(df, signal_one_idx):
    """
    Find Signal 3: After the two consecutive limit-up boards from Signal 1,
    find a single day (Day X) that:
    - Closes up (close > previous day close)
    - Is a yang line (close > open)
    - Amount is maximum since Day T
    - High price is highest since Day T

    Args:
        df: Price data
        signal_one_idx: Index of Day T (first board)

    Returns:
        Dictionary with:
        {
            'idx': Day X index,
            'close': Day X close price,
            'high': Day X high price,
            'amount': Day X amount
        }
        or None if not found
    """
    second_idx = signal_one_idx + 1

    # Start searching from day after the two consecutive limit-ups
    for i in range(second_idx + 1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]

        # 1. Closes up (close > previous day close)
        if row['close'] <= prev_row['close']:
            continue

        # 2. Yang line (close > open)
        if row['close'] <= row['open']:
            continue

        # 3. Amount is maximum since Day T
        # Calculate max amount from Day T to current day
        period_amounts = df.iloc[signal_one_idx:i + 1]['amount']
        max_amount_since_t = period_amounts.max()

        if row['amount'] < max_amount_since_t:
            continue

        # 4. High price is highest since Day T
        # Calculate max high from Day T to current day
        period_highs = df.iloc[signal_one_idx:i + 1]['high']
        max_high_since_t = period_highs.max()

        if row['high'] < max_high_since_t:
            continue

        # All Signal 3 conditions satisfied
        return {
            'idx': i,
            'close': row['close'],
            'high': row['high'],
            'amount': row['amount']
        }

    return None  # Signal 3 (Day X) not found

# ============== Main Screening Logic ==============

def screen_stock(df):
    """
    Screen single stock

    Screening Logic:
    1. Find Signal 1 (two consecutive limit-ups with specific amount conditions, skip 3+ limit-ups)
    2. Check Signal 2 (price protection: all days after Signal 1 have low >= Day T open)
    3. Find Signal 3 (Day X with specific conditions)
    4. Output result when all 3 signals are satisfied

    Args:
        df: Price data sorted by date

    Returns:
        Result dictionary if all signals satisfied, otherwise None
    """
    # ===== Step 1: Find Signal 1 =====
    signal_one = find_signal_one(df)
    if signal_one is None:
        return None

    signal_one_idx = signal_one['first_idx']
    signal_two_idx = signal_one['second_idx']

    # Check if Signal 1 is within 14-day range
    latest_date = df.iloc[-1]['trade_date']
    signal_one_date = df.iloc[signal_one_idx]['trade_date']
    days_since = (latest_date - signal_one_date).days

    if days_since > LIMIT_DAYS:
        return None  # Outside 14-day range

    # ===== Step 2: Check Signal 2 (Price Protection) =====
    if not check_signal_two(df, signal_one_idx):
        return None

    # ===== Step 3: Find Signal 3 (Day X) =====
    signal_three = find_signal_three(df, signal_one_idx)
    if signal_three is None:
        return None

    signal_three_idx = signal_three['idx']

    # ===== Step 4: All 3 signals satisfied, output result =====
    first_board = df.iloc[signal_one_idx]
    second_board = df.iloc[signal_two_idx]
    launch_day = df.iloc[signal_three_idx]

    # Calculate max amount and max high since Day T
    period_amounts = df.iloc[signal_one_idx:signal_three_idx + 1]['amount']
    max_amount_t = period_amounts.max()

    period_highs = df.iloc[signal_one_idx:signal_three_idx + 1]['high']
    max_high_t = period_highs.max()

    return {
        'signal_one_idx': signal_one_idx,
        'signal_two_idx': signal_two_idx,
        'signal_three_idx': signal_three_idx,

        # Signal 1 features
        't_date': first_board['trade_date'],
        't_open': first_board['open'],
        't_amount': first_board['amount'],

        # Signal 2 features
        's2_date': second_board['trade_date'],
        's2_amount': second_board['amount'],

        # Signal 3 (Day X) features
        'x_date': launch_day['trade_date'],
        'x_close': launch_day['close'],
        'x_high': launch_day['high'],
        'x_amount': launch_day['amount'],

        # Max since Day T
        'max_amount_t': max_amount_t,
        'max_high_t': max_high_t,

        # Additional metrics
        'amount_ratio_first_prev': first_board['amount'] / df.iloc[signal_one_idx - 1]['amount'],
        'days_to_launch': signal_three_idx - signal_two_idx,

        'all_signals_confirmed': True
    }
