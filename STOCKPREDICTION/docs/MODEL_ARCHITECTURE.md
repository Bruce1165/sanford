# 模型架构

## 概述

本项目使用监督学习方法，将股票预测问题建模为二分类问题：预测股票在未来 21-34 个交易日内是否上涨 20%+。

## 问题定义

### 标签定义

| 类别 | 定义 | 标签值 |
|------|------|--------|
| 正样本 | 未来 21-34 天内最大涨幅 ≥ 20% | 1 |
| 负样本 | 未来 21-34 天内最大涨幅 < 20% | 0 |

### 损失函数

由于样本不平衡（正样本率约 5-10%），使用加权损失函数：

```
Loss = -w_pos * y * log(p) - w_neg * (1-y) * log(1-p)
```

其中：
- `w_pos`: 正样本权重（通常较高）
- `w_neg`: 负样本权重

## 模型架构

### 整体架构

```
                    ┌─────────────────────────────────┐
                    │      Feature Engineering        │
                    │  (Technical + Screener + Rel)   │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │      Feature Preprocessing       │
                    │  (缺失值处理 + 标准化 + 选择)     │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │         Model Layer               │
                    │  (XGBoost / LightGBM)            │
                    │  ┌─────────────────────────────┐  │
                    │  │  Gradient Boosted Trees    │  │
                    │  │  - 100-500 trees           │  │
                    │  │  - max_depth: 4-8          │  │
                    │  │  - learning_rate: 0.01-0.1  │  │
                    │  └─────────────────────────────┘  │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │      Output Layer                │
                    │  (Probability: 0-1)               │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │      Post-processing             │
                    │  (Top-K 选择 + 阈值过滤)         │
                    └─────────────────────────────────┘
```

### XGBoost 模型配置

```python
xgb_params = {
    # 基本参数
    'n_estimators': 300,          # 树的数量
    'max_depth': 6,               # 树的最大深度
    'learning_rate': 0.05,        # 学习率
    'subsample': 0.8,             # 样本采样率
    'colsample_bytree': 0.8,      # 特征采样率

    # 正则化
    'reg_alpha': 0.1,             # L1 正则化
    'reg_lambda': 1.0,            # L2 正则化
    'min_child_weight': 3,        # 最小子节点权重

    # 不平衡处理
    'scale_pos_weight': (neg_samples / pos_samples) * 0.5,

    # 其他
    'random_state': 42,
    'n_jobs': -1,
    'eval_metric': 'auc'
}
```

### LightGBM 模型配置

```python
lgb_params = {
    'objective': 'binary',
    'metric': 'auc',

    # 树参数
    'num_leaves': 31,             # 叶子节点数
    'max_depth': -1,              # -1 表示无限制
    'min_data_in_leaf': 20,       # 叶子最小样本数

    # 学习参数
    'learning_rate': 0.05,
    'n_estimators': 300,
    'feature_fraction': 0.8,      # 特征采样
    'bagging_fraction': 0.8,      # 样本采样
    'bagging_freq': 5,

    # 正则化
    'lambda_l1': 0.1,
    'lambda_l2': 1.0,

    # 其他
    'verbosity': -1,
    'random_state': 42,
    'is_unbalance': True
}
```

## 训练流程

### 1. 数据准备

```python
# 1. 加载标签
labels = pd.read_sql("SELECT * FROM training_labels", labels_db)

# 2. 加载特征
features = pd.read_sql("SELECT * FROM stock_features", features_db)
screener_features = pd.read_sql("SELECT * FROM screener_features", screener_db)

# 3. 合并数据
data = labels.merge(features, on=['code', 'base_date'])
data = data.merge(screener_features, on=['code', 'base_date'], how='left')

# 4. 编码筛选器特征
screener_pivot = screener_features.pivot_table(
    index=['code', 'trade_date'],
    columns='screener_name',
    values='hit',
    fill_value=0
).reset_index()

# 5. 最终合并
data = data.merge(screener_pivot, on=['code', 'trade_date'])
```

### 2. 特征工程

```python
from sklearn.preprocessing import RobustScaler
from sklearn.impute import SimpleImputer

# 缺失值处理
imputer = SimpleImputer(strategy='median')
X_imputed = imputer.fit_transform(X)

# 标准化
scaler = RobustScaler()
X_scaled = scaler.fit_transform(X_imputed)

# 特征选择
from sklearn.feature_selection import SelectKBest, f_classif
selector = SelectKBest(f_classif, k=30)
X_selected = selector.fit_transform(X_scaled, y)
```

### 3. 数据分割（时间序列）

```python
# 按时间分割，不随机打乱
train_end = '2025-12-31'
val_start = '2026-01-01'
val_end = '2026-02-28'
test_start = '2026-03-01'

train_data = data[data['base_date'] <= train_end]
val_data = data[(data['base_date'] >= val_start) & (data['base_date'] <= val_end)]
test_data = data[data['base_date'] >= test_start]

X_train, y_train = train_data[feature_cols], train_data['label']
X_val, y_val = val_data[feature_cols], val_data['label']
X_test, y_test = test_data[feature_cols], test_data['label']
```

### 4. 模型训练

```python
import xgboost as xgb
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

# 创建 DMatrix
dtrain = xgb.DMatrix(X_train, label=y_train)
dval = xgb.DMatrix(X_val, label=y_val)

# 训练
model = xgb.train(
    params,
    dtrain,
    num_boost_round=1000,
    evals=[(dtrain, 'train'), (dval, 'val')],
    early_stopping_rounds=50,
    verbose_eval=10
)

# 预测
dtest = xgb.DMatrix(X_test)
y_pred_proba = model.predict(dtest)
y_pred = (y_pred_proba > 0.5).astype(int)

# 评估
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_pred_proba)
```

## 验证策略

### Walk-Forward Validation

由于金融时间序列的非平稳性，使用滚动窗口验证：

```
训练窗口                    验证窗口
├─────────────────────────┤├────┤
│                        ││    │
│                        ││    │
└─────────────────────────┘└────┘
     ↓ 滚动
├─────────────────────────┤├────┤
│                        ││    │
└─────────────────────────┘└────┘
```

### 实现代码

```python
def walk_forward_validation(data, feature_cols, window_size=90, val_size=30):
    """Walk-Forward 交叉验证"""
    results = []

    dates = sorted(data['base_date'].unique())

    for i in range(window_size, len(dates) - val_size, val_size):
        train_dates = dates[i-window_size:i]
        val_dates = dates[i:i+val_size]

        train_data = data[data['base_date'].isin(train_dates)]
        val_data = data[data['base_date'].isin(val_dates)]

        X_train, y_train = train_data[feature_cols], train_data['label']
        X_val, y_val = val_data[feature_cols], val_data['label']

        # 训练模型
        model = train_model(X_train, y_train)

        # 预测
        y_pred = model.predict(X_val)
        y_proba = model.predict_proba(X_val)[:, 1]

        # 评估
        metrics = evaluate(y_val, y_pred, y_proba)
        results.append({
            'val_start': val_dates[0],
            'val_end': val_dates[-1],
            **metrics
        })

    return pd.DataFrame(results)
```

### 评估指标

#### 分类指标

| 指标 | 公式 | 说明 |
|------|------|------|
| Precision | TP / (TP + FP) | 预测为正的样本中实际为正的比例 |
| Recall | TP / (TP + FN) | 实际为正的样本中被正确预测的比例 |
| F1-Score | 2 × (Precision × Recall) / (Precision + Recall) | Precision 和 Recall 的调和平均 |
| AUC | - | ROC 曲线下面积 |
| Precision@K | TP@K / K | Top K 预测中的精确率 |

#### 回测指标

| 指标 | 公式 | 说明 |
|------|------|------|
| Win Rate | 盈利次数 / 总交易次数 | 胜率 |
| Average Return | 平均收益 | 平均每笔交易的收益 |
| Max Drawdown | 最大回撤 | 最大连续亏损 |
| Sharpe Ratio | (收益 - 无风险) / 波动 | 夏普比率 |

## 模型解释

### SHAP 值分析

```python
import shap

# 计算 SHAP 值
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# 特征重要性图
shap.summary_plot(shap_values, X_test, plot_type="bar")

# 依赖图
shap.dependence_plot("rsi", shap_values, X_test)

# 单样本解释
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])
```

### 特征重要性输出

```
特征重要性排名 (Top 20)
===================================
1. rsi                0.1234    动量指标
2. return_5d          0.0987    短期收益
3. ma20               0.0876    趋势指标
4. bollinger_pct      0.0765    波动率指标
5. vol_ratio_5d       0.0654    成交量指标
6. coffee_cup_hit     0.0543    筛选器特征
7. rel_to_market      0.0432    相对表现
8. macd_hist          0.0321    MACD指标
9. atr                0.0210    波动率指标
10. return_20d        0.0198    中期收益
...
```

## 模型优化

### 超参数调优

```python
from sklearn.model_selection import ParameterGrid
from sklearn.metrics import f1_score

param_grid = {
    'n_estimators': [100, 300, 500],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'subsample': [0.7, 0.8, 0.9],
    'colsample_bytree': [0.7, 0.8, 0.9],
}

best_score = 0
best_params = None

for params in ParameterGrid(param_grid):
    model = xgb.XGBClassifier(**params, scale_pos_weight=scale_pos_weight)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    score = f1_score(y_val, y_pred)

    if score > best_score:
        best_score = score
        best_params = params

print(f"最佳参数: {best_params}")
print(f"最佳 F1: {best_score}")
```

### 贝叶斯优化

```python
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials

def objective(params):
    model = xgb.XGBClassifier(
        n_estimators=int(params['n_estimators']),
        max_depth=int(params['max_depth']),
        learning_rate=params['learning_rate'],
        subsample=params['subsample'],
        colsample_bytree=params['colsample_bytree'],
        scale_pos_weight=scale_pos_weight,
        n_jobs=-1
    )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_val)
    score = f1_score(y_val, y_pred)

    return {'loss': -score, 'status': STATUS_OK}

space = {
    'n_estimators': hp.quniform('n_estimators', 100, 500, 50),
    'max_depth': hp.quniform('max_depth', 3, 10, 1),
    'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.2)),
    'subsample': hp.uniform('subsample', 0.6, 1.0),
    'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
}

trials = Trials()
best = fmin(fn=objective, space=space, algo=tpe.suggest, max_evals=100, trials=trials)
```

## 模型部署

### 模型保存

```python
import joblib
import json

# 保存模型
model.save_model('models/xgboost_model.json')

# 保存元数据
metadata = {
    'model_name': 'xgboost_stock_predictor',
    'version': '1.0.0',
    'train_date_range': ['2024-09-01', '2025-12-31'],
    'features': feature_cols.tolist(),
    'params': params,
    'metrics': {
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'auc': auc
    }
}

with open('models/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)
```

### 模型加载

```python
import xgboost as xgb

# 加载模型
model = xgb.XGBClassifier()
model.load_model('models/xgboost_model.json')

# 加载元数据
with open('models/metadata.json', 'r') as f:
    metadata = json.load(f)

# 预测
def predict_stock(model, features, metadata):
    X = features[metadata['features']]
    probability = model.predict_proba(X)[:, 1]
    return probability
```

## 模型监控

### 性能监控

```python
def monitor_model_performance(predictions, actuals, threshold=0.5):
    """监控模型性能"""
    metrics = {
        'precision': precision_score(actuals, predictions > threshold),
        'recall': recall_score(actuals, predictions > threshold),
        'f1': f1_score(actuals, predictions > threshold),
        'auc': roc_auc_score(actuals, predictions),
    }

    # 检查性能下降
    if metrics['precision'] < 0.15:  # 阈值
        send_alert(f"模型性能下降: Precision = {metrics['precision']:.2%}")

    return metrics
```

### 数据漂移检测

```python
def detect_data_drift(new_features, reference_features, threshold=0.1):
    """检测数据漂移"""
    from scipy import stats

    drift_detected = False
    drift_report = {}

    for feature in new_features.columns:
        # KS 检验
        ks_stat, p_value = stats.ks_2samp(
            new_features[feature],
            reference_features[feature]
        )

        if ks_stat > threshold:
            drift_detected = True
            drift_report[feature] = {
                'ks_statistic': ks_stat,
                'p_value': p_value,
                'status': 'DRIFT'
            }

    return drift_detected, drift_report
```
