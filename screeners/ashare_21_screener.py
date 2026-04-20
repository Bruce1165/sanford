import os
#!/usr/bin/env python3
"""
A股2.1型筛选推荐 - AShare21Screener

策略框架：20天主观多头 + 突破主升
数据模式：T+1盘后筛选，次日执行

核心逻辑：
1. 多策略并行（突破+低吸+量价）
2. 统一评分体系
3. 输出次日执行清单

筛选维度：
- 突破质量（结构+量能+K线）
- 趋势强度（均线+相对强弱）
- 资金活跃度（换手+量能）
- 行业/板块因素
- 大盘环境适配

输出：
- 候选股票池（按综合评分排序）
- 每个股票的策略标签
- 建议仓位和止损位
- 次日执行要点
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import argparse
import json

from base_screener import BaseScreener

logger = logging.getLogger(__name__)

# 策略参数
LOOKBACK_DAYS = 20  # 分析周期
MIN_SCORE = 60  # 最低综合评分


class AShare21Screener(BaseScreener):
    """A股2.1型筛选推荐器"""
    
    def __init__(self,
                 lookback_days: int = LOOKBACK_DAYS,
                 min_score: int = MIN_SCORE,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,  # 2.1策略暂不需要新闻
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='ashare_21',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.lookback_days = lookback_days
        self.min_score = min_score
        self.index_data = None
        self.industry_data = None

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'LOOKBACK_DAYS': {
                'type': 'int',
                'default': 20,
                'min': 5,
                'max': 60,
                'display_name': '分析周期（交易日）',
                'description': '回溯分析的历史数据天数',
                'group': '基础设置'
            },
            'MIN_SCORE': {
                'type': 'int',
                'default': 60,
                'min': 0,
                'max': 100,
                'display_name': '最低综合评分',
                'description': '股票必须达到的最低综合评分（0-100）',
                'group': '评分条件'
            }
        }
    
    def load_market_context(self, date_str: str):
        """加载市场环境数据（大盘、行业）"""
        import sqlite3
        conn = sqlite3.connect(str(self._db_path))
        
        # 尝试加载指数数据（表可能不存在）
        try:
            cursor = conn.execute('''
                SELECT code, index_name, close, pct_change
                FROM index_prices
                WHERE trade_date = ?
                ORDER BY code
            ''', (date_str,))
            self.index_data = {row[1]: {'close': row[2], 'change': row[3]} 
                              for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            # index_prices表不存在，跳过
            self.index_data = {}
            logger.warning("  index_prices表不存在，跳过大盘指数数据")
        
        # 加载行业数据（计算行业平均涨幅）
        try:
            cursor = conn.execute('''
                SELECT s.industry, AVG(d.pct_change) as avg_change,
                       COUNT(*) as stock_count
                FROM daily_prices d
                JOIN stocks s ON d.code = s.code
                WHERE d.trade_date = ? AND s.industry IS NOT NULL
                GROUP BY s.industry
                HAVING COUNT(*) >= 5
                ORDER BY avg_change DESC
            ''', (date_str,))
            self.industry_data = {row[0]: {'avg_change': row[1], 'count': row[2]}
                                 for row in cursor.fetchall()}
        except Exception as e:
            logger.warning(f"  加载行业数据失败: {e}")
            self.industry_data = {}
        
        conn.close()
        
        logger.info("市场环境:")
        if self.index_data:
            for name, data in list(self.index_data.items())[:3]:
                logger.info(f"  {name}: {data['change']:+.2f}%")
        else:
            logger.info("  指数数据: 无")
        if self.industry_data:
            top3 = list(self.industry_data.items())[:3]
            top3_str = ', '.join([f"{k}({v['avg_change']:+.1f}%)" for k, v in top3])
            logger.info(f"  领涨行业: {top3_str}")
        else:
            logger.info("  行业数据: 无")
    
    def calculate_breakout_score(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """
        计算突破质量评分（0-25分）
        
        评分维度：
        - 横盘整理质量（0-8分）
        - 突破力度（0-8分）
        - 量能配合（0-5分）
        - K线形态（0-4分）
        """
        if len(df) < 10:
            return 0, {}
        
        latest = df.iloc[-1]
        
        # 1. 横盘整理质量（最近7-10天）
        consolidation_period = df.iloc[-10:-3]
        if len(consolidation_period) < 5:
            return 0, {}
        
        consolidation_high = consolidation_period['high'].max()
        consolidation_low = consolidation_period['low'].min()
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
        
        # 波动小 = 整理充分（满分8分）
        if consolidation_range < 0.05:
            consolidation_score = 8
        elif consolidation_range < 0.08:
            consolidation_score = 6
        elif consolidation_range < 0.12:
            consolidation_score = 4
        else:
            consolidation_score = 2
        
        # 2. 突破力度
        breakout_pct = (latest['close'] - consolidation_high) / consolidation_high * 100
        if breakout_pct > 5:
            breakout_score = 8
        elif breakout_pct > 3:
            breakout_score = 6
        elif breakout_pct > 1:
            breakout_score = 4
        else:
            breakout_score = 0
        
        # 3. 量能配合
        avg_volume = df.iloc[-10:-1]['volume'].mean()
        volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 0
        
        if 1.5 <= volume_ratio <= 3:
            volume_score = 5
        elif 1.2 <= volume_ratio < 1.5:
            volume_score = 3
        elif volume_ratio > 3:
            volume_score = 2  # 暴量扣分
        else:
            volume_score = 1
        
        # 4. K线形态
        body_pct = abs(latest['close'] - latest['open']) / latest['open'] * 100
        upper_shadow = (latest['high'] - max(latest['close'], latest['open'])) / latest['open'] * 100
        
        if body_pct > 3 and upper_shadow < 1:
            kline_score = 4  # 实体饱满，上影线短
        elif body_pct > 2 and upper_shadow < 2:
            kline_score = 3
        elif body_pct > 1:
            kline_score = 2
        else:
            kline_score = 1
        
        total_score = consolidation_score + breakout_score + volume_score + kline_score
        
        details = {
            'consolidation_score': consolidation_score,
            'breakout_score': breakout_score,
            'volume_score': volume_score,
            'kline_score': kline_score,
            'consolidation_range': round(consolidation_range * 100, 2),
            'breakout_pct': round(breakout_pct, 2),
            'volume_ratio': round(volume_ratio, 2),
            'body_pct': round(body_pct, 2),
            'upper_shadow': round(upper_shadow, 2)
        }
        
        return total_score, details
    
    def calculate_trend_score(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """
        计算趋势强度评分（0-20分）
        """
        if len(df) < 20:
            return 0, {}
        
        # 均线排列
        ma5 = df.iloc[-5:]['close'].mean()
        ma10 = df.iloc[-10:]['close'].mean()
        ma20 = df.iloc[-20:]['close'].mean()
        
        ma_score = 0
        if ma5 > ma10 > ma20:
            ma_score = 8  # 多头排列
        elif ma5 > ma10:
            ma_score = 5
        elif ma10 > ma20:
            ma_score = 3
        else:
            ma_score = 1
        
        # 20日涨跌幅
        return_20d = (df.iloc[-1]['close'] - df.iloc[-20]['close']) / df.iloc[-20]['close'] * 100
        if return_20d > 15:
            return_score = 6
        elif return_20d > 5:
            return_score = 4
        elif return_20d > -5:
            return_score = 2
        else:
            return_score = 0
        
        # 波动率（适中最好）
        volatility = df.iloc[-20:]['pct_change'].std()
        if 2 <= volatility <= 4:
            vol_score = 6
        elif 1 <= volatility < 2:
            vol_score = 4
        elif 4 < volatility <= 6:
            vol_score = 3
        else:
            vol_score = 2
        
        total_score = ma_score + return_score + vol_score
        
        details = {
            'ma_score': ma_score,
            'return_score': return_score,
            'volatility_score': vol_score,
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'return_20d': round(return_20d, 2),
            'volatility': round(volatility, 2)
        }
        
        return total_score, details
    
    def calculate_momentum_score(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """
        计算资金活跃度评分（0-15分）
        """
        latest = df.iloc[-1]
        
        # 换手率
        turnover = latest.get('turnover', 0) or 0
        if turnover >= 10:
            turnover_score = 5
        elif turnover >= 5:
            turnover_score = 4
        elif turnover >= 3:
            turnover_score = 3
        elif turnover >= 1:
            turnover_score = 2
        else:
            turnover_score = 1
        
        # 量能趋势（最近3天 vs 前3天）
        recent_vol = df.iloc[-3:]['volume'].mean()
        prev_vol = df.iloc[-6:-3]['volume'].mean()
        vol_trend = recent_vol / prev_vol if prev_vol > 0 else 1
        
        if vol_trend >= 1.5:
            vol_trend_score = 5
        elif vol_trend >= 1.2:
            vol_trend_score = 4
        elif vol_trend >= 1:
            vol_trend_score = 3
        else:
            vol_trend_score = 1
        
        # 价格动量（5日涨幅）
        return_5d = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close'] * 100
        if return_5d > 10:
            momentum_score = 5
        elif return_5d > 5:
            momentum_score = 4
        elif return_5d > 0:
            momentum_score = 3
        elif return_5d > -5:
            momentum_score = 2
        else:
            momentum_score = 1
        
        total_score = turnover_score + vol_trend_score + momentum_score
        
        details = {
            'turnover_score': turnover_score,
            'vol_trend_score': vol_trend_score,
            'momentum_score': momentum_score,
            'turnover': round(turnover, 2),
            'vol_trend': round(vol_trend, 2),
            'return_5d': round(return_5d, 2)
        }
        
        return total_score, details
    
    def calculate_environment_score(self, code: str, industry: str) -> Tuple[float, Dict]:
        """
        计算市场环境评分（0-10分）
        """
        score = 5  # 基础分
        details = {'market_bias': 'neutral'}
        
        if not self.index_data or not self.industry_data:
            return score, details
        
        # 大盘环境
        sh_change = self.index_data.get('上证指数', {}).get('change', 0)
        if sh_change > 1:
            score += 2
            details['market_bias'] = 'strong'
        elif sh_change > 0:
            score += 1
            details['market_bias'] = 'positive'
        elif sh_change > -1:
            score -= 1
            details['market_bias'] = 'weak'
        else:
            score -= 2
            details['market_bias'] = 'bearish'
        
        # 行业强度
        if industry and industry in self.industry_data:
            ind_change = self.industry_data[industry]['avg_change']
            ind_rank = list(self.industry_data.keys()).index(industry) + 1
            
            if ind_rank <= 10:  # 前10行业
                score += 3
                details['industry_rank'] = f'Top{ind_rank}'
            elif ind_rank <= 30:
                score += 2
                details['industry_rank'] = f'Top{ind_rank}'
            elif ind_change > 0:
                score += 1
                details['industry_rank'] = f'Rank{ind_rank}'
            else:
                details['industry_rank'] = f'Weak({ind_rank})'
        
        return min(max(score, 0), 10), details
    
    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票，计算综合评分"""
        df = self.get_stock_data(code, days=self.lookback_days + 5)
        if df is None or len(df) < self.lookback_days:
            return None
        
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 获取行业信息
        industry = ''
        try:
            conn = self.get_db_connection()
            cursor = conn.execute('SELECT industry FROM stocks WHERE code = ?', (code,))
            row = cursor.fetchone()
            if row:
                industry = row[0] or ''
            conn.close()
        except Exception as e:
            logger.debug(f"获取行业信息失败 {code}: {e}")
        
        # 计算各项评分
        breakout_score, breakout_details = self.calculate_breakout_score(df)
        trend_score, trend_details = self.calculate_trend_score(df)
        momentum_score, momentum_details = self.calculate_momentum_score(df)
        env_score, env_details = self.calculate_environment_score(code, industry)
        
        # 综合评分
        total_score = breakout_score + trend_score + momentum_score + env_score
        
        if total_score < self.min_score:
            return None
        
        latest = df.iloc[-1]
        
        # 确定策略标签
        strategies = []
        if breakout_score >= 18:
            strategies.append('突破主升')
        if trend_score >= 15 and momentum_score >= 10:
            strategies.append('趋势延续')
        if momentum_score >= 12:
            strategies.append('量价爆发')
        if not strategies:
            strategies.append('综合评分')
        
        # 建议仓位（基于评分）
        if total_score >= 85:
            suggested_position = '15-20%'
        elif total_score >= 75:
            suggested_position = '10-15%'
        elif total_score >= 65:
            suggested_position = '5-10%'
        else:
            suggested_position = '观察'
        
        # 计算止损位
        stop_loss = df.iloc[-5:]['low'].min()  # 最近5日最低价
        
        return {
            'code': code,
            'name': name,
            'industry': industry,
            'close': round(latest['close'], 2),
            'pct_change': round(latest['pct_change'], 2),
            'turnover': round(latest.get('turnover', 0) or 0, 2),
            
            # 综合评分
            'total_score': total_score,
            'breakout_score': breakout_score,
            'trend_score': trend_score,
            'momentum_score': momentum_score,
            'environment_score': env_score,
            
            # 策略标签
            'strategies': ','.join(strategies),
            'suggested_position': suggested_position,
            'stop_loss': round(stop_loss, 2),
            
            # 详细指标
            'breakout_details': json.dumps(breakout_details, ensure_ascii=False),
            'trend_details': json.dumps(trend_details, ensure_ascii=False),
            'momentum_details': json.dumps(momentum_details, ensure_ascii=False),
            'environment_details': json.dumps(env_details, ensure_ascii=False),
            
            # 次日执行要点
            'entry_price': f"≤{round(latest['close'] * 1.01, 2)}",
            'target_1': round(latest['close'] * 1.08, 2),
            'target_2': round(latest['close'] * 1.15, 2),
            'max_hold_days': 10
        }
    
    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False) -> List[Dict]:
        """运行2.1筛选"""
        if date_str is None:
            date_str = self.current_date
        
        self.current_date = date_str
        
        # 检查数据是否可用
        if not self.check_data_availability(self.current_date):
            logger.warning(f"⚠️  无可用数据 ({self.current_date}) - 市场尚未收盘或数据未下载")
            return []
        
        logger.info("="*60)
        logger.info("A股2.1型筛选推荐")
        logger.info(f"分析日期: {date_str}")
        logger.info(f"评分门槛: {self.min_score}分")
        logger.info("="*60)
        
        # 加载市场环境
        self.load_market_context(date_str)
        
        # 获取股票列表
        stocks = self.get_all_stocks()
        stocks = [s for s in stocks if not s.code.startswith(('8', '4'))]
        
        total_stocks = len(stocks)
        logger.info(f"总股票数: {total_stocks}")
        
        # 进度跟踪
        if self.progress_tracker:
            self.progress_tracker.start(total_stocks=total_stocks)
        
        results = []
        for i, stock in enumerate(stocks):
            try:
                if self.progress_tracker and i % 100 == 0:
                    self.progress_tracker.update(processed=i+1, matched=len(results))
                
                result = self.screen_stock(stock.code, stock.name)
                if result:
                    results.append(result)
                    logger.info(f"✓ {stock.code} {stock.name}: {result['total_score']}分")
                
            except Exception as e:
                logger.error(f"Error {stock.code}: {e}")
        
        if self.progress_tracker:
            self.progress_tracker.complete(success=True)
        
        # 按评分排序
        results.sort(key=lambda x: x['total_score'], reverse=True)
        
        logger.info(f"\n筛选完成: {len(results)} 只候选股")
        
        return results
    
    def save_results(self, results: List[Dict]) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'industry': '所属行业',
            'close': '收盘价',
            'pct_change': '涨幅%',
            'turnover': '换手率%',
            'total_score': '综合评分',
            'breakout_score': '突破评分',
            'trend_score': '趋势评分',
            'momentum_score': '动量评分',
            'environment_score': '环境评分',
            'strategies': '策略标签',
            'suggested_position': '建议仓位',
            'stop_loss': '止损位',
            'entry_price': '入场价',
            'target_1': '目标1(+8%)',
            'target_2': '目标2(+15%)',
            'max_hold_days': '最长持有天数'
        }
        
        return super().save_results(results, None, "", column_mapping)


def main():
    parser = argparse.ArgumentParser(description='A股2.1型筛选推荐')
    parser.add_argument('--date', type=str, help='分析日期 (YYYY-MM-DD)')
    parser.add_argument('--min-score', type=int, default=MIN_SCORE, help='最低评分')
    parser.add_argument('--lookback', type=int, default=LOOKBACK_DAYS, help='回看天数')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    screener = AShare21Screener(
        lookback_days=args.lookback,
        min_score=args.min_score
    )
    
    results = screener.run_screening(date_str=args.date, force_restart=args.restart)
    
    if results:
        output_path = screener.save_results(results)
        print(f"\n结果已保存: {output_path}")
        print(f"\n前10名:")
        for r in results[:10]:
            print(f"{r['code']} {r['name']}: {r['total_score']}分 | "
                  f"{r['strategies']} | 仓位{r['suggested_position']}")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'ashare_21_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        from config import FLASK_PORT as _PORT
        print(f"  Excel: http://localhost:{_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n无符合条件的股票")


if __name__ == '__main__':
    main()
