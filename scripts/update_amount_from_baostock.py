#!/usr/bin/env python3
"""
使用 Baostock 数据更新数据库中 amount 字段
只更新 amount 字段，不影响其他字段
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'scripts'))

from config import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def update_amount_for_stock(conn, stock_code, start_date, end_date):
    """更新单只股票的 amount 字段"""
    import baostock as bs

    # 格式化股票代码为 Baostock 格式 (sh.600000 或 sz.000000)
    if stock_code.startswith('6'):
        formatted_code = f"sh.{stock_code}"
    else:
        formatted_code = f"sz.{stock_code}"

    fields = 'date,code,amount'

    try:
        rs = bs.query_history_k_data_plus(
            code=formatted_code,
            fields=fields,
            start_date=start_date,
            end_date=end_date,
            frequency='d',
            adjustflag='2'
        )

        updated = 0
        failed = 0

        cursor = conn.cursor()

        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            if not row:
                continue

            trade_date = row[0]
            amount = row[2]  # amount 在第3个字段 (0=date, 1=code, 2=amount)

            if not amount or amount == '':
                continue

            try:
                cursor.execute(
                    "UPDATE daily_prices SET amount = ? WHERE code = ? AND trade_date = ?",
                    (float(amount), stock_code, trade_date)
                )
                updated += 1
            except Exception as e:
                logger.error(f"更新{stock_code} {trade_date}失败: {e}")
                failed += 1

        conn.commit()
        cursor.close()

        logger.info(f"[{stock_code}] 更新{updated}条记录, 失败{failed}条")

        return updated, failed

    except Exception as e:
        logger.error(f"处理{stock_code}失败: {e}")
        return 0, 1


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='更新 amount 字段')
    parser.add_argument('--start-date', type=str, help='开始日期 (YYYY-MM-DD)')
    args = parser.parse_args()

    # 计算日期范围
    end_date = datetime.now().strftime('%Y-%m-%d')

    if args.start_date:
        start_date = args.start_date
    else:
        # 默认获取最近1年数据
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    print(f"数据范围: {start_date} 到 {end_date}")
    print(f"操作: UPDATE（仅更新 amount 字段）")

    # 连接数据库
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        # 获取所有股票代码
        cursor = conn.execute("SELECT code FROM stocks WHERE is_delisted = 0")
        stock_codes = [row[0] for row in cursor.fetchall()]
        cursor.close()

        logger.info(f"找到{len(stock_codes)}只股票")

        # 登录 Baostock
        import baostock as bs
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"Baostock 登录失败: {lg.error_msg}")
            return

        logger.info("Baostock 登录成功")

        total_updated = 0
        total_failed = 0
        processed = 0

        # 处理每只股票
        for i, stock_code in enumerate(stock_codes):
            updated, failed = update_amount_for_stock(conn, stock_code, start_date, end_date)
            total_updated += updated
            total_failed += failed
            processed += 1

            # 每100只股票休息一下
            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i+1}/{len(stock_codes)} ({(i+1)/len(stock_codes)*100:.1f}%) 更新: {total_updated}条")
                time.sleep(2)

        # 登出
        bs.logout()
        logger.info("Baostock 登出")

        # 打印统计
        logger.info("=" * 60)
        logger.info("更新完成")
        logger.info(f"总共处理: {processed}只股票")
        logger.info(f"成功更新: {total_updated}条记录")
        logger.info(f"失败: {total_failed}条记录")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"处理过程中出错: {e}", exc_info=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
