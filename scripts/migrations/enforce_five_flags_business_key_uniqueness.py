#!/usr/bin/env python3
"""
Enforce business-key uniqueness for lao_ya_tou_five_flags.

Business key:
  (stock_code, screen_date, screener_id)
"""

import sqlite3
from pathlib import Path


def migrate(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path), timeout=30)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM lao_ya_tou_five_flags
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM lao_ya_tou_five_flags
                GROUP BY stock_code, screen_date, screener_id
            )
            """
        )
        removed = cur.rowcount if cur.rowcount is not None else 0

        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_five_flags_stock_date_screener
            ON lao_ya_tou_five_flags(stock_code, screen_date, screener_id)
            """
        )

        conn.commit()

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT stock_code, screen_date, screener_id, COUNT(*) AS cnt
                FROM lao_ya_tou_five_flags
                GROUP BY stock_code, screen_date, screener_id
                HAVING cnt > 1
            )
            """
        )
        dup_groups = int(cur.fetchone()[0])

        print(f"[OK] removed_duplicates={removed}")
        print("[OK] unique_index=ux_five_flags_stock_date_screener")
        print(f"[OK] duplicate_groups_after_migration={dup_groups}")
    finally:
        conn.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    database = root / "data" / "stock_data.db"
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")
    migrate(database)
