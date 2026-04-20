import os
#!/usr/bin/env python3
"""
平底形态筛选器 - Flat Base Screener (欧奈尔 CANSLIM)

形态定义：
- 股价在一段时间内横向整理，波动幅度很小
- 形成水平的底部区域（类似矩形整理）
- 突破时放量上涨

技术参数（欧奈尔标准）：
- 整理周期：5-7周（25-35个交易日）
- 波动幅度：≤15%（最高价-最低价）/ 最低价
- 突破幅度：收盘价突破区间高点3%以上
- 突破成交量：≥1.5倍整理期均量
- 整理期特征：成交量逐渐萎缩

欧奈尔认为平底是杯柄形态的一种变体，出现在杯柄之后或单独出现。
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


class FlatBaseScreener(BaseScreener):
    """平底形态筛选器（欧奈尔标准）"""
    
    def __init__(self,
                 min_base_days: int = 25,
                 max_base_days: int = 35,
                 max_range_pct: float = 0.15,
                 min_breakout_pct: float = 0.03,
                 min_volume_ratio: float = 1.5,
                 min_position: float = 0.3,
                 max_position: float = 0.7,
                 slope_tolerance: float = 0.5,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = True,
                 enable_llm: bool = True,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='flat_base',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.min_base_days = min_base_days
        self.max_base_days = max_base_days
        self.max_range_pct = max_range_pct
        self.min_breakout_pct = min_breakout_pct
        self.min_volume_ratio = min_volume_ratio
        self.min_position = min_position
        self.max_position = max_position
        self.slope_tolerance = slope_tolerance

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'MIN_BASE_DAYS': {
                'type': 'int',
                'default': 25,
                'min': 15,
                'max': 60,
                'display_name': '最小整理天数',
                'description': '平底整理的最少交易日数',
                'group': '基础设置'
            },
            'MAX_BASE_DAYS': {
                'type': 'int',
                'default': 35,
                'min': 25,
                'max': 60,
                'display_name': '最大整理天数',
                'description': '平底整理的最多交易日数',
                'group': '基础设置'
            },
            'MAX_RANGE_PCT': {
                'type': 'float',
                'default': 0.15,
                'min': 0.10,
                'max': 0.25,
                'step': 0.01,
                'display_name': '最大波动幅度',
                'description': '整理期间允许的最大波动幅度比例',
                'group': '形态条件'
            },
            'MIN_BREAKOUT_PCT': {
                'type': 'float',
                'default': 0.03,
                'min': 0.02,
                'max': 0.05,
                'step': 0.005,
                'display_name': '最小突破幅度',
                'description': '收盘价突破区间高点的最小幅度',
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
            'MIN_POSITION': {
                'type': 'float',
                'default': 0.3,
                'min': 0.2,
                'max': 0.5,
                'step': 0.05,
                'display_name': '最小平均位置',
                'description': '收盘价在区间中的最小平均位置比例',
                'group': '形态条件'
            },
            'MAX_POSITION': {
                'type': 'float',
                'default': 0.7,
                'min': 0.5,
                'max': 0.8,
                'step': 0.05,
                'display_name': '最大平均位置',
                'description': '收盘价在区间中的最大平均位置比例',
                'group': '形态条件'
            },
            'SLOPE_TOLERANCE': {
                'type': 'float',
                'default': 0.5,
                'min': 0.3,
                'max': 0.7,
                'step': 0.05,
                'display_name': '斜率容忍度',
                'description': '允许的线性回归斜率相对于波动幅度的最大比例',
                'group': '形态条件'
            }
        }
    
    def find_flat_base(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找平底形态
        
        Returns:
            平底信息或None
        """
        if len(df) < self.max_base_days + 10:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 从后向前寻找整理区间
        for i in range(len(df) - 1, self.max_base_days, -1):
            # 取可能的整理期
            base_period = df.iloc[i - self.max_base_days:i]
            
            if len(base_period) < self.min_base_days:
                continue
            
            base_high = base_period['high'].max()
            base_low = base_period['low'].min()
            base_close_avg = base_period['close'].mean()
            
            # 检查波动幅度
            range_pct = (base_high - base_low) / base_low
            if range_pct > self.max_range_pct:
                continue
            
            # 检查收盘价是否集中在区间中部（排除趋势形态）
            close_positions = []
            for _, row in base_period.iterrows():
                pos = (row['close'] - base_low) / (base_high - base_low)
                close_positions.append(pos)
            
            avg_position = np.mean(close_positions)
            # 平均位置应在指定范围内（不是一直跌或一直涨）
            if not (self.min_position <= avg_position <= self.max_position):
                continue

            # 检查是否有明显的趋势线（排除上升通道或下降通道）
            # 简单线性回归检查斜率
            x = np.arange(len(base_period))
            y = base_period['close'].values
            slope = np.polyfit(x, y, 1)[0]

            # 斜率应接近0（水平整理）
            if abs(slope) > (base_high - base_low) / len(base_period) * self.slope_tolerance:
                continue
            
            # 检查突破
            latest = df.iloc[-1]
            breakout_price = latest['close']
            
            # 收盘价突破区间高点3%以上
            if breakout_price < base_high * (1 + self.min_breakout_pct):
                continue
            
            # 检查突破成交量
            base_volume_avg = base_period['volume'].mean()
            if base_volume_avg > 0 and latest['volume'] < base_volume_avg * self.min_volume_ratio:
                continue
            
            # 检查整理期成交量特征（应逐渐萎缩）
            first_half_vol = base_period.iloc[:len(base_period)//2]['volume'].mean()
            second_half_vol = base_period.iloc[len(base_period)//2:]['volume'].mean()
            
            return {
                'base_high': round(base_high, 2),
                'base_low': round(base_low, 2),
                'base_range_pct': round(range_pct * 100, 2),
                'avg_close': round(base_close_avg, 2),
                'slope': round(slope, 4),
                'breakout_price': round(breakout_price, 2),
                'breakout_pct': round((breakout_price - base_high) / base_high * 100, 2),
                'volume_ratio': round(latest['volume'] / base_volume_avg, 2) if base_volume_avg > 0 else 0,
                'volume_contraction': round(second_half_vol / first_half_vol * 100, 1) if first_half_vol > 0 else 100,
                'base_days': len(base_period)
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
        
        # 寻找平底形态
        flat_base = self.find_flat_base(df)
        if flat_base is None:
            return None
        
        return {
            'code': code,
            'name': name,
            'close': round(yesterday['close'], 2),
            'pct_change': round(yesterday.get('pct_change', 0), 2),
            'turnover': round(yesterday.get('turnover', 0) or 0, 2),
            'base_high': flat_base['base_high'],
            'base_low': flat_base['base_low'],
            'base_range_pct': flat_base['base_range_pct'],
            'breakout_pct': flat_base['breakout_pct'],
            'volume_ratio': flat_base['volume_ratio'],
            'volume_contraction': flat_base['volume_contraction'],
            'base_days': flat_base['base_days']
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
        
        # 检查平底形态
        flat_base = self.find_flat_base(df)
        
        if flat_base is None:
            reasons.append(f'未找到平底形态（需满足：整理期{self.min_base_days}-{self.max_base_days}天、'
                          f'波动≤{self.max_range_pct*100:.0f}%、突破≥{self.min_breakout_pct*100:.0f}%）')
        else:
            details['整理区间高点'] = f"{flat_base['base_high']:.2f}"
            details['整理区间低点'] = f"{flat_base['base_low']:.2f}"
            details['区间波动'] = f"{flat_base['base_range_pct']:.2f}%"
            details['突破幅度'] = f"{flat_base['breakout_pct']:.2f}%"
            details['量比'] = f"{flat_base['volume_ratio']:.2f}倍"
            details['缩量程度'] = f"{flat_base['volume_contraction']:.1f}%"
            details['整理天数'] = flat_base['base_days']
            
            # 风控计算
            stop_loss = flat_base['base_low'] * 0.97
            target = flat_base['base_high'] + (flat_base['base_high'] - flat_base['base_low']) * 1.5
            
            risk_management = {
                '止损位': f'{stop_loss:.2f}',
                '目标位': f'{target:.2f}',
                '盈亏比': f'1:{(target - yesterday["close"]) / (yesterday["close"] - stop_loss):.1f}'
            }
        
        if len(reasons) == 0 and flat_base is not None:
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
    parser = argparse.ArgumentParser(description='平底形态筛选器（欧奈尔标准）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    screener = FlatBaseScreener()
    results = screener.run_screening(args.date)
    
    print(f"找到 {len(results)} 只平底形态股票")
    for r in results:
        print(f"  {r['code']} - {r['name']}: 区间{r['base_range_pct']:.1f}%, 突破{r['breakout_pct']:.1f}%")
