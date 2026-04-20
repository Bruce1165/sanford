#!/usr/bin/env python3
"""
Five Flags Pool Screening - Main script for parallel processing

This script provides:
1. Parallel processing of stock pools across multiple screener types
2. Batch insertion for optimal database performance
3. Progress tracking with checkpoint/resume capability
4. Comprehensive logging and error handling
5. Performance monitoring and statistics

Author: Claude Code
Date: 2026-04-19
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
# Add project root to path for screeners module
sys.path.insert(0, str(Path(__file__).parent.parent))

from pool_screener_adapter import ScreenerAdapter
from database.lao_ya_tou_pool import LaoYaTouPoolRepository
from database.lao_ya_tou_five_flags import LaoYaTouFiveFlagsRepository

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_WORKERS = min(cpu_count(), 4)
BATCH_INSERT_SIZE = 100
PROGRESS_SAVE_INTERVAL = 100
DEFAULT_DB_PATH = 'data/stock_data.db'
PROGRESS_FILE = 'data/five_flags_screening_progress.json'

# Screener codes to use
FIVE_FLAGS_SCREENERS = [
    'er_ban_hui_tiao',
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'zhang_ting_bei_liang_yin'
]


class FiveFlagsPoolScreening:
    """Five flags pool screening manager with parallel processing"""

    def __init__(self, db_path: str = DEFAULT_DB_PATH,
                 max_workers: int = None,
                 progress_file: str = PROGRESS_FILE):
        self.db_path = db_path
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.progress_file = progress_file
        self.adapter = ScreenerAdapter(db_path)
        self.pool_repo = LaoYaTouPoolRepository(db_path)
        self.flags_repo = LaoYaTouFiveFlagsRepository(db_path)

        self.progress = {
            'start_time': None,
            'last_update': None,
            'total_stocks': 0,
            'processed_stocks': 0,
            'failed_stocks': 0,
            'processed_pool_ids': [],
            'statistics': {
                'total_matches': 0,
                'by_screener': {s: 0 for s in FIVE_FLAGS_SCREENERS}
            }
        }

    def load_progress_file(self) -> dict:
        if Path(self.progress_file).exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            'start_time': None,
            'last_update': None,
            'total_stocks': 0,
            'processed_stocks': 0,
            'failed_stocks': 0,
            'processed_pool_ids': [],
            'statistics': {
                'total_matches': 0,
                'by_screener': {s: 0 for s in FIVE_FLAGS_SCREENERS}
            }
        }

    def save_progress_file(self):
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def get_pools_to_screen(self, pool_ids: Optional[List[int]] = None) -> List[dict]:
        if pool_ids is not None:
            pools = self.pool_repo.find_pools_by_ids(pool_ids)
        else:
            pools = self.pool_repo.find_unprocessed_pools()

        return pools

    def screen_stock_range(self, pool_data: dict, screener_id: str) -> Optional[dict]:
        """
        Screen a single stock across all trading days.

        Check each trading day in the stock's date range and record ALL matches.
        Do NOT break - we need all matching signals, not just the first one.
        """
        trading_days = self.adapter.get_trading_days(
            pool_data['stock_code'],
            pool_data['start_date'],
            pool_data['end_date']
        )

        if not trading_days:
            return None

        results = []

        for trade_date in trading_days:
            try:
                result = self.adapter.check_stock(
                    screener_id=screener_id,
                    stock_code=pool_data['stock_code'],
                    stock_name=pool_data['stock_name'],
                    date=trade_date
                )

                if result and 'matched' in result and result['matched']:
                    # Record all matches - price will be filled from database later if needed
                    results.append({
                        'pool_id': pool_data['id'],
                        'screener_id': screener_id,
                        'stock_code': pool_data['stock_code'],
                        'stock_name': pool_data['stock_name'],
                        'screen_date': trade_date,
                        'close_price': result.get('price', 0.0),
                        'match_reason': result.get('reason', ''),
                        'extra_data': {}  # Empty dict for extra_data field
                    })

            except Exception as e:
                logger.warning(
                    f"Error screening {pool_data['stock_code']} on {trade_date} "
                    f"with {screener_id}: {e}"
                )

        return {
            'results': results
        } if results else None

    def _process_stock_batch(self, results: List[dict]) -> int:
        if not results:
            return 0

        inserted_count = self.flags_repo.insert_flag_results_batch(results)
        return inserted_count

    def distribute_tasks_to_workers(self, pools: List[dict], screener_id: str) -> List[List[dict]]:
        pool_count = len(pools)
        task_size = max(1, pool_count // self.max_workers)

        tasks = []
        for worker_id in range(self.max_workers):
            worker_tasks = pools[worker_id * task_size: (worker_id + 1) * task_size]
            tasks.append(worker_tasks)

        return tasks

    def process_pool_batch(self, pool_batch: List[dict]) -> dict:
        """
        Process pools with all 5 screeners using parallel workers.

        For each pool:
        1. Run all 5 screeners in parallel
        2. Collect ALL matches from each screener (not just first match)
        3. Mark pool as processed
        """
        all_results = []

        for pool_data in pool_batch:
            # For each pool, run all 5 screeners
            # Use ThreadPoolExecutor to run 5 screeners in parallel for this pool
            screener_results = []
            with ThreadPoolExecutor(max_workers=min(len(FIVE_FLAGS_SCREENERS), self.max_workers)) as executor:
                futures = {
                    executor.submit(self.screen_stock_range, pool_data, screener_id)
                    for screener_id in FIVE_FLAGS_SCREENERS
                }

                for future in as_completed(futures):
                    try:
                        task_data = future.result()
                        if task_data and 'results' in task_data and task_data['results']:
                            screener_results.extend(task_data['results'])
                    except Exception as e:
                        logger.error(f"Error in screener result: {e}")

            # Log matches found for this pool
            screener_summary = {}
            for result in screener_results:
                screener_id = result['screener_id']
                if screener_id not in screener_summary:
                    screener_summary[screener_id] = 0
                screener_summary[screener_id] += 1

            if screener_summary:
                logger.info(
                    f"Pool {pool_data['id']} ({pool_data['stock_code']}): "
                    f"matches - {screener_summary}"
                )

            all_results.extend(screener_results)

            # Mark this pool as processed after all 5 screeners complete
            try:
                self.pool_repo.mark_as_processed(pool_data['id'])
                logger.info(f"Pool {pool_data['id']} marked as processed")
            except Exception as e:
                logger.error(f"Failed to mark pool {pool_data['id']} as processed: {e}")

        # Batch insert all results
        total_inserted = 0
        batch = []
        for result in all_results:
            batch.append(result)
            if len(batch) >= BATCH_INSERT_SIZE:
                total_inserted += self._process_stock_batch(batch)
                batch = []

        if batch:
            total_inserted += self._process_stock_batch(batch)

        # Count results by screener
        screener_counts = {}
        for result in all_results:
            screener_id = result['screener_id']
            if screener_id not in screener_counts:
                screener_counts[screener_id] = 0
            screener_counts[screener_id] += 1

        return {
            'total_stocks': len(pool_batch),
            'processed_stocks': total_inserted,
            'failed_stocks': len(pool_batch) - total_inserted,
            'by_screener': screener_counts
        }

    def run_screening(self, pool_ids: Optional[List[int]] = None) -> dict:
        """
        Run screening for all pools with 5 screeners.

        Logic:
        1. Get pools to screen
        2. For each pool:
           - Run all 5 screeners in parallel
           - Collect ALL matches from each screener (not just first match)
           - Check all trading days (do NOT break after first match)
           - Mark pool as processed
        3. Batch insert all results
        """
        self.progress['start_time'] = datetime.now().isoformat()

        pools = self.get_pools_to_screen(pool_ids)

        logger.info(f"Starting screening for {len(pools)} pools with {len(FIVE_FLAGS_SCREENERS)} screeners")

        # Process all pools with all 5 screeners
        results = self.process_pool_batch(pools)

        # Update progress
        self.progress['total_stocks'] = results['total_stocks']
        self.progress['processed_stocks'] = results['processed_stocks']
        self.progress['failed_stocks'] = results['failed_stocks']
        self.progress['statistics'] = {
            'total_matches': results['processed_stocks'],
            'by_screener': results.get('by_screener', {})
        }

        self.save_progress_file()

        return {
            'total_stocks': self.progress['total_stocks'],
            'processed_stocks': self.progress['processed_stocks'],
            'failed_stocks': self.progress['failed_stocks'],
            'by_screener': results.get('by_screener', {})
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Five Flags Pool Screening')
    parser.add_argument('--max-workers', type=int, default=DEFAULT_MAX_WORKERS,
                       help='Maximum number of worker processes')
    parser.add_argument('--pool-ids', type=str,
                       help='Specific pool IDs to screen (comma-separated)')
    args = parser.parse_args()

    screening = FiveFlagsPoolScreening(
        db_path=DEFAULT_DB_PATH,
        max_workers=args.max_workers
    )

    pool_ids = [int(pid.strip()) for pid in args.pool_ids.split(',')] if args.pool_ids else None
    result = screening.run_screening(pool_ids=pool_ids)

    print("=" * 60)
    print(f"Five Flags Pool Screening completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total stocks processed: {result['total_stocks']}")
    print(f"Total matches found: {result['processed_stocks']}")
    print(f"Total failed: {result['failed_stocks']}")
    print()
    for screener_id, matches in result['by_screener'].items():
        print(f"  {screener_id}: {matches} matches")
