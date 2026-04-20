#!/usr/bin/env python3
"""
Screener Adapter - Unified interface for 5 screeners

This adapter provides a unified interface to call different screeners
and normalize their output for database insertion.

Author: Claude Code
Date: 2026-04-19
"""

import os
import sys
import time
import logging
import importlib
import inspect
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path

import sqlite3

# Add both scripts and backend directories to path
scripts_dir = str(Path(__file__).parent)
project_root = str(Path(__file__).parent.parent)  # NeoTrade2 directory
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import ConfigLoader from backend
from backend.config_loader import ConfigLoader

# Import screener modules directly from screeners package
from screeners import er_ban_hui_tiao_screener
from screeners import jin_feng_huang_screener
from screeners import yin_feng_huang_screener
from screeners import shi_pan_xian_screener
from screeners import zhang_ting_bei_liang_yin_screener

logger = logging.getLogger(__name__)

# Screener code mapping
# Use class names only (without '_screener' suffix)
# Modules are imported at top of file: from screeners import er_ban_hui_tiao_screener
FIVE_FLAGS_SCREENERS = {
    'er_ban_hui_tiao': 'er_ban_hui_tiao_screener',
    'jin_feng_huang': 'jin_feng_huang_screener',
    'yin_feng_huang': 'yin_feng_huang_screener',
    'shi_pan_xian': 'shi_pan_xian_screener',
    'zhang_ting_bei_liang_yin': 'zhang_ting_bei_liang_yin_screener'
}


class ScreenerAdapter:
    """Adapter to unify 5 screener interfaces"""

    def __init__(self, db_path: str = 'data/stock_data.db'):
        """
        Initialize adapter.

        Args:
            db_path: Path to stock_data.db
        """
        self.db_path = db_path
        self.screener_instances = {}
        self.screener_map = {}
        self.statistics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'by_screener': {},
            'avg_time_ms': 0
        }
        self._load_screeners()

    def _load_screeners(self) -> Dict[str, object]:
        """
        Dynamically load 5 screener classes with Dashboard configuration support.

        Strategy:
        1. Use importlib to import screener modules
        2. Load configuration from Dashboard database (screener_configs table)
        3. Instantiate screener classes with config parameters
        4. Cache instances for reuse
        5. Skip screeners that fail to load

        Returns:
            Dict mapping screener codes to screener instances
        """
        screeners = {}

        for screener_id, module_name in FIVE_FLAGS_SCREENERS.items():
            try:
                # Import screener module
                # Values in FIVE_FLAGS_SCREENERS already include '_screener' suffix
                # e.g., 'er_ban_hui_tiao_screener' maps to file 'er_ban_hui_tiao_screener.py'
                import_path = module_name  # Use key directly, no additional suffix
                module = importlib.import_module(import_path)

                # Get screener class (class name matches file name)
                screener_class_name = module_name.replace('_', ' ').title().replace(' ', '') + 'Screener'
                screener_class = getattr(module, screener_class_name)

                # Get screener's __init__ signature to only pass accepted parameters
                screener_init = screener_class.__init__
                init_params = inspect.signature(screener_init).parameters

                # Load configuration from Dashboard database
                config = ConfigLoader.load_config(screener_id, prefer_database=True)

                # Build kwargs based on what screener accepts and config
                screener_kwargs = {'db_path': self.db_path}

                # If config exists from database, extract parameters from config_json
                if config and 'config_json' in config:
                    logger.info(f"Loaded config from Dashboard for {screener_id}")
                    # Extract parameters from config_json
                    config_params = config['config_json']
                    for key, value in config_params.items():
                        screener_kwargs[key] = value
                else:
                    logger.info(f"No config found in Dashboard for {screener_id}, using defaults")

                # Optional parameters - only add if screener accepts them
                if 'enable_news' in init_params:
                    screener_kwargs['enable_news'] = False
                if 'enable_llm' in init_params:
                    screener_kwargs['enable_llm'] = False
                if 'enable_progress' in init_params:
                    screener_kwargs['enable_progress'] = False
                if 'use_pool' in init_params:
                    screener_kwargs['use_pool'] = False

                # Instantiate screener with config or default parameters
                screener_instance = screener_class(**screener_kwargs)

                screeners[screener_id] = screener_instance
                logger.info(f"Loaded screener: {screener_id}")

            except Exception as e:
                logger.error(f"Failed to load screener {screener_id}: {e}")
                screeners[screener_id] = None

        self.screener_map = screeners
        return screeners

    def get_trading_days(self, stock_code: str, start_date: str, end_date: str):
        """Get trading days for a stock within date range"""
        import sqlite3
        conn = sqlite3.connect(self.db_path, timeout=30)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE code = ?
              AND trade_date >= ?
              AND trade_date <= ?
            ORDER BY trade_date ASC
        ''', (stock_code, start_date, end_date))

        trading_days = [row[0] for row in cursor.fetchall()]
        conn.close()

        return trading_days

    def check_stock(self, screener_id: str, stock_code: str,
                  stock_name: str, date: str) -> Optional[dict]:
        """
        Call specified screener to check single stock on single day.

        Args:
            screener_id: Screener identifier (er_ban_hui_tiao, jin_feng_huang, etc.)
            stock_code: 6-digit stock code
            stock_name: Stock name
            date: Screening date in YYYY-MM-DD format

        Returns:
            Normalized dict with format:
                {
                    'matched': True,
                    'price': 12.50,
                    'reason': 'Match reason description',
                    'details': {
                        'screener_specific_field1': value1,
                        'screener_specific_field2': value2
                    }
                }
            Returns None if no match
        """
        start_time = time.time()

        # Check if screener is available
        screener = self.screener_map.get(screener_id)
        if screener is None:
            logger.error(f"Screener {screener_id} not available")
            return None

        # Update statistics
        self.statistics['total_calls'] += 1
        if screener_id not in self.statistics['by_screener']:
            self.statistics['by_screener'][screener_id] = {
                'calls': 0,
                'successes': 0,
                'failures': 0
            }
        self.statistics['by_screener'][screener_id]['calls'] += 1

        # Set current date for screener
        screener.current_date = date

        # Call screener with retry logic
        result = self._call_screener_with_retry(screener, screener_id, stock_code, stock_name)

        # Update statistics
        elapsed_ms = (time.time() - start_time) * 1000
        self._update_avg_time(elapsed_ms)

        if result is not None:
            self.statistics['successful_calls'] += 1
            self.statistics['by_screener'][screener_id]['successes'] += 1
            logger.info(f"Match: {screener_id} - {stock_code} - {result.get('reason', 'Unknown')}")
        else:
            self.statistics['failed_calls'] += 1
            self.statistics['by_screener'][screener_id]['failures'] += 1

        return result

    def _call_screener_with_retry(self, screener: object, screener_id: str,
                                  stock_code: str, stock_name: str,
                                  max_retries: int = 2) -> Optional[dict]:
        """
        Call screener with retry mechanism.

        Strategy:
        1. Try up to max_retries times
        2. Exponential backoff between retries (1s, 2s)
        3. Catch and log all exceptions
        4. Return None if all retries fail

        Args:
            screener: Screener instance
            screener_id: Screener identifier for logging
            stock_code: Stock code
            stock_name: Stock name
            max_retries: Maximum number of retry attempts

        Returns:
            Normalized result dict or None if failed
        """
        for attempt in range(max_retries):
            try:
                # Call screener's screen_stock method
                screener_result = screener.screen_stock(stock_code, stock_name)

                if screener_result is not None:
                    # Normalize screener output to unified format
                    return self._normalize_screener_output(screener_id, screener_result)

                return None

            except Exception as e:
                logger.warning(
                    f"Screener {screener_id} call attempt {attempt + 1}/{max_retries} "
                    f"failed for {stock_code}: {e}"
                )

                # Backoff before retry
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s

        # All retries failed
        logger.error(f"Screener {screener_id} failed for {stock_code} after {max_retries} attempts")
        return None

    def _normalize_screener_output(self, screener_id: str,
                                  screener_result: dict) -> dict:
        """
        Normalize different screener outputs to unified format.

        Strategy:
        1. Extract common fields: code, name, price
        2. Generate reason description based on screener type
        3. Preserve all screener-specific details in details dict
        4. Ensure price is extracted correctly from different key names

        Args:
            screener_id: Screener identifier
            screener_result: Raw screener output dict

        Returns:
            Unified format dict
        """
        # Extract price from different key names across screeners
        price = None
        if screener_id == 'er_ban_hui_tiao':
            # Two-Board Pullback Screener uses 'x_close' for launch price
            price = screener_result.get('x_close') or screener_result.get('close')
            # If still None, check other common keys
            if price is None:
                price = screener_result.get('close_price') or 0.0
            reason = f"Two consecutive limit-up boards (Day T: {screener_result.get('t_date')})"
        elif screener_id == 'jin_feng_huang':
            # Golden Phoenix Screener uses 's5_close' for launch price
            price = screener_result.get('s5_close')
            # If still None, check other common keys
            if price is None:
                price = screener_result.get('close_price') or 0.0
            reason = f"Golden Phoenix pattern (limit-up: {screener_result.get('signal_one_date')}, launch: {screener_result.get('signal_five_date')})"
        elif screener_id == 'yin_feng_huang':
            # Silver Phoenix Screener uses 's4_close' for launch price
            price = screener_result.get('s4_close')
            # If still None, check other common keys
            if price is None:
                price = screener_result.get('close_price') or 0.0
            reason = f"Silver Phoenix pattern (limit-up: {screener_result.get('signal_one_date')}, launch: {screener_result.get('signal_four_date')})"
        elif screener_id == 'shi_pan_xian':
            # Test Line Screener uses 'close_price' for current price
            price = screener_result.get('current_price') or screener_result.get('close_price')
            reason = f"Test line pattern (high volume: {screener_result.get('high_volume_date')}, limit-up: {screener_result.get('limit_up_date')})"
        else:
            price = screener_result.get('price') or 0.0
            reason = f"Pattern matched by {screener_id}"

        # Build unified output
        return {
            'matched': True,
            'screener_id': screener_id,
            'code': screener_result.get('code'),
            'name': screener_result.get('name'),
            'price': price,
            'reason': reason,
            'details': screener_result  # Preserve all screener-specific details
        }

    def _update_avg_time(self, elapsed_ms: float):
        """
        Update average time per call.

        Strategy: Exponential moving average for smooth tracking
        """
        current_avg = self.statistics['avg_time_ms']
        alpha = 0.1  # Smoothing factor
        self.statistics['avg_time_ms'] = current_avg * (1 - alpha) + elapsed_ms * alpha

    def get_statistics(self) -> dict:
        """
        Get current adapter statistics.

        Returns:
            Dict with call counts, success rates, timing, and per-screener stats
        """
        if self.statistics['total_calls'] == 0:
            return self.statistics

        # Calculate success rate
        success_rate = self.statistics['successful_calls'] / self.statistics['total_calls']

        # Calculate per-screener success rates
        for screener_id, stats in self.statistics['by_screener'].items():
            if stats['calls'] > 0:
                stats['success_rate'] = stats['successes'] / stats['calls']

        return {
            **self.statistics,
            'success_rate': success_rate
        }

    def reset_statistics(self):
        """Reset statistics counters."""
        self.statistics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'by_screener': {},
            'avg_time_ms': 0
        }


def main():
    """Test adapter functionality."""
    import logging
    logging.basicConfig(level=logging.INFO)

    adapter = ScreenerAdapter('data/stock_data.db')
    stats = adapter.get_statistics()

    print("Screener Adapter Statistics:")
    print(f"Total calls: {stats['total_calls']}")
    print(f"Successful calls: {stats['successful_calls']}")
    print(f"Failed calls: {stats['failed_calls']}")
    print(f"Average time: {stats['avg_time_ms']:.2f}ms")
    print(f"Success rate: {stats['success_rate']:.2%}")

    print("\nPer-screener statistics:")
    for screener_id, stats in stats['by_screener'].items():
        print(f"  {screener_id}: {stats['calls']} calls, {stats['successes']} matches")

if __name__ == '__main__':
    main()
