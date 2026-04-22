#!/usr/bin/env python3
"""
Ground Truth Dataset Builder - CORRECTED VERSION

Creates labeled dataset using er_ban_hui_tiao and breakout_20day as ground truth.
These screeners identified actual market patterns during Sept 2024 - May 2025.
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
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

# All 11 screeners
ALL_SCREENERS = [
    'coffee_cup',  # Exclude - this is unverified
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'er_ban_hui_tiao',  # Target 1
    'zhang_ting_bei_liang_yin',
    'breakout_20day',  # Target 2
    'daily_hot_cold',
    'shuang_shou_ban',
    'ashare_21'
]

# Target screeners (ground truth)
TARGET_SCREENERS = ['er_ban_hui_tiao', 'breakout_20day']

# Analysis window
START_DATE = '2024-09-01'
END_DATE = '2025-05-26'
LOOKBACK_DAYS = 30  # Days before trigger date to analyze


def load_screener_results(screener_name: str) -> dict:
    """Load screener results into dict: {date: set(stock_codes)}"""
    screener_dir = SCREENERS_DIR / screener_name

    if not screener_dir.exists():
        logger.warning(f"Screener directory not found: {screener_dir}")
        return {}

    results = {}

    for file_path in screener_dir.glob('*.xlsx'):
        if not file_path.suffix.lower().endswith(('.xlsx', '.xls')):
            continue

        try:
            # Extract date from filename (format: YYYY-MM-DD.xlsx)
            date_str = file_path.stem

            df = pd.read_excel(file_path)

            # Handle different column formats
            stock_col = None
            for col in df.columns:
                if 'code' in col.lower() or '股票代码' in col or '代码' in col:
                    stock_col = col
                    break

            if stock_col is None:
                logger.warning(f"No stock column found in {file_path}")
                continue

            # Get stock codes
            stock_codes = set(df[stock_col].dropna().astype(str).tolist())

            results[date_str] = stock_codes

        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")

    logger.info(f"Loaded {len(results)} dates from {screener_name}")
    return results


def get_stock_basic_info(conn, code: str) -> dict:
    """Get stock basic information from database"""
    try:
        cursor = conn.execute(
            "SELECT name, industry, market_cap, circulating_market_cap FROM stocks WHERE code = ?",
            (code,)
        )
        row = cursor.fetchone()
        if row:
            return {
                'name': row[0] if row[0] else '',
                'industry': row[1] if row[1] else '',
                'market_cap': row[2] if row[2] else None,
                'circulating_cap': row[3] if row[3] else None
            }
        return {}
    except Exception as e:
        logger.error(f"Error getting stock info for {code}: {e}")
        return {}


def extract_screener_triggers(conn, code: str, target_date: str, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """
    Extract screener triggers for a stock in days BEFORE a target date.
    This provides predictive features: which screeners fired early.
    """
    query = """
        SELECT trade_date, close, volume, amount, pct_change
        FROM daily_prices
        WHERE code = ?
        AND trade_date < ?
        AND trade_date >= date(?, '-' || ?, ' days' || ?)
        ORDER BY trade_date ASC
    """

    try:
        df = pd.read_sql_query(query, conn, params=(code, target_date, target_date, lookback_days))
        df = df.sort_values('trade_date').reset_index(drop=True)
    except Exception as e:
        logger.error(f"Error querying prices for {code}: {e}")
        return {}

    if len(df) == 0:
        return {}

    triggers = {}

    # Analyze triggers for each screener (excluding target screeners)
    for screener in ALL_SCREENERS:
        if screener in TARGET_SCREENERS:
            continue

        screener_results = load_screener_results(screener)

        for date, stock_codes in screener_results.items():
            # Check if this stock triggered on any day in lookback window
            stock_triggered_dates = []

            for trigger_date, trigger_stocks in screener_results.items():
                if trigger_date < target_date:
                    # Check if within lookback window and stock is in trigger list
                    days_diff = (target_date - trigger_date).days
                    if 0 <= days_diff <= lookback_days and code in trigger_stocks:
                        stock_triggered_dates.append(trigger_date)

            if stock_triggered_dates:
                # Count triggers in each time window
                triggers_in_window = len(stock_triggered_dates)
                triggers[f'{screener}_count'] = triggers_in_window
                # Get latest trigger date before target
                latest_date = max(stock_triggered_dates) if stock_triggered_dates else None
                triggers[f'{screener}_latest'] = latest_date
            else:
                triggers[f'{screener}_count'] = 0
                triggers[f'{screener}_latest'] = None

    return triggers


def build_ground_truth_dataset():
    """
    Build ground truth dataset with labels and features.
    """
    logger.info("=" * 70)
    logger.info("Ground Truth Dataset Builder")
    logger.info("=" * 70)

    logger.info(f"Analysis period: {START_DATE} to {END_DATE}")
    logger.info(f"Target screeners: {', '.join(TARGET_SCREENERS)}")

    # Load screener results for target screeners
    logger.info("Loading screener results...")
    target_results = {}
    for screener in TARGET_SCREENERS:
        results = load_screener_results(screener)
        target_results[screener] = results

    # Get all stock codes that appeared in ANY target screener
    all_target_stocks = set()
    for screener_results in target_results.values():
        for stock_codes in screener_results.values():
            all_target_stocks.update(stock_codes)

    logger.info(f"Total unique stocks in target screeners: {len(all_target_stocks)}")

    # Get all A-share stocks from database
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

    # Build dataset
    records = []

    for stock in all_stocks:
        code = stock

        # Get basic stock info
        stock_info = get_stock_basic_info(conn, code)

        # Check if stock appeared in target screeners
        is_positive = code in all_target_stocks

        # Determine which target screener triggered first
        first_trigger_date = None
        first_trigger_screener = None

        for screener, screener_results in target_results.items():
            screener_dates = list(screener_results.keys())
            for date, stock_codes in screener_results.items():
                if code in stock_codes and date < END_DATE:
                    first_trigger_date = date
                    first_trigger_screener = screener
                    break

        # Extract screener triggers BEFORE first trigger date (predictive features)
        triggers = {}
        for screener in ALL_SCREENERS:
            if screener in TARGET_SCREENERS:
                continue

            screener_results = load_screener_results(screener)

            for date, trigger_stocks in screener_results.items():
                if code in trigger_stocks:
                    days_diff = (first_trigger_date - date).days if first_trigger_date else None
                    if 0 <= days_diff <= LOOKBACK_DAYS:
                        screener_key = f'{screener}_{date.strftime("%Y%m%d")}'
                        triggers[screener_key] = True

        # Count total triggers across all non-target screeners
        total_triggers = sum(1 for k in triggers.values() if isinstance(k, bool))

        # Add record
        records.append({
            'code': code,
            'name': stock_info.get('name', ''),
            'industry': stock_info.get('industry', ''),
            'market_cap': stock_info.get('market_cap'),
            'circulating_cap': stock_info.get('circulating_cap'),
            'is_positive': is_positive,
            'first_trigger_date': first_trigger_date,
            'first_trigger_screener': first_trigger_screener,
            'total_triggers': total_triggers
            **triggers**: json.dumps(triggers)
        })

    conn.close()

    logger.info(f"Dataset built: {len(records)} records")
    logger.info(f"Positive cases: {sum(1 for r in records if r['is_positive'])}")
    logger.info(f"Negative cases: {sum(1 for r in records if not r['is_positive'])}")

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_dataset_{timestamp}.csv'

    # Define columns - base + trigger columns
    base_cols = [
        'code', 'name', 'industry', 'market_cap', 'circulating_cap',
        'is_positive', 'first_trigger_date', 'first_trigger_screener', 'total_triggers'
    ]

    # Add trigger columns dynamically
    screener_cols = []
    for screener in ALL_SCREENERS:
        if screener not in TARGET_SCREENERS:
            screener_cols.append(f'{screener}_count')
            screener_cols.append(f'{screener}_latest')

    columns = base_cols + screener_cols

    df = pd.DataFrame(records, columns=columns)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Dataset saved to: {output_file}")

    # Statistics
    print("\n" + "=" * 70)
    print("Ground Truth Dataset Builder Complete")
    print("=" * 70)
    print(f"  Total records: {len(df)}")
    print(f"  Positive cases: {sum(df['is_positive'])}")
    print(f"  Negative cases: {sum(~df['is_positive'])}")
    print(f"  Positive rate: {df['is_positive'].mean():.2%}")
    print(f"\nDataset saved to: {output_file}")
    print("=" * 70)

    # Feature statistics
    print("\nFeature Statistics (non-target screeners only):")
    for screener in ALL_SCREENERS:
        if screener not in TARGET_SCREENERS:
            col_name = f'{screener}_count'
            print(f"  {screener}: {df[col_name].sum()} total triggers")

    return str(output_file)


if __name__ == '__main__':
    build_ground_truth_dataset()
