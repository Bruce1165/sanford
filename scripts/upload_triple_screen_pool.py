#!/usr/bin/env python3
"""
Import triple-screen pool from Excel into triple_screen_pool.

Default mode is dry-run (no DB writes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import config  # noqa: E402


NAME_KEYWORD_EXCLUDES = ("指数", "ETF", "LOF", "REIT", "REITs")
INDEX_PREFIX_EXCLUDES = ("399",)
DEFAULT_MANUAL_EXCLUDE_CODES = ("000680",)


def normalize_code(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6)


def detect_columns(df: pd.DataFrame) -> Tuple[str, str]:
    code_alias = ("代码", "股票代码", "stock_code", "code")
    name_alias = ("名称", "股票名称", "stock_name", "name")

    code_col = None
    name_col = None
    for col in df.columns:
        col_s = str(col).strip().lower()
        if code_col is None and any(a.lower() in col_s for a in code_alias):
            code_col = col
        if name_col is None and any(a.lower() in col_s for a in name_alias):
            name_col = col
    if code_col is None and len(df.columns) >= 1:
        code_col = df.columns[0]
    if name_col is None and len(df.columns) >= 2:
        name_col = df.columns[1]
    if code_col is None or name_col is None:
        raise ValueError("Cannot detect code/name columns from Excel")
    return str(code_col), str(name_col)


def classify_row(stock_code: str, stock_name: str, manual_exclude_codes: set[str]) -> Tuple[bool, str]:
    if not stock_code or not stock_code.isdigit() or len(stock_code) != 6:
        return False, "invalid_code"
    if stock_code in manual_exclude_codes:
        return False, "manual_exclude_code"
    if stock_code.startswith(INDEX_PREFIX_EXCLUDES):
        return False, "index_code_prefix"
    if any(k.lower() in stock_name.lower() for k in NAME_KEYWORD_EXCLUDES):
        return False, "index_name_keyword"
    return True, "valid"


def build_pool_biz_key(stock_code: str) -> str:
    return hashlib.sha256(stock_code.encode("utf-8")).hexdigest()[:32]


def parse_excel(excel_path: Path, manual_exclude_codes: set[str]) -> Tuple[List[dict], Dict[str, int], Dict[str, List[dict]]]:
    df = pd.read_excel(excel_path)
    code_col, name_col = detect_columns(df)
    stats = {
        "total_rows": int(len(df)),
        "valid_rows": 0,
        "invalid_code": 0,
        "manual_exclude_code": 0,
        "index_code_prefix": 0,
        "index_name_keyword": 0,
        "deduped_within_file": 0,
    }
    samples: Dict[str, List[dict]] = {
        "invalid_code": [],
        "manual_exclude_code": [],
        "index_code_prefix": [],
        "index_name_keyword": [],
    }
    by_code: Dict[str, dict] = {}
    for _, row in df.iterrows():
        code = normalize_code(row.get(code_col, ""))
        name = str(row.get(name_col, "")).strip()
        ok, reason = classify_row(code, name, manual_exclude_codes)
        if not ok:
            stats[reason] += 1
            if len(samples[reason]) < 20:
                samples[reason].append({"stock_code": code, "stock_name": name})
            continue
        if code in by_code:
            stats["deduped_within_file"] += 1
            continue
        by_code[code] = {"stock_code": code, "stock_name": name}
        stats["valid_rows"] += 1
    return list(by_code.values()), stats, samples


def run_import(excel_path: Path, execute: bool, deactivate_missing: bool, manual_exclude_codes: set[str]) -> dict:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    records, stats, samples = parse_excel(excel_path, manual_exclude_codes)
    report = {
        "timestamp": datetime.now().isoformat(),
        "file": str(excel_path),
        "execute": execute,
        "deactivate_missing": deactivate_missing,
        "manual_exclude_codes": sorted(list(manual_exclude_codes)),
        "stats": stats,
        "samples": samples,
        "db_changes": {"upserted": 0, "deactivated": 0},
    }
    if not execute:
        return report

    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    import_date = datetime.now().strftime("%Y-%m-%d")
    source_file = excel_path.name

    try:
        cur = conn.cursor()
        for rec in records:
            biz_key = build_pool_biz_key(rec["stock_code"])
            cur.execute(
                """
                INSERT INTO triple_screen_pool
                (pool_biz_key, stock_code, stock_name, source_file, import_batch_id, import_date,
                 is_active, validation_status, validation_message)
                VALUES (?, ?, ?, ?, ?, ?, 1, 'valid', NULL)
                ON CONFLICT(pool_biz_key) DO UPDATE SET
                    stock_code = excluded.stock_code,
                    stock_name = excluded.stock_name,
                    source_file = excluded.source_file,
                    import_batch_id = excluded.import_batch_id,
                    import_date = excluded.import_date,
                    is_active = 1,
                    validation_status = 'valid',
                    validation_message = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    biz_key,
                    rec["stock_code"],
                    rec["stock_name"],
                    source_file,
                    batch_id,
                    import_date,
                ),
            )
        report["db_changes"]["upserted"] = len(records)

        if deactivate_missing:
            imported_codes = [r["stock_code"] for r in records]
            if imported_codes:
                placeholders = ",".join("?" for _ in imported_codes)
                cur.execute(
                    f"""
                    UPDATE triple_screen_pool
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE is_active = 1 AND stock_code NOT IN ({placeholders})
                    """,
                    imported_codes,
                )
            else:
                cur.execute(
                    """
                    UPDATE triple_screen_pool
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE is_active = 1
                    """
                )
            report["db_changes"]["deactivated"] = cur.rowcount if cur.rowcount is not None else 0

        if manual_exclude_codes:
            placeholders = ",".join("?" for _ in manual_exclude_codes)
            cur.execute(
                f"""
                UPDATE triple_screen_pool
                SET is_active = 0,
                    validation_status = 'manual_exclude',
                    validation_message = 'manually excluded by import rule',
                    updated_at = CURRENT_TIMESTAMP
                WHERE stock_code IN ({placeholders})
                """,
                tuple(sorted(list(manual_exclude_codes))),
            )

        conn.commit()
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import pool file into triple_screen_pool")
    parser.add_argument("--file", required=True, help="Excel file path")
    parser.add_argument("--execute", action="store_true", help="Actually write DB. Default dry-run")
    parser.add_argument("--deactivate-missing", action="store_true", help="Deactivate missing stocks in current import")
    parser.add_argument(
        "--exclude-codes",
        default=",".join(DEFAULT_MANUAL_EXCLUDE_CODES),
        help="Comma-separated stock codes to exclude",
    )
    parser.add_argument("--report", default="", help="Optional report output json path")
    args = parser.parse_args()

    excel_path = Path(args.file).expanduser().resolve()
    manual_exclude_codes = {
        normalize_code(x)
        for x in str(args.exclude_codes).split(",")
        if str(x).strip()
    }
    report = run_import(
        excel_path=excel_path,
        execute=bool(args.execute),
        deactivate_missing=bool(args.deactivate_missing),
        manual_exclude_codes=manual_exclude_codes,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else ROOT / "logs" / f"triple_screen_import_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] report saved: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
