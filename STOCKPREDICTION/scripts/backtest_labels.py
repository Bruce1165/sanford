"""
backtest_labels.py – 通过历史回测生成训练标签

对每个交易日的每只股票，向后看 21-34 个交易日，
计算最大涨幅，如果达到 20% 则标记为正样本。
"""

import argparse
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

import sys
from pathlib import Path

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    NEOTRADE_DB_PATH,
    LABELS_DB,
    LOOKBACK_DAYS,
    TARGET_HORIZON_MIN,
    TARGET_HORIZON_MAX,
    TARGET_GAIN,
    MIN_HISTORY_DAYS,
)
from models.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LabelGenerator:
    """标签生成器 - 通过历史回测生成训练标签"""

    def __init__(self, source_db: Path = NEOTRADE_DB_PATH,
                 target_db: Path = LABELS_DB):
        self.source_db = source_db
        self.target_db = target_db
        self._init_target_db()

    def _init_target_db(self):
        """初始化目标数据库"""
        init_db(self.target_db)
        logger.info(f"目标数据库已初始化: {self.target_db}")

    def get_all_stocks(self) -> List[Tuple[str, str]]:
        """获取所有有效股票列表"""
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, name
                FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND name NOT LIKE '%ST%'
                  AND name NOT LIKE '%*ST%'
                  AND name NOT LIKE '%退%'
                  AND name NOT LIKE '%指数%'
                  AND name NOT LIKE '%ETF%'
                  AND name NOT LIKE '%LOF%'
                  AND code NOT LIKE '43%'
                  AND code NOT LIKE '83%'
                  AND code NOT LIKE '87%'
                  AND code NOT LIKE '88%'
                  AND code NOT LIKE '399%'
                ORDER BY code
            """).fetchall()
        return [(r[0], r[1]) for r in rows]

    def get_stock_prices(self, code: str,
                         start_date: str,
                         end_date: str) -> pd.DataFrame:
        """获取股票价格数据"""
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            query = """
                SELECT trade_date, close, high, low, open, volume
                FROM daily_prices
                WHERE code = ? AND trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """
            df = pd.read_sql_query(query, conn, params=(code, start_date, end_date))
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df

    def get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取所有交易日列表"""
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            rows = conn.execute("""
                SELECT DISTINCT trade_date
                FROM daily_prices
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """, (start_date, end_date)).fetchall()
        return [r[0] for r in rows]

    def calculate_max_forward_gain(self, prices: pd.Series,
                                   min_days: int = 21,
                                   max_days: int = 34) -> Tuple[float, int, Optional[int]]:
        """
        计算向前的最大涨幅

        Args:
            prices: 价格序列
            min_days: 最短天数
            max_days: 最长天数

        Returns:
            (max_gain, gain_days, gain_index)
        """
        if len(prices) < min_days + 1:
            return 0.0, 0, None

        base_price = prices.iloc[0]
        max_gain = 0.0
        gain_days = 0
        gain_index = None

        for i in range(min_days, min(len(prices), max_days + 1)):
            future_price = prices.iloc[i]
            gain = (future_price - base_price) / base_price
            if gain > max_gain:
                max_gain = gain
                gain_days = i
                gain_index = i

        return max_gain, gain_days, gain_index

    def generate_labels_for_stock(self, code: str, name: str,
                                  start_date: str, end_date: str) -> List[Dict]:
        """为单只股票生成标签"""
        # 获取价格数据（需要额外数据用于计算特征）
        price_start = (datetime.strptime(start_date, "%Y-%m-%d") -
                       timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        price_end = (datetime.strptime(end_date, "%Y-%m-%d") +
                     timedelta(days=TARGET_HORIZON_MAX)).strftime("%Y-%m-%d")

        df = self.get_stock_prices(code, price_start, price_end)
        if df.empty or len(df) < MIN_HISTORY_DAYS + TARGET_HORIZON_MIN:
            return []

        df = df.set_index('trade_date').sort_index()
        labels = []

        # 对每个交易日计算标签
        for i in range(LOOKBACK_DAYS, len(df) - TARGET_HORIZON_MIN):
            base_date = df.index[i]
            base_date_str = base_date.strftime("%Y-%m-%d")

            # 向前看 21-34 天
            future_prices = df['close'].iloc[i+1:i+TARGET_HORIZON_MAX+1]
            max_gain, gain_days, gain_index = self.calculate_max_forward_gain(
                future_prices, TARGET_HORIZON_MIN, TARGET_HORIZON_MAX
            )

            # 确定标签
            label = 1 if max_gain >= TARGET_GAIN else 0
            max_gain_date = None
            if gain_index is not None:
                gain_date_idx = i + gain_days
                if gain_date_idx < len(df):
                    max_gain_date = df.index[gain_date_idx].strftime("%Y-%m-%d")

            labels.append({
                'code': code,
                'name': name,
                'base_date': base_date_str,
                'label': label,
                'max_gain': max_gain,
                'max_gain_date': max_gain_date,
                'max_gain_days': gain_days,
                'horizon_min': TARGET_HORIZON_MIN,
                'horizon_max': TARGET_HORIZON_MAX,
                'target_gain': TARGET_GAIN,
            })

        return labels

    def generate_all_labels(self, start_date: str, end_date: str,
                          overwrite: bool = False) -> int:
        """为所有股票生成标签"""
        logger.info(f"开始生成标签: {start_date} 到 {end_date}")

        # 获取所有股票
        stocks = self.get_all_stocks()
        logger.info(f"共 {len(stocks)} 只股票")

        # 清空现有数据（如果需要）
        if overwrite:
            with sqlite3.connect(str(self.target_db), timeout=30) as conn:
                conn.execute("DELETE FROM training_labels")
                conn.commit()
            logger.info("已清空现有标签数据")

        total_labels = 0
        positive_count = 0
        processed = 0

        for code, name in stocks:
            try:
                labels = self.generate_labels_for_stock(code, name, start_date, end_date)

                if labels:
                    # 保存到数据库
                    with sqlite3.connect(str(self.target_db), timeout=30) as conn:
                        for label in labels:
                            conn.execute("""
                                INSERT INTO training_labels
                                (code, name, base_date, label, max_gain, max_gain_date,
                                 max_gain_days, horizon_min, horizon_max, target_gain)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                label['code'], label['name'], label['base_date'],
                                label['label'], label['max_gain'], label['max_gain_date'],
                                label['max_gain_days'], label['horizon_min'],
                                label['horizon_max'], label['target_gain']
                            ))
                        conn.commit()

                    total_labels += len(labels)
                    positive_count += sum(1 for l in labels if l['label'] == 1)

                processed += 1
                if processed % 100 == 0:
                    logger.info(f"已处理 {processed}/{len(stocks)} 只股票, "
                               f"累计标签 {total_labels}, 正样本 {positive_count}")

            except Exception as e:
                logger.warning(f"处理股票 {code} 时出错: {e}")

        # 统计结果
        logger.info(f"\n标签生成完成:")
        logger.info(f"  处理股票: {processed}/{len(stocks)}")
        logger.info(f"  总标签数: {total_labels}")
        logger.info(f"  正样本数: {positive_count}")
        logger.info(f"  负样本数: {total_labels - positive_count}")
        if total_labels > 0:
            logger.info(f"  正样本率: {positive_count/total_labels*100:.2f}%")

        return total_labels

    def get_label_stats(self) -> Dict:
        """获取标签统计信息"""
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            # 总体统计
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN label = 1 THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN label = 0 THEN 1 ELSE 0 END) as negative,
                    AVG(max_gain) as avg_max_gain,
                    MAX(max_gain) as max_max_gain,
                    MIN(max_gain) as min_max_gain
                FROM training_labels
            """).fetchone()

            # 按日期统计
            date_rows = conn.execute("""
                SELECT base_date,
                       COUNT(*) as total,
                       SUM(CASE WHEN label = 1 THEN 1 ELSE 0 END) as positive
                FROM training_labels
                GROUP BY base_date
                ORDER BY base_date
                LIMIT 30
            """).fetchall()

        return {
            'total': row[0],
            'positive': row[1],
            'negative': row[2],
            'positive_rate': row[1] / row[3] if row[0] > 0 else 0,
            'avg_max_gain': row[3],
            'max_max_gain': row[4],
            'min_max_gain': row[5],
            'recent_dates': date_rows,
        }


def main():
    parser = argparse.ArgumentParser(description='生成训练标签')
    parser.add_argument('--start-date', type=str, default='2024-09-01',
                        help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        help='结束日期 (YYYY-MM-DD), 默认为数据最新日期')
    parser.add_argument('--overwrite', action='store_true',
                        help='覆盖现有标签')
    parser.add_argument('--stats', action='store_true',
                        help='只显示统计信息')

    args = parser.parse_args()

    generator = LabelGenerator()

    if args.stats:
        stats = generator.get_label_stats()
        print("\n" + "="*60)
        print("标签统计信息")
        print("="*60)
        print(f"总标签数: {stats['total']}")
        print(f"正样本数: {stats['positive']}")
        print(f"负样本数: {stats['negative']}")
        print(f"正样本率: {stats['positive_rate']*100:.2f}%")
        print(f"平均最大涨幅: {stats['avg_max_gain']*100:.2f}%")
        print(f"最大最大涨幅: {stats['max_max_gain']*100:.2f}%")
        print(f"最小最大涨幅: {stats['min_max_gain']*100:.2f}%")
        print("\n最近30天统计:")
        print(f"{'日期':<12} {'总数':<8} {'正样本':<8}")
        print("-"*30)
        for row in stats['recent_dates']:
            print(f"{row[0]:<12} {row[1]:<8} {row[2]:<8}")
        return

    # 确定结束日期
    if args.end_date:
        end_date = args.end_date
    else:
        # 使用 NeoTrade2 数据库的最新日期
        with sqlite3.connect(str(NEOTRADE_DB_PATH), timeout=30) as conn:
            row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
            end_date = row[0] if row and row[0] else datetime.now().strftime("%Y-%m-%d")

    logger.info(f"标签生成范围: {args.start_date} 到 {end_date}")

    # 生成标签
    generator.generate_all_labels(args.start_date, end_date, args.overwrite)

    # 显示统计
    stats = generator.get_label_stats()
    print(f"\n正样本率: {stats['positive_rate']*100:.2f}%")


if __name__ == '__main__':
    main()
