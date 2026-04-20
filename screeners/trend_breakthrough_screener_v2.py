#!/usr/bin/env python3
"""
Trend Breakthrough Screener V2 - 趋势跟踪突破买入策略

Based on Pascal strategy with dual EMA system:
- Short-term EMA (N1=10): E1
- Mid-long-term EMA (N2=30): E2

Core Logic:
1. A1: Short-term EMA stabilizes and turns up (after adjustment)
2. A2: Mid-long-term EMA continues upward (bullish trend)
3. A3: Price pullback ≤10% (controlled correction)
4. A4: E1 always above E2 (bullish structure)
5. A5: Price stays above E2 for 5 consecutive days
6. A6: Price breaks above E1 (breakthrough signal)
7. A7: Volume expansion (energy confirmation)

Strong Move Confirmation:
- At least 1 limit-up or gap-up within 50 days
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date
from pathlib import Path
import logging
import sys
from typing import List, Dict, Optional, Tuple

# Add workspace root to path for imports
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from base_screener import BaseScreener, ScreenResult

logger = logging.getLogger(__name__)


class TrendBreakthroughScreenerV2(BaseScreener):
    """
    Trend Breakthrough Screener V2 based on Pascal strategy.

    Strategy: Trend tracking + breakthrough buy signal
    Timeframe: Daily data
    """

    def __init__(self, n1: int = 10, n2: int = 30, **kwargs):
        """
        Initialize trend breakthrough screener.

        Args:
            n1: Short-term EMA period (default: 10)
            n2: Mid-long-term EMA period (default: 30)
        """
        super().__init__(**kwargs)
        self.n1 = n1
        self.n2 = n2

        # Strategy parameters
        self.a1_down_days = 5  # A1: Check last N days for down moves
        self.a1_min_down = 3   # A1: Minimum down days required
        self.a2_up_days = 13   # A2: Check last N days for up moves
        self.a2_min_up = 8     # A2: Minimum up days required
        self.a3_lookback = 13  # A3: Pullback control window
        self.a3_max_pullback = 0.1  # A3: Max 10% pullback
        self.a4_lookback = 13  # A4: Bullish structure window
        self.a5_lookback = 5   # A5: Price above E2 window
        self.a7_volume_ma = 5  # A7: Volume MA period
        self.con_lookback = 50 # Strong move confirmation window
        self.limit_up_threshold = 0.099  # 9.9% for limit-up

    def calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average."""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]
        return ema

    def check_a1(self, ema1: np.ndarray, index: int) -> bool:
        """
        A1: Short-term EMA stabilizes and turns up.

        Condition:
        - At least 3 days out of last 5 days, E1 was declining
        - Current day E1 is rising (E1 > E1[-1])
        """
        if index < self.a1_down_days:
            return False

        # Count down days in last N days
        down_days = 0
        for i in range(index - self.a1_down_days + 1, index + 1):
            if i > 0 and ema1[i] < ema1[i - 1]:
                down_days += 1

        # At least 3 days declining
        if down_days < self.a1_min_down:
            return False

        # Current day E1 is rising
        if ema1[index] <= ema1[index - 1]:
            return False

        return True

    def check_a2(self, ema2: np.ndarray, index: int) -> bool:
        """
        A2: Mid-long-term EMA continues upward.

        Condition:
        - At least 8 days out of last 13 days, E2 was rising
        - Current day, E2 is rising (E2 > E2[-1])
        """
        if index < self.a2_up_days:
            return False

        # Count up days in last N days
        up_days = 0
        for i in range(index - self.a2_up_days + 1, index + 1):
            if i > 0 and ema2[i] > ema2[i - 1]:
                up_days += 1

        # At least 8 days rising
        if up_days < self.a2_min_up:
            return False

        # Current day E2 is rising
        if ema2[index] <= ema2[index - 1]:
            return False

        return True

    def check_a3(self, low: np.ndarray, ema2: np.ndarray, index: int) -> bool:
        """
        A3: Price pullback is controlled (≤10%).

        Condition:
        - Maximum deviation of low price from E2 in last 13 days ≤ 10%
        """
        if index < self.a3_lookback:
            return False

        # Calculate minimum deviation
        min_deviation = float('inf')
        for i in range(index - self.a3_lookback + 1, index + 1):
            deviation = (low[i] / ema2[i] - 1)
            if deviation < min_deviation:
                min_deviation = deviation

        # Minimum deviation should be >= -10%
        return min_deviation >= -self.a3_max_pullback

    def check_a4(self, ema1: np.ndarray, ema2: np.ndarray, index: int) -> bool:
        """
        A4: Short-term EMA always above mid-long-term EMA.

        Condition:
        - Every day in last 13 days, E1 > E2
        """
        if index < self.a4_lookback:
            return False

        for i in range(index - self.a4_lookback + 1, index + 1):
            if ema1[i] <= ema2[i]:
                return False

        return True

    def check_a5(self, close: np.ndarray, ema2: np.ndarray, index: int) -> bool:
        """
        A5: Price stays above E2 for consecutive days.

        Condition:
        - Every day in last 5 days, Close > E2
        """
        if index < self.a5_lookback:
            return False

        for i in range(index - self.a5_lookback + 1, index + 1):
            if close[i] <= ema2[i]:
                return False

        return True

    def check_a6(self, close: np.ndarray, ema1: np.ndarray, index: int) -> bool:
        """
        A6: Price breaks above short-term EMA.

        Condition:
        - Current day Close > E1 (cross above)
        - Previous day Close <= E1
        """
        if index < 1:
            return False

        # Cross above: Close crosses E1 from below
        return (close[index - 1] <= ema1[index - 1]) and (close[index] > ema1[index])

    def check_a7(self, volume: np.ndarray, index: int) -> bool:
        """
        A7: Volume expansion.

        Condition:
        - Current day volume > 5-day average volume
        """
        if index < self.a7_volume_ma:
            return False

        # Calculate 5-day average volume
        avg_volume = np.mean(volume[index - self.a7_volume_ma:index])
        current_volume = volume[index]

        return current_volume > avg_volume

    def check_strong_move(self, close: np.ndarray, high: np.ndarray, low: np.ndarray, index: int) -> bool:
        """
        Check for strong move (limit-up or gap-up) within lookback window.

        Conditions:
        - Limit-up: Price change > 9.9%
        - Gap-up: Today's low > yesterday's high
        """
        if index < 1:
            return False

        start_idx = max(0, index - self.con_lookback + 1)

        # Check for limit-up (change > 9.9%)
        for i in range(start_idx + 1, index + 1):
            price_change = (close[i] - close[i - 1]) / close[i - 1]
            if price_change > self.limit_up_threshold:
                return True

        # Check for gap-up (low > previous high)
        for i in range(start_idx + 1, index + 1):
            if low[i] > high[i - 1]:
                return True

        return False

    def screen_stock(self, stock_code: str, stock_name: str) -> Optional[Dict]:
        """
        Screen a single stock for trend breakthrough pattern.

        Args:
            stock_code: Stock code
            stock_name: Stock name

        Returns:
            Dict with screening result if pattern found, None otherwise
        """
        try:
            # Load data from database using BaseScreener method
            # Get more data than needed to ensure we have enough for all checks
            days_needed = max(self.con_lookback, self.a4_lookback) + 10
            df = self.get_stock_data(stock_code, days=days_needed)

            if df is None or len(df) < days_needed:
                return None

            # Sort by date ascending (oldest first)
            df = df.sort_values('trade_date').reset_index(drop=True)

            # Extract data as numpy arrays for faster computation
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            pct_change = df['pct_change'].values

            # Calculate EMAs
            ema1 = self.calculate_ema(close, self.n1)
            ema2 = self.calculate_ema(close, self.n2)

            # Check from the most recent day backwards
            for i in range(len(close) - 1, max(self.con_lookback, self.a4_lookback), -1):
                # Skip if EMA values are NaN or zero
                if np.isnan(ema1[i]) or np.isnan(ema2[i]) or ema2[i] == 0:
                    continue

                # Check all A1-A7 conditions
                a1 = self.check_a1(ema1, i)
                a2 = self.check_a2(ema2, i)
                a3 = self.check_a3(low, ema2, i)
                a4 = self.check_a4(ema1, ema2, i)
                a5 = self.check_a5(close, ema2, i)
                a6 = self.check_a6(close, ema1, i)
                a7 = self.check_a7(volume, i)

                # Core condition YT
                yt = a1 and a2 and a3 and a4 and a5 and a6 and a7

                if not yt:
                    continue

                # Check strong move confirmation
                has_strong_move = self.check_strong_move(close, high, low, i)

                if has_strong_move:
                    # Calculate volume ratio
                    volume_ma5 = np.mean(volume[i - self.a7_volume_ma:i])
                    volume_ratio = volume[i] / volume_ma5 if volume_ma5 > 0 else 1.0

                    # Pattern found!
                    result = {
                        'code': stock_code,
                        'name': stock_name,
                        'date': df.iloc[i]['trade_date'].strftime('%Y-%m-%d'),
                        'price': float(close[i]),
                        'score': 1.0,  # Base score for all matches
                        'reason': (
                            f"A1(A1={a1}),A2(A2={a2}),A3(A3={a3}),"
                            f"A4(A4={a4}),A5(A5={a5}),A6(A6={a6}),A7(A7={a7})"
                        ),
                        'e1': round(float(ema1[i]), 2),
                        'e2': round(float(ema2[i]), 2),
                        'volume': int(volume[i]),
                        'volume_ma5': round(float(volume_ma5), 0),
                        'volume_ratio': round(float(volume_ratio), 2),
                        'pct_change': round(float(pct_change[i]), 2),
                        'n1': self.n1,
                        'n2': self.n2
                    }

                    logger.info(f"✓ {stock_code} {stock_name}: Trend breakthrough at {df.iloc[i]['trade_date']}")
                    logger.info(f"  E1={ema1[i]:.2f}, E2={ema2[i]:.2f}, "
                              f"Volume Ratio={volume_ratio:.2f}")

                    return result

            return None

        except Exception as e:
            logger.error(f"Error screening {stock_code}: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Main function to run trend breakthrough screener."""
    import argparse

    parser = argparse.ArgumentParser(description='Trend Breakthrough Screener V2')
    parser.add_argument('--date', type=str, default=None, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--n1', type=int, default=10, help='Short-term EMA period')
    parser.add_argument('--n2', type=int, default=30, help='Mid-long-term EMA period')
    parser.add_argument('--output', type=str, default=None, help='Output file path')

    args = parser.parse_args()

    # Create screener
    screener = TrendBreakthroughScreenerV2(n1=args.n1, n2=args.n2)

    # Get target date
    if args.date is None:
        args.date = screener.current_date

    # Set current date for screener
    screener.current_date = args.date

    logger.info(f"Starting Trend Breakthrough Screener V2 for date: {args.date}")
    logger.info(f"Parameters: N1={args.n1}, N2={args.n2}")

    # Run screening
    results, summary = screener.run()

    # Print summary
    print("\n" + "=" * 80)
    print("TREND BREAKTHROUGH SCREENER V2 SUMMARY")
    print("=" * 80)
    print(f"Screening Date: {args.date}")
    print(f"Parameters: N1={args.n1}, N2={args.n2}")
    print(f"Stocks Processed: {summary.get('processed', 0)}")
    print(f"Stocks Found: {len(results)}")
    if summary.get('processed', 0) > 0:
        print(f"Success Rate: {len(results)/summary['processed']*100:.2f}%")
    print("=" * 80)

    if results:
        print(f"\n{'Code':<8} {'Name':<16} {'Date':<12} {'Price':<8} {'E1':<8} {'E2':<8} {'VolRatio':<8} {'Change%'}")
        print("-" * 80)
        for result in results:
            extra = result.extra
            print(f"{result.code:<8} {result.name:<16} {extra.get('date', ''):<12} "
                  f"{extra.get('price', 0):<8.2f} {extra.get('e1', 0):<8.2f} {extra.get('e2', 0):<8.2f} "
                  f"{extra.get('volume_ratio', 0):<8.2f} {extra.get('pct_change', 0):>6.2f}")

    # Save results
    if args.output:
        screener.save_results(results, args.output)
    else:
        output_file = f"data/screeners/trend_breakthrough/trend_breakthrough_{args.date}.xlsx"
        screener.save_results(results, output_file)
        print(f"\nResults saved to: {output_file}")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
