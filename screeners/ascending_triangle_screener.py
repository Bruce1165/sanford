import os
#!/usr/bin/env python3
"""
上升三角形筛选器 - Ascending Triangle Screener (欧奈尔 CANSLIM)

形态定义：
- 股价形成一系列高点相近的水平阻力线
- 低点逐渐抬高，形成上升支撑线
- 两条线形成向上的三角形
- 突破时成交量放大

技术参数（欧奈尔标准）：
- 整理周期：4-8周（20-40个交易日）
- 至少2个高点相近（±3%）
- 至少2个低点逐渐抬高
- 突破幅度：收盘价突破阻力线3%以上
- 突破成交量：≥1.5倍整理期均量

特点：
- 看涨持续形态
- 显示买方力量逐渐增强
- 通常出现在上升趋势中
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


class AscendingTriangleScreener(BaseScreener):
    """上升三角形筛选器（欧奈尔标准）"""
    
    def __init__(self,
                 min_triangle_days: int = 20,
                 max_triangle_days: int = 40,
                 resistance_tolerance: float = 0.03,
                 min_touches: int = 2,
                 min_breakout_pct: float = 0.03,
                 min_volume_ratio: float = 1.5,
                 low_tolerance: float = 1.01,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='ascending_triangle',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.min_triangle_days = min_triangle_days
        self.max_triangle_days = max_triangle_days
        self.resistance_tolerance = resistance_tolerance
        self.min_touches = min_touches
        self.min_breakout_pct = min_breakout_pct
        self.min_volume_ratio = min_volume_ratio
        self.low_tolerance = low_tolerance

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'MIN_TRIANGLE_DAYS': {
                'type': 'int',
                'default': 20,
                'min': 15,
                'max': 60,
                'display_name': '最小整理天数',
                'description': '三角形整理的最少交易日数',
                'group': '基础设置'
            },
            'MAX_TRIANGLE_DAYS': {
                'type': 'int',
                'default': 40,
                'min': 30,
                'max': 80,
                'display_name': '最大整理天数',
                'description': '三角形整理的最多交易日数',
                'group': '基础设置'
            },
            'RESISTANCE_TOLERANCE': {
                'type': 'float',
                'default': 0.03,
                'min': 0.02,
                'max': 0.05,
                'step': 0.005,
                'display_name': '阻力线容忍度',
                'description': '高点之间允许的最大差异比例',
                'group': '形态条件'
            },
            'MIN_TOUCHES': {
                'type': 'int',
                'default': 2,
                'min': 2,
                'max': 4,
                'display_name': '最少触及次数',
                'description': '支撑线或阻力线最少触及次数',
                'group': '形态条件'
            },
            'MIN_BREAKOUT_PCT': {
                'type': 'float',
                'default': 0.03,
                'min': 0.02,
                'max': 0.05,
                'step': 0.005,
                'display_name': '最小突破幅度',
                'description': '收盘价突破阻力线的最小幅度',
                'group': '突破条件'
            },
            'MIN_VOLUME_RATIO': {
                'type': 'float',
                'default': 1.5,
                'min': 1.2,
                'max': 2.0,
                'step': 0.1,
                'display_name': '最小成交量倍数',
                'description': '突破日成交量相对于整理期均量的最小倍数',
                'group': '量能条件'
            },
            'LOW_TOLERANCE': {
                'type': 'float',
                'default': 1.01,
                'min': 1.0,
                'max': 1.02,
                'step': 0.005,
                'display_name': '低点抬升容忍度',
                'description': '低点抬升时允许的误差比例',
                'group': '形态条件'
            }
        }
    
    def find_ascending_triangle(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找上升三角形形态
        
        Returns:
            三角形信息或None
        """
        if len(df) < 60:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 从后向前寻找整理区间
        for i in range(len(df) - 1, self.max_triangle_days, -1):
            period = df.iloc[i - self.max_triangle_days:i]
            
            if len(period) < self.min_triangle_days:
                continue
            
            # 寻找高点（阻力线）
            highs = period['high'].nlargest(5).values  # 取最高的5个点
            
            # 检查高点是否接近（形成水平阻力线）
            resistance_price = np.median(highs)
            high_variation = np.max(np.abs(highs - resistance_price)) / resistance_price
            
            if high_variation > self.resistance_tolerance:
                continue
            
            # 寻找低点（支撑线）
            # 寻找至少2个逐渐抬高的低点
            lows_data = []
            for j in range(1, len(period) - 1):
                # 局部低点
                if (period.iloc[j]['low'] < period.iloc[j-1]['low'] and 
                    period.iloc[j]['low'] < period.iloc[j+1]['low']):
                    lows_data.append({
                        'idx': j,
                        'price': period.iloc[j]['low']
                    })
            
            if len(lows_data) < self.min_touches:
                continue
            
            # 检查低点是否逐渐抬高
            ascending = True
            for k in range(1, len(lows_data)):
                if lows_data[k]['price'] <= lows_data[k-1]['price'] * self.low_tolerance:
                    ascending = False
                    break
            
            if not ascending:
                continue
            
            # 计算支撑线斜率（应为正）
            support_slope = (lows_data[-1]['price'] - lows_data[0]['price']) / (lows_data[-1]['idx'] - lows_data[0]['idx'])
            if support_slope <= 0:
                continue
            
            # 检查突破
            latest = df.iloc[-1]
            breakout_price = latest['close']
            
            # 收盘价突破阻力线3%以上
            if breakout_price < resistance_price * (1 + self.min_breakout_pct):
                continue
            
            # 检查突破成交量
            period_volume_avg = period['volume'].mean()
            if period_volume_avg > 0 and latest['volume'] < period_volume_avg * self.min_volume_ratio:
                continue
            
            # 计算形态高度（用于目标位）
            lowest_low = period['low'].min()
            triangle_height = resistance_price - lowest_low
            
            return {
                'resistance_price': round(resistance_price, 2),
                'support_start': round(lows_data[0]['price'], 2),
                'support_end': round(lows_data[-1]['price'], 2),
                'support_slope': round(support_slope, 4),
                'high_touches': len(highs),
                'low_touches': len(lows_data),
                'lowest_low': round(lowest_low, 2),
                'triangle_height': round(triangle_height, 2),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - resistance_price) / resistance_price * 100, 2),
                'volume_ratio': round(latest['volume'] / period_volume_avg, 2) if period_volume_avg > 0 else 0,
                'triangle_days': len(period)
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
        df = self.get_stock_data(code, days=60)
        if df is None or len(df) < 40:
            return None
        
        yesterday = df.iloc[-1]
        
        # 基础条件
        if yesterday.get('pct_change', 0) < 2.0:
            return None
        
        # 寻找上升三角形
        triangle = self.find_ascending_triangle(df)
        if triangle is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'resistance_price': triangle['resistance_price'],
            'support_slope': triangle['support_slope'],
            'high_touches': triangle['high_touches'],
            'low_touches': triangle['low_touches'],
            'triangle_height': triangle['triangle_height'],
            'breakout_pct': triangle['breakout_pct'],
            'volume_ratio': triangle['volume_ratio'],
            'triangle_days': triangle['triangle_days']
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
        
        df = self.get_stock_data(code, days=60)
        if df is None or len(df) < 40:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取足够的历史数据（需要至少40天）']
            }
        
        yesterday = df.iloc[-1]
        
        # 检查涨幅
        pct_change = yesterday.get('pct_change', 0) or 0
        if pct_change < 2.0:
            reasons.append(f'涨幅不足：{pct_change:.2f}% < 2%')
        else:
            details['涨幅'] = f'{pct_change:.2f}%'
        
        # 检查上升三角形
        triangle = self.find_ascending_triangle(df)
        
        if triangle is None:
            reasons.append(f'未找到上升三角形（需满足：整理期{self.min_triangle_days}-{self.max_triangle_days}天、'
                          f'水平阻力线、低点抬高、突破≥{self.min_breakout_pct*100:.0f}%）')
        else:
            details['阻力线价格'] = f"{triangle['resistance_price']:.2f}"
            details['阻力触及次数'] = triangle['high_touches']
            details['支撑触及次数'] = triangle['low_touches']
            details['形态高度'] = f"{triangle['triangle_height']:.2f}"
            details['突破幅度'] = f"{triangle['breakout_pct']:.2f}%"
            details['量比'] = f"{triangle['volume_ratio']:.2f}倍"
            details['整理天数'] = triangle['triangle_days']
            
            # 风控计算
            stop_loss = triangle['support_end'] * 0.97
            target = triangle['resistance_price'] + triangle['triangle_height']  # 等幅上涨
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and triangle is not None:
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
    parser = argparse.ArgumentParser(description='上升三角形筛选器（欧奈尔标准）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = AscendingTriangleScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只上升三角形股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 突破{r['breakout_pct']:.1f}%, 高度{r['triangle_height']:.2f}")
