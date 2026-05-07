#!/usr/bin/env python3
"""
Verify Neil migration objects without changing data.

Usage:
  python3 scripts/migrations/verify_neil_migrations.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import config  # noqa: E402


REQUIRED_TABLES = [
    "neil_stock_pool",
    "neil_turtle_signals",
]

REQUIRED_INDEXES = [
    "ux_neil_pool_biz_key",
    "idx_neil_pool_code",
    "idx_neil_pool_active",
    "idx_neil_pool_import_batch",
    "ux_neil_sig_biz_key",
    "idx_neil_sig_code_date",
    "idx_neil_sig_task_date",
    "idx_neil_sig_new_entry_date",
    "idx_neil_sig_pool",
]


def exists(conn: sqlite3.Connection, obj_type: str, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
        (obj_type, name),
    ).fetchone()
    return bool(row)


def collect_report(conn: sqlite3.Connection) -> dict:
    report = {
        "tables": {},
        "indexes": {},
        "row_counts": {},
        "foreign_key_check": [],
    }

    for t in REQUIRED_TABLES:
        report["tables"][t] = exists(conn, "table", t)
        if report["tables"][t]:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            report["row_counts"][t] = int(count)

    for idx in REQUIRED_INDEXES:
        report["indexes"][idx] = exists(conn, "index", idx)

    # SQLite built-in FK consistency check.
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    report["foreign_key_check"] = [tuple(r) for r in fk_rows]
    return report


def main() -> int:
    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        report = collect_report(conn)
        print(json.dumps(report, ensure_ascii=False, indent=2))

        missing_tables = [k for k, ok in report["tables"].items() if not ok]
        missing_indexes = [k for k, ok in report["indexes"].items() if not ok]
        fk_issues = report["foreign_key_check"]

        if missing_tables or missing_indexes or fk_issues:
            if missing_tables:
                print(f"[FAIL] Missing tables: {missing_tables}")
            if missing_indexes:
                print(f"[FAIL] Missing indexes: {missing_indexes}")
            if fk_issues:
                print(f"[FAIL] Foreign key check issues: {fk_issues}")
            return 1

        print("[OK] Neil migration objects verified.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
