#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
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


def fmt(v: object) -> str:
    if v is None:
        return ""
    return f"{float(v):.2f}"


def chunked(rows: list[dict], size: int) -> list[list[dict]]:
    if size <= 0:
        return [rows]
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate near-candidate PDF for triple-screen in date range")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--near-threshold",
        type=float,
        default=5.0,
        help="Near-entry threshold in percent, e.g. 5 means <=5%%",
    )
    parser.add_argument(
        "--pdf-path",
        default="/Users/mac/Desktop/triple_screen_range_2026-03-24_to_2026-04-30_near_candidates.pdf",
        help="Output PDF path",
    )
    args = parser.parse_args()

    start_date = str(args.start_date).strip()
    end_date = str(args.end_date).strip()
    near_threshold = float(args.near_threshold)
    pdf_path = Path(args.pdf_path).expanduser().resolve()

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT stock_code, stock_name FROM triple_screen_pool WHERE is_active=1 ORDER BY stock_code")
    pool = cur.fetchall()
    conn.close()

    cfg = load_triple_screen_config()
    strict_rows = []
    near_rows = []

    for code, name in pool:
        df = load_daily_prices_for_stock(str(config.DB_PATH), code, end_date=end_date)
        if df.empty:
            continue
        out = compute_triple_screen_signals(df, cfg)
        rg = out[
            (out["trade_date"].dt.strftime("%Y-%m-%d") >= start_date)
            & (out["trade_date"].dt.strftime("%Y-%m-%d") <= end_date)
        ]
        if rg.empty:
            continue
        for _, r in rg.iterrows():
            trade_date = r["trade_date"].strftime("%Y-%m-%d")
            trend = int(bool(r["trend_ok"]))
            timing = int(bool(r["timing_ok"]))
            entry = int(bool(r["entry_ok"]))
            if bool(r["is_entry"]):
                strict_rows.append(
                    {
                        "code": code,
                        "name": name,
                        "date": trade_date,
                        "close": r.get("close"),
                        "entry": r.get("entry_level"),
                        "exit": r.get("exit_level"),
                        "rsi": r.get("rsi14"),
                    }
                )
                continue
            entry_level = r.get("entry_level")
            close = r.get("close")
            if trend == 1 and timing == 1 and entry == 0 and entry_level is not None and close is not None:
                try:
                    entry_level = float(entry_level)
                    close = float(close)
                except Exception:
                    continue
                if entry_level <= 0:
                    continue
                gap_pct = (entry_level - close) / entry_level * 100.0
                if 0 <= gap_pct <= near_threshold:
                    near_rows.append(
                        {
                            "code": code,
                            "name": name,
                            "date": trade_date,
                            "close": close,
                            "entry": entry_level,
                            "exit": r.get("exit_level"),
                            "rsi": r.get("rsi14"),
                            "gap_pct": gap_pct,
                        }
                    )

    strict_rows.sort(key=lambda x: (x["date"], x["code"]))
    near_rows.sort(key=lambda x: (x["date"], x["gap_pct"], x["code"]))

    md_path = ROOT / ".tmp_triple_screen_near_candidates.md"
    html_path = ROOT / ".tmp_triple_screen_near_candidates.html"
    css_path = ROOT / ".tmp_report_landscape.css"

    lines = []
    lines.append("# 三重滤网区间核查：严格命中与接近突破（不入库）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 区间：{start_date} ~ {end_date}")
    lines.append(f"- 严格命中（趋势+择时+入场全满足）条数：{len(strict_rows)}")
    lines.append(f"- 接近突破（趋势+择时满足，距离入场位<={near_threshold:.2f}%）条数：{len(near_rows)}")
    lines.append("")

    lines.append("## 一、严格命中明细")
    lines.append("| 序号 | 代码 | 日期 | 收盘价 | 入场位 | 失效位 | RSI14 |")
    lines.append("|---:|---|---|---:|---:|---:|---:|")
    if strict_rows:
        for idx, r in enumerate(strict_rows, start=1):
            lines.append(
                f"| {idx} | {r['code']} | {r['date']} | {fmt(r['close'])} | {fmt(r['entry'])} | {fmt(r['exit'])} | {fmt(r['rsi'])} |"
            )
    else:
        lines.append("| 1 | - | - | - | - | - | - |")

    lines.append("")
    lines.append("## 二、接近突破分档统计")
    lines.append("| 分档 | 条数 |")
    lines.append("|---|---:|")
    stat_thresholds = [1, 2, 3, 5]
    if near_threshold > 5:
        stat_thresholds.append(near_threshold)
    for threshold in stat_thresholds:
        subset = [r for r in near_rows if r["gap_pct"] <= threshold]
        lines.append(f"| <= {threshold:.2f}% | {len(subset)} |")

    lines.append("")
    lines.append(f"## 三、接近突破明细（<= {near_threshold:.2f}%，按日期分段）")
    if near_rows:
        by_date = defaultdict(list)
        for r in near_rows:
            by_date[r["date"]].append(r)

        for dt in sorted(by_date.keys()):
            rows = sorted(by_date[dt], key=lambda x: (x["gap_pct"], x["code"]))
            lines.append("")
            lines.append(f"### {dt}（{len(rows)} 条）")
            for part_idx, part_rows in enumerate(chunked(rows, 25), start=1):
                if len(rows) > 25:
                    lines.append(f"- 分段：{part_idx}/{(len(rows) + 24) // 25}")
                lines.append("| 序号 | 代码 | 名称 | 收盘价 | 入场位 | 距离入场(%) | RSI14 |")
                lines.append("|---:|---|---|---:|---:|---:|---:|")
                for idx, r in enumerate(part_rows, start=1 + (part_idx - 1) * 25):
                    lines.append(
                        f"| {idx} | {r['code']} | {r['name']} | {fmt(r['close'])} | {fmt(r['entry'])} | {r['gap_pct']:.2f} | {fmt(r['rsi'])} |"
                    )
                lines.append("")
    else:
        lines.append("| 代码 | 日期 | 距离入场(%) |")
        lines.append("|---|---|---:|")
        lines.append("| 无 | - | - |")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    subprocess.run(["pandoc", str(md_path), "-s", "--css", str(css_path), "-o", str(html_path)], check=True)

    node_script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://{html_path.as_posix()}', {{ waitUntil: 'networkidle' }});
  await page.pdf({{
    path: '{pdf_path.as_posix()}',
    format: 'A4',
    landscape: true,
    printBackground: true,
    margin: {{ top: '14mm', right: '12mm', bottom: '14mm', left: '12mm' }}
  }});
  await browser.close();
}})().catch(err => {{ console.error(err); process.exit(1); }});
"""
    subprocess.run(["node", "-e", node_script], check=True)

    print(f"[OK] PDF generated: {pdf_path}")
    print(f"[OK] strict_rows={len(strict_rows)}, near_rows_le_threshold={len(near_rows)}, threshold={near_threshold:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
