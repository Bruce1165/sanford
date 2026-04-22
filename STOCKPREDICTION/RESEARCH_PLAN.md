# 股票预测研究计划

## 研究目标

**目标**: 预测未来 21-34 个交易日内上涨 20%+ 的潜力股

**数据来源**:
- 主数据: NeoTrade2 项目的历史股价数据（4,663 只 A 股）
- 辅助数据: 大盘指数、行业指数（可选）

**研究方法**: 计划 → 实施 → 验证 → 优化 → 循环

## 第一阶段：数据准备 (Week 1-2)

### 1.1 标签生成
- 运行 `backtest_labels.py` 生成训练标签
- 对每个交易日向后看 21-34 天，标记最大涨幅 ≥20% 的股票为正样本
- 预期正样本率: ~5-10%

**命令**:
```bash
python scripts/backtest_labels.py --start-date 2024-09-01 --end-date 2026-03-31 --overwrite
```

**输出**: `data/labels.db` - 包含所有股票在各个交易日的标签

### 1.2 特征计算
- 运行 `compute_features.py` 计算技术指标
- 计算移动平均、MACD、RSI、ATR、布林带、KDJ 等指标
- 计算历史收益率、波动率、成交量特征

**命令**:
```bash
python scripts/compute_features.py --start-date 2024-09-01 --end-date 2026-03-31 --overwrite
```

**输出**: `data/features.db` - 包含所有股票的技术指标特征

### 1.3 筛选器特征收集
- 运行 `collect_screener_scores.py` 收集 NeoTrade2 筛选器结果
- 将筛选器命中结果作为分类特征

**命令**:
```bash
python scripts/collect_screener_scores.py --start-date 2024-09-01 --end-date 2026-03-31 --overwrite
```

**输出**: `data/screener_scores.db` - 包含筛选器命中特征

### 1.4 市场相对特征（可选）
- 计算股票相对于大盘指数的收益
- 计算股票相对于行业指数的收益

## 第二阶段：模型开发 (Week 3-4)

### 2.1 特征工程
- 合并标签、技术特征、筛选器特征
- 特征选择：去除高相关性特征
- 特征标准化

### 2.2 基准模型
- 逻辑回归（可解释性强）
- 评估基准性能

### 2.3 主模型
- XGBoost / LightGBM
- 处理类别不平衡（SMOTE 或调整 class_weight）

### 2.4 时间序列验证
- 使用 Walk-Forward 验证
- 训练集: 2024-09-01 ~ 2025-12-31
- 验证集: 2026-01-01 ~ 2026-03-31

**输出**: `models/` 目录下的训练好的模型

## 第三阶段：模型验证 (Week 5)

### 3.1 性能评估
- Precision, Recall, F1, AUC
- Precision@K (Top 10, 50, 100 预测的精确率)
- 混淆矩阵

### 3.2 回测分析
- 模拟按预测结果选股的收益
- 计算胜率、平均收益、最大回撤

### 3.3 特征重要性
- 使用 SHAP 分析特征重要性
- 识别关键预测因子

## 第四阶段：优化迭代 (Week 6+)

### 4.1 超参数调优
- Grid Search / Bayesian Optimization
- 交叉验证选择最优参数

### 4.2 特征优化
- 添加新特征（如市场情绪、资金流向）
- 移除不重要的特征

### 4.3 模型集成
- 尝试模型融合（Stacking / Blending）

### 4.4 在线更新
- 每日运行预测
- 根据最新数据定期重新训练模型

## 成功指标

| 指标 | 目标 | 说明 |
|------|------|------|
| Precision@50 | >20% | Top 50 预测中至少有 10 只实际涨 20%+ |
| Precision@100 | >15% | Top 100 预测中至少有 15 只实际涨 20%+ |
| 胜率 | >30% | 预测正样本中实际达到目标的比率 |
| AUC | >0.70 | 模型区分能力 |

## 技术栈

- **语言**: Python 3.10+
- **数据处理**: pandas, numpy
- **数据库**: SQLite
- **技术分析**: TA-Lib
- **机器学习**: scikit-learn, XGBoost, LightGBM
- **可视化**: matplotlib, seaborn, plotly
- **实验跟踪**: Jupyter Notebook

## 数据流程图

```
NeoTrade2 数据库 (只读)
    ↓
┌─────────────────────────────────────┐
│  1. 标签生成 (backtest_labels.py)   │ → labels.db
├─────────────────────────────────────┤
│  2. 特征计算 (compute_features.py)  │ → features.db
├─────────────────────────────────────┤
│  3. 筛选器收集 (collect_screener_   │ → screener_scores.db
│               scores.py)            │
└─────────────────────────────────────┘
    ↓
特征合并 & 数据预处理
    ↓
┌─────────────────────────────────────┐
│  4. 模型训练 (train_model.py)       │ → models/*.pkl
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  5. 每日预测 (predict.py)           │ → predictions.db
└─────────────────────────────────────┘
    ↓
Dashboard 展示预测结果
```

## 风险与限制

1. **数据质量**: 依赖 NeoTrade2 数据完整性
2. **过拟合**: 需严格的时间序列验证
3. **市场变化**: 历史模式可能不适用于未来
4. **样本不平衡**: 正样本率低（~5-10%）
5. **黑天鹅事件**: 模型无法预测突发事件

## 下一步行动

1. 安装依赖: `pip install -r requirements.txt`
2. 生成标签: `python scripts/backtest_labels.py --start-date 2024-09-01 --end-date 2026-03-31`
3. 计算特征: `python scripts/compute_features.py --start-date 2024-09-01 --end-date 2026-03-31`
4. 开始模型训练
