#!/usr/bin/env python3
"""
Direct Ground Truth Dataset Builder

Simple, direct approach without complex formatting.
Uses er_ban_hui_tiao and breakout_20day as ground truth.
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

# Target screeners
TARGET1 = 'er_ban_hui_tiao'
TARGET2 = 'breakout_20day'

# Date range
START_DATE = '2024-09-01'
END_DATE = '2025-05-26'
LOOKBACK_DAYS = 30


def get_stocks():
    """Get all A-share stocks from database"""
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

    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    logger.info(f"Total stocks: {len(stocks)}")
    return stocks


def load_screener_file(screener_name, date_str):
    """Load screener results for specific date"""
    screener_dir = SCREENERS_DIR / screener_name
    file_path = screener_dir / f'{date_str}.xlsx'

    if not file_path.exists():
        return []

    try:
        df = pd.read_excel(file_path)

        # Find stock code column
        stock_col = None
        for col in df.columns:
            if 'code' in col.lower() or '股票代码' in col:
                stock_col = col
                break

        if stock_col is None:
            logger.warning(f"No stock column in {file_path}")
            return []

        # Get stock codes
        return df[stock_col].dropna().astype(str).tolist()

    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return []


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("=" * 70)
    logger.info("Ground Truth Dataset Builder - Direct")
    logger.info("=" * 70)

    logger.info(f"Period: {START_DATE} to {END_DATE}")
    logger.info(f"Target: {TARGET1} + ', ' + TARGET2)

    # Get all stocks
    logger.info("Loading stocks...")
    all_stocks = get_stocks()
    all_stock_codes = {s[0] for s in all_stocks}
    logger.info(f"Total stocks: {len(all_stocks)}")

    # Load target screener results
    logger.info(f"Loading {TARGET1} results...")
    target1_results = load_screener_file(TARGET1, START_DATE)
    logger.info(f"Found {len(target1_results)} stocks")

    logger.info(f"Loading {TARGET2} results...")
    target2_results = load_screener_file(TARGET2, START_DATE)
    logger.info(f"Found {len(target2_results)} stocks")

    # Find positive stocks (appeared in either target)
    all_positive_codes = set()

    for screener_results in [target1_results, target2_results]:
        for date_str, stock_codes in screener_results.items():
            all_positive_codes.update(stock_codes)

    logger.info(f"Total positive stocks: {len(all_positive_codes)}")

    # Build dataset
    records = []

    for stock in all_stocks:
        code = stock

        # Check if positive
        is_positive = code in all_positive_codes

        # Check target1
        first_trigger_date1 = None
        if START_DATE in target1_results:
            if code in target1_results:
                if START_DATE in target1_results:
                    for trigger_date, trigger_stocks in target1_results.items():
                        if code in trigger_stocks:
                            if first_trigger_date1 is None or trigger_date < first_trigger_date1:
                                first_trigger_date1 = trigger_date

        # Check target2
        first_trigger_date2 = None
        if START_DATE in target2_results:
            if code in target2_results:
                if START_DATE in target2_results:
                    for trigger_date, trigger_stocks in target2_results.items():
                        if code in trigger_stocks:
                            if first_trigger_date2 is None or trigger_date < first_trigger_date2:
                                first_trigger_date2 = trigger_date

        records.append({
            'code': code,
            'is_positive': is_positive
        })

    logger.info(f"Dataset built: {len(records)} records")

    # Count statistics
    positive_count = sum(1 for r in records if r['is_positive'])
    negative_count = sum(1 for r in records if not r['is_positive'])

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_{timestamp}.csv'

    # Simple columns - no dynamic column names
    columns = ['code', 'is_positive', 'target_er_ban_hui_tiao_date', 'target_breakout_20day_date']

    df = pd.DataFrame(records, columns=columns)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Saved to: {output_file}")

    # Print summary
    print("\n" + "=" * 70)
    print("Ground Truth Dataset Builder Complete")
    print("=" * 70)
    print(f"  Total records: {len(df)}")
    print(f"  Positive: {positive_count}")
    print(f"  Negative: {negative_count}")
    print(f"  Positive rate: {positive_count / len(df) * 100:.2f}%")
    print(f"\nDataset: {output_file}")
    print("=" * 70)

    return output_file


if __name__ == '__main__':
    main()
