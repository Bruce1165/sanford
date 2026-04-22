#!/usr/bin/env python3
"""
Manual Coffee Cup Formation Labeling

Manually identifies coffee cup formations from OHLCV data for ground truth labels.
Based on O'Neil CANSLIM criteria as defined in coffee_cup_screener.py
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import json
import logging

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# Configuration
DB_PATH = Path('/Users/mac/NeoTrade2/data/stock_data.db')
OUTPUT_DIR = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Coffee Cup Pattern Parameters
CUP_PERIOD_MIN = 60
CUP_PERIOD_MAX = 250
CUP_DEPTH_MIN = 0.20
CUP_DEPTH_MAX = 0.50
HANDLE_PERIOD_MIN = 1
HANDLE_PERIOD_MAX = 21
HANDLE_RETRACE_MIN = 0.05
HANDLE_RETRACE_MAX = 0.12
HANDLE_VOLUME_RATIO = 0.85
BREAKOUT_THRESHOLD = 1.0
MA_SHORT = 50
MA_MEDIUM = 150
MA_LONG = 200
MIN_TURNOVER = 5.0
MIN_PCT_CHANGE = 2.0
VOLUME_SURGE_RATIO = 2.0
RS_MIN_SCORE = 85


def check_volume_surge(df: pd.DataFrame) -> tuple[bool, float]:
    if len(df) < 7:
        return False, 0.0
    recent_3_days = df.iloc[-3:]['amount'].sum()
    previous_3_days = df.iloc[-6:-3]['amount'].sum()
    if previous_3_days <= 0:
        return False, 0.0
    volume_ratio = recent_3_days / previous_3_days
    return volume_ratio >= VOLUME_SURGE_RATIO, volume_ratio


def find_cup_handle_formation(df: pd.DataFrame):
    if len(df) < CUP_PERIOD_MAX + HANDLE_PERIOD_MAX:
        return None

    latest = df.iloc[-1]
    cup_rim_price = latest['close']
    latest_date = latest['trade_date']

    cup_period_start = len(df) - CUP_PERIOD_MAX
    cup_period_end = len(df) - CUP_PERIOD_MIN

    if cup_period_start < 0:
        return None

    for handle_end_idx in range(cup_period_end, cup_period_start, -1):
        handle_start_idx = max(0, handle_end_idx - HANDLE_PERIOD_MAX)

        if handle_start_idx < 10:
            continue

        handle_period = df.iloc[handle_start_idx:handle_end_idx]
        pre_handle_period = df.iloc[handle_start_idx - HANDLE_PERIOD_MIN:handle_start_idx]

        if len(handle_period) < HANDLE_PERIOD_MIN:
            continue

        handle_high = handle_period['high'].max()
        handle_low = handle_period['low'].min()
        handle_close_avg = handle_period['close'].mean()

        pre_handle_high = pre_handle_period['high'].max()
        price_diff_pct = abs(handle_high - pre_handle_high) / pre_handle_high

        if price_diff_pct > 0.05:
            continue

        handle_volume_avg = handle_period['volume'].mean()
        pre_handle_volume_avg = pre_handle_period['volume'].mean()

        if pre_handle_volume_avg > 0:
            volume_ratio = handle_volume_avg / pre_handle_volume_avg
            if volume_ratio > HANDLE_VOLUME_RATIO:
                continue

        cup_start_idx = max(0, handle_start_idx - 30)
        cup_period = df.iloc[cup_start_idx:handle_start_idx]

        if len(cup_period) < 20:
            continue

        cup_high = max(pre_handle_high, handle_high)
        cup_low = cup_period['low'].min()
        cup_depth = (cup_high - cup_low) / cup_high

        if not (CUP_DEPTH_MIN <= cup_depth <= CUP_DEPTH_MAX):
            continue

        handle_retrace = (pre_handle_high - handle_low) / pre_handle_high
        handle_retrace_max = cup_depth / 2

        if not (0 <= handle_retrace <= handle_retrace_max):
            continue

        has_spike = False
        for _, day in cup_period.iterrows():
            if day['high'] > cup_high * 1.02:
                has_spike = True
                break

        if has_spike:
            continue

        cup_low_idx = cup_period['low'].idxmin()
        cup_lowest_date = df.loc[cup_low_idx, 'trade_date']
        cup_position = (cup_low_idx - cup_start_idx) / len(cup_period)

        if cup_rim_price <= handle_high * BREAKOUT_THRESHOLD:
            continue

        days_after = len(df) - handle_end_idx

        ma50 = df.iloc[-MA_SHORT:]['close'].mean()
        ma150 = df.iloc[-MA_MEDIUM:]['close'].mean()
        ma200 = df.iloc[-MA_LONG:]['close'].mean()
        ma200_prev = df.iloc[-MA_LONG-5:-MA_LONG]['close'].mean()

        bullish_arrangement = ma50 > ma150 > ma200
        ma200_rising = ma200 > ma200_prev

        return {
            'formation_date': str(handle_period.iloc[-1]['trade_date']),
            'handle_high': round(handle_high, 2),
            'handle_low': round(handle_low, 2),
            'handle_retrace': round(handle_retrace * 100, 2),
            'cup_high': round(cup_high, 2),
            'cup_low': round(cup_low, 2),
            'cup_depth': round(cup_depth * 100, 2),
            'cup_lowest_date': str(cup_lowest_date),
            'cup_position': round(cup_position * 100, 2),
            'cup_is_u_shape': 30 <= cup_position * 100 <= 70,
            'breakout_price': round(cup_rim_price, 2),
            'breakout_pct': round((cup_rim_price - handle_high) / handle_high * 100, 2),
            'days_after': days_after,
            'ma50': round(ma50, 2),
            'ma150': round(ma150, 2),
            'ma200': round(ma200, 2),
            'bullish_arrangement': bullish_arrangement,
            'ma200_rising': ma200_rising
        }


def calculate_rs_score(df: pd.DataFrame) -> float:
    if len(df) < 252:
        return 50.0
    price_12m_ago = df.iloc[-252]['close'] if len(df) >= 252 else df.iloc[0]['close']
    price_now = df.iloc[-1]['close']
    stock_return = (price_now - price_12m_ago) / price_12m_ago * 100

    if stock_return > 100:
        return 95.0
    elif stock_return > 50:
        return 85.0 + (stock_return - 50) / 2
    elif stock_return > 30:
        return 75.0 + (stock_return - 30) / 2
    elif stock_return > 10:
        return 65.0 + (stock_return - 10) / 2
    elif stock_return > 0:
        return 55.0 + stock_return / 2
    else:
        return max(30.0, 50.0 + stock_return / 2)


def analyze_stock_for_cups(code: str, name: str, start_date: str, end_date: str) -> dict:
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        query = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date ASC
        """
        df = pd.read_sql_query(query, conn, params=(code, start_date, end_date))
        conn.close()

        if len(df) < CUP_PERIOD_MAX + HANDLE_PERIOD_MAX:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': 'Insufficient data (need 310+ days)'
            }

        df = df.reset_index(drop=True)

        last = df.iloc[-1]

        if last.get('turnover', 0) < MIN_TURNOVER:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': f'Turnover too low: {last.get("turnover", 0):.2f}% < {MIN_TURNOVER}%'
            }

        if last.get('pct_change', 0) < MIN_PCT_CHANGE:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': f'Pct change too low: {last.get("pct_change", 0):.2f}% < {MIN_PCT_CHANGE}%'
            }

        has_volume_surge, volume_ratio = check_volume_surge(df)
        if not has_volume_surge:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': f'No volume surge: ratio {volume_ratio:.2f}x < {VOLUME_SURGE_RATIO}x'
            }

        if len(df) < MA_LONG:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': 'Insufficient MA data'
            }

        ma50 = df.iloc[-MA_SHORT:]['close'].mean()
        ma150 = df.iloc[-MA_MEDIUM:]['close'].mean()
        ma200 = df.iloc[-MA_LONG:]['close'].mean()
        ma200_prev = df.iloc[-MA_LONG-5:-MA_LONG]['close'].mean()

        bullish_arrangement = ma50 > ma150 > ma200
        ma200_rising = ma200 > ma200_prev

        if not bullish_arrangement:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': 'MA not bullish (need MA50 > MA150 > MA200)'
            }

        if not ma200_rising:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': 'MA200 not rising (need upward long-term trend)'
            }

        rs_score = calculate_rs_score(df)
        if rs_score < RS_MIN_SCORE:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': f'RS score too low: {rs_score:.0f} < {RS_MIN_SCORE}'
            }

        cup_formation = find_cup_handle_formation(df)

        if cup_formation is None:
            return {
                'code': code,
                'name': name,
                'start_date': start_date,
                'end_date': end_date,
                'cup_formed': False,
                'reason': 'No valid cup handle formation found'
            }

        cup_formation.update({
            'code': code,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'cup_formed': True,
            'reason': None,
            'volume_ratio': volume_ratio,
            'ma50': ma50,
            'ma150': ma150,
            'ma200': ma200,
            'rs_score': rs_score
        })

        return cup_formation

    except Exception as e:
        logger.error(f"Error analyzing {code}: {e}")
        return {
            'code': code,
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'cup_formed': False,
            'reason': f'Exception: {str(e)}'
        }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 70)
    logger.info("Manual Coffee Cup Formation Labeling")
    logger.info("=" * 70)

    start_date = '2024-09-01'
    end_date = '2025-05-26'

    logger.info(f"Analysis period: {start_date} to {end_date}")

    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    stocks_query = """
        SELECT code, name, industry
        FROM stocks
        WHERE is_delisted = 0
        AND code NOT LIKE '399%'
        AND code NOT LIKE '43%'
        AND code NOT LIKE '83%'
        AND code NOT LIKE '87%'
        AND code NOT LIKE '88%'
        AND name NOT LIKE '%ST%'
        AND name NOT LIKE '%退%'
        AND name NOT LIKE '%指数%'
        AND name NOT LIKE '%ETF%'
        AND name NOT LIKE '%LOF%'
        AND name NOT LIKE '%REITs%'
        ORDER BY code
    """

    cursor = conn.execute(stocks_query)
    stocks = cursor.fetchall()
    conn.close()

    logger.info(f"Total stocks to analyze: {len(stocks)}")

    results = []
    for stock in stocks:
        code, name, industry = stock

        result = analyze_stock_for_cups(code, name, start_date, end_date)
        results.append(result)

        if len(results) % 100 == 0:
            logger.info(f"Processed: {len(results)} stocks...")

    cup_formed = [r for r in results if r['cup_formed']]
    no_cup = [r for r in results if not r['cup_formed']]

    logger.info("=" * 70)
    logger.info("Analysis Complete")
    logger.info("=" * 70)
    logger.info(f"Total stocks analyzed: {len(results)}")
    logger.info(f"Cup formations found: {len(cup_formed)}")
    logger.info(f"No cup formations: {len(no_cup)}")

    output_file = OUTPUT_DIR / f'manual_cup_labels_{datetime.now().strftime("%Y%m%d")}.csv'
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Results saved to: {output_file}")

    print("\n" + "=" * 70)
    print("Manual Cup Labeling Complete")
    print("=" * 70)
    print(f"  Total stocks analyzed: {len(results)}")
    print(f"  Cup formations found: {len(cup_formed)} ({len(cup_formed)/len(results):.1%})")
    print(f"  No cup formations: {len(no_cup)}")
    print(f"\nResults saved to: {output_file}")
    print("=" * 70)

    if cup_formed:
        print(f"\nSample cup formations ({min(5, len(cup_formed))}):")
        for cup in cup_formed[:5]:
            print(f"  {cup['code']} ({cup['name']}): {cup['formation_date']}")
            print(f"    - Cup depth: {cup['cup_depth']}%, Handle retrace: {cup['handle_retrace']}%")

    return str(output_file)


if __name__ == '__main__':
    main()
