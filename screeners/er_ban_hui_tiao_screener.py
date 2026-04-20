#!/usr/bin/env python3
from __future__ import annotations
"""
二板回调筛选器 (V4) - Er Ban Hui Tiao Screener (V4)

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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener
from config import FLASK_PORT

logger = logging.getLogger(__name__)

LIMIT_DAYS = 14  # Last 14 trading days
LIMIT_UP_THRESHOLD = 9.9  # Limit-up threshold
FIRST_BOARD_VOLUME_RATIO = 2.0  # Signal 1: first board amount / previous day amount ratio


class ErBanHuiTiaoScreener(BaseScreener):
    """Two-Board Pullback Screener V4"""

    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 limit_up_threshold: float = LIMIT_UP_THRESHOLD,
                 first_board_volume_ratio: float = FIRST_BOARD_VOLUME_RATIO,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True,
                 use_pool: bool = False):
        super().__init__(
            screener_name='er_ban_hui_tiao',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.limit_up_threshold = limit_up_threshold
        self.first_board_volume_ratio = first_board_volume_ratio
        self.use_pool = use_pool

    def get_screener_code(self) -> str:
        """Return this screener's code for DB lookup."""
        return 'er_ban_hui_tiao'

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """Return parameter schema for the screener"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 14,
                'min': 1,
                'max': 60,
                'display_name': 'Time Range (Trading Days)',
                'description': 'Filter signals within last N trading days',
                'group': 'Basic Settings'
            },
            'LIMIT_UP_THRESHOLD': {
                'type': 'float',
                'default': 9.9,
                'min': 9.0,
                'max': 10.5,
                'step': 0.1,
                'display_name': 'Limit-up Threshold (%)',
                'description': 'Minimum gain threshold for limit-up',
                'group': 'Signal Conditions'
            },
            'FIRST_BOARD_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': 'First Board Amount Ratio',
                'description': 'First board amount must be N times of previous day',
                'group': 'Signal Conditions'
            }
        }

    def is_limit_up(self, pct_change: float) -> bool:
        """Check if it's a limit-up day"""
        return pct_change >= self.limit_up_threshold

    def find_signal_one(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Find Signal 1: Two consecutive limit-up boards, and:
        - First board (Day T) amount >= previous day amount * 2
        - Second board amount < first board amount
        - Skip if 3 or more consecutive limit-ups found

        Returns:
            Dictionary with first_idx, second_idx, first_open, first_amount, second_amount
            or None if not found
        """
        if len(df) < 3:  # Need at least previous day + two consecutive boards
            return None

        # Search backwards, i is first board index
        for i in range(len(df) - 2, 0, -1):

            # Check two consecutive limit-ups (i and i+1)
            first_pct = df.iloc[i]['pct_change'] or 0
            second_pct = df.iloc[i + 1]['pct_change'] or 0

            if not (self.is_limit_up(first_pct) and self.is_limit_up(second_pct)):
                continue

            # Check for 3 or more consecutive limit-ups (i+2 also limit-up)
            if i + 2 < len(df):
                third_pct = df.iloc[i + 2]['pct_change'] or 0
                if self.is_limit_up(third_pct):
                    continue  # Skip, found 3 consecutive limit-ups

            # Check first board amount >= previous day amount * 2
            first_amount = df.iloc[i]['amount']
            prev_amount = df.iloc[i - 1]['amount']

            if prev_amount <= 0 or first_amount < prev_amount * self.first_board_volume_ratio:
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

    def check_signal_two(self, df: pd.DataFrame, signal_one_idx: int) -> bool:
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

    def find_signal_three(self, df: pd.DataFrame, signal_one_idx: int) -> Optional[Dict]:
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
            Dictionary with idx, close, high, amount or None if not found
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

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """Screen single stock"""
        # Get sufficient data (14 days + few days after for Signal 3 judgment)
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < 10:
            return None

        # Ensure data is sorted by date
        df = df.sort_values('trade_date').reset_index(drop=True)

        # ===== Step 1: Find Signal 1 =====
        signal_one = self.find_signal_one(df)
        if signal_one is None:
            return None

        signal_one_idx = signal_one['first_idx']
        signal_two_idx = signal_one['second_idx']

        # Check if Signal 1 is within 14-day range
        latest_date = df.iloc[-1]['trade_date']
        signal_one_date = df.iloc[signal_one_idx]['trade_date']
        days_since = (latest_date - signal_one_date).days

        if days_since > self.limit_days:
            return None  # Outside 14-day range

        # ===== Step 2: Check Signal 2 (Price Protection) =====
        if not self.check_signal_two(df, signal_one_idx):
            return None

        # ===== Step 3: Find Signal 3 (Day X) =====
        signal_three = self.find_signal_three(df, signal_one_idx)
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

        # Calculate amount ratio
        prev_amount = df.iloc[signal_one_idx - 1]['amount']
        amount_ratio = first_board['amount'] / prev_amount if prev_amount > 0 else 0

        return {
            'code': code,
            'name': name,
            'signal_one_idx': signal_one_idx,
            'signal_two_idx': signal_two_idx,
            'signal_three_idx': signal_three_idx,

            # Signal 1 features (Day T)
            't_date': first_board['trade_date'].strftime('%Y-%m-%d'),
            't_open': round(first_board['open'], 2),
            't_amount': round(first_board['amount'] / 10000, 2),  # in 10k yuan

            # Signal 2 features (Second board)
            's2_date': second_board['trade_date'].strftime('%Y-%m-%d'),
            's2_amount': round(second_board['amount'] / 10000, 2),  # in 10k yuan

            # Signal 3 features (Day X - Launch day)
            'x_date': launch_day['trade_date'].strftime('%Y-%m-%d'),
            'x_close': round(launch_day['close'], 2),
            'x_high': round(launch_day['high'], 2),
            'x_amount': round(launch_day['amount'] / 10000, 2),  # in 10k yuan

            # Max since Day T
            'max_amount_t': round(max_amount_t / 10000, 2),  # in 10k yuan
            'max_high_t': round(max_high_t, 2),

            # Additional metrics
            'prev_amount': round(prev_amount / 10000, 2),  # in 10k yuan
            'amount_ratio': round(amount_ratio, 2),
            'days_to_launch': signal_three_idx - signal_two_idx,

            'all_signals_confirmed': True
        }

    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True,
                      no_check: bool = False) -> List[Dict]:
        """Run screening"""
        if date_str:
            self.current_date = date_str

        # Check if data is available
        if not no_check and not self.check_data_availability(self.current_date):
            logger.warning(f"No available data ({self.current_date}) - Market not closed or data not downloaded")
            return []

        logger.info("="*60)
        logger.info("Two-Board Pullback Screener V4 - Er Ban Hui Tiao Screener")
        logger.info(f"Time Range: Last {self.limit_days} trading days")
        logger.info("Screening Conditions:")
        logger.info("  Signal 1: Two consecutive limit-ups + Day T amount >= prev * 2 + 2nd board < 1st board")
        logger.info("  Signal 2: Price protection - all days after Signal 1 have low >= Day T open")
        logger.info("  Signal 3: Find Day X with close up + yang line + max amount + max high since Day T")
        logger.info("="*60)

        # Get stock list (exclude Beijing Stock Exchange)
        stocks = self.get_all_stocks()
        stocks = [
            s for s in stocks
            if not s.code.startswith('8')
            and not s.code.startswith('4')
        ]

        total_stocks = len(stocks)
        logger.info(f"Total stocks: {total_stocks}")

        # Check progress tracking
        start_idx = 0
        if self.progress_tracker and not force_restart:
            if self.progress_tracker.is_resumable():
                processed_codes = self.progress_tracker.get_processed_codes()
                start_idx = len(processed_codes)
                logger.info(f"Resuming from stock {start_idx}")
            else:
                self.progress_tracker.reset()

        if self.progress_tracker:
            self.progress_tracker.start(
                total_stocks=total_stocks,
                metadata={'date': date_str or self.current_date, 'screener': self.screener_name}
            )

        results = []
        analysis_data = {}

        for i, stock in enumerate(stocks[start_idx:], start=start_idx):
            try:
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(
                        processed=i+1,
                        matched=len(results),
                        current_code=stock.code
                    )

                result = self.screen_stock(stock.code, stock.name)

                if result:
                    results.append(result)

                    if enable_analysis and self.news_fetcher:
                        news = self.fetch_news(stock.code)
                        price_data = {
                            'close': result['x_close'],
                            'pct_change': 0,
                            'turnover': 0
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis

                        logger.info(f"Found: {stock.code} {stock.name} - "
                                   f"2nd board:{result['s2_date']}, "
                                   f"launch:{result['x_date']}, "
                                   f"industry:{analysis.get('industry', 'N/A')}")
                    else:
                        logger.info(f"Found: {stock.code} {stock.name} - "
                                   f"2nd board:{result['s2_date']}, "
                                   f"launch:{result['x_date']}")

                if (i + 1) % 500 == 0:
                    logger.info(f"Progress: {i+1}/{total_stocks}, Found: {len(results)}")

            except Exception as e:
                logger.error(f"Error screening {stock.code}: {e}")
                continue

        if self.progress_tracker:
            self.progress_tracker.complete(success=True)

        logger.info(f"\n{'='*60}")
        logger.info("Screening completed!")
        logger.info(f"Checked: {total_stocks} stocks")
        logger.info(f"Matched: {len(results)} stocks")
        logger.info(f"{'='*60}")

        return results

    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """Save results"""
        column_mapping = {
            'code': 'Stock Code',
            'name': 'Stock Name',
            't_date': 'Day T Date',
            't_open': 'Day T Open',
            't_amount': 'Day T Amount (10k)',
            's2_date': '2nd Board Date',
            's2_amount': '2nd Board Amount (10k)',
            'prev_amount': 'Previous Day Amount (10k)',
            'amount_ratio': 'Day T Amount Ratio',
            'x_date': 'Day X Date',
            'x_close': 'Day X Close',
            'x_high': 'Day X High',
            'x_amount': 'Day X Amount (10k)',
            'max_amount_t': 'Max Amount Since Day T (10k)',
            'max_high_t': 'Max High Since Day T',
            'days_to_launch': 'Days to Launch',
            'all_signals_confirmed': 'All Signals Confirmed'
        }

        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='Two-Board Pullback Screener V4')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='Time range (trading days)')
    parser.add_argument('--no-news', action='store_true', help='Disable news fetching')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM analysis')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress tracking')
    parser.add_argument('--no-check', action='store_true', help='Skip data check (compatibility param)')
    parser.add_argument('--restart', action='store_true', help='Force restart')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='Database path')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    screener = ErBanHuiTiaoScreener(
        limit_days=args.limit_days,
        db_path=args.db_path or None,
        enable_news=False,  # Disable news
        enable_llm=False,   # Disable LLM
        enable_progress=not args.no_progress
    )

    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=False,  # Disable LLM analysis
        no_check=args.no_check
    )

    # Handle different return formats
    if result is None:
        results, analysis_data = [], {}
    elif isinstance(result, tuple) and len(result) == 2:
        results, analysis_data = result
    else:
        results, analysis_data = result, {}

    if results:
        output_path = screener.save_results(results, analysis_data)
        print(f"\nResults saved to: {output_path}")

        print("\n" + "="*80)
        print("Screening Results:")
        print("="*80)
        for r in results:
            analysis = analysis_data.get(r['code'], {})
            industry = analysis.get('industry', 'N/A')
            print(f"{r['code']} {r['name']} [{industry}]: "
                  f"Day T {r['t_date']}, 2nd board {r['s2_date']}, launch {r['x_date']}, "
                  f"T amount {r['t_amount']:.0f}k ({r['amount_ratio']:.1f}x), "
                  f"launch price {r['x_close']:.2f}")

        # Display download links
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'er_ban_hui_tiao_screener'
        print(f"\n{'='*60}")
        print(f"Download Links:")
        print(f"  Excel: http://localhost:{FLASK_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{FLASK_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\nNo stocks found matching the criteria")


if __name__ == '__main__':
    main()
