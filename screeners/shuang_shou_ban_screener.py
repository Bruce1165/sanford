import os
#!/usr/bin/env python3
"""
双首板筛选器 - Shuang Shou Ban Screener (原试盘线)

核心逻辑（五个信号同时具备才算启动确认）：

信号一：非一字板涨停，次日（X日）收阳+成交额翻倍
- 涨幅≥9.9%
- 不是一字板
- 次日（X日）收涨 + 成交额 ≥ 涨停日成交额 × 2

信号二：X日后出现第二个涨停，成交额 < X日成交额
- 第二个涨停（涨幅≥9.9%）
- 成交额 < X日成交额

信号三：第二个涨停后，所有交易日最低价 > 第二个涨停开盘价

信号四：第二个涨停后，出现地量T日，成交额 < X日成交额 × 0.25

信号五：T日之后出现启动信号
- 单日收涨
- 成交额 ≥ 前1日成交额 × 2

输出：五个信号都满足即输出
"""

import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).parent))

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

LIMIT_DAYS = 34  # 最近34个交易日
LIMIT_UP_THRESHOLD = 9.9  # 涨停阈值（%）


class ShuangShouBanScreener(BaseScreener):
    """双首板筛选器"""

    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 limit_up_threshold: float = LIMIT_UP_THRESHOLD,
                 x_day_volume_ratio: float = 2.0,
                 signal_four_volume_ratio: float = 0.25,
                 signal_five_volume_ratio: float = 2.0,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='shuang_shou_ban',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.limit_up_threshold = limit_up_threshold
        self.x_day_volume_ratio = x_day_volume_ratio
        self.signal_four_volume_ratio = signal_four_volume_ratio
        self.signal_five_volume_ratio = signal_five_volume_ratio
    
    def is_limit_up(self, pct_change: float) -> bool:
        """判断是否涨停"""
        return pct_change >= self.limit_up_threshold

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 34,
                'min': 1,
                'max': 60,
                'display_name': '时间范围（交易日）',
                'description': '筛选最近多少个交易日内的信号',
                'group': '基础设置'
            },
            'LIMIT_UP_THRESHOLD': {
                'type': 'float',
                'default': 9.9,
                'min': 9.0,
                'max': 10.5,
                'step': 0.1,
                'display_name': '涨停阈值（%）',
                'description': '判断涨停的最低涨幅阈值',
                'group': '信号条件'
            },
            'X_DAY_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': 'X日成交额倍数',
                'description': 'X日（涨停次日）成交额需要达到涨停日的倍数',
                'group': '信号条件'
            },
            'SIGNAL_FOUR_VOLUME_RATIO': {
                'type': 'float',
                'default': 0.25,
                'min': 0.15,
                'max': 0.4,
                'step': 0.05,
                'display_name': '信号四地量倍数',
                'description': '地量日成交额需要小于X日成交额的倍数',
                'group': '信号条件'
            },
            'SIGNAL_FIVE_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': '信号五成交额倍数',
                'description': '启动日成交额需要达到前一日成交额的倍数',
                'group': '信号条件'
            }
        }
    
    def is_yi_zi_ban(self, row: pd.Series) -> bool:
        """判断是否为一字板"""
        return row['open'] == row['close'] == row['high'] == row['low']
    
    def find_signal_one_and_x(self, df: pd.DataFrame) -> Optional[Tuple[int, int]]:
        """
        寻找信号一和X日
        - 信号一：非一字板涨停
        - X日：次日收阳+成交额翻倍
        
        Returns:
            (信号一索引, X日索引) 或 None
        """
        for i in range(len(df) - 2, 0, -1):
            row = df.iloc[i]
            
            # 1. 涨停
            if not self.is_limit_up(row['pct_change'] or 0):
                continue
            
            # 2. 非一字板
            if self.is_yi_zi_ban(row):
                continue
            
            # 检查X日（次日）
            x_idx = i + 1
            if x_idx >= len(df):
                continue
            
            x_row = df.iloc[x_idx]
            
            # X日收阳
            if x_row['pct_change'] <= 0:
                continue
            
            # X日成交额 ≥ 涨停日成交额 × 指定倍数
            if x_row['amount'] < row['amount'] * self.x_day_volume_ratio:
                continue
            
            return i, x_idx
        
        return None
    
    def find_signal_two(self, df: pd.DataFrame, x_idx: int) -> Optional[int]:
        """
        寻找信号二：X日后第二个涨停，成交额 < X日成交额
        
        Returns:
            第二个涨停的索引，或None
        """
        x_amount = df.iloc[x_idx]['amount']
        
        # 从X日后一天开始找
        for i in range(x_idx + 1, len(df)):
            row = df.iloc[i]
            
            # 涨停
            if not self.is_limit_up(row['pct_change'] or 0):
                continue
            
            # 成交额 < X日成交额
            if row['amount'] >= x_amount:
                continue
            
            return i
        
        return None
    
    def check_signal_three(self, df: pd.DataFrame, signal_two_idx: int, end_idx: int) -> bool:
        """
        检查信号三：第二个涨停后到end_idx，所有最低价 > 第二个涨停开盘价
        """
        signal_two_open = df.iloc[signal_two_idx]['open']
        
        for i in range(signal_two_idx + 1, end_idx):
            if i >= len(df):
                break
            if df.iloc[i]['low'] <= signal_two_open:
                return False
        
        return True
    
    def find_signal_four(self, df: pd.DataFrame, signal_two_idx: int, x_idx: int) -> Optional[int]:
        """
        寻找信号四：第二个涨停后，地量T日（成交额 < X日成交额 × 指定倍数）

        Returns:
            地量日索引，或None
        """
        x_amount = df.iloc[x_idx]['amount']
        threshold = x_amount * self.signal_four_volume_ratio

        # 从第二个涨停后一天开始找
        for i in range(signal_two_idx + 1, len(df)):
            if df.iloc[i]['amount'] < threshold:
                return i

        return None
    
    def find_signal_five(self, df: pd.DataFrame, signal_four_idx: int) -> Optional[int]:
        """
        寻找信号五：T日之后启动（收涨 + 成交额翻倍）
        
        Returns:
            启动日索引，或None
        """
        for i in range(signal_four_idx + 1, len(df)):
            row = df.iloc[i]
            
            # 收涨
            if row['pct_change'] <= 0:
                continue
            
            # 成交额 ≥ 前1日 × 指定倍数
            prev_amount = df.iloc[i - 1]['amount']
            if prev_amount <= 0 or row['amount'] < prev_amount * self.signal_five_volume_ratio:
                continue
            
            return i
        
        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < 10:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 找信号一和X日
        result = self.find_signal_one_and_x(df)
        if result is None:
            return None
        
        signal_one_idx, x_idx = result
        
        # 检查34天范围
        latest_date = df.iloc[-1]['trade_date']
        signal_one_date = df.iloc[signal_one_idx]['trade_date']
        if (latest_date - signal_one_date).days > self.limit_days:
            return None
        
        # 找信号二
        signal_two_idx = self.find_signal_two(df, x_idx)
        if signal_two_idx is None:
            return None
        
        # 找信号四
        signal_four_idx = self.find_signal_four(df, signal_two_idx, x_idx)
        if signal_four_idx is None:
            return None
        
        # 找信号五
        signal_five_idx = self.find_signal_five(df, signal_four_idx)
        if signal_five_idx is None:
            return None
        
        # 检查信号三
        if not self.check_signal_three(df, signal_two_idx, signal_five_idx):
            return None
        
        # 五个信号都满足
        signal_one = df.iloc[signal_one_idx]
        x_day = df.iloc[x_idx]
        signal_two = df.iloc[signal_two_idx]
        signal_four = df.iloc[signal_four_idx]
        signal_five = df.iloc[signal_five_idx]
        
        return {
            'code': code,
            'name': name,
            'first_limit_up_date': signal_one_date.strftime('%Y-%m-%d'),
            'x_date': x_day['trade_date'].strftime('%Y-%m-%d'),
            'second_limit_up_date': signal_two['trade_date'].strftime('%Y-%m-%d'),
            't_date': signal_four['trade_date'].strftime('%Y-%m-%d'),
            'launch_date': signal_five['trade_date'].strftime('%Y-%m-%d'),
            'days_total': signal_five_idx - signal_one_idx,
            
            # 信号一
            's1_amount': round(signal_one['amount'] / 10000, 2),
            
            # X日
            'x_amount': round(x_day['amount'] / 10000, 2),
            'x_amount_ratio': round(x_day['amount'] / signal_one['amount'], 2),
            
            # 信号二
            's2_amount': round(signal_two['amount'] / 10000, 2),
            's2_to_x_ratio': round(signal_two['amount'] / x_day['amount'], 2),
            
            # 信号四
            't_amount': round(signal_four['amount'] / 10000, 2),
            't_to_x_ratio': round(signal_four['amount'] / x_day['amount'], 2),
            
            # 信号五
            'launch_close': round(signal_five['close'], 2),
            'launch_pct': round(signal_five['pct_change'], 2),
            'launch_amount_ratio': round(signal_five['amount'] / df.iloc[signal_five_idx - 1]['amount'], 2),
            
            'all_signals_confirmed': True
        }
    
    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """运行筛选"""
        if date_str:
            self.current_date = date_str
        
        # 检查数据是否可用
        
        logger.info("="*60)
        logger.info("双首板筛选器 - Shuang Shou Ban Screener")
        logger.info(f"时间范围: 最近{self.limit_days}个交易日")
        logger.info("="*60)
        
        stocks = self.get_all_stocks()
        stocks = [s for s in stocks if not s.code.startswith(('8', '4'))]
        
        total_stocks = len(stocks)
        logger.info(f"Total stocks: {total_stocks}")
        
        start_idx = 0
        if self.progress_tracker and not force_restart:
            if self.progress_tracker.is_resumable():
                processed_codes = self.progress_tracker.get_processed_codes()
                start_idx = len(processed_codes)
        
        if self.progress_tracker:
            self.progress_tracker.start(total_stocks=total_stocks)
        
        results = []
        analysis_data = {}
        
        for i, stock in enumerate(stocks[start_idx:], start=start_idx):
            try:
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(processed=i+1, matched=len(results))
                
                result = self.screen_stock(stock.code, stock.name)
                
                if result:
                    results.append(result)
                    logger.info(f"✓ Found: {stock.code} {stock.name}")
                
            except Exception as e:
                logger.error(f"Error: {e}")
        
        if self.progress_tracker:
            self.progress_tracker.complete(success=True)
        
        logger.info(f"\n完成! 检查: {total_stocks}, 匹配: {len(results)}")
        
        return results
    
    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'first_limit_up_date': '首板日期',
            'x_date': 'X日日期',
            'second_limit_up_date': '二板日期',
            't_date': 'T日日期',
            'launch_date': '启动日期',
            'days_total': '总天数',
            'x_amount_ratio': 'X日/首板成交额',
            's2_to_x_ratio': '二板/X日成交额',
            't_to_x_ratio': 'T日/X日成交额',
            'launch_pct': '启动日涨幅%',
            'launch_amount_ratio': '启动日成交额环比',
            'all_signals_confirmed': '五信号确认'
        }
        
        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='双首板筛选器')
    parser.add_argument('--date', type=str, help='目标日期')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS)
    parser.add_argument('--no-news', action='store_true')
    parser.add_argument('--no-llm', action='store_true')
    parser.add_argument('--restart', action='store_true')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    screener = ShuangShouBanScreener(
        limit_days=args.limit_days,
        enable_news=False,  # 禁用新闻
        enable_llm=False    # 禁用LLM
    )
    
    result = screener.run_screening(date_str=args.date, force_restart=args.restart)
    
    # Handle different return formats
    if result is None:
        results, _ = [], {}
    elif isinstance(result, tuple) and len(result) == 2:
        results, _ = result
    else:
        results = result
    
    if results:
        output_path = screener.save_results(results)
        print(f"\n结果已保存: {output_path}")
        for r in results[:10]:
            print(f"{r['code']} {r['name']}: 首板{r['first_limit_up_date']}, 启动{r['launch_date']}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'shuang_shou_ban_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        from config import FLASK_PORT as _PORT
        print(f"  Excel: http://localhost:{_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n无结果")


if __name__ == '__main__':
    main()
