"""
analyze_market_phase.py - 基于现有数据和外部数据模糊判断A股当前所处的八段论阶段

八段论：五浪上升 + A、B、C三浪下降
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MarketPhaseAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_market_data(self, days: int = 120) -> pd.DataFrame:
        """获取市场平均数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            df = pd.read_sql_query("""
                SELECT trade_date,
                       AVG(close) as avg_close,
                       AVG(pct_change) as avg_pct_change,
                       SUM(volume) as total_volume,
                       COUNT(*) as stock_count
                FROM daily_prices
                WHERE trade_date >= date('now', '-{} days')
                GROUP BY trade_date
                ORDER BY trade_date ASC
            """.format(days), conn)

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.sort_values('trade_date').reset_index(drop=True)

        # 移动平均线
        df['ma5'] = df['avg_close'].rolling(window=5).mean()
        df['ma10'] = df['avg_close'].rolling(window=10).mean()
        df['ma20'] = df['avg_close'].rolling(window=20).mean()
        df['ma60'] = df['avg_close'].rolling(window=60).mean()

        # MACD
        ema12 = df['avg_close'].ewm(span=12, adjust=False).mean()
        ema26 = df['avg_close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # RSI
        delta = df['avg_close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 波动率
        df['volatility_20'] = df['avg_pct_change'].rolling(window=20).std()

        return df

    def analyze_trend(self, df: pd.DataFrame) -> dict:
        """分析趋势"""
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else latest

        analysis = {
            'date': latest['trade_date'].strftime('%Y-%m-%d'),
            'close': latest['avg_close'],
            'ma5': latest['ma5'],
            'ma10': latest['ma10'],
            'ma20': latest['ma20'],
            'ma60': latest['ma60'],
            'macd': latest['macd'],
            'macd_signal': latest['macd_signal'],
            'macd_hist': latest['macd_hist'],
            'rsi': latest['rsi'],
            'volatility': latest['volatility_20']
        }

        # 均线排列
        if latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60']:
            analysis['ma_pattern'] = '多头排列'
            analysis['trend'] = '上升'
        elif latest['ma5'] < latest['ma10'] < latest['ma20'] < latest['ma60']:
            analysis['ma_pattern'] = '空头排列'
            analysis['trend'] = '下降'
        else:
            analysis['ma_pattern'] = '纠缠'
            analysis['trend'] = '震荡'

        # MACD信号
        if latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0:
            analysis['macd_signal'] = '金叉向上'
        elif latest['macd'] < latest['macd_signal'] and latest['macd_hist'] < 0:
            analysis['macd_signal'] = '死叉向下'
        else:
            analysis['macd_signal'] = '中性'

        # RSI状态
        if latest['rsi'] > 70:
            analysis['rsi_status'] = '超买'
        elif latest['rsi'] < 30:
            analysis['rsi_status'] = '超卖'
        else:
            analysis['rsi_status'] = '中性'

        # 波动率
        vol_20 = df['volatility_20'].tail(20).mean()
        if latest['volatility_20'] > vol_20 * 1.5:
            analysis['volatility_status'] = '高波动'
        elif latest['volatility_20'] < vol_20 * 0.5:
            analysis['volatility_status'] = '低波动'
        else:
            analysis['volatility_status'] = '正常'

        return analysis

    def infer_eight_wave_phase(self, df: pd.DataFrame) -> dict:
        """推断八段论阶段（模糊判断）"""
        latest = df.iloc[-1]
        recent_30 = df.tail(30)
        recent_60 = df.tail(60)

        # 计算近期涨跌幅度
        recent_30_return = (latest['avg_close'] / recent_30.iloc[0]['avg_close'] - 1) * 100
        recent_60_return = (latest['avg_close'] / recent_60.iloc[0]['avg_close'] - 1) * 100

        # 判断整体趋势
        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            overall_trend = '上升'
        elif latest['ma5'] < latest['ma10'] < latest['ma20']:
            overall_trend = '下降'
        else:
            overall_trend = '震荡'

        # 判断浪型阶段
        phase = {
            'date': latest['trade_date'].strftime('%Y-%m-%d'),
            'overall_trend': overall_trend,
            'recent_30d_return': round(recent_30_return, 2),
            'recent_60d_return': round(recent_60_return, 2),
            'ma_pattern': latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60'],
            'macd_trend': '上升' if latest['macd_hist'] > 0 else '下降',
            'rsi': round(latest['rsi'], 2),
            'volatility': round(latest['volatility_20'], 4)
        }

        # 模糊判断八段论阶段
        if overall_trend == '上升':
            if latest['rsi'] > 70 and recent_30_return > 10:
                phase['wave_phase'] = '可能处于第3浪或第5浪'
                phase['phase_description'] = '快速上涨阶段，RSI超买，涨幅较大'
                phase['confidence'] = '中等'
            elif latest['rsi'] > 50 and recent_30_return > 5:
                phase['wave_phase'] = '可能处于第1浪或第3浪'
                phase['phase_description'] = '上涨初期，RSI偏高，有一定涨幅'
                phase['confidence'] = '中等'
            else:
                phase['wave_phase'] = '可能处于第2浪或第4浪'
                phase['phase_description'] = '上升回调阶段，RSI中性'
                phase['confidence'] = '低'
        elif overall_trend == '下降':
            if latest['rsi'] < 30 and recent_30_return < -10:
                phase['wave_phase'] = '可能处于浪A或浪C'
                phase['phase_description'] = '大幅下跌阶段，RSI超卖，跌幅较大'
                phase['confidence'] = '中等'
            elif latest['rsi'] < 50 and recent_30_return < -5:
                phase['wave_phase'] = '可能处于浪A或浪C'
                phase['phase_description'] = '下跌阶段，RSI偏低，有一定跌幅'
                phase['confidence'] = '中等'
            else:
                phase['wave_phase'] = '可能处于浪B'
                phase['phase_description'] = '下跌反弹阶段，RSI中性'
                phase['confidence'] = '低'
        else:  # 震荡
            phase['wave_phase'] = '可能处于调整浪（第2浪或第4浪或浪B）'
            phase['phase_description'] = '横盘震荡阶段，方向不明'
            phase['confidence'] = '低'

        return phase

    def analyze(self) -> dict:
        """执行完整分析"""
        logger.info("开始分析市场阶段...")

        # 获取市场数据
        df = self.get_market_data(days=120)
        if len(df) < 60:
            logger.error("数据不足，至少需要60天数据")
            return {'error': '数据不足'}

        # 计算技术指标
        df = self.calculate_technical_indicators(df)

        # 分析趋势
        trend_analysis = self.analyze_trend(df)

        # 推断八段论阶段
        wave_phase = self.infer_eight_wave_phase(df)

        result = {
            'trend_analysis': trend_analysis,
            'wave_phase': wave_phase,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        return result


def main():
    db_path = "/Users/mac/NeoTrade2/data/stock_data.db"

    analyzer = MarketPhaseAnalyzer(db_path)
    result = analyzer.analyze()

    # 输出结果
    print("=" * 80)
    print("A股当前市场阶段分析（基于DB现有数据）")
    print("=" * 80)
    print(f"分析时间：{result['analysis_date']}")
    print()

    # 趋势分析
    trend = result['trend_analysis']
    print("【趋势分析】")
    print(f"  市场收盘价：{trend['close']:.2f}")
    print(f"  均线排列：{trend['ma_pattern']}")
    print(f"  MACD信号：{trend['macd_signal']}（MACD={trend['macd']:.4f}, Signal={trend['macd_signal']:.4f}）")
    print(f"  RSI状态：{trend['rsi_status']}（RSI={trend['rsi']:.2f}）")
    print(f"  波动率：{trend['volatility_status']}（波动率={trend['volatility']:.4f}）")
    print()

    # 八段论阶段
    wave = result['wave_phase']
    print("【八段论阶段推断】")
    print(f"  整体趋势：{wave['overall_trend']}")
    print(f"  近30日涨跌：{wave['recent_30d_return']:.2f}%")
    print(f"  近60日涨跌：{wave['recent_60d_return']:.2f}%")
    print(f"  推断阶段：{wave['wave_phase']}")
    print(f"  阶段描述：{wave['phase_description']}")
    print(f"  推断置信度：{wave['confidence']}")
    print()

    print("=" * 80)
    print("说明：")
    print("1. 基于DB现有价格数据计算技术指标进行模糊判断")
    print("2. 未包含宏观经济数据、产业政策、资金流向、市场情绪等外部数据")
    print("3. 八段论 = 五浪上升（1-2-3-4-5）+ 三浪下降（A-B-C）")
    print("=" * 80)


if __name__ == '__main__':
    main()
