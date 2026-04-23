#!/usr/bin/env python3
"""
Check stock_meta freshness and coverage against latest daily_prices date.

Usage:
  python3 scripts/check_stock_meta_freshness.py
  python3 scripts/check_stock_meta_freshness.py --min-update-ratio 0.90 --min-sector-ratio 0.95
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stock_meta freshness/coverage")
    parser.add_argument("--db", default="data/stock_data.db", help="Path to stock_data.db")
    parser.add_argument("--min-update-ratio", type=float, default=0.90, help="Minimum ratio of rows updated on/after latest trade date")
    parser.add_argument("--min-sector-ratio", type=float, default=0.95, help="Minimum ratio of active stocks with sector_lv1")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parent.parent / db_path
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.execute("SELECT MAX(trade_date) FROM daily_prices")
        latest_trade_date = cur.fetchone()[0]
        if not latest_trade_date:
            print("[ERROR] daily_prices has no trade_date")
            return 2

        cur.execute("SELECT COUNT(*) FROM stock_meta WHERE asset_type='stock' AND is_delisted=0")
        active_stock_meta = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM stock_meta
            WHERE asset_type='stock' AND is_delisted=0
              AND updated_at IS NOT NULL
              AND date(substr(updated_at, 1, 19)) >= date(?)
            """,
            (latest_trade_date,),
        )
        updated_on_or_after_latest_trade_date = int(cur.fetchone()[0] or 0)

        # Keep strict-equality metric for observability/debugging.
        cur.execute(
            """
            SELECT COUNT(*)
            FROM stock_meta
            WHERE asset_type='stock' AND is_delisted=0
              AND updated_at IS NOT NULL
              AND substr(updated_at, 1, 10) = ?
            """,
            (latest_trade_date,),
        )
        updated_on_latest_trade_date = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM stock_meta
            WHERE asset_type='stock' AND is_delisted=0
              AND NULLIF(TRIM(sector_lv1), '') IS NOT NULL
            """
        )
        sector_covered = int(cur.fetchone()[0] or 0)
    finally:
        conn.close()

    update_ratio = (updated_on_or_after_latest_trade_date / active_stock_meta) if active_stock_meta > 0 else 0.0
    sector_ratio = (sector_covered / active_stock_meta) if active_stock_meta > 0 else 0.0

    print(
        {
            "latest_trade_date": latest_trade_date,
            "active_stock_meta": active_stock_meta,
            "updated_on_or_after_latest_trade_date": updated_on_or_after_latest_trade_date,
            "updated_on_latest_trade_date": updated_on_latest_trade_date,
            "update_ratio": round(update_ratio, 4),
            "sector_covered": sector_covered,
            "sector_ratio": round(sector_ratio, 4),
            "min_update_ratio": args.min_update_ratio,
            "min_sector_ratio": args.min_sector_ratio,
        }
    )

    ok = True
    if update_ratio < args.min_update_ratio:
        print("[FAIL] stock_meta update ratio is below threshold")
        ok = False
    if sector_ratio < args.min_sector_ratio:
        print("[FAIL] stock_meta sector coverage ratio is below threshold")
        ok = False
    if ok:
        print("[OK] stock_meta freshness and coverage checks passed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
