#!/usr/bin/env python3
"""
Array Utilities for Stock Screeners
Efficient array/vector operations for technical analysis
"""

from typing import List, Tuple, Optional, Dict
import numpy as np


class ArrayUtils:
    """Utility class for efficient array operations"""

    @staticmethod
    def calculate_ema_vectorized(prices: List[float], period: int) -> List[float]:
        """
        Calculate EMA using numpy for efficiency

        EMA formula: EMA_today = (Price_today × (2 / (period + 1))) + EMA_yesterday × (1 - (2 / (period + 1)))

        Args:
            prices: List of prices
            period: EMA period (e.g., 5, 10, 30)

        Returns:
            List of EMA values
        """
        if len(prices) < period:
            return []

        prices_array = np.array(prices, dtype=np.float64)
        emas = np.zeros_like(prices_array)

        multiplier = 2.0 / (period + 1.0)
        emas[0] = prices_array[0]

        # Vectorized calculation
        for i in range(1, len(prices_array)):
            emas[i] = prices_array[i] * multiplier + emas[i - 1] * (1.0 - multiplier)

        return emas.tolist()

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average using numpy"""
        if len(prices) < period:
            return []

        prices_array = np.array(prices, dtype=np.float64)
        return np.convolve(prices_array, np.ones(period) / period, mode='valid').tolist()

    @staticmethod
    def calculate_std(prices: List[float], period: int) -> List[float]:
        """Calculate rolling standard deviation using numpy"""
        if len(prices) < period:
            return []

        prices_array = np.array(prices, dtype=np.float64)
        stds = []

        for i in range(period - 1, len(prices_array)):
            window = prices_array[i - period + 1:i + 1]
            stds.append(np.std(window))

        # Pad with NaNs at beginning
        return [np.nan] * (period - 1) + stds

    @staticmethod
    def find_local_extremes(
        prices: List[float],
        window: int = 30,
        mode: str = 'high'
    ) -> Tuple[float, int]:
        """
        Find local high or low within a window

        Args:
            prices: List of prices
            window: Window size to search within (default: 30)
            mode: 'high' or 'low'

        Returns:
            Tuple of (extreme_price, extreme_index)
        """
        if len(prices) == 0:
            return 0.0, 0

        window_size = min(window, len(prices))
        recent_prices = prices[-window_size:]

        if mode == 'high':
            extreme_price = float(np.max(recent_prices))
        else:  # low
            extreme_price = float(np.min(recent_prices))

        extreme_idx = len(prices) - window_size + recent_prices.index(extreme_price)

        return extreme_price, extreme_idx

    @staticmethod
    def detect_crossings(
        series_a: List[float],
        series_b: List[float],
        crossing_type: str = 'up'
    ) -> List[int]:
        """
        Detect cross points between two series

        Args:
            series_a: First series (e.g., MA5)
            series_b: Second series (e.g., MA10)
            crossing_type: 'up' for A crosses above B, 'down' for A crosses below B

        Returns:
            List of indices where crossing occurs
        """
        if len(series_a) < 2 or len(series_b) < 2:
            return []

        series_a_array = np.array(series_a)
        series_b_array = np.array(series_b)

        if crossing_type == 'up':
            # Previous: A <= B, Current: A > B
            crossings = np.where(
                (series_a_array[1:] > series_b_array[1:]) &
                (series_a_array[:-1] <= series_b_array[:-1])
            )[0] + 1
        else:  # down
            # Previous: A >= B, Current: A < B
            crossings = np.where(
                (series_a_array[1:] < series_b_array[1:]) &
                (series_a_array[:-1] >= series_b_array[:-1])
            )[0] + 1

        return crossings.tolist()

    @staticmethod
    def calculate_gaps(
        series_a: List[float],
        series_b: List[float],
        indices: List[int]
    ) -> List[float]:
        """
        Calculate absolute gap sizes between two series at specific indices

        Args:
            series_a: First series
            series_b: Second series
            indices: List of indices to calculate gaps at

        Returns:
            List of gap sizes (absolute difference)
        """
        if len(series_a) == 0 or len(series_b) == 0:
            return []

        series_a_array = np.array(series_a)
        series_b_array = np.array(series_b)

        # Vectorized gap calculation at specified indices
        gaps = np.abs(series_a_array[indices] - series_b_array[indices])

        return gaps.tolist()

    @staticmethod
    def calculate_volume_ratios(
        volumes: List[float],
        window_start: int,
        window_end: int
    ) -> List[float]:
        """
        Calculate volume ratios to average for a window

        Args:
            volumes: List of volumes
            window_start: Start index of window
            window_end: End index of window (exclusive)

        Returns:
            List of volume ratios for each point in window
        """
        if len(volumes) == 0 or window_start >= window_end:
            return []

        volumes_array = np.array(volumes, dtype=np.float64)
        window_volumes = volumes_array[window_start:window_end]

        if len(window_volumes) == 0:
            return []

        avg_volume = np.mean(window_volumes)
        volume_ratios = volumes_array[window_start:window_end] / avg_volume

        return volume_ratios.tolist()

    @staticmethod
    def find_contraction_periods(
        volumes: List[float],
        pullback_start: int = 0,
        threshold: float = 0.8,
        min_consecutive: int = 2
    ) -> List[List[int]]:
        """
        Find periods where volume contracts below threshold

        Args:
            volumes: List of volumes
            pullback_start: Index from which to start average calculation (default: 0 = use all data)
            threshold: Contraction threshold (default: 0.8 = 80% of average)
            min_consecutive: Minimum consecutive periods (default: 2)

        Returns:
            List of period ranges (start_idx, end_idx)
        """
        if len(volumes) == 0:
            return []

        volumes_array = np.array(volumes, dtype=np.float64)

        # Calculate average volume from pullback start (or all data if pullback_start=0)
        if pullback_start > 0:
            pullback_volumes = volumes_array[pullback_start:]
            avg_volume = np.mean(pullback_volumes) if len(pullback_volumes) > 0 else np.mean(volumes_array)
        else:
            avg_volume = np.mean(volumes_array)

        # Boolean mask for contraction periods
        is_contracting = volumes_array < (avg_volume * threshold)

        # Find contraction ranges (consecutive periods)
        contraction_periods = []
        current_start = None

        for i, contracting in enumerate(is_contracting.tolist()):
            if contracting and current_start is None:
                current_start = i
            elif not contracting and current_start is not None:
                period_length = i - current_start
                if period_length >= min_consecutive:
                    contraction_periods.append([current_start, i])
                current_start = None

        # Handle trailing contraction
        if current_start is not None and is_contracting[-1]:
            period_length = len(volumes) - current_start
            if period_length >= min_consecutive:
                contraction_periods.append([current_start, len(volumes)])

        return contraction_periods

    @staticmethod
    def calculate_momentum(
        prices: List[float],
        period: int = 10
    ) -> List[float]:
        """
        Calculate momentum (rate of change)

        Args:
            prices: List of prices
            period: Period for momentum calculation (default: 10)

        Returns:
            List of momentum values
        """
        if len(prices) < period + 1:
            return []

        prices_array = np.array(prices, dtype=np.float64)

        # Rate of change over period
        momentum = (prices_array[period:] - prices_array[:-period]) / prices_array[:-period]

        # Pad with NaNs at beginning
        return [np.nan] * period + momentum.tolist()

    @staticmethod
    def detect_trend(
        prices: List[float],
        lookback: int = 20
    ) -> str:
        """
        Detect overall trend direction

        Args:
            prices: List of prices
            lookback: Number of periods to analyze (default: 20)

        Returns:
            'up', 'down', or 'sideways'
        """
        if len(prices) < lookback:
            return 'sideways'

        recent_prices = prices[-lookback:]
        prices_array = np.array(recent_prices, dtype=np.float64)

        # Simple linear regression slope
        x = np.arange(len(prices_array))
        y = prices_array

        # Calculate slope using least squares
        A = np.vstack([x, np.ones(len(x))]).T
        slope = np.linalg.lstsq(A, y, rcond=None)[0][0]

        if slope > 0.01:  # Upward trend
            return 'up'
        elif slope < -0.01:  # Downward trend
            return 'down'
        else:
            return 'sideways'

    @staticmethod
    def calculate_rsi(
        prices: List[float],
        period: int = 14
    ) -> List[float]:
        """
        Calculate Relative Strength Index (RSI)

        Args:
            prices: List of prices
            period: RSI period (default: 14)

        Returns:
            List of RSI values
        """
        if len(prices) < period + 1:
            return []

        prices_array = np.array(prices, dtype=np.float64)

        # Calculate price changes
        deltas = np.diff(prices_array)

        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gains and losses
        avg_gains = np.convolve(gains, np.ones(period) / period, mode='valid')
        avg_losses = np.convolve(losses, np.ones(period) / period, mode='valid')

        # Calculate RS (Relative Strength)
        rs = avg_gains / np.where(avg_losses == 0, 1e-10, avg_losses)

        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))

        # Pad with NaNs at beginning
        return [np.nan] * period + rsi.tolist()

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_multiplier: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate Bollinger Bands

        Args:
            prices: List of prices
            period: Period for moving average (default: 20)
            std_multiplier: Standard deviation multiplier (default: 2.0)

        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        if len(prices) < period:
            return [], [], []

        sma = ArrayUtils.calculate_sma(prices, period)
        std = ArrayUtils.calculate_std(prices, period)

        # Convert to arrays
        sma_array = np.array(sma)
        std_array = np.array(std)

        # Calculate bands
        upper_band = sma_array + std_array * std_multiplier
        lower_band = sma_array - std_array * std_multiplier

        return upper_band.tolist(), sma, lower_band.tolist()


# Convenience functions for common operations

def calculate_all_emas(prices: List[float], periods: Tuple[int, int, int] = (5, 10, 30)) -> Tuple[List[float], List[float], List[float]]:
    """
    Calculate multiple EMAs at once

    Args:
        prices: List of prices
        periods: Tuple of (ma5, ma10, ma30) periods

    Returns:
        Tuple of (ma5, ma10, ma30) lists
    """
    ma5 = ArrayUtils.calculate_ema_vectorized(prices, periods[0])
    ma10 = ArrayUtils.calculate_ema_vectorized(prices, periods[1])
    ma30 = ArrayUtils.calculate_ema_vectorized(prices, periods[2])
    return ma5, ma10, ma30


def analyze_arrangement(ma_short: List[float], ma_medium: List[float], ma_long: List[float]) -> Dict:
    """
    Analyze moving average arrangement

    Args:
        ma_short: Short-term MA (e.g., MA5)
        ma_medium: Medium-term MA (e.g., MA10)
        ma_long: Long-term MA (e.g., MA30)

    Returns:
        Dict with arrangement status and metrics
    """
    if len(ma_short) == 0:
        return {'status': 'insufficient_data', 'bull_count': 0, 'bear_count': 0}

    # Count periods with each arrangement
    bull_count = 0  # MA_short > MA_medium > MA_long
    bear_count = 0  # MA_short < MA_medium < MA_long

    for i in range(len(ma_short)):
        if ma_short[i] > ma_medium[i] > ma_long[i]:
            bull_count += 1
        elif ma_short[i] < ma_medium[i] < ma_long[i]:
            bear_count += 1

    total = len(ma_short)
    bull_pct = bull_count / total * 100 if total > 0 else 0
    bear_pct = bear_count / total * 100 if total > 0 else 0

    return {
        'status': 'bull' if bull_count > bear_count else 'bear' if bear_count > bull_count else 'mixed',
        'bull_count': bull_count,
        'bear_count': bear_count,
        'bull_percentage': round(bull_pct, 2),
        'bear_percentage': round(bear_pct, 2)
    }
