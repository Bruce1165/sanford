# API 参考

## 概述

本文档描述项目中主要模块、类和函数的接口。

## 目录

- [数据层](#数据层)
- [特征工程](#特征工程)
- [模型层](#模型层)
- [预测服务](#预测服务)

---

## 数据层

### database.py

#### 类: TrainingLabel

训练标签数据模型。

**表名**: `training_labels`

**字段**:
- `id` (Integer): 主键
- `code` (String): 股票代码
- `name` (String): 股票名称
- `base_date` (String): 基准日期
- `label` (Integer): 标签 (0/1)
- `max_gain` (Float): 最大涨幅
- `max_gain_date` (String): 达到最大涨幅的日期
- `max_gain_days` (Integer): 达到最大涨幅的天数
- `horizon_min` (Integer): 最短持有天数
- `horizon_max` (Integer): 最长持有天数
- `target_gain` (Float): 目标涨幅
- `created_at` (DateTime): 创建时间

#### 类: StockFeature

股票特征数据模型。

**表名**: `stock_features`

**字段** (部分):
- `code` (String): 股票代码
- `trade_date` (String): 交易日期
- `close` (Float): 收盘价
- `pct_change` (Float): 涨跌幅
- `ma5`, `ma10`, `ma20`, `ma60` (Float): 移动平均线
- `rsi` (Float): RSI 指标
- `macd`, `macd_signal`, `macd_hist` (Float): MACD 指标
- ... (更多字段见 DATA_MODEL.md)

#### 类: ScreenerFeature

筛选器特征数据模型。

**表名**: `screener_features`

**字段**:
- `code` (String): 股票代码
- `trade_date` (String): 交易日期
- `screener_name` (String): 筛选器名称
- `hit` (Boolean): 是否命中
- `score` (Float): 筛选器分数
- `reason` (String): 命中原因
- `extra_data` (Text): 额外数据 (JSON)
- `created_at` (DateTime): 创建时间

#### 类: Prediction

预测结果数据模型。

**表名**: `predictions`

**字段**:
- `code` (String): 股票代码
- `name` (String): 股票名称
- `prediction_date` (String): 预测日期
- `probability` (Float): 预测概率
- `label` (Integer): 实际标签 (回填)
- `model_name` (String): 模型名称
- `model_version` (String): 模型版本
- `rank` (Integer): 当天预测排名
- `features_importance` (Text): 特征重要性 (JSON)
- `notes` (Text): 备注
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

#### 类: ModelPerformance

模型性能记录数据模型。

**表名**: `model_performance`

**字段**:
- `model_name` (String): 模型名称
- `model_version` (String): 模型版本
- `train_start` (String): 训练起始日期
- `train_end` (String): 训练结束日期
- `test_start` (String): 测试起始日期
- `test_end` (String): 测试结束日期
- `precision` (Float): 精确率
- `recall` (Float): 召回率
- `f1_score` (Float): F1 分数
- `auc` (Float): AUC 值
- `precision_at_10`, `precision_at_50`, `precision_at_100` (Float): Top K 精确率
- `avg_return` (Float): 平均收益
- `win_rate` (Float): 胜率
- `max_drawdown` (Float): 最大回撤
- `notes` (Text): 备注
- `created_at` (DateTime): 创建时间

#### 函数: get_engine(db_path)

获取数据库引擎。

```python
from models.database import get_engine

engine = get_engine(Path("data/labels.db"))
```

**参数**:
- `db_path` (Path): 数据库文件路径

**返回**: SQLAlchemy Engine 对象

#### 函数: init_db(db_path)

初始化数据库，创建所有表。

```python
from models.database import init_db

init_db(Path("data/labels.db"))
```

**参数**:
- `db_path` (Path): 数据库文件路径

**返回**: SQLAlchemy Engine 对象

#### 函数: get_session(db_path)

获取数据库会话。

```python
from models.database import get_session

session = get_session(Path("data/labels.db"))
```

**参数**:
- `db_path` (Path): 数据库文件路径

**返回**: SQLAlchemy Session 对象

---

## 特征工程

### backtest_labels.py

#### 类: LabelGenerator

标签生成器。

**初始化**:
```python
from scripts.backtest_labels import LabelGenerator

generator = LabelGenerator(
    source_db=Path("/path/to/stock_data.db"),
    target_db=Path("data/labels.db")
)
```

**参数**:
- `source_db` (Path): NeoTrade2 数据库路径（只读）
- `target_db` (Path): 本地标签数据库路径

#### 方法: get_all_stocks()

获取所有有效股票列表。

```python
stocks = generator.get_all_stocks()
# 返回: List[Tuple[code, name]]
```

**返回**: List[Tuple[str, str]] - 股票代码和名称的列表

#### 方法: get_stock_prices(code, start_date, end_date)

获取股票价格数据。

```python
df = generator.get_stock_prices("000001.SZ", "2024-09-01", "2026-03-31")
```

**参数**:
- `code` (str): 股票代码
- `start_date` (str): 起始日期 (YYYY-MM-DD)
- `end_date` (str): 结束日期 (YYYY-MM-DD)

**返回**: pandas.DataFrame - 包含 trade_date, close, high, low, open, volume 的数据框

#### 方法: calculate_max_forward_gain(prices, min_days=21, max_days=34)

计算向前的最大涨幅。

```python
max_gain, gain_days, gain_index = generator.calculate_max_forward_gain(
    prices, min_days=21, max_days=34
)
```

**参数**:
- `prices` (pd.Series): 价格序列
- `min_days` (int): 最短天数
- `max_days` (int): 最长天数

**返回**: Tuple[float, int, Optional[int]] - (最大涨幅, 达到天数, 索引)

#### 方法: generate_labels_for_stock(code, name, start_date, end_date)

为单只股票生成标签。

```python
labels = generator.generate_labels_for_stock(
    "000001.SZ", "平安银行", "2024-09-01", "2026-03-31"
)
```

**参数**:
- `code` (str): 股票代码
- `name` (str): 股票名称
- `start_date` (str): 起始日期
- `end_date` (str): 结束日期

**返回**: List[Dict] - 标签列表

#### 方法: generate_all_labels(start_date, end_date, overwrite=False)

为所有股票生成标签。

```python
total = generator.generate_all_labels(
    "2024-09-01", "2026-03-31", overwrite=True
)
```

**参数**:
- `start_date` (str): 起始日期
- `end_date` (str): 结束日期
- `overwrite` (bool): 是否覆盖现有数据

**返回**: int - 生成的标签总数

---

### compute_features.py

#### 类: FeatureEngine

特征计算引擎。

**初始化**:
```python
from scripts.compute_features import FeatureEngine

engine = FeatureEngine(
    source_db=Path("/path/to/stock_data.db"),
    target_db=Path("data/features.db")
)
```

#### 方法: compute_ma(df, windows)

计算移动平均线。

```python
df = engine.compute_ma(df, [5, 10, 20, 60])
```

**参数**:
- `df` (pd.DataFrame): 价格数据
- `windows` (List[int]): 窗口列表

**返回**: pd.DataFrame - 添加了 ma5, ma10, ... 列的数据框

#### 方法: compute_macd(df, fast=12, slow=26, signal=9)

计算 MACD 指标。

```python
df = engine.compute_macd(df, fast=12, slow=26, signal=9)
```

**参数**:
- `df` (pd.DataFrame): 价格数据
- `fast` (int): 快速 EMA 周期
- `slow` (int): 慢速 EMA 周期
- `signal` (int): 信号线周期

**返回**: pd.DataFrame - 添加了 macd, macd_signal, macd_hist 列的数据框

#### 方法: compute_rsi(df, window=14)

计算 RSI 指标。

```python
df = engine.compute_rsi(df, window=14)
```

**参数**:
- `df` (pd.DataFrame): 价格数据
- `window` (int): RSI 周期

**返回**: pd.DataFrame - 添加了 rsi 列的数据框

#### 方法: compute_all_features(df)

计算所有技术指标特征。

```python
df = engine.compute_all_features(df)
```

**参数**:
- `df` (pd.DataFrame): 价格数据

**返回**: pd.DataFrame - 添加了所有技术指标的数据框

#### 方法: compute_for_stock(code, name, start_date, end_date)

为单只股票计算特征。

```python
count = engine.compute_for_stock("000001.SZ", "平安银行", "2024-09-01", "2026-03-31")
```

**参数**:
- `code` (str): 股票代码
- `name` (str): 股票名称
- `start_date` (str): 起始日期
- `end_date` (str): 结束日期

**返回**: int - 计算的特征数量

#### 方法: compute_all(start_date, end_date, overwrite=False)

为所有股票计算特征。

```python
stats = engine.compute_all("2024-09-01", "2026-03-31", overwrite=True)
```

**参数**:
- `start_date` (str): 起始日期
- `end_date` (str): 结束日期
- `overwrite` (bool): 是否覆盖现有数据

**返回**: Dict - 包含 processed 和 total_features 的字典

---

### collect_screener_scores.py

#### 类: ScreenerFeatureCollector

筛选器特征收集器。

**初始化**:
```python
from scripts.collect_screener_scores import ScreenerFeatureCollector

collector = ScreenerFeatureCollector(
    source_db=Path("/path/to/stock_data.db"),
    screeners_dir=Path("/path/to/screeners"),
    target_db=Path("data/screener_scores.db")
)
```

#### 方法: run_screener(screener_name, date_str)

运行单个筛选器。

```python
results = collector.run_screener("coffee_cup_screener", "2026-04-14")
# 返回: Dict[code, {'hit': bool, 'score': float, 'reason': str, ...}]
```

**参数**:
- `screener_name` (str): 筛选器名称
- `date_str` (str): 目标日期

**返回**: Dict[str, Dict] - 股票代码到筛选器结果的映射

#### 方法: collect_for_date(date_str, screeners=None)

为指定日期收集所有筛选器特征。

```python
collector.collect_for_date("2026-04-14", screeners=["coffee_cup_screener", "jin_feng_huang_screener"])
```

**参数**:
- `date_str` (str): 目标日期
- `screeners` (Optional[List[str]]): 筛选器列表，None 表示全部

#### 方法: get_stock_screener_features(code, date_str)

获取某只股票在指定日期的筛选器特征。

```python
features = collector.get_stock_screener_features("000001.SZ", "2026-04-14")
# 返回: Dict[screener_name, {'hit': bool, 'score': float, ...}]
```

**参数**:
- `code` (str): 股票代码
- `date_str` (str): 目标日期

**返回**: Dict[str, Dict] - 筛选器名称到特征的映射

---

## 模型层

### train_model.py (待开发)

#### 类: ModelTrainer

模型训练器。

**初始化**:
```python
from scripts.train_model import ModelTrainer

trainer = ModelTrainer(
    labels_db=Path("data/labels.db"),
    features_db=Path("data/features.db"),
    screener_db=Path("data/screener_scores.db")
)
```

#### 方法: prepare_data(start_date, end_date)

准备训练数据。

```python
X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(
    "2024-09-01", "2026-03-31"
)
```

**参数**:
- `start_date` (str): 起始日期
- `end_date` (str): 结束日期

**返回**: Tuple[DataFrame, DataFrame, DataFrame, Series, Series, Series] - 训练集、验证集、测试集

#### 方法: train_model(X_train, y_train, X_val, y_val, params=None)

训练模型。

```python
model = trainer.train_model(X_train, y_train, X_val, y_val, params=xgb_params)
```

**参数**:
- `X_train` (DataFrame): 训练特征
- `y_train` (Series): 训练标签
- `X_val` (DataFrame): 验证特征
- `y_val` (Series): 验证标签
- `params` (Optional[Dict]): 模型参数

**返回**: 训练好的模型对象

#### 方法: evaluate_model(model, X_test, y_test)

评估模型。

```python
metrics = trainer.evaluate_model(model, X_test, y_test)
```

**参数**:
- `model`: 训练好的模型
- `X_test` (DataFrame): 测试特征
- `y_test` (Series): 测试标签

**返回**: Dict - 包含各种评估指标的字典

#### 方法: save_model(model, model_name, metadata)

保存模型。

```python
trainer.save_model(model, "xgboost_v1.0", {"version": "1.0.0", ...})
```

**参数**:
- `model`: 训练好的模型
- `model_name` (str): 模型名称
- `metadata` (Dict): 模型元数据

---

## 预测服务

### predict.py (待开发)

#### 类: StockPredictor

股票预测器。

**初始化**:
```python
from scripts.predict import StockPredictor

predictor = StockPredictor(
    model_path=Path("models/xgboost_model.json"),
    metadata_path=Path("models/metadata.json"),
    source_db=Path("/path/to/stock_data.db"),
    target_db=Path("data/predictions.db")
)
```

#### 方法: predict(date_str)

为指定日期进行预测。

```python
predictions = predictor.predict("2026-04-14")
# 返回: DataFrame 包含 code, name, probability, rank
```

**参数**:
- `date_str` (str): 预测日期

**返回**: pandas.DataFrame - 预测结果

#### 方法: get_top_k(predictions, k=50)

获取 Top K 预测。

```python
top_50 = predictor.get_top_k(predictions, k=50)
```

**参数**:
- `predictions` (DataFrame): 预测结果
- `k` (int): 返回数量

**返回**: pandas.DataFrame - Top K 预测

#### 方法: save_predictions(predictions)

保存预测结果。

```python
predictor.save_predictions(predictions)
```

**参数**:
- `predictions` (DataFrame): 预测结果

---

## 工具函数

### config.py

#### 常量配置

```python
from scripts.config import (
    # 路径配置
    PROJECT_ROOT,
    DATA_DIR,
    MODELS_DIR,
    NEOTRADE_DB_PATH,
    NEOTRADE_SCREENERS_DIR,

    # 数据库路径
    LABELS_DB,
    FEATURES_DB,
    SCREENER_SCORES_DB,
    PREDICTIONS_DB,

    # 预测参数
    TARGET_HORIZON_MIN,  # 21
    TARGET_HORIZON_MAX,  # 34
    TARGET_GAIN,         # 0.20

    # 筛选器列表
    SCREENER_FEATURES,
)
```

### 数据库查询辅助函数

```python
import sqlite3
import pandas as pd
from pathlib import Path

def query_db(db_path: Path, sql: str, params=None) -> pd.DataFrame:
    """查询数据库并返回 DataFrame"""
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df

def execute_db(db_path: Path, sql: str, params=None) -> int:
    """执行 SQL 语句"""
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        cursor = conn.execute(sql, params or ())
        conn.commit()
        return cursor.rowcount
```

### 时间工具函数

```python
from datetime import datetime, timedelta

def get_trading_dates(start_date: str, end_date: str, db_path: Path) -> List[str]:
    """获取交易日列表"""
    sql = """
        SELECT DISTINCT trade_date
        FROM daily_prices
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY trade_date
    """
    return query_db(db_path, sql, (start_date, end_date))['trade_date'].tolist()

def is_trading_day(date_str: str, db_path: Path) -> bool:
    """判断是否是交易日"""
    sql = """
        SELECT 1 FROM daily_prices WHERE trade_date = ?
    """
    return len(query_db(db_path, sql, (date_str,))) > 0
```
