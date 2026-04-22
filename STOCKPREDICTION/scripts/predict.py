"""
predict.py – 每日股票预测脚本

从准备好的数据中执行预测，输出结果。
"""

import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    NEOTRADE_DB_PATH,
    FEATURES_DB,
    SCREENER_SCORES_DB,
    PREDICTIONS_DB,
    SCREENER_FEATURES,
)

# 简化日志配置，不写入文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StockPredictor:
    """股票预测器"""

    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model = None
        self.metadata = None
        self.feature_names = None

    def load_model(self):
        """加载模型和元数据"""
        logger.info(f"加载模型: {self.model_path}")

        self.model = xgb.XGBClassifier()
        self.model.load_model(str(self.model_path))

        metadata_path = self.model_path.parent / 'model_metadata.json'
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
            self.feature_names = self.metadata.get('features', [])
            logger.info(f"模型加载完成，特征数: {len(self.feature_names)}")
        else:
            raise FileNotFoundError(f"元数据文件不存在: {metadata_path}")

    def get_latest_date(self) -> str:
        """获取 NeoTrade2 中的最新交易日"""
        with sqlite3.connect(str(NEOTRADE_DB_PATH), timeout=30) as conn:
            row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
            return row[0] if row and row[0] else datetime.now().strftime("%Y-%m-%d")

    def prepare_data(self, date_str: str) -> pd.DataFrame:
        """准备预测数据"""
        logger.info(f"准备预测数据，日期: {date_str}")

        # 加载特征
        with sqlite3.connect(str(FEATURES_DB)) as conn:
            features_df = pd.read_sql_query(
                "SELECT * FROM stock_features WHERE trade_date = ?",
                conn, params=(date_str,)
            )

        if features_df.empty:
            raise ValueError(f"日期 {date_str} 没有特征数据")

        # 加载筛选器特征
        with sqlite3.connect(str(SCREENER_SCORES_DB)) as conn:
            screener_df = pd.read_sql_query(
                "SELECT * FROM screener_features WHERE trade_date = ?",
                conn, params=(date_str,)
            )

        # 编码筛选器特征
        if not screener_df.empty:
            screener_pivot = screener_df.pivot_table(
                index='code',
                columns='screener_name',
                values='hit',
                fill_value=0
            ).reset_index()

            # 合并数据
            predict_data = features_df.merge(
                screener_pivot, on='code', how='left'
            )
        else:
            predict_data = features_df.copy()

        # 填充筛选器特征为0
        for screener in SCREENER_FEATURES:
            if screener not in predict_data.columns:
                predict_data[screener] = 0

        logger.info(f"准备数据完成: {len(predict_data)} 只股票")
        return predict_data

    def predict(self, date_str: str, top_k: int = 50) -> pd.DataFrame:
        """执行预测"""
        # 准备数据
        predict_data = self.prepare_data(date_str)

        # 提取特征
        X = predict_data[self.feature_names].fillna(0)

        # 预测
        probabilities = self.model.predict_proba(X)[:, 1]

        # 创建结果
        results = pd.DataFrame({
            'code': predict_data['code'],
            'name': predict_data.get('name', ''),
            'probability': probabilities,
            'prediction_date': date_str
        })

        # 排序
        results = results.sort_values('probability', ascending=False)
        results['rank'] = range(1, len(results) + 1)

        logger.info(f"预测完成，Top {top_k} 平均概率: {results.head(top_k)['probability'].mean():.4f}")

        return results

    def save_results(self, predictions: pd.DataFrame):
        """保存预测结果到数据库"""
        with sqlite3.connect(str(PREDICTIONS_DB)) as conn:
            for _, row in predictions.iterrows():
                conn.execute("""
                    INSERT OR REPLACE INTO predictions
                    (code, name, prediction_date, probability, rank, model_name, model_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['code'], row['name'], row['prediction_date'],
                    row['probability'], int(row['rank']),
                    'xgboost', self.metadata.get('version', '1.0.0')
                ))
            conn.commit()

        logger.info(f"预测结果已保存: {len(predictions)} 条")

    def generate_report(self, predictions: pd.DataFrame, top_k: int = 50):
        """生成预测报告"""
        top_k_df = predictions.head(top_k)

        report_lines = [
            f"=== 股票预测报告 ===",
            f"日期: {predictions['prediction_date'].iloc[0]}",
            f"总预测数: {len(predictions)}",
            "",
            f"=== Top {top_k} 预测 ===",
            f"{'排名':<5} {'代码':<10} {'名称':<15} {'概率':<10}",
            "-" * 40,
        ]

        for _, row in top_k_df.iterrows():
            report_lines.append(
                f"{int(row['rank']):<5} {row['code']:<10} {str(row['name'])[:15]:<15} {row['probability']:.4f}"
            )

        report = '\n'.join(report_lines)
        print(report)

        return report

    def run(self, date_str: str = None, top_k: int = 50):
        """运行完整预测流程"""
        # 加载模型
        self.load_model()

        # 确定日期
        if not date_str:
            date_str = self.get_latest_date()

        # 预测
        predictions = self.predict(date_str, top_k)

        # 保存结果
        self.save_results(predictions)

        # 生成报告
        self.generate_report(predictions, top_k)

        return predictions


def main():
    parser = argparse.ArgumentParser(description='每日股票预测')
    parser.add_argument('--model', type=str, default='models/xgboost_model.json')
    parser.add_argument('--date', type=str, help='预测日期 (YYYY-MM-DD)')
    parser.add_argument('--top-k', type=int, default=50, help='输出 Top K')

    args = parser.parse_args()

    predictor = StockPredictor(args.model)
    predictor.run(args.date, args.top_k)


if __name__ == '__main__':
    main()
