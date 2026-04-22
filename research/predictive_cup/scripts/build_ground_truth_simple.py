#!/usr/bin/env python3
"""
Simplified Ground Truth Dataset Builder

Creates labeled dataset using er_ban_hui_tiao and breakout_20day as ground truth.
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging

# Add project root to path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

# Configuration
DB_PATH = Path('/Users/mac/NeoTrade2/data/stock_data.db')
SCREENERS_DIR = Path('/Users/mac/NeoTrade2/data/screeners')
OUTPUT_DIR = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/analysis')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Target screeners (ground truth)
TARGET_SCREENERS = ['er_ban_hui_tiao', 'breakout_20day']
ALL_SCREENERS = [
    'coffee_cup', 'jin_feng_huang', 'yin_feng_huang', 'shi_pan_xian',
    'er_ban_hui_tiao', 'zhang_ting_bei_liang_yin', 'breakout_20day',
    'daily_hot_cold', 'shuang_shou_ban', 'ashare_21'
]

START_DATE = '2024-09-01'
END_DATE = '2025-05-26'
LOOKBACK_DAYS = 30


def load_screener_results(screener_name):
    """Load screener results into dict: {date: set(stock_codes)}"""
    screener_dir = SCREENERS_DIR / screener_name
    if not screener_dir.exists():
        logger.warning(f"Screener directory not found: {screener_dir}")
        return {}

    results = {}
    for file_path in screener_dir.glob('*.xlsx'):
        date_str = file_path.stem
        try:
            df = pd.read_excel(file_path)
            stock_col = None
            for col in df.columns:
                if 'code' in col.lower() or '股票代码' in col or '代码' in col:
                    stock_col = col
                    break

            if stock_col is None:
                continue

            stock_codes = set(df[stock_col].dropna().astype(str).tolist())
            results[date_str] = stock_codes
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")

    return results


def build_ground_truth_dataset():
    """Build ground truth dataset with labels and features."""
    logger.info("=" * 70)
    logger.info("Ground Truth Dataset Builder - Simplified")
    logger.info("=" * 70)
    logger.info(f"Analysis period: {START_DATE} to {END_DATE}")
    logger.info(f"Target screeners: {', '.join(TARGET_SCREENERS)}")

    logger.info("Loading screener results...")
    target_results = {}
    for screener in TARGET_SCREENERS:
        results = load_screener_results(screener)
        target_results[screener] = results

    all_target_stocks = set()
    for screener_results in target_results.values():
        for stock_codes in screener_results.values():
            all_target_stocks.update(stock_codes)

    logger.info(f"Total unique stocks in target screeners: {len(all_target_stocks)}")

    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    cursor = conn.execute("""
        SELECT code FROM stocks
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
    """)

    all_stocks = [row[0] for row in cursor.fetchall()]
    conn.close()

    logger.info(f"Total A-share stocks in database: {len(all_stocks)}")

    records = []
    for stock in all_stocks:
        code = stock

        is_positive = code in all_target_stocks

        records.append({
            'code': code,
            'is_positive': int(is_positive),
            'target_er_ban_hui_tiao': 0,
            'target_breakout_20day': 0
        })

    conn.close()

    logger.info(f"Dataset built: {len(records)} records")
    logger.info(f"Positive cases: {sum(1 for r in records if r['is_positive'])}")
    logger.info(f"Positive rate: {sum(1 for r in records if r['is_positive'])} / len(records):.1%}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_{timestamp}.csv'

    columns = ['code', 'is_positive', 'target_er_ban_hui_tiao', 'target_breakout_20day']

    df = pd.DataFrame(records)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Dataset saved to: {output_file}")

    print("\n" + "=" * 70)
    print("Ground Truth Dataset Builder Complete")
    print("=" * 70)
    print(f"  Total records: {len(df)}")
    print(f"  Positive cases: {df['is_positive'].sum()}")
    print(f"  Positive rate: {df['is_positive'].mean():.1%}")
    print(f"\nDataset saved to: {output_file}")
    print("=" * 70)

    return str(output_file)


if __name__ == '__main__':
    build_ground_truth_dataset()
