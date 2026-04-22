# 训练流程

## 概述

本文档描述从原始数据到训练好的模型的完整流程。

## 流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│                       1. 数据准备阶段                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       2. 特征工程阶段                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       3. 数据预处理阶段                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       4. 模型训练阶段                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       5. 模型评估阶段                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       6. 模型保存阶段                            │
└─────────────────────────────────────────────────────────────────┘
```

## 1. 数据准备阶段

### 1.1 标签生成

**脚本**: `scripts/backtest_labels.py`

**命令**:
```bash
python scripts/backtest_labels.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite
```

**输出**: `data/labels.db`

**预期结果**:
- 总标签数: ~900,000 条
- 正样本数: ~45,000-90,000 条 (5-10%)
- 负样本数: ~810,000-855,000 条

### 1.2 特征计算

**脚本**: `scripts/compute_features.py`

**命令**:
```bash
python scripts/compute_features.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite
```

**输出**: `data/features.db`

**预期结果**:
- 总特征数: ~900,000 条
- 每条特征: ~35 个技术指标

### 1.3 筛选器特征收集

**脚本**: `scripts/collect_screener_scores.py`

**命令**:
```bash
python scripts/collect_screener_scores.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite
```

**输出**: `data/screener_scores.db`

**预期结果**:
- 总记录数: ~10,800,000 条 (12 个筛选器 × 900,000 条)

## 2. 特征工程阶段

### 2.1 数据合并

```python
import pandas as pd
import sqlite3
from pathlib import Path

# 加载数据
labels = pd.read_sql("SELECT * FROM training_labels", sqlite3.connect("data/labels.db"))
features = pd.read_sql("SELECT * FROM stock_features", sqlite3.connect("data/features.db"))
screener_features = pd.read_sql("SELECT * FROM screener_features", sqlite3.connect("data/screener_scores.db"))

# 合并基础数据
data = labels.merge(
    features,
    left_on=['code', 'base_date'],
    right_on=['code', 'trade_date'],
    how='left'
)

# 编码筛选器特征
screener_pivot = screener_features.pivot_table(
    index=['code', 'trade_date'],
    columns='screener_name',
    values='hit',
    fill_value=0
).reset_index()

# 最终合并
data = data.merge(
    screener_pivot,
    left_on=['code', 'base_date'],
    right_on=['code', 'trade_date'],
    how='left'
)
```

### 2.2 特征选择

```python
# 定义特征列
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

screener_features_list = [
    'coffee_cup_screener',
    'coffee_cup_handle_screener_v4',
    'jin_feng_huang_screener',
    'yin_feng_huang_screener',
    'shi_pan_xian_screener',
    'er_ban_hui_tiao_screener',
    'zhang_ting_bei_liang_yin_screener',
    'breakout_20day_screener',
    'breakout_main_screener',
    'daily_hot_cold_screener',
    'shuang_shou_ban_screener',
    'ashare_21_screener',
]

all_features = technical_features + screener_features_list

# 筛选存在的特征
existing_features = [f for f in all_features if f in data.columns]
X = data[existing_features].copy()
y = data['label'].copy()
```

## 3. 数据预处理阶段

### 3.1 缺失值处理

```python
from sklearn.impute import SimpleImputer

# 数值特征：中位数填充
numeric_imputer = SimpleImputer(strategy='median')
X_imputed = numeric_imputer.fit_transform(X)

# 筛选器特征：0 填充（未命中）
screener_imputer = SimpleImputer(strategy='constant', fill_value=0)
X_screener = screener_imputer.fit_transform(X[screener_features_list])
```

### 3.2 特征标准化

```python
from sklearn.preprocessing import RobustScaler

# 使用 RobustScaler 处理异常值
scaler = RobustScaler()
X_scaled = scaler.fit_transform(X_imputed)

# 筛选器特征不需要标准化
for i, col in enumerate(screener_features_list):
    if col in X.columns:
        X_scaled[:, i] = X[col].values
```

### 3.3 时间序列分割

```python
# 按时间分割数据
train_end = '2025-12-31'
val_start = '2026-01-01'
val_end = '2026-02-28'
test_start = '2026-03-01'

train_mask = data['base_date'] <= train_end
val_mask = (data['base_date'] >= val_start) & (data['base_date'] <= val_end)
test_mask = data['base_date'] >= test_start

X_train = X_scaled[train_mask]
y_train = y[train_mask]
X_val = X_scaled[val_mask]
y_val = y[val_mask]
X_test = X_scaled[test_mask]
y_test = y[test_mask]

print(f"训练集: {len(X_train)} 条, 正样本率: {y_train.mean():.2%}")
print(f"验证集: {len(X_val)} 条, 正样本率: {y_val.mean():.2%}")
print(f"测试集: {len(X_test)} 条, 正样本率: {y_test.mean():.2%}")
```

### 3.4 处理类别不平衡

```python
# 方法1: 调整类别权重
scale_pos_weight = (len(y_train) - sum(y_train)) / sum(y_train) * 0.5

# 方法2: SMOTE 过采样（可选）
from imblearn.over_sampling import SMOTE

smote = SMOTE(random_state=42, sampling_strategy=0.1)
X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

# 方法3: 欠采样（可选）
from imblearn.under_sampling import RandomUnderSampler

undersampler = RandomUnderSampler(sampling_strategy=0.5, random_state=42)
X_train_balanced, y_train_balanced = undersampler.fit_resample(X_train_resampled, y_train_resampled)
```

## 4. 模型训练阶段

### 4.1 基础训练

```python
import xgboost as xgb

# 模型参数
params = {
    'objective': 'binary:logistic',
    'eval_metric': 'auc',
    'n_estimators': 500,
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'min_child_weight': 3,
    'scale_pos_weight': scale_pos_weight,
    'random_state': 42,
    'n_jobs': -1,
}

# 训练模型
model = xgb.XGBClassifier(**params)
model.fit(
    X_train, y_train,
    eval_set=[(X_train, y_train), (X_val, y_val)],
    early_stopping_rounds=50,
    verbose=10
)
```

### 4.2 交叉验证

```python
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import f1_score

# 时间序列交叉验证
tscv = TimeSeriesSplit(n_splits=5)
cv_scores = []

for train_idx, val_idx in tscv.split(X_train):
    X_cv_train, X_cv_val = X_train[train_idx], X_train[val_idx]
    y_cv_train, y_cv_val = y_train.iloc[train_idx], y_train.iloc[val_idx]

    model_cv = xgb.XGBClassifier(**params)
    model_cv.fit(X_cv_train, y_cv_train)

    y_pred = model_cv.predict(X_cv_val)
    score = f1_score(y_cv_val, y_pred)
    cv_scores.append(score)

print(f"CV F1: {np.mean(cv_scores):.4f} (±{np.std(cv_scores):.4f})")
```

## 5. 模型评估阶段

### 5.1 分类指标

```python
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, confusion_matrix
)

# 预测
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

# 基础指标
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_proba)

print(f"Precision: {precision:.4f}")
print(f"Recall: {recall:.4f}")
print(f"F1-Score: {f1:.4f}")
print(f"AUC: {auc:.4f}")
```

### 5.2 Precision@K

```python
def precision_at_k(y_true, y_proba, k):
    """计算 Top K 预测的精确率"""
    # 获取 Top K 索引
    top_k_idx = np.argsort(y_proba)[::-1][:k]
    top_k_true = y_true.iloc[top_k_idx]
    return top_k_true.sum() / k

# 计算 Precision@K
for k in [10, 20, 50, 100]:
    p_at_k = precision_at_k(y_test, y_proba, k)
    print(f"Precision@{k}: {p_at_k:.4f}")
```

### 5.3 混淆矩阵

```python
cm = confusion_matrix(y_test, y_pred)

print("混淆矩阵:")
print(f"              预测负样本    预测正样本")
print(f"实际负样本    {cm[0,0]:6d}     {cm[0,1]:6d}")
print(f"实际正样本    {cm[1,0]:6d}     {cm[1,1]:6d}")
```

### 5.4 特征重要性

```python
import matplotlib.pyplot as plt

# 获取特征重要性
importance = model.feature_importances_
feature_names = existing_features

# 排序
feature_importance = pd.DataFrame({
    'feature': feature_names,
    'importance': importance
}).sort_values('importance', ascending=False)

# Top 20 特征
top_features = feature_importance.head(20)
print(top_features)

# 可视化
plt.figure(figsize=(10, 6))
plt.barh(top_features['feature'], top_features['importance'])
plt.xlabel('Importance')
plt.title('Top 20 Feature Importance')
plt.tight_layout()
plt.savefig('reports/feature_importance.png')
```

## 6. 模型保存阶段

### 6.1 保存模型

```python
import joblib
import json
from datetime import datetime

# 保存模型
model_path = Path('models/xgboost_model.json')
model.save_model(str(model_path))

# 保存元数据
metadata = {
    'model_name': 'xgboost_stock_predictor',
    'version': '1.0.0',
    'created_at': datetime.now().isoformat(),
    'train_date_range': ['2024-09-01', '2025-12-31'],
    'features': existing_features,
    'params': params,
    'metrics': {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'auc': auc,
        'precision_at_10': precision_at_k(y_test, y_proba, 10),
        'precision_at_50': precision_at_k(y_test, y_proba, 50),
        'precision_at_100': precision_at_k(y_test, y_proba, 100),
    }
}

metadata_path = Path('models/model_metadata.json')
with open(metadata_path, 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"模型已保存: {model_path}")
print(f"元数据已保存: {metadata_path}")
```

### 6.2 保存性能记录

```python
import sqlite3
from models.database import ModelPerformance

# 保存到数据库
with sqlite3.connect('data/predictions.db') as conn:
    conn.execute("""
        INSERT INTO model_performance
        (model_name, model_version, train_start, train_end,
         test_start, test_end, precision, recall, f1_score, auc,
         precision_at_10, precision_at_50, precision_at_100)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'xgboost', '1.0.0',
        '2024-09-01', '2025-12-31',
        '2026-03-01', '2026-03-31',
        precision, recall, f1, auc,
        precision_at_k(y_test, y_proba, 10),
        precision_at_k(y_test, y_proba, 50),
        precision_at_k(y_test, y_proba, 100),
    ))
    conn.commit()
```

## 完整训练脚本

```bash
#!/bin/bash
# train.sh - 完整训练流程

echo "=== 开始训练流程 ==="

# 1. 生成标签
echo "步骤 1: 生成标签..."
python scripts/backtest_labels.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 2. 计算特征
echo "步骤 2: 计算特征..."
python scripts/compute_features.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 3. 收集筛选器特征
echo "步骤 3: 收集筛选器特征..."
python scripts/collect_screener_scores.py \
    --start-date 2024-09-01 \
    --end-date 2026-03-31 \
    --overwrite

# 4. 训练模型
echo "步骤 4: 训练模型..."
python scripts/train_model.py \
    --model xgboost \
    --cv 5 \
    --output models/xgboost_model.json

# 5. 评估模型
echo "步骤 5: 评估模型..."
python scripts/backtest_model.py \
    --model models/xgboost_model.json \
    --start-date 2026-03-01 \
    --end-date 2026-03-31

echo "=== 训练流程完成 ==="
```

## 训练监控

### 实时监控

```python
import time
from datetime import datetime

def log_training_progress(stage, message):
    """记录训练进度"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {stage}: {message}"
    print(log_line)
    with open('logs/training.log', 'a') as f:
        f.write(log_line + '\n')

# 使用示例
log_training_progress("DATA_PREP", "加载标签数据...")
log_training_progress("DATA_PREP", f"标签数据加载完成: {len(labels)} 条")
log_training_progress("FEATURE", "计算技术指标...")
```

### TensorBoard 可视化（可选）

```python
from torch.utils.tensorboard import SummaryWriter

writer = SummaryWriter('logs/tensorboard')

# 记录指标
for epoch in range(100):
    # ... 训练代码 ...
    writer.add_scalar('Loss/train', train_loss, epoch)
    writer.add_scalar('AUC/val', val_auc, epoch)

writer.close()
```
