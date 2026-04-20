#!/usr/bin/env python3
"""
Lao Ya Tou Database Classifier - Direct SQL-based signal classification.

This script scans all stocks in the database and classifies them into three signals:
- Signal 1: Duck Nostril (Aggressive) - MA5 golden cross MA10 with small gap
- Signal 2: Duck Mouth (Stable) - Second golden cross, opening upward
- Signal 3: Volume Breakout (Chase) - Volume expansion above duck head high
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"


class LaoYaTouSignalClassifier:
    """Classify stocks into Lao Ya Tou three-signal system using database data."""

    def __init__(self, target_date: Optional[str] = None):
        """
        Initialize classifier.

        Args:
            target_date: Target date for screening (default: latest trading day)
        """
        self.target_date = target_date
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

        # LYT Parameters
        self.ma5_period = 5
        self.ma10_period = 10
        self.ma30_period = 30
        self.amplitude_lookback_weeks = 22
        self.amplitude_min_threshold = 65.0
        self.min_gap = 2.0
        self.max_gap = 10.0
        self.volume_contraction_threshold = 0.7
        self.local_high_window = 12

        # If no target date, get latest trading day
        if target_date is None:
            self.target_date = self._get_latest_trading_day()

        logger.info(f"Initialized LYT Signal Classifier for date: {self.target_date}")

    def _get_latest_trading_day(self) -> str:
        """Get the latest trading day from database."""
        query = """
            SELECT MAX(trade_date) as max_date
            FROM daily_prices
            WHERE trade_date <= date('now', 'localtime')
        """
        result = self.conn.execute(query).fetchone()
        return result['max_date'] if result else '2026-04-16'

    def _convert_to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert daily data to weekly data."""
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df['week_num'] = df['trade_date'].dt.isocalendar().week
        df['year'] = df['trade_date'].dt.year
        df['week_key'] = df['year'].astype(str) + '_' + df['week_num'].astype(str)

        # Get last trading day of each week
        weekly_df = df.groupby('week_key').last().reset_index()
        weekly_df = weekly_df.sort_values('trade_date').reset_index(drop=True)

        return weekly_df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MA indicators."""
        df = df.copy()

        # Calculate MAs
        df['ma5'] = df['close'].rolling(window=self.ma5_period, min_periods=self.ma5_period).mean()
        df['ma10'] = df['close'].rolling(window=self.ma10_period, min_periods=self.ma10_period).mean()
        df['ma30'] = df['close'].rolling(window=self.ma30_period, min_periods=self.ma30_period).mean()

        # Calculate gap
        df['ma_gap'] = ((df['ma5'] - df['ma10']) / df['ma10'] * 100)

        # Volume indicators
        df['volume_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
        df['volume_ma10'] = df['volume'].rolling(window=10, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma5'].replace(0, 1)

        return df

    def _check_amplitude(self, df: pd.DataFrame) -> bool:
        """Check if stock has sufficient price movement."""
        if len(df) < self.amplitude_lookback_weeks:
            return False

        recent_period = df.tail(self.amplitude_lookback_weeks)
        high_price = recent_period['high'].max()
        low_price = recent_period['low'].min()

        if low_price == 0:
            return False

        amplitude = ((high_price - low_price) / low_price) * 100
        return amplitude >= self.amplitude_min_threshold

    def _detect_golden_cross(self, ma5: pd.Series, ma10: pd.Series, index: int) -> bool:
        """Detect MA5 golden cross above MA10."""
        if index < 1:
            return False

        # Previous: MA5 <= MA10
        prev_condition = ma5.iloc[index - 1] <= ma10.iloc[index - 1]

        # Current: MA5 > MA10
        curr_condition = ma5.iloc[index] > ma10.iloc[index]

        return prev_condition and curr_condition

    def _detect_death_cross(self, ma5: pd.Series, ma10: pd.Series, index: int) -> bool:
        """Detect MA5 death cross below MA10."""
        if index < 1:
            return False

        # Previous: MA5 >= MA10
        prev_condition = ma5.iloc[index - 1] >= ma10.iloc[index - 1]

        # Current: MA5 < MA10
        curr_condition = ma5.iloc[index] < ma10.iloc[index]

        return prev_condition and curr_condition

    def _find_local_high(self, df: pd.DataFrame, window: int) -> Tuple[float, int]:
        """Find local high point in recent window."""
        if len(df) < window:
            window = len(df)

        recent_df = df.tail(window)
        max_price = recent_df['high'].max()
        max_idx = recent_df['high'].idxmax()

        return max_price, max_idx

    def _classify_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Classify stock into one of three LYT signals.

        Returns:
            Tuple of (signal_type, details_dict)
        """
        # Check basic LYT pattern elements
        if not self._check_amplitude(df):
            return None, None

        # Check recent weeks for pattern
        last_idx = len(df) - 1

        # Need at least 30 weeks of data
        if last_idx < 30:
            return None, None

        # Find local high in recent window
        recent_high, high_idx = self._find_local_high(df, self.local_high_window)

        # Check for recent death cross (after high)
        has_death_cross = False
        death_cross_idx = -1

        for i in range(high_idx, min(last_idx + 1, high_idx + 10)):
            if self._detect_death_cross(df['ma5'], df['ma10'], i):
                has_death_cross = True
                death_cross_idx = i
                break

        if not has_death_cross:
            return None, None

        # Check for golden crosses after death cross
        golden_crosses = []
        for i in range(death_cross_idx + 1, last_idx + 1):
            if self._detect_golden_cross(df['ma5'], df['ma10'], i):
                gap = df.iloc[i]['ma_gap']
                golden_crosses.append({
                    'index': i,
                    'date': df.iloc[i]['trade_date'],
                    'price': df.iloc[i]['close'],
                    'ma5': df.iloc[i]['ma5'],
                    'ma10': df.iloc[i]['ma10'],
                    'ma30': df.iloc[i]['ma30'],
                    'gap': gap,
                    'volume_ratio': df.iloc[i]['volume_ratio']
                })

        if not golden_crosses:
            return None, None

        # Classify based on golden crosses
        latest_cross = golden_crosses[-1]

        # Signal 1: Duck Nostril (First golden cross with small gap)
        if len(golden_crosses) == 1:
            if self.min_gap <= latest_cross['gap'] <= self.max_gap:
                # Check if price is above MA30
                if latest_cross['ma5'] > latest_cross['ma30'] and latest_cross['ma10'] > latest_cross['ma30']:
                    return 'signal_1', latest_cross

        # Signal 2: Duck Mouth (Second golden cross)
        elif len(golden_crosses) >= 2:
            # Check if latest cross has MA5/MA10 spreading upward
            if latest_cross['ma5'] > latest_cross['ma10'] > latest_cross['ma30']:
                # Check if gap is increasing (opening)
                if len(golden_crosses) >= 2:
                    prev_gap = golden_crosses[-2]['gap']
                    if latest_cross['gap'] > prev_gap:
                        return 'signal_2', latest_cross

        # Signal 3: Volume Breakout (Volume expansion above high)
        if latest_cross['volume_ratio'] > 1.5:  # Volume 50% above average
            if latest_cross['price'] > recent_high * 0.98:  # Price near or above recent high
                return 'signal_3', latest_cross

        return None, None

    def screen_stock(self, stock_code: str, stock_name: str) -> Optional[Dict]:
        """
        Screen a single stock for LYT signals.

        Args:
            stock_code: Stock code
            stock_name: Stock name

        Returns:
            Dict with classification result or None
        """
        try:
            # Load data from database
            query = """
                SELECT trade_date, open, high, low, close, volume, amount, pct_change
                FROM daily_prices
                WHERE code = ?
                AND trade_date <= ?
                ORDER BY trade_date ASC
            """
            df = pd.read_sql_query(query, self.conn, params=(stock_code, self.target_date))

            if len(df) < 52:  # Need at least 1 year of weekly data
                return None

            # Convert to weekly
            weekly_df = self._convert_to_weekly(df)

            if len(weekly_df) < 30:
                return None

            # Calculate indicators
            weekly_df = self._calculate_indicators(weekly_df)

            # Classify signal
            signal_type, details = self._classify_signal(weekly_df)

            if signal_type and details:
                return {
                    'code': stock_code,
                    'name': stock_name,
                    'signal_type': signal_type,
                    'signal_date': str(details['date'].date()),
                    'signal_price': details['price'],
                    'ma5': details['ma5'],
                    'ma10': details['ma10'],
                    'ma30': details['ma30'],
                    'gap': details['gap'],
                    'volume_ratio': details['volume_ratio'],
                    'screening_date': self.target_date
                }

            return None

        except Exception as e:
            logger.error(f"Error screening {stock_code}: {e}")
            return None

    def screen_all_stocks(self) -> Dict[str, List[Dict]]:
        """
        Screen all stocks and classify by signal type.

        Returns:
            Dict with signal types as keys and list of stocks as values
        """
        # Get all stocks
        query = """
            SELECT code, name
            FROM stocks
            WHERE is_delisted = 0
            ORDER BY code
        """
        stocks = self.conn.execute(query).fetchall()

        logger.info(f"Screening {len(stocks)} stocks...")

        results = {
            'signal_1': [],  # Duck Nostril (Aggressive)
            'signal_2': [],  # Duck Mouth (Stable)
            'signal_3': [],  # Volume Breakout (Chase)
            'total_screened': len(stocks)
        }

        for i, stock in enumerate(stocks):
            stock_code = stock['code']
            stock_name = stock['name']

            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{len(stocks)} stocks screened")

            result = self.screen_stock(stock_code, stock_name)

            if result:
                signal_type = result['signal_type']
                results[signal_type].append(result)
                logger.info(f"  Found {signal_type}: {stock_code} {stock_name}")

        self.conn.close()

        return results

    def save_results(self, results: Dict[str, List[Dict]], output_file: Optional[str] = None):
        """Save classification results to file."""
        if output_file is None:
            output_file = f"data/lao_ya_tou_classification_{self.target_date}.json"

        output_path = Path(__file__).parent.parent / output_file

        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Results saved to {output_path}")

        # Print summary
        print("\n" + "=" * 60)
        print("LAO YA TOU CLASSIFICATION SUMMARY")
        print("=" * 60)
        print(f"Screening Date: {self.target_date}")
        print(f"Total Stocks Screened: {results['total_screened']}")
        print(f"")
        print(f"Signal 1 (Duck Nostril - Aggressive): {len(results['signal_1'])} stocks")
        print(f"Signal 2 (Duck Mouth - Stable): {len(results['signal_2'])} stocks")
        print(f"Signal 3 (Volume Breakout - Chase): {len(results['signal_3'])} stocks")
        print(f"")
        print(f"Total LYT Pattern Stocks: {len(results['signal_1']) + len(results['signal_2']) + len(results['signal_3'])}")
        print("=" * 60)

        # Print signal details
        for signal_type in ['signal_1', 'signal_2', 'signal_3']:
            if results[signal_type]:
                print(f"\n{signal_type.upper()} ({len(results[signal_type])} stocks):")
                print("-" * 60)
                print(f"{'Code':<8} {'Name':<20} {'Date':<12} {'Price':<8} {'Gap':<8} {'VolRatio'}")
                print("-" * 60)
                for stock in sorted(results[signal_type], key=lambda x: x['code']):
                    print(f"{stock['code']:<8} {stock['name']:<20} {stock['signal_date']:<12} "
                          f"{stock['signal_price']:<8.2f} {stock['gap']:<8.2f} {stock['volume_ratio']:.2f}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Classify stocks into Lao Ya Tou signals')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, help='Output file path')

    args = parser.parse_args()

    classifier = LaoYaTouSignalClassifier(target_date=args.date)
    results = classifier.screen_all_stocks()
    classifier.save_results(results, args.output)


if __name__ == '__main__':
    main()
