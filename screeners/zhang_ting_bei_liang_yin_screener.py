#!/usr/bin/env python3
"""
涨停倍量阴筛选器 (V2) - Zhang Ting Bei Liang Yin Screener (V2)

Core Logic (all 6 signals must be satisfied):

Signal 1: Limit-up with yang line, body length >= 3x of lower shadow length
- Gain >= 9.9%
- (Close - Open) >= 3 * (Open - Low)

Signal 2: Next day opens high and closes as yin line, yin body length >= 2x of (upper + lower shadow)
- Open high (Open > Previous Close)
- Yin line (Close < Open)
- (Open - Close) >= 2 * [(High - Open) + (Close - Low)]

Signal 3: Signal 2 day amount > Signal 1 day amount * 2

Signal 4: Day X (after Signal 2) with amount < Signal 2 day amount * 0.5

Signal 5: Launch signal after Day X
- Single day closes up
- Amount > Previous day amount * 2
- [New] Any day after Day T has low >= Day T open (Price Protection)

Output: Stock is output when all 6 signals are satisfied
"""

import os
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent))

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

LIMIT_DAYS = 14  # Last 14 trading days
LIMIT_UP_THRESHOLD = 9.9  # Limit-up threshold


class ZhangTingBeiLiangYinScreener(BaseScreener):
    """Zhang Ting Bei Liang Yin Screener V2"""

    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 limit_up_threshold: float = LIMIT_UP_THRESHOLD,
                 enable_price_protection: bool = True,
                 signal_one_body_ratio: float = 3.0,
                 signal_two_body_ratio: float = 2.0,
                 signal_three_volume_ratio: float = 2.0,
                 signal_four_volume_ratio: float = 0.5,
                 signal_five_volume_ratio: float = 2.0,
                 min_history_days: int = 10,
                 history_buffer_days: int = 10,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True,
                 use_pool: bool = False):
        super().__init__(
            screener_name='zhang_ting_bei_liang_yin',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.limit_up_threshold = limit_up_threshold
        self.enable_price_protection = enable_price_protection
        self.signal_one_body_ratio = signal_one_body_ratio
        self.signal_two_body_ratio = signal_two_body_ratio
        self.signal_three_volume_ratio = signal_three_volume_ratio
        self.signal_four_volume_ratio = signal_four_volume_ratio
        self.signal_five_volume_ratio = signal_five_volume_ratio
        self.min_history_days = max(1, int(min_history_days))
        self.history_buffer_days = max(0, int(history_buffer_days))
        self.use_pool = use_pool

    def get_screener_code(self) -> str:
        """Return this screener's code for DB lookup."""
        return 'zhang_ting_bei_liang_yin'

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """Return parameter schema for the screener"""
        return {
            'ENABLE_PRICE_PROTECTION': {
                'type': 'bool',
                'default': True,
                'display_name': 'Enable Price Protection',
                'description': 'Any day after Day T must have low >= Day T open',
                'group': 'Signal Conditions'
            },
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
            'SIGNAL_ONE_BODY_RATIO': {
                'type': 'float',
                'default': 3.0,
                'min': 2.0,
                'max': 5.0,
                'step': 0.5,
                'display_name': 'Signal 1 Body/Lower Shadow Ratio',
                'description': 'Signal 1 body length must be N times of lower shadow',
                'group': 'Signal Conditions'
            },
            'SIGNAL_TWO_BODY_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.5,
                'display_name': 'Signal 2 Body/(Upper+Lower Shadow) Ratio',
                'description': 'Signal 2 yin body length must be N times of (upper+lower shadow)',
                'group': 'Signal Conditions'
            },
            'SIGNAL_THREE_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': 'Signal 3 Amount Ratio',
                'description': 'Signal 2 amount must be N times of Signal 1 amount',
                'group': 'Signal Conditions'
            },
            'SIGNAL_FOUR_VOLUME_RATIO': {
                'type': 'float',
                'default': 0.5,
                'min': 0.3,
                'max': 0.7,
                'step': 0.05,
                'display_name': 'Signal 4 Low Volume Ratio',
                'description': 'Day X amount must be less than N times of Signal 2 amount',
                'group': 'Signal Conditions'
            },
            'SIGNAL_FIVE_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': 'Signal 5 Amount Ratio',
                'description': 'Launch day amount must be N times of previous day',
                'group': 'Signal Conditions'
            },
            'MIN_HISTORY_DAYS': {
                'type': 'int',
                'default': 10,
                'min': 1,
                'max': 120,
                'display_name': 'Minimum history days',
                'description': 'Minimum historical days required before screening',
                'group': 'Basic Settings'
            },
            'HISTORY_BUFFER_DAYS': {
                'type': 'int',
                'default': 10,
                'min': 0,
                'max': 120,
                'display_name': 'History buffer days',
                'description': 'Extra days added beyond LIMIT_DAYS when loading history data',
                'group': 'Basic Settings'
            }
        }

    def check_price_protection(self, df: pd.DataFrame, signal_one_idx: int) -> bool:
        """
        Check Signal 2.5 (Price Protection): Any trading day after Day T
        must have low >= Day T open price

        Args:
            df: Price data
            signal_one_idx: Index of limit-up day (Day T)

        Returns:
            True: Price protection passed (no breakdown)
            False: Price protection failed (breakdown occurred)
        """
        if not self.enable_price_protection:
            return True  # Default to pass when price protection is disabled

        if signal_one_idx < 0 or signal_one_idx >= len(df):
            return False

        # Get Day T (limit-up day) open price
        t_day_open = df.iloc[signal_one_idx]['open']

        # Check all trading days after Day T
        for i in range(signal_one_idx + 1, len(df)):
            if df.iloc[i]['low'] < t_day_open:
                # If any day has low below Day T open, price protection fails
                logger.debug(f"Price protection failed: {df.iloc[i]['trade_date']} low {df.iloc[i]['low']:.2f} < Day T open {t_day_open:.2f}")
                return False

        return True

    def is_limit_up(self, pct_change: float) -> bool:
        """Check if it's a limit-up day"""
        return pct_change >= self.limit_up_threshold

    def check_signal_one(self, df: pd.DataFrame, idx: int) -> bool:
        """
        Check Signal 1: Limit-up with yang line, body length >= 3x of lower shadow length

        Args:
            idx: Limit-up day index

        Returns:
            True: Signal 1 satisfied
            False: Not satisfied
        """
        if idx < 0 or idx >= len(df):
            return False

        row = df.iloc[idx]

        # 1. Limit-up
        if not self.is_limit_up(row['pct_change'] or 0):
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

        if body_length < lower_shadow * self.signal_one_body_ratio:
            return False

        return True

    def check_signal_two(self, df: pd.DataFrame, idx: int) -> bool:
        """
        Check Signal 2: Next day opens high and closes as yin line,
        yin body length >= 2x of (upper + lower shadow) combined length

        Args:
            idx: Signal 2 day index (day after limit-up)

        Returns:
            True: Signal 2 satisfied
            False: Not satisfied
        """
        if idx <= 0 or idx >= len(df):
            return False

        row = df.iloc[idx]
        prev_row = df.iloc[idx - 1]

        # 1. Open high (open > previous close)
        if row['open'] <= prev_row['close']:
            return False

        # 2. Yin line (close < open)
        if row['close'] >= row['open']:
            return False

        # 3. Yin body length is 2x or more of (upper + lower shadow) combined length
        # Yin body length = open - close
        # Upper shadow length = high - open
        # Lower shadow length = close - low
        body_length = row['open'] - row['close']
        upper_shadow = row['high'] - row['open']
        lower_shadow = row['close'] - row['low']

        total_shadow = upper_shadow + lower_shadow

        if total_shadow <= 0:
            return False

        if body_length < total_shadow * self.signal_two_body_ratio:
            return False

        return True

    def check_signal_three(self, df: pd.DataFrame, signal_one_idx: int, signal_two_idx: int) -> bool:
        """
        Check Signal 3: Signal 2 day amount > Signal 1 day amount * 2
        """
        if signal_one_idx < 0 or signal_two_idx >= len(df):
            return False

        signal_one_amount = df.iloc[signal_one_idx]['amount']
        signal_two_amount = df.iloc[signal_two_idx]['amount']

        return signal_two_amount > signal_one_amount * self.signal_three_volume_ratio

    def find_signal_four(self, df: pd.DataFrame, signal_one_idx: int) -> Optional[int]:
        """
        Find Signal 4: Find Day X after Signal 2 with amount < Signal 2 amount * 0.5

        Args:
            signal_one_idx: Index of limit-up day (Day T)

        Returns:
            Index of low volume day, or None if not found
        """
        signal_two_idx = signal_one_idx + 1  # Day after limit-up

        if signal_two_idx < 0 or signal_two_idx >= len(df):
            return None

        signal_two_amount = df.iloc[signal_two_idx]['amount']
        threshold = signal_two_amount * self.signal_four_volume_ratio

        # Start searching from day after Signal 2 (i.e., from Day T+2)
        for i in range(signal_two_idx + 1, len(df)):
            if df.iloc[i]['amount'] < threshold:
                return i

        return None

    def find_signal_five(self, df: pd.DataFrame, signal_four_idx: int) -> Optional[int]:
        """
        Find Signal 5: Find launch day after Day X that:
        - Closes up (pct_change > 0)
        - Is yang line (close > open)
        - Amount > Previous day amount * 2

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

            # 3. Amount > Previous day amount * 2
            if row['amount'] <= prev_row['amount'] * self.signal_five_volume_ratio:
                continue

            return i

        return None

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """Screen single stock"""
        df = self.get_stock_data(code, days=self.limit_days + self.history_buffer_days)
        if df is None or len(df) < self.min_history_days:
            return None

        # Ensure data is sorted by date
        df = df.sort_values('trade_date').reset_index(drop=True)

        # Search backwards for Signal 1 (limit-up day)
        for i in range(len(df) - 1, -1, -1):
            # Check Signal 1
            if not self.check_signal_one(df, i):
                continue

            signal_one_idx = i

            # Check if Signal 1 is within 14-day range
            latest_date = df.iloc[-1]['trade_date']
            signal_one_date = df.iloc[signal_one_idx]['trade_date']
            days_since = (latest_date - signal_one_date).days

            if days_since > self.limit_days:
                continue

            # Check Signal 2 (next day)
            signal_two_idx = signal_one_idx + 1
            if signal_two_idx >= len(df):
                continue

            if not self.check_signal_two(df, signal_two_idx):
                continue

            # Check Signal 3
            if not self.check_signal_three(df, signal_one_idx, signal_two_idx):
                continue

            # Find Signal 4 (Day X - low volume day)
            signal_four_idx = self.find_signal_four(df, signal_one_idx)
            if signal_four_idx is None:
                continue

            # Find Signal 5 (launch day)
            signal_five_idx = self.find_signal_five(df, signal_four_idx)
            if signal_five_idx is None:
                continue

            # Check Signal 2.5 (Price Protection)
            if not self.check_price_protection(df, signal_one_idx):
                logger.debug(f"Price protection failed: Signal 1 date {df.iloc[signal_one_idx]['trade_date']}")
                continue

            # All 6 signals satisfied, output result
            signal_one = df.iloc[signal_one_idx]
            signal_two = df.iloc[signal_two_idx]
            signal_four = df.iloc[signal_four_idx]
            signal_five = df.iloc[signal_five_idx]

            # Calculate K-line features
            s1_body = signal_one['close'] - signal_one['open']
            s1_lower = signal_one['open'] - signal_one['low']
            s1_ratio = round(s1_body / s1_lower, 2) if s1_lower > 0 else 0

            s2_body = signal_two['open'] - signal_two['close']
            s2_upper = signal_two['high'] - signal_two['open']
            s2_lower = signal_two['close'] - signal_two['low']
            s2_ratio = round(s2_body / (s2_upper + s2_lower), 2) if (s2_upper + s2_lower) > 0 else 0

            return {
                'code': code,
                'name': name,
                'signal_one_date': signal_one['trade_date'].strftime('%Y-%m-%d'),
                'signal_two_date': signal_two['trade_date'].strftime('%Y-%m-%d'),
                'signal_four_date': signal_four['trade_date'].strftime('%Y-%m-%d'),
                'signal_five_date': signal_five['trade_date'].strftime('%Y-%m-%d'),
                'days_to_launch': signal_five_idx - signal_one_idx,

                # Signal 1 features
                's1_open': round(signal_one['open'], 2),
                's1_close': round(signal_one['close'], 2),
                's1_low': round(signal_one['low'], 2),
                's1_body_ratio': s1_ratio,
                's1_amount': round(signal_one['amount'] / 10000, 2),

                # Signal 2 features
                's2_open': round(signal_two['open'], 2),
                's2_close': round(signal_two['close'], 2),
                's2_high': round(signal_two['high'], 2),
                's2_low': round(signal_two['low'], 2),
                's2_body_ratio': s2_ratio,
                's2_amount': round(signal_two['amount'] / 10000, 2),

                # Signal 3: Amount ratio
                'amount_ratio_s2_s1': round(signal_two['amount'] / signal_one['amount'], 2),

                # Signal 4: Day X low volume
                's4_amount': round(signal_four['amount'] / 10000, 2),
                'di_liang_ratio': round(signal_four['amount'] / signal_two['amount'], 2),

                # Signal 5: Launch day
                's5_close': round(signal_five['close'], 2),
                's5_pct_change': round(signal_five['pct_change'], 2),
                's5_amount': round(signal_five['amount'] / 10000, 2),
                's5_amount_ratio': round(signal_five['amount'] / df.iloc[signal_five_idx - 1]['amount'], 2),

                'all_signals_confirmed': True
            }

        return None

    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """Run screening"""
        if date_str:
            self.current_date = date_str

        logger.info("="*60)
        logger.info("Zhang Ting Bei Liang Yin Screener V2")
        logger.info(f"Time Range: Last {self.limit_days} trading days")
        logger.info("Price Protection:", "Enabled" if self.enable_price_protection else "Disabled")
        logger.info("Screening Conditions:")
        logger.info("  Signal 1: Limit-up with yang line, body/lower_shadow >= 3")
        logger.info("  Signal 2: Next day opens high + yin line, body/(upper+lower) >= 2")
        logger.info("  Signal 3: Signal 2 amount > Signal 1 amount * 2")
        logger.info("  Signal 4: Day X low volume, amount < Signal 2 * 0.5")
        logger.info("  Signal 5: Launch, close up + yang line + amount 2x")
        if self.enable_price_protection:
            logger.info("  Signal 2.5: Price Protection - any day after Day T has low >= Day T open")
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
                            'close': result['s5_close'],
                            'pct_change': result['s5_pct_change'],
                            'turnover': 0
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis

                        logger.info(f"Found: {stock.code} {stock.name} - "
                                   f"limit-up:{result['signal_one_date']}, "
                                   f"launch:{result['signal_five_date']}, "
                                   f"industry:{analysis.get('industry', 'N/A')}")
                    else:
                        logger.info(f"Found: {stock.code} {stock.name} - "
                                   f"limit-up:{result['signal_one_date']}, "
                                   f"launch:{result['signal_five_date']}")

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
            'signal_one_date': 'Limit-up Date',
            'signal_two_date': 'High-Volume Yin Date',
            'signal_four_date': 'Low-Volume Date',
            'signal_five_date': 'Launch Date',
            'days_to_launch': 'Days to Launch',
            's1_body_ratio': 'Signal 1 Body/Lower Shadow',
            's2_body_ratio': 'Signal 2 Body/(Upper+Lower Shadow)',
            'amount_ratio_s2_s1': 'Yin/Limit-up Amount Ratio',
            'di_liang_ratio': 'Low-Volume/Yin Amount Ratio',
            's5_pct_change': 'Launch Day Gain %',
            's5_amount_ratio': 'Launch Day Sequential Amount Ratio',
            'all_signals_confirmed': 'All Signals Confirmed'
        }

        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='Zhang Ting Bei Liang Yin Screener V2')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='Time range (trading days)')
    parser.add_argument('--no-news', action='store_true', help='Disable news fetching')
    parser.add_argument('--no-llm', action='store_true', help='Disable LLM analysis')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress tracking')
    parser.add_argument('--restart', action='store_true', help='Force restart')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='Database path')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    screener = ZhangTingBeiLiangYinScreener(
        limit_days=args.limit_days,
        db_path=args.db_path,
        enable_news=False,  # Disable news
        enable_llm=False,   # Disable LLM
        enable_progress=not args.no_progress
    )

    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=False  # Disable LLM analysis
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
                  f"limit-up {r['signal_one_date']}, yin {r['signal_two_date']}, "
                  f"launch {r['signal_five_date']}, "
                  f"body/lower {r['s1_body_ratio']:.1f}x, "
                  f"amount ratio {r['amount_ratio_s2_s1']:.1f}x")

        # Display download links
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'zhang_ting_bei_liang_yin'
        print(f"\n{'='*60}")
        print(f"Download Links:")
        from config import FLASK_PORT as _PORT
        print(f"  Excel: http://localhost:{_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\nNo stocks found matching the criteria")


if __name__ == '__main__':
    main()
