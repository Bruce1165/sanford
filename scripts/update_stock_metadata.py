#!/usr/bin/env python3
"""
sync_stock_basic_baostock.py — 从 BaoStock 同步股票基础信息到 stocks 表
更新字段：list_date, is_delisted, asset_type, sector_lv1, sector_lv2
数据源：BaoStock query_stock_basic + query_stock_industry
用法：python3 sync_stock_basic_baostock.py [--dry-run]
"""

import sys
import sqlite3
import logging
import argparse
from pathlib import Path
from datetime import datetime

import baostock as bs

WORKSPACE_ROOT = Path(__file__).parent.parent
DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(WORKSPACE_ROOT / "logs" / "sync_stock_basic.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_all_codes_from_db(conn):
    """获取数据库中所有股票代码"""
    cur = conn.execute("SELECT code FROM stock_meta ORDER BY code")
    return [row[0] for row in cur.fetchall()]


def to_bs_code(code: str) -> str:
    """000001 → sz.000001, 600000 → sh.600000"""
    if code.startswith('6') or code.startswith('9'):
        return f"sh.{code}"
    return f"sz.{code}"


def sync_basic(conn, codes, dry_run=False):
    """同步 list_date, is_delisted, asset_type"""
    logger.info(f"=== 同步基础信息（共 {len(codes)} 只）===")
    updated = skipped = failed = 0

    for i, code in enumerate(codes):
        bs_code = to_bs_code(code)
        try:
            rs = bs.query_stock_basic(code=bs_code)
            if rs.error_code != '0' or not rs.next():
                skipped += 1
                continue

            row = rs.get_row_data()
            # fields: code, code_name, ipoDate, outDate, type, status
            ipo_date  = row[2] if row[2] else None
            out_date  = row[3] if row[3] else None
            asset_type_raw = row[4]  # '1'=股票 '2'=指数 '3'=其他
            status    = row[5]       # '1'=上市 '0'=退市

            is_delisted = 0 if status == '1' else 1
            asset_type = 'stock'

            if not dry_run:
                conn.execute("""
                    UPDATE stocks SET
                        list_date   = COALESCE(?, list_date),
                        is_delisted = ?,
                        updated_at  = ?
                    WHERE code = ?
                """, (ipo_date, is_delisted, datetime.now().isoformat(), code))

            updated += 1

        except Exception as e:
            logger.warning(f"{code}: {e}")
            failed += 1

        if (i + 1) % 500 == 0:
            if not dry_run:
                conn.commit()
            logger.info(f"  进度 {i+1}/{len(codes)} — 更新:{updated} 跳过:{skipped} 失败:{failed}")

    if not dry_run:
        conn.commit()
    logger.info(f"基础信息同步完成 — 更新:{updated} 跳过:{skipped} 失败:{failed}")
    return updated


def sync_industry(conn, codes, dry_run=False):
    """同步 sector_lv1, sector_lv2"""
    logger.info(f"=== 同步行业分类（共 {len(codes)} 只）===")
    updated = skipped = failed = 0

    for i, code in enumerate(codes):
        bs_code = to_bs_code(code)
        try:
            rs = bs.query_stock_industry(code=bs_code)
            if rs.error_code != '0' or not rs.next():
                skipped += 1
                continue

            row = rs.get_row_data()
            # fields: updateDate, code, code_name, industry, industryClassification
            industry_raw = row[3]  # e.g. 'J66货币金融服务'
            classification = row[4]  # '证监会行业分类'

            # 拆分：'J66货币金融服务' → lv1='J66', lv2='货币金融服务'
            import re
            m = re.match(r'^([A-Z]\d+)(.*)', industry_raw)
            if m:
                sector_lv1 = m.group(1)          # 'J66'
                sector_lv2 = m.group(2).strip()  # '货币金融服务'
            else:
                sector_lv1 = industry_raw
                sector_lv2 = ''

            if not dry_run:
                conn.execute("""
                    UPDATE stocks SET
                        sector_lv1 = COALESCE(NULLIF(?, ''), sector_lv1),
                        sector_lv2 = COALESCE(NULLIF(?, ''), sector_lv2),
                        updated_at = ?
                    WHERE code = ?
                """, (sector_lv1, sector_lv2, datetime.now().isoformat(), code))

            updated += 1

        except Exception as e:
            logger.warning(f"{code}: {e}")
            failed += 1

        if (i + 1) % 500 == 0:
            if not dry_run:
                conn.commit()
            logger.info(f"  进度 {i+1}/{len(codes)} — 更新:{updated} 跳过:{skipped} 失败:{failed}")

    if not dry_run:
        conn.commit()
    logger.info(f"行业分类同步完成 — 更新:{updated} 跳过:{skipped} 失败:{failed}")
    return updated


def add_asset_type_column(conn):
    """如果 asset_type 列不存在则添加"""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(stocks)").fetchall()]
    if 'asset_type' not in cols:
        conn.execute("ALTER TABLE stocks ADD COLUMN asset_type VARCHAR(10) DEFAULT 'stock'")
        conn.commit()
        logger.info("已添加 asset_type 列")


def main():
    parser = argparse.ArgumentParser(description='从 BaoStock 同步股票基础信息')
    parser.add_argument('--dry-run', action='store_true', help='只读不写')
    parser.add_argument('--basic-only', action='store_true', help='只同步基础信息，跳过行业')
    parser.add_argument('--industry-only', action='store_true', help='只同步行业，跳过基础信息')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"sync_stock_basic_baostock 启动 {'[DRY-RUN]' if args.dry_run else ''}")
    logger.info("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    add_asset_type_column(conn)
    codes = get_all_codes_from_db(conn)
    logger.info(f"数据库共 {len(codes)} 只股票/指数")

    ret = bs.login()
    if ret.error_code != '0':
        logger.error(f"BaoStock 登录失败: {ret.error_msg}")
        sys.exit(1)

    try:
        if not args.industry_only:
            sync_basic(conn, codes, dry_run=args.dry_run)
        if not args.basic_only:
            sync_industry(conn, codes, dry_run=args.dry_run)
    finally:
        bs.logout()
        conn.close()

    logger.info("全部完成")


if __name__ == '__main__':
    main()
