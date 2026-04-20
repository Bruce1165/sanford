import os
#!/usr/bin/env python3
"""
高紧旗形筛选器 - High Tight Flag Screener (欧奈尔 CANSLIM)

欧奈尔最喜欢的形态之一！

形态定义：
- 股价在短期内（3-6周）快速上涨 100%+（旗杆）
- 随后进入紧凑的、小幅回调的整理阶段（旗面）
- 整理幅度通常只有 10%-25%
- 整理期间成交量明显萎缩
- 突破时放量继续上攻

技术参数（欧奈尔标准）：
- 旗杆涨幅：≥100%（3-6周内翻倍）
- 旗面回调：10%-25%
- 旗面周期：2-4周
- 突破成交量：≥1.5倍旗面均量
- 整体形态紧凑，不松散

特点：
- 强势股的标志
- 通常出现在行业龙头股上
- 突破后涨幅可观
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

from base_screener import BaseScreener
try:
    from database import init_db, get_session, Stock
    _HAS_DATABASE = True
except ImportError:
    _HAS_DATABASE = False
    init_db = get_session = Stock = None

logger = logging.getLogger(__name__)


class HighTightFlagScreener(BaseScreener):
    """高紧旗形筛选器（欧奈尔最喜爱的形态）"""
    
    def __init__(self,
                 pole_min_gain: float = 1.00,
                 pole_max_days: int = 45,
                 flag_max_retrace: float = 0.25,
                 flag_min_retrace: float = 0.10,
                 flag_max_days: int = 28,
                 flag_min_days: int = 10,
                 min_volume_ratio: float = 1.5,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='high_tight_flag',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.pole_min_gain = pole_min_gain
        self.pole_max_days = pole_max_days
        self.flag_max_retrace = flag_max_retrace
        self.flag_min_retrace = flag_min_retrace
        self.flag_max_days = flag_max_days
        self.flag_min_days = flag_min_days
        self.min_volume_ratio = min_volume_ratio

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'POLE_MIN_GAIN': {
                'type': 'float',
                'default': 1.00,
                'min': 0.8,
                'max': 1.5,
                'step': 0.1,
                'display_name': '旗杆最小涨幅',
                'description': '旗杆上涨需要的最小涨幅比例',
                'group': '旗杆条件'
            },
            'POLE_MAX_DAYS': {
                'type': 'int',
                'default': 45,
                'min': 30,
                'max': 60,
                'display_name': '旗杆最大天数',
                'description': '旗杆上涨的最大交易日数',
                'group': '旗杆条件'
            },
            'FLAG_MAX_RETRACE': {
                'type': 'float',
                'default': 0.25,
                'min': 0.15,
                'max': 0.35,
                'step': 0.05,
                'display_name': '旗面最大回调',
                'description': '旗面整理期间最大回调幅度比例',
                'group': '旗面条件'
            },
            'FLAG_MIN_RETRACE': {
                'type': 'float',
                'default': 0.10,
                'min': 0.05,
                'max': 0.15,
                'step': 0.01,
                'display_name': '旗面最小回调',
                'description': '旗面整理期间最小回调幅度比例',
                'group': '旗面条件'
            },
            'FLAG_MAX_DAYS': {
                'type': 'int',
                'default': 28,
                'min': 20,
                'max': 40,
                'display_name': '旗面最大天数',
                'description': '旗面整理的最大交易日数',
                'group': '旗面条件'
            },
            'FLAG_MIN_DAYS': {
                'type': 'int',
                'default': 10,
                'min': 7,
                'max': 15,
                'display_name': '旗面最小天数',
                'description': '旗面整理的最少交易日数',
                'group': '旗面条件'
            },
            'MIN_VOLUME_RATIO': {
                'type': 'float',
                'default': 1.5,
                'min': 1.2,
                'max': 2.0,
                'step': 0.1,
                'display_name': '最小成交量倍数',
                'description': '突破日成交量相对于旗面均量的最小倍数',
                'group': '量能条件'
            }
        }
    
    def find_high_tight_flag(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找高紧旗形形态
        
        Returns:
            旗形信息或None
        """
        if len(df) < 80:  # 需要足够的历史数据
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        latest = df.iloc[-1]
        
        # 从后向前寻找旗面整理期
        for flag_end_idx in range(len(df) - 1, self.flag_max_days + 10, -1):
            flag_start_idx = max(flag_end_idx - self.flag_max_days, flag_end_idx - self.flag_min_days)
            
            if flag_start_idx < 10:
                continue
            
            flag_period = df.iloc[flag_start_idx:flag_end_idx]
            
            if len(flag_period) < self.flag_min_days:
                continue
            
            flag_high = flag_period['high'].max()
            flag_low = flag_period['low'].min()
            
            # 检查旗面回调幅度
            flag_retrace = (flag_high - flag_low) / flag_high
            if not (self.flag_min_retrace <= flag_retrace <= self.flag_max_retrace):
                continue
            
            # 寻找旗杆起点（旗面前的高点）
            pole_period = df.iloc[max(0, flag_start_idx - self.pole_max_days):flag_start_idx]
            
            if len(pole_period) < 10:
                continue
            
            pole_start_price = pole_period.iloc[:5]['close'].mean()  # 旗杆起点均价
            pole_end_price = flag_high  # 旗杆终点即旗面高点
            
            # 检查旗杆涨幅
            pole_gain = (pole_end_price - pole_start_price) / pole_start_price
            if pole_gain < self.pole_min_gain:
                continue
            
            # 检查旗面成交量（应萎缩）
            pole_volume_avg = pole_period['volume'].mean()
            flag_volume_avg = flag_period['volume'].mean()
            
            if pole_volume_avg > 0:
                volume_contraction = flag_volume_avg / pole_volume_avg
                if volume_contraction > 0.70:  # 旗面成交量应明显小于旗杆
                    continue
            
            # 检查突破
            breakout_price = latest['close']
            
            # 收盘价突破旗面高点
            if breakout_price <= flag_high * 1.01:
                continue
            
            # 检查突破成交量
            if flag_volume_avg > 0 and latest['volume'] < flag_volume_avg * self.min_volume_ratio:
                continue
            
            # 计算旗面紧凑度（标准差/均值）
            flag_range_pct = flag_period['close'].std() / flag_period['close'].mean()
            
            return {
                'pole_start_price': round(pole_start_price, 2),
                'pole_end_price': round(pole_end_price, 2),
                'pole_gain': round(pole_gain * 100, 1),
                'pole_days': len(pole_period),
                'flag_high': round(flag_high, 2),
                'flag_low': round(flag_low, 2),
                'flag_retrace': round(flag_retrace * 100, 1),
                'flag_days': len(flag_period),
                'volume_contraction': round(volume_contraction * 100, 1),
                'flag_tightness': round(flag_range_pct * 100, 2),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - flag_high) / flag_high * 100, 2)
            }
        
        return None
    
    def run_screening(self, date_str=None, force_restart=False,
                      enable_analysis=False, no_check=False):
        """运行筛选，返回匹配结果列表。"""
        if date_str:
            self.current_date = date_str
        if not no_check and not self.check_data_availability(self.current_date):
            import logging as _log
            _log.getLogger(__name__).warning(
                "⚠️  无可用数据 (%s) - 市场尚未收盘或数据未下载", self.current_date)
            return []
        stocks = self.get_all_stocks()
        results = []
        for s in stocks:
            try:
                r = self.screen_stock(s.code, s.name)
                if r:
                    results.append(r)
            except Exception as exc:
                pass
        return results

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=100)
        if df is None or len(df) < 80:
            return None
        
        yesterday = df.iloc[-1]
        
        # 基础条件
        if yesterday.get('pct_change', 0) < 2.0:
            return None
        
        # 寻找高紧旗形
        flag_pattern = self.find_high_tight_flag(df)
        if flag_pattern is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'pole_gain': flag_pattern['pole_gain'],
            'pole_days': flag_pattern['pole_days'],
            'flag_retrace': flag_pattern['flag_retrace'],
            'flag_days': flag_pattern['flag_days'],
            'volume_contraction': flag_pattern['volume_contraction'],
            'breakout_pct': flag_pattern['breakout_pct']
        }
    
    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """详细检查单个股票"""
        import sqlite3 as _sqlite3
        
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        reasons = []
        details = {}
        
        try:
            with _sqlite3.connect(str(self._db_path), timeout=10) as _conn:
                _row = _conn.execute('SELECT name FROM stocks WHERE code=?', (code,)).fetchone()
            name = _row[0] if _row else ''
        except Exception:
            name = ''
        
        df = self.get_stock_data(code, days=100)
        if df is None or len(df) < 80:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少80天）']
            }
        
        yesterday = df.iloc[-1]
        
        # 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2.0:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < 2%')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 检查高紧旗形
        flag_pattern = self.find_high_tight_flag(df)
        
        if flag_pattern is None:
            reasons.append(f'未找到高紧旗形（需满足：旗杆翻倍{self.pole_min_gain*100:.0f}%+、'
                          f'旗面回调{self.flag_min_retrace*100:.0f}%-{self.flag_max_retrace*100:.0f}%、'
                          f'旗面紧凑）')
        else:
            details['旗杆涨幅'] = f"{flag_pattern['pole_gain']:.1f}%"
            details['旗杆天数'] = flag_pattern['pole_days']
            details['旗面回调'] = f"{flag_pattern['flag_retrace']:.1f}%"
            details['旗面天数'] = flag_pattern['flag_days']
            details['旗面缩量'] = f"{flag_pattern['volume_contraction']:.1f}%"
            details['突破幅度'] = f"{flag_pattern['breakout_pct']:.2f}%"
            
            # 风控计算（高紧旗形通常更激进）
            stop_loss = flag_pattern['flag_low'] * 0.95  # 5%止损
            target = flag_pattern['pole_end_price'] + (flag_pattern['pole_end_price'] - flag_pattern['pole_start_price']) * 0.5
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and flag_pattern is not None:
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [],
                'details': details,
                'risk_management': risk_management
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details if details else None,
                'risk_management': None
            }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='高紧旗形筛选器（欧奈尔最喜爱的形态）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = HighTightFlagScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只高紧旗形股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 旗杆{r['pole_gain']:.0f}%, 旗面{r['flag_retrace']:.0f}%")
