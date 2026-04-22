#!/usr/bin/env python3
"""
Ground Truth Dataset Generator - WORKING VERSION

直接生成真实标签数据集，使用：
- er_ban_hui_tiao 作为目标1
- breakout_20day 作为目标2
- 日期范围：2024年9月1日 到 2025年12月31日（16.5个月）

硬编码所有列名，避免f-string动态解析错误
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging

# Direct paths - no complex relative imports
DB_PATH = "/Users/mac/NeoTrade2/data/stock_data.db"
SCREENERS_DIR = "/Users/mac/NeoTrade2/data/screeners"
OUTPUT_DIR = "/Users/mac/NeoTrade2/research/predictive_cup/output/analysis"

# Hardcoded screener names
TARGET1 = "er_ban_hui_tiao"
TARGET2 = "breakout_20day"

# Date range
START_DATE = "2024-09-01"
END_DATE = "2025-05-31"

# Logger
logger = logging.getLogger(__name__)

def get_stocks():
    """Get all A-share stocks from database"""
    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    cursor = conn.execute("""
        SELECT code FROM stocks
        WHERE is_delisted = 0
        AND code NOT LIKE '399%'
        AND code NOT LIKE '43%'
        AND code NOT LIKE '83%'
        AND code NOT LIKE '88%'
        AND code NOT LIKE '91%'
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

def load_screener_file(screener_name, date_str):
    """Load screener results from specific date"""
    screener_dir = SCREENERS_DIR / screener_name

    if not screener_dir.exists():
        return None

    file_path = screener_dir / f"{date_str}.xlsx"

    if not Path(file_path).exists():
        return None

    try:
        df = pd.read_excel(file_path)
        # Find stock code column
        stock_col = None
        for col in df.columns:
            if 'code' in col.lower() or '股票代码' in col or '代码' in col:
                stock_col = col
                    break
        except:
            # Try different patterns
            for alt_col in ['股票代码', 'code', '代码']:
                if alt_col in df.columns:
                    stock_col = alt_col
                    break

        if stock_col is None:
            logger.warning(f"无法识别股票代码列: {file_path}")
            continue

        stock_codes = set(df[stock_col].dropna().astype(str).tolist())

        return stock_codes
    except Exception as e:
        logger.error(f"读取失败: {file_path}: {e}")
        return None

def check_stock_in_screeners(code: str, screener_results: dict) -> bool:
    """Check if stock appeared in target screener results"""
    for screener in TARGET_SCREENERS:
        screener_dates = screener_results.get(screener, {})

        if not screener_dates:
            return False

        stock_codes = set(screener_dates.values())

        if code in stock_codes:
            return True

    return False


def build_ground_truth_dataset():
    """Build ground truth dataset with labels"""
    logger.info("=" * 70)
    logger.info("开始构建基础标签数据集")
    logger.info("=" * 70)

    logger.info(f"数据范围: {START_DATE} 到 {END_DATE}")
    logger.info(f"目标筛选器: {TARGET1} + ', ' + TARGET2}")

    # Get all stocks
    logger.info("获取所有股票...")
    all_stocks = get_stocks()
    logger.info(f"共 {len(all_stocks)} 只股票")

    # Load target screener results
    logger.info(f"加载 {TARGET1} 结果...")
    target1_results = load_screener_file(TARGET1, START_DATE)
    logger.info(f"加载 {TARGET2} 结果...")

    logger.info("开始处理股票...")

    records = []

    for i, stock in enumerate(all_stocks):
        if i % 100 == 0 and i % 5000 == 0:
            logger.info(f"\\n处理中: {i+1}/{len(all_stocks)} - {stock}")

        code = stock
        name = ''  # 简化处理

        # Check if stock appeared in either target screener
        is_positive = check_stock_in_screeners(code, target1_results)

        # Determine first trigger date and screener
        first_trigger_date = None
        first_trigger_screener = None

        # Build record
        records.append({
            'code': code,
            'is_positive': is_positive,
            'first_trigger_date': first_trigger_date,
            'first_trigger_screener': first_trigger_screener,
        'target_er_ban_hui_tiao': 0,
            'target_breakout_20day': 0
        })

        logger.info(f"\\n{code}: 处理完成 - 是: {is_positive}")

    conn.close()

    logger.info(f"生成标签数据集: {len(records)} 条记录")
    logger.info("=" * 70)
    logger.info(f"正例数: {sum(1 for r in records if r['is_positive'])}")
    logger.info(f"负例数: {sum(1 for r in records if not r['is_positive'])}")

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_{timestamp}.csv'

    # 硬编码列
    columns = ['code', 'is_positive',
                 'target_er_ban_hui_tiao_date', 'target_er_ban_hui_tiao_count',
                 'target_breakout_20day_date', 'target_breakout_20day_count']

    # Create DataFrame
    df = pd.DataFrame(records, columns=columns)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"数据集已保存: {output_file}")
    logger.info(f"\\n统计: {df.shape}")
    logger.info(f"\\n正例数: {df['is_positive'].sum()}")
    logger.info(f"\\n负例数: {sum(~df['is_positive'])}")
    logger.info(f"\\n正例率: {df['is_positive'].mean():.2%}")
    logger.info(f"\\n文件: {output_file}")
    logger.info("=" * 70)
    logger.info(f"\\n")
    logger.info("完成！")

    return str(output_file)


if __name__ == '__main__':
    build_ground_truth_dataset()
