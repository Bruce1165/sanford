"""
sync_market_cap.py – 每日市值同步（AKShare → stocks 表）

从 AKShare stock_zh_a_spot_em() 获取全市场实时总市值和流通市值，
更新到 stocks 表的 total_market_cap / circulating_market_cap 字段。

特性
----
* 指数退避重试
* 批量 UPDATE（单次事务）
* 只更新 stocks 表中已存在的代码
* 写入 ifind_updated_at（复用现有字段记录同步时间）
"""

from __future__ import annotations

import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DB_PATH,
    RETRY_BASE_DELAY,
    RETRY_MAX_ATTEMPTS,
)
from backfill_baostock import with_retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync_market_cap")


# ────────────────────────────────────────────────────────────────────────────
# AKShare 获取（带重试）
# ────────────────────────────────────────────────────────────────────────────
@with_retry(max_attempts=RETRY_MAX_ATTEMPTS)
def _fetch_market_cap() -> list[dict]:
    """
    从 AKShare 获取全市场市值数据。
    返回字段：code, total_market_cap, circulating_market_cap
    单位：元（原始数值）
    """
    import akshare as ak
    df = ak.stock_zh_a_spot_em()
    if df is None or df.empty:
        raise ValueError("AKShare 返回空数据")

    required = {"代码", "总市值", "流通市值"}
    if not required.issubset(df.columns):
        raise ValueError(f"字段缺失: {required - set(df.columns)}")

    df = df[["代码", "总市值", "流通市值"]].copy()
    df.columns = ["code", "total_market_cap", "circulating_market_cap"]
    df = df.dropna(subset=["total_market_cap", "circulating_market_cap"])

    return df.to_dict(orient="records")


# ────────────────────────────────────────────────────────────────────────────
# 写入 DB
# ────────────────────────────────────────────────────────────────────────────
def _update_db(records: list[dict]) -> int:
    """
    批量更新 stocks 表的市值字段。
    只更新 stocks 表中已存在的代码（不插入新行）。
    返回实际更新行数。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    updated = 0
    try:
        for rec in records:
            cursor = conn.execute(
                """
                UPDATE stocks
                SET    total_market_cap       = ?,
                       circulating_market_cap = ?,
                       ifind_updated_at       = ?
                WHERE  code = ?
                """,
                (
                    rec["total_market_cap"],
                    rec["circulating_market_cap"],
                    now,
                    rec["code"],
                ),
            )
            updated += cursor.rowcount
        conn.commit()
    finally:
        conn.close()

    return updated


# ────────────────────────────────────────────────────────────────────────────
# 主函数
# ────────────────────────────────────────────────────────────────────────────
def run_sync(dry_run: bool = False) -> dict:
    """
    执行市值同步。

    Returns
    -------
    dict  包含 fetched / updated / elapsed 的摘要。
    """
    logger.info("=== 市值同步开始 ===")
    start = time.time()

    try:
        records = _fetch_market_cap()
        logger.info("AKShare 返回 %d 条市值数据", len(records))
    except Exception as exc:
        logger.error("AKShare 获取市值失败: %s", exc)
        return {"ok": False, "error": str(exc), "fetched": 0, "updated": 0}

    if dry_run:
        logger.info("dry-run 模式，不写库")
        return {"ok": True, "fetched": len(records), "updated": 0, "dry_run": True}

    try:
        updated = _update_db(records)
    except Exception as exc:
        logger.error("DB 更新失败: %s", exc)
        return {"ok": False, "error": str(exc), "fetched": len(records), "updated": 0}

    elapsed = round(time.time() - start, 1)
    logger.info("=== 市值同步完成: 获取=%d 更新=%d 耗时=%.1fs ===",
                len(records), updated, elapsed)
    return {"ok": True, "fetched": len(records), "updated": updated, "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="每日市值同步")
    p.add_argument("--dry-run", action="store_true", help="不写库，只拉取")
    args = p.parse_args()

    result = run_sync(dry_run=args.dry_run)
    print(result)
    sys.exit(0 if result.get("ok") else 1)
