#!/usr/bin/env python3
"""
Download today's stock data from iFind Realtime
Saves to SQLite database
"""
import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add scripts dir to path (for config)
sys.path.insert(0, str(Path(__file__).parent))
# Add dashboard to path (for ifind_client / ifind_realtime)
sys.path.insert(0, str(Path(__file__).parent.parent / 'dashboard'))

from config import DB_PATH
from ifind_realtime import RealtimeFeed
from ifind_client import IfindClient


def get_all_stock_codes(db_path=None):
    """Get all active stock codes from database"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT code FROM stock_meta
        WHERE asset_type = 'stock' AND is_delisted = 0
        ORDER BY code
    """)

    codes = []
    for row in cursor.fetchall():
        code = row[0]
        if code.startswith('6') or code.startswith('5') or code.startswith('11'):
            codes.append(f"{code}.SH")
        elif code.startswith('8') or code.startswith('43'):
            codes.append(f"{code}.BJ")
        else:
            codes.append(f"{code}.SZ")

    conn.close()
    return codes


def download_today_data():
    """Download today's data for all stocks"""
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Downloading data for {today}")

    print("📋 Loading stock codes...")
    codes = get_all_stock_codes()
    print(f"🎯 Total stocks: {len(codes)}")

    print("🔌 Connecting to iFind...")
    client = IfindClient()
    feed = RealtimeFeed(client)

    print("⬇️ Downloading realtime data...")
    try:
        df = feed.fetch(codes, indicators=feed.FULL_INDICATORS)
        print(f"✅ Downloaded {len(df)} stocks")
        print(f"📊 Columns: {list(df.columns)}")
        print(df.head())
        return df, today
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise


def sync_fundamentals():
    """同步股票基本面数据（总市值、流通市值等）"""
    print("\n📊 同步股票基本面数据...")
    try:
        from sync_ifind_fundamentals import get_all_stock_codes as _get_codes, \
            fetch_fundamental_data, update_stocks_fundamentals
        codes = _get_codes()
        client = IfindClient()
        data = fetch_fundamental_data(codes, client)
        update_stocks_fundamentals(data)
        print("✅ 基本面数据同步完成")
    except Exception as e:
        print(f"⚠️ 基本面同步失败: {e}")


def save_to_database(df, trade_date, db_path=None):
    """Save data to SQLite database"""
    if db_path is None:
        db_path = DB_PATH
    print(f"💾 Saving to database: {db_path}")

    conn = sqlite3.connect(db_path)
    records = []
    for _, row in df.iterrows():
        thscode = row.get('thscode', '') or row.get('code', '')
        code = str(thscode).split('.')[0]
        if not code or code == 'nan':
            continue
        records.append({
            'code': code,
            'trade_date': trade_date,
            'open': row.get('open', 0),
            'close': row.get('latest', 0),
            'high': row.get('high', 0),
            'low': row.get('low', 0),
            'preclose': row.get('preClose', 0),
            'volume': row.get('volume', 0),
            'amount': row.get('amount', 0),
            'turnover': row.get('turnoverRatio', 0),
            'pct_change': row.get('changeRatio', 0),
        })

    cursor = conn.cursor()
    inserted = 0
    for record in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_prices
                (code, trade_date, open, close, high, low, preclose, volume, amount, turnover, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record['code'], record['trade_date'], record['open'],
                record['close'], record['high'], record['low'],
                record['preclose'], record['volume'], record['amount'],
                record['turnover'], record['pct_change'],
            ))
            inserted += 1
        except Exception as e:
            print(f"⚠️ Error inserting {record['code']}: {e}")

    conn.commit()
    conn.close()
    print(f"✅ Inserted/Updated {inserted} records")
    return inserted


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Download iFind stock data')
    parser.add_argument('--fundamentals', action='store_true',
                        help='Also sync fundamental data (market cap, etc.)')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check iFind connection')
    args = parser.parse_args()

    if args.check_only:
        client = IfindClient()
        if client.access_token:
            print("✅ iFind connection OK")
            sys.exit(0)
        else:
            print("❌ iFind connection failed")
            sys.exit(1)

    try:
        df, today = download_today_data()
        if len(df) > 0:
            inserted = save_to_database(df, today)
            print(f"\n🎉 Success! Downloaded {inserted} stocks for {today}")
            if args.fundamentals:
                sync_fundamentals()
        else:
            print("❌ No data downloaded")
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
