"""
数据库模型 - Neo量化研究体系
全A股数据存储
"""
from sqlalchemy import create_engine, Column, String, Float, Date, DateTime, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path

Base = declarative_base()

class Stock(Base):
    """股票基础信息"""
    __tablename__ = 'stocks'
    
    code = Column(String(10), primary_key=True)      # 股票代码
    name = Column(String(50))                         # 股票名称
    industry = Column(String(50))                     # 所属行业
    area = Column(String(50))                         # 地区
    list_date = Column(Date)                          # 上市日期
    total_market_cap = Column(Float)                  # AB股总市值（元）
    circulating_market_cap = Column(Float)            # 流通市值（元）
    pb_ratio = Column(Float)                          # 市净率
    updated_at = Column(DateTime, default=datetime.now)

class DailyPrice(Base):
    """日线行情数据"""
    __tablename__ = 'daily_prices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)         # 股票代码
    trade_date = Column(Date, index=True)         # 交易日期
    open = Column(Float)                          # 开盘价
    high = Column(Float)                          # 最高价
    low = Column(Float)                           # 最低价
    close = Column(Float)                         # 收盘价
    volume = Column(Float)                        # 成交量（股）
    amount = Column(Float)                        # 成交额（元）
    turnover = Column(Float)                      # 换手率
    preclose = Column(Float)                      # 昨收价
    pct_change = Column(Float)                    # 涨跌幅
    updated_at = Column(DateTime, default=datetime.now)

class Announcement(Base):
    """公告数据"""
    __tablename__ = 'announcements'
    
    id = Column(String(50), primary_key=True)     # 公告ID
    code = Column(String(10), index=True)         # 股票代码
    name = Column(String(50))                     # 股票名称
    title = Column(Text)                          # 公告标题
    type = Column(String(50))                     # 公告类型
    publish_date = Column(DateTime, index=True)   # 发布时间
    url = Column(Text)                            # 公告链接
    updated_at = Column(DateTime, default=datetime.now)

class LimitUpReason(Base):
    """涨停原因（手动录入）"""
    __tablename__ = 'limit_up_reasons'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), index=True)         # 股票代码
    trade_date = Column(Date, index=True)         # 交易日期
    reason = Column(Text)                         # 涨停原因
    category = Column(String(50))                 # 原因分类（概念/板块）
    source = Column(String(50))                   # 来源
    updated_at = Column(DateTime, default=datetime.now)

def get_engine(db_path=None):
    """获取数据库引擎"""
    if db_path is None:
        # Use relative path from scripts/ directory
        workspace_root = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
        db_path = workspace_root / 'data' / 'stock_data.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f'sqlite:///{db_path}', echo=False)

def init_db(engine=None):
    """初始化数据库"""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine

def get_session(engine=None):
    """获取数据库会话"""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == '__main__':
    engine = init_db()
    print(f"数据库初始化完成: {engine.url}")
