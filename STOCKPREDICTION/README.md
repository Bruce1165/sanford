# STOCKPREDICTION - 股票上涨潜力预测研究

## 项目简介

STOCKPREDICTION 是一个基于机器学习的股票预测研究项目，目标是通过历史数据分析，预测未来 21-34 个交易日内有潜力上涨 20%+ 的股票。

**研究目标**: 预测 A 股市场中未来 21-34 个交易日内上涨 20% 的潜力股

**数据来源**: NeoTrade2 项目历史数据（4,663 只 A 股）

**技术路线**: 特征工程 + 机器学习 (XGBoost/LightGBM) + 时间序列验证

## 快速开始

### 1. 环境配置

```bash
# 进入项目目录
cd /Users/mac/NeoTrade2/STOCKPREDICTION

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据准备

```bash
# 生成训练标签（回测找出 20%+ 上涨股）
python scripts/backtest_labels.py --start-date 2024-09-01 --end-date 2026-03-31

# 计算技术指标特征
python scripts/compute_features.py --start-date 2024-09-01 --end-date 2026-03-31

# 收集 NeoTrade2 筛选器特征
python scripts/collect_screener_scores.py --start-date 2024-09-01 --end-date 2026-03-31
```

### 3. 模型训练

```bash
# 训练 XGBoost 模型
python scripts/train_model.py --model xgboost --cv 5
```

### 4. 每日预测

```bash
# 运行预测
python scripts/predict.py --model models/xgboost_model.json
```

## 项目结构

```
STOCKPREDICTION/
├── docs/                   # 技术文档
│   ├── INDEX.md            # 文档索引
│   ├── DATA_MODEL.md       # 数据模型
│   ├── FEATURE_ENGINEERING.md  # 特征工程
│   ├── MODEL_ARCHITECTURE.md   # 模型架构
│   ├── API_REFERENCE.md    # API 参考
│   ├── DEVELOPMENT_GUIDE.md   # 开发指南
│   └── DEPLOYMENT_GUIDE.md    # 部署指南
├── data/                   # 数据目录
│   ├── labels.db           # 训练标签
│   ├── features.db         # 技术特征
│   ├── screener_scores.db  # 筛选器特征
│   └── predictions.db      # 预测结果
├── models/                 # 模型代码
│   └── database.py         # 数据库定义
├── scripts/                # 脚本
│   ├── config.py           # 配置中心
│   ├── backtest_labels.py  # 标签生成
│   ├── compute_features.py # 特征计算
│   └── collect_screener_scores.py  # 筛选器收集
├── notebooks/              # Jupyter 笔记本
├── dashboard/              # Dashboard UI
├── logs/                   # 日志
├── reports/                # 报告
├── CLAUDE.md              # Claude Code 指南
├── requirements.txt       # Python 依赖
└── RESEARCH_PLAN.md       # 研究计划
```

## 特征体系

### 技术指标特征 (35+ 个)
- **趋势**: MA(5,10,20,60), EMA(12,26), MACD
- **动量**: RSI, KDJ, 历史收益率
- **波动**: ATR, 布林带, 波动率
- **成交量**: 量比, 换手率

### 筛选器特征 (12 个)
- 咖啡杯柄、涨停金凤凰、涨停银凤凰、涨停试盘线
- 二板回踩、涨停倍量阴、20日突破、主升突破
- 每日冷热、双手板、A股21综合

### 市场相对特征 (4+ 个)
- 相对大盘表现
- 相对行业表现

## 模型性能

### 目标指标

| 指标 | 目标 |
|------|------|
| Precision@50 | > 20% |
| Precision@100 | > 15% |
| 胜率 | > 30% |
| AUC | > 0.70 |

### 验证策略
- 时间序列验证（Walk-Forward）
- 训练集: 2024-09-01 ~ 2025-12-31
- 验证集: 2026-01-01 ~ 2026-02-28
- 测试集: 2026-03-01 ~ 2026-03-31

## 研究流程

```
计划 (Plan) → 实施 (Implement) → 验证 (Verify) → 优化 (Optimize) → 循环 (Loop)
```

1. **计划**: 定义研究问题和成功指标
2. **实施**: 生成标签、计算特征、训练模型
3. **验证**: 评估性能、分析结果
4. **优化**: 调参、特征选择、模型改进
5. **循环**: 重复以上步骤

## 文档

- [技术文档索引](docs/INDEX.md) - 完整的技术文档
- [研究计划](RESEARCH_PLAN.md) - 详细的研究计划
- [开发指南](docs/DEVELOPMENT_GUIDE.md) - 如何参与开发
- [部署指南](docs/DEPLOYMENT_GUIDE.md) - 如何部署运行

## 注意事项

1. **只读访问 NeoTrade2**: 本项目只读取 NeoTrade2 的数据，不修改任何文件
2. **数据隔离**: 所有本地数据存储在 `data/` 目录下
3. **时间顺序**: 训练使用历史数据，预测只针对未来日期
4. **样本不平衡**: 正样本率约 5-10%，需要特殊处理

## 依赖

- Python 3.10+
- pandas, numpy
- xgboost, lightgbm
- scikit-learn
- SQLAlchemy
- TA-Lib (可选)

详细依赖见 [requirements.txt](requirements.txt)

## 许可证

本项目为研究项目，仅供个人学习使用。

## 联系方式

- 项目位置: `/Users/mac/NeoTrade2/STOCKPREDICTION`
- 上级项目: NeoTrade2
