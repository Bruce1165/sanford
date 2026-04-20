#!/usr/bin/env python3
from __future__ import annotations
"""
突破主升筛选器 - Breakout Main Screener (真突破策略)

策略来源：20天主观多头 - 突破策略实战版
核心逻辑：只做真突破，过滤假突破，做主升惯性

入场条件（必须全满足）：
1. 结构：横盘箱体 ≥ 7天，突破前高/箱体上沿
2. 量能：突破日成交量 = 1.5~2倍5日均量（<3倍防暴量）
3. K线：收盘站稳突破位上方，中阳/大阳（实体饱满）
4. 过滤假突破：无上影线或上影线短（<实体1/3）

出场规则（记录到输出）：
- 止损位：突破位/大阳线开盘价
- 目标1：+8~12%
- 目标2：+15~20%
- 时间止：10天不达标减半，20天强制清

假突破过滤（出现任意一条排除）：
- 长上影（上影线 > 实体1/3）
- 暴量（>3倍5日均量）
- 尾盘回落（收盘 < 最高价×0.97）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging
import argparse

from base_screener import BaseScreener
from config import FLASK_PORT

logger = logging.getLogger(__name__)

LIMIT_DAYS = 34  # 回看周期
MIN_CONSOLIDATION_DAYS = 7  # 最小横盘天数


class BreakoutMainScreener(BaseScreener):
    """突破主升筛选器（真突破策略）"""

    def __init__(self,
                 limit_days: int = LIMIT_DAYS,
                 min_consolidation_days: int = MIN_CONSOLIDATION_DAYS,
                 volume_breakout_min: float = 1.5,
                 volume_breakout_max: float = 2.0,
                 volume_fake_threshold: float = 3.0,
                 max_upper_shadow_ratio: float = 0.33,
                 min_body_pct: float = 3.0,
                 consolidation_max_range: float = 0.15,
                 breakout_min_pct: float = 0.01,
                 close_high_min_ratio: float = 0.97,
                 db_path: str = "data/stock_data.db",
                 enable_news: bool = False,
                 enable_llm: bool = False,
                 enable_progress: bool = True):
        super().__init__(
            screener_name='breakout_main',
            db_path=db_path,
            enable_news=enable_news,
            enable_llm=enable_llm,
            enable_progress=enable_progress
        )
        self.limit_days = limit_days
        self.min_consolidation_days = min_consolidation_days
        self.volume_breakout_min = volume_breakout_min
        self.volume_breakout_max = volume_breakout_max
        self.volume_fake_threshold = volume_fake_threshold
        self.max_upper_shadow_ratio = max_upper_shadow_ratio
        self.min_body_pct = min_body_pct
        self.consolidation_max_range = consolidation_max_range
        self.breakout_min_pct = breakout_min_pct
        self.close_high_min_ratio = close_high_min_ratio

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'LIMIT_DAYS': {
                'type': 'int',
                'default': 34,
                'min': 20,
                'max': 60,
                'display_name': '时间范围（交易日）',
                'description': '筛选最近多少个交易日内的信号',
                'group': '基础设置'
            },
            'MIN_CONSOLIDATION_DAYS': {
                'type': 'int',
                'default': 7,
                'min': 5,
                'max': 20,
                'display_name': '最小横盘天数',
                'description': '横盘整理至少需要的天数',
                'group': '基础设置'
            },
            'VOLUME_BREAKOUT_MIN': {
                'type': 'float',
                'default': 1.5,
                'min': 1.2,
                'max': 2.0,
                'step': 0.1,
                'display_name': '最小放量倍数',
                'description': '突破日成交量需要达到5日均量的最小倍数',
                'group': '量能条件'
            },
            'VOLUME_BREAKOUT_MAX': {
                'type': 'float',
                'default': 2.0,
                'min': 1.5,
                'max': 2.5,
                'step': 0.1,
                'display_name': '最大放量倍数',
                'description': '突破日成交量相对于5日均量的最大倍数（防暴量）',
                'group': '量能条件'
            },
            'VOLUME_FAKE_THRESHOLD': {
                'type': 'float',
                'default': 3.0,
                'min': 2.5,
                'max': 4.0,
                'step': 0.1,
                'display_name': '暴量阈值',
                'description': '超过此倍数认为是假突破',
                'group': '假突破过滤'
            },
            'MAX_UPPER_SHADOW_RATIO': {
                'type': 'float',
                'default': 0.33,
                'min': 0.2,
                'max': 0.5,
                'step': 0.01,
                'display_name': '最大上影线比例',
                'description': '上影线长度相对于实体的最大比例',
                'group': '形态条件'
            },
            'MIN_BODY_PCT': {
                'type': 'float',
                'default': 3.0,
                'min': 2.0,
                'max': 5.0,
                'step': 0.5,
                'display_name': '最小阳线实体涨幅（%）',
                'description': '突破日阳线实体的最小涨幅',
                'group': '形态条件'
            },
            'CONSOLIDATION_MAX_RANGE': {
                'type': 'float',
                'default': 0.15,
                'min': 0.10,
                'max': 0.25,
                'step': 0.01,
                'display_name': '横盘最大波动幅度',
                'description': '横盘期波动幅度上限（确认是横盘不是趋势）',
                'group': '结构条件'
            },
            'BREAKOUT_MIN_PCT': {
                'type': 'float',
                'default': 0.01,
                'min': 0.005,
                'max': 0.03,
                'step': 0.005,
                'display_name': '最小突破幅度',
                'description': '突破箱体上沿的最小幅度',
                'group': '结构条件'
            },
            'CLOSE_HIGH_MIN_RATIO': {
                'type': 'float',
                'default': 0.97,
                'min': 0.95,
                'max': 0.99,
                'step': 0.01,
                'display_name': '收盘价/最高价最小比例',
                'description': '收盘价相对于最高价的最小比例（防尾盘回落）',
                'group': '假突破过滤'
            }
        }

    def find_consolidation_and_breakout(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        寻找横盘整理后的真突破

        Returns:
            突破信息或None
        """
        if len(df) < self.min_consolidation_days + 5:
            return None

        # 从后往前找突破点
        for i in range(len(df) - 1, self.min_consolidation_days, -1):
            latest = df.iloc[i]

            # 检查涨幅（中阳/大阳）
            if latest['pct_change'] < self.min_body_pct:
                continue

            # 检查阳线
            if latest['close'] <= latest['open']:
                continue

            # 获取横盘期数据
            consolidation_period = df.iloc[i-self.min_consolidation_days:i]

            if len(consolidation_period) < self.min_consolidation_days:
                continue

            # 计算箱体上沿（横盘期最高价）
            consolidation_high = consolidation_period['high'].max()
            consolidation_low = consolidation_period['low'].min()

            # 检查是否突破箱体上沿（突破指定幅度以上）
            if latest['close'] <= consolidation_high * (1 + self.breakout_min_pct):
                continue

            # 检查横盘期波动幅度（确认是横盘不是趋势）
            consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
            if consolidation_range > self.consolidation_max_range:
                continue

            # 计算成交量条件
            avg_volume_5 = df.iloc[i-5:i]['volume'].mean()
            volume_ratio = latest['volume'] / avg_volume_5 if avg_volume_5 > 0 else 0

            # 检查放量倍数
            if not (self.volume_breakout_min <= volume_ratio <= self.volume_breakout_max):
                continue

            # 检查假突破：暴量过滤
            if volume_ratio > self.volume_fake_threshold:
                continue

            # 检查K线形态：上影线不能太长
            body_length = latest['close'] - latest['open']
            upper_shadow = latest['high'] - latest['close']

            if body_length <= 0:
                continue

            upper_shadow_ratio = upper_shadow / body_length if body_length > 0 else 999
            if upper_shadow_ratio > self.max_upper_shadow_ratio:
                continue  # 长上影，可能是假突破

            # 检查尾盘回落（收盘不应离最高价太远）
            if latest['close'] < latest['high'] * self.close_high_min_ratio:
                continue  # 尾盘回落，可能是假突破

            # 计算突破质量
            breakout_quality = (latest['close'] - consolidation_high) / consolidation_high * 100

            # 计算止损位和目标位
            stop_loss = consolidation_high  # 跌破箱体上沿止损
            target_1 = latest['close'] * 1.10  # +10%
            target_2 = latest['close'] * 1.18  # +18%

            return {
                'consolidation_high': round(consolidation_high, 2),
                'consolidation_low': round(consolidation_low, 2),
                'consolidation_range_pct': round(consolidation_range * 100, 2),
                'breakout_price': round(latest['close'], 2),
                'breakout_high': round(latest['high'], 2),
                'breakout_low': round(latest['low'], 2),
                'breakout_pct': round(latest['pct_change'], 2),
                'body_length': round(body_length, 2),
                'upper_shadow_ratio': round(upper_shadow_ratio, 2),
                'volume_ratio': round(volume_ratio, 2),
                'avg_volume_5': int(avg_volume_5),
                'breakout_quality': round(breakout_quality, 2),
                'consolidation_days': self.min_consolidation_days,
                'stop_loss': round(stop_loss, 2),
                'target_1': round(target_1, 2),
                'target_2': round(target_2, 2),
                'is_true_breakout': True
            }

        return None

    def check_ma_trend(self, df: pd.DataFrame) -> Dict:
        """检查均线趋势"""
        if len(df) < 20:
            return {'ma5': 0, 'ma10': 0, 'ma20': 0, 'trend': 'unknown'}

        ma5 = df.iloc[-5:]['close'].mean()
        ma10 = df.iloc[-10:]['close'].mean()
        ma20 = df.iloc[-20:]['close'].mean()

        # 判断趋势
        if ma5 > ma10 > ma20:
            trend = 'bullish'
        elif ma5 < ma10 < ma20:
            trend = 'bearish'
        else:
            trend = 'mixed'

        return {
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'trend': trend
        }

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """筛选单只股票"""
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None or len(df) < self.limit_days:
            return None

        # 确保数据按日期排序
        df = df.sort_values('trade_date').reset_index(drop=True)

        # 寻找真突破
        breakout_info = self.find_consolidation_and_breakout(df)
        if breakout_info is None:
            return None

        # 检查均线趋势（排除空头排列）
        ma_info = self.check_ma_trend(df)
        if ma_info['trend'] == 'bearish':
            return None

        latest = df.iloc[-1]

        return {
            'code': code,
            'name': name,
            'close': round(breakout_info['breakout_price'], 2),
            'current_price': round(breakout_info['breakout_price'], 2),
            'pct_change': breakout_info['breakout_pct'],
            'turnover': round(latest.get('turnover', 0) or 0, 2),
            'consolidation_high': breakout_info['consolidation_high'],
            'consolidation_low': breakout_info['consolidation_low'],
            'consolidation_range_pct': breakout_info['consolidation_range_pct'],
            'breakout_high': breakout_info['breakout_high'],
            'breakout_low': breakout_info['breakout_low'],
            'breakout_pct': breakout_info['breakout_pct'],
            'body_length': breakout_info['body_length'],
            'upper_shadow_ratio': breakout_info['upper_shadow_ratio'],
            'volume_ratio': breakout_info['volume_ratio'],
            'avg_volume_5': breakout_info['avg_volume_5'],
            'breakout_quality': breakout_info['breakout_quality'],
            'consolidation_days': breakout_info['consolidation_days'],
            'stop_loss': breakout_info['stop_loss'],
            'target_1': breakout_info['target_1'],
            'target_2': breakout_info['target_2'],
            'is_true_breakout': breakout_info['is_true_breakout'],
            'ma5': ma_info['ma5'],
            'ma10': ma_info['ma10'],
            'ma20': ma_info['ma20'],
            'ma_trend': ma_info['trend']
        }

    def check_single_stock(self, code: str, date_str: Optional[str] = None) -> Dict:
        """
        详细检查单个股票是否符合筛选条件
        返回详细的匹配信息和不符合的原因
        """
        # 设置日期
        if date_str:
            self.current_date = date_str
        else:
            self.current_date = datetime.now().strftime('%Y-%m-%d')

        reasons = []
        details = {}

        # 获取股票名称（使用 sqlite3，不依赖 SQLAlchemy）
        try:
            with self.get_conn() as conn:
                row = conn.execute(
                    "SELECT name FROM stocks WHERE code=?", (code,)
                ).fetchone()
            name = row["name"] if row else ""
        except Exception:
            name = ""

        # 获取股票数据
        df = self.get_stock_data(code, days=self.limit_days + 10)
        if df is None:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': ['无法获取股票数据（可能是退市股或数据不足）']
            }

        if len(df) < self.limit_days:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [f'历史数据不足，需要{self.limit_days}天，实际{len(df)}天']
            }

        df = df.sort_values('trade_date').reset_index(drop=True)
        latest = df.iloc[-1]

        # 检查1：涨幅（中阳/大阳）
        if latest['pct_change'] < MIN_BODY_PCT:
            reasons.append(f'涨幅不足：{latest["pct_change"]:.2f}% < {MIN_BODY_PCT}%（需要中阳/大阳）')
        else:
            details['涨幅'] = f'{latest["pct_change"]:.2f}%'

        # 检查2：阳线
        if latest['close'] <= latest['open']:
            reasons.append('K线不是阳线（收盘价必须>开盘价）')

        # 获取横盘期数据
        if len(df) < self.min_consolidation_days + 1:
            reasons.append(f'数据不足以分析横盘（需要{self.min_consolidation_days+1}天）')
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details
            }

        consolidation_period = df.iloc[-self.min_consolidation_days-1:-1]
        consolidation_high = consolidation_period['high'].max()
        consolidation_low = consolidation_period['low'].min()

        # 检查3：突破箱体上沿
        if latest['close'] <= consolidation_high * 1.01:
            reasons.append(f'未突破箱体上沿：收盘价{latest["close"]:.2f} <= 箱体上沿{consolidation_high * 1.01:.2f}')
        else:
            breakout_pct = (latest['close'] - consolidation_high) / consolidation_high * 100
            details['突破幅度'] = f'{breakout_pct:.2f}%'

        # 检查4：横盘期波动幅度
        consolidation_range = (consolidation_high - consolidation_low) / consolidation_low
        if consolidation_range > 0.15:
            reasons.append(f'横盘期波动过大：{consolidation_range*100:.1f}% > 15%（不是有效横盘）')
        else:
            details['横盘波动'] = f'{consolidation_range*100:.1f}%'

        # 检查5：成交量
        avg_volume_5 = df.iloc[-6:-1]['volume'].mean()
        volume_ratio = latest['volume'] / avg_volume_5 if avg_volume_5 > 0 else 0

        if volume_ratio < VOLUME_BREAKOUT_MIN:
            reasons.append(f'放量不足：{volume_ratio:.2f}倍 < {VOLUME_BREAKOUT_MIN}倍（需要放量突破）')
        elif volume_ratio > VOLUME_BREAKOUT_MAX:
            reasons.append(f'放量过大：{volume_ratio:.2f}倍 > {VOLUME_BREAKOUT_MAX}倍（可能是暴量假突破）')
        elif volume_ratio > VOLUME_FAKE_THRESHOLD:
            reasons.append(f'成交量暴量：{volume_ratio:.2f}倍 > {VOLUME_FAKE_THRESHOLD}倍（疑似假突破）')
        else:
            details['量比'] = f'{volume_ratio:.2f}倍'

        # 检查6：K线形态 - 上影线
        body_length = latest['close'] - latest['open']
        upper_shadow = latest['high'] - latest['close']
        if body_length > 0:
            upper_shadow_ratio = upper_shadow / body_length
            if upper_shadow_ratio > MAX_UPPER_SHADOW_RATIO:
                reasons.append(f'上影线过长：{upper_shadow_ratio:.2f} > {MAX_UPPER_SHADOW_RATIO}（可能是假突破）')
            else:
                details['上影线比例'] = f'{upper_shadow_ratio:.2f}'

        # 检查7：尾盘回落
        if latest['close'] < latest['high'] * 0.97:
            pullback_pct = (latest['high'] - latest['close']) / latest['high'] * 100
            reasons.append(f'尾盘回落过大：{pullback_pct:.1f}% > 3%（收盘离最高价太远）')

        # 判断结果
        if len(reasons) == 0:
            ma_info = self.check_ma_trend(df)
            return {
                'match': True,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': [],
                'details': {
                    **details,
                    '收盘价': f'{latest["close"]:.2f}',
                    '箱体上沿': f'{consolidation_high:.2f}',
                    'MA5': f'{ma_info["ma5"]:.2f}',
                    'MA10': f'{ma_info["ma10"]:.2f}',
                    'MA20': f'{ma_info["ma20"]:.2f}',
                    '趋势': '多头排列' if ma_info['trend'] == 'bullish' else ma_info['trend']
                }
            }
        else:
            return {
                'match': False,
                'code': code,
                'name': name,
                'date': self.current_date,
                'reasons': reasons,
                'details': details if details else None
            }

    def run_screening(self, date_str: Optional[str] = None,
                      force_restart: bool = False,
                      enable_analysis: bool = True,
                      no_check: bool = False) -> List[Dict]:
        """运行筛选"""
        if date_str:
            self.current_date = date_str

        # 检查数据是否可用
        if not no_check and not self.check_data_availability(self.current_date):
            logger.warning("⚠️  无可用数据 (%s) - 市场尚未收盘或数据未下载", self.current_date)
            return []

        logger.info("=" * 60)
        logger.info("突破主升筛选器 - Breakout Main Screener")
        logger.info("时间范围: 最近%d个交易日", self.limit_days)
        logger.info("入场条件:")
        logger.info("  - 横盘≥%d天", self.min_consolidation_days)
        logger.info("  - 放量%.1f-%.1f倍（<%.1f倍防暴量）",
                    VOLUME_BREAKOUT_MIN, VOLUME_BREAKOUT_MAX, VOLUME_BREAKOUT_MAX)
        logger.info("  - 上影线比例<%.2f", MAX_UPPER_SHADOW_RATIO)
        logger.info("  - 尾盘回落<3%%")
        logger.info("=" * 60)

        # 获取股票列表（StockFilter 已排除北交所等）
        stocks = self.get_all_stocks()
        # 额外过滤：保险起见再过一遍北交所前缀
        stocks = [s for s in stocks if not s.code.startswith('8') and not s.code.startswith('4')]

        total_stocks = len(stocks)
        logger.info("Total stocks: %d", total_stocks)

        # 进度跟踪桩（progress_tracker 为 None 时全部跳过）
        start_idx = 0
        if self.progress_tracker and not force_restart:
            if self.progress_tracker.is_resumable():
                processed_codes = self.progress_tracker.get_processed_codes()
                start_idx = len(processed_codes)
                logger.info("Resuming from stock %d", start_idx)
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
                            'close': result.get('close', result.get('current_price', 0)),
                            'pct_change': result.get('pct_change', 0),
                            'turnover': result.get('turnover', 0)
                        }
                        analysis = self.analyze_stock(stock.code, stock.name, news, price_data)
                        analysis_data[stock.code] = analysis
                        logger.info("✓ Found: %s %s - 突破%.1f%%, 行业:%s",
                                    stock.code, stock.name,
                                    result['breakout_quality'],
                                    analysis.get('行业分类', 'N/A'))
                    else:
                        logger.info("✓ Found: %s %s - 突破%.1f%%",
                                    stock.code, stock.name, result['breakout_quality'])

                if (i + 1) % 500 == 0:
                    logger.info("Progress: %d/%d, Found: %d", i + 1, total_stocks, len(results))

            except Exception as e:
                logger.error("Error screening %s: %s", stock.code, e)
                continue

        if self.progress_tracker:
            self.progress_tracker.complete(success=True)

        logger.info("\n%s", "=" * 60)
        logger.info("筛选完成!")
        logger.info("检查: %d 只股票", total_stocks)
        logger.info("匹配: %d 只股票", len(results))
        logger.info("=" * 60)

        return results

    def save_results(self, results: List[Dict],
                     analysis_data: Optional[Dict] = None) -> str:
        """保存结果"""
        column_mapping = {
            'code': '股票代码',
            'name': '股票名称',
            'close': '收盘价',
            'current_price': '当前价格',
            'pct_change': '涨幅%',
            'turnover': '换手率%',
            'consolidation_high': '箱体上沿',
            'consolidation_low': '箱体下沿',
            'consolidation_range_pct': '箱体波动%',
            'breakout_high': '突破最高价',
            'breakout_low': '突破最低价',
            'breakout_pct': '突破涨幅%',
            'body_length': 'K线实体',
            'upper_shadow_ratio': '上影线比例',
            'volume_ratio': '放量倍数',
            'avg_volume_5': '5日均量',
            'breakout_quality': '突破质量%',
            'consolidation_days': '横盘天数',
            'stop_loss': '止损位',
            'target_1': '目标位1(+10%)',
            'target_2': '目标位2(+18%)',
            'is_true_breakout': '真突破确认',
            'ma5': 'MA5',
            'ma10': 'MA10',
            'ma20': 'MA20',
            'ma_trend': '均线趋势'
        }

        return super().save_results(results, analysis_data, column_mapping=column_mapping)


def main():
    parser = argparse.ArgumentParser(description='突破主升筛选器（真突破策略）')
    parser.add_argument('--date', type=str, help='目标日期 (YYYY-MM-DD)')
    parser.add_argument('--limit-days', type=int, default=LIMIT_DAYS, help='回看周期')
    parser.add_argument('--min-consolidation', type=int, default=MIN_CONSOLIDATION_DAYS, help='最小横盘天数')
    parser.add_argument('--no-news', action='store_true', help='禁用新闻抓取')
    parser.add_argument('--no-llm', action='store_true', help='禁用LLM分析')
    parser.add_argument('--no-progress', action='store_true', help='禁用进度跟踪')
    parser.add_argument('--no-check', action='store_true', help='跳过数据检查（兼容参数）')
    parser.add_argument('--restart', action='store_true', help='强制重新开始')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    screener = BreakoutMainScreener(
        limit_days=args.limit_days,
        min_consolidation_days=args.min_consolidation,
        db_path=args.db_path or None,
        enable_news=False,
        enable_llm=False,
        enable_progress=not args.no_progress
    )

    result = screener.run_screening(
        date_str=args.date,
        force_restart=args.restart,
        enable_analysis=False,
        no_check=args.no_check
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
                  f"突破{r['breakout_quality']:.1f}%, "
                  f"放量{r['volume_ratio']:.1f}x, "
                  f"止损{r['stop_loss']:.2f}, "
                  f"目标1{r['target_1']:.2f}")

        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'breakout_main_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:{FLASK_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{FLASK_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
