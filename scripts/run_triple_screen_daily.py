#!/usr/bin/env python3
"""
Run daily triple-screen screening.
Default mode is dry-run (no DB writes).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import config  # noqa: E402
from scripts.run_triple_screen_backfill import (  # noqa: E402
    build_signal_biz_key,
    parse_stock_codes,
    upsert_rows,
)
from scripts.strategies.triple_screen_strategy import (  # noqa: E402
    build_param_snapshot,
    compute_triple_screen_signals,
    load_daily_prices_for_stock,
    load_triple_screen_config,
    normalize_trade_date,
)


def fetch_active_pool(conn: sqlite3.Connection, stock_codes: Optional[List[str]]) -> List[dict]:
    sql = """
        SELECT id, stock_code, stock_name
        FROM triple_screen_pool
        WHERE is_active = 1
    """
    params: List[str] = []
    if stock_codes:
        placeholders = ",".join("?" for _ in stock_codes)
        sql += f" AND stock_code IN ({placeholders})"
        params.extend(stock_codes)
    sql += " ORDER BY stock_code ASC"
    rows = conn.execute(sql, params).fetchall()
    return [{"pool_id": int(r[0]), "stock_code": str(r[1]), "stock_name": str(r[2])} for r in rows]


def resolve_target_trade_date(conn: sqlite3.Connection, stock_codes: Optional[List[str]], as_of_date: Optional[str]) -> Optional[str]:
    sql = """
        SELECT MAX(dp.trade_date)
        FROM daily_prices dp
        JOIN triple_screen_pool p ON p.stock_code = dp.code
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
    val = conn.execute(sql, params).fetchone()[0]
    return str(val) if val else None


def run_daily(execute: bool, as_of_date: Optional[str], stock_codes: Optional[List[str]]) -> dict:
    cfg = load_triple_screen_config()
    param_snapshot = build_param_snapshot(cfg)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        pools = fetch_active_pool(conn, stock_codes)
        target_trade_date = resolve_target_trade_date(conn, stock_codes, as_of_date)
        report = {
            "timestamp": datetime.now().isoformat(),
            "execute": bool(execute),
            "as_of_date": as_of_date,
            "target_trade_date": target_trade_date,
            "param_version": cfg.param_version,
            "timing_rsi_threshold": cfg.timing_rsi_threshold,
            "entry_lookback_days": cfg.entry_lookback_days,
            "stop_lookback_days": cfg.stop_lookback_days,
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

        payloads: List[tuple] = []
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
            out = compute_triple_screen_signals(df, cfg)
            target = out.loc[out["trade_date"].dt.strftime("%Y-%m-%d") == target_trade_date]
            if target.empty:
                report["stocks_without_target_date"] += 1
                continue
            r = target.iloc[-1]
            if not bool(r["is_new_entry"]):
                continue

            trade_date = normalize_trade_date(r.get("trade_date")) or target_trade_date
            payload = (
                int(p["pool_id"]),
                p["stock_code"],
                p["stock_name"],
                trade_date,
                "daily",
                int(bool(r["trend_ok"])),
                int(bool(r["timing_ok"])),
                int(bool(r["entry_ok"])),
                1,
                int(bool(r["is_exit_ref"])),
                int(cfg.entry_lookback_days),
                int(cfg.stop_lookback_days),
                float(cfg.timing_rsi_threshold),
                float(r["entry_level"]) if r.get("entry_level") is not None else None,
                float(r["exit_level"]) if r.get("exit_level") is not None else None,
                float(r["close"]) if r.get("close") is not None else None,
                float(r["rsi14"]) if r.get("rsi14") is not None else None,
                float(r["weekly_macd_hist"]) if r.get("weekly_macd_hist") is not None else None,
                float(r["weekly_macd"]) if r.get("weekly_macd") is not None else None,
                float(r["weekly_signal"]) if r.get("weekly_signal") is not None else None,
                cfg.param_version,
                param_snapshot,
                build_signal_biz_key(p["stock_code"], trade_date, "daily", cfg.param_version, cfg),
            )
            payloads.append(payload)
            report["candidates"].append(
                {
                    "stock_code": p["stock_code"],
                    "stock_name": p["stock_name"],
                    "trade_date": trade_date,
                    "close_price": float(r["close"]) if r.get("close") is not None else None,
                    "entry_price": float(r["entry_level"]) if r.get("entry_level") is not None else None,
                    "rsi14": float(r["rsi14"]) if r.get("rsi14") is not None else None,
                }
            )

        report["new_entry_count"] = len(payloads)
        if execute and payloads:
            report["db_upserts"] = upsert_rows(conn, payloads)
            conn.commit()
        return report
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily triple-screen screening")
    parser.add_argument("--execute", action="store_true", help="Actually write to DB. Default dry-run")
    parser.add_argument("--as-of-date", default="", help="Optional cutoff date (YYYY-MM-DD)")
    parser.add_argument("--stock-codes", default="", help="Optional stock codes, comma-separated")
    parser.add_argument("--report", default="", help="Optional report JSON output path")
    args = parser.parse_args()

    report = run_daily(
        execute=bool(args.execute),
        as_of_date=(str(args.as_of_date).strip() or None),
        stock_codes=parse_stock_codes(args.stock_codes),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else ROOT / "logs" / f"triple_screen_daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
