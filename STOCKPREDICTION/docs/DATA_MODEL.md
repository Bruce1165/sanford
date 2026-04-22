# 数据模型

## 概述

本项目使用 SQLite 作为本地数据库，存储训练标签、特征和预测结果。所有数据模型定义在 `models/database.py` 中。

## 数据库列表

| 数据库 | 路径 | 用途 |
|--------|------|------|
| `labels.db` | `data/labels.db` | 存储训练标签（通过历史回测生成） |
| `features.db` | `data/features.db` | 存储技术指标特征 |
| `screener_scores.db` | `data/screener_scores.db` | 存储 NeoTrade2 筛选器特征 |
| `predictions.db` | `data/predictions.db` | 存储预测结果 |

## 表结构

### 1. training_labels - 训练标签表

存储通过历史回测生成的训练标签，标记哪些股票在未来 21-34 个交易日内上涨 20%+。

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 主键（自增） |
| `code` | String(10) | YES | 股票代码（如 000001.SZ） |
| `name` | String(50) | NO | 股票名称 |
| `base_date` | String(10) | YES | 基准日期（预测日期，YYYY-MM-DD） |
| `label` | Integer | NO | 标签：1=后续21-34天涨20%+, 0=未达到 |
| `max_gain` | Float | NO | 后续最大涨幅（小数，如 0.25 表示 25%） |
| `max_gain_date` | String(10) | NO | 达到最大涨幅的日期 |
| `max_gain_days` | Integer | NO | 达到最大涨幅的天数 |
| `horizon_min` | Integer | NO | 最短持有天数（默认 21） |
| `horizon_max` | Integer | NO | 最长持有天数（默认 34） |
| `target_gain` | Float | NO | 目标涨幅（默认 0.20） |
| `created_at` | DateTime | NO | 创建时间 |

**示例数据**:
```
code: 000001.SZ
name: 平安银行
base_date: 2025-12-01
label: 1
max_gain: 0.285
max_gain_date: 2025-12-20
max_gain_days: 19
```

**索引**:
- `(code)` - 按股票代码查询
- `(base_date)` - 按日期查询
- `(code, base_date)` - 联合查询

---

### 2. stock_features - 股票特征表

存储所有技术指标特征，用于模型训练和预测。

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 主键（自增） |
| `code` | String(10) | YES | 股票代码 |
| `trade_date` | String(10) | YES | 交易日期 |
| **价格数据** | | | |
| `close` | Float | NO | 收盘价 |
| `pct_change` | Float | NO | 涨跌幅（小数） |
| `volume` | Float | NO | 成交量（股） |
| `amount` | Float | NO | 成交额（元） |
| `turnover` | Float | NO | 换手率 |
| **移动平均线** | | | |
| `ma5` | Float | NO | 5日移动平均 |
| `ma10` | Float | NO | 10日移动平均 |
| `ma20` | Float | NO | 20日移动平均 |
| `ma60` | Float | NO | 60日移动平均 |
| **EMA & MACD** | | | |
| `ema12` | Float | NO | 12日指数移动平均 |
| `ema26` | Float | NO | 26日指数移动平均 |
| `macd` | Float | NO | MACD 值 |
| `macd_signal` | Float | NO | MACD 信号线 |
| `macd_hist` | Float | NO | MACD 柱状图 |
| **动量指标** | | | |
| `rsi` | Float | NO | RSI (相对强弱指标, 0-100) |
| `atr` | Float | NO | ATR (平均真实波幅) |
| **布林带** | | | |
| `bollinger_upper` | Float | NO | 布林带上轨 |
| `bollinger_middle` | Float | NO | 布林带中轨 |
| `bollinger_lower` | Float | NO | 布林带下轨 |
| `bollinger_pct` | Float | NO | 价格在布林带中的位置 (0-1) |
| **KDJ** | | | |
| `stoch_k` | Float | NO | K 值 (0-100) |
| `stoch_d` | Float | NO | D 值 (0-100) |
| **历史收益** | | | |
| `return_3d` | Float | NO | 3日收益率 |
| `return_5d` | Float | NO | 5日收益率 |
| `return_10d` | Float | NO | 10日收益率 |
| `return_20d` | Float | NO | 20日收益率 |
| `return_60d` | Float | NO | 60日收益率 |
| **波动率** | | | |
| `volatility_10d` | Float | NO | 10日波动率 |
| `volatility_20d` | Float | NO | 20日波动率 |
| `volatility_60d` | Float | NO | 60日波动率 |
| **成交量** | | | |
| `vol_ratio_5d` | Float | NO | 成交量5日均量比率 |
| `vol_ratio_20d` | Float | NO | 成交量20日均量比率 |
| **相对表现** | | | |
| `rel_to_market` | Float | NO | 相对大盘涨跌幅 |
| `rel_to_industry` | Float | NO | 相对行业涨跌幅 |
| **元数据** | | | |
| `updated_at` | DateTime | NO | 更新时间 |

**索引**:
- `(code)` - 按股票代码查询
- `(trade_date)` - 按日期查询

---

### 3. screener_features - 筛选器特征表

存储从 NeoTrade2 筛选器收集的特征数据。

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 主键（自增） |
| `code` | String(10) | YES | 股票代码 |
| `trade_date` | String(10) | YES | 交易日期 |
| `screener_name` | String(50) | YES | 筛选器名称 |
| `hit` | Boolean | NO | 是否命中（True/False） |
| `score` | Float | NO | 筛选器分数（如果有） |
| `reason` | Text | NO | 命中原因 |
| `extra_data` | Text | NO | 额外数据（JSON 字符串） |
| `created_at` | DateTime | NO | 创建时间 |

**筛选器列表**:
- `coffee_cup_screener` - 咖啡杯柄形态
- `coffee_cup_handle_screener_v4` - 咖啡杯柄 V4
- `jin_feng_huang_screener` - 涨停金凤凰
- `yin_feng_huang_screener` - 涨停银凤凰
- `shi_pan_xian_screener` - 涨停试盘线
- `er_ban_hui_tiao_screener` - 二板回踩
- `zhang_ting_bei_liang_yin_screener` - 涨停倍量阴
- `breakout_20day_screener` - 20日突破
- `breakout_main_screener` - 主升突破
- `daily_hot_cold_screener` - 每日冷热
- `shuang_shou_ban_screener` - 双手板
- `ashare_21_screener` - A股21综合

**索引**:
- `(code)` - 按股票代码查询
- `(trade_date)` - 按日期查询
- `(screener_name)` - 按筛选器查询

---

### 4. predictions - 预测结果表

存储模型预测结果。

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 主键（自增） |
| `code` | String(10) | YES | 股票代码 |
| `name` | String(50) | NO | 股票名称 |
| `prediction_date` | String(10) | YES | 预测日期 |
| `probability` | Float | NO | 预测概率（0-1） |
| `label` | Integer | NO | 实际标签（回填，1/0/NULL） |
| `model_name` | String(50) | NO | 模型名称 |
| `model_version` | String(20) | NO | 模型版本 |
| `rank` | Integer | NO | 当天预测排名 |
| `features_importance` | Text | NO | 特征重要性（JSON） |
| `notes` | Text | NO | 备注 |
| `created_at` | DateTime | NO | 创建时间 |
| `updated_at` | DateTime | NO | 更新时间 |

**索引**:
- `(code)` - 按股票代码查询
- `(prediction_date)` - 按预测日期查询

---

### 5. model_performance - 模型性能记录表

存储模型训练和回测的性能指标。

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | Integer | PK | 主键（自增） |
| `model_name` | String(50) | YES | 模型名称 |
| `model_version` | String(20) | NO | 模型版本 |
| **数据范围** | | | |
| `train_start` | String(10) | NO | 训练起始日期 |
| `train_end` | String(10) | NO | 训练结束日期 |
| `test_start` | String(10) | NO | 测试起始日期 |
| `test_end` | String(10) | NO | 测试结束日期 |
| **分类指标** | | | |
| `precision` | Float | NO | 精确率 |
| `recall` | Float | NO | 召回率 |
| `f1_score` | Float | NO | F1 分数 |
| `auc` | Float | NO | AUC 值 |
| `precision_at_10` | Float | NO | Top10 精确率 |
| `precision_at_50` | Float | NO | Top50 精确率 |
| `precision_at_100` | Float | NO | Top100 精确率 |
| **回测指标** | | | |
| `avg_return` | Float | NO | 平均收益 |
| `win_rate` | Float | NO | 胜率 |
| `max_drawdown` | Float | NO | 最大回撤 |
| **元数据** | | | |
| `notes` | Text | NO | 备注 |
| `created_at` | DateTime | NO | 创建时间 |

**索引**:
- `(model_name)` - 按模型名称查询

---

## 数据库关系图

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ training_labels │         │ stock_features  │         │ screener_      │
│                 │         │                 │         │   features      │
│ code (FK) ─────┼────────→│ code (PK/FK)   │←────────┤ code (FK) ─────┼────┐
│ base_date       │         │ trade_date (PK) │         │ trade_date (PK) │    │
│ label           │         │ ma5, rsi, ...  │         │ screener_name   │    │
└─────────────────┘         └─────────────────┘         └─────────────────┘    │
         │                                                                │
         │                ┌─────────────────┐                               │
         └───────────────→│   predictions   │←──────────────────────────────┘
                          │                 │
                          │ code (FK) ─────┼───┐
                          │ prediction_date │    │
                          │ probability     │    │
                          │ model_name ──────┼────┼───┐
                          └─────────────────┘    │    │
                                                 │    │
                          ┌───────────────────────┼────┘
                          │                       │
                    ┌─────┴─────────┐      ┌──────┴──────┐
                    │   stock_     │      │ screener_   │
                    │   features   │      │   features  │
                    │   (特征)      │      │   (特征)     │
                    └───────────────┘      └─────────────┘
```

## 数据生命周期

1. **训练阶段**:
   - NeoTrade2 数据库 (只读) → labels.db (标签)
   - NeoTrade2 数据库 (只读) → features.db (特征)
   - NeoTrade2 筛选器 → screener_scores.db (筛选器特征)

2. **预测阶段**:
   - features.db + screener_scores.db → 模型 → predictions.db

3. **验证阶段**:
   - predictions.db + labels.db (实际数据回填) → model_performance

## 数据库操作

### 初始化数据库

```python
from models.database import init_db
from scripts.config import LABELS_DB, FEATURES_DB, SCREENER_SCORES_DB, PREDICTIONS_DB

# 初始化所有数据库
for db_path in [LABELS_DB, FEATURES_DB, SCREENER_SCORES_DB, PREDICTIONS_DB]:
    init_db(db_path)
```

### 查询示例

```python
import sqlite3
from scripts.config import LABELS_DB

# 查询某日期的标签
with sqlite3.connect(str(LABELS_DB)) as conn:
    df = pd.read_sql_query("""
        SELECT * FROM training_labels
        WHERE base_date = '2025-12-01'
    """, conn)
```

## 数据质量保证

### 数据验证规则

1. **标签验证**:
   - `label` 只能是 0 或 1
   - `max_gain` 必须 ≥ 0
   - `max_gain_days` 必须在 [horizon_min, horizon_max] 范围内

2. **特征验证**:
   - RSI 必须在 [0, 100] 范围内
   - `bollinger_pct` 必须在 [0, 1] 范围内
   - `stoch_k`, `stoch_d` 必须在 [0, 100] 范围内

3. **预测验证**:
   - `probability` 必须在 [0, 1] 范围内
   - `rank` 必须为正整数
