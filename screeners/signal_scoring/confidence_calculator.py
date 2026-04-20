"""
Confidence calculator for signal validation.
"""

from typing import List
from signal_models.signal_detection import SignalDetection


class ConfidenceCalculator:
    """
    Calculates and validates confidence scores for signals.

    This class provides utility methods for:
    - Validating confidence thresholds
    - Comparing multiple signals
    - Ranking signals by confidence
    """

    @staticmethod
    def validate_confidence(signal: SignalDetection, min_confidence: float = 50.0) -> bool:
        """
        Validate if a signal meets minimum confidence threshold.

        Args:
            signal: Signal detection result
            min_confidence: Minimum confidence threshold (default 50)

        Returns:
            True if signal meets threshold, False otherwise
        """
        return signal.confidence >= min_confidence

    @staticmethod
    def rank_signals(signals: List[SignalDetection]) -> List[SignalDetection]:
        """
        Rank signals by confidence score in descending order.

        Args:
            signals: List of signal detection results

        Returns:
            Sorted list of signals (highest confidence first)
        """
        return sorted(signals, key=lambda s: s.confidence, reverse=True)

    @staticmethod
    def select_best_signal(signals: List[SignalDetection]) -> SignalDetection:
        """
        Select the signal with highest confidence.

        Args:
            signals: List of signal detection results

        Returns:
            Signal with highest confidence

        Raises:
            ValueError: If signals list is empty
        """
        if not signals:
            raise ValueError("Cannot select best signal from empty list")

        return max(signals, key=lambda s: s.confidence)

    @staticmethod
    def calculate_aggregate_confidence(signals: List[SignalDetection]) -> float:
        """
        Calculate aggregate confidence from multiple signals.

        This can be used when a stock generates multiple signals.
        The aggregate is a weighted average, giving more weight to
        higher confidence signals.

        Args:
            signals: List of signal detection results

        Returns:
            Aggregate confidence score (0-100)
        """
        if not signals:
            return 0.0

        # Weighted average by confidence squared (gives more weight to high confidence)
        weighted_sum = sum(s.confidence ** 2 for s in signals)
        weights = sum(s.confidence for s in signals)

        if weights == 0:
            return 0.0

        return weighted_sum / weights

    @staticmethod
    def get_confidence_level(confidence: float) -> str:
        """
        Get human-readable confidence level.

        Args:
            confidence: Confidence score (0-100)

        Returns:
            Confidence level description
        """
        if confidence >= 85:
            return "Very High"
        elif confidence >= 70:
            return "High"
        elif confidence >= 55:
            return "Medium"
        elif confidence >= 40:
            return "Low"
        else:
            return "Very Low"
