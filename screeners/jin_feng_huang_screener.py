import os
#!/usr/bin/env python3
"""
涨停金凤凰筛选器 - Jin Feng Huang Screener (V2)

核心逻辑（五个信号同时具备才算启动确认）：

信号一：非一字板涨停，当日成交额 ≥ 前1日成交额的2倍
- 涨幅≥9.9%
- 不是一字板（开盘/收盘/最高/最低价不全相同）
- 成交额 ≥ 前1日成交额 × 2

信号二：次日高开收阳，成交额 ≥ 信号一成交额的2倍
- 高开（开盘价 > 信号一收盘价）
- 收阳（收盘价 > 开盘价）
- 成交额 ≥ 信号一成交额 × 2

信号三：信号一之后到信号五之前，所有交易日最低价 > 信号一最高价

信号四：出现地量日（T日），成交额 < T日前1日成交额的0.5倍

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

LIMIT_DAYS = 14  # 最近14个交易日


class JinFengHuangScreener(BaseScreener):
    """涨停金凤凰筛选器 V2"""
    
    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 limit_up_threshold: float = 9.9,
                 signal_one_volume_ratio: float = 2.0,
                 signal_two_volume_ratio: float = 2.0,
                 signal_four_volume_ratio: float = 0.5,
                 signal_five_volume_ratio: float = 2.0,
                 min_history_days: int = 10,
                 history_buffer_days: int = 10,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True,
                 use_pool: bool = False):
        super().__init__(
            screener_name='jin_feng_huang',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.limit_up_threshold = limit_up_threshold
        self.signal_one_volume_ratio = signal_one_volume_ratio
        self.signal_two_volume_ratio = signal_two_volume_ratio
        self.signal_four_volume_ratio = signal_four_volume_ratio
        self.signal_five_volume_ratio = signal_five_volume_ratio
        self.min_history_days = max(1, int(min_history_days))
        self.history_buffer_days = max(0, int(history_buffer_days))
        self.use_pool = use_pool

    def get_screener_code(self) -> str:
        """Return this screener's code for DB lookup."""
        return 'jin_feng_huang'

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 14,
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
            'SIGNAL_ONE_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': '信号一成交额倍数',
                'description': '信号一当日成交额需要达到前一日的倍数',
                'group': '信号条件'
            },
            'SIGNAL_TWO_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': '信号二成交额倍数',
                'description': '信号二当日成交额需要达到前一日的倍数',
                'group': '信号条件'
            },
            'SIGNAL_FOUR_VOLUME_RATIO': {
                'type': 'float',
                'default': 0.5,
                'min': 0.3,
                'max': 0.7,
                'step': 0.05,
                'display_name': '信号四地量倍数',
                'description': '信号四（地量日）成交额需要小于前一日的最大倍数',
                'group': '信号条件'
            },
            'SIGNAL_FIVE_VOLUME_RATIO': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 3.0,
                'step': 0.1,
                'display_name': '信号五成交额倍数',
                'description': '信号五（启动日）成交额需要达到前一日的倍数',
                'group': '信号条件'
            },
            'MIN_HISTORY_DAYS': {
                'type': 'int',
                'default': 10,
                'min': 1,
                'max': 120,
                'display_name': '最小历史天数',
                'description': '单股筛选前要求的最少历史数据天数',
                'group': '基础设置'
            },
            'HISTORY_BUFFER_DAYS': {
                'type': 'int',
                'default': 10,
                'min': 0,
                'max': 120,
                'display_name': '历史缓冲天数',
                'description': '加载数据时在 LIMIT_DAYS 基础上额外增加的缓冲天数',
                'group': '基础设置'
            }
        }

    def is_limit_up(self, pct_change: float) -> bool:
        """判断是否涨停"""
        return pct_change >= self.limit_up_threshold
    
    def is_yi_zi_ban(self, row: pd.Series) -> bool:
        """判断是否为一字板（开盘/收盘/最高/最低价全相同）"""
        return row['open'] == row['close'] == row['high'] == row['low']
    
    def check_signal_one(self, df: pd.DataFrame, idx: int) -> bool:
        """
        检查信号一：非一字板涨停，当日成交额 ≥ 前1日成交额的2倍
        """
        if idx <= 0 or idx >= len(df):
            return False
        
        row = df.iloc[idx]
        
        # 1. 涨停
        if not self.is_limit_up(row['pct_change'] or 0):
            return False
        
        # 2. 非一字板
        if self.is_yi_zi_ban(row):
            return False
        
        # 3. 成交额 ≥ 前1日成交额的倍数
        prev_amount = df.iloc[idx - 1]['amount']
        if prev_amount <= 0 or row['amount'] < prev_amount * self.signal_one_volume_ratio:
            return False
        
        return True
    
    def check_signal_two(self, df: pd.DataFrame, signal_one_idx: int) -> bool:
        """
        检查信号二：次日收涨的阳线，最低价>T日最高价，成交额 ≥ 前1日成交额的2倍
        """
        signal_two_idx = signal_one_idx + 1
        if signal_two_idx >= len(df):
            return False

        signal_one = df.iloc[signal_one_idx]
        signal_two = df.iloc[signal_two_idx]

        # 1. 收阳（收盘价 > 开盘价）
        if signal_two['close'] <= signal_two['open']:
            return False

        # 2. 最低价 > T日最高价
        if signal_two['low'] <= signal_one['high']:
            return False

        # 3. 成交额 ≥ 前1日成交额的倍数
        prev_amount = df.iloc[signal_two_idx - 1]['amount']
        if prev_amount <= 0 or signal_two['amount'] < prev_amount * self.signal_two_volume_ratio:
            return False

        return True
    
    def check_signal_three(self, df: pd.DataFrame, signal_one_idx: int, end_idx: int) -> bool:
        """
        检查信号三：信号一之后到end_idx，所有交易日最低价 > 信号一最高价
        """
        signal_one_high = df.iloc[signal_one_idx]['high']
        
        # 从信号二开始到end_idx（不包括end_idx本身）
        for i in range(signal_one_idx + 1, end_idx):
            if i >= len(df):
                break
            if df.iloc[i]['low'] <= signal_one_high:
                return False
        
        return True
    
    def find_signal_four(self, df: pd.DataFrame, signal_two_idx: int) -> Optional[int]:
        """
        寻找信号四：出现地量日（T日），成交额 < T日前1日成交额的0.5倍
        
        Returns:
            地量日的索引，或None
        """
        # 从信号二后一天开始找
        for i in range(signal_two_idx + 1, len(df)):
            current_amount = df.iloc[i]['amount']
            prev_amount = df.iloc[i - 1]['amount']

            if prev_amount > 0 and current_amount < prev_amount * self.signal_four_volume_ratio:
                return i
        
        return None
    
    def find_signal_five(self, df: pd.DataFrame, signal_four_idx: int, signal_one_idx: int) -> Optional[int]:
        """
        寻找信号五：T日之后出现启动信号
        - 单日收涨
        - 成交额 ≥ 前1日成交额 × 2
        - Y日最高价创T日以来新高

        Args:
            signal_four_idx: 地量日索引
            signal_one_idx: T日（涨停日）索引

        Returns:
            启动日的索引，或None
        """
        # 从地量日后一天开始找
        for i in range(signal_four_idx + 1, len(df)):
            row = df.iloc[i]

            # 1. 单日收涨
            if row['pct_change'] <= 0:
                continue

            # 2. 成交额 ≥ 前1日成交额的倍数
            prev_amount = df.iloc[i - 1]['amount']
            if prev_amount <= 0 or row['amount'] < prev_amount * self.signal_five_volume_ratio:
                continue

            # 3. Y日最高价创T日以来新高
            # 获取从T日到Y日的所有最高价
            period_highs = df.iloc[signal_one_idx:i + 1]['high']
            max_high = period_highs.max()

            if row['high'] < max_high:
                continue

            return i

        return None
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.limit_days + self.history_buffer_days)
        if df is None or len(df) < self.min_history_days:
            return None
        
        # 确保数据按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 找信号一（涨停日）
        for i in range(len(df) - 1, 0, -1):
            # 检查信号一
            if not self.check_signal_one(df, i):
                continue
            
            signal_one_idx = i
            
            # 检查是否在34天范围内
            latest_date = df.iloc[-1]['trade_date']
            signal_one_date = df.iloc[signal_one_idx]['trade_date']
            days_since = (latest_date - signal_one_date).days
            
            if days_since > self.limit_days:
                continue
            
            # 检查信号二（次日）
            if not self.check_signal_two(df, signal_one_idx):
                continue
            
            signal_two_idx = signal_one_idx + 1
            
            # 找信号四（地量日）
            signal_four_idx = self.find_signal_four(df, signal_two_idx)
            if signal_four_idx is None:
                continue

            # 找信号五（启动日）
            signal_five_idx = self.find_signal_five(df, signal_four_idx, signal_one_idx)
            if signal_five_idx is None:
                continue

            # 检查信号三（信号一之后到信号五，所有最低价 > 信号一最高价）
            if not self.check_signal_three(df, signal_one_idx, signal_five_idx):
                continue
            
            # 五个信号都满足，输出结果
            signal_one = df.iloc[signal_one_idx]
            signal_two = df.iloc[signal_two_idx]
            signal_four = df.iloc[signal_four_idx]
            signal_five = df.iloc[signal_five_idx]
            
            return {
                'code': code,
                'name': name,
                'signal_one_date': signal_one_date.strftime('%Y-%m-%d'),
                'signal_two_date': signal_two['trade_date'].strftime('%Y-%m-%d'),
                'signal_four_date': signal_four['trade_date'].strftime('%Y-%m-%d'),
                'signal_five_date': signal_five['trade_date'].strftime('%Y-%m-%d'),
                'days_to_launch': signal_five_idx - signal_one_idx,
                
                # 信号一特征
                's1_open': round(signal_one['open'], 2),
                's1_close': round(signal_one['close'], 2),
                's1_high': round(signal_one['high'], 2),
                's1_low': round(signal_one['low'], 2),
                's1_amount': round(signal_one['amount'] / 10000, 2),
                's1_prev_amount': round(df.iloc[signal_one_idx - 1]['amount'] / 10000, 2),
                's1_amount_ratio': round(signal_one['amount'] / df.iloc[signal_one_idx - 1]['amount'], 2),
                
                # 信号二特征
                's2_open': round(signal_two['open'], 2),
                's2_close': round(signal_two['close'], 2),
                's2_amount': round(signal_two['amount'] / 10000, 2),
                's2_amount_ratio': round(signal_two['amount'] / signal_one['amount'], 2),
                
                # 信号四特征
                's4_amount': round(signal_four['amount'] / 10000, 2),
                's4_prev_amount': round(df.iloc[signal_four_idx - 1]['amount'] / 10000, 2),
                's4_shrink_ratio': round(signal_four['amount'] / df.iloc[signal_four_idx - 1]['amount'], 2),
                
                # 信号五特征
                's5_close': round(signal_five['close'], 2),
                's5_pct_change': round(signal_five['pct_change'], 2),
                's5_amount': round(signal_five['amount'] / 10000, 2),
                's5_prev_amount': round(df.iloc[signal_five_idx - 1]['amount'] / 10000, 2),
                's5_amount_ratio': round(signal_five['amount'] / df.iloc[signal_five_idx - 1]['amount'], 2),
                
                'all_signals_confirmed': True
            }
        
        return None
    
    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True) -> List[Dict]:
        """运行筛选"""
        if date_str:
            self.current_date = date_str
        
        # 检查数据是否可用
        
        logger.info("="*60)
        logger.info("涨停金凤凰筛选器 V2 - Jin Feng Huang Screener")
        logger.info(f"时间范围: 最近{self.limit_days}个交易日")
        logger.info("筛选条件:")
        logger.info("  信号一: 非一字板涨停，成交额≥前1日2倍")
        logger.info("  信号二: 次日高开收阳，成交额≥信号一2倍")
        logger.info("  信号三: 最低价始终>信号一最高价")
        logger.info("  信号四: 地量，成交额<前1日0.5倍")
        logger.info("  信号五: 启动，收涨+成交额翻倍")
        logger.info("="*60)
        
        # 获取股票列表（排除北交所等）
        stocks = self.get_all_stocks()
        stocks = [
            s for s in stocks
            if not s.code.startswith('8')
            and not s.code.startswith('4')
        ]
        
        total_stocks = len(stocks)
        logger.info(f"Total stocks: {total_stocks}")
        
        # 检查进度跟踪
        start_idx = 0
        if self.progress_tracker and not force_restart:
            if self.progress_tracker.is_resumable():
                processed_codes = self.progress_tracker.get_processed_codes()
                start_idx = len(processed_codes)
                logger.info(f"Resuming from stock {start_idx}")
            else:
                self.progress_tracker.reset()
        
        if self.progress_tracker:
            self.progress_tracker.start(
                total_stocks=total_stocks,
                metadata={'date': date_str or self.current_date, 'screener': self.screener_name}
            )
        
        results = []
        analysis_data = {}
        
        for i, stock in enumerate(stocks[start_idx:], start=start_idx):
            try:
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(
                        processed=i+1,
                        matched=len(results),
                        current_code=stock.code
                    )
                
                result = self.screen_stock(stock.code, stock.name)
                
                if result:
                    results.append(result)
                    
                    if enable_analysis and self.news_fetcher:
                        news = self.fetch_news(stock.code)
                        price_data = {
                            'close': result['s5_close'],
                            'pct_change': result['s5_pct_change'],
                            'turnover': 0
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"涨停:{result['signal_one_date']}, "
                                   f"启动:{result['signal_five_date']}, "
                                   f"行业:{analysis.get('行业分类', 'N/A')}")
                    else:
                        logger.info(f"✓ Found: {stock.code} {stock.name} - "
                                   f"涨停:{result['signal_one_date']}, "
                                   f"启动:{result['signal_five_date']}")
                
                if (i + 1) % 500 == 0:
                    logger.info(f"Progress: {i+1}/{total_stocks}, Found: {len(results)}")
                    
            except Exception as e:
                logger.error(f"Error screening {stock.code}: {e}")
                continue
        
        if self.progress_tracker:
            self.progress_tracker.complete(success=True)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"筛选完成!")
        logger.info(f"检查: {total_stocks} 只股票")
        logger.info(f"匹配: {len(results)} 只股票")
        logger.info(f"{'='*60}")
        
        return results
    
    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict[str, Dict]] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'signal_one_date': '涨停日期',
            'signal_two_date': '次日高开日期',
            'signal_four_date': '地量日期',
            'signal_five_date': '启动日期',
            'days_to_launch': '涨停到启动天数',
            's1_amount': '涨停成交额(万)',
            's1_prev_amount': '涨停前日成交额(万)',
            's1_amount_ratio': '涨停成交额倍数',
            's2_amount': '次日成交额(万)',
            's2_amount_ratio': '次日/涨停成交额',
            's4_shrink_ratio': '地量缩量比例',
            's5_pct_change': '启动日涨幅%',
            's5_amount_ratio': '启动日成交额环比',
            'all_signals_confirmed': '五信号确认'
        }
        
        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='涨停金凤凰筛选器 V2')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='时间范围（交易日）')
    parser.add_argument('--no-news', action='store_true', help='禁用新闻抓取')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM分析')
    parser.add_argument('--no-progress', action='store_true', help='禁用进度跟踪')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    screener = JinFengHuangScreener(
        limit_days=args.limit_days,
        db_path=args.db_path,
        enable_news=not args.no_news,
        enable_llm=not args.no_llm,
        enable_progress=not args.no_progress
    )
    
    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=not args.no_llm
    )
    
    # Handle different return formats
    if result is None:
        results, analysis_data = [], {}
    elif isinstance(result, tuple) and len(result) == 2:
        results, analysis_data = result
    else:
        results, analysis_data = result, {}
    
    if results:
        output_path = screener.save_results(results, analysis_data)
        print(f"\n结果已保存至: {output_path}")
        
        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)
        for r in results:
            analysis = analysis_data.get(r['code'], {})
            industry = analysis.get('行业分类', 'N/A')
            print(f"{r['code']} {r['name']} [{industry}]: "
                  f"涨停{r['signal_one_date']}, 启动{r['signal_five_date']}, "
                  f"涨停成交{r['s1_amount']:.0f}万({r['s1_amount_ratio']:.1f}x), "
                  f"次日成交{r['s2_amount']:.0f}万({r['s2_amount_ratio']:.1f}x)")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'jin_feng_huang_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        from config import FLASK_PORT as _PORT
        print(f"  Excel: http://localhost:{_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
