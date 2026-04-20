"""
Base detector with common functionality for all signal detectors.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sqlite3
import logging
import sys
from pathlib import Path

# Add workspace root to path for imports
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

# Import DB_PATH from config
try:
    from config import DB_PATH
except ImportError:
    # Fallback if config module not in path
    from pathlib import Path
    WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
    DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"

logger = logging.getLogger(__name__)


class BaseDetector:
    """
    Base detector class providing common data loading and preprocessing.

    Responsibilities:
    - Data loading and preprocessing
    - MA calculation (vectorized)
    - Local high point identification
    - Volume statistics
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float):
        """
        Initialize base detector with common parameters.

        Args:
            ma5_period: MA5 period in weeks
            ma10_period: MA10 period in weeks
            ma30_period: MA30 period in weeks
            local_high_window: Window size for local high identification (in weeks)
            volume_contraction_threshold: Volume contraction threshold (0.5-0.9)
            min_gap: Minimum gap between MA5 and MA10 (percentage)
            max_gap: Maximum gap between MA5 and MA10 (percentage)
        """
        self.ma5_period = ma5_period
        self.ma10_period = ma10_period
        self.ma30_period = ma30_period
        self.local_high_window = local_high_window
        self.volume_contraction_threshold = volume_contraction_threshold
        self.min_gap = min_gap
        self.max_gap = max_gap

    def load_stock_data(self, stock_code: str, target_date: str,
                       min_weeks: int = 52) -> Optional[pd.DataFrame]:
        """
        Load stock data from database.

        Args:
            stock_code: Stock code
            target_date: Target date for screening
            min_weeks: Minimum number of weeks of data required

        Returns:
            DataFrame with weekly data or None if insufficient data
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row

            query = """
                SELECT trade_date, open, high, low, close, volume, amount, pct_change
                FROM daily_prices
                WHERE code = ?
                AND trade_date <= ?
                ORDER BY trade_date ASC
            """
            df = pd.read_sql_query(query, conn, params=(stock_code, target_date))
            conn.close()

            if len(df) < min_weeks:
                logger.debug(f"Insufficient data for {stock_code}: {len(df)} weeks < {min_weeks}")
                return None

            # Convert to weekly data (take last trading day of each week)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df['week_num'] = df['trade_date'].dt.isocalendar().week
            df['year'] = df['trade_date'].dt.year
            df['week_key'] = df['year'].astype(str) + '_' + df['week_num'].astype(str)

            # Take last trading day of each week
            weekly_df = df.groupby('week_key').last().reset_index()
            weekly_df = weekly_df.sort_values('trade_date').reset_index(drop=True)

            # Convert period parameters to weeks (assuming 5 trading days per week)
            ma5_weeks = self.ma5_period
            ma10_weeks = self.ma10_period
            ma30_weeks = self.ma30_period

            # Calculate MAs (vectorized)
            weekly_df['ma5'] = weekly_df['close'].rolling(window=ma5_weeks, min_periods=ma5_weeks).mean()
            weekly_df['ma10'] = weekly_df['close'].rolling(window=ma10_weeks, min_periods=ma10_weeks).mean()
            weekly_df['ma30'] = weekly_df['close'].rolling(window=ma30_weeks, min_periods=ma30_weeks).mean()

            # Calculate MA5/MA10 gap
            weekly_df['ma_gap'] = ((weekly_df['ma5'] - weekly_df['ma10']) / weekly_df['ma10'] * 100)

            # Calculate volume statistics
            weekly_df['volume_ma5'] = weekly_df['volume'].rolling(window=5, min_periods=1).mean()
            weekly_df['volume_ma10'] = weekly_df['volume'].rolling(window=10, min_periods=1).mean()
            weekly_df['volume_ratio'] = weekly_df['volume'] / weekly_df['volume_ma5'].replace(0, 1)

            return weekly_df

        except Exception as e:
            logger.error(f"Error loading data for {stock_code}: {e}")
            return None

    def find_local_high(self, df: pd.DataFrame, window: Optional[int] = None) -> int:
        """
        Find the most recent local high point.

        Args:
            df: DataFrame with price data
            window: Window size (uses self.local_high_window if None)

        Returns:
            Index of the local high point
        """
        if window is None:
            window = self.local_high_window

        if len(df) < window * 2:
            return -1

        # Check from recent to past
        for i in range(len(df) - 1, -1, -1):
            if i < window or i > len(df) - window:
                continue

            # Check if this is a local high
            is_local_high = True
            current_high = df.iloc[i]['high']

            for j in range(i - window, i + window + 1):
                if j < 0 or j >= len(df):
                    continue
                if j != i and df.iloc[j]['high'] >= current_high:
                    is_local_high = False
                    break

            if is_local_high:
                return i

        return -1

    def calculate_amplitude(self, df: pd.DataFrame, lookback_weeks: int) -> float:
        """
        Calculate price amplitude over the lookback period.

        Args:
            df: DataFrame with price data
            lookback_weeks: Number of weeks to look back

        Returns:
            Amplitude percentage
        """
        if len(df) < lookback_weeks:
            return 0.0

        recent_period = df.tail(lookback_weeks)
        high_price = recent_period['high'].max()
        low_price = recent_period['low'].min()

        if low_price == 0:
            return 0.0

        return ((high_price - low_price) / low_price) * 100

    def check_ma_alignment(self, df: pd.DataFrame, index: int) -> Tuple[bool, str]:
        """
        Check if MA lines are in bullish alignment.

        Args:
            df: DataFrame with MA data
            index: Index to check

        Returns:
            Tuple of (is_aligned, alignment_description)
        """
        if index < 2:
            return False, "Insufficient data"

        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        # Check bullish alignment: MA5 > MA10 > MA30
        if ma5 > ma10 > ma30:
            return True, "Bullish alignment: MA5 > MA10 > MA30"

        if ma5 > ma10 and ma10 < ma30:
            return False, "MA10 below MA30"

        if ma5 < ma10:
            return False, "MA5 below MA10"

        return False, "No bullish alignment"

    def detect_crossing(self, df: pd.DataFrame, fast_col: str, slow_col: str,
                     index: int) -> Tuple[bool, str]:
        """
        Detect if fast MA crosses above slow MA (golden cross).

        Args:
            df: DataFrame with MA data
            fast_col: Name of fast MA column
            slow_col: Name of slow MA column
            index: Index to check

        Returns:
            Tuple of (is_crossing, crossing_type)
        """
        if index < 1:
            return False, "Insufficient data"

        fast_curr = df.iloc[index][fast_col]
        fast_prev = df.iloc[index - 1][fast_col]
        slow_curr = df.iloc[index][slow_col]
        slow_prev = df.iloc[index - 1][slow_col]

        # Golden cross: fast crosses above slow
        if fast_curr > slow_curr and fast_prev <= slow_prev:
            return True, "golden_cross"

        # Death cross: fast crosses below slow
        if fast_curr < slow_curr and fast_prev >= slow_prev:
            return True, "death_cross"

        return False, "no_cross"
