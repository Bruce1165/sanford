"""
analyze_market_phase_simple.py - 简化版本的市场阶段分析
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    db_path = "/Users/mac/NeoTrade2/data/stock_data.db"

    print("=" * 80)
    print("A股当前市场阶段分析（基于DB现有数据）")
    print("=" * 80)
    print("分析时间：2026-04-15")
    print()

    # 获取市场数据
    with sqlite3.connect(db_path, timeout=30) as conn:
        df = pd.read_sql_query("""
            SELECT trade_date,
                   AVG(close) as avg_close,
                   AVG(pct_change) as avg_pct_change,
                   SUM(volume) as total_volume,
                   COUNT(*) as stock_count
            FROM daily_prices
            WHERE trade_date >= date('now', '-120 days')
            GROUP BY trade_date
            ORDER BY trade_date ASC
        """, conn)

    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)

    if len(df) < 60:
        print("错误：数据不足")
        return

    # 计算技术指标
    df['ma5'] = df['avg_close'].rolling(window=5).mean()
    df['ma10'] = df['avg_close'].rolling(window=10).mean()
    df['ma20'] = df['avg_close'].rolling(window=20).mean()
    df['ma60'] = df['avg_close'].rolling(window=60).mean()

    ema12 = df['avg_close'].ewm(span=12, adjust=False).mean()
    ema26 = df['avg_close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    delta = df['avg_close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['volatility_20'] = df['avg_pct_change'].rolling(window=20).std()

    latest = df.iloc[-1]
    recent_30 = df.tail(30)
    recent_60 = df.tail(60)

    # 计算近期涨跌幅度
    recent_30_return = (latest['avg_close'] / recent_30.iloc[0]['avg_close'] - 1) * 100
    recent_60_return = (latest['avg_close'] / recent_60.iloc[0]['avg_close'] - 1) * 100

    # 趋势分析
    print("【趋势分析】")
    print(f"  市场收盘价：{latest['avg_close']:.2f}")

    # 均线排列
    if latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60']:
        ma_pattern = "多头排列"
        overall_trend = "上升"
    elif latest['ma5'] < latest['ma10'] < latest['ma20'] < latest['ma60']:
        ma_pattern = "空头排列"
        overall_trend = "下降"
    else:
        ma_pattern = "纠缠"
        overall_trend = "震荡"

    print(f"  均线排列：{ma_pattern}")

    # MACD信号
    if latest['macd'] > latest['macd_signal'] and latest['macd_hist'] > 0:
        macd_signal = "金叉向上"
    elif latest['macd'] < latest['macd_signal'] and latest['macd_hist'] < 0:
        macd_signal = "死叉向下"
    else:
        macd_signal = "中性"

    print(f"  MACD信号：{macd_signal}")
    print(f"  MACD数值：{latest['macd']:.4f}")

    # RSI状态
    if latest['rsi'] > 70:
        rsi_status = "超买"
    elif latest['rsi'] < 30:
        rsi_status = "超卖"
    else:
        rsi_status = "中性"

    print(f"  RSI状态：{rsi_status} ({latest['rsi']:.2f})")

    # 波动率
    vol_20 = df['volatility_20'].tail(20).mean()
    if latest['volatility_20'] > vol_20 * 1.5:
        volatility_status = "高波动"
    elif latest['volatility_20'] < vol_20 * 0.5:
        volatility_status = "低波动"
    else:
        volatility_status = "正常"

    print(f"  波动率：{volatility_status} ({latest['volatility_20']:.4f})")
    print()

    # 八段论阶段推断
    print("【八段论阶段推断】")
    print(f"  整体趋势：{overall_trend}")
    print(f"  近30日涨跌：{recent_30_return:.2f}%")
    print(f"  近60日涨跌：{recent_60_return:.2f}%")
    print(f"  均线多头排列：{latest['ma5'] > latest['ma10'] > latest['ma20'] > latest['ma60']}")

    # 推断八段论阶段
    if overall_trend == "上升":
        if latest['rsi'] > 70 and recent_30_return > 10:
            wave_phase = "可能处于第3浪或第5浪"
            phase_desc = "快速上涨阶段，RSI超买，涨幅较大"
            confidence = "中等"
        elif latest['rsi'] > 50 and recent_30_return > 5:
            wave_phase = "可能处于第1浪或第3浪"
            phase_desc = "上涨初期，RSI偏高，有一定涨幅"
            confidence = "中等"
        else:
            wave_phase = "可能处于第2浪或第4浪"
            phase_desc = "上升回调阶段，RSI中性"
            confidence = "低"
    elif overall_trend == "下降":
        if latest['rsi'] < 30 and recent_30_return < -10:
            wave_phase = "可能处于浪A或浪C"
            phase_desc = "大幅下跌阶段，RSI超卖，跌幅较大"
            confidence = "中等"
        elif latest['rsi'] < 50 and recent_30_return < -5:
            wave_phase = "可能处于浪A或浪C"
            phase_desc = "下跌阶段，RSI偏低，有一定跌幅"
            confidence = "中等"
        else:
            wave_phase = "可能处于浪B"
            phase_desc = "下跌反弹阶段，RSI中性"
            confidence = "低"
    else:
        wave_phase = "可能处于调整浪（第2浪或第4浪或浪B）"
        phase_desc = "横盘震荡阶段，方向不明"
        confidence = "低"

    print(f"  推断阶段：{wave_phase}")
    print(f"  阶段描述：{phase_desc}")
    print(f"  推断置信度：{confidence}")
    print()

    print("=" * 80)
    print("说明：")
    print("1. 基于DB现有价格数据计算技术指标进行模糊判断")
    print("2. 未包含宏观经济数据、产业政策、资金流向、市场情绪等外部数据")
    print("3. 八段论 = 五浪上升（1-2-3-4-5）+ 三浪下降（A-B-C）")
    print("4. 由于缺乏宏观经济和政策数据，推断置信度较低，仅供参考")
    print("=" * 80)


if __name__ == '__main__':
    main()
