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
    parser = argparse.ArgumentParser(description="Generate strict vs relaxed triple-screen compare PDF (no DB writes)")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--pdf-path",
        default="/Users/mac/Desktop/triple_screen_range_2026-03-24_to_2026-04-30_relaxed_compare.pdf",
        help="Output PDF path",
    )
    args = parser.parse_args()

    start_date = str(args.start_date).strip()
    end_date = str(args.end_date).strip()
    pdf_path = Path(args.pdf_path).expanduser().resolve()

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT stock_code, stock_name FROM triple_screen_pool WHERE is_active=1 ORDER BY stock_code")
    pool = cur.fetchall()
    conn.close()

    cfg = load_triple_screen_config()
    strict_rows = []
    relaxed_rows = []
    processed = 0
    no_data = 0

    for code, name in pool:
        processed += 1
        df = load_daily_prices_for_stock(str(config.DB_PATH), code, end_date=end_date)
        if df.empty:
            no_data += 1
            continue
        out = compute_triple_screen_signals(df, cfg)
        rg = out[
            (out["trade_date"].dt.strftime("%Y-%m-%d") >= start_date)
            & (out["trade_date"].dt.strftime("%Y-%m-%d") <= end_date)
        ]
        if rg.empty:
            continue

        for _, r in rg.iterrows():
            item = {
                "code": code,
                "name": name,
                "date": r["trade_date"].strftime("%Y-%m-%d"),
                "trend_ok": int(bool(r["trend_ok"])),
                "timing_ok": int(bool(r["timing_ok"])),
                "entry_ok": int(bool(r["entry_ok"])),
                "is_new_entry": int(bool(r["is_new_entry"])),
                "close": r.get("close"),
                "entry": r.get("entry_level"),
                "exit": r.get("exit_level"),
                "rsi": r.get("rsi14"),
            }
            if bool(r["is_entry"]):
                strict_rows.append(item)
            if bool(r["trend_ok"]) and bool(r["entry_ok"]):
                relaxed_rows.append(item)

    strict_rows.sort(key=lambda x: (x["date"], x["code"]))
    relaxed_rows.sort(key=lambda x: (x["date"], x["code"]))

    strict_stocks = len(set(x["code"] for x in strict_rows))
    relaxed_stocks = len(set(x["code"] for x in relaxed_rows))

    md_path = ROOT / ".tmp_triple_screen_relaxed_compare.md"
    html_path = ROOT / ".tmp_triple_screen_relaxed_compare.html"
    css_path = ROOT / ".tmp_report_landscape.css"

    lines = []
    lines.append("# 三重滤网区间核查：严格口径 vs 宽松口径（不入库）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 区间：{start_date} ~ {end_date}")
    lines.append("- 严格口径：trend_ok + timing_ok + entry_ok")
    lines.append("- 宽松口径：trend_ok + entry_ok（不强制 timing_ok）")
    lines.append(f"- 股票池活跃数：{len(pool)}（处理={processed}，无数据={no_data}）")
    lines.append(f"- 严格命中：{len(strict_rows)} 条，{strict_stocks} 只股票")
    lines.append(f"- 宽松命中：{len(relaxed_rows)} 条，{relaxed_stocks} 只股票")
    lines.append("")

    lines.append("## 一、按日期统计")
    strict_by_date = defaultdict(int)
    relaxed_by_date = defaultdict(int)
    for r in strict_rows:
        strict_by_date[r["date"]] += 1
    for r in relaxed_rows:
        relaxed_by_date[r["date"]] += 1
    all_dates = sorted(set(strict_by_date.keys()) | set(relaxed_by_date.keys()))
    lines.append("| 日期 | 严格条数 | 宽松条数 |")
    lines.append("|---|---:|---:|")
    if all_dates:
        for dt in all_dates:
            lines.append(f"| {dt} | {strict_by_date.get(dt, 0)} | {relaxed_by_date.get(dt, 0)} |")
    else:
        lines.append("| - | 0 | 0 |")

    lines.append("")
    lines.append("## 二、严格口径命中明细")
    lines.append("| 序号 | 代码 | 名称 | 日期 | 收盘价 | 入场位 | 失效位 | RSI14 |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|")
    if strict_rows:
        for i, r in enumerate(strict_rows, start=1):
            lines.append(
                f"| {i} | {r['code']} | {r['name']} | {r['date']} | "
                f"{fmt(r['close'])} | {fmt(r['entry'])} | {fmt(r['exit'])} | {fmt(r['rsi'])} |"
            )
    else:
        lines.append("| 1 | - | 无 | - | - | - | - | - |")

    lines.append("## 三、宽松口径命中明细（按日期分段）")
    lines.append("- 说明：`择时OK=0` 表示该条在宽松口径命中，但未满足严格择时条件。")
    if relaxed_rows:
        by_date = defaultdict(list)
        for r in relaxed_rows:
            by_date[r["date"]].append(r)

        for dt in sorted(by_date.keys()):
            rows = sorted(by_date[dt], key=lambda x: (x["code"], x["name"]))
            lines.append("")
            lines.append(f"### {dt}（{len(rows)} 条）")
            for part_idx, part_rows in enumerate(chunked(rows, 30), start=1):
                if len(rows) > 30:
                    lines.append(f"- 分段：{part_idx}/{(len(rows) + 29) // 30}")
                lines.append("| 序号 | 代码 | 名称 | 收盘价 | 入场位 | RSI14 | 择时OK |")
                lines.append("|---:|---|---|---:|---:|---:|---:|")
                for i, r in enumerate(part_rows, start=1 + (part_idx - 1) * 30):
                    lines.append(
                        f"| {i} | {r['code']} | {r['name']} | {fmt(r['close'])} | {fmt(r['entry'])} | {fmt(r['rsi'])} | {r['timing_ok']} |"
                    )
                lines.append("")
    else:
        lines.append("| 代码 | 日期 | 择时OK |")
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
    print(f"[OK] strict_rows={len(strict_rows)}, strict_stocks={strict_stocks}, relaxed_rows={len(relaxed_rows)}, relaxed_stocks={relaxed_stocks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
