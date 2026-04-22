"""
database.py – STOCKPREDICTION 数据库模型

定义本地数据库的表结构，用于存储标签、特征和预测结果。
"""

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path

Base = declarative_base()


class TrainingLabel(Base):
    """训练标签 - 通过历史回测生成的 20%+ 上涨股票标签"""
    __tablename__ = 'training_labels'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)          # 股票代码
    name = Column(String(50))                      # 股票名称
    base_date = Column(String(10), index=True)     # 基准日期（预测日期）
    label = Column(Integer)                        # 标签：1=后续21-34天涨20%+, 0=未达到
    max_gain = Column(Float)                       # 后续最大涨幅
    max_gain_date = Column(String(10))             # 达到最大涨幅的日期
    max_gain_days = Column(Integer)                # 达到最大涨幅的天数
    horizon_min = Column(Integer, default=21)      # 最短持有天数
    horizon_max = Column(Integer, default=34)      # 最长持有天数
    target_gain = Column(Float, default=0.20)      # 目标涨幅
    created_at = Column(DateTime, default=datetime.now)


class StockFeature(Base):
    """股票特征 - 技术指标和筛选器特征"""
    __tablename__ = 'stock_features'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)          # 股票代码
    trade_date = Column(String(10), index=True)    # 交易日期

    # 价格特征
    close = Column(Float)
    pct_change = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    turnover = Column(Float)

    # 技术指标
    ma5 = Column(Float, nullable=True)
    ma10 = Column(Float, nullable=True)
    ma20 = Column(Float, nullable=True)
    ma60 = Column(Float, nullable=True)
    ema12 = Column(Float, nullable=True)
    ema26 = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    macd_hist = Column(Float, nullable=True)
    rsi = Column(Float, nullable=True)
    atr = Column(Float, nullable=True)
    bollinger_upper = Column(Float, nullable=True)
    bollinger_middle = Column(Float, nullable=True)
    bollinger_lower = Column(Float, nullable=True)
    bollinger_pct = Column(Float, nullable=True)   # 价格在布林带中的位置
    stoch_k = Column(Float, nullable=True)
    stoch_d = Column(Float, nullable=True)

    # 相对表现特征
    rel_to_market = Column(Float, nullable=True)   # 相对大盘涨跌幅
    rel_to_industry = Column(Float, nullable=True) # 相对行业涨跌幅

    # 历史收益特征
    return_3d = Column(Float, nullable=True)       # 3日收益
    return_5d = Column(Float, nullable=True)       # 5日收益
    return_10d = Column(Float, nullable=True)      # 10日收益
    return_20d = Column(Float, nullable=True)      # 20日收益
    return_60d = Column(Float, nullable=True)      # 60日收益

    # 波动率特征
    volatility_10d = Column(Float, nullable=True)
    volatility_20d = Column(Float, nullable=True)
    volatility_60d = Column(Float, nullable=True)

    # 成交量特征
    vol_ratio_5d = Column(Float, nullable=True)    # 成交量5日均量比率
    vol_ratio_20d = Column(Float, nullable=True)   # 成交量20日均量比率

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ScreenerFeature(Base):
    """筛选器特征 - 来自 NeoTrade2 筛选器的结果"""
    __tablename__ = 'screener_features'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)          # 股票代码
    trade_date = Column(String(10), index=True)    # 交易日期
    screener_name = Column(String(50), index=True) # 筛选器名称
    hit = Column(Boolean, default=False)           # 是否命中
    score = Column(Float, nullable=True)           # 筛选器分数（如果有）
    reason = Column(Text, nullable=True)           # 命中原因
    extra_data = Column(Text, nullable=True)       # 额外数据（JSON）
    created_at = Column(DateTime, default=datetime.now)


class Prediction(Base):
    """预测结果"""
    __tablename__ = 'predictions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)          # 股票代码
    name = Column(String(50))                      # 股票名称
    prediction_date = Column(String(10), index=True) # 预测日期
    probability = Column(Float)                    # 预测概率（0-1）
    label = Column(Integer, nullable=True)         # 实际标签（回填）
    model_name = Column(String(50))                # 模型名称
    model_version = Column(String(20))             # 模型版本
    rank = Column(Integer)                         # 当天预测排名
    features_importance = Column(Text, nullable=True) # 特征重要性（JSON）
    notes = Column(Text, nullable=True)            # 备注
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ModelPerformance(Base):
    """模型性能记录"""
    __tablename__ = 'model_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(50), index=True)    # 模型名称
    model_version = Column(String(20))             # 模型版本
    train_start = Column(String(10))               # 训练起始日期
    train_end = Column(String(10))                 # 训练结束日期
    test_start = Column(String(10))                # 测试起始日期
    test_end = Column(String(10))                  # 测试结束日期

    # 性能指标
    precision = Column(Float)                      # 精确率
    recall = Column(Float)                         # 召回率
    f1_score = Column(Float)                       # F1分数
    auc = Column(Float)                            # AUC
    precision_at_10 = Column(Float, nullable=True) # Top10精确率
    precision_at_50 = Column(Float, nullable=True) # Top50精确率
    precision_at_100 = Column(Float, nullable=True)# Top100精确率

    # 回测指标
    avg_return = Column(Float, nullable=True)      # 平均收益
    win_rate = Column(Float, nullable=True)        # 胜率
    max_drawdown = Column(Float, nullable=True)    # 最大回撤

    notes = Column(Text, nullable=True)            # 备注
    created_at = Column(DateTime, default=datetime.now)


def get_engine(db_path: Path) -> create_engine:
    """获取数据库引擎"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f'sqlite:///{db_path}', echo=False)


def init_db(db_path: Path) -> create_engine:
    """初始化数据库"""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: Path):
    """获取数据库会话"""
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    from scripts.config import LABELS_DB, FEATURES_DB, PREDICTIONS_DB

    for db_name, db_path in [
        ("Labels", LABELS_DB),
        ("Features", FEATURES_DB),
        ("Predictions", PREDICTIONS_DB),
    ]:
        print(f"初始化 {db_name} 数据库: {db_path}")
        init_db(db_path)
        print(f"  ✓ 完成")

    print("\n所有数据库初始化完成！")
