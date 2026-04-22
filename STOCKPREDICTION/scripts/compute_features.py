"""
compute_features.py – 计算股票技术指标特征
"""

import argparse
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pandas as pd
import numpy as np

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    NEOTRADE_DB_PATH,
    FEATURES_DB,
    LOOKBACK_DAYS,
    MA_WINDOWS,
    EMA_WINDOWS,
    RSI_WINDOW,
    ATR_WINDOW,
    BOLLINGER_WINDOW,
    STOCHASTIC_K,
    STOCHASTIC_D,
)
from models.database import init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FeatureEngine:
    def __init__(self, source_db: Path = NEOTRADE_DB_PATH, target_db: Path = FEATURES_DB):
        self.source_db = source_db
        self.target_db = target_db
        self._init_target_db()

    def _init_target_db(self):
        init_db(self.target_db)
        logger.info(f"目标数据库已初始化: {self.target_db}")

    def get_all_stocks(self) -> List[tuple]:
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            return conn.execute("""
                SELECT code, name FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND name NOT LIKE '%ST%' AND name NOT LIKE '%*ST%'
                  AND name NOT LIKE '%退%' AND name NOT LIKE '%指数%'
                  AND name NOT LIKE '%ETF%' AND name NOT LIKE '%LOF%'
                  AND code NOT LIKE '43%' AND code NOT LIKE '83%'
                  AND code NOT LIKE '87%' AND code NOT LIKE '88%'
                  AND code NOT LIKE '399%'
                ORDER BY code
            """).fetchall()

    def get_stock_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            df = pd.read_sql_query("""
                SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
                FROM daily_prices
                WHERE code = ? AND trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """, conn, params=(code, start_date, end_date))
            if not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df

    def compute_ma(self, df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
        for w in windows:
            df[f'ma{w}'] = df['close'].rolling(window=w, min_periods=w).mean()
        return df

    def compute_ema(self, df: pd.DataFrame, windows: List[int]) -> pd.DataFrame:
        for w in windows:
            df[f'ema{w}'] = df['close'].ewm(span=w, adjust=False).mean()
        return df

    def compute_macd(self, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        df['ema12'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=slow, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        return df

    def compute_rsi(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss))
        return df

    def compute_atr(self, df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=window).mean()
        return df

    def compute_bollinger(self, df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
        df['bollinger_middle'] = df['close'].rolling(window=window).mean()
        std = df['close'].rolling(window=window).std()
        df['bollinger_upper'] = df['bollinger_middle'] + (std * num_std)
        df['bollinger_lower'] = df['bollinger_middle'] - (std * num_std)
        df['bollinger_pct'] = (df['close'] - df['bollinger_lower']) / (df['bollinger_upper'] - df['bollinger_lower'])
        return df

    def compute_stochastic(self, df: pd.DataFrame, k_window: int = 14, d_window: int = 3) -> pd.DataFrame:
        low_min = df['low'].rolling(window=k_window).min()
        high_max = df['high'].rolling(window=k_window).max()
        df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
        df['stoch_d'] = df['stoch_k'].rolling(window=d_window).mean()
        return df

    def compute_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        df['return_3d'] = df['close'].pct_change(3)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_20d'] = df['close'].pct_change(20)
        df['return_60d'] = df['close'].pct_change(60)
        return df

    def compute_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        df['volatility_10d'] = df['pct_change'].rolling(window=10).std()
        df['volatility_20d'] = df['pct_change'].rolling(window=20).std()
        df['volatility_60d'] = df['pct_change'].rolling(window=60).std()
        return df

    def compute_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df['vol_ma5'] = df['volume'].rolling(window=5).mean()
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio_5d'] = df['volume'] / df['vol_ma5']
        df['vol_ratio_20d'] = df['volume'] / df['vol_ma20']
        return df

    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < LOOKBACK_DAYS:
            return df
        df = self.compute_ma(df, MA_WINDOWS)
        df = self.compute_ema(df, EMA_WINDOWS)
        df = self.compute_macd(df)
        df = self.compute_rsi(df, RSI_WINDOW)
        df = self.compute_atr(df, ATR_WINDOW)
        df = self.compute_bollinger(df, BOLLINGER_WINDOW)
        df = self.compute_stochastic(df, STOCHASTIC_K, STOCHASTIC_D)
        df = self.compute_returns(df)
        df = self.compute_volatility(df)
        df = self.compute_volume_features(df)
        return df

    def save_features(self, code: str, name: str, df: pd.DataFrame):
        df_to_save = df.dropna(subset=['ma20']).copy()
        if df_to_save.empty:
            return
        
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            for _, row in df_to_save.iterrows():
                trade_date = row['trade_date'].strftime('%Y-%m-%d')
                
                # Build values list matching 37 columns
                values = [
                    code, trade_date,
                    row.get('close'), row.get('pct_change'),
                    row.get('volume'), row.get('amount'), row.get('turnover'),
                    row.get('ma5'), row.get('ma10'), row.get('ma20'), row.get('ma60'),
                    row.get('ema12'), row.get('ema26'),
                    row.get('macd'), row.get('macd_signal'), row.get('macd_hist'),
                    row.get('rsi'), row.get('atr'),
                    row.get('bollinger_upper'), row.get('bollinger_middle'), row.get('bollinger_lower'),
                    row.get('bollinger_pct'),
                    row.get('stoch_k'), row.get('stoch_d'),
                    None, None,  # rel_to_market, rel_to_industry
                    row.get('return_3d'), row.get('return_5d'),
                    row.get('return_10d'), row.get('return_20d'), row.get('return_60d'),
                    row.get('volatility_10d'), row.get('volatility_20d'), row.get('volatility_60d'),
                    row.get('vol_ratio_5d'), row.get('vol_ratio_20d'),
                    None  # updated_at
                ]
                
                placeholders = ','.join(['?' for _ in range(37)])
                columns = """code, trade_date, close, pct_change, volume, amount, turnover,
                     ma5, ma10, ma20, ma60, ema12, ema26, macd, macd_signal, macd_hist,
                     rsi, atr, bollinger_upper, bollinger_middle, bollinger_lower, bollinger_pct,
                     stoch_k, stoch_d, rel_to_market, rel_to_industry,
                     return_3d, return_5d, return_10d, return_20d, return_60d,
                     volatility_10d, volatility_20d, volatility_60d, vol_ratio_5d, vol_ratio_20d, updated_at"""
                
                sql = f"INSERT OR REPLACE INTO stock_features ({columns}) VALUES ({placeholders})"
                conn.execute(sql, values)
            conn.commit()

    def compute_for_stock(self, code: str, name: str, start_date: str, end_date: str) -> int:
        price_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=LOOKBACK_DAYS + 60)).strftime("%Y-%m-%d")
        df = self.get_stock_data(code, price_start, end_date)
        if df.empty or len(df) < LOOKBACK_DAYS:
            return 0
        df = df.sort_values('trade_date').reset_index(drop=True)
        df = self.compute_all_features(df)
        self.save_features(code, name, df)
        return len(df)

    def compute_all(self, start_date: str, end_date: str, overwrite: bool = False):
        logger.info(f"开始计算特征: {start_date} 到 {end_date}")
        if overwrite:
            with sqlite3.connect(str(self.target_db), timeout=30) as conn:
                conn.execute("DELETE FROM stock_features")
                conn.commit()
            logger.info("已清空现有特征数据")
        
        stocks = self.get_all_stocks()
        logger.info(f"共 {len(stocks)} 只股票")
        
        total_features = 0
        processed = 0
        for code, name in stocks:
            try:
                count = self.compute_for_stock(code, name, start_date, end_date)
                total_features += count
                processed += 1
                if processed % 100 == 0:
                    logger.info(f"已处理 {processed}/{len(stocks)} 只股票, 累计特征 {total_features}")
            except Exception as e:
                logger.warning(f"处理股票 {code} 时出错: {e}")
        
        logger.info(f"特征计算完成: 处理股票 {processed}/{len(stocks)}, 总特征数 {total_features}")
        return {'processed': processed, 'total_features': total_features}

    def get_feature_stats(self):
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            row = conn.execute("""
                SELECT COUNT(DISTINCT code) as stocks, COUNT(*) as total_features,
                       MIN(trade_date) as min_date, MAX(trade_date) as max_date
                FROM stock_features
            """).fetchone()
            
            missing_stats = {}
            for col in ['ma5', 'ma10', 'ma20', 'ma60', 'rsi', 'atr', 'bollinger_upper', 'macd', 'stoch_k']:
                r = conn.execute(f"SELECT COUNT(*) as total, SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) as null_count FROM stock_features").fetchone()
                missing_stats[col] = r[1] / r[0] if r[0] > 0 else 0
        
        return {'stocks': row[0], 'total_features': row[1], 'date_range': f"{row[2]} 到 {row[3]}", 'missing_stats': missing_stats}


def main():
    parser = argparse.ArgumentParser(description='计算技术指标特征')
    parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, default='2024-09-01', help='起始日期')
    parser.add_argument('--end-date', type=str, help='结束日期')
    parser.add_argument('--overwrite', action='store_true', help='覆盖现有特征')
    parser.add_argument('--stats', action='store_true', help='只显示统计信息')
    
    args = parser.parse_args()
    engine = FeatureEngine()
    
    if args.stats:
        stats = engine.get_feature_stats()
        print(f"股票数量: {stats['stocks']}")
        print(f"总特征数: {stats['total_features']}")
        print(f"日期范围: {stats['date_range']}")
        for col, rate in stats['missing_stats'].items():
            print(f"{col}: {rate*100:.2f}%")
        return
    
    if args.date:
        start_date = end_date = args.date
    else:
        start_date = args.start_date
        end_date = args.end_date if args.end_date else datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"特征计算范围: {start_date} 到 {end_date}")
    engine.compute_all(start_date, end_date, args.overwrite)


if __name__ == '__main__':
    main()
