"""
Signal type enumeration for the three-signal system.
"""

from enum import Enum


class SignalType(Enum):
    """
    Signal types for Lao Ya Tou Zhou Xian pattern.

    Signal 1: 激进买点・鸭鼻孔缩量金叉 (Aggressive entry - Duck nostril shrinkage golden cross)
    Signal 2: 核心主买・鸭嘴开口金叉 (Core main entry - Duck mouth opening golden cross)
    Signal 3: 加速追买・放量突破鸭头前高 (Acceleration chase - Volume breakout above duck head high)
    """
    SIGNAL_1 = "signal_1"  # Duck nostril golden cross with volume contraction
    SIGNAL_2 = "signal_2"  # Duck mouth opening with multiple alignment
    SIGNAL_3 = "signal_3"  # Volume breakout above duck head high

    def get_display_name(self):
        """Get Chinese display name for the signal."""
        names = {
            self.SIGNAL_1: "信号一：激进买点・鸭鼻孔缩量金叉",
            self.SIGNAL_2: "信号二：核心主买・鸭嘴开口金叉",
            self.SIGNAL_3: "信号三：加速追买・放量突破鸭头前高"
        }
        return names[self]
