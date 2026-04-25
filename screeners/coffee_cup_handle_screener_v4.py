#!/usr/bin/env python3
"""
V4 咖啡杯柄筛选器

关键更新（2026-04-14）:
1. 快速下跌和快速上涨时间固定为12天（不再是嵌套循环）
2. 使用成交额（amount）代替成交量（volume）进行比较
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from openpyxl import Workbook

# Get workspace root and add to path
if 'WORKSPACE_ROOT' in __import__('os').environ:
    workspace_root = Path(__import__('os').environ['WORKSPACE_ROOT'])
else:
    workspace_root = Path(__file__).parent.parent

import sys
sys.path.insert(0, str(workspace_root))
sys.path.insert(0, str(workspace_root / 'scripts'))
sys.path.insert(0, str(workspace_root / 'backend'))
sys.path.insert(0, str(workspace_root / 'screeners'))

from config import DATA_DIR, DB_PATH
from base_screener import BaseScreener

logger = logging.getLogger(__name__)


# ========== 参数类 ==========

@dataclass
class CoffeeCupHandleParamsV4:
    """V4版本咖啡杯柄形态参数"""

    # 杯沿相关
    RIM_INTERVAL_MIN = 45      # 杯沿间隔最小天数
    RIM_INTERVAL_MAX = 250     # 杯沿间隔最大天数
    RIM_PRICE_MATCH_PCT = 0.05   # 杯沿价格匹配度 ±5%
    RIGHT_RIM_SEARCH_DAYS = 13  # 右侧杯沿搜索天数
    HISTORY_BUFFER_DAYS = 50    # 历史数据缓冲天数

    # 杯体相关
    CUP_DEPTH_MIN = 0.05      # 杯深最小 5%
    CUP_DEPTH_MAX = 0.70      # 杯深最大 70%

    # 杯体阶段长度
    RAPID_DECLINE_DAYS = 12     # 快速下跌天数（实际使用）
    RAPID_ASCENT_DAYS = 12      # 快速上涨天数（实际使用）

    # 杯柄相关
    HANDLE_PERIOD_MIN = 1        # 杯柄最小天数（0表示无杯柄，单独放行）
    HANDLE_PERIOD_MAX = 13       # 杯柄最大天数
    HANDLE_MAX_DAYS = 13         # 兼容旧字段（同 HANDLE_PERIOD_MAX）

    # 成交额/成交量相关（运行时使用 amount 字段）
    VOLUME_RATIO_THRESHOLD = 2.0 # 倍数要求
    AMOUNT_RATIO_THRESHOLD = 2.0 # 兼容旧字段（同 VOLUME_RATIO_THRESHOLD）

    # 趋势相关
    MA5_TREND_DAYS = 14          # MA5趋势判断天数
    MA_SHORT = 50
    MA_MEDIUM = 150
    MA_LONG = 200
    MA_TREND_WINDOW = 5           # MA趋势计算窗口（日）
    MA_TREND_MIN_VALID_POINTS = 10  # MA趋势判定最少有效点数
    DECLINE_AMOUNT_MAX_RATIO = 0.5   # 第4轮：快速下跌总成交额上限（相对快速上涨总成交额）
    SAFETY_LEVEL_DEPTH_RATIO = 0.5   # 第5轮：安全水位=杯底 + 杯深*该比例
    RECENT_LOW_LOOKBACK_DAYS = 18    # 第5轮：最近N天最低价检查窗口


@dataclass
class ScreeningStats:
    """筛选统计"""
    total_stocks: int = 0
    round1_passed: int = 0
    round1_failed: int = 0
    round2_passed: int = 0
    round2_failed: int = 0
    round3_passed: int = 0
    round3_failed: int = 0
    round4_passed: int = 0
    round4_failed: int = 0
    round5_passed: int = 0
    round5_failed: int = 0
    final_passed: int = 0


# ========== V4筛选器主类 ==========

class CoffeeCupHandleScreenerV4(BaseScreener):
    """咖啡杯柄形态筛选器 V4"""

    screener_name = "coffee_cup_handle_screener_v4"

    def __init__(
        self,
        screener_name: Optional[str] = None,
        db_path: Optional[str] = None,
        enable_news: bool = False,
        enable_llm: bool = False,
        enable_progress: bool = False,
        rim_interval_min: Optional[int] = None,
        rim_interval_max: Optional[int] = None,
        rim_price_match_pct: Optional[float] = None,
        right_rim_search_days: Optional[int] = None,
        history_buffer_days: Optional[int] = None,
        cup_depth_min: Optional[float] = None,
        cup_depth_max: Optional[float] = None,
        rapid_decline_days: Optional[int] = None,
        rapid_ascent_days: Optional[int] = None,
        handle_period_min: Optional[int] = None,
        handle_period_max: Optional[int] = None,
        handle_max_days: Optional[int] = None,
        volume_ratio_threshold: Optional[float] = None,
        amount_ratio_threshold: Optional[float] = None,
        ma5_trend_days: Optional[int] = None,
        ma_short: Optional[int] = None,
        ma_medium: Optional[int] = None,
        ma_long: Optional[int] = None,
        ma_trend_window: Optional[int] = None,
        ma_trend_min_valid_points: Optional[int] = None,
        decline_amount_max_ratio: Optional[float] = None,
        safety_level_depth_ratio: Optional[float] = None,
        recent_low_lookback_days: Optional[int] = None,
        **kwargs,
    ) -> None:
        """初始化筛选器"""
        super().__init__(
            screener_name=screener_name,
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress,
            **kwargs
        )
        # 设置参数 - 使用传入的配置值或默认值
        params = CoffeeCupHandleParamsV4()
        if rim_interval_min is not None:
            params.RIM_INTERVAL_MIN = rim_interval_min
        if rim_interval_max is not None:
            params.RIM_INTERVAL_MAX = rim_interval_max
        if rim_price_match_pct is not None:
            params.RIM_PRICE_MATCH_PCT = rim_price_match_pct
        if right_rim_search_days is not None:
            params.RIGHT_RIM_SEARCH_DAYS = right_rim_search_days
        if history_buffer_days is not None:
            params.HISTORY_BUFFER_DAYS = history_buffer_days
        if cup_depth_min is not None:
            params.CUP_DEPTH_MIN = cup_depth_min
        if cup_depth_max is not None:
            params.CUP_DEPTH_MAX = cup_depth_max
        if rapid_decline_days is not None:
            params.RAPID_DECLINE_DAYS = rapid_decline_days
        if rapid_ascent_days is not None:
            params.RAPID_ASCENT_DAYS = rapid_ascent_days
        if handle_period_min is not None:
            params.HANDLE_PERIOD_MIN = handle_period_min
        if handle_period_max is not None:
            params.HANDLE_PERIOD_MAX = handle_period_max
        if handle_max_days is not None:
            params.HANDLE_PERIOD_MAX = handle_max_days
        if volume_ratio_threshold is not None:
            params.VOLUME_RATIO_THRESHOLD = volume_ratio_threshold
        if amount_ratio_threshold is not None:
            params.VOLUME_RATIO_THRESHOLD = amount_ratio_threshold
        if ma5_trend_days is not None:
            params.MA5_TREND_DAYS = ma5_trend_days
        if ma_short is not None:
            params.MA_SHORT = ma_short
        if ma_medium is not None:
            params.MA_MEDIUM = ma_medium
        if ma_long is not None:
            params.MA_LONG = ma_long
        if ma_trend_window is not None:
            params.MA_TREND_WINDOW = ma_trend_window
        if ma_trend_min_valid_points is not None:
            params.MA_TREND_MIN_VALID_POINTS = ma_trend_min_valid_points
        if decline_amount_max_ratio is not None:
            params.DECLINE_AMOUNT_MAX_RATIO = decline_amount_max_ratio
        if safety_level_depth_ratio is not None:
            params.SAFETY_LEVEL_DEPTH_RATIO = safety_level_depth_ratio
        if recent_low_lookback_days is not None:
            params.RECENT_LOW_LOOKBACK_DAYS = recent_low_lookback_days

        # 统一别名字段并做边界收敛，确保参数可直接参与运行时判断
        params.HANDLE_PERIOD_MIN = max(0, int(params.HANDLE_PERIOD_MIN))
        params.HANDLE_PERIOD_MAX = max(int(params.HANDLE_PERIOD_MIN), int(params.HANDLE_PERIOD_MAX))
        params.HANDLE_MAX_DAYS = params.HANDLE_PERIOD_MAX

        params.RAPID_DECLINE_DAYS = max(1, int(params.RAPID_DECLINE_DAYS))
        params.RAPID_ASCENT_DAYS = max(1, int(params.RAPID_ASCENT_DAYS))
        params.VOLUME_RATIO_THRESHOLD = float(params.VOLUME_RATIO_THRESHOLD)
        params.AMOUNT_RATIO_THRESHOLD = params.VOLUME_RATIO_THRESHOLD
        params.RIGHT_RIM_SEARCH_DAYS = max(1, int(params.RIGHT_RIM_SEARCH_DAYS))
        params.HISTORY_BUFFER_DAYS = max(0, int(params.HISTORY_BUFFER_DAYS))
        params.MA_TREND_WINDOW = max(1, int(params.MA_TREND_WINDOW))
        params.MA_TREND_MIN_VALID_POINTS = max(1, int(params.MA_TREND_MIN_VALID_POINTS))
        params.DECLINE_AMOUNT_MAX_RATIO = max(0.0, float(params.DECLINE_AMOUNT_MAX_RATIO))
        params.SAFETY_LEVEL_DEPTH_RATIO = max(0.0, float(params.SAFETY_LEVEL_DEPTH_RATIO))
        params.RECENT_LOW_LOOKBACK_DAYS = max(1, int(params.RECENT_LOW_LOOKBACK_DAYS))

        self.params = params
        # 初始化统计
        self.stats = ScreeningStats()
        self._last_check_fail_reason: Optional[str] = None
        logger.info("V4咖啡杯柄筛选器初始化完成")

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回参数配置schema"""
        return {
            'RIM_INTERVAL_MIN': {
                'type': 'int',
                'default': 45,
                'min': 30,
                'max': 100,
                'display_name': '杯沿间隔最小天数',
                'description': '左右杯沿之间最小间隔天数',
                'group': '杯沿参数'
            },
            'RIM_INTERVAL_MAX': {
                'type': 'int',
                'default': 250,
                'min': 100,
                'max': 365,
                'display_name': '杯沿间隔最大天数',
                'description': '左右杯沿之间最大间隔天数',
                'group': '杯沿参数'
            },
            'RIM_PRICE_MATCH_PCT': {
                'type': 'float',
                'default': 0.05,
                'min': 0.01,
                'max': 0.10,
                'step': 0.01,
                'display_name': '杯沿价格匹配度',
                'description': '左右杯沿价格匹配的误差范围（百分比）',
                'group': '杯沿参数'
            },
            'RIGHT_RIM_SEARCH_DAYS': {
                'type': 'int',
                'default': 13,
                'min': 1,
                'max': 60,
                'display_name': '右杯沿搜索天数',
                'description': '右杯沿向左搜索局部高点时使用的窗口长度',
                'group': '杯沿参数'
            },
            'HISTORY_BUFFER_DAYS': {
                'type': 'int',
                'default': 50,
                'min': 0,
                'max': 300,
                'display_name': '历史缓冲天数',
                'description': '计算所需历史数据时额外增加的缓冲天数',
                'group': '基础参数'
            },
            'CUP_DEPTH_MIN': {
                'type': 'float',
                'default': 0.05,
                'min': 0.03,
                'max': 0.15,
                'step': 0.01,
                'display_name': '杯深最小比例',
                'description': '杯深占杯沿价格的最小比例',
                'group': '杯体参数'
            },
            'CUP_DEPTH_MAX': {
                'type': 'float',
                'default': 0.70,
                'min': 0.50,
                'max': 0.80,
                'step': 0.05,
                'display_name': '杯深最大比例',
                'description': '杯深占杯沿价格的最大比例',
                'group': '杯体参数'
            },
            'RAPID_DECLINE_DAYS': {
                'type': 'int',
                'default': 12,
                'min': 5,
                'max': 60,
                'display_name': '快速下跌天数',
                'description': '快速下调阶段持续天数',
                'group': '杯体参数'
            },
            'RAPID_ASCENT_DAYS': {
                'type': 'int',
                'default': 12,
                'min': 5,
                'max': 60,
                'display_name': '快速上涨天数',
                'description': '快速上涨阶段持续天数',
                'group': '杯体参数'
            },
            'HANDLE_PERIOD_MIN': {
                'type': 'int',
                'default': 1,
                'min': 0,
                'max': 30,
                'display_name': '杯柄最小天数',
                'description': '杯柄形成最少天数（0表示允许无杯柄）',
                'group': '杯柄参数'
            },
            'HANDLE_PERIOD_MAX': {
                'type': 'int',
                'default': 13,
                'min': 1,
                'max': 60,
                'display_name': '杯柄最大天数',
                'description': '杯柄形成最多天数',
                'group': '杯柄参数'
            },
            'HANDLE_MAX_DAYS': {
                'type': 'int',
                'default': 13,
                'min': 5,
                'max': 60,
                'display_name': '杯柄最大天数',
                'description': '杯柄持续最大天数',
                'group': '杯柄参数'
            },
            'VOLUME_RATIO_THRESHOLD': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 10.0,
                'step': 0.1,
                'display_name': '成交额倍数要求',
                'description': '右杯沿前成交额与左杯沿后成交额的最小倍数',
                'group': '成交量参数'
            },
            'AMOUNT_RATIO_THRESHOLD': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 10.0,
                'step': 0.1,
                'display_name': '成交额倍数要求（兼容）',
                'description': '兼容旧字段，等价于 VOLUME_RATIO_THRESHOLD',
                'group': '成交量参数'
            },
            'MA5_TREND_DAYS': {
                'type': 'int',
                'default': 14,
                'min': 5,
                'max': 60,
                'display_name': 'MA5趋势判断天数',
                'description': '用于判断左杯沿前MA5趋势的窗口长度',
                'group': '趋势参数'
            },
            'MA_TREND_WINDOW': {
                'type': 'int',
                'default': 5,
                'min': 1,
                'max': 60,
                'display_name': '趋势均线窗口',
                'description': '趋势判定时滚动均线的窗口长度',
                'group': '趋势参数'
            },
            'MA_TREND_MIN_VALID_POINTS': {
                'type': 'int',
                'default': 10,
                'min': 1,
                'max': 200,
                'display_name': '趋势最少有效点',
                'description': '趋势判定时滚动均线的最少有效点数',
                'group': '趋势参数'
            },
            'MA_SHORT': {
                'type': 'int',
                'default': 50,
                'min': 5,
                'max': 120,
                'display_name': '短期均线周期',
                'description': '第5轮均线过滤短周期',
                'group': '趋势参数'
            },
            'MA_MEDIUM': {
                'type': 'int',
                'default': 150,
                'min': 10,
                'max': 250,
                'display_name': '中期均线周期',
                'description': '第5轮均线过滤中周期',
                'group': '趋势参数'
            },
            'MA_LONG': {
                'type': 'int',
                'default': 200,
                'min': 20,
                'max': 400,
                'display_name': '长期均线周期',
                'description': '第5轮均线过滤长周期',
                'group': '趋势参数'
            },
            'DECLINE_AMOUNT_MAX_RATIO': {
                'type': 'float',
                'default': 0.5,
                'min': 0.0,
                'max': 2.0,
                'step': 0.01,
                'display_name': '快速下跌成交额上限系数',
                'description': '第4轮中快速下跌总成交额必须小于快速上涨总成交额乘以该系数',
                'group': '第4轮-成交额'
            },
            'SAFETY_LEVEL_DEPTH_RATIO': {
                'type': 'float',
                'default': 0.5,
                'min': 0.0,
                'max': 1.0,
                'step': 0.01,
                'display_name': '安全水位杯深比例',
                'description': '第5轮安全水位计算比例：杯底 + 杯深*该比例',
                'group': '第5轮-价格质量'
            },
            'RECENT_LOW_LOOKBACK_DAYS': {
                'type': 'int',
                'default': 18,
                'min': 1,
                'max': 120,
                'display_name': '最近低点检查天数',
                'description': '第5轮检查“当前日是否为最近N天最低收盘价”时的窗口长度',
                'group': '第5轮-价格质量'
            },
        }

    def calculate_required_days(self) -> int:
        """计算所需历史数据天数"""
        return (
            self.params.RIM_INTERVAL_MAX +
            self.params.RAPID_DECLINE_DAYS +
            self.params.RAPID_ASCENT_DAYS +
            self.params.RIGHT_RIM_SEARCH_DAYS +
            self.params.HISTORY_BUFFER_DAYS
        )

    def check_ma5_trend(
        self,
        df: pd.DataFrame,
        left_rim_idx: int
    ) -> Tuple[bool, str]:
        """
        检查MA5趋势

        参数：
            df: 价格数据DataFrame
            left_rim_idx: 左杯沿索引

        返回：
            (是否通过, 原因/信息)
        """
        trend_days = max(int(self.params.MA_TREND_WINDOW), int(self.params.MA5_TREND_DAYS))
        trend_start = max(0, left_rim_idx - trend_days)
        trend_period = df.iloc[trend_start:left_rim_idx]

        if len(trend_period) < trend_days:
            return False, f"数据不足{trend_days}天"

        # 计算MA5
        ma5_values = trend_period['close'].rolling(self.params.MA_TREND_WINDOW).mean().dropna()
        if len(ma5_values) < self.params.MA_TREND_MIN_VALID_POINTS:
            return False, "MA5数据不足"

        # 比较前后两半的均值
        half = len(ma5_values) // 2
        first_half_mean = ma5_values.iloc[:half].mean()
        second_half_mean = ma5_values.iloc[half:].mean()

        if second_half_mean > first_half_mean:
            improvement = ((second_half_mean - first_half_mean) / first_half_mean) * 100
            return True, f"MA5上升趋势（后半段均值{second_half_mean:.2f} > 前半段{first_half_mean:.2f}，提升{improvement:.2f}%）"
        else:
            decline = ((first_half_mean - second_half_mean) / first_half_mean) * 100
            return False, f"MA5无上升趋势（后半段均值{second_half_mean:.2f} <= 前半段{first_half_mean:.2f}，下降{decline:.2f}%）"

    # ========== 第1轮：找右侧杯沿 ==========

    def _set_check_fail_reason(self, reason: str) -> None:
        self._last_check_fail_reason = reason

    def _consume_check_fail_reason(self) -> Optional[str]:
        reason = self._last_check_fail_reason
        self._last_check_fail_reason = None
        return reason

    def _round1_find_right_rim(
        self,
        df: pd.DataFrame
    ) -> Optional[Dict]:
        """
        第1轮：找右侧杯沿

        参数：
            df: 价格数据DataFrame

        返回：
            包含 right_rim_idx, right_rim_price, handle_length, latest_idx 的字典
            如果失败返回 None
        """
        latest_idx = len(df) - 1

        # 计算搜索窗口（最近13天）
        right_rim_search_window = self.params.RIGHT_RIM_SEARCH_DAYS
        right_rim_search_start = max(0, latest_idx - right_rim_search_window)

        # 提取搜索期间数据
        right_rim_period = df.iloc[right_rim_search_start:latest_idx + 1]

        # 找最高价作为右杯沿
        right_rim_price_idx = right_rim_period['high'].idxmax()
        right_rim_price = right_rim_period.loc[right_rim_price_idx, 'high']

        # 计算杯柄长度
        handle_length = latest_idx - right_rim_price_idx

        # 验证杯柄长度
        if handle_length > self.params.HANDLE_PERIOD_MAX:
            logger.debug(f"杯柄太长：{handle_length}天 > {self.params.HANDLE_PERIOD_MAX}天")
            self._set_check_fail_reason(
                f"第1轮：杯柄过长（{handle_length}天 > {self.params.HANDLE_PERIOD_MAX}天）"
            )
            return None
        if handle_length > 0 and handle_length < self.params.HANDLE_PERIOD_MIN:
            logger.debug(f"杯柄太短：{handle_length}天 < {self.params.HANDLE_PERIOD_MIN}天")
            self._set_check_fail_reason(
                f"第1轮：杯柄过短（{handle_length}天 < {self.params.HANDLE_PERIOD_MIN}天）"
            )
            return None

        return {
            'right_rim_idx': right_rim_price_idx,
            'right_rim_price': float(right_rim_price),
            'handle_length': handle_length,
            'latest_idx': latest_idx
        }

    # ========== 第2轮：找左侧杯沿 ==========

    def _round2_find_left_rim(
        self,
        df: pd.DataFrame,
        round1_result: Dict
    ) -> Optional[Dict]:
        """
        第2轮：找左侧杯沿

        参数：
            df: 价格数据DataFrame
            round1_result: 第1轮结果

        返回：
            添加 left_rim_idx, left_rim_price, ma5_passed, ma5_reason 的结果
            如果失败返回 None
        """
        right_rim_idx = round1_result['right_rim_idx']
        right_rim_price = round1_result['right_rim_price']

        # 检查：从右杯沿回溯最小间隔窗口内是否有价格达到或超过右杯沿
        check_start_idx = max(0, right_rim_idx - self.params.RIM_INTERVAL_MIN)
        check_period = df.iloc[check_start_idx:right_rim_idx]
        if not check_period.empty and check_period['high'].max() >= right_rim_price:
            logger.debug(f"右杯沿前{self.params.RIM_INTERVAL_MIN}天内有价格达到或超过右杯沿{right_rim_price:.2f}")
            self._set_check_fail_reason(
                f"第2轮：右杯沿前{self.params.RIM_INTERVAL_MIN}天内出现更高/相等高点，右沿不成立"
            )
            return None

        # 计算搜索范围：从T-RIM_INTERVAL_MIN往回追溯到T-RIM_INTERVAL_MAX
        search_start = right_rim_idx - self.params.RIM_INTERVAL_MIN
        search_end = right_rim_idx - self.params.RIM_INTERVAL_MAX

        # 边界检查
        search_start = max(0, search_start)
        search_end = max(0, search_end)

        if search_start <= search_end:
            logger.debug(f"搜索范围无效：{search_start} <= {search_end}")
            self._set_check_fail_reason(
                f"第2轮：左杯沿搜索区间无效（start={search_start}, end={search_end}）"
            )
            return None

        # 往回迭代找左杯沿
        price_match_failed = 0
        local_peak_failed = 0
        rim_interval_failed = 0
        ma5_failed = 0
        last_ma5_reason: Optional[str] = None
        for left_rim_idx in range(search_start, search_end - 1, -1):
            # 获取价格
            left_rim_price = df.iloc[left_rim_idx]['high']

            # 价格匹配检查
            price_diff_pct = abs(right_rim_price - left_rim_price) / right_rim_price
            if price_diff_pct > self.params.RIM_PRICE_MATCH_PCT:
                price_match_failed += 1
                continue

            # 局部高点检查
            local_window_start = max(0, left_rim_idx - 5)
            local_window_end = min(len(df) - 1, left_rim_idx + 5)
            local_period = df.iloc[local_window_start:local_window_end + 1]
            local_high = local_period['high'].max()

            if left_rim_price < local_high - 0.001:
                local_peak_failed += 1
                continue

            # 杯沿间隔检查
            rim_interval = right_rim_idx - left_rim_idx
            if rim_interval < self.params.RIM_INTERVAL_MIN or rim_interval > self.params.RIM_INTERVAL_MAX:
                logger.debug(f"杯沿间隔{rim_interval}天不在范围[{self.params.RIM_INTERVAL_MIN}, {self.params.RIM_INTERVAL_MAX}]")
                rim_interval_failed += 1
                continue

            # MA5趋势检查
            ma5_passed, ma5_reason = self.check_ma5_trend(df, left_rim_idx)
            if not ma5_passed:
                logger.debug(f"MA5趋势检查失败：{ma5_reason}")
                ma5_failed += 1
                last_ma5_reason = ma5_reason
                continue

            # 找到符合条件的左杯沿
            logger.info(f"找到左杯沿：索引{left_rim_idx}，价格{left_rim_price:.2f}，间隔{rim_interval}天，{ma5_reason}")

            return {
                **round1_result,
                'left_rim_idx': left_rim_idx,
                'left_rim_price': float(left_rim_price),
                'rim_interval': rim_interval,
                'ma5_passed': ma5_passed,
                'ma5_reason': ma5_reason
            }

        logger.debug("未找到符合条件的左杯沿")
        if ma5_failed > 0 and last_ma5_reason:
            self._set_check_fail_reason(f"第2轮：MA5趋势不满足（{last_ma5_reason}）")
        elif rim_interval_failed > 0:
            self._set_check_fail_reason(
                f"第2轮：杯沿间隔不满足范围[{self.params.RIM_INTERVAL_MIN}, {self.params.RIM_INTERVAL_MAX}]"
            )
        elif local_peak_failed > 0:
            self._set_check_fail_reason("第2轮：候选左杯沿不是局部高点")
        elif price_match_failed > 0:
            self._set_check_fail_reason(
                f"第2轮：左/右杯沿价格偏差超过{self.params.RIM_PRICE_MATCH_PCT * 100:.1f}%"
            )
        else:
            self._set_check_fail_reason("第2轮：未找到满足条件的左杯沿")
        return None

    # ========== 第3轮：验证杯深 ==========

    def _round3_validate_cup_depth(
        self,
        df: pd.DataFrame,
        round2_result: Dict
    ) -> Optional[Dict]:
        """
        第3轮：验证杯深

        参数：
            df: 价格数据DataFrame
            round2_result: 第2轮结果

        返回：
            添加 cup_bottom_price, cup_depth 的结果
            如果失败返回 None
        """
        left_rim_idx = round2_result['left_rim_idx']
        left_rim_price = round2_result['left_rim_price']
        right_rim_idx = round2_result['right_rim_idx']

        # 提取杯体数据
        cup_body_period = df.iloc[left_rim_idx:right_rim_idx + 1]

        # 计算杯底
        cup_bottom_price = cup_body_period['low'].min()

        # 计算杯深
        cup_depth = (left_rim_price - cup_bottom_price) / left_rim_price

        # 验证杯深范围
        if cup_depth < self.params.CUP_DEPTH_MIN:
            logger.debug(f"杯深太浅：{cup_depth*100:.1f}% < {self.params.CUP_DEPTH_MIN*100:.1f}%")
            self._set_check_fail_reason(
                f"第3轮：杯深过浅（{cup_depth * 100:.1f}% < {self.params.CUP_DEPTH_MIN * 100:.1f}%）"
            )
            return None

        if cup_depth > self.params.CUP_DEPTH_MAX:
            logger.debug(f"杯深太深：{cup_depth*100:.1f}% > {self.params.CUP_DEPTH_MAX*100:.1f}%")
            self._set_check_fail_reason(
                f"第3轮：杯深过深（{cup_depth * 100:.1f}% > {self.params.CUP_DEPTH_MAX * 100:.1f}%）"
            )
            return None

        logger.info(f"杯深验证通过：{cup_depth*100:.1f}%（范围{self.params.CUP_DEPTH_MIN*100:.1f}%-{self.params.CUP_DEPTH_MAX*100:.1f}%）")

        return {
            **round2_result,
            'cup_bottom_price': float(cup_bottom_price),
            'cup_depth': float(cup_depth)
        }

    # ========== 第4轮：验证形态（杯体、杯柄、成交额） ==========

    def _round4_validate_pattern(
        self,
        df: pd.DataFrame,
        round3_result: Dict
    ) -> Optional[Dict]:
        """
        第4轮：验证杯体结构与阶段成交额

        重要更新（2026-04-24）:
        1. 快速下跌/快速上涨使用固定窗口
        2. 移除震荡期相关检查
        3. 仅比较快速下跌期与快速上涨期总成交额

        参数：
            df: 价格数据DataFrame
            round3_result: 第3轮结果

        返回：
            添加 handle_low, handle_drop, amount_ratio 的结果
            如果失败返回 None
        """
        left_rim_idx = round3_result['left_rim_idx']
        right_rim_idx = round3_result['right_rim_idx']
        right_rim_price = round3_result['right_rim_price']
        latest_idx = round3_result['latest_idx']
        handle_length = round3_result['handle_length']

        # ========== 阶段窗口 ==========

        # 快速下跌阶段
        rapid_decline_days = self.params.RAPID_DECLINE_DAYS
        decline_end_idx = left_rim_idx + rapid_decline_days

        # 快速上涨阶段
        rapid_ascent_days = self.params.RAPID_ASCENT_DAYS
        ascent_start_idx = right_rim_idx - rapid_ascent_days

        # 验证索引有效
        if decline_end_idx >= right_rim_idx:
            logger.debug(f"快速下跌结束索引{decline_end_idx} >= 右杯沿索引{right_rim_idx}")
            self._set_check_fail_reason(
                f"第4轮：阶段索引无效（下跌结束{decline_end_idx} >= 右沿{right_rim_idx}）"
            )
            return None

        if ascent_start_idx <= decline_end_idx:
            logger.debug(f"快速上涨开始索引{ascent_start_idx} <= 快速下跌结束索引{decline_end_idx}")
            self._set_check_fail_reason(
                f"第4轮：阶段重叠（上涨开始{ascent_start_idx} <= 下跌结束{decline_end_idx}）"
            )
            return None

        if ascent_start_idx < left_rim_idx:
            logger.debug(f"快速上涨开始索引{ascent_start_idx} < 左杯沿索引{left_rim_idx}")
            self._set_check_fail_reason(
                f"第4轮：上涨起点越界（{ascent_start_idx} < 左沿{left_rim_idx}）"
            )
            return None

        # 为保持输出字段兼容，杯柄仍返回统计信息（不作为第4轮过滤条件）
        if handle_length > 0:
            handle_period = df.iloc[right_rim_idx + 1:latest_idx + 1]['close']
            handle_low = float(handle_period.min()) if not handle_period.empty else float(right_rim_price)
            if right_rim_price <= 0:
                self._set_check_fail_reason("第4轮：右杯沿价格无效，无法计算杯柄回撤")
                return None
            handle_drop = max(0.0, (right_rim_price - handle_low) / right_rim_price)
        else:
            handle_low = right_rim_price
            handle_drop = 0.0

        # ========== 验证成交额（仅比较快速下跌期与快速上涨期总额） ==========

        # 定义快速下跌期和快速上涨期
        decline_period = df.iloc[left_rim_idx + 1:decline_end_idx + 1]
        ascent_period = df.iloc[ascent_start_idx:right_rim_idx + 1]

        if decline_period.empty:
            self._set_check_fail_reason("第4轮：快速下跌期数据为空")
            return None

        if ascent_period.empty:
            self._set_check_fail_reason("第4轮：快速上涨期数据为空")
            return None

        if decline_period['amount'].isna().any():
            self._set_check_fail_reason("第4轮：快速下跌期成交额存在空值")
            return None

        if ascent_period['amount'].isna().any():
            self._set_check_fail_reason("第4轮：快速上涨期成交额存在空值")
            return None

        # 计算快速下跌/快速上涨成交额总额
        decline_total_amt = decline_period['amount'].sum()
        ascent_total_amt = ascent_period['amount'].sum()

        if decline_total_amt <= 0:
            logger.debug(f"快速下跌阶段成交额无效：{decline_total_amt:.2f}")
            self._set_check_fail_reason(
                f"第4轮：快速下跌阶段成交额无效（{decline_total_amt:.2f}）"
            )
            return None

        amount_ratio = ascent_total_amt / decline_total_amt
        decline_amount_limit = ascent_total_amt * self.params.DECLINE_AMOUNT_MAX_RATIO
        if decline_total_amt >= decline_amount_limit:
            logger.debug(
                f"快速下跌总成交额不满足约束：{decline_total_amt:.2f} >= {decline_amount_limit:.2f}"
            )
            self._set_check_fail_reason(
                f"第4轮：快速下跌总成交额不满足（{decline_total_amt:.2f} >= {decline_amount_limit:.2f}）"
            )
            return None

        logger.info(f"成交额倍数验证通过：{amount_ratio:.2f}x")

        return {
            **round3_result,
            'handle_low': float(handle_low),
            'handle_drop': float(handle_drop),
            'amount_ratio': float(amount_ratio)
        }

    # ========== 第5轮：验证当前价格 ==========

    def _round5_validate_current_price(
        self,
        df: pd.DataFrame,
        round4_result: Dict
    ) -> Optional[Dict]:
        """
        第5轮：验证当前价格

        参数：
            df: 价格数据DataFrame
            round4_result: 第4轮结果

        返回：
            添加 latest_price 的结果
            如果失败返回 None
        """
        latest_idx = round4_result['latest_idx']
        right_rim_idx = round4_result['right_rim_idx']
        left_rim_price = round4_result['left_rim_price']
        cup_bottom_price = round4_result['cup_bottom_price']
        handle_length = round4_result['handle_length']

        # 获取最新价格
        latest_price = df.iloc[latest_idx]['close']

        # 特殊处理：右杯沿即基准日时直接通过
        if handle_length == 0:
            logger.debug("右杯沿即基准日，跳过中间区间价格检查")
            return {
                **round4_result,
                'latest_price': float(latest_price)
            }

        # 仅检查右杯沿到基准日中间区间：任一天收盘价不得跌破安全水位
        # cup_depth 为比例，安全水位需按价格维度计算
        safety_level = cup_bottom_price + (left_rim_price - cup_bottom_price) * self.params.SAFETY_LEVEL_DEPTH_RATIO
        middle_period = df.iloc[right_rim_idx + 1:latest_idx]['close']
        if middle_period.isna().any():
            self._set_check_fail_reason("第5轮：中间区间收盘价存在空值")
            return None
        if not middle_period.empty:
            middle_min_close = float(middle_period.min())
            if middle_min_close < safety_level:
                logger.debug(f"中间区间最低收盘价{middle_min_close:.2f} < 安全水位{safety_level:.2f}")
                self._set_check_fail_reason(
                    f"第5轮：中间区间收盘价跌破安全水位（{middle_min_close:.2f} < {safety_level:.2f}）"
                )
                return None

        # 杯柄质量补充：当前日若为最近18天最低收盘且低于安全水位，则淘汰
        latest_close = float(latest_price)
        recent_lookback_days = self.params.RECENT_LOW_LOOKBACK_DAYS
        recent_start_idx = max(0, latest_idx - (recent_lookback_days - 1))
        recent_18_close = df.iloc[recent_start_idx:latest_idx + 1]['close']
        if recent_18_close.isna().any():
            self._set_check_fail_reason("第5轮：最近18天收盘价存在空值")
            return None
        recent_18_low = float(recent_18_close.min())
        if latest_close <= recent_18_low and latest_close < safety_level:
            self._set_check_fail_reason(
                f"第5轮：当前日创{recent_lookback_days}天新低且跌破安全水位（{latest_close:.2f} <= {recent_18_low:.2f} 且 < {safety_level:.2f}）"
            )
            return None
        logger.info(f"中间区间价格验证通过：最低收盘价不低于安全水位{safety_level:.2f}")

        return {
            **round4_result,
            'latest_price': float(latest_price)
        }

    def _print_stats_report(self):
        """打印统计报告"""
        def _pct(numerator: int, denominator: int) -> float:
            return (numerator / denominator * 100.0) if denominator else 0.0

        logger.info("=" * 70)
        logger.info("筛选统计报告")
        logger.info("=" * 70)

        total = self.stats.total_stocks

        logger.info(f"总股票数: {total}")
        logger.info("")

        # 第1轮
        logger.info("第1轮：找右侧杯沿")
        logger.info(f"  通过: {self.stats.round1_passed} ({_pct(self.stats.round1_passed, total):.1f}%)")
        logger.info(f"  淘汰: {self.stats.round1_failed} ({_pct(self.stats.round1_failed, total):.1f}%)")
        logger.info("")

        # 第2轮
        logger.info("第2轮：找左侧杯沿")
        logger.info(f"  通过: {self.stats.round2_passed} ({_pct(self.stats.round2_passed, self.stats.round1_passed):.1f}% of R1)")
        logger.info(f"  淘汰: {self.stats.round2_failed} ({_pct(self.stats.round2_failed, self.stats.round1_passed):.1f}% of R1)")
        logger.info("")

        # 第3轮
        logger.info("第3轮：验证杯深")
        logger.info(f"  通过: {self.stats.round3_passed} ({_pct(self.stats.round3_passed, self.stats.round2_passed):.1f}% of R2)")
        logger.info(f"  淘汰: {self.stats.round3_failed} ({_pct(self.stats.round3_failed, self.stats.round2_passed):.1f}% of R2)")
        logger.info("")

        # 第4轮
        logger.info("第4轮：验证形态（杯体、杯柄、成交额）")
        logger.info(f"  通过: {self.stats.round4_passed} ({_pct(self.stats.round4_passed, self.stats.round3_passed):.1f}% of R3)")
        logger.info(f"  淘汰: {self.stats.round4_failed} ({_pct(self.stats.round4_failed, self.stats.round3_passed):.1f}% of R3)")
        logger.info("")

        # 第5轮
        logger.info("第5轮：验证当前价格")
        logger.info(f"  通过: {self.stats.round5_passed} ({_pct(self.stats.round5_passed, self.stats.round4_passed):.1f}% of R4)")
        logger.info(f"  淘汰: {self.stats.round5_failed} ({_pct(self.stats.round5_failed, self.stats.round4_passed):.1f}% of R4)")
        logger.info("")

        # 最终结果
        logger.info(f"最终通过: {self.stats.final_passed} ({_pct(self.stats.final_passed, total):.1f}% of total)")
        logger.info("=" * 70)

    # ========== 组合5轮方法 ==========

    def find_cup_pattern(
        self,
        df: pd.DataFrame,
        stock_code: str,
        stock_name: str
    ) -> Optional[Dict]:
        """
        组合5轮方法找形态

        参数：
            df: 价格数据DataFrame
            stock_code: 股票代码
            stock_name: 股票名称

        返回：
            包含所有筛选结果的字典
            如果任一轮失败返回 None
        """
        self.stats.total_stocks += 1

        # 第1轮：找右侧杯沿
        round1_result = self._round1_find_right_rim(df)
        if round1_result is None:
            self.stats.round1_failed += 1
            logger.debug(f"{stock_code}: 第1轮失败 - 未找到有效的右侧杯沿")
            return None
        self.stats.round1_passed += 1

        # 第2轮：找左侧杯沿
        round2_result = self._round2_find_left_rim(df, round1_result)
        if round2_result is None:
            self.stats.round2_failed += 1
            logger.debug(f"{stock_code}: 第2轮失败 - 未找到有效的左侧杯沿")
            return None
        self.stats.round2_passed += 1

        # 第3轮：验证杯深
        round3_result = self._round3_validate_cup_depth(df, round2_result)
        if round3_result is None:
            self.stats.round3_failed += 1
            logger.debug(f"{stock_code}: 第3轮失败 - 杯深不符合要求")
            return None
        self.stats.round3_passed += 1

        # 第4轮：验证形态（杯体、杯柄、成交额）
        round4_result = self._round4_validate_pattern(df, round3_result)
        if round4_result is None:
            self.stats.round4_failed += 1
            logger.debug(f"{stock_code}: 第4轮失败 - 形态验证不符合要求")
            return None
        self.stats.round4_passed += 1

        # 第5轮：验证当前价格
        round5_result = self._round5_validate_current_price(df, round4_result)
        if round5_result is None:
            self.stats.round5_failed += 1
            logger.debug(f"{stock_code}: 第5轮失败 - 当前价格不符合要求")
            return None
        self.stats.round5_passed += 1

        # 全部通过
        self.stats.final_passed += 1
        logger.info(f"{stock_code} {stock_name}: 通过所有5轮筛选")
        return {
            **round5_result,
            'stock_code': stock_code,
            'stock_name': stock_name
        }

    # ========== 筛选单只股票 ==========

    def screen_stock(
        self,
        stock_code: str,
        stock_name: str
    ) -> Optional[Dict]:
        """
        筛选单只股票

        参数：
            stock_code: 股票代码
            stock_name: 股票名称

        返回：
            包含筛选结果的字典
            如果不符合条件返回 None
        """
        try:
            # 获取所需天数的历史数据
            required_days = self.calculate_required_days()
            prices = self.get_latest_n_prices(stock_code, required_days)

            # 转换为DataFrame
            df = pd.DataFrame([{
                'trade_date': p.trade_date,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume,
                'amount': p.amount,
                'pct_change': p.pct_change,
                'turnover': p.turnover
            } for p in prices])

            # 重置索引
            df.reset_index(drop=True, inplace=True)

            # 调用形态查找
            result = self.find_cup_pattern(df, stock_code, stock_name)

            if result:
                return result

            return None

        except Exception as e:
            logger.error(f"筛选股票{stock_code}时出错: {e}", exc_info=True)
            return None

    def _diagnose_check_failure(
        self,
        df: pd.DataFrame
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        单票诊断模式：返回最终结果或首个失败原因。

        说明：
            - 仅用于 check_single_stock 的失败可解释性输出；
            - 不修改统计计数，不影响批量筛选逻辑。
        """
        self._last_check_fail_reason = None

        round1_result = self._round1_find_right_rim(df)
        if round1_result is None:
            return None, self._consume_check_fail_reason() or "第1轮失败：未找到有效右侧杯沿"

        round2_result = self._round2_find_left_rim(df, round1_result)
        if round2_result is None:
            return None, self._consume_check_fail_reason() or "第2轮失败：未找到有效左侧杯沿"

        round3_result = self._round3_validate_cup_depth(df, round2_result)
        if round3_result is None:
            return None, self._consume_check_fail_reason() or "第3轮失败：杯深不满足要求"

        round4_result = self._round4_validate_pattern(df, round3_result)
        if round4_result is None:
            return None, self._consume_check_fail_reason() or "第4轮失败：杯体/杯柄/成交额结构校验不满足条件"

        round5_result = self._round5_validate_current_price(df, round4_result)
        if round5_result is None:
            return None, self._consume_check_fail_reason() or "第5轮失败：当前价过滤不满足条件"

        return round5_result, None

    def _collect_diagnostic_hints(
        self,
        df: pd.DataFrame,
        max_candidates: int = 5
    ) -> List[str]:
        """
        影子诊断：在不改变主判定的前提下，评估多个右沿候选的首个失败点。
        """
        if df.empty:
            return []

        latest_idx = len(df) - 1
        search_start = max(0, latest_idx - int(self.params.RIGHT_RIM_SEARCH_DAYS))
        right_rim_window = df.iloc[search_start:latest_idx + 1]
        if right_rim_window.empty:
            return []

        candidate_indices = right_rim_window['high'].sort_values(ascending=False).index.tolist()
        hints: List[str] = []
        seen: set[int] = set()
        evaluated = 0

        for rim_idx in candidate_indices:
            if rim_idx in seen:
                continue
            seen.add(rim_idx)
            evaluated += 1
            if evaluated > max_candidates:
                break

            right_rim_price = float(df.iloc[rim_idx]['high'])
            handle_length = latest_idx - rim_idx
            prefix = f"候选右沿[idx={rim_idx}, 价={right_rim_price:.2f}]"

            if handle_length > self.params.HANDLE_PERIOD_MAX:
                hints.append(
                    f"{prefix} -> 第1轮：杯柄过长（{handle_length}天 > {self.params.HANDLE_PERIOD_MAX}天）"
                )
                continue
            if handle_length > 0 and handle_length < self.params.HANDLE_PERIOD_MIN:
                hints.append(
                    f"{prefix} -> 第1轮：杯柄过短（{handle_length}天 < {self.params.HANDLE_PERIOD_MIN}天）"
                )
                continue

            round1_result = {
                'right_rim_idx': rim_idx,
                'right_rim_price': right_rim_price,
                'handle_length': handle_length,
                'latest_idx': latest_idx,
            }

            self._last_check_fail_reason = None
            round2_result = self._round2_find_left_rim(df, round1_result)
            if round2_result is None:
                hints.append(f"{prefix} -> {self._consume_check_fail_reason() or '第2轮失败'}")
                continue

            self._last_check_fail_reason = None
            round3_result = self._round3_validate_cup_depth(df, round2_result)
            if round3_result is None:
                hints.append(f"{prefix} -> {self._consume_check_fail_reason() or '第3轮失败'}")
                continue

            self._last_check_fail_reason = None
            round4_result = self._round4_validate_pattern(df, round3_result)
            if round4_result is None:
                hints.append(f"{prefix} -> {self._consume_check_fail_reason() or '第4轮失败'}")
                continue

            self._last_check_fail_reason = None
            round5_result = self._round5_validate_current_price(df, round4_result)
            if round5_result is None:
                hints.append(f"{prefix} -> {self._consume_check_fail_reason() or '第5轮失败'}")
                continue

            hints.append(f"{prefix} -> 后续第2~5轮均通过")

        # 去重并保持顺序，避免前端展示重复信息
        unique_hints: List[str] = []
        seen_hint = set()
        for hint in hints:
            if hint in seen_hint:
                continue
            seen_hint.add(hint)
            unique_hints.append(hint)
        return unique_hints

    def check_single_stock(
        self,
        code: str,
        date_str: Optional[str] = None
    ) -> Dict:
        """
        Check single stock (compatibility method for backend API)

        Parameters:
            code: Stock code
            date_str: Date string (optional, not used in V4)

        Returns:
            Dictionary with screening result or error info
        """
        try:
            # Get stock name from database
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stocks WHERE code = ?", (code,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return {
                    'code': code,
                    'error': f'Stock {code} not found in database'
                }

            stock_name = result[0]

            # 构造单票所需K线数据
            required_days = self.calculate_required_days()
            prices = self.get_latest_n_prices(code, required_days)
            df = pd.DataFrame([{
                'trade_date': p.trade_date,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume,
                'amount': p.amount,
                'pct_change': p.pct_change,
                'turnover': p.turnover
            } for p in prices])
            df.reset_index(drop=True, inplace=True)

            # 诊断模式：返回首个失败环节，便于前端展示
            screening_result, fail_reason = self._diagnose_check_failure(df)

            if screening_result is None:
                primary_reason = fail_reason or 'No coffee cup handle pattern found'
                hints = self._collect_diagnostic_hints(df, max_candidates=5)
                hints = [h for h in hints if h != primary_reason]
                return {
                    'code': code,
                    'name': stock_name,
                    'pattern_found': False,
                    'reason': primary_reason,
                    'reasons': [primary_reason],
                    'details': {
                        'diagnostic_hints': hints
                    }
                }

            # Return result in standard format
            return {
                'code': code,
                'name': stock_name,
                'pattern_found': True,
                **screening_result
            }

        except Exception as e:
            logger.error(f"check_single_stock error for {code}: {e}", exc_info=True)
            return {
                'code': code,
                'error': str(e)
            }

    # ========== 运行筛选 ==========

    def run_screening(
        self,
        date_str: Optional[str] = None,
        force_restart: bool = False,
        enable_analysis: bool = False
    ) -> List[Dict]:
        """
        运行筛选

        参数：
            date_str: 筛选日期（可选）
            force_restart: 强制重新开始
            enable_analysis: 启用分析

        返回：
            筛选结果列表
        """
        if date_str:
            self._current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            self._current_date = self.get_latest_data_date()

        if not self._current_date:
            logger.error("无法确定筛选日期")
            return []

        logger.info(f"开始筛选，日期: {self._current_date}")
        logger.info(f"参数: 杯沿间隔{self.params.RIM_INTERVAL_MIN}-{self.params.RIM_INTERVAL_MAX}天, "
                   f"杯深{self.params.CUP_DEPTH_MIN*100:.0f}%-{self.params.CUP_DEPTH_MAX*100:.0f}%, "
                   f"杯柄{self.params.HANDLE_PERIOD_MIN}-{self.params.HANDLE_PERIOD_MAX}天, "
                   f"成交额倍数{self.params.VOLUME_RATIO_THRESHOLD}x, "
                   f"均线{self.params.MA_SHORT}/{self.params.MA_MEDIUM}/{self.params.MA_LONG}")

        # 重置统计
        self.stats = ScreeningStats()

        # 获取所有股票
        stocks = self.get_all_stocks()
        logger.info(f"获取到{len(stocks)}只股票")

        results = []
        for stock in stocks:
            result = self.screen_stock(stock.code, stock.name)
            if result:
                results.append(result)

        logger.info(f"筛选完成，找到{len(results)}只符合条件的股票")

        # 打印统计报告
        self._print_stats_report()

        return results

    # ========== 保存结果 ==========

    def save_results(
        self,
        results: List[Dict],
        column_mapping: Optional[Dict] = None,
        target_date: Optional[str] = None
    ) -> str:
        """
        保存结果到Excel

        参数：
            results: 筛选结果列表
            column_mapping: 列映射（可选）
            target_date: 目标日期（可选）

        返回：
            输出文件路径
        """
        if not results:
            logger.warning("没有结果需要保存")
            return ""

        if target_date is None:
            target_date = self._current_date.strftime("%Y-%m-%d") if self._current_date else "latest"

        # 确定输出目录
        output_dir = Path(DATA_DIR) / 'screeners' / self.screener_name / target_date
        output_dir.mkdir(parents=True, exist_ok=True)

        # 转换为DataFrame
        df = pd.DataFrame(results)

        # 调整列顺序
        columns_order = [
            'stock_code', 'stock_name',
            'left_rim_idx', 'left_rim_price', 'right_rim_idx', 'right_rim_price',
            'rim_interval', 'cup_bottom_price', 'cup_depth',
            'handle_length', 'handle_low', 'handle_drop',
            'amount_ratio', 'latest_price', 'ma5_reason'
        ]

        # 只保留存在的列
        columns_order = [col for col in columns_order if col in df.columns]
        df = df[columns_order]

        # 保存为Excel
        output_path = output_dir / 'results.xlsx'
        df.to_excel(output_path, index=False, engine='openpyxl')

        logger.info(f"结果已保存到: {output_path}")
        return str(output_path)


# ========== 主函数 ==========

def main():
    """主函数入口"""
    import argparse

    parser = argparse.ArgumentParser(description='V4咖啡杯柄筛选器')
    parser.add_argument('--date', type=str, help='筛选日期 (YYYY-MM-DD)')
    parser.add_argument('--db-path', type=str, help='数据库路径')

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 60)
    logger.info("V4咖啡杯柄筛选器")
    logger.info("=" * 60)
    logger.info(f"筛选日期: {args.date or '最新数据日期'}")
    logger.info(f"数据库路径: {args.db_path or DB_PATH}")
    logger.info("")

    # 创建筛选器实例
    screener = CoffeeCupHandleScreenerV4(
        db_path=args.db_path
    )

    # 运行筛选
    results = screener.run_screening(args.date)

    # 保存结果
    if results:
        output_path = screener.save_results(results)
        logger.info("=" * 60)
        logger.info(f"筛选完成，共找到{len(results)}只股票")
        logger.info(f"结果文件: {output_path}")
        logger.info("=" * 60)

        # 打印结果摘要
        for result in results:
            logger.info(f"  {result['stock_code']} {result['stock_name']}: "
                       f"杯深{result['cup_depth']*100:.1f}%, "
                       f"杯柄{result['handle_length']}天, "
                       f"成交额倍数{result['amount_ratio']:.2f}x")
    else:
        logger.info("=" * 60)
        logger.info("未找到符合条件的股票")
        logger.info("=" * 60)

    return 0 if results else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
