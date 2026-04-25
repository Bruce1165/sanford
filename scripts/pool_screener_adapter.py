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
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path

import sqlite3
import pandas as pd

# Add both scripts and backend directories to path
# IMPORTANT: Insert project_root FIRST to ensure screeners/ directory is found before backend/screeners.py
scripts_dir = str(Path(__file__).parent)
project_root = str(Path(__file__).parent.parent)  # NeoTrade2 directory

# Force project_root to the front so `screeners/` package wins over backend/screeners.py
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)
if scripts_dir in sys.path:
    sys.path.remove(scripts_dir)
sys.path.insert(1, scripts_dir)

# If a wrong top-level `screeners` module was already loaded from backend/screeners.py,
# drop it so the following imports resolve to project_root/screeners package.
loaded_screeners = sys.modules.get('screeners')
if loaded_screeners is not None:
    loaded_file = str(getattr(loaded_screeners, '__file__', '') or '')
    if loaded_file.endswith('/backend/screeners.py'):
        del sys.modules['screeners']

# Import screener modules directly from screeners package FIRST
# This must be done before importing anything from backend to avoid conflicts
from screeners import er_ban_hui_tiao_screener
from screeners import jin_feng_huang_screener
from screeners import yin_feng_huang_screener
from screeners import shi_pan_xian_screener
from screeners import zhang_ting_bei_liang_yin_screener

# Now import ConfigLoader from backend
from backend.config_loader import ConfigLoader

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

    def __init__(self, db_path: str = 'data/stock_data.db', screener_overrides: Optional[Dict[str, Dict]] = None):
        """
        Initialize adapter.

        Args:
            db_path: Path to stock_data.db
        """
        self.db_path = db_path
        self.screener_overrides = screener_overrides or {}
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

    @staticmethod
    def _extract_config_kwargs(config: Optional[Dict], init_params: Dict) -> Dict:
        """Extract init kwargs from config in either legacy or dashboard format."""
        if not isinstance(config, dict):
            return {}

        kwargs = {}
        parameters = config.get('parameters')
        if isinstance(parameters, dict):
            for key, meta in parameters.items():
                value = meta.get('value') if isinstance(meta, dict) else meta
                normalized = str(key).strip().lower()
                if normalized in init_params:
                    kwargs[normalized] = value

        config_json = config.get('config_json')
        if isinstance(config_json, dict):
            for key, value in config_json.items():
                normalized = str(key).strip().lower()
                if normalized in init_params:
                    kwargs[normalized] = value

        # Fallback for plain flat configs.
        if not kwargs:
            for key, value in config.items():
                if key in {'display_name', 'description', 'category', 'metadata', 'parameters'}:
                    continue
                normalized = str(key).strip().lower()
                if normalized in init_params:
                    kwargs[normalized] = value
        return kwargs

    def _extract_override_kwargs(self, screener_id: str, init_params: Dict) -> Dict:
        """Extract per-screener runtime override kwargs."""
        overrides = self.screener_overrides.get(screener_id) or {}
        if not isinstance(overrides, dict):
            return {}
        kwargs = {}
        for key, value in overrides.items():
            normalized = str(key).strip().lower()
            if normalized in init_params:
                kwargs[normalized] = value
        return kwargs

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

                # Build screener class name from module name.
                # Example: er_ban_hui_tiao_screener -> ErBanHuiTiaoScreener
                base_name = module_name[:-9] if module_name.endswith('_screener') else module_name
                screener_class_name = base_name.replace('_', ' ').title().replace(' ', '') + 'Screener'
                screener_class = getattr(module, screener_class_name)

                # Get screener's __init__ signature to only pass accepted parameters
                screener_init = screener_class.__init__
                init_params = inspect.signature(screener_init).parameters

                # Load configuration from Dashboard database
                config = ConfigLoader.load_config(screener_id, prefer_database=True)

                # Build kwargs based on what screener accepts and config
                screener_kwargs = {'db_path': self.db_path}

                if config:
                    logger.info(f"Loaded config for {screener_id}")
                    screener_kwargs.update(self._extract_config_kwargs(config, init_params))
                else:
                    logger.info(f"No config found in Dashboard for {screener_id}, using defaults")

                runtime_overrides = self._extract_override_kwargs(screener_id, init_params)
                if runtime_overrides:
                    logger.info(f"Applied runtime phase overrides for {screener_id}: {list(runtime_overrides.keys())}")
                    screener_kwargs.update(runtime_overrides)

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
                  stock_name: str, date: str,
                  include_miss_details: bool = False) -> Optional[dict]:
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

        if result is not None or not include_miss_details:
            return result

        miss_detail = self._diagnose_miss(screener, screener_id, stock_code, stock_name)
        return {
            'matched': False,
            'screener_id': screener_id,
            'code': stock_code,
            'name': stock_name,
            **miss_detail,
        }

    @staticmethod
    def _first_failure(checks):
        for item in checks:
            if not item.get('passed'):
                return item
        return None

    @staticmethod
    def _normalize_hint_list(items, limit: int = 6) -> List[str]:
        if not isinstance(items, list):
            return []
        hints: List[str] = []
        seen = set()
        for item in items:
            text = str(item or '').strip()
            if not text or text in seen:
                continue
            seen.add(text)
            hints.append(text)
            if len(hints) >= limit:
                break
        return hints

    def _build_miss_payload(self, checks, fallback_reason: str, diagnostic_hints: Optional[List[str]] = None) -> Dict:
        first_failed = self._first_failure(checks)
        reason_miss = first_failed.get('message') if first_failed else fallback_reason
        hints: List[str] = []
        passed_labels = [
            str(item.get('label', '') or '').strip()
            for item in checks
            if isinstance(item, dict) and item.get('passed')
        ]
        if passed_labels:
            hints.append(f"主链通过阶段: {' -> '.join([x for x in passed_labels if x])}")
        if first_failed and first_failed.get('label'):
            hints.append(f"主链阻断阶段: {str(first_failed.get('label') or '').strip()}")
        failed_messages = [
            str(item.get('message', '') or '').strip()
            for item in checks
            if isinstance(item, dict) and not item.get('passed')
        ]
        for msg in failed_messages:
            if msg and msg != reason_miss:
                hints.append(f"补充线索: {msg}")
        if isinstance(diagnostic_hints, list):
            hints.extend(diagnostic_hints)
        normalized_hints = self._normalize_hint_list(hints)
        return {
            'reason_miss': reason_miss,
            'failed_checks': checks,
            'first_failed_check': first_failed,
            'diagnostic_hints': normalized_hints,
        }

    def _load_sorted_df(self, screener: object, stock_code: str, min_rows: int, default_days: int = 24):
        days = getattr(screener, 'limit_days', default_days)
        days = int(days) + 10 if days else default_days
        df = screener.get_stock_data(stock_code, days=days)
        if df is None or len(df) < min_rows:
            return None
        if isinstance(df, pd.DataFrame):
            return df.sort_values('trade_date').reset_index(drop=True)
        return None

    def _diagnose_er_ban_hui_tiao(self, screener: object, stock_code: str) -> Dict:
        checks = []
        df = self._load_sorted_df(screener, stock_code, min_rows=10)
        checks.append({'key': 'data', 'label': '数据完整性', 'passed': df is not None, 'message': '可用K线不足（至少10个交易日）'})
        if df is None:
            return self._build_miss_payload(checks, '数据不足，无法判定二板回调信号')

        signal_one = screener.find_signal_one(df)
        checks.append({'key': 'signal_1', 'label': '信号1', 'passed': signal_one is not None, 'message': '未满足二连板+量能约束（信号1）'})
        if signal_one is None:
            return self._build_miss_payload(checks, '信号1未满足')

        signal_one_idx = signal_one['first_idx']
        latest_date = df.iloc[-1]['trade_date']
        signal_one_date = df.iloc[signal_one_idx]['trade_date']
        within_window = (latest_date - signal_one_date).days <= screener.limit_days
        checks.append({'key': 'window', 'label': '时间窗口', 'passed': within_window, 'message': f'信号1超出最近{screener.limit_days}个交易日窗口'})
        if not within_window:
            return self._build_miss_payload(checks, '信号触发时间超窗')

        signal_two_ok = screener.check_signal_two(df, signal_one_idx)
        checks.append({'key': 'signal_2', 'label': '信号2', 'passed': signal_two_ok, 'message': '信号2失败：后续最低价跌破Day T开盘价'})
        if not signal_two_ok:
            return self._build_miss_payload(checks, '价格保护条件不满足')

        signal_three = screener.find_signal_three(df, signal_one_idx)
        checks.append({'key': 'signal_3', 'label': '信号3', 'passed': signal_three is not None, 'message': '未出现满足启动条件的Day X（信号3）'})
        return self._build_miss_payload(checks, '未满足完整信号链路')

    def _diagnose_jin_feng_huang(self, screener: object, stock_code: str) -> Dict:
        checks = []
        df = self._load_sorted_df(screener, stock_code, min_rows=10)
        checks.append({'key': 'data', 'label': '数据完整性', 'passed': df is not None, 'message': '可用K线不足（至少10个交易日）'})
        if df is None:
            return self._build_miss_payload(checks, '数据不足，无法判定金凤凰信号')

        candidate_idx = None
        for i in range(len(df) - 1, 0, -1):
            if not screener.check_signal_one(df, i):
                continue
            latest_date = df.iloc[-1]['trade_date']
            if (latest_date - df.iloc[i]['trade_date']).days <= screener.limit_days:
                candidate_idx = i
                break
        checks.append({'key': 'signal_1', 'label': '信号1', 'passed': candidate_idx is not None, 'message': '未找到满足涨停量能的一号信号日'})
        if candidate_idx is None:
            return self._build_miss_payload(checks, '信号1未满足')

        signal_two_ok = screener.check_signal_two(df, candidate_idx)
        checks.append({'key': 'signal_2', 'label': '信号2', 'passed': signal_two_ok, 'message': '信号2失败：次日高开收阳+放量条件不满足'})
        if not signal_two_ok:
            return self._build_miss_payload(checks, '信号2未满足')

        signal_two_idx = candidate_idx + 1
        signal_four_idx = screener.find_signal_four(df, signal_two_idx)
        checks.append({'key': 'signal_4', 'label': '信号4', 'passed': signal_four_idx is not None, 'message': '未找到地量日（信号4）'})
        if signal_four_idx is None:
            return self._build_miss_payload(checks, '信号4未满足')

        signal_five_idx = screener.find_signal_five(df, signal_four_idx, candidate_idx)
        checks.append({'key': 'signal_5', 'label': '信号5', 'passed': signal_five_idx is not None, 'message': '未找到启动日（信号5）'})
        if signal_five_idx is None:
            return self._build_miss_payload(checks, '信号5未满足')

        signal_three_ok = screener.check_signal_three(df, candidate_idx, signal_five_idx)
        checks.append({'key': 'signal_3', 'label': '信号3', 'passed': signal_three_ok, 'message': '信号3失败：中间区间存在低点跌破信号一高点'})
        return self._build_miss_payload(checks, '未满足完整信号链路')

    def _diagnose_yin_feng_huang(self, screener: object, stock_code: str) -> Dict:
        checks = []
        df = self._load_sorted_df(screener, stock_code, min_rows=10)
        checks.append({'key': 'data', 'label': '数据完整性', 'passed': df is not None, 'message': '可用K线不足（至少10个交易日）'})
        if df is None:
            return self._build_miss_payload(checks, '数据不足，无法判定银凤凰信号')

        candidate_idx = None
        for i in range(len(df) - 1, 0, -1):
            if not screener.check_signal_one(df, i):
                continue
            latest_date = df.iloc[-1]['trade_date']
            if (latest_date - df.iloc[i]['trade_date']).days <= screener.limit_days:
                candidate_idx = i
                break
        checks.append({'key': 'signal_1', 'label': '信号1', 'passed': candidate_idx is not None, 'message': '未找到满足涨停量能的一号信号日'})
        if candidate_idx is None:
            return self._build_miss_payload(checks, '信号1未满足')

        signal_three_idx = screener.find_signal_three(df, candidate_idx)
        checks.append({'key': 'signal_3', 'label': '信号3', 'passed': signal_three_idx is not None, 'message': '未找到缩量阴线日（信号3）'})
        if signal_three_idx is None:
            return self._build_miss_payload(checks, '信号3未满足')

        signal_four_idx = screener.find_signal_four(df, signal_three_idx)
        checks.append({'key': 'signal_4', 'label': '信号4', 'passed': signal_four_idx is not None, 'message': '未找到启动日（信号4）'})
        if signal_four_idx is None:
            return self._build_miss_payload(checks, '信号4未满足')

        signal_two_ok = screener.check_signal_two(df, candidate_idx, signal_four_idx)
        checks.append({'key': 'signal_2', 'label': '信号2', 'passed': signal_two_ok, 'message': '信号2失败：区间最低价跌破信号一开盘价'})
        return self._build_miss_payload(checks, '未满足完整信号链路')

    def _diagnose_zhang_ting_bei_liang_yin(self, screener: object, stock_code: str) -> Dict:
        checks = []
        df = self._load_sorted_df(screener, stock_code, min_rows=10)
        checks.append({'key': 'data', 'label': '数据完整性', 'passed': df is not None, 'message': '可用K线不足（至少10个交易日）'})
        if df is None:
            return self._build_miss_payload(checks, '数据不足，无法判定倍量阴信号')

        candidate_idx = None
        for i in range(len(df) - 1, -1, -1):
            if not screener.check_signal_one(df, i):
                continue
            latest_date = df.iloc[-1]['trade_date']
            if (latest_date - df.iloc[i]['trade_date']).days <= screener.limit_days:
                candidate_idx = i
                break
        checks.append({'key': 'signal_1', 'label': '信号1', 'passed': candidate_idx is not None, 'message': '未找到满足涨停阳线形态的一号信号日'})
        if candidate_idx is None:
            return self._build_miss_payload(checks, '信号1未满足')

        signal_two_idx = candidate_idx + 1
        signal_two_ok = signal_two_idx < len(df) and screener.check_signal_two(df, signal_two_idx)
        checks.append({'key': 'signal_2', 'label': '信号2', 'passed': signal_two_ok, 'message': '信号2失败：次日高开阴线形态不满足'})
        if not signal_two_ok:
            return self._build_miss_payload(checks, '信号2未满足')

        signal_three_ok = screener.check_signal_three(df, candidate_idx, signal_two_idx)
        checks.append({'key': 'signal_3', 'label': '信号3', 'passed': signal_three_ok, 'message': '信号3失败：次日成交额未达到阈值'})
        if not signal_three_ok:
            return self._build_miss_payload(checks, '信号3未满足')

        signal_four_idx = screener.find_signal_four(df, candidate_idx)
        checks.append({'key': 'signal_4', 'label': '信号4', 'passed': signal_four_idx is not None, 'message': '未找到低量日（信号4）'})
        if signal_four_idx is None:
            return self._build_miss_payload(checks, '信号4未满足')

        signal_five_idx = screener.find_signal_five(df, signal_four_idx)
        checks.append({'key': 'signal_5', 'label': '信号5', 'passed': signal_five_idx is not None, 'message': '未找到启动日（信号5）'})
        if signal_five_idx is None:
            return self._build_miss_payload(checks, '信号5未满足')

        price_protection_ok = screener.check_price_protection(df, candidate_idx)
        checks.append({'key': 'signal_2_5', 'label': '信号2.5', 'passed': price_protection_ok, 'message': '价格保护失败：后续低点跌破Day T开盘价'})
        return self._build_miss_payload(checks, '未满足完整信号链路')

    def _diagnose_shi_pan_xian(self, screener: object, stock_code: str) -> Dict:
        checks = []
        df = screener.get_stock_data(stock_code)
        if isinstance(df, pd.DataFrame):
            df = df.sort_values('trade_date').reset_index(drop=True)
        else:
            df = None
        checks.append({'key': 'data', 'label': '数据完整性', 'passed': df is not None and len(df) >= 50, 'message': '可用K线不足（至少50个交易日）'})
        if df is None or len(df) < 50:
            return self._build_miss_payload(checks, '数据不足，无法判定试盘线信号')

        hv_idx = screener.find_high_volume_yang_line(df)
        checks.append({'key': 'signal_1', 'label': '信号1', 'passed': hv_idx is not None, 'message': '未找到低位横盘后的高量阳线'})
        if hv_idx is None:
            return self._build_miss_payload(checks, '信号1未满足')

        callback = screener.check_limit_up_and_callback(df, hv_idx)
        checks.append({
            'key': 'signal_2_5',
            'label': '信号2-5',
            'passed': callback is not None,
            'message': '涨停后区间约束、缩量或再次放量条件未满足'
        })
        return self._build_miss_payload(checks, '未满足完整信号链路')

    def _diagnose_miss(self, screener: object, screener_id: str, stock_code: str, stock_name: str) -> Dict:
        try:
            if screener_id == 'er_ban_hui_tiao':
                return self._diagnose_er_ban_hui_tiao(screener, stock_code)
            if screener_id == 'jin_feng_huang':
                return self._diagnose_jin_feng_huang(screener, stock_code)
            if screener_id == 'yin_feng_huang':
                return self._diagnose_yin_feng_huang(screener, stock_code)
            if screener_id == 'zhang_ting_bei_liang_yin':
                return self._diagnose_zhang_ting_bei_liang_yin(screener, stock_code)
            if screener_id == 'shi_pan_xian':
                return self._diagnose_shi_pan_xian(screener, stock_code)
        except Exception as exc:
            logger.warning(f"Miss diagnose failed for {screener_id}/{stock_code}: {exc}")

        fallback = f"{stock_name} 在当前日期未命中 {screener_id}"
        return self._build_miss_payload(
            [{'key': 'unknown', 'label': '判定', 'passed': False, 'message': fallback}],
            fallback
        )

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
