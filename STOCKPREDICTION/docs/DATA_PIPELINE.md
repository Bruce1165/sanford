# 数据流程

## 概述

数据流程描述数据从 NeoTrade2 项目到最终预测结果的完整流转过程。

## 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        NeoTrade2 (只读)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  stock_data.db                                         │   │
│  │  ├── stocks (股票基本信息)                             │   │
│  │  └── daily_prices (日线行情)                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  screeners/ (筛选器)                                    │   │
│  │  ├── coffee_cup_screener.py                           │   │
│  │  ├── jin_feng_huang_screener.py                       │   │
│  │  └── ... (12个筛选器)                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 读取 (READ ONLY)
┌─────────────────────────────────────────────────────────────────┐
│                     STOCKPREDICTION (读写)                      │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  1. 标签生成阶段                                         │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  backtest_labels.py                              │  │   │
│  │  │  ↓                                               │  │   │
│  │  │  data/labels.db                                  │  │   │
│  │  │  └── training_labels (训练标签)                   │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  2. 特征计算阶段                                         │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  compute_features.py                              │  │   │
│  │  │  ↓                                               │  │   │
│  │  │  data/features.db                                │  │   │
│  │  │  └── stock_features (技术特征)                    │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  3. 筛选器特征收集                                       │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  collect_screener_scores.py                       │  │   │
│  │  │  ↓                                               │  │   │
│  │  │  data/screener_scores.db                         │  │   │
│  │  │  └── screener_features (筛选器特征)               │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  4. 数据整合与预处理                                     │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  - 合并 labels + features + screener_features    │  │   │
│  │  │  - 缺失值处理                                     │  │   │
│  │  │  - 特征标准化                                     │  │   │
│  │  │  - 特征选择                                       │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  5. 模型训练                                             │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  train_model.py                                  │  │   │
│  │  │  ↓                                               │  │   │
│  │  │  models/xgboost_model.json                        │  │   │
│  │  │  models/model_metadata.json                      │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  6. 每日预测                                             │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  predict.py                                      │  │   │
│  │  │  ↓                                               │  │   │
│  │  │  data/predictions.db                            │  │   │
│  │  │  └── predictions (预测结果)                      │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  7. 结果可视化                                           │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │  dashboard/                                      │  │   │
│  │  │  └── Flask/Dashboard UI                         │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 详细流程说明

### 阶段 1: 标签生成 (Label Generation)

**脚本**: `scripts/backtest_labels.py`

**输入**:
- NeoTrade2 `stock_data.db` 中的 `daily_prices` 表

**处理逻辑**:
```python
for each trading_date:
    for each stock:
        # 向前看 21-34 天
        future_prices = get_future_prices(code, date, days=34)
        max_gain = calculate_max_gain(future_prices)

        # 生成标签
        label = 1 if max_gain >= 0.20 else 0
```

**输出**:
- `data/labels.db` 的 `training_labels` 表

**数据量**:
- 约 4,600 只股票 × 200 个交易日 ≈ 920,000 条记录
- 预计正样本率: 5-10%

---

### 阶段 2: 特征计算 (Feature Computation)

**脚本**: `scripts/compute_features.py`

**输入**:
- NeoTrade2 `stock_data.db` 中的 `daily_prices` 表

**计算的特征**:

| 类别 | 特征 | 计算 |
|------|------|------|
| 趋势 | ma5, ma10, ma20, ma60 | 移动平均 |
| | ema12, ema26 | 指数移动平均 |
| | macd, macd_signal, macd_hist | MACD |
| 动量 | rsi | RSI(14) |
| | return_3d, 5d, 10d, 20d, 60d | 收益率 |
| 波动 | atr | ATR(14) |
| | bollinger_upper, middle, lower, pct | 布林带 |
| | stoch_k, stoch_d | KDJ |
| | volatility_10d, 20d, 60d | 波动率 |
| 成交量 | vol_ratio_5d, 20d | 量比 |

**输出**:
- `data/features.db` 的 `stock_features` 表

**数据量**:
- 约 4,600 只股票 × 200 个交易日 ≈ 920,000 条记录
- 每条记录约 35 个特征

---

### 阶段 3: 筛选器特征收集 (Screener Feature Collection)

**脚本**: `scripts/collect_screener_scores.py`

**输入**:
- NeoTrade2 `screeners/` 目录下的筛选器脚本

**处理逻辑**:
```python
for each screener in SCREENER_FEATURES:
    for each trading_date:
        for each stock:
            # 运行筛选器
            result = screener.screen_stock(code, name)

            # 保存特征
            save_feature({
                'code': code,
                'trade_date': date,
                'screener_name': screener_name,
                'hit': result is not None,
                'score': result.get('score', 0)
            })
```

**筛选器列表**:
1. coffee_cup_screener
2. coffee_cup_handle_screener_v4
3. jin_feng_huang_screener
4. yin_feng_huang_screener
5. shi_pan_xian_screener
6. er_ban_hui_tiao_screener
7. zhang_ting_bei_liang_yin_screener
8. breakout_20day_screener
9. breakout_main_screener
10. daily_hot_cold_screener
11. shuang_shou_ban_screener
12. ashare_21_screener

**输出**:
- `data/screener_scores.db` 的 `screener_features` 表

**数据量**:
- 约 4,600 只股票 × 200 个交易日 × 12 筛选器 ≈ 11,040,000 条记录

---

### 阶段 4: 数据整合 (Data Integration)

**脚本**: `scripts/train_model.py` 中的数据准备部分

**处理步骤**:

```python
# 1. 加载数据
labels = load_from_db("data/labels.db")
features = load_from_db("data/features.db")
screener_features = load_from_db("data/screener_scores.db")

# 2. 合并基础数据
data = labels.merge(features, on=['code', 'base_date'])

# 3. 编码筛选器特征
screener_pivot = screener_features.pivot(
    index=['code', 'trade_date'],
    columns='screener_name',
    values='hit',
    fill_value=0
)

# 4. 最终合并
data = data.merge(screener_pivot, on=['code', 'trade_date'])

# 5. 特征选择
selected_features = [
    # 技术指标
    'ma5', 'ma10', 'ma20', 'rsi', 'macd', 'atr', 'bollinger_pct',
    'return_5d', 'return_10d', 'volatility_20d', 'vol_ratio_5d',
    # 筛选器特征 (二进制)
    'coffee_cup_screener', 'jin_feng_huang_screener', ...
]

# 6. 时间序列分割
train = data[data['base_date'] <= '2025-12-31']
val = data[data['base_date'].between('2026-01-01', '2026-02-28')]
test = data[data['base_date'] >= '2026-03-01']
```

---

### 阶段 5: 模型训练 (Model Training)

**脚本**: `scripts/train_model.py`

**处理流程**:

```python
# 1. 特征预处理
X_train, y_train = prepare_data(train_data)
X_val, y_val = prepare_data(val_data)

# 2. 模型训练
model = xgb.XGBClassifier(**params)
model.fit(X_train, y_train,
          eval_set=[(X_val, y_val)],
          early_stopping_rounds=50)

# 3. 模型评估
metrics = evaluate_model(model, X_test, y_test)

# 4. 保存模型
model.save_model('models/xgboost_model.json')
save_metadata('models/metadata.json', metrics)
```

**输出**:
- `models/xgboost_model.json` - 模型文件
- `models/model_metadata.json` - 模型元数据
- `data/predictions.db` 的 `model_performance` 表

---

### 阶段 6: 每日预测 (Daily Prediction)

**脚本**: `scripts/predict.py`

**处理流程**:

```python
# 1. 获取最新数据
date = get_latest_trading_date()

# 2. 计算特征（当天）
features_today = compute_features(date)
screener_features_today = run_screeners(date)

# 3. 加载模型
model = load_model('models/xgboost_model.json')

# 4. 预测
X = prepare_features(features_today, screener_features_today)
probabilities = model.predict_proba(X)[:, 1]

# 5. 保存结果
predictions = pd.DataFrame({
    'code': stocks,
    'name': names,
    'probability': probabilities,
    'prediction_date': date
})
save_predictions(predictions)
```

**输出**:
- `data/predictions.db` 的 `predictions` 表

---

### 阶段 7: 结果可视化 (Visualization)

**脚本**: `dashboard/app.py` (待开发)

**展示内容**:
- 今日 Top 50 预测股票
- 历史预测准确率
- 特征重要性
- 个股预测详情
- 回测收益曲线

---

## 数据依赖关系

```
NeoTrade2/stock_data.db
    │
    ├─→ labels.db (backtest_labels.py)
    │
    ├─→ features.db (compute_features.py)
    │
    └─→ screener_scores.db (collect_screener_scores.py)
            │
            ↓
        训练数据集 (labels + features + screener_features)
            │
            ↓
        模型训练 (train_model.py)
            │
            ↓
        模型文件 (models/*.json)
            │
            ↓
        每日预测 (predict.py)
            │
            ↓
        预测结果 (predictions.db)
            │
            ↓
        Dashboard 可视化
```

## 数据质量检查点

### 1. 标签生成后

```python
# 检查标签分布
label_stats = pd.read_sql("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN label = 1 THEN 1 ELSE 0 END) as positive,
        SUM(CASE WHEN label = 0 THEN 1 ELSE 0 END) as negative
    FROM training_labels
""", labels_db)

assert label_stats['positive'][0] > 0, "没有正样本"
assert label_stats['positive'][0] / label_stats['total'][0] > 0.01, "正样本率过低"
```

### 2. 特征计算后

```python
# 检查特征完整性
feature_stats = pd.read_sql("""
    SELECT
        COUNT(*) as total,
        COUNT(ma5) as ma5_count,
        COUNT(rsi) as rsi_count,
        COUNT(macd) as macd_count
    FROM stock_features
""", features_db)

assert feature_stats['ma5_count'][0] / feature_stats['total'][0] > 0.95, "ma5 缺失率过高"
```

### 3. 数据合并后

```python
# 检查数据对齐
merged = pd.read_sql("""
    SELECT l.code, l.base_date, l.label, f.ma5, f.rsi
    FROM training_labels l
    LEFT JOIN stock_features f ON l.code = f.code AND l.base_date = f.trade_date
""", labels_db)

assert merged['ma5'].notna().sum() / len(merged) > 0.9, "合并后数据缺失过多"
```

## 数据更新策略

### 增量更新

对于每日新数据，采用增量更新策略：

```python
# 1. 获取最新数据日期
latest_date = get_latest_date(source_db)

# 2. 只处理新增日期
new_dates = get_trading_dates(latest_date, latest_date + timedelta(days=7))

# 3. 增量计算特征
for date in new_dates:
    compute_features(date=date)
    collect_screener_scores(date=date)
```

### 全量更新

定期（如每周）进行全量重新计算，确保数据一致性：

```bash
# 每周日凌晨执行
python scripts/backtest_labels.py --start-date 2024-09-01 --overwrite
python scripts/compute_features.py --start-date 2024-09-01 --overwrite
python scripts/collect_screener_scores.py --start-date 2024-09-01 --overwrite
```

## 数据备份

### 备份策略

```bash
# 每日备份
cp data/*.db backups/daily/$(date +%Y%m%d)/

# 每周完整备份
tar -czf backups/weekly/$(date +%Y%m%d).tar.gz data/ models/
```

### 恢复流程

```bash
# 从备份恢复
cp backups/daily/20260414/*.db data/
cp backups/weekly/20260414/*.json models/
```
