#!/usr/bin/env python3
"""
Targeted retry task for stock_meta updates.

Reads retry codes from scripts/cron/stock_meta_retry_codes.txt, invokes
scripts/update_stock_metadata.py with retry arguments, then reports which
codes were fixed and which still remain behind latest_trade_date.
"""

import argparse
import logging
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Set


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = WORKSPACE_ROOT / "data" / "stock_data.db"
DEFAULT_CODES_FILE = WORKSPACE_ROOT / "scripts" / "cron" / "stock_meta_retry_codes.txt"
DEFAULT_FAILED_OUT = WORKSPACE_ROOT / "scripts" / "cron" / "stock_meta_retry_failed.txt"
UPDATE_SCRIPT = WORKSPACE_ROOT / "scripts" / "update_stock_metadata.py"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(WORKSPACE_ROOT / "logs" / "stock_meta_retry_task.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def load_retry_codes(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"codes file not found: {path}")
    seen: Set[str] = set()
    codes: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not re.fullmatch(r"\d{6}", line):
            logger.warning("Skip invalid code in retry file: %s", line)
            continue
        if line in seen:
            continue
        seen.add(line)
        codes.append(line)
    return codes


def get_latest_trade_date(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT MAX(trade_date) FROM daily_prices")
    latest = cur.fetchone()[0]
    if not latest:
        raise RuntimeError("daily_prices has no trade_date")
    return str(latest)


def get_missing_codes(conn: sqlite3.Connection, latest_trade_date: str, codes: Iterable[str]) -> Set[str]:
    code_list = list(codes)
    if not code_list:
        return set()
    placeholders = ",".join("?" for _ in code_list)
    sql = f"""
        SELECT code
        FROM stock_meta
        WHERE asset_type='stock' AND is_delisted=0
          AND (updated_at IS NULL OR date(substr(updated_at,1,19)) < date(?))
          AND code IN ({placeholders})
    """
    cur = conn.cursor()
    cur.execute(sql, [latest_trade_date, *code_list])
    return {str(row[0]) for row in cur.fetchall()}


def write_failed_codes(path: Path, latest_trade_date: str, failed: List[str]) -> None:
    lines = [
        f"# generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"# latest_trade_date: {latest_trade_date}",
        f"# failed_count: {len(failed)}",
    ]
    lines.extend(failed)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry stock_meta updates for a code list")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to stock_data.db")
    parser.add_argument("--codes-file", default=str(DEFAULT_CODES_FILE), help="Path to retry code file")
    parser.add_argument("--failed-out", default=str(DEFAULT_FAILED_OUT), help="Path to output remaining failed codes")
    parser.add_argument("--login-retry", type=int, default=5, help="BaoStock login retry count")
    parser.add_argument("--query-retry", type=int, default=4, help="BaoStock query retry count")
    parser.add_argument("--retry-delay", type=float, default=1.2, help="Retry base delay seconds")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = (WORKSPACE_ROOT / db_path).resolve()
    codes_file = Path(args.codes_file)
    if not codes_file.is_absolute():
        codes_file = (WORKSPACE_ROOT / codes_file).resolve()
    failed_out = Path(args.failed_out)
    if not failed_out.is_absolute():
        failed_out = (WORKSPACE_ROOT / failed_out).resolve()

    codes = load_retry_codes(codes_file)
    if not codes:
        logger.info("No valid codes in retry file: %s", codes_file)
        return 0

    conn = sqlite3.connect(str(db_path))
    try:
        latest_trade_date = get_latest_trade_date(conn)
        missing_before = get_missing_codes(conn, latest_trade_date, codes)
    finally:
        conn.close()

    logger.info(
        "Retry start: latest_trade_date=%s, target_codes=%d, missing_before=%d",
        latest_trade_date,
        len(codes),
        len(missing_before),
    )
    if not missing_before:
        logger.info("All target codes are already up-to-date.")
        write_failed_codes(failed_out, latest_trade_date, [])
        return 0

    cmd = [
        sys.executable,
        str(UPDATE_SCRIPT),
        "--codes-file",
        str(codes_file),
        "--login-retry",
        str(max(1, args.login_retry)),
        "--query-retry",
        str(max(1, args.query_retry)),
        "--retry-delay",
        str(max(0.1, args.retry_delay)),
    ]
    logger.info("Executing: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True)
    if proc.stdout:
        logger.info("update_stdout:\n%s", proc.stdout.strip())
    if proc.stderr:
        logger.warning("update_stderr:\n%s", proc.stderr.strip())

    conn = sqlite3.connect(str(db_path))
    try:
        latest_trade_date = get_latest_trade_date(conn)
        missing_after = get_missing_codes(conn, latest_trade_date, codes)
    finally:
        conn.close()

    fixed = sorted(list(missing_before - missing_after))
    failed = sorted(list(missing_after))
    write_failed_codes(failed_out, latest_trade_date, failed)

    logger.info(
        "Retry done: fixed=%d, failed=%d, update_rc=%d, failed_out=%s",
        len(fixed),
        len(failed),
        proc.returncode,
        failed_out,
    )
    if fixed:
        logger.info("Fixed codes: %s", ",".join(fixed))
    if failed:
        logger.warning("Failed codes: %s", ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
