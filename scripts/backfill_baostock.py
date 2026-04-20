"""
backfill_baostock.py – Baostock 历史数据回填（Level-1）

修复记录
--------
* [BUG-FIX] 换手率字段名 turn → turnover（与 daily_prices schema 一致）
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sqlite3
import sys
import time
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from typing import Callable, List, Optional, Set, TypeVar

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    BACKUP_DIR,
    BAOSTOCK_ADJUST,
    BAOSTOCK_DAILY_FIELDS,
    CHECKPOINT_DIR,
    DB_BACKUP_COUNT,
    DB_PATH,
    DOWNLOAD_START_DATE,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_FAILURE_FACTOR,
    RATE_LIMIT_MAX_DELAY,
    RATE_LIMIT_MIN_DELAY,
    RATE_LIMIT_SUCCESS_FACTOR,
    RETRY_BASE_DELAY,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
    get_end_date,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_baostock")

F = TypeVar("F", bound=Callable)


# ────────────────────────────────────────────────────────────────────────────
# 重试装饰器
# ────────────────────────────────────────────────────────────────────────────
def with_retry(
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    max_delay: float = RETRY_MAX_DELAY,
    exceptions=(Exception,),
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts - 1:
                        raise
                    wait = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "[retry] %s 第%d次失败: %s，%.1fs后重试",
                        func.__name__, attempt + 1, exc, wait,
                    )
                    time.sleep(wait)
        return wrapper  # type: ignore
    return decorator


# ────────────────────────────────────────────────────────────────────────────
# 自适应限速
# ────────────────────────────────────────────────────────────────────────────
class AdaptiveRateLimiter:
    def __init__(self, initial: float = RATE_LIMIT_DEFAULT) -> None:
        self._delay = initial

    def wait(self) -> None:
        time.sleep(self._delay)

    def success(self) -> None:
        self._delay = max(RATE_LIMIT_MIN_DELAY, self._delay * RATE_LIMIT_SUCCESS_FACTOR)

    def failure(self) -> None:
        self._delay = min(RATE_LIMIT_MAX_DELAY, self._delay * RATE_LIMIT_FAILURE_FACTOR)

    @property
    def current_delay(self) -> float:
        return self._delay


# ────────────────────────────────────────────────────────────────────────────
# Checkpoint
# ────────────────────────────────────────────────────────────────────────────
class Checkpoint:
    def __init__(self, name: str = "baostock") -> None:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self._path = CHECKPOINT_DIR / f"checkpoint_{name}.json"
        self._done: Set[str] = self._load()

    def _load(self) -> Set[str]:
        if self._path.exists():
            try:
                return set(json.loads(self._path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return set()

    def save(self, code: str) -> None:
        self._done.add(code)
        self._path.write_text(
            json.dumps(sorted(self._done), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_done(self, code: str) -> bool:
        return code in self._done

    def clear(self) -> None:
        self._done.clear()
        if self._path.exists():
            self._path.unlink()

    def __len__(self) -> int:
        return len(self._done)


# ────────────────────────────────────────────────────────────────────────────
# DB 备份
# ────────────────────────────────────────────────────────────────────────────
def backup_database() -> Optional[Path]:
    if not DB_PATH.exists():
        logger.warning("DB 不存在，跳过备份")
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"stock_data_{ts}.db.bak"
    try:
        shutil.copy2(str(DB_PATH), str(dest))
        logger.info("DB 已备份至 %s", dest)
        baks = sorted(BACKUP_DIR.glob("stock_data_*.db.bak"))
        for old in baks[:-DB_BACKUP_COUNT]:
            old.unlink(missing_ok=True)
        return dest
    except Exception as exc:
        logger.error("DB 备份失败: %s", exc)
        return None


# ────────────────────────────────────────────────────────────────────────────
# DB 工具
# ────────────────────────────────────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_stocks_to_fill(
    full: bool = False,
    code_list: Optional[List[str]] = None,
) -> List[dict]:
    from config import MIN_DATA_DAYS
    with _get_conn() as conn:
        if code_list:
            placeholders = ",".join("?" * len(code_list))
            rows = conn.execute(
                f"SELECT code, name FROM stocks WHERE code IN ({placeholders})"
                f" AND COALESCE(is_delisted,0)=0",
                code_list,
            ).fetchall()
        elif full:
            rows = conn.execute(
                "SELECT code, name FROM stock_meta WHERE asset_type='stock' AND is_delisted=0"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT s.code, s.name
                FROM   stocks s
                LEFT JOIN (
                    SELECT code, COUNT(*) AS cnt
                    FROM   daily_prices
                    GROUP  BY code
                ) dp ON s.code = dp.code
                WHERE  COALESCE(s.is_delisted,0) = 0
                  AND  COALESCE(dp.cnt, 0) < ?
                """,
                (MIN_DATA_DAYS,),
            ).fetchall()
    return [{"code": r[0], "name": r[1]} for r in rows]


# ────────────────────────────────────────────────────────────────────────────
# Baostock 核心
# ────────────────────────────────────────────────────────────────────────────
def _bs_code(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"sh.{code}"
    return f"sz.{code}"


@with_retry(max_attempts=RETRY_MAX_ATTEMPTS)
def _fetch_one_stock(bs_mod, code: str, start_date: str, end_date: str) -> List[dict]:
    rs = bs_mod.query_history_k_data_plus(
        _bs_code(code),
        BAOSTOCK_DAILY_FIELDS,
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag=BAOSTOCK_ADJUST,
    )
    if rs.error_code != "0":
        raise RuntimeError(f"Baostock 错误: {rs.error_msg}")
    records: List[dict] = []
    fields = BAOSTOCK_DAILY_FIELDS.split(",")
    while rs.next():
        row = rs.get_row_data()
        rec = dict(zip(fields, row))
        if rec.get("tradestatus") == "0":
            continue
        records.append(rec)
    return records


def _safe_float(val) -> Optional[float]:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _insert_records(conn: sqlite3.Connection, code: str, records: List[dict]) -> int:
    """
    插入 Baostock 数据到 daily_prices。
    注意：换手率字段 Baostock 返回 'turn'，写入 DB 列名为 'turnover'。
    """
    inserted = 0
    for rec in records:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_prices
                    (code, trade_date, open, high, low, close, preclose,
                     volume, amount, turnover, pct_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    rec.get("date"),
                    _safe_float(rec.get("open")),
                    _safe_float(rec.get("high")),
                    _safe_float(rec.get("low")),
                    _safe_float(rec.get("close")),
                    _safe_float(rec.get("preclose")),
                    _safe_float(rec.get("volume")),
                    _safe_float(rec.get("amount")),
                    _safe_float(rec.get("turn")),      # Baostock 字段名 turn → DB 列名 turnover
                    _safe_float(rec.get("pctChg")),
                ),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]
        except Exception as exc:
            logger.debug("插入 %s %s 失败: %s", code, rec.get("date"), exc)
    return inserted


# ────────────────────────────────────────────────────────────────────────────
# 主函数
# ────────────────────────────────────────────────────────────────────────────
def run_backfill(
    start_date: str = DOWNLOAD_START_DATE,
    end_date: Optional[str] = None,
    full: bool = False,
    resume: bool = True,
    code_list: Optional[List[str]] = None,
    dry_run: bool = False,
) -> dict:
    if end_date is None:
        end_date = get_end_date()

    logger.info("=== Baostock 回填开始 start=%s end=%s full=%s resume=%s ===",
                start_date, end_date, full, resume)

    if not dry_run:
        backup_database()

    stocks = get_stocks_to_fill(full=full, code_list=code_list)
    logger.info("待处理股票数: %d", len(stocks))
    if not stocks:
        return {"source": "baostock", "success": 0, "total": 0, "inserted": 0, "errors": 0}

    ckpt = Checkpoint("baostock")
    if not resume:
        ckpt.clear()
    logger.info("Checkpoint 已跳过: %d 只", len(ckpt))

    try:
        import baostock as bs
    except ImportError:
        logger.error("baostock 未安装")
        return {"source": "baostock", "success": 0, "total": len(stocks), "inserted": 0, "errors": len(stocks)}

    lg = bs.login()
    if lg.error_code != "0":
        logger.error("Baostock 登录失败: %s", lg.error_msg)
        return {"source": "baostock", "success": 0, "total": len(stocks), "inserted": 0, "errors": len(stocks)}
    logger.info("Baostock 登录成功")

    limiter = AdaptiveRateLimiter(RATE_LIMIT_DEFAULT)
    total_inserted = success_count = error_count = 0

    try:
        conn = _get_conn()
        for idx, stock in enumerate(stocks, 1):
            code, name = stock["code"], stock["name"]
            if ckpt.is_done(code):
                continue
            limiter.wait()
            try:
                records = _fetch_one_stock(bs, code, start_date, end_date)
                if not dry_run and records:
                    n = _insert_records(conn, code, records)
                    conn.commit()
                    total_inserted += n
                    logger.info("[%d/%d] %s %s: 拉取=%d 插入=%d 延迟=%.2fs",
                                idx, len(stocks), code, name, len(records), n, limiter.current_delay)
                else:
                    logger.info("[%d/%d] %s %s: 拉取=%d (dry-run)",
                                idx, len(stocks), code, name, len(records))
                ckpt.save(code)
                success_count += 1
                limiter.success()
            except Exception as exc:
                logger.warning("[%d/%d] %s %s 失败: %s", idx, len(stocks), code, name, exc)
                error_count += 1
                limiter.failure()
        conn.close()
    finally:
        bs.logout()
        logger.info("Baostock 已登出")

    summary = {
        "source": "baostock",
        "start": start_date, "end": end_date,
        "total": len(stocks), "success": success_count,
        "inserted": total_inserted, "errors": error_count,
    }
    logger.info("=== Baostock 回填完成: %s ===", summary)
    return summary


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Baostock 历史数据回填")
    p.add_argument("--start", default=DOWNLOAD_START_DATE)
    p.add_argument("--end", default=None)
    p.add_argument("--full", action="store_true")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--stocks", nargs="+", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = run_backfill(
        start_date=args.start, end_date=args.end, full=args.full,
        resume=not args.no_resume, code_list=args.stocks, dry_run=args.dry_run,
    )
    sys.exit(0 if result.get("errors", 0) == 0 else 4)
