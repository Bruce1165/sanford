#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional


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


def calc_rsi(values: list[float], period: int) -> Optional[float]:
    if period <= 0 or len(values) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for idx in range(len(values) - period, len(values)):
        change = float(values[idx]) - float(values[idx - 1])
        if change >= 0:
            gains += change
        else:
            losses += -change
    avg_gain = gains / float(period)
    avg_loss = losses / float(period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def apply_overrides(base_out, entry_lookback_days: int, rsi_period: int, timing_rsi_threshold: float):
    out = base_out.copy()
    out["entry_level"] = (
        out["high"]
        .shift(1)
        .rolling(window=entry_lookback_days, min_periods=entry_lookback_days)
        .max()
    )
    out["entry_ok"] = (out["close"] > out["entry_level"]).fillna(False).astype(bool)

    close_values = [float(v) for v in out["close"].tolist()]
    rsi_values: list[Optional[float]] = []
    for i in range(len(out)):
        rsi_values.append(calc_rsi(close_values[: i + 1], rsi_period))
    out["rsi_custom"] = rsi_values

    out["timing_ok"] = (
        out["trend_ok"].astype(bool)
        & out["rsi_custom"].notna()
        & (out["rsi_custom"].astype(float) < float(timing_rsi_threshold))
    )
    out["timing_ok"] = out["timing_ok"].astype(bool)
    out["is_entry"] = out["trend_ok"].astype(bool) & out["timing_ok"] & out["entry_ok"]
    out["is_new_entry"] = out["is_entry"] & (~out["is_entry"].shift(1, fill_value=False).astype(bool))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate triple-screen date-range PDF report without DB writes")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--timing-rsi-threshold", type=float, default=40.0, help="Timing RSI threshold")
    parser.add_argument("--entry-lookback-days", type=int, default=5, help="Entry breakout lookback days")
    parser.add_argument("--rsi-period", type=int, default=14, help="RSI period used for timing filter")
    parser.add_argument(
        "--pdf-path",
        default="/Users/mac/Desktop/triple_screen_range_2026-03-24_to_2026-04-30.pdf",
        help="Output PDF path",
    )
    args = parser.parse_args()

    start_date = str(args.start_date).strip()
    end_date = str(args.end_date).strip()
    timing_rsi_threshold = float(args.timing_rsi_threshold)
    entry_lookback_days = int(args.entry_lookback_days)
    rsi_period = int(args.rsi_period)
    pdf_path = Path(args.pdf_path).expanduser().resolve()

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT stock_code, stock_name FROM triple_screen_pool WHERE is_active=1 ORDER BY stock_code")
    pool = cur.fetchall()
    conn.close()

    cfg = load_triple_screen_config()
    rows = []
    processed = 0
    without_data = 0

    for code, name in pool:
        processed += 1
        df = load_daily_prices_for_stock(str(config.DB_PATH), code, end_date=end_date)
        if df.empty:
            without_data += 1
            continue
        base_out = compute_triple_screen_signals(df, cfg)
        out = apply_overrides(base_out, entry_lookback_days, rsi_period, timing_rsi_threshold)
        target = out[
            (out["trade_date"].dt.strftime("%Y-%m-%d") >= start_date)
            & (out["trade_date"].dt.strftime("%Y-%m-%d") <= end_date)
            & (out["is_entry"] == True)  # noqa: E712
        ]
        if target.empty:
            continue
        for _, r in target.iterrows():
            rows.append(
                {
                    "stock_code": code,
                    "stock_name": name,
                    "trade_date": r["trade_date"].strftime("%Y-%m-%d"),
                    "trend_ok": int(bool(r["trend_ok"])),
                    "timing_ok": int(bool(r["timing_ok"])),
                    "entry_ok": int(bool(r["entry_ok"])),
                    "is_new_entry": int(bool(r["is_new_entry"])),
                    "close_price": None if r.get("close") is None else float(r["close"]),
                    "entry_price": None if r.get("entry_level") is None else float(r["entry_level"]),
                    "exit_price": None if r.get("exit_level") is None else float(r["exit_level"]),
                    "rsi_custom": None if r.get("rsi_custom") is None else float(r["rsi_custom"]),
                }
            )

    rows.sort(key=lambda x: (x["trade_date"], x["stock_code"]))
    counter = Counter([r["stock_code"] for r in rows])
    name_dict = {code: name for code, name in pool}
    ranked = sorted(counter.items(), key=lambda x: (-x[1], x[0]))

    md_path = ROOT / ".tmp_triple_screen_range_report.md"
    html_path = ROOT / ".tmp_triple_screen_range_report.html"
    css_path = ROOT / ".tmp_report_landscape.css"

    lines = []
    lines.append("# 三重滤网区间重筛报告（不入库）")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 筛选区间：{start_date} ~ {end_date}")
    lines.append("- 运行模式：只读计算，不写入数据库")
    lines.append(f"- 参数：TIMING_RSI_THRESHOLD={timing_rsi_threshold}, ENTRY_LOOKBACK_DAYS={entry_lookback_days}, RSI_PERIOD={rsi_period}")
    lines.append(f"- 其余参数：STOP_LOOKBACK_DAYS={cfg.stop_lookback_days}, NEW_ENTRY_RULE={cfg.new_entry_rule}")
    lines.append(f"- 股票池活跃数：{len(pool)}")
    lines.append(f"- 实际处理股票数：{processed}")
    lines.append(f"- 无价格数据股票数：{without_data}")
    lines.append(f"- 区间命中总条数：{len(rows)}")
    lines.append(f"- 区间命中股票数：{len(counter)}")
    lines.append("")

    lines.append("## 一、命中次数排名")
    lines.append("| 排名 | 代码 | 名称 | 命中次数 |")
    lines.append("|---:|---|---|---:|")
    if ranked:
        for idx, (code, cnt) in enumerate(ranked, start=1):
            lines.append(f"| {idx} | {code} | {name_dict.get(code, '')} | {cnt} |")
    else:
        lines.append("| 1 | - | 区间无命中 | 0 |")

    lines.append("")
    lines.append("## 二、命中明细表（全量）")
    lines.append(f"| 序号 | 代码 | 名称 | 日期 | 趋势OK | 择时OK | 入场OK | 新入场 | 收盘价 | 入场位 | 失效位 | RSI{rsi_period} |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    if rows:
        for idx, r in enumerate(rows, start=1):
            lines.append(
                f"| {idx} | {r['stock_code']} | {r['stock_name']} | {r['trade_date']} | "
                f"{r['trend_ok']} | {r['timing_ok']} | {r['entry_ok']} | {r['is_new_entry']} | "
                f"{fmt(r['close_price'])} | {fmt(r['entry_price'])} | {fmt(r['exit_price'])} | {fmt(r['rsi_custom'])} |"
            )
    else:
        lines.append("| 1 | - | 区间无命中 | - | - | - | - | - | - | - | - | - |")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    subprocess.run(
        ["pandoc", str(md_path), "-s", "--css", str(css_path), "-o", str(html_path)],
        check=True,
    )

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
    print(f"[OK] rows={len(rows)}, hit_stocks={len(counter)}, processed={processed}, no_data={without_data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
