#!/usr/bin/env python3
"""
Base Strategy Class - 所有战法必须继承此类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import date, datetime
import json


class BaseStrategy(ABC):
    """战法基类 - 所有战法必须继承此类"""

    def __init__(self, strategy_name: str, config: Dict[str, Any]):
        """
        初始化战法

        Args:
            strategy_name: 战法唯一标识
            config: 战法配置字典
        """
        self.strategy_name = strategy_name
        self.config = config
        self.current_date = None

    @property
    def display_name(self) -> str:
        """显示名称"""
        return self.config.get('display_name', self.strategy_name)

    @property
    def description(self) -> str:
        """战法描述"""
        return self.config.get('description', '')

    @property
    def category(self) -> str:
        """战法类别"""
        return self.config.get('category', '通用')

    @property
    def version(self) -> str:
        """战法版本"""
        return self.config.get('version', 'v1.0.0')

    def set_date(self, target_date: date):
        """
        设置分析日期

        Args:
            target_date: 目标分析日期
        """
        self.current_date = target_date

    @abstractmethod
    def analyze_stock(self, code: str, name: str) -> Optional[Dict[str, Any]]:
        """
        分析单只股票

        Args:
            code: 股票代码
            name: 股票名称

        Returns:
            如果股票满足条件，返回字典:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD' | 'WATCH',
                'strength': float,  # 信号强度 0-100
                'reason': str,      # 信号原因说明
                'entry_price': float,   # 建议入场价
                'stop_loss': float,     # 止损价
                'take_profit': float,   # 止盈价
                'risk_reward_ratio': float,  # 盈亏比
                'confidence': float,    # 置信度 0-100
                'extra': dict  # 战法特定数据
            }

            如果股票不满足任何条件，返回None
        """
        pass

    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """
        返回战法需要的技术指标列表

        Returns:
            指标名称列表，例如: ['MACD', 'RSI', 'MA5', 'MA20', 'VOL_MA3']
        """
        pass

    def validate_config(self) -> bool:
        """
        验证配置是否有效

        Returns:
            配置是否有效
        """
        return True

    def get_parameter_defaults(self) -> Dict[str, Any]:
        """
        获取参数默认值

        Returns:
            参数默认值字典
        """
        return {}

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值
        """
        # 先从参数中获取，再从默认值获取
        params = self.config.get('parameters', {})
        if key in params:
            return params[key]

        return self.get_parameter_defaults().get(key, default)

    def calculate_risk_reward(self, entry_price: float, stop_loss: float,
                             take_profit: float) -> float:
        """
        计算盈亏比

        Args:
            entry_price: 入场价
            stop_loss: 止损价
            take_profit: 止盈价

        Returns:
            盈亏比 (止盈幅度 / 止损幅度)
        """
        if entry_price <= 0:
            return 0.0

        risk = abs(entry_price - stop_loss) / entry_price if stop_loss > 0 else 0.01
        reward = abs(take_profit - entry_price) / entry_price if take_profit > 0 else 0.01

        if risk == 0:
            return 0.0

        return reward / risk

    def format_signal(self, signal_type: str, strength: float, reason: str,
                     entry_price: float = None, stop_loss: float = None,
                     take_profit: float = None, confidence: float = None,
                     extra: Dict = None) -> Dict[str, Any]:
        """
        格式化信号结果

        Args:
            signal_type: 信号类型 (BUY/SELL/HOLD/WATCH)
            strength: 信号强度 (0-100)
            reason: 信号原因
            entry_price: 入场价
            stop_loss: 止损价
            take_profit: 止盈价
            confidence: 置信度 (0-100)
            extra: 额外数据

        Returns:
            格式化的信号字典
        """
        signal = {
            'signal': signal_type,
            'strength': strength,
            'reason': reason,
            'confidence': confidence or strength,
            'extra': extra or {}
        }

        if entry_price is not None:
            signal['entry_price'] = entry_price

        if stop_loss is not None:
            signal['stop_loss'] = stop_loss

        if take_profit is not None:
            signal['take_profit'] = take_profit

        # 计算盈亏比
        if entry_price and stop_loss and take_profit:
            signal['risk_reward_ratio'] = self.calculate_risk_reward(
                entry_price, stop_loss, take_profit
            )

        return signal

    def __str__(self):
        return f"{self.display_name} ({self.strategy_name})"

    def __repr__(self):
        return f"BaseStrategy(name={self.strategy_name}, display_name={self.display_name})"
