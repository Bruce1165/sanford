"""
Base Lao Ya Tou pattern detector - Stage 1 screening.

This detector identifies stocks that have the Lao Ya Tou pattern elements,
regardless of which specific signal phase they are in.

Pattern elements:
- Duck neck: MA5/MA10 cross above MA30, bullish alignment
- Duck head: Price high then contraction pullback, MA5/MA10 death cross above MA30
- Duck nostril: MA5/MA10 golden cross with small gap
- Duck mouth: MA5/MA10 second golden cross, opening upward
- MA30 as support level
"""

import pandas as pd
import numpy as np
from typing import Optional, List
import sqlite3
import logging
import sys
from pathlib import Path

# Add workspace root to path for imports
WORKSPACE_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

# Import DB_PATH from config
try:
    from config import DB_PATH
except ImportError:
    # Fallback if config module not in path
    DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"

logger = logging.getLogger(__name__)


class BaseLaoYaTouDetector:
    """
    Base detector for identifying Lao Ya Tou pattern stocks.

    This is Stage 1 of the two-stage architecture:
    - Runs on ALL stocks (not signal-specific)
    - Identifies stocks with Lao Ya Tou pattern elements
    - Applies common pre-filters (22-week amplitude, etc.)

    Output: Pool of stocks that have the Lao Ya Tou pattern
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float, min_days: int,
                 amplitude_lookback_days: int, amplitude_min_threshold: float):
        """
        Initialize base Lao Ya Tou detector.

        Args:
            ma5_period: MA5 period in days
            ma10_period: MA10 period in days
            ma30_period: MA30 period in days
            local_high_window: Window size for local high identification
            volume_contraction_threshold: Volume contraction threshold
            min_gap: Minimum gap between MA5 and MA10
            max_gap: Maximum gap between MA5 and MA10
            min_days: Minimum number of days of data
            amplitude_lookback_days: Days for amplitude check (110 days)
            amplitude_min_threshold: Minimum amplitude threshold (65%)
        """
        self.ma5_period = ma5_period
        self.ma10_period = ma10_period
        self.ma30_period = ma30_period
        self.local_high_window = local_high_window
        self.volume_contraction_threshold = volume_contraction_threshold
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.min_days = min_days
        self.amplitude_lookback_days = amplitude_lookback_days
        self.amplitude_min_threshold = amplitude_min_threshold

    def load_stock_data(self, stock_code: str, target_date: str) -> Optional[pd.DataFrame]:
        """
        Load stock data from database and calculate indicators.

        Args:
            stock_code: Stock code
            target_date: Target date for screening

        Returns:
            DataFrame with daily data and calculated MAs or None
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

            if len(df) < self.min_days:
                return None

            # Work with daily data (no weekly conversion)
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date').reset_index(drop=True)

            # Calculate MAs using daily data
            df['ma5'] = df['close'].rolling(window=self.ma5_period, min_periods=self.ma5_period).mean()
            df['ma10'] = df['close'].rolling(window=self.ma10_period, min_periods=self.ma10_period).mean()
            df['ma30'] = df['close'].rolling(window=self.ma30_period, min_periods=self.ma30_period).mean()
            df['ma_gap'] = ((df['ma5'] - df['ma10']) / df['ma10'] * 100)

            # Calculate volume statistics
            df['volume_ma5'] = df['volume'].rolling(window=5, min_periods=1).mean()
            df['volume_ma10'] = df['volume'].rolling(window=10, min_periods=1).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma5'].replace(0, 1)

            return df

        except Exception as e:
            logger.error(f"Error loading data for {stock_code}: {e}")
            return None

    def check_amplitude(self, df: pd.DataFrame) -> bool:
        """
        Check if stock has sufficient price movement (110-day amplitude).

        Args:
            df: DataFrame with price data

        Returns:
            True if amplitude meets threshold
        """
        if len(df) < self.amplitude_lookback_days:
            logger.debug(f"Amplitude check failed: insufficient data {len(df)} < {self.amplitude_lookback_days}")
            return False

        recent_period = df.tail(self.amplitude_lookback_days)
        high_price = recent_period['high'].max()
        low_price = recent_period['low'].min()

        if low_price == 0:
            return False

        amplitude = ((high_price - low_price) / low_price) * 100
        logger.debug(f"Amplitude: {amplitude:.2f}%, threshold: {self.amplitude_min_threshold}%")
        return amplitude >= self.amplitude_min_threshold

    def check_bullish_alignment(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check if MA lines are in bullish alignment (MA5 > MA10 > MA30).

        Args:
            df: DataFrame with MA data
            index: Index to check

        Returns:
            True if bullish alignment
        """
        if index < 2:
            return False

        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        return ma5 > ma10 > ma30

    def detect_crossing(self, df: pd.DataFrame, fast_col: str, slow_col: str,
                     index: int) -> str:
        """
        Detect MA crossing type.

        Args:
            df: DataFrame with MA data
            fast_col: Name of fast MA column
            slow_col: Name of slow MA column
            index: Index to check

        Returns:
            Crossing type: 'golden_cross', 'death_cross', or 'no_cross'
        """
        if index < 1:
            return 'no_cross'

        fast_curr = df.iloc[index][fast_col]
        fast_prev = df.iloc[index - 1][fast_col]
        slow_curr = df.iloc[index][slow_col]
        slow_prev = df.iloc[index - 1][slow_col]

        # Golden cross: fast crosses above slow
        if fast_curr > slow_curr and fast_prev <= slow_prev:
            return 'golden_cross'

        # Death cross: fast crosses below slow
        if fast_curr < slow_curr and fast_prev >= slow_prev:
            return 'death_cross'

        return 'no_cross'

    def has_pattern_elements(self, df: pd.DataFrame) -> bool:
        """
        Check if stock has Lao Ya Tou pattern elements.

        Pattern elements to check:
        1. Sufficient price movement (22-week amplitude >= 65%)
        2. Bullish MA alignment exists
        3. MA5 and MA10 have crossed (golden or death)
        4. MA30 provides support

        Args:
            df: DataFrame with price and MA data

        Returns:
            True if stock has Lao Ya Tou pattern elements
        """
        # Check amplitude
        if not self.check_amplitude(df):
            return False

        # Check recent weeks for pattern elements
        for i in range(len(df) - 1, max(0, len(df) - 10), -1):
            # Check bullish alignment
            if not self.check_bullish_alignment(df, i):
                continue

            # Check for recent crossing
            has_recent_crossing = False
            for j in range(max(0, i - 5), i + 1):
                crossing = self.detect_crossing(df, 'ma5', 'ma10', j)
                if crossing in ['golden_cross', 'death_cross']:
                    has_recent_crossing = True
                    break

            if not has_recent_crossing:
                continue

            # Check MA30 support
            ma5 = df.iloc[i]['ma5']
            ma10 = df.iloc[i]['ma10']
            ma30 = df.iloc[i]['ma30']

            if ma5 > ma30 and ma10 > ma30:
                return True

        return False

    def screen(self, stock_code: str, stock_name: str, target_date: str, cached_df: Optional[pd.DataFrame] = None) -> tuple[bool, Optional[pd.DataFrame]]:
        """
        Screen a stock for Lao Ya Tou pattern (Stage 1).

        Args:
            stock_code: Stock code
            stock_name: Stock name
            target_date: Target date
            cached_df: Optional DataFrame to pass (for internal caching)

        Returns:
            Tuple of (bool, df): bool result and DataFrame with indicators
        """
        df = cached_df if cached_df is not None else self.load_stock_data(stock_code, target_date)
        if df is None:
            return False, None

        return self.has_pattern_elements(df), df
