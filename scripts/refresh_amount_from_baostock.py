#!/usr/bin/env python3
"""
使用 Baostock 数据覆盖数据库中的 amount 字段

确保成交额数据的一致性和正确性
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time

# 添加路径
if 'WORKSPACE_ROOT' in __import__('os').environ:
    workspace_root = Path(__import__('os').environ['WORKSPACE_ROOT'])
else:
    workspace_root = Path(__file__).parent.parent

sys.path.insert(0, str(workspace_root))
sys.path.insert(0, str(workspace_root / 'scripts'))

from config import DB_PATH, DATA_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_stock_codes(conn):
    """获取所有股票代码"""
    cursor = conn.execute("SELECT code FROM stocks WHERE is_delisted = 0")
    raw_codes = [row[0] for row in cursor.fetchall()]

    # 格式化为 Baostock 格式 (sh.600000 或 sz.000000)
    formatted_codes = []
    for code in raw_codes:
        # 判断市场（以6开头的上海，以0开头的深圳）
        if code.startswith('6'):
            formatted_code = f"sh.{code}.000"
        else:
            formatted_code = f"sz.{code}.000"
        formatted_codes.append(formatted_code)

    return formatted_codes


def format_baostock_code(stock_code):
    """格式化股票代码为 Baostock 格式 (sh.600000)"""
    return f"sh.{stock_code}.000"


def fetch_baostock_amount(formatted_code, start_date, end_date):
    """从 Baostock 获取单个股票的 amount 数据
    formatted_code 已经是 Baostock 格式 (sh.600000 或 sz.000000)
    """
    import baostock as bs

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

        data_list = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            data_list.append((row[0], row[6]))  # date, amount

        return data_list

    except Exception as e:
        logger.error(f"获取{formatted_code}数据失败: {e}")
        return []


def update_database_amounts(conn, stock_updates):
    """批量更新数据库中的 amount 字段"""
    if not stock_updates:
        return

    updated = 0
    failed = 0

    cursor = conn.cursor()

    try:
        # 使用事务
        conn.execute("BEGIN TRANSACTION")

        for stock_code, data_updates in stock_updates:
            for trade_date, amount in data_updates:
                try:
                    # 更新 amount 字段
                    cursor.execute(
                        """
                        UPDATE daily_prices
                        SET amount = ?
                        WHERE code = ? AND trade_date = ?
                        """,
                        (amount, stock_code, trade_date)
                    )
                    updated += 1
                except Exception as e:
                    logger.error(f"更新{stock_code} {trade_date}失败: {e}")
                    failed += 1

        # 提交事务
        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.error(f"批量更新失败: {e}")
    finally:
        cursor.close()

    return updated, failed


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始使用 Baostock 数据覆盖 amount 字段")
    logger.info("=" * 60)

    # 连接数据库
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        # 获取所有股票代码
        stock_codes = get_all_stock_codes(conn)
        logger.info(f"找到{len(stock_codes)}只股票")

        # 计算日期范围（获取最近1年数据）
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

        logger.info(f"数据范围: {start_date} 到 {end_date}")

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

        # 批量处理
        batch_size = 50
        batch_updates = []

        for i, formatted_code in enumerate(formatted_codes):
            # 获取数据（formatted_code 已经是 Baostock 格式）
            data_updates = fetch_baostock_amount(formatted_code, start_date, end_date)
            if data_updates:
                batch_updates.append((formatted_code, data_updates))
                processed += 1

                # 达到批量大小时更新数据库
                if len(batch_updates) >= batch_size or i == len(stock_codes) - 1:
                    updated, failed = update_database_amounts(conn, batch_updates)
                    total_updated += updated
                    total_failed += failed
                    batch_updates = []

                    logger.info(f"进度: {processed}/{len(stock_codes)} "
                               f"({processed/len(stock_codes)*100:.1f}%)")

                    # 每100只股票休息一下
                    if processed % 100 == 0:
                        logger.info("休息2秒...")
                        time.sleep(2)

        # 更新最后一批
        if batch_updates:
            updated, failed = update_database_amounts(conn, batch_updates)
            total_updated += updated
            total_failed += failed

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
