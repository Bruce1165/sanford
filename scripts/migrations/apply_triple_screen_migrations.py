#!/usr/bin/env python3
"""
Apply triple-screen migration SQL files with safe default dry-run mode.

Usage:
  python3 scripts/migrations/apply_triple_screen_migrations.py
  python3 scripts/migrations/apply_triple_screen_migrations.py --execute
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import config  # noqa: E402


MIGRATION_FILES = [
    ROOT / "scripts" / "database" / "migrations" / "create_triple_screen_pool.sql",
    ROOT / "scripts" / "database" / "migrations" / "create_triple_screen_signals.sql",
]

SNAPSHOT_PATH = ROOT / "logs" / "triple_screen_migration_snapshot.json"


def fetch_scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    ).fetchone()
    return bool(row)


def build_snapshot(conn: sqlite3.Connection) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "tables": {
            "lao_ya_tou_pool_exists": table_exists(conn, "lao_ya_tou_pool"),
            "lao_ya_tou_five_flags_exists": table_exists(conn, "lao_ya_tou_five_flags"),
            "lao_ya_tou_pool_count": fetch_scalar(conn, "SELECT COUNT(*) FROM lao_ya_tou_pool")
            if table_exists(conn, "lao_ya_tou_pool")
            else None,
            "lao_ya_tou_five_flags_count": fetch_scalar(conn, "SELECT COUNT(*) FROM lao_ya_tou_five_flags")
            if table_exists(conn, "lao_ya_tou_five_flags")
            else None,
            "neil_stock_pool_exists": table_exists(conn, "neil_stock_pool"),
            "neil_turtle_signals_exists": table_exists(conn, "neil_turtle_signals"),
            "triple_screen_pool_exists": table_exists(conn, "triple_screen_pool"),
            "triple_screen_signals_exists": table_exists(conn, "triple_screen_signals"),
        },
        "indexes": {
            "ux_triple_pool_biz_key": index_exists(conn, "ux_triple_pool_biz_key"),
            "idx_triple_pool_code": index_exists(conn, "idx_triple_pool_code"),
            "idx_triple_pool_active": index_exists(conn, "idx_triple_pool_active"),
            "idx_triple_pool_import_batch": index_exists(conn, "idx_triple_pool_import_batch"),
            "ux_triple_sig_biz_key": index_exists(conn, "ux_triple_sig_biz_key"),
            "idx_triple_sig_code_date": index_exists(conn, "idx_triple_sig_code_date"),
            "idx_triple_sig_task_date": index_exists(conn, "idx_triple_sig_task_date"),
            "idx_triple_sig_new_entry_date": index_exists(conn, "idx_triple_sig_new_entry_date"),
            "idx_triple_sig_pool": index_exists(conn, "idx_triple_sig_pool"),
        },
    }


def print_snapshot(title: str, snap: dict) -> None:
    print(f"\n[{title}]")
    print(json.dumps(snap, ensure_ascii=False, indent=2))


def backup_db(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"stock_data_before_triple_screen_migration_{timestamp}.db"
    shutil.copy2(db_path, target)
    return target


def apply_migrations(conn: sqlite3.Connection) -> None:
    for migration_file in MIGRATION_FILES:
        sql = migration_file.read_text(encoding="utf-8")
        conn.executescript(sql)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply triple-screen migrations safely")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute SQL migrations. Default is dry-run only.",
    )
    args = parser.parse_args()

    db_path = Path(config.DB_PATH)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    for f in MIGRATION_FILES:
        if not f.exists():
            raise FileNotFoundError(f"Migration file not found: {f}")

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        before = build_snapshot(conn)
        print_snapshot("PRECHECK", before)

        if not args.execute:
            print("\n[DRY-RUN] No SQL executed.")
            print("[DRY-RUN] To execute, run with --execute.")
            return 0

        backup_path = backup_db(db_path)
        print(f"\n[EXECUTE] Database backup created: {backup_path}")

        apply_migrations(conn)
        conn.commit()
        print("[EXECUTE] Migrations applied successfully.")

        after = build_snapshot(conn)
        print_snapshot("POSTCHECK", after)

        old_pool_before = before["tables"]["lao_ya_tou_pool_count"]
        old_pool_after = after["tables"]["lao_ya_tou_pool_count"]
        old_flags_before = before["tables"]["lao_ya_tou_five_flags_count"]
        old_flags_after = after["tables"]["lao_ya_tou_five_flags_count"]
        if old_pool_before != old_pool_after or old_flags_before != old_flags_after:
            raise RuntimeError(
                "Guardrail failed: lao_ya_tou table row counts changed unexpectedly."
            )

        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(
            json.dumps({"before": before, "after": after}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[EXECUTE] Snapshot saved: {SNAPSHOT_PATH}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
