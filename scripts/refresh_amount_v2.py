#!/usr/bin/env python3
"""
使用 Baostock 数据覆盖数据库中的 amount 字段

简化版本，避免复杂的作用域问题
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


def format_baostock_code(stock_code):
    """格式化股票代码为 Baostock 格式
    Baostock API 需要完整的 6 位代码，会自动添加前缀
    """
    # 直接返回原始的 6 位代码
    return stock_code


def refresh_single_stock(conn, stock_code, formatted_code, start_date, end_date):
    """刷新单只股票的 amount 数据"""
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

        if not data_list:
            return 0, 0

        # 更新数据库
        cursor = conn.cursor()
        updated = 0

        for trade_date, amount in data_list:
            try:
                cursor.execute(
                    "UPDATE daily_prices SET amount = ? WHERE code = ? AND trade_date = ?",
                    (amount, stock_code, trade_date)
                )
                updated += 1
            except Exception as e:
                logger.error(f"更新{stock_code} {trade_date}失败: {e}")

        conn.commit()
        cursor.close()

        return updated, len(data_list)

    except Exception as e:
        logger.error(f"刷新{stock_code}失败: {e}")
        return 0, 0


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
        cursor = conn.execute("SELECT code FROM stocks WHERE is_delisted = 0")
        raw_codes = [row[0] for row in cursor.fetchall()]

        logger.info(f"找到{len(raw_codes)}只股票")

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
        total_processed = 0
        total_failed = 0

        # 处理每只股票
        for i, stock_code in enumerate(raw_codes):
            formatted_code = format_baostock_code(stock_code)
            updated, expected = refresh_single_stock(conn, stock_code, formatted_code, start_date, end_date)
            total_updated += updated
            total_processed += 1
            total_failed += expected - updated

            # 每100只股票休息一下
            if (i + 1) % 100 == 0:
                logger.info(f"进度: {i+1}/{len(raw_codes)} "
                           f"({(i+1)/len(raw_codes)*100:.1f}%) "
                           f"更新: {total_updated}条")

                if i % 500 == 0:
                    logger.info("休息3秒...")
                    time.sleep(3)

        # 登出
        bs.logout()
        logger.info("Baostock 登出")

        # 打印统计
        logger.info("=" * 60)
        logger.info("更新完成")
        logger.info(f"总共处理: {len(raw_codes)}只股票")
        logger.info(f"成功更新: {total_updated}条记录")
        logger.info(f"失败: {total_failed}条记录")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"处理过程中出错: {e}", exc_info=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
