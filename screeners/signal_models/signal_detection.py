"""
Data classes for signal detection results.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from enum import Enum


class TradingPosition(Enum):
    """Trading position suggestion."""
    CONSERVATIVE = "conservative"  # Conservative position size
    MODERATE = "moderate"  # Moderate position size
    AGGRESSIVE = "aggressive"  # Aggressive position size


@dataclass
class SignalDetection:
    """
    Result of a single signal detection.

    Attributes:
        signal_type: Type of signal detected
        stock_code: Stock code
        stock_name: Stock name
        detection_date: Date when signal was detected
        confidence: Confidence score (0-100)
        gap: Gap between MA5 and MA10 (percentage)
        volume_ratio: Current volume to average volume ratio
        price: Current stock price
        duck_head_high: Duck head high price (for Signal 3)
        stop_loss: Suggested stop loss price
        suggested_position: Suggested position size
        description: Description of the signal
        technical_details: Dictionary of technical indicators
    """
    signal_type: str
    stock_code: str
    stock_name: str
    detection_date: date
    confidence: float
    gap: float
    volume_ratio: float
    price: float
    duck_head_high: Optional[float] = None
    stop_loss: Optional[float] = None
    suggested_position: Optional[str] = None
    description: str = ""
    technical_details: dict = None

    def __post_init__(self):
        if self.technical_details is None:
            self.technical_details = {}

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            'signal_type': self.signal_type,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'detection_date': self.detection_date.isoformat() if self.detection_date else None,
            'confidence': self.confidence,
            'gap': self.gap,
            'volume_ratio': self.volume_ratio,
            'price': self.price,
            'duck_head_high': self.duck_head_high,
            'stop_loss': self.stop_loss,
            'suggested_position': self.suggested_position,
            'description': self.description,
            'technical_details': self.technical_details
        }


@dataclass
class ScreenerResult:
    """
    Result of the screener execution for a single stock.

    Attributes:
        stock_code: Stock code
        stock_name: Stock name
        has_signal: Whether any signal was detected
        primary_signal: The primary signal detected (highest confidence)
        all_signals: All detected signals
        best_confidence: Highest confidence score among all signals
        recommended_action: Recommended trading action
        stop_loss_price: Suggested stop loss price
        position_size: Suggested position size
        trade_date: Date when the signal is valid
        reason: Explanation of the screening result
    """
    stock_code: str
    stock_name: str
    has_signal: bool
    primary_signal: Optional[SignalDetection]
    all_signals: list[SignalDetection]
    best_confidence: float
    recommended_action: str
    stop_loss_price: Optional[float]
    position_size: str
    trade_date: date
    reason: str

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'has_signal': self.has_signal,
            'primary_signal': self.primary_signal.to_dict() if self.primary_signal else None,
            'all_signals': [s.to_dict() for s in self.all_signals],
            'best_confidence': self.best_confidence,
            'recommended_action': self.recommended_action,
            'stop_loss_price': self.stop_loss_price,
            'position_size': self.position_size,
            'trade_date': self.trade_date.isoformat() if self.trade_date else None,
            'reason': self.reason
        }
