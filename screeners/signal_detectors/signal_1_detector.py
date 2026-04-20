"""
Signal 1 detector: Aggressive entry - Duck nostril shrinkage golden cross.

Logic:
- Detect duck nostril: MA5 and MA10 death cross followed by golden cross
- Volume contraction during the nostril period
- Small gap between MA5 and MA10 after golden cross
"""

import pandas as pd
import numpy as np
from datetime import date
from typing import Optional

from .base_detector import BaseDetector
from signal_models.signal_detection import SignalDetection
from signal_models.signal_types import SignalType


class Signal1Detector(BaseDetector):
    """
    Detector for Signal 1: 激进买点・鸭鼻孔缩量金叉.

    This signal detects the early entry point when:
    1. MA5 and MA10 form a death cross (duck nostril formation)
    2. Volume contracts during the nostril period
    3. MA5 and MA10 form a golden cross (nostril closes)
    4. Gap between MA5 and MA10 is small
    5. Volume starts expanding

    This is an aggressive, early entry signal with higher risk but potentially higher reward.
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float, min_weeks: int,
                 signal_1_min_gap: float, signal_1_volume_ratio_min: float):
        """
        Initialize Signal 1 detector.

        Args:
            ma5_period: MA5 period in weeks
            ma10_period: MA10 period in weeks
            ma30_period: MA30 period in weeks
            local_high_window: Window size for local high identification
            volume_contraction_threshold: Volume contraction threshold
            min_gap: Minimum gap between MA5 and MA10
            max_gap: Maximum gap between MA5 and MA10
            min_weeks: Minimum number of weeks of data
            signal_1_min_gap: Minimum MA gap for Signal 1 (smaller is stronger)
            signal_1_volume_ratio_min: Minimum volume ratio after golden cross
        """
        super().__init__(ma5_period, ma10_period, ma30_period,
                       local_high_window, volume_contraction_threshold,
                       min_gap, max_gap)
        self.min_weeks = min_weeks
        self.signal_1_min_gap = signal_1_min_gap
        self.signal_1_volume_ratio_min = signal_1_volume_ratio_min

    def detect(self, stock_code: str, stock_name: str,
              target_date: str) -> Optional[SignalDetection]:
        """
        Detect Signal 1 for a stock.

        Args:
            stock_code: Stock code
            stock_name: Stock name
            target_date: Target date for detection

        Returns:
            SignalDetection if signal found, None otherwise
        """
        df = self.load_stock_data(stock_code, target_date, self.min_weeks)
        if df is None or len(df) < self.ma10_period + 5:
            return None

        # Check recent 5 weeks for signal
        for i in range(len(df) - 1, max(0, len(df) - 5), -1):
            signal = self._check_nostril_pattern(df, i, stock_code, stock_name, target_date)
            if signal:
                return signal

        return None

    def _check_nostril_pattern(self, df: pd.DataFrame, index: int,
                              stock_code: str, stock_name: str,
                              target_date: str) -> Optional[SignalDetection]:
        """
        Check for duck nostril pattern at given index.

        The duck nostril pattern consists of:
        1. Death cross: MA5 crosses below MA10
        2. Golden cross: MA5 crosses above MA10
        3. Small gap between MA5 and MA10
        4. Volume contraction during the nostril
        5. Volume expansion after golden cross
        """
        if index < 3:
            return None

        # Check for golden cross at current index
        is_cross, cross_type = self.detect_crossing(df, 'ma5', 'ma10', index)
        if cross_type != "golden_cross":
            return None

        # Check for death cross before golden cross (nostril formation)
        death_cross_index = -1
        for j in range(index - 1, max(0, index - 10), -1):
            is_cross_dc, cross_type_dc = self.detect_crossing(df, 'ma5', 'ma10', j)
            if cross_type_dc == "death_cross":
                death_cross_index = j
                break

        if death_cross_index == -1:
            return None

        # Check gap between MA5 and MA10 (smaller is stronger)
        current_gap = df.iloc[index]['ma_gap']
        if abs(current_gap) > self.signal_1_min_gap:
            return None

        # Check volume contraction during nostril period
        volume_contracted = self._check_volume_contraction(df, death_cross_index, index)

        # Check volume expansion after golden cross
        current_volume_ratio = df.iloc[index]['volume_ratio']
        volume_expanded = current_volume_ratio >= self.signal_1_volume_ratio_min

        if not volume_contracted or not volume_expanded:
            return None

        # Check that MA30 is below (support level)
        ma30 = df.iloc[index]['ma30']
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']

        if ma5 <= ma30 or ma10 <= ma30:
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(
            df, index, current_gap, current_volume_ratio, volume_contracted
        )

        # Calculate stop loss (below MA30)
        stop_loss = ma30 * 0.98

        # Determine position size
        if confidence >= 80:
            suggested_position = "aggressive"
        elif confidence >= 60:
            suggested_position = "moderate"
        else:
            suggested_position = "conservative"

        return SignalDetection(
            signal_type=SignalType.SIGNAL_1.value,
            stock_code=stock_code,
            stock_name=stock_name,
            detection_date=pd.to_datetime(target_date).date(),
            confidence=confidence,
            gap=current_gap,
            volume_ratio=current_volume_ratio,
            price=df.iloc[index]['close'],
            stop_loss=stop_loss,
            suggested_position=suggested_position,
            description=f"Signal 1: Duck nostril golden cross. MA5/MA10 gap: {current_gap:.2f}%, Volume ratio: {current_volume_ratio:.2f}",
            technical_details={
                'ma5': ma5,
                'ma10': ma10,
                'ma30': ma30,
                'death_cross_index': death_cross_index,
                'golden_cross_index': index,
                'volume_contracted': volume_contracted
            }
        )

    def _check_volume_contraction(self, df: pd.DataFrame,
                               start_index: int, end_index: int) -> bool:
        """
        Check if volume contracted during the nostril period.

        Args:
            df: DataFrame with volume data
            start_index: Start index (death cross)
            end_index: End index (golden cross)

        Returns:
            True if volume contracted significantly
        """
        if end_index <= start_index:
            return False

        # Average volume before nostril
        pre_nostril_vol = df.iloc[max(0, start_index - 5):start_index]['volume'].mean()

        # Average volume during nostril
        nostril_vol = df.iloc[start_index:end_index]['volume'].mean()

        if pre_nostril_vol == 0:
            return False

        volume_ratio = nostril_vol / pre_nostril_vol
        return volume_ratio <= self.volume_contraction_threshold

    def _calculate_confidence(self, df: pd.DataFrame, index: int,
                           gap: float, volume_ratio: float,
                           volume_contracted: bool) -> float:
        """
        Calculate confidence score for Signal 1.

        Factors:
        1. Gap size (smaller is better): 30 points
        2. Volume expansion: 30 points
        3. Volume contraction during nostril: 20 points
        4. MA alignment: 20 points

        Returns:
            Confidence score (0-100)
        """
        confidence = 0

        # Gap score (smaller gap is better, but must be positive)
        if 0 < gap <= 1.0:
            confidence += 30
        elif 1.0 < gap <= 2.0:
            confidence += 25
        elif 2.0 < gap <= self.signal_1_min_gap:
            confidence += 20
        else:
            confidence += 10

        # Volume expansion score
        if volume_ratio >= 2.0:
            confidence += 30
        elif volume_ratio >= 1.5:
            confidence += 25
        elif volume_ratio >= self.signal_1_volume_ratio_min:
            confidence += 20
        else:
            confidence += 10

        # Volume contraction score
        if volume_contracted:
            confidence += 20

        # MA alignment score
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        # Check for strong bullish alignment
        if ma5 > ma10 > ma30:
            if (ma5 - ma10) / ma10 > 0.02:  # More than 2% separation
                confidence += 20
            else:
                confidence += 15
        else:
            confidence += 5

        return min(confidence, 100)
