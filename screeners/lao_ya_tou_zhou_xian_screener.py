"""
老鸭头周线筛选器 (LYT) - Lao Ya Tou Zhou Xian Screener - Three Signal System.

This screener implements the complete three-signal system for the Old Duck Head pattern:
- Signal 1: Aggressive entry - Duck nostril shrinkage golden cross
- Signal 2: Core main entry - Duck mouth opening golden cross
- Signal 3: Acceleration chase - Volume breakout above duck head high

The screener uses a modular architecture with separate detectors for each signal type,
providing flexibility and maintainability.
"""

from __future__ import annotations

import logging
import sqlite3
import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from base_screener import BaseScreener, ScreenResult
from signal_detectors.base_lao_ya_tou_detector import BaseLaoYaTouDetector
from signal_detectors.signal_classifier import SignalClassifier
from signal_scoring.signal_merger import SignalMerger
from signal_models.signal_detection import ScreenerResult

logger = logging.getLogger(__name__)


class LaoYaTouZhouXianParams:
    """
    Configuration parameters for Lao Ya Tou Zhou Xian screener.

    All parameters are stored as class-level attributes with UPPERCASE names.
    """

    # Backward compatible parameters (9) - Changed from weekly to daily
    MA5_PERIOD: int = 5
    MA10_PERIOD: int = 13  # Changed from 10 to 13
    MA30_PERIOD: int = 55  # Changed from 30 to 55
    LOCAL_HIGH_WINDOW: int = 60  # Changed from 12 weeks to 60 days
    VOLUME_CONTRACTION_THRESHOLD: float = 0.7
    MIN_GAP: float = 2.0
    MAX_GAP: float = 10.0
    MIN_DAYS: int = 120  # Changed from MIN_WEEKS (52 weeks) to 120 days
    TEST_MODE: bool = False

    # Amplitude parameters (applies to ALL signals as pre-filter)
    AMPLITUDE_LOOKBACK_DAYS: int = 110  # Changed from 22 weeks to 110 days
    AMPLITUDE_MIN_THRESHOLD: float = 65.0

    # Signal switches (3)
    ENABLE_SIGNAL_1: bool = True
    ENABLE_SIGNAL_2: bool = True
    ENABLE_SIGNAL_3: bool = True

    # Signal 1 parameters (2)
    SIGNAL_1_MIN_GAP: float = 3.0
    SIGNAL_1_VOLUME_RATIO_MIN: float = 1.5

    # Signal 2 parameters (1)
    SIGNAL_2_CONFIRM_DAYS: int = 5  # Reduced from 10 to 5 days for better signal detection

    # Signal 3 parameters (1)
    SIGNAL_3_BREAKOUT_LOOKBACK: int = 110  # Changed from 22 weeks to 110 days

    # Position size parameters (6)
    POSITION_SIZE_SIGNAL_1_MIN: float = 1.0
    POSITION_SIZE_SIGNAL_1_MAX: float = 3.0
    POSITION_SIZE_SIGNAL_2_MIN: float = 2.0
    POSITION_SIZE_SIGNAL_2_MAX: float = 5.0
    POSITION_SIZE_SIGNAL_3_MIN: float = 3.0
    POSITION_SIZE_SIGNAL_3_MAX: float = 6.0


class LaoYaTouZhouXianScreener(BaseScreener):
    """
    Lao Ya Tou Zhou Xian (Old Duck Head) screener with two-stage architecture.

    Stage 1: Base pattern detection - Runs on ALL stocks (4,663)
             Identifies stocks with Lao Ya Tou pattern elements
             Applies 22-week amplitude pre-filter

    Stage 2: Signal classification - Runs on qualified pool from Stage 1
             Determines which signal (1, 2, or 3) each stock is in
             Classifies based on specific signal patterns

    Final: Results grouped by signal type
    """

    def __init__(
        self,
        screener_name: Optional[str] = None,
        db_path: Optional[str] = None,
        enable_news: bool = False,
        enable_llm: bool = False,
        enable_progress: bool = False,
        # Backward compatible parameters
        ma5_period: Optional[int] = None,
        ma10_period: Optional[int] = None,
        ma30_period: Optional[int] = None,
        local_high_window: Optional[int] = None,
        volume_contraction_threshold: Optional[float] = None,
        min_gap: Optional[float] = None,
        max_gap: Optional[float] = None,
        min_days: Optional[int] = None,  # Changed from min_weeks
        test_mode: Optional[bool] = None,
        # Amplitude parameters (applies to ALL signals)
        amplitude_lookback_days: Optional[int] = None,  # Changed from amplitude_lookback_weeks
        amplitude_min_threshold: Optional[float] = None,
        # Signal switches
        enable_signal_1: Optional[bool] = None,
        enable_signal_2: Optional[bool] = None,
        enable_signal_3: Optional[bool] = None,
        # Signal 1 parameters
        signal_1_min_gap: Optional[float] = None,
        signal_1_volume_ratio_min: Optional[float] = None,
        # Signal 2 parameters
        signal_2_confirm_days: Optional[int] = None,  # Changed from signal_2_confirm_weeks
        # Signal 3 parameters
        signal_3_breakout_lookback: Optional[int] = None,
        # Position size parameters
        position_size_signal_1_min: Optional[float] = None,
        position_size_signal_1_max: Optional[float] = None,
        position_size_signal_2_min: Optional[float] = None,
        position_size_signal_2_max: Optional[float] = None,
        position_size_signal_3_min: Optional[float] = None,
        position_size_signal_3_max: Optional[float] = None,
        **kwargs,
    ) -> None:
        """Initialize Lao Ya Tou Zhou Xian screener."""
        super().__init__(
            screener_name=screener_name or "lao_ya_tou_zhou_xian",
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress,
            **kwargs
        )

        # Set parameters from configuration
        params = LaoYaTouZhouXianParams()

        # Backward compatible parameters
        if ma5_period is not None:
            params.MA5_PERIOD = ma5_period
        if ma10_period is not None:
            params.MA10_PERIOD = ma10_period
        if ma30_period is not None:
            params.MA30_PERIOD = ma30_period
        if local_high_window is not None:
            params.LOCAL_HIGH_WINDOW = local_high_window
        if volume_contraction_threshold is not None:
            params.VOLUME_CONTRACTION_THRESHOLD = volume_contraction_threshold
        if min_gap is not None:
            params.MIN_GAP = min_gap
        if max_gap is not None:
            params.MAX_GAP = max_gap
        if min_days is not None:
            params.MIN_DAYS = min_days
        if test_mode is not None:
            params.TEST_MODE = test_mode

        # Amplitude parameters (applies to ALL signals)
        if amplitude_lookback_days is not None:
            params.AMPLITUDE_LOOKBACK_DAYS = amplitude_lookback_days
        if amplitude_min_threshold is not None:
            params.AMPLITUDE_MIN_THRESHOLD = amplitude_min_threshold

        # Signal switches
        if enable_signal_1 is not None:
            params.ENABLE_SIGNAL_1 = enable_signal_1
        if enable_signal_2 is not None:
            params.ENABLE_SIGNAL_2 = enable_signal_2
        if enable_signal_3 is not None:
            params.ENABLE_SIGNAL_3 = enable_signal_3

        # Signal 1 parameters
        if signal_1_min_gap is not None:
            params.SIGNAL_1_MIN_GAP = signal_1_min_gap
        if signal_1_volume_ratio_min is not None:
            params.SIGNAL_1_VOLUME_RATIO_MIN = signal_1_volume_ratio_min

        # Signal 2 parameters
        if signal_2_confirm_days is not None:
            params.SIGNAL_2_CONFIRM_DAYS = signal_2_confirm_days

        # Signal 3 parameters
        if signal_3_breakout_lookback is not None:
            params.SIGNAL_3_BREAKOUT_LOOKBACK = signal_3_breakout_lookback

        # Position size parameters
        if position_size_signal_1_min is not None:
            params.POSITION_SIZE_SIGNAL_1_MIN = position_size_signal_1_min
        if position_size_signal_1_max is not None:
            params.POSITION_SIZE_SIGNAL_1_MAX = position_size_signal_1_max
        if position_size_signal_2_min is not None:
            params.POSITION_SIZE_SIGNAL_2_MIN = position_size_signal_2_min
        if position_size_signal_2_max is not None:
            params.POSITION_SIZE_SIGNAL_2_MAX = position_size_signal_2_max
        if position_size_signal_3_min is not None:
            params.POSITION_SIZE_SIGNAL_3_MIN = position_size_signal_3_min
        if position_size_signal_3_max is not None:
            params.POSITION_SIZE_SIGNAL_3_MAX = position_size_signal_3_max

        self.params = params

        # Stage 1: Initialize base Lao Ya Tou detector (applies to ALL stocks)
        self.base_detector = BaseLaoYaTouDetector(
            ma5_period=params.MA5_PERIOD,
            ma10_period=params.MA10_PERIOD,
            ma30_period=params.MA30_PERIOD,
            local_high_window=params.LOCAL_HIGH_WINDOW,
            volume_contraction_threshold=params.VOLUME_CONTRACTION_THRESHOLD,
            min_gap=params.MIN_GAP,
            max_gap=params.MAX_GAP,
            min_days=params.MIN_DAYS,  # Changed from min_weeks
            amplitude_lookback_days=params.AMPLITUDE_LOOKBACK_DAYS,  # Changed from amplitude_lookback_weeks
            amplitude_min_threshold=params.AMPLITUDE_MIN_THRESHOLD
        )

        # Stage 2: Initialize signal classifier (applies to qualified pool)
        self.signal_classifier = SignalClassifier(
            ma5_period=params.MA5_PERIOD,
            ma10_period=params.MA10_PERIOD,
            ma30_period=params.MA30_PERIOD,
            local_high_window=params.LOCAL_HIGH_WINDOW,
            volume_contraction_threshold=params.VOLUME_CONTRACTION_THRESHOLD,
            min_gap=params.MIN_GAP,
            max_gap=params.MAX_GAP,
            signal_1_min_gap=params.SIGNAL_1_MIN_GAP,
            signal_1_volume_ratio_min=params.SIGNAL_1_VOLUME_RATIO_MIN,
            signal_2_confirm_days=params.SIGNAL_2_CONFIRM_DAYS,  # Changed from signal_2_confirm_weeks
            signal_3_breakout_lookback=params.SIGNAL_3_BREAKOUT_LOOKBACK
        )

        # Initialize signal merger for final results
        self.signal_merger = SignalMerger(
            min_confidence=50.0,
            position_size_signal_1_min=params.POSITION_SIZE_SIGNAL_1_MIN,
            position_size_signal_1_max=params.POSITION_SIZE_SIGNAL_1_MAX,
            position_size_signal_2_min=params.POSITION_SIZE_SIGNAL_2_MIN,
            position_size_signal_2_max=params.POSITION_SIZE_SIGNAL_2_MAX,
            position_size_signal_3_min=params.POSITION_SIZE_SIGNAL_3_MIN,
            position_size_signal_3_max=params.POSITION_SIZE_SIGNAL_3_MAX
        )

        # Track which signals are enabled for final filtering
        self.enabled_signals = []
        if params.ENABLE_SIGNAL_1:
            self.enabled_signals.append('signal_1')
        if params.ENABLE_SIGNAL_2:
            self.enabled_signals.append('signal_2')
        if params.ENABLE_SIGNAL_3:
            self.enabled_signals.append('signal_3')

        # Initialize pool integration
        self.lyt_screener_id = None
        self._init_pool_integration()

        logger.info("Lao Ya Tou Zhou Xian screener initialized with two-stage architecture")

    def _init_pool_integration(self):
        """Initialize pool integration: get screener ID, verify pool exists."""
        db_conn = sqlite3.connect(str(self._db_path))
        db_conn.row_factory = sqlite3.Row

        # Get screener ID from screener_types
        screener_code = 'lao_ya_tou'
        query = """
            SELECT id FROM screener_types
            WHERE code = ?
        """
        result = db_conn.execute(query, (screener_code,)).fetchone()

        if result:
            self.lyt_screener_id = result['id']
            logger.info(f"Pool integration initialized: screener_id={self.lyt_screener_id}")
        else:
            logger.error("LYT screener not found in screener_types table")
            raise RuntimeError("Pool not initialized - run migration script first")

        db_conn.close()

    def _check_pool_stock_exists(self, db_conn: sqlite3.Connection, stock_code: str) -> bool:
        """Check if stock already exists in pool."""
        query = """
            SELECT code FROM lao_ya_tou_pool
            WHERE code = ?
        """
        result = db_conn.execute(query, (stock_code,)).fetchone()
        return result is not None

    def _get_current_pool_signal(self, db_conn: sqlite3.Connection, stock_code: str) -> Optional[str]:
        """Get current signal type for a stock in pool."""
        query = """
            SELECT current_signal FROM lao_ya_tou_pool
            WHERE code = ?
        """
        result = db_conn.execute(query, (stock_code,)).fetchone()
        return result['current_signal'] if result else None

    def _insert_pool_stock(self, db_conn: sqlite3.Connection, stock, signal_type: str, screen_date: str, signal_result: dict):
        """Insert new stock into pool."""
        query = """
            INSERT INTO lao_ya_tou_pool (
                code, name, entry_date, current_signal,
                last_screened_date, last_updated
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        db_conn.execute(query, (
            stock.code,
            stock.name,
            screen_date,
            signal_type,
            screen_date
        ))

    def _update_pool_stock(self, db_conn: sqlite3.Connection, stock, signal_type: str, screen_date: str, signal_result: dict):
        """Update existing stock in pool with new signal."""
        query = """
            UPDATE lao_ya_tou_pool
            SET current_signal = ?,
                last_screened_date = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE code = ?
        """
        db_conn.execute(query, (
            signal_type,
            screen_date,
            stock.code
        ))

    def _update_pool_screen_date(self, db_conn: sqlite3.Connection, stock_code: str, screen_date: str):
        """Update only the last_screened_date for a pool stock."""
        query = """
            UPDATE lao_ya_tou_pool
            SET last_screened_date = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE code = ?
        """
        db_conn.execute(query, (screen_date, stock_code))

    def _insert_signal_history(self, db_conn: sqlite3.Connection, stock, old_signal: Optional[str], new_signal: str, change_date: str):
        """Insert signal change history record."""
        query = """
            INSERT INTO lao_ya_tou_signal_history (
                code, old_signal, new_signal, change_date, changed_by_screener
            ) VALUES (?, ?, ?, ?, ?)
        """
        db_conn.execute(query, (
            stock.code,
            old_signal,
            new_signal,
            change_date,
            'lao_ya_tou'
        ))

    def _insert_pool_screening_result(self, db_conn: sqlite3.Connection, stock, screen_date: str, signal_result: dict):
        """Insert LYT screening result into unified table."""
        if self.lyt_screener_id is None:
            logger.warning("Screener ID not set, skipping pool insert")
            return

        query = """
            INSERT INTO pool_screening_results (
                screener_id, code, screen_date, signal_type,
                score, price, stop_loss, position_size,
                action, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        db_conn.execute(query, (
            self.lyt_screener_id,
            stock.code,
            screen_date,
            signal_result['signal_type'],
            signal_result['confidence'],
            signal_result['price'],
            signal_result.get('stop_loss'),
            signal_result.get('position_size'),
            signal_result.get('action'),
            signal_result['description']
        ))

    def _get_pool_size(self, db_conn: sqlite3.Connection) -> int:
        """Get current pool size (number of stocks)."""
        query = "SELECT COUNT(*) FROM lao_ya_tou_pool"
        result = db_conn.execute(query).fetchone()
        return result[0]

    def _get_pool_signal_distribution(self, db_conn: sqlite3.Connection) -> dict:
        """Get distribution of signal types in pool."""
        query = """
            SELECT current_signal, COUNT(*) as count
            FROM lao_ya_tou_pool
            GROUP BY current_signal
        """
        results = db_conn.execute(query).fetchall()
        return {row['current_signal']: row['count'] for row in results}

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """Return parameter schema with 26 parameters."""
        return {
            # Backward compatible parameters (9)
            'MA5_PERIOD': {
                'type': 'int',
                'default': 5,
                'min': 3,
                'max': 10,
                'display_name': 'MA5周期（周）',
                'description': 'MA5均线周期（周）',
                'group': '均线参数'
            },
            'MA10_PERIOD': {
                'type': 'int',
                'default': 13,
                'min': 5,
                'max': 20,
                'display_name': 'MA13周期（天）',
                'description': 'MA13均线周期（天）',
                'group': '均线参数'
            },
            'MA30_PERIOD': {
                'type': 'int',
                'default': 55,
                'min': 20,
                'max': 60,
                'display_name': 'MA55周期（天）',
                'description': 'MA55均线周期（天）',
                'group': '均线参数'
            },
            'LOCAL_HIGH_WINDOW': {
                'type': 'int',
                'default': 60,
                'min': 5,
                'max': 120,
                'display_name': '局部高点窗口（天）',
                'description': '识别局部高点的窗口大小（天）',
                'group': '识别参数'
            },
            'VOLUME_CONTRACTION_THRESHOLD': {
                'type': 'float',
                'default': 0.7,
                'min': 0.5,
                'max': 0.9,
                'step': 0.05,
                'display_name': '缩量阈值',
                'description': '成交量缩量比例阈值（0.5-0.9）',
                'group': '成交量参数'
            },
            'MIN_GAP': {
                'type': 'float',
                'default': 2.0,
                'min': 0.5,
                'max': 5.0,
                'step': 0.5,
                'display_name': '最小缺口（%）',
                'description': 'MA5与MA10之间的最小缺口百分比',
                'group': '识别参数'
            },
            'MAX_GAP': {
                'type': 'float',
                'default': 10.0,
                'min': 5.0,
                'max': 20.0,
                'step': 1.0,
                'display_name': '最大缺口（%）',
                'description': 'MA5与MA10之间的最大缺口百分比',
                'group': '识别参数'
            },
            'MIN_DAYS': {
                'type': 'int',
                'default': 120,
                'min': 60,
                'max': 250,
                'display_name': '最小数据天数',
                'description': '筛选所需的最少历史数据天数',
                'group': '识别参数'
            },
            'TEST_MODE': {
                'type': 'bool',
                'default': False,
                'display_name': '测试模式',
                'description': '启用测试模式，输出详细日志',
                'group': '调试参数'
            },
            # Amplitude parameters (applies to ALL signals as pre-filter)
            'AMPLITUDE_LOOKBACK_DAYS': {
                'type': 'int',
                'default': 110,
                'min': 60,
                'max': 150,
                'display_name': '振幅回溯天数',
                'description': '计算股价振幅的回溯天数（110天振幅）',
                'group': '识别参数'
            },
            'AMPLITUDE_MIN_THRESHOLD': {
                'type': 'float',
                'default': 65.0,
                'min': 30.0,
                'max': 100.0,
                'step': 5.0,
                'display_name': '最小振幅阈值（%）',
                'description': '110天振幅的最小阈值百分比（65%）',
                'group': '识别参数'
            },
            # Signal switches (3)
            'ENABLE_SIGNAL_1': {
                'type': 'bool',
                'default': True,
                'display_name': '启用信号一',
                'description': '启用信号一：激进买点・鸭鼻孔缩量金叉',
                'group': '信号开关'
            },
            'ENABLE_SIGNAL_2': {
                'type': 'bool',
                'default': True,
                'display_name': '启用信号二',
                'description': '启用信号二：核心主买・鸭嘴开口金叉',
                'group': '信号开关'
            },
            'ENABLE_SIGNAL_3': {
                'type': 'bool',
                'default': True,
                'display_name': '启用信号三',
                'description': '启用信号三：加速追买・放量突破鸭头前高',
                'group': '信号开关'
            },
            # Signal 1 parameters (2)
            'SIGNAL_1_MIN_GAP': {
                'type': 'float',
                'default': 3.0,
                'min': 1.0,
                'max': 5.0,
                'step': 0.5,
                'display_name': '信号一最小缺口（%）',
                'description': '信号一：鸭鼻孔金叉时MA5与MA10的最大缺口百分比',
                'group': '信号一参数'
            },
            'SIGNAL_1_VOLUME_RATIO_MIN': {
                'type': 'float',
                'default': 1.5,
                'min': 1.2,
                'max': 2.5,
                'step': 0.1,
                'display_name': '信号一最小量比',
                'description': '信号一：金叉时成交额与5日均量的最小比值',
                'group': '信号一参数'
            },
            # Signal 2 parameters (1)
            'SIGNAL_2_CONFIRM_DAYS': {
                'type': 'int',
                'default': 5,
                'min': 3,
                'max': 15,
                'display_name': '信号二确认天数',
                'description': '信号二：金叉后需要确认的天数',
                'group': '信号二参数'
            },
            # Signal 3 parameters (1)
            'SIGNAL_3_BREAKOUT_LOOKBACK': {
                'type': 'int',
                'default': 110,
                'min': 60,
                'max': 150,
                'display_name': '信号三回溯天数',
                'description': '信号三：寻找鸭头高点的回溯天数（110天振幅）',
                'group': '信号三参数'
            },
            # Position size parameters (6)
            'POSITION_SIZE_SIGNAL_1_MIN': {
                'type': 'float',
                'default': 1.0,
                'min': 0.5,
                'max': 2.0,
                'step': 0.1,
                'display_name': '信号一最小仓位',
                'description': '信号一建议的最小仓位大小',
                'group': '仓位控制'
            },
            'POSITION_SIZE_SIGNAL_1_MAX': {
                'type': 'float',
                'default': 3.0,
                'min': 2.0,
                'max': 5.0,
                'step': 0.5,
                'display_name': '信号一最大仓位',
                'description': '信号一建议的最大仓位大小',
                'group': '仓位控制'
            },
            'POSITION_SIZE_SIGNAL_2_MIN': {
                'type': 'float',
                'default': 2.0,
                'min': 1.0,
                'max': 3.0,
                'step': 0.1,
                'display_name': '信号二最小仓位',
                'description': '信号二建议的最小仓位大小',
                'group': '仓位控制'
            },
            'POSITION_SIZE_SIGNAL_2_MAX': {
                'type': 'float',
                'default': 5.0,
                'min': 3.0,
                'max': 8.0,
                'step': 0.5,
                'display_name': '信号二最大仓位',
                'description': '信号二建议的最大仓位大小',
                'group': '仓位控制'
            },
            'POSITION_SIZE_SIGNAL_3_MIN': {
                'type': 'float',
                'default': 3.0,
                'min': 2.0,
                'max': 4.0,
                'step': 0.1,
                'display_name': '信号三最小仓位',
                'description': '信号三建议的最小仓位大小',
                'group': '仓位控制'
            },
            'POSITION_SIZE_SIGNAL_3_MAX': {
                'type': 'float',
                'default': 6.0,
                'min': 4.0,
                'max': 10.0,
                'step': 0.5,
                'display_name': '信号三最大仓位',
                'description': '信号三建议的最大仓位大小',
                'group': '仓位控制'
            },
        }

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """
        Screen a single stock for Lao Ya Tou signals.

        Simplified version: returns all stocks that pass base pattern detection
        without signal classification constraints.

        Args:
            code: Stock code
            name: Stock name

        Returns:
            Dict with screening result or None if no signal
        """
        target_date = self.current_date

        # Check if stock has Lao Ya Tou pattern
        has_pattern, df = self.base_detector.screen(code, name, target_date)

        logger.debug(f"Stage 1 for {code}: has_pattern={has_pattern}, df rows={len(df) if df is not None else 0}")

        if not has_pattern or df is None:
            return None

        # Skip signal classification, return all stocks that pass base detection
        try:
            # Get latest data point
            latest_idx = len(df) - 1
            ma5 = df.iloc[latest_idx]['ma5']
            ma10 = df.iloc[latest_idx]['ma10']
            ma30 = df.iloc[latest_idx]['ma30']
            current_price = df.iloc[latest_idx]['close']
            current_gap = df.iloc[latest_idx]['ma_gap']
            volume_ratio = df.iloc[latest_idx]['volume_ratio']

            # Calculate stop loss (below MA30)
            stop_loss = ma30 * 0.97

            # Build result dict with general LYT signal
            result_dict = {
                'code': code,
                'name': name,
                'score': 75.0,  # Default confidence
                'signal_type': 'lao_ya_tou',
                'confidence': 75.0,
                'price': current_price,
                'gap': current_gap,
                'volume_ratio': volume_ratio,
                'stop_loss': stop_loss,
                'position_size': 'medium',
                'action': 'buy',
                'description': f'老鸭头形态: MA5={ma5:.2f}, MA13={ma10:.2f}, MA55={ma30:.2f}',
                'reason': f'老鸭头基础形态通过: MA缺口={current_gap:.2f}%, 量比={volume_ratio:.2f}'
            }

            logger.debug(f"{code} ({name}): 老鸭头基础形态通过")

            return result_dict

        except Exception as e:
            logger.warning(f"Error processing {code}: {e}")
            return None

    def _calculate_position_size(self, signal_type: str, confidence: float) -> str:
        """Calculate position size based on signal type and confidence."""
        params = self.params

        if signal_type == 'signal_1':
            min_size = params.POSITION_SIZE_SIGNAL_1_MIN
            max_size = params.POSITION_SIZE_SIGNAL_1_MAX
        elif signal_type == 'signal_2':
            min_size = params.POSITION_SIZE_SIGNAL_2_MIN
            max_size = params.POSITION_SIZE_SIGNAL_2_MAX
        else:  # signal_3
            min_size = params.POSITION_SIZE_SIGNAL_3_MIN
            max_size = params.POSITION_SIZE_SIGNAL_3_MAX

        confidence_ratio = confidence / 100.0
        position_size = min_size + (max_size - min_size) * confidence_ratio
        return f"{position_size:.2f}"

    def _determine_action(self, signal_type: str, confidence: float) -> str:
        """Determine recommended trading action."""
        if signal_type == 'signal_1':
            if confidence >= 70:
                return "BUY_AGGRESSIVE"
            elif confidence >= 55:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"
        elif signal_type == 'signal_2':
            if confidence >= 75:
                return "BUY_AGGRESSIVE"
            elif confidence >= 60:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"
        elif signal_type == 'signal_3':
            if confidence >= 80:
                return "BUY_AGGRESSIVE"
            elif confidence >= 65:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"

        return "WAIT"

        return None

    def run_screening(self, date: str = None) -> list[dict]:
        """
        Run LYT screener with pool management.

        Flow:
        1. Get all stocks
        2. For each stock, run two-stage screening
        3. Manage pool state (INSERT/UPDATE/track history)
        4. Return results with pool stats

        Args:
            date: Target date for screening (optional, uses current_date if not provided)
        """
        cur = date if date is not None else self.current_date
        logger.info("[%s] 开始选股（pool management），基准日期=%s", self.screener_name, cur)

        # Open DB connection for pool operations
        db_conn = sqlite3.connect(str(self._db_path))
        db_conn.row_factory = sqlite3.Row

        stocks = self.get_all_stocks()
        logger.info("[%s] 过滤后有效股票数: %d", self.screener_name, len(stocks))

        results_raw: List[ScreenResult] = []
        processed = pool_inserted = pool_updated = errors = 0

        for stock in stocks:
            try:
                # Two-stage screening
                raw = self.screen_stock(stock.code, stock.name)

                if raw is not None:
                    results_raw.append(
                        ScreenResult(
                            code=stock.code,
                            name=stock.name,
                            score=raw.get("score", 0.0),
                            reason=raw.get("reason", ""),
                            extra={k: v for k, v in raw.items()
                                   if k not in ("code", "name", "score", "reason")},
                        )
                    )

                    # Pool management
                    signal_type = raw['signal_type']
                    stock_in_pool = self._check_pool_stock_exists(db_conn, stock.code)

                    if stock_in_pool:
                        # Stock exists in pool - check for signal change
                        current_signal = self._get_current_pool_signal(db_conn, stock.code)

                        if current_signal != signal_type:
                            # Signal changed - UPDATE pool + INSERT history
                            self._update_pool_stock(db_conn, stock, signal_type, cur, raw)
                            self._insert_signal_history(db_conn, stock, current_signal, signal_type, cur)
                            pool_updated += 1
                            logger.info(f"{stock.code}: Signal changed {current_signal} → {signal_type}")
                        else:
                            # No change - UPDATE last_screened_date only
                            self._update_pool_screen_date(db_conn, stock.code, cur)
                    else:
                        # New stock enters pool - INSERT
                        self._insert_pool_stock(db_conn, stock, signal_type, cur, raw)
                        self._insert_signal_history(db_conn, stock, None, signal_type, cur)
                        pool_inserted += 1
                        logger.info(f"{stock.code}: New stock entered pool with {signal_type}")

                    # Always insert screening result
                    self._insert_pool_screening_result(db_conn, stock, cur, raw)

                processed += 1
            except Exception as exc:
                logger.warning("[%s] 处理 %s 异常: %s", self.screener_name, stock.code, exc)
                errors += 1

        # Commit all DB changes
        db_conn.commit()

        # Build summary with pool stats
        summary = {
            "screener": self.screener_name,
            "date": cur,
            "total_stocks": len(stocks),
            "processed": processed,
            "pool_inserted": pool_inserted,
            "pool_updated": pool_updated,
            "errors": errors,
            "hits": len(results_raw),
            "pool_size": self._get_pool_size(db_conn),
            "pool_signal_distribution": self._get_pool_signal_distribution(db_conn)
        }

        db_conn.close()

        logger.info(
            "[%s] 选股完成: 命中=%d / 处理=%d / 插入=%d / 更新=%d / 错误=%d",
            self.screener_name, len(results_raw), processed, pool_inserted, pool_updated, errors
        )

        # Convert ScreenResult objects to dicts for backend compatibility
        results_as_dicts = [
            {
                'code': result.code,
                'name': result.name,
                'score': result.score,
                'reason': result.reason,
                **result.extra
            }
            for result in results_raw
        ]

        return results_as_dicts


def main():
    """Main function for testing the screener."""
    import logging.config

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create screener
    screener = LaoYaTouZhouXianScreener(
        screener_name="lao_ya_tou_zhou_xian"
    )

    # Set date to latest available
    latest_date = screener.get_latest_data_date()
    if latest_date:
        screener.current_date = latest_date.strftime('%Y-%m-%d')
        logger.info(f"Running screener for date: {screener.current_date}")

        # Run screener
        results, _ = screener.run()

        # Print summary
        logger.info(f"\nScreening complete. Found {len(results)} stocks with signals.")

        for i, result in enumerate(results[:10], 1):
            logger.info(
                f"{i}. {result.code} {result.name}: "
                f"{result.extra.get('signal_type', 'N/A')} "
                f"(confidence: {result.extra.get('confidence', 0):.1f})"
            )

    else:
        logger.error("No data available in database")


if __name__ == "__main__":
    main()
