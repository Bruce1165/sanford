#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path("/Users/mac/NeoTrade2")
DB_PATH = ROOT / "data" / "stock_data.db"
DESKTOP = Path("/Users/mac/Desktop")
STYLE_PATH = ROOT / ".tmp_report_landscape.css"

BACKFILL_MD = DESKTOP / "triple_screen_backfill_report.md"
DAILY_MD = DESKTOP / "triple_screen_daily_report.md"
BACKFILL_HTML = DESKTOP / "triple_screen_backfill_report.html"
DAILY_HTML = DESKTOP / "triple_screen_daily_report.html"
BACKFILL_PDF = DESKTOP / "triple_screen_backfill_report.pdf"
DAILY_PDF = DESKTOP / "triple_screen_daily_report.pdf"


def _fmt_price(v: object) -> str:
    if v is None:
        return ""
    return f"{float(v):.2f}"


def build_markdown_files() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    pool_total = cur.execute("SELECT COUNT(*) FROM triple_screen_pool").fetchone()[0]
    pool_active = cur.execute("SELECT COUNT(*) FROM triple_screen_pool WHERE is_active=1").fetchone()[0]
    backfill_total = cur.execute(
        "SELECT COUNT(*) FROM triple_screen_signals WHERE task_type='backfill'"
    ).fetchone()[0]
    backfill_stocks = cur.execute(
        "SELECT COUNT(DISTINCT stock_code) FROM triple_screen_signals WHERE task_type='backfill'"
    ).fetchone()[0]
    min_date, max_date = cur.execute(
        "SELECT MIN(trade_date), MAX(trade_date) FROM triple_screen_signals WHERE task_type='backfill'"
    ).fetchone()
    param_versions = cur.execute(
        "SELECT GROUP_CONCAT(DISTINCT param_version) FROM triple_screen_signals WHERE task_type='backfill'"
    ).fetchone()[0] or ""

    top_counts = cur.execute(
        """
        SELECT stock_code, stock_name, COUNT(*) AS cnt, MIN(trade_date), MAX(trade_date)
        FROM triple_screen_signals
        WHERE task_type='backfill'
        GROUP BY stock_code, stock_name
        ORDER BY cnt DESC, stock_code ASC
        LIMIT 30
        """
    ).fetchall()

    backfill_details = cur.execute(
        """
        SELECT stock_code, stock_name, trade_date, trend_ok, timing_ok, entry_ok,
               is_new_entry, close_price, entry_price, exit_price, rsi14
        FROM triple_screen_signals
        WHERE task_type='backfill'
        ORDER BY trade_date DESC, stock_code ASC
        LIMIT 200
        """
    ).fetchall()

    backfill_lines = [
        "# 三重滤网策略回溯结果报告（表格版）",
        "",
        f"- 生成时间：{now}",
        "- 策略口径：长周期趋势 + 中周期RSI择时 + 短周期突破触发",
        f"- 股票池总数：{pool_total}",
        f"- 股票池活跃数：{pool_active}",
        f"- 回溯命中股票数：{backfill_stocks}",
        f"- 回溯信号总数：{backfill_total}",
        f"- 回溯日期范围：{min_date} ~ {max_date}",
        f"- 参数版本：{param_versions}",
        "",
        "## 一、命中次数 Top30（按股票）",
        "| 排名 | 代码 | 名称 | 命中次数 | 首次命中 | 最近命中 |",
        "|---:|---|---|---:|---|---|",
    ]
    for idx, (code, name, cnt, first_date, last_date) in enumerate(top_counts, start=1):
        backfill_lines.append(f"| {idx} | {code} | {name} | {cnt} | {first_date} | {last_date} |")

    backfill_lines.extend(
        [
            "",
            "## 二、回溯明细表（最近200条）",
            "| 代码 | 名称 | 日期 | 趋势OK | 择时OK | 入场OK | 新入场 | 收盘价 | 入场位 | 失效位 | RSI14 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in backfill_details:
        code, name, date, trend_ok, timing_ok, entry_ok, is_new_entry, close_p, entry_p, exit_p, rsi14 = row
        backfill_lines.append(
            f"| {code} | {name} | {date} | {trend_ok} | {timing_ok} | {entry_ok} | {is_new_entry} | "
            f"{_fmt_price(close_p)} | {_fmt_price(entry_p)} | {_fmt_price(exit_p)} | {_fmt_price(rsi14)} |"
        )

    BACKFILL_MD.write_text("\n".join(backfill_lines), encoding="utf-8")

    target_trade_date = cur.execute(
        "SELECT MAX(trade_date) FROM triple_screen_signals WHERE task_type='daily'"
    ).fetchone()[0]
    daily_total = cur.execute(
        "SELECT COUNT(*) FROM triple_screen_signals WHERE task_type='daily'"
    ).fetchone()[0]
    daily_param_versions = cur.execute(
        "SELECT GROUP_CONCAT(DISTINCT param_version) FROM triple_screen_signals WHERE task_type='daily'"
    ).fetchone()[0] or "v1.0(当日无信号)"
    daily_rows = cur.execute(
        """
        SELECT stock_code, stock_name, trade_date, trend_ok, timing_ok, entry_ok,
               is_new_entry, close_price, entry_price, exit_price, rsi14
        FROM triple_screen_signals
        WHERE task_type='daily'
        ORDER BY stock_code ASC
        """
    ).fetchall()

    daily_lines = [
        "# 三重滤网策略当日结果报告（表格版）",
        "",
        f"- 生成时间：{now}",
        "- 任务类型：daily（仅当日新触发）",
        f"- 目标交易日：{target_trade_date or '无'}",
        f"- 当日新触发数量：{daily_total}",
        f"- 参数版本：{daily_param_versions}",
        "",
        "## 一、当日可入场清单",
        "| 序号 | 代码 | 名称 | 日期 | 趋势OK | 择时OK | 入场OK | 新入场 | 收盘价 | 入场位 | 失效位 | RSI14 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if daily_rows:
        for idx, row in enumerate(daily_rows, start=1):
            code, name, date, trend_ok, timing_ok, entry_ok, is_new_entry, close_p, entry_p, exit_p, rsi14 = row
            daily_lines.append(
                f"| {idx} | {code} | {name} | {date} | {trend_ok} | {timing_ok} | {entry_ok} | {is_new_entry} | "
                f"{_fmt_price(close_p)} | {_fmt_price(entry_p)} | {_fmt_price(exit_p)} | {_fmt_price(rsi14)} |"
            )
    else:
        daily_lines.append("| 1 | - | 当日无新触发 | - | - | - | - | - | - | - | - | - |")

    DAILY_MD.write_text("\n".join(daily_lines), encoding="utf-8")
    conn.close()


def markdown_to_html(md_path: Path, html_path: Path) -> None:
    subprocess.run(
        ["pandoc", str(md_path), "-s", "--css", str(STYLE_PATH), "-o", str(html_path)],
        check=True,
    )


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    node_script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://{html_path.as_posix()}', {{ waitUntil: 'networkidle' }});
  await page.pdf({{
    path: '{pdf_path.as_posix()}',
    format: 'A4',
    printBackground: true,
    margin: {{ top: '18mm', right: '16mm', bottom: '18mm', left: '16mm' }}
  }});
  await browser.close();
}})().catch(err => {{ console.error(err); process.exit(1); }});
"""
    subprocess.run(["node", "-e", node_script], check=True)


def main() -> None:
    build_markdown_files()
    markdown_to_html(BACKFILL_MD, BACKFILL_HTML)
    markdown_to_html(DAILY_MD, DAILY_HTML)
    html_to_pdf(BACKFILL_HTML, BACKFILL_PDF)
    html_to_pdf(DAILY_HTML, DAILY_PDF)
    print(
        json.dumps(
            {
                "backfill_pdf": str(BACKFILL_PDF),
                "daily_pdf": str(DAILY_PDF),
                "backfill_md": str(BACKFILL_MD),
                "daily_md": str(DAILY_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
