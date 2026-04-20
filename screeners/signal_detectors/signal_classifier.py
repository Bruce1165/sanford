"""
Signal classifier - Stage 2 classification.

This classifier determines which specific signal phase each qualified stock is in:
- Signal 1: 激进买点・鸭鼻孔缩量金叉 (Duck nostril golden cross with volume contraction)
- Signal 2: 核心主买・鸭嘴开口金叉 (Duck mouth opening with confirmation)
- Signal 3: 加速追买・放量突破鸭头前高 (Volume breakout above duck head high)
"""

import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SignalClassifier:
    """
    Classifies qualified Lao Ya Tou stocks into specific signal phases.

    This is Stage 2 of the two-stage architecture:
    - Runs on the pool of stocks identified by BaseLaoYaTouDetector
    - Determines which signal (1, 2, or 3) each stock matches
    - Provides confidence score and signal details

    Output: Each stock labeled with Signal 1, Signal 2, or Signal 3
    """

    def __init__(self, ma5_period: int, ma10_period: int, ma30_period: int,
                 local_high_window: int, volume_contraction_threshold: float,
                 min_gap: float, max_gap: float,
                 signal_1_min_gap: float, signal_1_volume_ratio_min: float,
                 signal_2_confirm_days: int,
                 signal_3_breakout_lookback: int):
        """
        Initialize signal classifier.

        Args:
            ma5_period: MA5 period in days
            ma10_period: MA10 period in days
            ma30_period: MA30 period in days
            local_high_window: Window size for local high identification
            volume_contraction_threshold: Volume contraction threshold
            min_gap: Minimum gap between MA5 and MA10
            max_gap: Maximum gap between MA5 and MA10
            signal_1_min_gap: Minimum gap for Signal 1
            signal_1_volume_ratio_min: Minimum volume ratio for Signal 1
            signal_2_confirm_days: Confirmation days for Signal 2
            signal_3_breakout_lookback: Lookback days for Signal 3 breakout
        """
        self.ma5_period = ma5_period
        self.ma10_period = ma10_period
        self.ma30_period = ma30_period
        self.local_high_window = local_high_window
        self.volume_contraction_threshold = volume_contraction_threshold
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.signal_1_min_gap = signal_1_min_gap
        self.signal_1_volume_ratio_min = signal_1_volume_ratio_min
        self.signal_2_confirm_days = signal_2_confirm_days
        self.signal_3_breakout_lookback = signal_3_breakout_lookback

    def detect_crossing(self, df: pd.DataFrame, fast_col: str, slow_col: str,
                     index: int) -> str:
        """Detect MA crossing type."""
        if index < 1:
            return 'no_cross'

        fast_curr = df.iloc[index][fast_col]
        fast_prev = df.iloc[index - 1][fast_col]
        slow_curr = df.iloc[index][slow_col]
        slow_prev = df.iloc[index - 1][slow_col]

        if fast_curr > slow_curr and fast_prev <= slow_prev:
            return 'golden_cross'
        if fast_curr < slow_curr and fast_prev >= slow_prev:
            return 'death_cross'
        return 'no_cross'

    def find_local_high(self, df: pd.DataFrame, window: int, index: int) -> Optional[int]:
        """Find local high point before given index."""
        if index < window * 2:
            return None

        for i in range(index - 1, max(0, index - window), -1):
            is_local_high = True
            current_high = df.iloc[i]['high']

            for j in range(i - window, min(len(df), i + window + 1)):
                if j < 0 or j >= len(df):
                    continue
                if j != i and df.iloc[j]['high'] >= current_high:
                    is_local_high = False
                    break

            if is_local_high:
                return i

        return None

    def classify_signal_1(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Classify as Signal 1: Duck nostril golden cross.

        Pattern:
        1. Recent golden cross (MA5 crosses above MA10)
        2. Small gap between MA5 and MA10
        3. Volume contraction during the nostril period
        4. Volume expansion after golden cross
        """
        for i in range(len(df) - 1, max(0, len(df) - 5), -1):
            # Check for golden cross
            crossing = self.detect_crossing(df, 'ma5', 'ma10', i)
            if crossing != 'golden_cross':
                continue

            # Check gap size
            current_gap = df.iloc[i]['ma_gap']
            if abs(current_gap) > self.signal_1_min_gap:
                continue

            # Check for death cross before golden cross (nostril formation)
            death_cross_index = -1
            for j in range(i - 1, max(0, i - 10), -1):
                crossing_dc = self.detect_crossing(df, 'ma5', 'ma10', j)
                if crossing_dc == 'death_cross':
                    death_cross_index = j
                    break

            if death_cross_index == -1:
                continue

            # Check volume contraction during nostril
            if death_cross_index > 0:
                pre_nostril_vol = df.iloc[death_cross_index - 5:death_cross_index]['volume'].mean()
                nostril_vol = df.iloc[death_cross_index:i]['volume'].mean()

                if pre_nostril_vol > 0:
                    contracted = nostril_vol / pre_nostril_vol <= self.volume_contraction_threshold
                else:
                    contracted = False
            else:
                contracted = False

            # Check volume expansion
            current_volume_ratio = df.iloc[i]['volume_ratio']
            expanded = current_volume_ratio >= self.signal_1_volume_ratio_min

            if not contracted or not expanded:
                continue

            # Check MA30 support
            ma30 = df.iloc[i]['ma30']
            ma5 = df.iloc[i]['ma5']
            ma10 = df.iloc[i]['ma10']

            if ma5 <= ma30 or ma10 <= ma30:
                continue

            # Calculate confidence
            confidence = self._calculate_confidence_signal_1(
                df, i, current_gap, current_volume_ratio, contracted
            )

            return {
                'signal_type': 'signal_1',
                'index': i,
                'confidence': confidence,
                'gap': current_gap,
                'volume_ratio': current_volume_ratio,
                'price': df.iloc[i]['close'],
                'description': f'Signal 1: Duck nostril golden cross. MA gap: {current_gap:.2f}%, Volume ratio: {current_volume_ratio:.2f}'
            }

        return None

    def classify_signal_2(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Classify as Signal 2: Duck mouth opening.

        Pattern:
        1. Golden cross with wide gap (duck mouth opening)
        2. MA5 > MA10 > MA30 (bullish alignment)
        3. Volume contraction followed by expansion
        4. Confirmation over subsequent days
        """
        for i in range(len(df) - 1, max(0, len(df) - self.signal_2_confirm_days - 2), -1):
            # Check for golden cross
            crossing = self.detect_crossing(df, 'ma5', 'ma10', i)
            if crossing != 'golden_cross':
                continue

            # Check gap size
            current_gap = df.iloc[i]['ma_gap']
            if current_gap < self.min_gap or current_gap > self.max_gap:
                continue

            # Check bullish alignment
            ma5 = df.iloc[i]['ma5']
            ma10 = df.iloc[i]['ma10']
            ma30 = df.iloc[i]['ma30']

            if not (ma5 > ma10 > ma30):
                continue

            # Check volume pattern
            if not self._check_volume_pattern(df, i):
                continue

            # Check confirmation
            if i + self.signal_2_confirm_days >= len(df):
                continue

            confirmed = True
            for j in range(1, self.signal_2_confirm_days + 1):
                ma5_c = df.iloc[i + j]['ma5']
                ma10_c = df.iloc[i + j]['ma10']
                ma30_c = df.iloc[i + j]['ma30']

                if not (ma5_c > ma10_c > ma30_c):
                    confirmed = False
                    break

            if not confirmed:
                continue

            # Calculate confidence
            current_volume_ratio = df.iloc[i]['volume_ratio']
            confidence = self._calculate_confidence_signal_2(
                df, i, current_gap, current_volume_ratio, confirmed
            )

            return {
                'signal_type': 'signal_2',
                'index': i,
                'confidence': confidence,
                'gap': current_gap,
                'volume_ratio': current_volume_ratio,
                'price': df.iloc[i]['close'],
                'description': f'Signal 2: Duck mouth opening. MA gap: {current_gap:.2f}%, Volume ratio: {current_volume_ratio:.2f}'
            }

        return None

    def classify_signal_3(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Classify as Signal 3: Volume breakout above duck head high.

        Pattern:
        1. Find duck head high (local high before golden cross)
        2. Price breaks out above duck head high
        3. Volume expands significantly at breakout
        """
        # Find duck head high
        duck_head_index = self.find_local_high(df, self.signal_3_breakout_lookback, len(df) - 1)
        if duck_head_index is None:
            return None

        duck_head_high = df.iloc[duck_head_index]['high']

        # Check for breakout
        for i in range(len(df) - 1, max(duck_head_index, len(df) - 5), -1):
            current_high = df.iloc[i]['high']
            current_close = df.iloc[i]['close']

            # Check if price broke out
            breakout_percent = ((current_close - duck_head_high) / duck_head_high) * 100

            # Breakout should be between 1% and 10%
            if breakout_percent < 1.0 or breakout_percent > 10.0:
                continue

            # Check volume expansion
            current_volume_ratio = df.iloc[i]['volume_ratio']
            if current_volume_ratio < 1.5:
                continue

            # Check MA alignment
            ma5 = df.iloc[i]['ma5']
            ma10 = df.iloc[i]['ma10']
            ma30 = df.iloc[i]['ma30']

            if not (ma5 > ma10 > ma30):
                continue

            # Calculate confidence
            confidence = self._calculate_confidence_signal_3(
                df, i, duck_head_index, breakout_percent, current_volume_ratio
            )

            return {
                'signal_type': 'signal_3',
                'index': i,
                'confidence': confidence,
                'gap': df.iloc[i]['ma_gap'],
                'volume_ratio': current_volume_ratio,
                'price': current_close,
                'duck_head_high': duck_head_high,
                'description': f'Signal 3: Volume breakout. Breakout: {breakout_percent:.2f}%, Volume ratio: {current_volume_ratio:.2f}'
            }

        return None

    def _check_volume_pattern(self, df: pd.DataFrame, index: int) -> bool:
        """Check volume pattern for Signal 2."""
        if index < 5:
            return False

        pre_pullback_vol = df.iloc[index - 5:index - 2]['volume'].mean()
        pullback_vol = df.iloc[index - 2:index]['volume'].mean()
        current_vol = df.iloc[index]['volume']

        if pre_pullback_vol == 0:
            return False

        contracted = pullback_vol / pre_pullback_vol <= self.volume_contraction_threshold
        expanded = current_vol / pullback_vol >= 1.5

        return contracted and expanded

    def _calculate_confidence_signal_1(self, df: pd.DataFrame, index: int,
                                       gap: float, volume_ratio: float,
                                       volume_contracted: bool) -> float:
        """Calculate confidence for Signal 1."""
        confidence = 0

        # Gap score (smaller is better)
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
        else:
            confidence += 10

        # Volume contraction score
        if volume_contracted:
            confidence += 20

        # MA alignment score
        ma5 = df.iloc[index]['ma5']
        ma10 = df.iloc[index]['ma10']
        ma30 = df.iloc[index]['ma30']

        if ma5 > ma10 > ma30 and (ma5 - ma10) / ma10 > 0.02:
            confidence += 20
        elif ma5 > ma10 > ma30:
            confidence += 15
        else:
            confidence += 5

        return min(confidence, 100)

    def _calculate_confidence_signal_2(self, df: pd.DataFrame, index: int,
                                       gap: float, volume_ratio: float,
                                       confirmed: bool) -> float:
        """Calculate confidence for Signal 2."""
        confidence = 0

        # Gap score
        if self.min_gap <= gap <= (self.min_gap + 2.0):
            confidence += 30
        elif (self.min_gap + 2.0) < gap <= (self.min_gap + 4.0):
            confidence += 25
        else:
            confidence += 10

        # Volume expansion score
        if volume_ratio >= 2.0:
            confidence += 30
        elif volume_ratio >= 1.5:
            confidence += 25
        else:
            confidence += 10

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

    def _calculate_confidence_signal_3(self, df: pd.DataFrame, index: int,
                                       duck_head_index: int, breakout_percent: float,
                                       volume_ratio: float) -> float:
        """Calculate confidence for Signal 3."""
        confidence = 0

        # Breakout score
        if 2.0 <= breakout_percent <= 5.0:
            confidence += 30
        elif 1.0 <= breakout_percent < 2.0 or 5.0 < breakout_percent <= 7.0:
            confidence += 25
        elif 7.0 < breakout_percent <= 10.0:
            confidence += 20
        else:
            confidence += 10

        # Volume expansion score
        if volume_ratio >= 3.0:
            confidence += 40
        elif volume_ratio >= 2.0:
            confidence += 35
        elif volume_ratio >= 1.5:
            confidence += 30
        else:
            confidence += 10

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
            confidence += 5

        # Price momentum score
        momentum_days = index - duck_head_index
        if momentum_days <= 2:
            confidence += 10
        elif momentum_days <= 4:
            confidence += 8
        elif momentum_days <= 6:
            confidence += 5
        else:
            confidence += 0

        return min(confidence, 100)

    def classify(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Classify which signal a stock is in.

        Args:
            df: DataFrame with stock data (already has Lao Ya Tou pattern)

        Returns:
            Signal classification with type and confidence
        """
        logger.debug(f"SignalClassifier: Starting classification with {len(df)} rows")

        # Try Signal 2 first (core signal, most reliable)
        result = self.classify_signal_2(df)
        if result:
            logger.debug(f"SignalClassifier: Matched Signal 2")
            return result

        # Try Signal 3 (momentum signal)
        result = self.classify_signal_3(df)
        if result:
            logger.debug(f"SignalClassifier: Matched Signal 3")
            return result

        # Try Signal 1 (early aggressive signal)
        result = self.classify_signal_1(df)
        if result:
            logger.debug(f"SignalClassifier: Matched Signal 1")
            return result

        logger.debug(f"SignalClassifier: No signal matched")
        return None
