"""
download_orchestrator.py – NeoTrade 主编排器（生产级）

工作流
------
Step 0   判断交易日（非交易日 exit 5）
Step 1   下载今日行情（download_today.py，mootdx → baostock → akshare）
Step 2   验证数据完整性（verify_data_integrity.py）
Step 3   历史回填（Baostock → AKShare → mootdx）
Step 3.5 市值同步（AKShare stock_zh_a_spot_em → stocks 表）
Step 4   运行所有选股器

CLI
---
--full-verify   完整验证
--no-backfill   跳过 Step 3 + Step 3.5
--dry-run       试运行，不写库
--force         强制运行（非交易日）
--resume        回填断点续传（默认）
--no-resume     重置 checkpoint
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import shutil
import subprocess
import sys
import time
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    BACKUP_DIR,
    DB_BACKUP_COUNT,
    DB_PATH,
    ENABLE_NOTIFICATIONS,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    LOGS_DIR,
    RUN_HISTORY_FILE,
    RUN_HISTORY_MAX_ENTRIES,
    SCRIPTS_DIR,
    STATUS_FILE,
    STEP_TIMEOUT,
    get_end_date,
)

# ────────────────────────────────────────────────────────────────────────────
# 日志配置
# ────────────────────────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
_log_file = LOGS_DIR / f"orchestrator_{date.today().strftime('%Y%m%d')}.log"

_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")

_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO)
_ch.setFormatter(_fmt)
_root.addHandler(_ch)

_fh = RotatingFileHandler(str(_log_file), maxBytes=LOG_MAX_BYTES,
                           backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)
_root.addHandler(_fh)

logger = logging.getLogger("orchestrator")


# ────────────────────────────────────────────────────────────────────────────
# 工具函数
# ────────────────────────────────────────────────────────────────────────────
def notify_macos(title: str, message: str, subtitle: str = "NeoTrade") -> None:
    if not ENABLE_NOTIFICATIONS or platform.system() != "Darwin":
        return
    try:
        script = (f'display notification "{message}" '
                  f'with title "{title}" subtitle "{subtitle}"')
        subprocess.run(["osascript", "-e", script], timeout=5, capture_output=True)
    except Exception:
        pass


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


def write_status_file(status: Dict[str, Any]) -> None:
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(
            json.dumps(status, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("写入状态文件失败: %s", exc)


def append_run_history(record: Dict[str, Any]) -> None:
    try:
        RUN_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        history: List[dict] = []
        if RUN_HISTORY_FILE.exists():
            try:
                history = json.loads(RUN_HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append(record)
        history = history[-RUN_HISTORY_MAX_ENTRIES:]
        RUN_HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("写入运行历史失败: %s", exc)


def _run_script(
    script_path: Path,
    extra_args: Optional[List[str]] = None,
    timeout: int = STEP_TIMEOUT,
    max_retries: int = 3,
) -> Tuple[int, str, str]:
    cmd = [sys.executable, str(script_path)] + (extra_args or [])
    rc, stdout_tail, stderr_tail = -1, "", ""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                cmd, timeout=timeout, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            stdout_tail = result.stdout[-2000:] if result.stdout else ""
            stderr_tail = result.stderr[-2000:] if result.stderr else ""
            rc = result.returncode
            if rc == 0:
                return rc, stdout_tail, stderr_tail
            wait = 2 ** attempt
            logger.warning("脚本 %s 第%d次失败(rc=%d)，%.0fs后重试",
                           script_path.name, attempt + 1, rc, wait)
            time.sleep(wait)
        except subprocess.TimeoutExpired:
            return -1, "", f"Timeout after {timeout}s"
        except Exception as exc:
            return -2, "", str(exc)
    return rc, stdout_tail, stderr_tail


# ────────────────────────────────────────────────────────────────────────────
# Step 0：交易日检测
# ────────────────────────────────────────────────────────────────────────────
def step0_check_trading_day(force: bool = False) -> bool:
    if force:
        logger.info("Step 0: --force 模式，跳过交易日检测")
        return True
    try:
        from trading_calendar import is_trading_day
        result = is_trading_day()
        logger.info("Step 0: 今日 %s 是否为交易日: %s", date.today(), result)
        return result
    except Exception as exc:
        logger.warning("Step 0: 交易日检测异常（%s），默认按交易日处理", exc)
        return True


# ────────────────────────────────────────────────────────────────────────────
# Step 1：下载今日行情
# ────────────────────────────────────────────────────────────────────────────
def step1_download_today(dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=== Step 1: 下载今日行情 ===")
    start_ts = time.time()

    if dry_run:
        logger.info("Step 1: dry-run，跳过")
        return {"ok": True, "dry_run": True, "elapsed": 0}

    script = SCRIPTS_DIR / "download_today_ifind.py"
    if not script.exists():
        logger.error("download_today.py 不存在")
        return {"ok": False, "rc": 1, "error": "download_today.py not found", "elapsed": 0}

    rc, _, err = _run_script(script, extra_args=["--fundamentals"], timeout=STEP_TIMEOUT, max_retries=1)
    elapsed = round(time.time() - start_ts, 1)
    if rc == 0:
        logger.info("Step 1 完成，耗时 %.1fs", elapsed)
        return {"ok": True, "rc": 0, "elapsed": elapsed}

    logger.error("Step 1 失败 rc=%d\n%s", rc, err[-500:])
    notify_macos("❌ NeoTrade 下载失败", f"今日行情下载失败 rc={rc}", "Step 1")
    return {"ok": False, "rc": rc, "error": err[-500:], "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# Step 1.5：元数据同步（BaoStock → stock_meta）
# ────────────────────────────────────────────────────────────────────────────
def step15_sync_stock_meta(dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=== Step 1.5: 元数据同步（BaoStock → stock_meta）===")
    start_ts = time.time()

    script = SCRIPTS_DIR / "update_stock_metadata.py"
    if not script.exists():
        logger.error("update_stock_metadata.py 不存在")
        return {"ok": False, "rc": 1, "error": "update_stock_metadata.py not found", "elapsed": 0}

    args = ["--dry-run"] if dry_run else []
    rc, _, err = _run_script(script, extra_args=args, timeout=STEP_TIMEOUT, max_retries=1)
    elapsed = round(time.time() - start_ts, 1)
    if rc == 0:
        logger.info("Step 1.5 完成，耗时 %.1fs", elapsed)
        return {"ok": True, "rc": 0, "elapsed": elapsed}

    logger.error("Step 1.5 失败 rc=%d\n%s", rc, err[-500:])
    notify_macos("❌ 元数据同步失败", f"stock_meta 同步失败 rc={rc}", "Step 1.5")
    return {"ok": False, "rc": rc, "error": err[-500:], "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# Step 2：数据完整性验证
# ────────────────────────────────────────────────────────────────────────────
def step2_verify_integrity(full_verify: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=== Step 2: 数据完整性验证 ===")
    start_ts = time.time()

    script = SCRIPTS_DIR / "verify_data_integrity.py"
    if not script.exists():
        logger.warning("验证脚本不存在，跳过")
        return {"ok": True, "skipped": True, "elapsed": 0}

    if dry_run:
        logger.info("Step 2: dry-run，跳过")
        return {"ok": True, "dry_run": True, "elapsed": 0}

    args = ["--full"] if full_verify else ["--full"]
    rc, _, err = _run_script(script, extra_args=args, timeout=STEP_TIMEOUT)
    elapsed = round(time.time() - start_ts, 1)

    if rc not in (0, 3):
        logger.error("Step 2 失败 rc=%d", rc)
        notify_macos("⚠️ NeoTrade 验证失败", f"数据验证异常 rc={rc}", "Step 2")
        return {"ok": False, "rc": rc, "error": err[-500:], "elapsed": elapsed}

    logger.info("Step 2 完成，耗时 %.1fs", elapsed)
    return {"ok": True, "rc": rc, "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# Step 3：历史回填（三级容错）
# ────────────────────────────────────────────────────────────────────────────
def step3_backfill(resume: bool = True, dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=== Step 3: 历史回填（Baostock → AKShare → mootdx）===")
    start_ts = time.time()
    backup_database()
    results = {}

    for source, module_name in [
        ("baostock", "backfill_baostock"),
        ("akshare",  "backfill_akshare"),
        ("mootdx",   "backfill_mootdx"),
    ]:
        step_label = {"baostock": "3.1", "akshare": "3.2", "mootdx": "3.3"}[source]
        try:
            import importlib
            mod = importlib.import_module(module_name)
            logger.info("Step %s: %s 回填…", step_label, source)
            r = mod.run_backfill(resume=resume, dry_run=dry_run)
            results[source] = r
            if r.get("errors", 0) == 0:
                logger.info("Step %s: %s 完成，插入=%d", step_label, source, r.get("inserted", 0))
            else:
                logger.warning("Step %s: %s 有 %d 个错误", step_label, source, r["errors"])
        except Exception as exc:
            logger.warning("Step %s: %s 异常: %s", step_label, source, exc)
            results[source] = {"ok": False, "error": str(exc)}

    total_inserted = sum(v.get("inserted", 0) for v in results.values() if isinstance(v, dict))
    elapsed = round(time.time() - start_ts, 1)
    logger.info("Step 3 完成，总插入=%d，耗时 %.1fs", total_inserted, elapsed)
    return {"ok": True, "details": results, "total_inserted": total_inserted, "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# Step 3.5：市值同步
# ────────────────────────────────────────────────────────────────────────────
def step35_sync_market_cap(dry_run: bool = False) -> Dict[str, Any]:
    logger.info("=== Step 3.5: 市值同步（AKShare → stocks 表）===")
    start_ts = time.time()
    try:
        from sync_market_cap import run_sync
        result = run_sync(dry_run=dry_run)
        elapsed = round(time.time() - start_ts, 1)
        if result.get("ok"):
            logger.info("Step 3.5 完成: 获取=%d 更新=%d 耗时=%.1fs",
                        result.get("fetched", 0), result.get("updated", 0), elapsed)
        else:
            logger.warning("Step 3.5 失败: %s", result.get("error"))
            notify_macos("⚠️ 市值同步失败", result.get("error", "未知错误"), "Step 3.5")
        result["elapsed"] = elapsed
        return result
    except Exception as exc:
        elapsed = round(time.time() - start_ts, 1)
        logger.warning("Step 3.5 异常: %s", exc)
        return {"ok": False, "error": str(exc), "elapsed": elapsed}


# ────────────────────────────────────────────────────────────────────────────
# 主函数
# ────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="NeoTrade 主编排器")
    parser.add_argument("--full-verify", action="store_true")
    parser.add_argument("--no-backfill", action="store_true", help="跳过 Step 3 + Step 3.5")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--force",       action="store_true")
    parser.add_argument("--resume",      action="store_true", default=True)
    parser.add_argument("--no-resume",   action="store_true")
    args = parser.parse_args()

    resume = args.resume and not args.no_resume
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_start = time.time()

    logger.info("=" * 60)
    logger.info("NeoTrade 编排器启动 run_id=%s", run_id)
    logger.info("参数: full_verify=%s no_backfill=%s no_screeners=%s dry_run=%s force=%s resume=%s",
                args.full_verify, args.no_backfill, args.dry_run, args.force, resume)
    logger.info("=" * 60)

    report: Dict[str, Any] = {
        "run_id": run_id,
        "date": get_end_date(),
        "started_at": datetime.now().isoformat(),
        "args": vars(args),
        "steps": {},
    }

    # Step 0
    if not step0_check_trading_day(force=args.force):
        logger.info("今日非交易日，退出（exit 5）")
        report["outcome"] = "non_trading_day"
        _finalize(report, run_start)
        return 5

    # Step 1
    s1 = step1_download_today(dry_run=args.dry_run)
    report["steps"]["step1"] = s1
    if not s1["ok"]:
        report["outcome"] = "download_failed"
        _finalize(report, run_start)
        return 2

    # Step 1.5
    s15 = step15_sync_stock_meta(dry_run=args.dry_run)
    report["steps"]["step1_5_stock_meta"] = s15
    if not s15["ok"]:
        report["outcome"] = "stock_meta_sync_failed"
        _finalize(report, run_start)
        return 6

    # Step 2
    s2 = step2_verify_integrity(full_verify=args.full_verify, dry_run=args.dry_run)
    report["steps"]["step2"] = s2
    if not s2["ok"]:
        report["outcome"] = "verify_failed"
        _finalize(report, run_start)
        return 3

    # Step 3 + Step 3.5
    if not args.no_backfill:
        s3 = step3_backfill(resume=resume, dry_run=args.dry_run)
        report["steps"]["step3"] = s3
        if not s3.get("ok"):
            report["outcome"] = "backfill_failed"
            _finalize(report, run_start)
            return 4

        s35 = step35_sync_market_cap(dry_run=args.dry_run)
        report["steps"]["step3_5_market_cap"] = s35
        # 市值同步失败不阻断流程，只记录警告
        if not s35.get("ok"):
            logger.warning("市值同步失败，继续执行选股器")
    else:
        logger.info("Step 3 + 3.5: 已跳过（--no-backfill）")
        report["steps"]["step3"] = {"skipped": True}
        report["steps"]["step3_5_market_cap"] = {"skipped": True}

    report["outcome"] = "success"
    _finalize(report, run_start)
    notify_macos("✅ NeoTrade 完成", f"所有步骤成功 run_id={run_id}", "编排器")
    return 0


def _finalize(report: Dict[str, Any], run_start: float) -> None:
    elapsed = round(time.time() - run_start, 1)
    report["elapsed_total"] = elapsed
    report["finished_at"] = datetime.now().isoformat()

    report_path = LOGS_DIR / f"orchestrator_report_{date.today()}.json"
    try:
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("报告已写入 %s", report_path)
    except Exception as exc:
        logger.warning("写入报告失败: %s", exc)

    write_status_file({
        "run_id": report.get("run_id"),
        "date": report.get("date"),
        "outcome": report.get("outcome"),
        "elapsed": elapsed,
        "updated_at": report.get("finished_at"),
    })

    append_run_history({
        "run_id": report.get("run_id"),
        "date": report.get("date"),
        "outcome": report.get("outcome"),
        "elapsed": elapsed,
        "ts": report.get("finished_at"),
    })

    logger.info("编排器结束 run_id=%s outcome=%s 总耗时=%.1fs",
                report.get("run_id"), report.get("outcome"), elapsed)


if __name__ == "__main__":
    sys.exit(main())
