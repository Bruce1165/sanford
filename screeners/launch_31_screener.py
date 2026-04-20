#!/usr/bin/env python3
from __future__ import annotations
"""
3.1%启动筛选器 - 3.1% Launch Screener

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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from typing import Optional, Dict
import logging

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

# Default parameters
LIMIT_DAYS = 60  # Time range: last 60 trading days
SIGNAL_ONE_DROP_MIN = -20.0  # Signal 1: Minimum drop percentage (more lenient default)
SIGNAL_ONE_DROP_MAX = -10.0  # Signal 1: Maximum drop percentage (more lenient default)
SIGNAL_TWO_VOL_MIN = 0.20  # Signal 2: Minimum volume ratio (20%)
SIGNAL_TWO_VOL_MAX = 0.30  # Signal 2: Maximum volume ratio (30%)
SIGNAL_THREE_MA_PERIOD_MIN = 5  # Signal 3: Minimum MA period
SIGNAL_THREE_MA_PERIOD_MAX = 20  # Signal 3: Maximum MA period
SIGNAL_FOUR_VOL_RATIO = 3.0  # Signal 4: Volume expansion ratio (3x)
CONVERGENCE_PCT_THRESHOLD = 0.015  # 1.5%
CONVERGENCE_PAIRS_REQUIRED = 3  # At least 3 pairs out of 6


class Launch31Screener(BaseScreener):
    """3.1% Launch Screener - V4 Base Class Compliant Version"""

    def __init__(
        self,
        limit_days: int = LIMIT_DAYS,
        signal_one_drop_min: float = SIGNAL_ONE_DROP_MIN,
        signal_one_drop_max: float = SIGNAL_ONE_DROP_MAX,
        signal_two_vol_min: float = SIGNAL_TWO_VOL_MIN,
        signal_two_vol_max: float = SIGNAL_TWO_VOL_MAX,
        signal_four_vol_ratio: float = SIGNAL_FOUR_VOL_RATIO,
        convergence_pct_threshold: float = CONVERGENCE_PCT_THRESHOLD,
        convergence_pairs_required: int = CONVERGENCE_PAIRS_REQUIRED,
        db_path: str = "data/stock_data.db",
        enable_news: bool = False,
        enable_llm: bool = False,
        enable_progress: bool = True
    ):
        super().__init__(
            screener_name='launch_31_screener',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.signal_one_drop_min = signal_one_drop_min
        self.signal_one_drop_max = signal_one_drop_max
        self.signal_two_vol_min = signal_two_vol_min
        self.signal_two_vol_max = signal_two_vol_max
        self.signal_four_vol_ratio = signal_four_vol_ratio
        self.convergence_pct_threshold = convergence_pct_threshold
        self.convergence_pairs_required = convergence_pairs_required

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """Return parameter schema for screener"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 60,
                'min': 30,
                'max': 120,
                'display_name': 'Time Range (Trading Days)',
                'description': 'Filter signals within last N trading days',
                'group': 'Basic Settings'
            },
            'SIGNAL_ONE_DROP_MIN': {
                'type': 'float',
                'default': -20.0,
                'min': -80.0,
                'max': -5.0,
                'step': 1.0,
                'display_name': 'Signal 1 Min Drop (%)',
                'description': 'Minimum drop percentage from high (negative value)',
                'group': 'Signal 1'
            },
            'SIGNAL_ONE_DROP_MAX': {
                'type': 'float',
                'default': -10.0,
                'min': -50.0,
                'max': -2.0,
                'step': 1.0,
                'display_name': 'Signal 1 Max Drop (%)',
                'description': 'Maximum drop percentage from high (negative value)',
                'group': 'Signal 1'
            },
            'SIGNAL_TWO_VOL_MIN': {
                'type': 'float',
                'default': 0.20,
                'min': 0.10,
                'max': 0.50,
                'step': 0.05,
                'display_name': 'Signal 2 Min Volume Ratio',
                'description': 'Minimum volume ratio of max volume',
                'group': 'Signal 2'
            },
            'SIGNAL_TWO_VOL_MAX': {
                'type': 'float',
                'default': 0.30,
                'min': 0.20,
                'max': 0.80,
                'step': 0.05,
                'display_name': 'Signal 2 Max Volume Ratio',
                'description': 'Maximum volume ratio of max volume',
                'group': 'Signal 2'
            },
            'SIGNAL_FOUR_VOL_RATIO': {
                'type': 'float',
                'default': 3.0,
                'min': 2.0,
                'max': 5.0,
                'step': 0.5,
                'display_name': 'Signal 4 Volume Expansion Ratio',
                'description': 'Volume must be N times previous low volume',
                'group': 'Signal 4'
            },
            'CONVERGENCE_PCT_THRESHOLD': {
                'type': 'float',
                'default': 0.015,
                'min': 0.005,
                'max': 0.05,
                'step': 0.005,
                'display_name': 'MA Convergence Threshold (%)',
                'description': 'Percentage threshold for MA convergence',
                'group': 'Signal 3'
            },
            'CONVERGENCE_PAIRS_REQUIRED': {
                'type': 'int',
                'default': 3,
                'min': 1,
                'max': 6,
                'display_name': 'MA Convergence Pairs Required',
                'description': 'Minimum MA pairs that must converge',
                'group': 'Signal 3'
            }
        }

    def calculate_drop_pct(self, current_price: float, high_price: float) -> Optional[float]:
        """Calculate percentage drop from high"""
        if high_price <= 0:
            return None
        return ((current_price - high_price) / high_price) * 100

    def check_signal_one(self, df: pd.DataFrame, idx: int) -> Optional[Dict]:
        """
        Check Signal 1: Price drop from previous high is between -38.2% and -61.8%

        Args:
            df: Price data
            idx: Index of current day being checked

        Returns:
            Dictionary with high_price, high_price_idx, drop_pct if satisfied
            None otherwise
        """
        if idx == 0:
            return None

        # Search backwards for the most recent high point in last 60 days
        search_start = max(0, idx - self.limit_days)

        # Find the highest price in the search window
        period_highs = df.iloc[search_start:idx + 1]['high']
        if period_highs.empty:
            return None

        high_price = period_highs.max()
        high_price_idx = period_highs.idxmax() + search_start

        # Calculate drop from that high
        current_price = df.iloc[idx]['close']
        drop_pct = self.calculate_drop_pct(current_price, high_price)

        if drop_pct is None:
            return None
        # Check if drop is within range (more negative = larger drop)
        # Example: -25% is within -20% to -10%? No (-25 < -20, so too much)
        # Example: -15% is within -20% to -10%? Yes (between -20 and -10)
        if drop_pct < self.signal_one_drop_min:  # More negative than min (too much drop)
            return None
        if drop_pct > self.signal_one_drop_max:  # Less negative than max (too little drop)
            return None

        return {
            'high_price': high_price,
            'high_price_idx': high_price_idx,
            'drop_pct': drop_pct
        }

    def check_signal_two(self, df: pd.DataFrame, idx: int, high_price_idx: int) -> bool:
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
        current_volume = df.iloc[idx]['amount']

        # Calculate maximum volume in last 60 days before or including current day
        search_start = max(0, idx - self.limit_days)
        period_volumes = df.iloc[search_start:idx + 1]['amount']

        if period_volumes.empty:
            return False

        max_volume = period_volumes.max()

        vol_ratio = current_volume / max_volume if max_volume > 0 else 0

        if vol_ratio >= self.signal_two_vol_min and vol_ratio <= self.signal_two_vol_max:
            return True
        return False

    def calculate_moving_averages(self, df: pd.DataFrame, end_idx: int, ma_periods: list) -> Dict[int, Optional[float]]:
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

    def check_signal_three(self, df: pd.DataFrame, idx: int, mas: Dict[int, Optional[float]]) -> bool:
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
            if pct_diff <= self.convergence_pct_threshold:
                convergence_count += 1

        # At least required pairs should converge
        if convergence_count >= self.convergence_pairs_required:
            return True

        return False

    def check_signal_four(self, df: pd.DataFrame, idx: int, ma5: float, ma10: float, ma20: float, ma60: float) -> bool:
        """
        Check Signal 4: Price breaks out all moving averages with volume expansion

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
        prev_low_vol = None
        for i in range(idx - 1, -1, -1):
            if df.iloc[i]['low'] < df.iloc[i - 1]['low']:
                prev_low_vol = df.iloc[i]['amount']
                break

        if prev_low_vol is None or prev_low_vol <= 0:
            return False

        # Check if current volume is >= 3x of previous low volume
        if volume < prev_low_vol * self.signal_four_vol_ratio:
            return False

        return True

    def run_screening(self, trade_date: str = None):
        """
        Run screening with trade_date parameter

        This method is called by backend screeners.py
        """
        if trade_date:
            self.current_date = trade_date

        # Call base class run() method which processes all stocks
        results_raw, summary = self.run()

        # Convert ScreenResult to dict format
        results = []
        for r in results_raw:
            result = {
                'code': r.code,
                'name': r.name,
                'score': r.score,
                'reason': r.reason,
                **r.extra
            }
            results.append(result)

        return results if results else []

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """
        Screen single stock

        Screening Logic:
        1. Get stock data
        2. Search backwards for Signal 1 (price drop within range)
        3. For each Signal 1 day, check Signal 2 (volume in range)
        4. For each Signal 1 + Signal 2 day, calculate MAs and check Signal 3 (MA consolidation)
        5. For each Signal 1 + Signal 2 + Signal 3 day, check Signal 4 (breakout + volume expansion)
        6. Output result when all 4 signals are satisfied

        Args:
            code: Stock code
            name: Stock name

        Returns:
            Result dictionary if all 4 signals satisfied, otherwise None
        """
        # Get stock data
        df = self.get_stock_data(code, days=self.limit_days + 10)  # Get extra days for calculations
        if df is None or len(df) < 65:  # Need at least 60 days + buffer
            return None

        # Search backwards for Signal 1 (price drop from high)
        for i in range(len(df) - 1, 0, -1):
            # ===== Step 1: Check Signal 1 (price drop) =====
            signal_one_result = self.check_signal_one(df, i)

            if signal_one_result is None:
                continue

            # Record Signal 1 info
            high_price = signal_one_result['high_price']
            high_price_idx = signal_one_result['high_price_idx']
            drop_pct = signal_one_result['drop_pct']

            # ===== Step 2: Check Signal 2 (volume in range) =====
            if not self.check_signal_two(df, i, high_price_idx):
                continue

            # ===== Step 3: Check Signal 3 (MA consolidation) =====
            mas = self.calculate_moving_averages(df, i, [5, 10, 20, 60])

            if not self.check_signal_three(df, i, mas):
                continue

            # ===== Step 4: Check Signal 4 (breakout + volume expansion) =====
            if not self.check_signal_four(df, i, mas[5], mas[10], mas[20], mas[60]):
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
                'code': code,
                'name': name,
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

                'score': 100.0,  # All signals confirmed
                'reason': f"All 4 signals confirmed (drop: {drop_pct:.1f}%)"
            }

            return result

        return None


def main():
    """Main function for testing"""
    import argparse
    parser = argparse.ArgumentParser(description='3.1% Launch Screener')
    parser.add_argument('--date', type=str, default=None, help='Trade date (YYYY-MM-DD)')
    args = parser.parse_args()

    screener = Launch31Screener()
    if args.date:
        screener.current_date = args.date

    results_raw, summary = screener.run()

    if results_raw:
        print(f"\nFound {len(results_raw)} stocks:")
        for r in results_raw[:10]:
            print(f"  {r.code} {r.name} - {r.reason}")
    else:
        print(f"\nNo stocks found")


if __name__ == '__main__':
    main()
