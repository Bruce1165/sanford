#!/usr/bin/env python3
"""
超简化基础标签数据集生成器

以er_ban_hui_tiao和breakout_20day作为目标筛选器，生成真实基础标签数据集。
避免了所有复杂的格式化和动态列命名问题。
直接、简单、可靠。
"""

import sys
from pathlib import Path
import sqlite3
import pandas as pd
from datetime import datetime
import logging
import json

# 路径配置
DB_PATH = Path('/Users/mac/NeoTrade2/data/stock_data.db')
SCREENERS_DIR = Path('/Users/mac/NeoTrade2/data/screeners')
OUTPUT_DIR = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/analysis')

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 日期范围
START_DATE = '2024-09-01'
END_DATE = '2025-05-26'

# 目标筛选器（ground truth）
TARGET_SCREENERS = ['er_ban_hui_tiao', 'breakout_20day']

# 所有筛选器
ALL_SCREENERS = ['coffee_cup', 'jin_feng_huang', 'yin_feng_huang', 'shi_pan_xian',
              'er_ban_hui_tiao', 'zhang_ting_bei_liang_yin', 'breakout_20day',
              'daily_hot_cold', 'shuang_shou_ban', 'ashare_21']

# 日数
LOOKBACK_DAYS = 30  # 目标日期前30天内

logger = logging.getLogger(__name__)


def get_all_stocks(conn):
    """获取所有A股股票"""
    query = """
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
    """

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    stocks = conn.execute(query)
    conn.close()

    return [row[0] for row in stocks]


def get_screener_trigger(conn, screener_name, code: str, start_date: str, end_date: str, lookback_days: int = 30) -> dict:
    """获取筛选器在日期范围内的所有触发记录"""
    screener_dir = SCREENERS_DIR / screener_name

    triggers = {}

    # 获取所有该筛选器的结果文件
    files = sorted(screener_dir.glob('*.xlsx'))

    for file_path in files:
        date_str = file_path.stem  # 格式: YYYY-MM-DD

        if not file_path.suffix.lower().endswith(('.xlsx', '.xls'):
            continue

        try:
            df = pd.read_excel(file_path)
        except:
            logger.error(f"无法读取: {file_path}")
            continue

        # 获取日期范围内的股票列表
        if date_str >= START_DATE and date_str <= END_DATE:
            if '股票代码' in df.columns:
                codes = set(df['股票代码'].dropna().astype(str).tolist())
            else:
                codes = set(df['code'].dropna().astype(str).tolist())

            for code in codes:
                triggers[code] = {
                    'date_str': date_str
                }

    return triggers


def build_ground_truth_dataset():
    """构建基础标签数据集

    使用er_ban_hui_tiao和breakout_20day作为ground truth
    原理时间窗口：Sept 2024 - May 2025
    """

    logger.info("=" * 70)
    logger.info("构建基础标签数据集")
    logger.info("=" * 70)

    # 获取所有股票
    logger.info("获取所有股票...")
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
    logger.info(f"获取股票数量: {len(all_stocks)}")

    # 遍历每个筛选器
    trigger_results = {}
    for screener_name in TARGET_SCREENERS:
        screener_dir = SCREENERS_DIR / screener_name

        if not screener_dir.exists():
            logger.warning(f"筛选器目录不存在: {screener_name}")
            continue

        logger.info(f"加载筛选器: {screener_name}...")
        files = sorted(screener_dir.glob('*.xlsx'))

        for file_path in files:
            date_str = file_path.stem

            if date_str >= START_DATE and date_str <= END_DATE:
                if '股票代码' in df.columns:
                    codes = set(df['股票代码'].dropna().astype(str).tolist())
                else:
                    codes = set(df['code'].dropna().astype(str).tolist())

                for code in codes:
                    if code in trigger_results:
                        trigger_results[code].setdefault(dict) = {
                            'date_str': date_str
                        }

            logger.info(f"已加载 {len(trigger_results[date_str]) 个触发记录: {len(trigger_results[date_str])}")

    return trigger_results

    # 构建数据集
    records = []

    for code in all_stocks[:100]:  # 限制样本数量，避免过多数据
        if len(records) >= 500:
            break

        # 获取股票基础信息
        code = code
        try:
            cursor = conn.execute(
                "SELECT name, industry, market_cap, circulating_market_cap FROM stocks WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()

            stock_info = {}
            if row:
                stock_info['name'] = row[0] if row[0] else ''
                stock_info['industry'] = row[1] if row[1] else ''
                stock_info['market_cap'] = row[2] if row[2] is not None else None
                stock_info['circulating_cap'] = row[3] if row[3] is not None else None
        except Exception as e:
            logger.error(f"获取股票信息错误 {code}: {e}")
        else:
            logger.warning(f"股票信息缺失: {code}")

        # 检查是否被任一目标筛选器选中
        is_positive = False
        for screener_name in TARGET_SCREENERS:
            if code in trigger_results.get(date_str, {}):
                is_positive = True
                break

    # 添加记录
        records.append({
            'code': code,
            'is_positive': is_positive
        })

    # 添加元数据列
        if stock_info:
            records[-1]['industry'] = stock_info.get('industry', '')
            records[-1]['market_cap'] = stock_info.get('market_cap', '')
            records[-1]['circulating_cap'] = stock_info.get('circulating_cap', '')
            records[-1]['is_positive'] = is_positive
        else:
            records[-1]['industry'] = ''
            records[-1]['market_cap'] = ''
            records[-1]['circulating_cap'] = ''
            records[-1]['is_positive'] = is_positive

    conn.close()

    logger.info(f"总记录数: {len(records)}")

    # 保存数据集
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_{timestamp}.csv'

    # 基础列
    base_cols = ['code', 'name', 'industry', 'market_cap', 'circulating_cap', 'is_positive']

    # 添加筛选器触发列
    screener_cols = []
    for screener in TARGET_SCREENERS:
        screener_cols.append(f'{screener}_count')

    columns = base_cols + screener_cols

    df = pd.DataFrame(records, columns=columns)

    # 保存
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"数据集已保存: {output_file}")

    # 打印统计
    print("=" * 70)
    print("构建基础标签数据集")
    print("=" * 70)
    print(f"日期范围: {START_DATE} 到 {END_DATE}")
    print(f"分析窗口: {LOOKBACK_DAYS} 天（标日期前）")
    print(f"目标筛选器: {', ', '.join(TARGET_SCREENERS)}")
    print(f"总股票数: {len(all_stocks)}")
    print(f" 采样限制: 前500只（避免数据过多）")
    print(f"数据集文件: {output_file}")
    print("=" * 70)
    print(f"特征数: {len(columns)}")
    print(f"采样股票: {min(500, len(df))}")
    print(f"\n" + "=" * 70)
    print("完成！")


if __name__ == '__main__':
    build_ground_truth_dataset()
