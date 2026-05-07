#!/usr/bin/env python3
"""
Run historical backfill for Neil pool using turtle short strategy.

Default mode is dry-run (no DB writes).

Usage:
  python3 scripts/run_neil_turtle_backfill.py
  python3 scripts/run_neil_turtle_backfill.py --execute
  python3 scripts/run_neil_turtle_backfill.py --execute --as-of-date 2026-05-01
  python3 scripts/run_neil_turtle_backfill.py --stock-codes 000034,000062
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import config  # noqa: E402
from scripts.strategies.turtle_short_strategy import (  # noqa: E402
    TurtleShortConfig,
    compute_turtle_short_signals,
    load_daily_prices_for_stock,
    load_turtle_short_config,
)


def parse_stock_codes(raw: str) -> Optional[List[str]]:
    if not raw:
        return None
    items: List[str] = []
    for token in str(raw).split(","):
        code = token.strip()
        if not code:
            continue
        if code.endswith(".0"):
            code = code[:-2]
        code = code.zfill(6)
        if code.isdigit() and len(code) == 6:
            items.append(code)
    return sorted(set(items)) if items else None


def fetch_active_neil_pool(conn: sqlite3.Connection, stock_codes: Optional[List[str]]) -> List[dict]:
    sql = """
        SELECT id, stock_code, stock_name
        FROM neil_stock_pool
        WHERE is_active = 1
    """
    params: List[str] = []
    if stock_codes:
        placeholders = ",".join("?" for _ in stock_codes)
        sql += f" AND stock_code IN ({placeholders})"
        params.extend(stock_codes)
    sql += " ORDER BY stock_code ASC"

    rows = conn.execute(sql, params).fetchall()
    return [
        {"pool_id": int(r[0]), "stock_code": str(r[1]), "stock_name": str(r[2])}
        for r in rows
    ]


def build_signal_biz_key(
    stock_code: str,
    trade_date: str,
    task_type: str,
    param_version: str,
    entry_n: int,
    exit_n: int,
) -> str:
    raw = f"{stock_code}|{trade_date}|{task_type}|{param_version}|{entry_n}|{exit_n}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def build_param_snapshot(entry_n: int, exit_n: int, rule: str) -> str:
    payload = {
        "ENTRY_N": int(entry_n),
        "EXIT_N": int(exit_n),
        "NEW_ENTRY_RULE": str(rule),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def build_rows_for_stock(
    db_path: str,
    pool_id: int,
    stock_code: str,
    stock_name: str,
    as_of_date: Optional[str],
    cfg: TurtleShortConfig,
    param_snapshot: str,
) -> List[tuple]:
    df = load_daily_prices_for_stock(db_path=db_path, stock_code=stock_code, end_date=as_of_date)
    if df.empty:
        return []

    out = compute_turtle_short_signals(df, cfg)
    # Backfill keeps historical entry signals (including repeated entries).
    out = out[out["is_entry"] == True]  # noqa: E712
    if out.empty:
        return []

    rows: List[tuple] = []
    for _, r in out.iterrows():
        trade_date = r["trade_date"].strftime("%Y-%m-%d")
        signal_biz_key = build_signal_biz_key(
            stock_code=stock_code,
            trade_date=trade_date,
            task_type="backfill",
            param_version=cfg.param_version,
            entry_n=cfg.entry_n,
            exit_n=cfg.exit_n,
        )
        rows.append(
            (
                int(pool_id),
                stock_code,
                stock_name,
                trade_date,
                "backfill",
                1,  # is_entry
                0,  # is_exit
                int(bool(r["is_new_entry"])),
                int(cfg.entry_n),
                int(cfg.exit_n),
                float(r["entry_level"]) if r.get("entry_level") is not None else None,
                float(r["exit_level"]) if r.get("exit_level") is not None else None,
                float(r["close"]) if r.get("close") is not None else None,
                cfg.param_version,
                param_snapshot,
                signal_biz_key,
            )
        )
    return rows


def upsert_rows(conn: sqlite3.Connection, rows: Iterable[tuple]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO neil_turtle_signals (
            pool_id, stock_code, stock_name, trade_date, task_type,
            is_entry, is_exit, is_new_entry,
            entry_n, exit_n, entry_price, exit_price, close_price,
            param_version, param_snapshot, signal_biz_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(signal_biz_key) DO UPDATE SET
            pool_id = excluded.pool_id,
            stock_name = excluded.stock_name,
            is_entry = excluded.is_entry,
            is_exit = excluded.is_exit,
            is_new_entry = excluded.is_new_entry,
            entry_n = excluded.entry_n,
            exit_n = excluded.exit_n,
            entry_price = excluded.entry_price,
            exit_price = excluded.exit_price,
            close_price = excluded.close_price,
            param_version = excluded.param_version,
            param_snapshot = excluded.param_snapshot,
            created_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    return len(rows)


def run_backfill(execute: bool, as_of_date: Optional[str], stock_codes: Optional[List[str]]) -> dict:
    cfg = load_turtle_short_config()
    entry_n = int(cfg.entry_n)
    exit_n = int(cfg.exit_n)
    param_version = str(cfg.param_version)
    param_snapshot = build_param_snapshot(entry_n, exit_n, cfg.new_entry_rule)

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        pools = fetch_active_neil_pool(conn, stock_codes)
        report = {
            "timestamp": datetime.now().isoformat(),
            "execute": bool(execute),
            "as_of_date": as_of_date,
            "param_version": param_version,
            "entry_n": entry_n,
            "exit_n": exit_n,
            "pool_size": len(pools),
            "processed_stocks": 0,
            "total_entry_signals": 0,
            "db_upserts": 0,
            "sample": [],
        }

        all_rows: List[tuple] = []
        for p in pools:
            rows = build_rows_for_stock(
                db_path=str(config.DB_PATH),
                pool_id=p["pool_id"],
                stock_code=p["stock_code"],
                stock_name=p["stock_name"],
                as_of_date=as_of_date,
                cfg=cfg,
                param_snapshot=param_snapshot,
            )
            report["processed_stocks"] += 1
            report["total_entry_signals"] += len(rows)
            if rows and len(report["sample"]) < 20:
                report["sample"].append(
                    {
                        "stock_code": p["stock_code"],
                        "stock_name": p["stock_name"],
                        "entry_signals": len(rows),
                        "first_date": rows[0][3],
                        "last_date": rows[-1][3],
                    }
                )
            all_rows.extend(rows)

        if execute and all_rows:
            report["db_upserts"] = upsert_rows(conn, all_rows)
            conn.commit()

        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Neil turtle short historical entry signals")
    parser.add_argument("--execute", action="store_true", help="Actually write to DB. Default dry-run")
    parser.add_argument("--as-of-date", default="", help="Optional end date (YYYY-MM-DD)")
    parser.add_argument("--stock-codes", default="", help="Optional stock codes, comma-separated")
    parser.add_argument("--report", default="", help="Optional report JSON output path")
    args = parser.parse_args()

    stock_codes = parse_stock_codes(args.stock_codes)
    as_of_date = str(args.as_of_date).strip() or None
    report = run_backfill(
        execute=bool(args.execute),
        as_of_date=as_of_date,
        stock_codes=stock_codes,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else ROOT / "logs" / f"neil_backfill_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
