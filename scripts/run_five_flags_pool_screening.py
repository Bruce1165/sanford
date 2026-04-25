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
import hashlib
import re
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
# Add project root to path for screeners module
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    # Preferred import path to avoid shadowing by scripts/database.py
    from scripts.pool_screener_adapter import ScreenerAdapter
    from scripts.database.lao_ya_tou_pool import LaoYaTouPoolRepository
    from scripts.database.lao_ya_tou_five_flags import LaoYaTouFiveFlagsRepository
except Exception:
    # Backward-compatible fallback
    from pool_screener_adapter import ScreenerAdapter
    from database.lao_ya_tou_pool import LaoYaTouPoolRepository
    from database.lao_ya_tou_five_flags import LaoYaTouFiveFlagsRepository

try:
    from scripts.trading_calendar import (
        get_recent_trading_day,
        get_next_trading_day,
        is_trading_day,
        get_latest_db_trade_date
    )
except Exception:
    from trading_calendar import (
        get_recent_trading_day,
        get_next_trading_day,
        is_trading_day,
        get_latest_db_trade_date
    )

try:
    from scripts.flow_engine.flow_config import load_flow_plan
except Exception:
    from flow_engine.flow_config import load_flow_plan

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_WORKERS = min(cpu_count(), 4)
BATCH_INSERT_SIZE = 100
PROGRESS_SAVE_INTERVAL = 100
DEFAULT_DB_PATH = 'data/stock_data.db'
PROGRESS_FILE = 'data/five_flags_screening_progress.json'
DEFAULT_PHASE_PROFILE = 'config/screeners/market_phase_profiles.json'
VALID_MARKET_PHASES = {
    'WAVE_1', 'WAVE_2', 'WAVE_3', 'WAVE_4', 'WAVE_5',
    'WAVE_A', 'WAVE_B', 'WAVE_C'
}
VALID_PROFILE_SLOTS = {'active', 'candidate'}

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
                 progress_file: str = PROGRESS_FILE,
                 flow_config_file: Optional[str] = None,
                 market_phase: Optional[str] = None,
                 phase_profile_file: Optional[str] = None,
                 profile_slot: str = 'active',
                 calibration_note: Optional[str] = None,
                 as_of_date: Optional[str] = None):
        self.db_path = db_path
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.progress_file = progress_file
        self.flow_config_file = flow_config_file
        self.market_phase = (market_phase or '').strip().upper() or None
        self.phase_profile_file = phase_profile_file
        self.profile_slot = (profile_slot or 'active').strip().lower()
        self.calibration_note = (calibration_note or '').strip() or None
        self.flow_batches, self.flow_id, self.flow_plan_type = self._resolve_flow_batches()
        self.phase_overrides, self.phase_context = self._resolve_phase_overrides()
        self.target_trade_date = self._resolve_target_trade_date(as_of_date)

        self.adapter = ScreenerAdapter(db_path, screener_overrides=self.phase_overrides)
        self.pool_repo = LaoYaTouPoolRepository(db_path)
        self.flags_repo = LaoYaTouFiveFlagsRepository(db_path)
        self._a_share_valid_cache: Dict[str, Tuple[bool, str]] = {}

        self.progress = {
            'start_time': None,
            'last_update': None,
            'total_stocks': 0,
            'processed_stocks': 0,
            'failed_stocks': 0,
            'flow_id': self.flow_id,
            'flow_plan_type': self.flow_plan_type,
            'market_phase': self.phase_context.get('resolved_phase'),
            'phase_param_profile': self.phase_context,
            'profile_slot': self.phase_context.get('profile_slot'),
            'profile_version': self.phase_context.get('profile_version'),
            'calibration_note': self.calibration_note,
            'target_trade_date': self.target_trade_date,
            'total_levels': len(self.flow_batches),
            'current_level': None,
            'level_duration_ms': {},
            'processed_pool_ids': [],
            'statistics': {
                'total_matches': 0,
                'by_screener': {s: 0 for s in FIVE_FLAGS_SCREENERS}
            }
        }

    @staticmethod
    def _parse_date_str(value: str) -> Optional[date]:
        if not value:
            return None
        text = str(value).strip()[:10]
        if not text:
            return None
        try:
            return datetime.strptime(text, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _resolve_target_trade_date(self, as_of_date: Optional[str]) -> str:
        if as_of_date:
            dt = self._parse_date_str(as_of_date)
            if dt is None:
                raise ValueError(f"invalid as_of_date: {as_of_date}, expected YYYY-MM-DD")
            calendar_target = get_recent_trading_day(dt)
        else:
            calendar_target = get_recent_trading_day(date.today())

        latest_db_trade_date = self._get_latest_trade_date_from_db()
        if latest_db_trade_date is not None and latest_db_trade_date < calendar_target:
            logger.info(
                "Price data lag detected, fallback target_trade_date from %s to latest_db_trade_date %s",
                calendar_target.strftime('%Y-%m-%d'),
                latest_db_trade_date.strftime('%Y-%m-%d')
            )
            return latest_db_trade_date.strftime('%Y-%m-%d')
        return calendar_target.strftime('%Y-%m-%d')

    def _get_latest_trade_date_from_db(self) -> Optional[date]:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            row = conn.execute('SELECT MAX(trade_date) FROM daily_prices').fetchone()
            if not row or row[0] is None:
                return None
            value = str(row[0])[:10]
            dt = self._parse_date_str(value)
            return dt
        except Exception as exc:
            logger.warning("Failed to resolve latest trade date from %s: %s", self.db_path, exc)
            return None
        finally:
            if conn is not None:
                conn.close()

    def _resolve_pool_start_date(self, pool_data: dict) -> Optional[str]:
        """
        Resolve catch-up start date with user-confirmed priority:
        1) last_screened_date + next trading day
        2) start_date
        """
        last_screened = self._parse_date_str(pool_data.get('last_screened_date'))
        if last_screened is not None:
            return get_next_trading_day(last_screened).strftime('%Y-%m-%d')

        start_date_value = self._parse_date_str(pool_data.get('start_date'))
        if start_date_value is not None:
            if is_trading_day(start_date_value):
                return start_date_value.strftime('%Y-%m-%d')
            return get_next_trading_day(start_date_value - timedelta(days=1)).strftime('%Y-%m-%d')
        return None

    def _is_valid_a_share_stock(self, pool_data: dict) -> Tuple[bool, str]:
        """
        Preconditions for five-flags catch-up:
        - stock code is 6 digits
        - stock exists in stocks table
        - stock is not delisted
        - stock is not a Shenzhen index code (399xxx)
        """
        code = str(pool_data.get('stock_code') or '').strip()
        if code in self._a_share_valid_cache:
            return self._a_share_valid_cache[code]

        if not re.fullmatch(r'\d{6}', code):
            result = (False, 'invalid_code')
            self._a_share_valid_cache[code] = result
            return result
        if code.startswith('399'):
            result = (False, 'index_code')
            self._a_share_valid_cache[code] = result
            return result

        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                '''
                SELECT code, COALESCE(is_delisted, 0) AS is_delisted
                FROM stocks
                WHERE code = ?
                ''',
                (code,)
            ).fetchone()
            if row is None:
                result = (False, 'not_in_stocks')
            elif int(row['is_delisted']) == 1:
                result = (False, 'delisted')
            else:
                result = (True, 'ok')
            self._a_share_valid_cache[code] = result
            return result
        except Exception as exc:
            logger.warning("A-share validation failed for %s: %s", code, exc)
            result = (False, 'validate_error')
            self._a_share_valid_cache[code] = result
            return result
        finally:
            if conn is not None:
                conn.close()

    def _resolve_flow_batches(self):
        default_flow = Path(__file__).parent / 'flow_engine' / 'default_five_flags_dag.json'
        flow_path = self.flow_config_file or str(default_flow)
        batches, flow_id, plan_type = load_flow_plan(flow_path, FIVE_FLAGS_SCREENERS)
        return batches, flow_id, plan_type

    def _normalize_phase_profile(self, loaded: Dict) -> Dict:
        # Backward compatibility: old format was {"default": {...}, "WAVE_1": {...}}.
        if 'profiles' in loaded and isinstance(loaded.get('profiles'), dict):
            normalized = loaded
        else:
            profiles = {}
            for key, value in loaded.items():
                if not isinstance(value, dict):
                    continue
                phase_key = str(key).strip().upper()
                if phase_key == 'DEFAULT':
                    phase_key = 'default'
                profiles[phase_key] = {'active': value, 'candidate': {}}
            normalized = {'metadata': {}, 'profiles': profiles}

        metadata = normalized.get('metadata') if isinstance(normalized.get('metadata'), dict) else {}
        profiles = normalized.get('profiles') if isinstance(normalized.get('profiles'), dict) else {}
        final_profiles = {}
        for key, value in profiles.items():
            phase_key = str(key).strip().upper()
            if phase_key == 'DEFAULT':
                phase_key = 'default'
            if phase_key != 'default' and phase_key not in VALID_MARKET_PHASES:
                continue
            entry = value if isinstance(value, dict) else {}
            active = entry.get('active') if isinstance(entry.get('active'), dict) else {}
            candidate = entry.get('candidate') if isinstance(entry.get('candidate'), dict) else {}
            final_profiles[phase_key] = {'active': active, 'candidate': candidate}
        if 'default' not in final_profiles:
            final_profiles['default'] = {'active': {}, 'candidate': {}}
        return {'metadata': metadata, 'profiles': final_profiles}

    def _resolve_phase_overrides(self) -> Tuple[Dict[str, Dict], Dict]:
        profile_path = self.phase_profile_file or str(Path(__file__).parent.parent / DEFAULT_PHASE_PROFILE)
        profile_file = Path(profile_path)
        profile_data = {'metadata': {}, 'profiles': {'default': {'active': {}, 'candidate': {}}}}
        if profile_file.exists():
            with open(profile_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    profile_data = self._normalize_phase_profile(loaded)
        elif self.market_phase:
            raise FileNotFoundError(f"phase profile file not found: {profile_path}")

        if self.market_phase and self.market_phase not in VALID_MARKET_PHASES:
            raise ValueError(
                f"invalid market_phase: {self.market_phase}, allowed: {', '.join(sorted(VALID_MARKET_PHASES))}"
            )
        if self.profile_slot not in VALID_PROFILE_SLOTS:
            raise ValueError(
                f"invalid profile_slot: {self.profile_slot}, allowed: {', '.join(sorted(VALID_PROFILE_SLOTS))}"
            )

        profiles = profile_data.get('profiles') or {}
        requested_phase = self.market_phase
        resolved_phase = requested_phase
        fallback_to_default = False
        if requested_phase and requested_phase not in profiles:
            resolved_phase = 'default'
            fallback_to_default = True
        if not resolved_phase:
            resolved_phase = 'default' if 'default' in profiles else None

        phase_entry = profiles.get(resolved_phase, {}) if resolved_phase else {}
        raw_overrides = phase_entry.get(self.profile_slot, {}) if isinstance(phase_entry, dict) else {}
        overrides = {}
        if isinstance(raw_overrides, dict):
            for screener_id, params in raw_overrides.items():
                if screener_id in FIVE_FLAGS_SCREENERS and isinstance(params, dict):
                    overrides[screener_id] = params

        profile_version = profile_data.get('metadata', {}).get('version')
        if not profile_version:
            digest_source = json.dumps(raw_overrides, sort_keys=True, ensure_ascii=False)
            profile_version = f"sha1:{hashlib.sha1(digest_source.encode('utf-8')).hexdigest()[:12]}"

        context = {
            'profile_file': str(profile_file),
            'requested_phase': requested_phase,
            'resolved_phase': resolved_phase,
            'profile_slot': self.profile_slot,
            'profile_version': profile_version,
            'fallback_to_default': fallback_to_default,
            'override_screeners': sorted(list(overrides.keys()))
        }
        return overrides, context

    def load_progress_file(self) -> dict:
        default_progress = {
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
        if Path(self.progress_file).exists():
            try:
                raw = Path(self.progress_file).read_text(encoding='utf-8').strip()
                if not raw:
                    return default_progress
                loaded = json.loads(raw)
                return loaded if isinstance(loaded, dict) else default_progress
            except Exception:
                return default_progress
        return default_progress

    def save_progress_file(self):
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def get_pools_to_screen(self, pool_ids: Optional[List[int]] = None) -> List[dict]:
        if pool_ids is not None:
            pools = self.pool_repo.find_pools_by_ids(pool_ids)
        else:
            pools = self.pool_repo.find_all_pools_for_screening()

        return pools

    def screen_stock_range(self, pool_data: dict, screener_id: str, trading_days: List[str]) -> Optional[dict]:
        """
        Screen a single stock across all trading days.

        Check each trading day in the stock's date range and record ALL matches.
        Do NOT break - we need all matching signals, not just the first one.
        """
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
                    details = result.get('details') if isinstance(result, dict) else None
                    extra_data = {'details': details} if isinstance(details, dict) else {}
                    # Record all matches - price will be filled from database later if needed
                    results.append({
                        'pool_id': pool_data['id'],
                        'screener_id': screener_id,
                        'stock_code': pool_data['stock_code'],
                        'stock_name': pool_data['stock_name'],
                        'screen_date': trade_date,
                        'close_price': result.get('price', 0.0),
                        'match_reason': result.get('reason', ''),
                        'extra_data': extra_data
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
        processed_pools = 0
        failed_pools = 0
        level_timing = {idx: 0.0 for idx in range(1, len(self.flow_batches) + 1)}

        for pool_data in pool_batch:
            if pool_data.get('id') in set(self.progress.get('processed_pool_ids') or []):
                logger.info("Pool %s skipped: already processed in progress file", pool_data.get('id'))
                continue
            pool_failed = False
            is_valid_stock, invalid_reason = self._is_valid_a_share_stock(pool_data)
            if not is_valid_stock:
                logger.info(
                    "Pool %s (%s) skipped: invalid A-share stock (%s)",
                    pool_data.get('id'),
                    pool_data.get('stock_code'),
                    invalid_reason
                )
                failed_pools += 1
                continue
            start_date = self._resolve_pool_start_date(pool_data)
            end_date = self.target_trade_date
            if not start_date:
                logger.warning(
                    "Pool %s (%s) skipped: start_date is required when last_screened_date is absent",
                    pool_data.get('id'),
                    pool_data.get('stock_code')
                )
                failed_pools += 1
                continue
            if start_date > end_date:
                logger.info(
                    "Pool %s (%s) up-to-date: start=%s, end=%s",
                    pool_data.get('id'),
                    pool_data.get('stock_code'),
                    start_date,
                    end_date
                )
                processed_pools += 1
                continue

            catchup_days = self.adapter.get_trading_days(
                pool_data['stock_code'],
                start_date,
                end_date
            )
            if not catchup_days:
                logger.info(
                    "Pool %s (%s) no trading data in range %s -> %s",
                    pool_data.get('id'),
                    pool_data.get('stock_code'),
                    start_date,
                    end_date
                )
                continue

            # For each pool, run configured flow batches. Screeners inside one batch run in parallel.
            screener_results = []
            for level_index, batch in enumerate(self.flow_batches, start=1):
                # Persist DAG runtime progress so API can expose current level in real time.
                self.progress['current_level'] = {
                    'index': level_index,
                    'total': len(self.flow_batches),
                    'screeners': list(batch)
                }
                self.progress['last_update'] = datetime.now().isoformat()
                self.save_progress_file()

                level_start = time.time()
                with ThreadPoolExecutor(max_workers=min(len(batch), self.max_workers)) as executor:
                    futures = {
                        executor.submit(self.screen_stock_range, pool_data, screener_id, catchup_days)
                        for screener_id in batch
                    }

                    for future in as_completed(futures):
                        try:
                            task_data = future.result()
                            if task_data and 'results' in task_data and task_data['results']:
                                screener_results.extend(task_data['results'])
                        except Exception as e:
                            logger.error(f"Error in screener result: {e}")
                            pool_failed = True
                elapsed_ms = (time.time() - level_start) * 1000
                level_timing[level_index] += elapsed_ms
                self.progress['level_duration_ms'] = {str(k): round(v, 2) for k, v in level_timing.items()}
                self.progress['last_update'] = datetime.now().isoformat()
                self.save_progress_file()

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
                self.pool_repo.update_last_screened_date(pool_data['id'], catchup_days[-1])
                logger.info(
                    "Pool %s marked screened to %s",
                    pool_data['id'],
                    catchup_days[-1]
                )
                self.progress.setdefault('processed_pool_ids', [])
                if pool_data['id'] not in self.progress['processed_pool_ids']:
                    self.progress['processed_pool_ids'].append(pool_data['id'])
                if pool_failed:
                    failed_pools += 1
                else:
                    processed_pools += 1
            except Exception as e:
                logger.error(f"Failed to mark pool {pool_data['id']} as processed: {e}")
                failed_pools += 1

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
            'processed_stocks': processed_pools,
            'failed_stocks': failed_pools,
            'total_matches': total_inserted,
            'by_screener': screener_counts,
            'level_duration_ms': {str(k): round(v, 2) for k, v in level_timing.items()}
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
        existing_progress = self.load_progress_file()
        if isinstance(existing_progress, dict):
            processed_pool_ids = existing_progress.get('processed_pool_ids')
            if isinstance(processed_pool_ids, list):
                self.progress['processed_pool_ids'] = list({int(x) for x in processed_pool_ids if isinstance(x, int) or str(x).isdigit()})

        self.progress['start_time'] = datetime.now().isoformat()

        pools = self.get_pools_to_screen(pool_ids)
        if self.progress.get('processed_pool_ids'):
            pools = [p for p in pools if p.get('id') not in set(self.progress['processed_pool_ids'])]

        logger.info(f"Starting screening for {len(pools)} pools with {len(FIVE_FLAGS_SCREENERS)} screeners")
        logger.info(
            f"Flow config loaded: {self.flow_id}, type={self.flow_plan_type}, batches={self.flow_batches}"
        )

        # Safety guard: never proceed if any screener failed to load.
        unavailable = [s for s, inst in self.adapter.screener_map.items() if inst is None]
        if unavailable:
            raise RuntimeError(f"Screeners unavailable: {', '.join(unavailable)}")

        # Process all pools with all 5 screeners
        results = self.process_pool_batch(pools)

        # Update progress
        self.progress['total_stocks'] = results['total_stocks']
        self.progress['processed_stocks'] = results['processed_stocks']
        self.progress['failed_stocks'] = results['failed_stocks']
        self.progress['statistics'] = {
            'total_matches': results['total_matches'],
            'by_screener': results.get('by_screener', {})
        }
        self.progress['level_duration_ms'] = results.get('level_duration_ms', {})
        self.progress['current_level'] = None
        self.progress['last_update'] = datetime.now().isoformat()

        self.save_progress_file()

        return {
            'total_stocks': self.progress['total_stocks'],
            'processed_stocks': self.progress['processed_stocks'],
            'failed_stocks': self.progress['failed_stocks'],
            'total_matches': self.progress['statistics']['total_matches'],
            'by_screener': results.get('by_screener', {}),
            'level_duration_ms': self.progress.get('level_duration_ms', {}),
            'market_phase': self.progress.get('market_phase'),
            'phase_param_profile': self.progress.get('phase_param_profile', {}),
            'profile_slot': self.progress.get('profile_slot'),
            'profile_version': self.progress.get('profile_version'),
            'calibration_note': self.progress.get('calibration_note')
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Five Flags Pool Screening')
    parser.add_argument('--max-workers', type=int, default=DEFAULT_MAX_WORKERS,
                       help='Maximum number of worker processes')
    parser.add_argument('--pool-ids', type=str,
                       help='Specific pool IDs to screen (comma-separated)')
    parser.add_argument('--flow-config', type=str,
                       help='Flow config file path (JSON). Default uses scripts/flow_engine/default_five_flags_dag.json')
    parser.add_argument('--market-phase', type=str,
                        help='Market phase enum: WAVE_1/WAVE_2/WAVE_3/WAVE_4/WAVE_5/WAVE_A/WAVE_B/WAVE_C')
    parser.add_argument('--phase-profile', type=str,
                        help='Market phase profile JSON path. Default uses config/screeners/market_phase_profiles.json')
    parser.add_argument('--profile-slot', type=str, default='active',
                        help='Profile slot: active or candidate. Default active')
    parser.add_argument('--calibration-note', type=str,
                        help='Optional calibration note for this run')
    parser.add_argument('--as-of-date', type=str,
                        help='Catch-up target date (YYYY-MM-DD). Will resolve to recent trading day.')
    args = parser.parse_args()

    screening = FiveFlagsPoolScreening(
        db_path=DEFAULT_DB_PATH,
        max_workers=args.max_workers,
        flow_config_file=args.flow_config,
        market_phase=args.market_phase,
        phase_profile_file=args.phase_profile,
        profile_slot=args.profile_slot,
        calibration_note=args.calibration_note,
        as_of_date=args.as_of_date
    )

    pool_ids = [int(pid.strip()) for pid in args.pool_ids.split(',')] if args.pool_ids else None
    result = screening.run_screening(pool_ids=pool_ids)

    print("=" * 60)
    print(f"Five Flags Pool Screening completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total stocks processed: {result['total_stocks']}")
    print(f"Total matches found: {result['total_matches']}")
    print(f"Total failed: {result['failed_stocks']}")
    print()
    for screener_id, matches in result['by_screener'].items():
        print(f"  {screener_id}: {matches} matches")
