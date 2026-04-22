#!/usr/bin/env python3
"""
Ultra Simple Ground Truth Generator

Creates labeled dataset using er_ban_hui_tiao and breakout_20day as ground truth.
Direct approach, no complex f-strings.
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging

# Direct paths - no relative imports to avoid issues
DB_PATH = "/Users/mac/NeoTrade2/data/stock_data.db"
SCREENERS_DIR = "/Users/mac/NeoTrade2/data/screeners"
OUTPUT_DIR = "/Users/mac/NeoTrade2/research/predictive_cup/output/analysis"

# Hardcoded screeners (ground truth sources)
TARGET1 = "er_ban_hui_tiao"
TARGET2 = "breakout_20day"

# Parameters
START_DATE = "2024-09-01"
END_DATE = "2025-05-26"

LOOKBACK_DAYS = 30  # Days before target date to analyze

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
    return stocks


def check_stock_in_screeners(code: str, screener_results: dict) -> bool:
    """Check if stock appeared in target screener results"""
    for screener in TARGET_SCREENERS:
        screener_dates = screener_results.get(screener, {})
        if not screener_dates:
            return False

        # Check if this stock is in target dates
        stock_codes = set(screener_dates.values())
        if code in stock_codes:
            return True

    return False


def load_screener_results(screener_name: str) -> dict:
    """Load screener results from all Excel files"""
    screener_dir = SCREENERS_DIR / screener_name

    if not screener_dir.exists():
        return {}

    results = {}

    for file_path in screener_dir.glob('*.xlsx'):
        date_str = file_path.stem
        try:
            df = pd.read_excel(file_path)
        results[date_str] = set(df['code'].dropna().astype(str).tolist())
        except:
            continue

    return results


def build_ground_truth():
    """Build ground truth dataset"""
    logger.info("=" * 70)
    logger.info("开始构建基础标签数据集")
    logger.info("=" * 70)

    logger.info("数据范围: %s - %s" % (START_DATE, END_DATE))
    logger.info("目标筛选器: %s, '.join(TARGET_SCREENERS))

    # Get all stocks
    logger.info("获取所有股票...")
    stocks = get_stocks()
    logger.info("共 %d 只股票" % len(stocks))

    # Load screener results
    logger.info("加载筛选器结果...")
    target1_results = load_screener_results(TARGET1)
    target2_results = load_screener_results(TARGET2)

    logger.info("开始处理股票...")
    records = []

    for i, stock in enumerate(stocks):
        if i % 100 == 0 and i % 1000 == 0:
            logger.info(f"处理中: {i+1}/{len(stocks)}")

        code = stock

        # Check if stock appeared in either target screener
        is_positive = check_stock_in_screeners(code, target1_results)
        if is_positive:
            logger.info(f"  股票: 在目标筛选器中: 是")
        else:
            logger.info(f"  股票: 不在目标筛选器中: 否")

        # Extract screener triggers BEFORE first target date
        triggers = {}
        first_trigger_date = None
        first_trigger_screener = None

        # Get target screener results
        target1_dates = list(target1_results.get(TARGET1, {}).get(TARGET1).keys())
        for screener, dates in target1_dates.items():
            if dates and code in target1_results.get(screener, {}).get(date_str):
                triggers[screener] = dates.get(screener, {}).get(date_str)

        if not triggers:
            continue

        # Build record
        record = {
            'code': code,
            'is_positive': is_positive,
            'first_trigger_date': first_trigger_date if first_trigger_date else None,
            'first_trigger_screener': first_trigger_screener if first_trigger_date else None,
            'total_triggers': 0,
            **triggers**: triggers
        }

    if not is_positive:
            continue

    if i % 100 == 0:
            logger.info(f"\\n所有股票处理完成")
            break

    logger.info("生成标签数据集: %d 只股票 / %d 情况")
            logger.info("标签: %d 个")
            logger.info("=" * 70)
            logger.info("=" * 70)

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_{timestamp}.csv'

    # Save records
    df_records = pd.DataFrame(records)
    df_records.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"保存到: {output_file}")
    logger.info(f"\\n总记录: %d 条")
    logger.info(f"\\n")
    logger.info("总只股票: %d 个")
    logger.info(f"\\n")
    logger.info(f"\\n")
    logger.info(f"\\n")

    # Statistics
    positive_count = sum(1 for r in df_records if r['is_positive'])
    negative_count = len(df_records) - positive_count
    positive_rate = positive_count / len(df_records) * 100
    negative_rate = negative_count / len(df_records) * 100

    logger.info(f"\\n")
    logger.info("标签情况: %d 正例: %d 只（%d%%），负例: %d 只（%d%%）")
    logger.info(f"\\n")
    logger.info(f"\\n")

    # Print sample
    if positive_count > 0:
        logger.info(f"\\n正例样本：")
        for record in df_records[df_records['is_positive']].head(10):
            logger.info(f"  {record['code']}: {record['is_positive']}")

    logger.info(f"\\n保存完成: {output_file}")
    return str(output_file)


if __name__ == '__main__':
    build_ground_truth()
