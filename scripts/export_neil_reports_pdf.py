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

BACKFILL_MD = DESKTOP / "neil_turtle_backfill_report.md"
DAILY_MD = DESKTOP / "neil_turtle_daily_report.md"
BACKFILL_HTML = DESKTOP / "neil_turtle_backfill_report.html"
DAILY_HTML = DESKTOP / "neil_turtle_daily_report.html"
BACKFILL_PDF = DESKTOP / "neil_turtle_backfill_report.pdf"
DAILY_PDF = DESKTOP / "neil_turtle_daily_report.pdf"


def _fmt_price(v: object) -> str:
    if v is None:
        return ""
    return f"{float(v):.2f}"


def build_markdown_files() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    active_pool = cur.execute(
        "SELECT COUNT(*) FROM neil_stock_pool WHERE is_active=1"
    ).fetchone()[0]
    backfill_total = cur.execute(
        "SELECT COUNT(*) FROM neil_turtle_signals WHERE task_type='backfill'"
    ).fetchone()[0]
    backfill_stocks = cur.execute(
        "SELECT COUNT(DISTINCT stock_code) FROM neil_turtle_signals WHERE task_type='backfill'"
    ).fetchone()[0]
    min_date, max_date = cur.execute(
        "SELECT MIN(trade_date), MAX(trade_date) FROM neil_turtle_signals WHERE task_type='backfill'"
    ).fetchone()
    param_versions = cur.execute(
        "SELECT GROUP_CONCAT(DISTINCT param_version) FROM neil_turtle_signals WHERE task_type='backfill'"
    ).fetchone()[0] or ""

    missing = cur.execute(
        """
        SELECT p.stock_code, p.stock_name
        FROM neil_stock_pool p
        LEFT JOIN (
          SELECT DISTINCT stock_code FROM neil_turtle_signals WHERE task_type='backfill'
        ) s ON s.stock_code = p.stock_code
        WHERE p.is_active = 1 AND s.stock_code IS NULL
        ORDER BY p.stock_code
        """
    ).fetchall()

    top_counts = cur.execute(
        """
        SELECT stock_code, stock_name, COUNT(*) AS cnt,
               MIN(trade_date) AS first_date,
               MAX(trade_date) AS last_date
        FROM neil_turtle_signals
        WHERE task_type='backfill'
        GROUP BY stock_code, stock_name
        ORDER BY cnt DESC, stock_code ASC
        LIMIT 30
        """
    ).fetchall()

    latest_backfill = cur.execute(
        """
        SELECT stock_code, stock_name, trade_date, is_new_entry, close_price, entry_price
        FROM neil_turtle_signals
        WHERE task_type='backfill'
        ORDER BY trade_date DESC, stock_code ASC
        LIMIT 30
        """
    ).fetchall()

    backfill_lines = [
        "# Neil 股票池海龟短期策略回溯结果报告",
        "",
        f"- 生成时间：{now}",
        "- 策略口径：海龟短期 `20/10`（`entry_n=20`，`exit_n=10`）",
        "- 任务类型：`backfill`（全历史回溯）",
        f"- 活跃股票池规模：{active_pool}",
        f"- 回溯命中股票数：{backfill_stocks}",
        f"- 回溯信号总数：{backfill_total}",
        f"- 回溯日期范围：{min_date} ~ {max_date}",
        f"- 参数版本：{param_versions}",
        "",
        "## 一、未产生回溯信号的活跃股票",
    ]
    if missing:
        backfill_lines.extend(["| 代码 | 名称 |", "|---|---|"])
        for code, name in missing:
            backfill_lines.append(f"| {code} | {name} |")
    else:
        backfill_lines.append("- 无")

    backfill_lines.extend(
        [
            "",
            "## 二、回溯命中次数 Top30",
            "| 排名 | 代码 | 名称 | 命中次数 | 首次命中 | 最近命中 |",
            "|---:|---|---|---:|---|---|",
        ]
    )
    for idx, (code, name, cnt, first_date, last_date) in enumerate(top_counts, start=1):
        backfill_lines.append(
            f"| {idx} | {code} | {name} | {cnt} | {first_date} | {last_date} |"
        )

    backfill_lines.extend(
        [
            "",
            "## 三、最近交易日回溯样本（Top30）",
            "| 代码 | 名称 | 日期 | 新入场 | 收盘价 | 入场位(20日高) |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for code, name, date, is_new, close_price, entry_price in latest_backfill:
        backfill_lines.append(
            f"| {code} | {name} | {date} | {is_new} | {_fmt_price(close_price)} | {_fmt_price(entry_price)} |"
        )
    BACKFILL_MD.write_text("\n".join(backfill_lines), encoding="utf-8")

    trade_date = cur.execute(
        "SELECT MAX(trade_date) FROM neil_turtle_signals WHERE task_type='daily'"
    ).fetchone()[0]
    daily_total = cur.execute(
        "SELECT COUNT(*) FROM neil_turtle_signals WHERE task_type='daily'"
    ).fetchone()[0]
    param_versions_daily = cur.execute(
        "SELECT GROUP_CONCAT(DISTINCT param_version) FROM neil_turtle_signals WHERE task_type='daily'"
    ).fetchone()[0] or ""
    daily_rows = cur.execute(
        """
        SELECT stock_code, stock_name, trade_date, close_price, entry_price, exit_price
        FROM neil_turtle_signals
        WHERE task_type='daily'
        ORDER BY stock_code ASC
        """
    ).fetchall()

    daily_lines = [
        "# Neil 股票池海龟短期策略当日结果报告",
        "",
        f"- 生成时间：{now}",
        "- 策略口径：海龟短期 `20/10`（仅输出当日新触发）",
        "- 任务类型：`daily`（人工运行）",
        f"- 目标交易日：{trade_date}",
        f"- 当日新触发数量：{daily_total}",
        f"- 参数版本：{param_versions_daily}",
        "",
        "## 一、当日可入场清单",
        "| 序号 | 代码 | 名称 | 交易日 | 收盘价 | 入场位(20日高) | 退出位(10日低) |",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for idx, (code, name, date, close_price, entry_price, exit_price) in enumerate(daily_rows, start=1):
        daily_lines.append(
            f"| {idx} | {code} | {name} | {date} | {_fmt_price(close_price)} | {_fmt_price(entry_price)} | {_fmt_price(exit_price)} |"
        )
    daily_lines.extend(
        [
            "",
            "## 二、说明",
            "- 本报告只包含“当日新触发”标的，不包含历史重复触发。",
            "- 若重复执行同一交易日任务，依据 `signal_biz_key` 幂等更新，不会重复插入。",
        ]
    )
    DAILY_MD.write_text("\n".join(daily_lines), encoding="utf-8")
    conn.close()


def markdown_to_html(md_path: Path, html_path: Path) -> None:
    subprocess.run(
        [
            "pandoc",
            str(md_path),
            "-s",
            "--css",
            str(STYLE_PATH),
            "-o",
            str(html_path),
        ],
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
    print(json.dumps(
        {
            "backfill_pdf": str(BACKFILL_PDF),
            "daily_pdf": str(DAILY_PDF),
            "backfill_md": str(BACKFILL_MD),
            "daily_md": str(DAILY_MD),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
