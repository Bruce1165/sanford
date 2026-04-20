"""
Signal 2 detector: Core main entry - Duck mouth opening golden cross.

Logic:
- Detect duck mouth opening: MA5 and MA10 form golden cross with wide gap
- Three MA lines (MA5, MA10, MA30) in bullish alignment
- Volume contraction followed by expansion
- This is the most reliable entry signal
"""

import pandas as pd
from datetime import date
from typing import Optional

from .base_detector import BaseDetector
from signal_models.signal_detection import SignalDetection
from signal_models.signal_types import SignalType


class Signal2Detector(BaseDetector):
    """
    Detector for Signal 2: 核心主买・鸭嘴开口金叉.

    This signal detects the optimal entry point when:
    1. MA5 and MA10 form a golden cross with wide gap (duck mouth opening)
    2. MA5 > MA10 > MA30 (bullish alignment)
    3. Volume contracts during pullback
    4. Volume expands at golden cross
    5. MA30 provides strong support

    This is the core, most reliable entry signal with balanced risk/reward.
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float, min_days: int,
                 signal_2_confirm_days: int):
        """
        Initialize Signal 2 detector.

        Args:
            ma5_period: MA5 period in days
            ma10_period: MA10 period in days
            ma30_period: MA30 period in days
            local_high_window: Window size for local high identification
            volume_contraction_threshold: Volume contraction threshold
            min_gap: Minimum gap between MA5 and MA10
            max_gap: Maximum gap between MA5 and MA10
            min_days: Minimum number of days of data
            signal_2_confirm_days: Number of days to confirm the signal
        """
        super().__init__(ma5_period, ma10_period, ma30_period,
                       local_high_window, volume_contraction_threshold,
                       min_gap, max_gap)
        self.min_days = min_days
        self.signal_2_confirm_days = signal_2_confirm_days

    def detect(self, stock_code: str, stock_name: str,
              target_date: str) -> Optional[SignalDetection]:
        """
        Detect Signal 2 for a stock.

        Args:
            stock_code: Stock code
            stock_name: Stock name
            target_date: Target date for detection

        Returns:
            SignalDetection if signal found, None otherwise
        """
        df = self.load_stock_data(stock_code, target_date, self.min_days)
        if df is None or len(df) < self.ma30_period + 5:
            return None

        # Check recent days for signal
        for i in range(len(df) - 1, max(0, len(df) - self.signal_2_confirm_days), -1):
            signal = self._check_mouth_pattern(df, i, stock_code, stock_name, target_date)
            if signal:
                return signal

        return None

    def _check_mouth_pattern(self, df: pd.DataFrame, index: int,
                           stock_code: str, stock_name: str,
                           target_date: str) -> Optional[SignalDetection]:
        """
        Check for duck mouth pattern at given index.

        The duck mouth pattern consists of:
        1. MA5 and MA10 golden cross with wide gap (mouth opening)
        2. MA5 > MA10 > MA30 (bullish alignment)
        3. Volume contraction during pullback
        4. Volume expansion at golden cross
        5. Confirmation over subsequent days
        """
        if index < self.signal_2_confirm_days:
            return None

        # Check for golden cross at current index
        is_cross, cross_type = self.detect_crossing(df, 'ma5', 'ma10', index)
        if cross_type != "golden_cross":
            return None

        # Check gap (mouth opening)
        current_gap = df.iloc[index]['ma_gap']
        if current_gap < self.min_gap or current_gap > self.max_gap:
            return None

        # Check bullish alignment
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        if not (ma5 > ma10 > ma30):
            return None

        # Check volume pattern
        volume_pattern_valid = self._check_volume_pattern(df, index)
        if not volume_pattern_valid:
            return None

        # Check confirmation over subsequent days
        confirmed = self._check_confirmation(df, index)
        if not confirmed:
            return None

        # Calculate confidence
        current_volume_ratio = df.iloc[index]['volume_ratio']
        confidence = self._calculate_confidence(
            df, index, current_gap, current_volume_ratio, confirmed
        )

        # Calculate stop loss (below MA30)
        stop_loss = ma30 * 0.97

        # Determine position size
        if confidence >= 85:
            suggested_position = "aggressive"
        elif confidence >= 70:
            suggested_position = "moderate"
        else:
            suggested_position = "conservative"

        return SignalDetection(
            signal_type=SignalType.SIGNAL_2.value,
            stock_code=stock_code,
            stock_name=stock_name,
            detection_date=pd.to_datetime(target_date).date(),
            confidence=confidence,
            gap=current_gap,
            volume_ratio=current_volume_ratio,
            price=df.iloc[index]['close'],
            stop_loss=stop_loss,
            suggested_position=suggested_position,
            description=f"Signal 2: Duck mouth opening. MA5/MA10 gap: {current_gap:.2f}%, Volume ratio: {current_volume_ratio:.2f}",
            technical_details={
                'ma5': ma5,
                'ma10': ma10,
                'ma30': ma30,
                'golden_cross_index': index,
                'confirmed': confirmed
            }
        )

    def _check_volume_pattern(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check volume pattern: contraction then expansion.

        Args:
            df: DataFrame with volume data
            index: Current index

        Returns:
            True if volume pattern is valid
        """
        if index < 5:
            return False

        # Volume before pullback
        pre_pullback_vol = df.iloc[index - 5:index - 2]['volume'].mean()

        # Volume during pullback
        pullback_vol = df.iloc[index - 2:index]['volume'].mean()

        # Volume at golden cross
        current_vol = df.iloc[index]['volume']

        if pre_pullback_vol == 0:
            return False

        # Check contraction
        contracted = pullback_vol / pre_pullback_vol <= self.volume_contraction_threshold

        # Check expansion
        expanded = current_vol / pullback_vol >= 1.5

        return contracted and expanded

    def _check_confirmation(self, df: pd.DataFrame, index: int) -> bool:
        """
        Check if signal is confirmed over subsequent days.

        Args:
            df: DataFrame with price data
            index: Index where signal occurred

        Returns:
            True if signal is confirmed
        """
        if index + self.signal_2_confirm_days >= len(df):
            return False

        # Check that MA5 stays above MA10 and MA10 stays above MA30
        for i in range(1, self.signal_2_confirm_days + 1):
            ma5 = df.iloc[index + i]['ma5']
            ma10 = df.iloc[index + i]['ma10']
            ma30 = df.iloc[index + i]['ma30']

            if not (ma5 > ma10 > ma30):
                return False

        return True

    def _calculate_confidence(self, df: pd.DataFrame, index: int,
                           gap: float, volume_ratio: float,
                           confirmed: bool) -> float:
        """
        Calculate confidence score for Signal 2.

        Factors:
        1. Gap size: 30 points
        2. Volume expansion: 30 points
        3. MA alignment strength: 20 points
        4. Confirmation: 20 points

        Returns:
            Confidence score (0-100)
        """
        confidence = 0

        # Gap score (wider gap within range is better)
        if self.min_gap <= gap <= (self.min_gap + 2.0):
            confidence += 30
        elif (self.min_gap + 2.0) < gap <= (self.min_gap + 4.0):
            confidence += 25
        elif gap <= self.max_gap:
            confidence += 20
        else:
            confidence += 10

        # Volume expansion score
        if volume_ratio >= 2.0:
            confidence += 30
        elif volume_ratio >= 1.5:
            confidence += 25
        else:
            confidence += 20

        # MA alignment score
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        ma5_10_gap = (ma5 - ma10) / ma10
        ma10_30_gap = (ma10 - ma30) / ma30

        if ma5_10_gap > 0.03 and ma10_30_gap > 0.02:
            confidence += 20
        elif ma5_10_gap > 0.02 and ma10_30_gap > 0.01:
            confidence += 15
        else:
            confidence += 10

        # Confirmation score
        if confirmed:
            confidence += 20

        return min(confidence, 100)
