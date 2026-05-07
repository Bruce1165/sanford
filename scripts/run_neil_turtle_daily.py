#!/usr/bin/env python3
"""
Run daily Neil turtle short screening.

Goal:
- Only output stocks that are "new entry" on target trade date.
- Default dry-run (no DB write). Use --execute to upsert records.
"""

from __future__ import annotations

import argparse
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
from scripts.run_neil_turtle_backfill import (  # noqa: E402
    build_param_snapshot,
    build_signal_biz_key,
    parse_stock_codes,
)
from scripts.strategies.turtle_short_strategy import (  # noqa: E402
    TurtleShortConfig,
    compute_turtle_short_signals,
    load_daily_prices_for_stock,
    load_turtle_short_config,
)


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


def resolve_target_trade_date(conn: sqlite3.Connection, stock_codes: Optional[List[str]], as_of_date: Optional[str]) -> Optional[str]:
    sql = """
        SELECT MAX(dp.trade_date)
        FROM daily_prices dp
        JOIN neil_stock_pool p ON p.stock_code = dp.code
        WHERE p.is_active = 1
    """
    params: List[str] = []
    if stock_codes:
        placeholders = ",".join("?" for _ in stock_codes)
        sql += f" AND dp.code IN ({placeholders})"
        params.extend(stock_codes)
    if as_of_date:
        sql += " AND dp.trade_date <= ?"
        params.append(as_of_date)
    value = conn.execute(sql, params).fetchone()[0]
    return str(value) if value else None


def build_daily_row(
    pool_id: int,
    stock_code: str,
    stock_name: str,
    target_trade_date: str,
    cfg: TurtleShortConfig,
    param_snapshot: str,
    signal: dict,
) -> tuple:
    signal_biz_key = build_signal_biz_key(
        stock_code=stock_code,
        trade_date=target_trade_date,
        task_type="daily",
        param_version=cfg.param_version,
        entry_n=cfg.entry_n,
        exit_n=cfg.exit_n,
    )
    return (
        int(pool_id),
        stock_code,
        stock_name,
        target_trade_date,
        "daily",
        int(bool(signal["is_entry"])),
        int(bool(signal["is_exit"])),
        1,  # daily task only stores new entries
        int(cfg.entry_n),
        int(cfg.exit_n),
        signal.get("entry_level"),
        signal.get("exit_level"),
        signal.get("close"),
        cfg.param_version,
        param_snapshot,
        signal_biz_key,
    )


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


def run_daily(execute: bool, as_of_date: Optional[str], stock_codes: Optional[List[str]]) -> dict:
    cfg = load_turtle_short_config()
    param_snapshot = build_param_snapshot(cfg.entry_n, cfg.exit_n, cfg.new_entry_rule)

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        pools = fetch_active_neil_pool(conn, stock_codes)
        target_trade_date = resolve_target_trade_date(conn, stock_codes, as_of_date)
        report = {
            "timestamp": datetime.now().isoformat(),
            "execute": bool(execute),
            "as_of_date": as_of_date,
            "target_trade_date": target_trade_date,
            "param_version": cfg.param_version,
            "entry_n": cfg.entry_n,
            "exit_n": cfg.exit_n,
            "pool_size": len(pools),
            "processed_stocks": 0,
            "stocks_without_price_data": 0,
            "stocks_without_target_date": 0,
            "new_entry_count": 0,
            "db_upserts": 0,
            "candidates": [],
        }
        if not target_trade_date:
            return report

        upsert_payloads: List[tuple] = []
        for p in pools:
            df = load_daily_prices_for_stock(
                db_path=str(config.DB_PATH),
                stock_code=p["stock_code"],
                end_date=target_trade_date,
            )
            report["processed_stocks"] += 1
            if df.empty:
                report["stocks_without_price_data"] += 1
                continue
            out = compute_turtle_short_signals(df, cfg)
            target = out.loc[out["trade_date"].dt.strftime("%Y-%m-%d") == target_trade_date]
            if target.empty:
                report["stocks_without_target_date"] += 1
                continue

            row = target.iloc[-1]
            is_new_entry = bool(row["is_new_entry"])
            if not is_new_entry:
                continue

            signal = {
                "is_entry": bool(row["is_entry"]),
                "is_exit": bool(row["is_exit"]),
                "entry_level": float(row["entry_level"]) if row.get("entry_level") is not None else None,
                "exit_level": float(row["exit_level"]) if row.get("exit_level") is not None else None,
                "close": float(row["close"]) if row.get("close") is not None else None,
            }
            payload = build_daily_row(
                pool_id=p["pool_id"],
                stock_code=p["stock_code"],
                stock_name=p["stock_name"],
                target_trade_date=target_trade_date,
                cfg=cfg,
                param_snapshot=param_snapshot,
                signal=signal,
            )
            upsert_payloads.append(payload)
            report["candidates"].append(
                {
                    "stock_code": p["stock_code"],
                    "stock_name": p["stock_name"],
                    "trade_date": target_trade_date,
                    "close_price": signal["close"],
                    "entry_price": signal["entry_level"],
                }
            )

        report["new_entry_count"] = len(upsert_payloads)
        if execute and upsert_payloads:
            report["db_upserts"] = upsert_rows(conn, upsert_payloads)
            conn.commit()
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Neil turtle short screening")
    parser.add_argument("--execute", action="store_true", help="Actually write to DB. Default dry-run")
    parser.add_argument("--as-of-date", default="", help="Optional cutoff date (YYYY-MM-DD)")
    parser.add_argument("--stock-codes", default="", help="Optional stock codes, comma-separated")
    parser.add_argument("--report", default="", help="Optional report JSON output path")
    args = parser.parse_args()

    stock_codes = parse_stock_codes(args.stock_codes)
    as_of_date = str(args.as_of_date).strip() or None
    report = run_daily(
        execute=bool(args.execute),
        as_of_date=as_of_date,
        stock_codes=stock_codes,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else ROOT / "logs" / f"neil_daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
