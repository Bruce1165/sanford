#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import config  # noqa: E402
from scripts.strategies.triple_screen_strategy import (  # noqa: E402
    compute_triple_screen_signals,
    load_daily_prices_for_stock,
    load_triple_screen_config,
)


def main() -> int:
    start_date = "2026-03-24"
    end_date = "2026-04-30"

    conn = sqlite3.connect(str(config.DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT stock_code, stock_name FROM triple_screen_pool WHERE is_active=1 ORDER BY stock_code")
    pool = cur.fetchall()
    conn.close()

    cfg = load_triple_screen_config()

    counts = {
        "processed": 0,
        "no_data": 0,
        "rows_in_range": 0,
        "trend_ok_rows": 0,
        "timing_ok_rows": 0,
        "entry_ok_rows": 0,
        "trend_timing_ok_rows": 0,
        "triple_all_ok_rows": 0,
        "distinct_stocks_triple": set(),
        "distinct_stocks_entry": set(),
        "distinct_stocks_trend_timing": set(),
    }

    near_buckets = {1: [], 2: [], 3: [], 5: []}

    for code, name in pool:
        counts["processed"] += 1
        df = load_daily_prices_for_stock(str(config.DB_PATH), code, end_date=end_date)
        if df.empty:
            counts["no_data"] += 1
            continue
        out = compute_triple_screen_signals(df, cfg)
        rg = out[
            (out["trade_date"].dt.strftime("%Y-%m-%d") >= start_date)
            & (out["trade_date"].dt.strftime("%Y-%m-%d") <= end_date)
        ]
        if rg.empty:
            continue

        for _, r in rg.iterrows():
            counts["rows_in_range"] += 1
            trend = bool(r["trend_ok"])
            timing = bool(r["timing_ok"])
            entry = bool(r["entry_ok"])
            triple = bool(r["is_entry"])

            if trend:
                counts["trend_ok_rows"] += 1
            if timing:
                counts["timing_ok_rows"] += 1
            if entry:
                counts["entry_ok_rows"] += 1
                counts["distinct_stocks_entry"].add(code)
            if trend and timing:
                counts["trend_timing_ok_rows"] += 1
                counts["distinct_stocks_trend_timing"].add(code)
            if triple:
                counts["triple_all_ok_rows"] += 1
                counts["distinct_stocks_triple"].add(code)

            entry_level = r.get("entry_level")
            close = r.get("close")
            if trend and timing and (not entry) and entry_level is not None and close is not None:
                try:
                    entry_level = float(entry_level)
                    close = float(close)
                except Exception:
                    continue
                if entry_level <= 0:
                    continue
                gap_pct = (entry_level - close) / entry_level * 100.0
                for b in [1, 2, 3, 5]:
                    if 0 <= gap_pct <= b:
                        near_buckets[b].append(
                            (code, name, r["trade_date"].strftime("%Y-%m-%d"), close, entry_level, gap_pct)
                        )

    for key in ["distinct_stocks_triple", "distinct_stocks_entry", "distinct_stocks_trend_timing"]:
        counts[key] = len(counts[key])

    print("COUNTS")
    for k, v in counts.items():
        print(k, v)

    for b in [1, 2, 3, 5]:
        arr = near_buckets[b]
        print(f"NEAR_{b}pct_rows {len(arr)} distinct_stocks {len(set(x[0] for x in arr))}")

    arr = sorted(near_buckets[3], key=lambda x: (x[2], x[0]), reverse=True)
    print("SAMPLE_NEAR_3pct_latest_80")
    for x in arr[:80]:
        print(x)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
