"""
Strategies Module - 战法模块

所有战法都应该继承自 BaseStrategy，并实现 analyze_stock 方法。
"""
from .base_strategy import BaseStrategy

__all__ = ['BaseStrategy']
