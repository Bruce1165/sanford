#!/usr/bin/env python3
"""
Cron task wrapper for stock_meta freshness/coverage check.

This task executes scripts/check_stock_meta_freshness.py and propagates
its exit code for scheduler monitoring.
"""

import logging
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
CHECK_SCRIPT = WORKSPACE_ROOT / "scripts" / "check_stock_meta_freshness.py"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(WORKSPACE_ROOT / "logs" / "stock_meta_freshness_cron.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("Starting stock_meta freshness cron task")
    cmd = [
        sys.executable,
        str(CHECK_SCRIPT),
        "--min-update-ratio",
        "0.90",
        "--min-sector-ratio",
        "0.95",
    ]
    logger.info("Executing: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True)
    if proc.stdout:
        logger.info("stdout:\n%s", proc.stdout.strip())
    if proc.stderr:
        logger.warning("stderr:\n%s", proc.stderr.strip())

    if proc.returncode == 0:
        logger.info("stock_meta freshness cron task passed")
    else:
        logger.error("stock_meta freshness cron task failed, exit_code=%s", proc.returncode)
    return int(proc.returncode)


if __name__ == "__main__":
    sys.exit(main())
