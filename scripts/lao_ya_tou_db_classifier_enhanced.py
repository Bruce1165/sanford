#!/usr/bin/env python3
"""
Lao Ya Tou Database Classifier - Enhanced Version with Detailed Analysis.

This script provides:
1. More flexible signal detection criteria
2. Detailed technical indicators for each signal
3. Historical signal tracking
4. Export to Excel for further analysis
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
import sys
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"


class LaoYaTouEnhancedClassifier:
    """Enhanced LYT classifier with flexible detection and detailed analysis."""

    def __init__(self, target_date: Optional[str] = None, use_strict: bool = True):
        """
        Initialize enhanced classifier.

        Args:
            target_date: Target date for screening
            use_strict: Use strict criteria (True) or relaxed criteria (False)
        """
        self.target_date = target_date
        self.use_strict = use_strict
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

        # LYT Parameters (can be relaxed)
        if use_strict:
            self.ma5_period = 5
            self.ma10_period = 10
            self.ma30_period = 30
            self.amplitude_lookback_weeks = 22
            self.amplitude_min_threshold = 65.0
            self.min_gap = 2.0
            self.max_gap = 10.0
            self.volume_contraction_threshold = 0.7
            self.local_high_window = 12
        else:
            # Relaxed criteria
            self.ma5_period = 5
            self.ma10_period = 10
            self.ma30_period = 30
            self.amplitude_lookback_weeks = 22
            self.amplitude_min_threshold = 50.0  # Lowered from 65%
            self.min_gap = 1.0  # Lowered from 2.0
            self.max_gap = 15.0  # Increased from 10.0
            self.volume_contraction_threshold = 0.6  # Lowered from 0.7
            self.local_high_window = 15  # Increased from 12

        # If no target date, get latest trading day
        if target_date is None:
            self.target_date = self._get_latest_trading_day()

        logger.info(f"Initialized Enhanced LYT Classifier for date: {self.target_date}")
        logger.info(f"Mode: {'Strict' if use_strict else 'Relaxed'}")

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
        """Calculate comprehensive technical indicators."""
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

        # Price indicators
        df['price_change'] = df['close'].pct_change() * 100
        df['high_low_ratio'] = (df['high'] - df['low']) / df['low'] * 100

        # Trend indicators
        df['ma5_trend'] = df['ma5'].diff()
        df['ma10_trend'] = df['ma10'].diff()
        df['ma30_trend'] = df['ma30'].diff()

        return df

    def _check_amplitude(self, df: pd.DataFrame) -> Tuple[bool, float]:
        """Check if stock has sufficient price movement."""
        if len(df) < self.amplitude_lookback_weeks:
            return False, 0.0

        recent_period = df.tail(self.amplitude_lookback_weeks)
        high_price = recent_period['high'].max()
        low_price = recent_period['low'].min()

        if low_price == 0:
            return False, 0.0

        amplitude = ((high_price - low_price) / low_price) * 100
        return amplitude >= self.amplitude_min_threshold, amplitude

    def _detect_crossings(self, df: pd.DataFrame) -> List[Dict]:
        """Detect all MA crossings (golden and death crosses)."""
        crossings = []

        for i in range(1, len(df)):
            ma5_curr = df.iloc[i]['ma5']
            ma5_prev = df.iloc[i - 1]['ma5']
            ma10_curr = df.iloc[i]['ma10']
            ma10_prev = df.iloc[i - 1]['ma10']

            # Golden cross: MA5 crosses above MA10
            if ma5_curr > ma10_curr and ma5_prev <= ma10_prev:
                crossings.append({
                    'index': i,
                    'date': df.iloc[i]['trade_date'],
                    'type': 'golden_cross',
                    'ma5': ma5_curr,
                    'ma10': ma10_curr,
                    'ma30': df.iloc[i]['ma30'],
                    'gap': df.iloc[i]['ma_gap'],
                    'price': df.iloc[i]['close'],
                    'volume_ratio': df.iloc[i]['volume_ratio']
                })

            # Death cross: MA5 crosses below MA10
            elif ma5_curr < ma10_curr and ma5_prev >= ma10_prev:
                crossings.append({
                    'index': i,
                    'date': df.iloc[i]['trade_date'],
                    'type': 'death_cross',
                    'ma5': ma5_curr,
                    'ma10': ma10_curr,
                    'ma30': df.iloc[i]['ma30'],
                    'gap': df.iloc[i]['ma_gap'],
                    'price': df.iloc[i]['close'],
                    'volume_ratio': df.iloc[i]['volume_ratio']
                })

        return crossings

    def _analyze_pattern(self, df: pd.DataFrame, crossings: List[Dict]) -> Optional[Dict]:
        """
        Analyze the pattern to determine signal type and quality.

        Returns:
            Dict with signal type and detailed analysis
        """
        if not crossings:
            return None

        last_idx = len(df) - 1
        recent_crossings = [c for c in crossings if c['index'] >= last_idx - 20]

        if not recent_crossings:
            return None

        # Find pattern: death cross followed by golden crosses
        death_crosses = [c for c in recent_crossings if c['type'] == 'death_cross']
        golden_crosses = [c for c in recent_crossings if c['type'] == 'golden_cross']

        if not death_crosses or not golden_crosses:
            return None

        # Get the last death cross
        last_death = death_crosses[-1]

        # Get golden crosses after death cross
        post_death_golden = [c for c in golden_crosses if c['index'] > last_death['index']]

        if not post_death_golden:
            return None

        # Analyze the latest golden cross
        latest_golden = post_death_golden[-1]

        # Check if MA5 > MA10 > MA30 (bullish alignment)
        is_bullish = (latest_golden['ma5'] > latest_golden['ma10'] > latest_golden['ma30'])

        if not is_bullish:
            return None

        # Calculate signal type
        signal_type = None
        confidence = 0.0

        # Signal 1: Duck Nostril (First golden cross after death)
        if len(post_death_golden) == 1:
            gap = latest_golden['gap']
            if self.min_gap <= gap <= self.max_gap:
                signal_type = 'signal_1'
                # Calculate confidence based on gap (smaller is better)
                gap_score = 1.0 - (gap / self.max_gap)
                confidence = gap_score * 0.7 + 0.3  # Base confidence

        # Signal 2: Duck Mouth (Second golden cross, opening)
        elif len(post_death_golden) >= 2:
            prev_golden = post_death_golden[-2]
            if latest_golden['gap'] > prev_golden['gap']:
                signal_type = 'signal_2'
                # Higher confidence for second signal
                gap_improvement = (latest_golden['gap'] - prev_golden['gap']) / prev_golden['gap']
                confidence = min(0.6 + gap_improvement * 2.0, 0.95)

        # Signal 3: Volume breakout (can be combined with signal 1 or 2)
        if latest_golden['volume_ratio'] > 1.3:  # Relaxed from 1.5
            # Find recent high
            recent_high = df.tail(self.local_high_window)['high'].max()
            if latest_golden['price'] >= recent_high * 0.95:  # Near or above recent high
                signal_type = 'signal_3'
                confidence = 0.5 + min(latest_golden['volume_ratio'] / 3.0, 0.45)

        if signal_type:
            # Add detailed analysis
            result = {
                'signal_type': signal_type,
                'signal_date': str(latest_golden['date'].date()),
                'signal_price': latest_golden['price'],
                'ma5': latest_golden['ma5'],
                'ma10': latest_golden['ma10'],
                'ma30': latest_golden['ma30'],
                'gap': latest_golden['gap'],
                'volume_ratio': latest_golden['volume_ratio'],
                'confidence': round(confidence, 2),
                'crossings_count': len(post_death_golden),
                'death_cross_date': str(last_death['date'].date()),
                'death_cross_price': last_death['price'],
                'trend_strength': self._calculate_trend_strength(df, latest_golden['index']),
                'support_distance': ((latest_golden['ma10'] - latest_golden['ma30']) / latest_golden['ma30'] * 100)
            }
            return result

        return None

    def _calculate_trend_strength(self, df: pd.DataFrame, index: int) -> float:
        """Calculate trend strength score."""
        if index < 5:
            return 0.0

        # Calculate MA slopes
        recent_ma5 = df['ma5'].iloc[index-5:index+1].values
        recent_ma10 = df['ma10'].iloc[index-5:index+1].values
        recent_ma30 = df['ma30'].iloc[index-5:index+1].values

        ma5_slope = np.polyfit(range(6), recent_ma5, 1)[0]
        ma10_slope = np.polyfit(range(6), recent_ma10, 1)[0]
        ma30_slope = np.polyfit(range(6), recent_ma30, 1)[0]

        # All slopes positive = strong uptrend
        if ma5_slope > 0 and ma10_slope > 0 and ma30_slope > 0:
            return 0.8
        elif ma5_slope > 0 and ma10_slope > 0:
            return 0.6
        elif ma5_slope > 0:
            return 0.4
        else:
            return 0.2

    def screen_stock(self, stock_code: str, stock_name: str) -> Optional[Dict]:
        """Screen a single stock for LYT signals."""
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

            # Check amplitude
            has_amplitude, amplitude = self._check_amplitude(weekly_df)
            if not has_amplitude:
                return None

            # Detect crossings
            crossings = self._detect_crossings(weekly_df)

            # Analyze pattern
            analysis = self._analyze_pattern(weekly_df, crossings)

            if analysis:
                return {
                    'code': stock_code,
                    'name': stock_name,
                    'amplitude': round(amplitude, 2),
                    'screening_date': self.target_date,
                    **analysis
                }

            return None

        except Exception as e:
            logger.error(f"Error screening {stock_code}: {e}")
            return None

    def screen_all_stocks(self) -> Dict[str, List[Dict]]:
        """Screen all stocks and classify by signal type."""
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
            'signal_1': [],
            'signal_2': [],
            'signal_3': [],
            'total_screened': len(stocks),
            'screening_mode': 'strict' if self.use_strict else 'relaxed'
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
                logger.info(f"  Found {signal_type}: {stock_code} {stock_name} (confidence: {result['confidence']})")

        self.conn.close()

        return results

    def save_results(self, results: Dict[str, List[Dict]], output_dir: Optional[str] = None):
        """Save results to JSON and Excel."""
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "data"
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(exist_ok=True)

        # Save JSON
        json_file = output_dir / f"lao_ya_tou_enhanced_{self.target_date}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"JSON results saved to {json_file}")

        # Save Excel
        excel_file = output_dir / f"lao_ya_tou_enhanced_{self.target_date}.xlsx"
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for signal_type in ['signal_1', 'signal_2', 'signal_3']:
                if results[signal_type]:
                    df = pd.DataFrame(results[signal_type])
                    df.to_excel(writer, sheet_name=signal_type, index=False)

            # Summary sheet
            summary_data = {
                'Metric': [
                    'Screening Date',
                    'Total Stocks Screened',
                    'Screening Mode',
                    'Signal 1 (Duck Nostril)',
                    'Signal 2 (Duck Mouth)',
                    'Signal 3 (Volume Breakout)',
                    'Total LYT Pattern Stocks'
                ],
                'Value': [
                    self.target_date,
                    results['total_screened'],
                    results['screening_mode'],
                    len(results['signal_1']),
                    len(results['signal_2']),
                    len(results['signal_3']),
                    len(results['signal_1']) + len(results['signal_2']) + len(results['signal_3'])
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        logger.info(f"Excel results saved to {excel_file}")

        # Print summary
        self._print_summary(results)

    def _print_summary(self, results: Dict[str, List[Dict]]):
        """Print classification summary."""
        print("\n" + "=" * 80)
        print("LAO YA TOU ENHANCED CLASSIFICATION SUMMARY")
        print("=" * 80)
        print(f"Screening Date: {self.target_date}")
        print(f"Screening Mode: {results['screening_mode'].upper()}")
        print(f"Total Stocks Screened: {results['total_screened']}")
        print(f"")
        print(f"Signal 1 (Duck Nostril - Aggressive): {len(results['signal_1'])} stocks")
        print(f"Signal 2 (Duck Mouth - Stable): {len(results['signal_2'])} stocks")
        print(f"Signal 3 (Volume Breakout - Chase): {len(results['signal_3'])} stocks")
        print(f"")
        print(f"Total LYT Pattern Stocks: {len(results['signal_1']) + len(results['signal_2']) + len(results['signal_3'])}")
        print("=" * 80)

        # Print signal details
        for signal_type, signal_name in [
            ('signal_1', 'SIGNAL 1 (Duck Nostril)'),
            ('signal_2', 'SIGNAL 2 (Duck Mouth)'),
            ('signal_3', 'SIGNAL 3 (Volume Breakout)')
        ]:
            if results[signal_type]:
                print(f"\n{signal_name} - {len(results[signal_type])} stocks:")
                print("-" * 80)
                print(f"{'Code':<8} {'Name':<16} {'Date':<12} {'Price':<8} {'Gap':<8} {'VolRatio':<8} {'Conf':<6}")
                print("-" * 80)
                for stock in sorted(results[signal_type], key=lambda x: x['confidence'], reverse=True):
                    print(f"{stock['code']:<8} {stock['name']:<16} {stock['signal_date']:<12} "
                          f"{stock['signal_price']:<8.2f} {stock['gap']:<8.2f} "
                          f"{stock['volume_ratio']:<8.2f} {stock['confidence']:<6.2f}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Enhanced LYT classifier with detailed analysis')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--relaxed', action='store_true', help='Use relaxed criteria')
    parser.add_argument('--output-dir', type=str, help='Output directory')

    args = parser.parse_args()

    classifier = LaoYaTouEnhancedClassifier(
        target_date=args.date,
        use_strict=not args.relaxed
    )
    results = classifier.screen_all_stocks()
    classifier.save_results(results, args.output_dir)


if __name__ == '__main__':
    main()
