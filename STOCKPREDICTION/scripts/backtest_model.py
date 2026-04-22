"""
backtest_model.py – 模型回测脚本

评估模型在历史时间段的表现。
"""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import xgboost as xgb
import matplotlib.pyplot as plt

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import PREDICTIONS_DB

# 简化日志，不写文件
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ModelBacktester:
    """模型回测器"""

    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model = None
        self.metadata = None
        self.feature_names = None

    def load_model(self):
        """加载模型"""
        logger.info(f"加载模型: {self.model_path}")

        self.model = xgb.XGBClassifier()
        self.model.load_model(str(self.model_path))

        import json
        metadata_path = self.model_path.parent / 'model_metadata.json'
        with open(metadata_path, 'r') as f:
            self.metadata = json.load(f)
        self.feature_names = self.metadata['features']

    def load_test_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """加载测试数据"""
        with sqlite3.connect('data/features.db') as conn:
            features = pd.read_sql_query(
                "SELECT * FROM stock_features WHERE trade_date BETWEEN ? AND ?",
                conn, params=(start_date, end_date)
            )

        with sqlite3.connect('data/screener_scores.db') as conn:
            screener = pd.read_sql_query(
                "SELECT * FROM screener_features WHERE trade_date BETWEEN ? AND ?",
                conn, params=(start_date, end_date)
            )

        # 合并
        screener_pivot = screener.pivot_table(
            index=['code', 'trade_date'],
            columns='screener_name',
            values='hit',
            fill_value=0
        ).reset_index()

        data = features.merge(
            screener_pivot,
            on=['code', 'trade_date'],
            how='left'
        )

        # 填充筛选器
        from scripts.config import SCREENER_FEATURES
        for s in SCREENER_FEATURES:
            if s not in data.columns:
                data[s] = 0

        return data

    def backtest_date(self, data: pd.DataFrame, date_str: str, top_k: int = 50) -> Dict:
        """回测单个日期"""
        # 筛选当日数据
        day_data = data[data['trade_date'] == date_str].copy()

        if day_data.empty:
            return {'date': date_str, 'predictions': 0}

        # 准备特征
        X = day_data[self.feature_names].fillna(0)

        # 预测
        probabilities = self.model.predict_proba(X)[:, 1]

        # Top K
        day_data['probability'] = probabilities
        top_k_stocks = day_data.nlargest(top_k, 'probability')

        # 计算未来收益
        results = []
        for _, stock in top_k_stocks.iterrows():
            code = stock['code']
            close = stock['close']

            # 查询未来收益（从 labels 获取）
            with sqlite3.connect('data/labels.db') as conn:
                row = conn.execute("""
                    SELECT label, max_gain, max_gain_date, max_gain_days
                    FROM training_labels
                    WHERE code = ? AND base_date = ?
                """, (code, date_str)).fetchone()

                if row:
                    results.append({
                        'code': code,
                        'probability': stock['probability'],
                        'label': row[0],
                        'max_gain': row[1],
                        'max_gain_days': row[3]
                    })

        if not results:
            return {'date': date_str, 'predictions': 0}

        results_df = pd.DataFrame(results)
        hit_count = results_df['label'].sum()
        avg_gain = results_df['max_gain'].mean()

        return {
            'date': date_str,
            'predictions': len(results),
            'hits': int(hit_count),
            'hit_rate': hit_count / len(results),
            'avg_gain': avg_gain
        }

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        top_k: int = 50
    ) -> List[Dict]:
        """运行回测"""
        # 加载模型
        self.load_model()

        # 加载数据
        data = self.load_test_data(start_date, end_date)

        # 获取交易日期
        dates = sorted(data['trade_date'].unique())

        logger.info(f"回测日期范围: {dates[0]} 到 {dates[-1]}, 共 {len(dates)} 个交易日")

        # 逐日回测
        results = []
        for date_str in dates:
            result = self.backtest_date(data, date_str, top_k)
            results.append(result)
            logger.info(f"{date_str}: 预测 {result['predictions']} 只, 命中 {result.get('hits', 0)} 只")

        return results

    def generate_report(self, results: List[Dict]):
        """生成回测报告"""
        df = pd.DataFrame(results)

        total_predictions = df['predictions'].sum()
        total_hits = df['hits'].sum()
        overall_hit_rate = total_hits / total_predictions if total_predictions > 0 else 0
        avg_daily_gain = df['avg_gain'].mean()

        report = f"""
=== 模型回测报告 ===

总体统计:
- 总预测数: {total_predictions}
- 总命中数: {total_hits}
- 整体胜率: {overall_hit_rate:.2%}
- 平均单日收益: {avg_daily_gain:.2%}

每日统计:
{'日期':<12} {'预测数':<8} {'命中':<6} {'胜率':<10}
{'-'*40}
"""
        for _, row in df.iterrows():
            hit_rate = row['hits'] / row['predictions'] if row['predictions'] > 0 else 0
            report += f"{row['date']:<12} {row['predictions']:<8} {row['hits']:<6} {hit_rate:.2%}\n"

        print(report)
        return report


def main():
    parser = argparse.ArgumentParser(description='模型回测')
    parser.add_argument('--model', type=str, default='models/xgboost_model.json')
    parser.add_argument('--start-date', type=str, default='2026-03-01')
    parser.add_argument('--end-date', type=str, default='2026-03-31')
    parser.add_argument('--top-k', type=int, default=50)

    args = parser.parse_args()

    backtester = ModelBacktester(args.model)
    results = backtester.run_backtest(args.start_date, args.end_date, args.top_k)
    backtester.generate_report(results)


if __name__ == '__main__':
    main()
