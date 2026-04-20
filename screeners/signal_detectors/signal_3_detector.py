"""
Signal 3 detector: Acceleration chase - Volume breakout above duck head high.

Logic:
- Identify duck head high (local high before golden cross)
- Detect price breakout with volume expansion
- Check for sector resonance (optional)
- This is a right-side momentum signal
"""

import pandas as pd
from datetime import date
from typing import Optional

from .base_detector import BaseDetector
from signal_models.signal_detection import SignalDetection
from signal_models.signal_types import SignalType


class Signal3Detector(BaseDetector):
    """
    Detector for Signal 3: 加速追买・放量突破鸭头前高.

    This signal detects the momentum entry point when:
    1. Duck head high is identified (local high before golden cross)
    2. Price breaks out above duck head high
    3. Volume expands significantly at breakout
    4. (Optional) Sector shows strength

    This is a right-side, momentum-driven signal with high breakout potential.
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float, min_weeks: int,
                 signal_3_breakout_lookback: int,
                 position_size_signal_3_min: float, position_size_signal_3_max: float):
        """
        Initialize Signal 3 detector.

        Args:
            ma5_period: MA5 period in weeks
            ma10_period: MA10 period in weeks
            ma30_period: MA30 period in weeks
            local_high_window: Window size for local high identification
            volume_contraction_threshold: Volume contraction threshold
            min_gap: Minimum gap between MA5 and MA10
            max_gap: Maximum gap between MA5 and MA10
            min_weeks: Minimum number of weeks of data
            signal_3_breakout_lookback: Weeks to look back for duck head high
            position_size_signal_3_min: Minimum position size for Signal 3
            position_size_signal_3_max: Maximum position size for Signal 3
        """
        super().__init__(ma5_period, ma10_period, ma30_period,
                       local_high_window, volume_contraction_threshold,
                       min_gap, max_gap)
        self.min_weeks = min_weeks
        self.signal_3_breakout_lookback = signal_3_breakout_lookback
        self.position_size_signal_3_min = position_size_signal_3_min
        self.position_size_signal_3_max = position_size_signal_3_max

    def detect(self, stock_code: str, stock_name: str,
              target_date: str) -> Optional[SignalDetection]:
        """
        Detect Signal 3 for a stock.

        Args:
            stock_code: Stock code
            stock_name: Stock name
            target_date: Target date for detection

        Returns:
            SignalDetection if signal found, None otherwise
        """
        df = self.load_stock_data(stock_code, target_date, self.min_weeks)
        if df is None or len(df) < self.ma30_period + 10:
            return None

        # Find duck head high
        duck_head_index = self.find_local_high(df, self.signal_3_breakout_lookback)
        if duck_head_index == -1:
            return None

        duck_head_high = df.iloc[duck_head_index]['high']

        # Check recent weeks for breakout
        for i in range(len(df) - 1, max(duck_head_index, len(df) - 5), -1):
            signal = self._check_breakout_pattern(
                df, i, duck_head_index, duck_head_high,
                stock_code, stock_name, target_date
            )
            if signal:
                return signal

        return None

    def _check_breakout_pattern(self, df: pd.DataFrame, index: int,
                              duck_head_index: int, duck_head_high: float,
                              stock_code: str, stock_name: str,
                              target_date: str) -> Optional[SignalDetection]:
        """
        Check for breakout pattern at given index.

        The breakout pattern consists of:
        1. Price breaks out above duck head high
        2. Volume expands significantly at breakout
        3. MA alignment is bullish
        """
        if index <= duck_head_index:
            return None

        current_high = df.iloc[index]['high']
        current_close = df.iloc[index]['close']

        # Check if price broke out above duck head high
        breakout_percent = ((current_close - duck_head_high) / duck_head_high) * 100

        # Breakout should be between 1% and 10%
        if breakout_percent < 1.0 or breakout_percent > 10.0:
            return None

        # Check volume expansion
        current_volume_ratio = df.iloc[index]['volume_ratio']
        if current_volume_ratio < 1.5:  # At least 50% above average
            return None

        # Check MA alignment
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        if not (ma5 > ma10 > ma30):
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(
            df, index, duck_head_index, breakout_percent, current_volume_ratio
        )

        # Calculate stop loss (below breakout point or MA30)
        stop_loss = min(duck_head_high * 0.98, ma30 * 0.97)

        # Determine position size based on confidence
        if confidence >= 85:
            suggested_position = "aggressive"
        elif confidence >= 70:
            suggested_position = "moderate"
        else:
            suggested_position = "conservative"

        return SignalDetection(
            signal_type=SignalType.SIGNAL_3.value,
            stock_code=stock_code,
            stock_name=stock_name,
            detection_date=pd.to_datetime(target_date).date(),
            confidence=confidence,
            gap=df.iloc[index]['ma_gap'],
            volume_ratio=current_volume_ratio,
            price=current_close,
            duck_head_high=duck_head_high,
            stop_loss=stop_loss,
            suggested_position=suggested_position,
            description=f"Signal 3: Volume breakout. Breakout: {breakout_percent:.2f}%, Volume ratio: {current_volume_ratio:.2f}",
            technical_details={
                'ma5': ma5,
                'ma10': ma10,
                'ma30': ma30,
                'duck_head_index': duck_head_index,
                'duck_head_high': duck_head_high,
                'breakout_percent': breakout_percent,
                'breakout_index': index
            }
        )

    def _calculate_confidence(self, df: pd.DataFrame, index: int,
                           duck_head_index: int, breakout_percent: float,
                           volume_ratio: float) -> float:
        """
        Calculate confidence score for Signal 3.

        Factors:
        1. Breakout magnitude: 30 points
        2. Volume expansion: 40 points
        3. MA alignment: 20 points
        4. Price momentum: 10 points

        Returns:
            Confidence score (0-100)
        """
        confidence = 0

        # Breakout score (3-5% is optimal)
        if 2.0 <= breakout_percent <= 5.0:
            confidence += 30
        elif 1.0 <= breakout_percent < 2.0 or 5.0 < breakout_percent <= 7.0:
            confidence += 25
        elif 7.0 < breakout_percent <= 10.0:
            confidence += 20
        else:
            confidence += 10

        # Volume expansion score (higher is better)
        if volume_ratio >= 3.0:
            confidence += 40
        elif volume_ratio >= 2.0:
            confidence += 35
        elif volume_ratio >= 1.5:
            confidence += 30
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

        # Price momentum score (how fast it reached breakout)
        momentum_days = index - duck_head_index
        if momentum_days <= 2:  # Fast breakout is better
            confidence += 10
        elif momentum_days <= 4:
            confidence += 8
        elif momentum_days <= 6:
            confidence += 5
        else:
            confidence += 0

        return min(confidence, 100)
