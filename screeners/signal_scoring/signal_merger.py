"""
Signal merger for combining multiple signal detection results.
"""

from typing import List, Dict
from signal_models.signal_detection import SignalDetection, ScreenerResult, TradingPosition
from signal_models.signal_types import SignalType
from .confidence_calculator import ConfidenceCalculator


class SignalMerger:
    """
    Merges multiple signal detection results into a single screener result.

    This class handles:
    - Collecting signals from all three detectors
    - Selecting the primary signal
    - Calculating stop loss and position size
    - Generating final recommendation
    """

    def __init__(self, min_confidence: float = 50.0,
                 position_size_signal_1_min: float = 1.0,
                 position_size_signal_1_max: float = 3.0,
                 position_size_signal_2_min: float = 2.0,
                 position_size_signal_2_max: float = 5.0,
                 position_size_signal_3_min: float = 3.0,
                 position_size_signal_3_max: float = 6.0):
        """
        Initialize signal merger.

        Args:
            min_confidence: Minimum confidence threshold (default 50)
            position_size_signal_1_min: Minimum position size for Signal 1
            position_size_signal_1_max: Maximum position size for Signal 1
            position_size_signal_2_min: Minimum position size for Signal 2
            position_size_signal_2_max: Maximum position size for Signal 2
            position_size_signal_3_min: Minimum position size for Signal 3
            position_size_signal_3_max: Maximum position size for Signal 3
        """
        self.min_confidence = min_confidence
        self.position_sizes = {
            'signal_1': (position_size_signal_1_min, position_size_signal_1_max),
            'signal_2': (position_size_signal_2_min, position_size_signal_2_max),
            'signal_3': (position_size_signal_3_min, position_size_signal_3_max)
        }

    def merge_signals(self, stock_code: str, stock_name: str,
                   signals: List[SignalDetection],
                   target_date) -> ScreenerResult:
        """
        Merge multiple signals into a single screener result.

        Args:
            stock_code: Stock code
            stock_name: Stock name
            signals: List of detected signals
            target_date: Target date for screening

        Returns:
            ScreenerResult with merged information
        """
        # Filter signals by minimum confidence
        valid_signals = [
            s for s in signals
            if ConfidenceCalculator.validate_confidence(s, self.min_confidence)
        ]

        if not valid_signals:
            return self._create_no_signal_result(stock_code, stock_name, target_date)

        # Rank signals by confidence
        ranked_signals = ConfidenceCalculator.rank_signals(valid_signals)

        # Select primary signal (highest confidence)
        primary_signal = ranked_signals[0]

        # Calculate position size
        position_size = self._calculate_position_size(
            primary_signal, primary_signal.confidence
        )

        # Determine recommended action
        recommended_action = self._determine_action(
            primary_signal, ranked_signals
        )

        # Calculate aggregate confidence
        best_confidence = primary_signal.confidence

        # Create result
        return ScreenerResult(
            stock_code=stock_code,
            stock_name=stock_name,
            has_signal=True,
            primary_signal=primary_signal,
            all_signals=ranked_signals,
            best_confidence=best_confidence,
            recommended_action=recommended_action,
            stop_loss_price=primary_signal.stop_loss,
            position_size=position_size,
            trade_date=target_date,
            reason=self._generate_reason(primary_signal, ranked_signals)
        )

    def _create_no_signal_result(self, stock_code: str, stock_name: str,
                               target_date) -> ScreenerResult:
        """
        Create a result object when no signals are detected.

        Args:
            stock_code: Stock code
            stock_name: Stock name
            target_date: Target date

        Returns:
            ScreenerResult with has_signal=False
        """
        return ScreenerResult(
            stock_code=stock_code,
            stock_name=stock_name,
            has_signal=False,
            primary_signal=None,
            all_signals=[],
            best_confidence=0.0,
            recommended_action="NO_ACTION",
            stop_loss_price=None,
            position_size="0",
            trade_date=target_date,
            reason="No signal detected or confidence below threshold"
        )

    def _calculate_position_size(self, signal: SignalDetection,
                                confidence: float) -> str:
        """
        Calculate position size based on signal type and confidence.

        Args:
            signal: Primary signal
            confidence: Confidence score (0-100)

        Returns:
            Position size as string
        """
        # Get position size range for signal type
        min_size, max_size = self.position_sizes.get(
            signal.signal_type, (1.0, 3.0)
        )

        # Calculate actual position size based on confidence
        confidence_ratio = confidence / 100.0
        position_size = min_size + (max_size - min_size) * confidence_ratio

        return f"{position_size:.2f}"

    def _determine_action(self, primary_signal: SignalDetection,
                        all_signals: List[SignalDetection]) -> str:
        """
        Determine recommended trading action.

        Args:
            primary_signal: The primary signal
            all_signals: All detected signals

        Returns:
            Recommended action string
        """
        confidence = primary_signal.confidence
        signal_type = primary_signal.signal_type

        if signal_type == SignalType.SIGNAL_1.value:
            if confidence >= 70:
                return "BUY_AGGRESSIVE"
            elif confidence >= 55:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"

        elif signal_type == SignalType.SIGNAL_2.value:
            if confidence >= 75:
                return "BUY_AGGRESSIVE"
            elif confidence >= 60:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"

        elif signal_type == SignalType.SIGNAL_3.value:
            if confidence >= 80:
                return "BUY_AGGRESSIVE"
            elif confidence >= 65:
                return "BUY_MODERATE"
            else:
                return "BUY_CONSERVATIVE"

        return "WAIT"

    def _generate_reason(self, primary_signal: SignalDetection,
                       all_signals: List[SignalDetection]) -> str:
        """
        Generate reason description for the screening result.

        Args:
            primary_signal: The primary signal
            all_signals: All detected signals

        Returns:
            Reason description string
        """
        if not all_signals:
            return "No valid signals detected"

        signal_descriptions = {
            'signal_1': '激进买点 (鸭鼻孔缩量金叉)',
            'signal_2': '核心主买 (鸭嘴开口金叉)',
            'signal_3': '加速追买 (放量突破鸭头前高)'
        }

        # Start with primary signal
        signal_desc = signal_descriptions.get(
            primary_signal.signal_type,
            f'未知信号 ({primary_signal.signal_type})'
        )

        reason_parts = [
            f"主要信号: {signal_desc}",
            f"置信度: {primary_signal.confidence:.1f}%"
        ]

        # Add multiple signal information
        if len(all_signals) > 1:
            other_signals = [
                signal_descriptions.get(s.signal_type, s.signal_type)
                for s in all_signals[1:]
            ]
            reason_parts.append(f"其他信号: {', '.join(other_signals)}")

        # Add technical details
        if primary_signal.technical_details:
            details = []
            if 'gap' in primary_signal.technical_details or primary_signal.gap != 0:
                details.append(f"MA缺口: {primary_signal.gap:.2f}%")
            if 'volume_ratio' in primary_signal.technical_details or primary_signal.volume_ratio != 0:
                details.append(f"量比: {primary_signal.volume_ratio:.2f}")
            if primary_signal.stop_loss:
                details.append(f"止损价: {primary_signal.stop_loss:.2f}")
            if details:
                reason_parts.append(' | '.join(details))

        return '。'.join(reason_parts)
