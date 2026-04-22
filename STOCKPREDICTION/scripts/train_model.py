"""
train_model.py – 模型训练脚本

从准备好的数据中训练机器学习模型。
"""

import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, accuracy_score
from sklearn.preprocessing import RobustScaler
from sklearn.impute import SimpleImputer

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    LABELS_DB,
    FEATURES_DB,
    PREDICTIONS_DB,
    MODEL_OUTPUT,
)
from models.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelTrainer:
    """模型训练器"""

    def __init__(self):
        self.scaler = None
        self.imputer = None
        self.feature_names = None

    def load_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """加载并合并训练数据"""
        logger.info("加载标签数据...")
        with sqlite3.connect(str(LABELS_DB)) as conn:
            labels = pd.read_sql_query(
                "SELECT * FROM training_labels WHERE base_date BETWEEN ? AND ?",
                conn, params=(start_date, end_date)
            )

        logger.info("加载特征数据...")
        with sqlite3.connect(str(FEATURES_DB)) as conn:
            features = pd.read_sql_query(
                "SELECT * FROM stock_features WHERE trade_date BETWEEN ? AND ?",
                conn, params=(start_date, end_date)
            )

        logger.info("合并数据...")
        data = labels.merge(
            features,
            left_on=['code', 'base_date'],
            right_on=['code', 'trade_date'],
            how='left'
        )

        logger.info(f"合并后数据量: {len(data)}")
        return data

    def define_features(self, data: pd.DataFrame) -> List[str]:
        """定义特征列"""
        # 技术指标特征
        technical_features = [
            'close', 'pct_change', 'volume', 'turnover',
            'ma5', 'ma10', 'ma20', 'ma60',
            'ema12', 'ema26', 'macd', 'macd_signal', 'macd_hist',
            'rsi', 'atr',
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower', 'bollinger_pct',
            'stoch_k', 'stoch_d',
            'return_3d', 'return_5d', 'return_10d', 'return_20d', 'return_60d',
            'volatility_10d', 'volatility_20d', 'volatility_60d',
            'vol_ratio_5d', 'vol_ratio_20d',
        ]

        # 筛选器特征（暂时不使用，因为数据为空）
        screener_cols = []

        # 合并并过滤存在的特征
        all_features = technical_features + screener_cols
        existing_features = [f for f in all_features if f in data.columns]

        logger.info(f"技术特征: {len(technical_features)}, 筛选器特征: {len(screener_cols)}")
        logger.info(f"有效特征数: {len(existing_features)}")

        return existing_features

    def prepare_data(
        self,
        data: pd.DataFrame,
        feature_names: List[str],
        train_end: str,
        val_end: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """准备训练/验证/测试数据"""
        # 按时间分割
        train_mask = data['base_date'] <= train_end
        val_mask = (data['base_date'] > train_end) & (data['base_date'] <= val_end)
        test_mask = data['base_date'] > val_end

        # 提取特征和标签
        feature_names = self.define_features(data)
        X = data[feature_names].values
        y = data['label'].values

        # 分割
        X_train, y_train = X[train_mask], y[train_mask]
        X_val, y_val = X[val_mask], y[val_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        # 缺失值处理
        self.imputer = SimpleImputer(strategy='median')
        X_train = self.imputer.fit_transform(X_train)
        X_val = self.imputer.transform(X_val)
        X_test = self.imputer.transform(X_test)

        # 标准化
        self.scaler = RobustScaler()
        X_train = self.scaler.fit_transform(X_train)
        X_val = self.scaler.transform(X_val)
        X_test = self.scaler.transform(X_test)

        # 保存特征名称
        self.feature_names = feature_names

        # 输出统计
        logger.info(f"训练集: {len(X_train)}, 正样本率: {y_train.mean():.2%}")
        logger.info(f"验证集: {len(X_val)}, 正样本率: {y_val.mean():.2%}")
        logger.info(f"测试集: {len(X_test)}, 正样本率: {y_test.mean():.2%}")

        return X_train, X_val, X_test, y_train, y_val, y_test

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        model_type: str = 'gradient_boosting'
    ) -> GradientBoostingClassifier | RandomForestClassifier:
        """训练模型"""
        # 计算类别权重
        neg_samples = (y_train == 0).sum()
        pos_samples = (y_train == 1).sum()
        scale_pos_weight = (neg_samples / pos_samples) * 0.5

        logger.info(f"类别权重: {scale_pos_weight:.2f}")

        # 模型参数
        if model_type == 'gradient_boosting':
            params = {
                'n_estimators': 200,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'random_state': 42,
            }
            logger.info(f"训练Gradient Boosting模型，参数: {params}")
            model = GradientBoostingClassifier(**params, random_state=42)
        else:  # random_forest
            params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 2,
                'class_weight': 'balanced',
                'random_state': 42,
            }
            logger.info(f"训练Random Forest模型，参数: {params}")
            model = RandomForestClassifier(**params, random_state=42)

        model.fit(X_train, y_train)

        # 保存模型
        timestamp = datetime.now().strftime('%Y%m%d')
        if model_type == 'gradient_boosting':
            model_name = f"gradient_boosting_{timestamp}.pkl"
        else:
            model_name = f"random_forest_{timestamp}.pkl"
        model_path = Path(f"models/{model_name}")
        joblib.dump(model, model_path)
        logger.info(f"模型已保存到: {model_path}")

        return model

    def evaluate_model(
        self,
        model: GradientBoostingClassifier | RandomForestClassifier,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict:
        """评估模型"""
        logger.info("评估模型...")

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        # 基础指标
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        auc = roc_auc_score(y_test, y_proba)

        # Precision@K
        def precision_at_k(y_true, y_proba, k):
            top_k_idx = np.argsort(y_proba)[::-1][:k]
            return y_true[top_k_idx].sum() / k

        p_at_10 = precision_at_k(y_test, y_proba, 10)
        p_at_50 = precision_at_k(y_test, y_proba, 50)
        p_at_100 = precision_at_k(y_test, y_proba, 100)

        metrics = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'auc': auc,
            'precision_at_10': p_at_10,
            'precision_at_50': p_at_50,
            'precision_at_100': p_at_100,
        }

        logger.info(f"Precision: {precision:.4f}")
        logger.info(f"Recall: {recall:.4f}")
        logger.info(f"F1-Score: {f1:.4f}")
        logger.info(f"AUC: {auc:.4f}")
        logger.info(f"Precision@50: {p_at_50:.4f}")

        return metrics

    def save_model(
        self,
        model: GradientBoostingClassifier | RandomForestClassifier,
        metrics: Dict,
        output_path: Path
    ):
        """保存模型和元数据"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存模型
        if isinstance(model, GradientBoostingClassifier):
            model_name = 'gradient_boosting'
        elif isinstance(model, RandomForestClassifier):
            model_name = 'random_forest'
        else:
            model_name = model.__class__.__name__

        model_path = output_path / f"{model_name}.pkl"
        joblib.dump(model, model_path)
        logger.info(f"模型已保存到: {model_path}")

        # 保存元数据
        timestamp = datetime.now().strftime('%Y%m%d')
        metadata = {
            'model_name': model_name,
            'version': '1.0.0',
            'created_at': datetime.now().isoformat(),
            'features': self.feature_names,
            'n_features': len(self.feature_names),
            'metrics': metrics,
        }

        metadata_path = output_path.parent / 'model_metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"元数据已保存: {metadata_path}")

        # 保存到数据库
        with sqlite3.connect(str(PREDICTIONS_DB)) as conn:
            conn.execute("""
                INSERT INTO model_performance
                (model_name, model_version, train_start, train_end, test_start, test_end,
                 precision, recall, f1_score, auc,
                 precision_at_10, precision_at_50, precision_at_100)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model_name, '1.0.0',
                metadata.get('train_start', ''), metadata.get('train_end', ''),
                metadata.get('test_start', ''), metadata.get('test_end', ''),
                metrics['precision'], metrics['recall'], metrics['f1'], metrics['auc'],
                metrics['precision_at_10'], metrics['precision_at_50'], metrics['precision_at_100'],
            ))
            conn.commit()

        logger.info("性能记录已保存到数据库")

    def run(
        self,
        start_date: str = '2024-11-01',
        train_end: str = '2024-11-30',
        val_end: str = '2024-11-30',
        output: str = 'models/gradient_boosting_model.json'
    ):
        """运行完整训练流程"""
        # 1. 加载数据
        data = self.load_data(start_date, val_end)

        # 2. 定义特征
        feature_names = self.define_features(data)

        # 3. 准备数据
        X_train, X_val, X_test, y_train, y_val, y_test = self.prepare_data(
            data, feature_names, train_end, val_end
        )

        # 4. 训练模型
        model = self.train_model(X_train, y_train, X_val, y_val)

        # 5. 评估模型
        metrics = self.evaluate_model(model, X_test, y_test)

        # 6. 保存模型
        self.save_model(model, metrics, Path(output))

        return model, metrics


def main():
    parser = argparse.ArgumentParser(description='训练预测模型')
    parser.add_argument('--start-date', type=str, default='2024-09-01')
    parser.add_argument('--train-end', type=str, default='2025-12-31')
    parser.add_argument('--val-end', type=str, default='2026-02-28')
    parser.add_argument('--output', type=str, default='models/gradient_boosting_model.json')
    parser.add_argument('--model', type=str, default='gradient_boosting', choices=['gradient_boosting', 'random_forest', 'xgboost'])

    args = parser.parse_args()

    # 初始化数据库
    init_db(PREDICTIONS_DB)

    # 训练
    trainer = ModelTrainer()
    trainer.run(
        start_date=args.start_date,
        train_end=args.train_end,
        val_end=args.val_end,
        output=args.output
    )


if __name__ == '__main__':
    main()
