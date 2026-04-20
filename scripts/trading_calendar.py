"""
trading_calendar.py – A 股交易日历（双级容错）
================================================
Level-1: Baostock（稳定，2700+ 条，实测可用）
Level-2: 周一至周五工作日近似（最终兜底）

移除 AKShare 依赖（py_mini_racer / dlsym macOS 兼容问题）

公共接口
--------
is_trading_day(date)            -> bool
get_recent_trading_day(date)    -> date   当天若非交易日则返回最近的上一交易日
get_trading_days_between(s, e)  -> List[date]
get_next_trading_day(date)      -> date
get_latest_db_trade_date()      -> date | None   DB 中 daily_prices 最新日期
refresh()                       -> None          强制刷新缓存
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("trading_calendar")

# ─────────────────────────── 路径配置 ────────────────────────────
_WORKSPACE = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).parent.parent)))
_DB_PATH = _WORKSPACE / "data" / "stock_data.db"
_CACHE_REFRESH_DAYS = 7          # 缓存超过 N 天则刷新
_BAOSTOCK_MAX_RETRY = 3
_BAOSTOCK_RETRY_DELAY = 2.0      # 秒

# ─────────────────────────── 单例 ────────────────────────────────
_lock = threading.Lock()
_calendar_instance: Optional["TradingCalendar"] = None


def _get_instance() -> "TradingCalendar":
    global _calendar_instance
    if _calendar_instance is None:
        with _lock:
            if _calendar_instance is None:
                _calendar_instance = TradingCalendar()
    return _calendar_instance


# ─────────────────────────── 核心类 ──────────────────────────────
class TradingCalendar:
    """线程安全的 A 股交易日历。"""

    def __init__(self) -> None:
        self._dates: set[date] = set()
        self._sorted: list[date] = []
        self._source: str = "uninitialized"
        self._loaded_at: Optional[datetime] = None
        self._rlock = threading.RLock()
        self._ensure_loaded()

    # ── 公开接口 ─────────────────────────────────────────────────

    def is_trading_day(self, d: date) -> bool:
        self._ensure_loaded()
        return d in self._dates

    def get_recent_trading_day(self, d: Optional[date] = None) -> date:
        """返回 d 当天或之前最近的交易日（最多回溯 30 天）。"""
        self._ensure_loaded()
        if d is None:
            d = date.today()
        for offset in range(30):
            candidate = d - timedelta(days=offset)
            if candidate in self._dates:
                return candidate
        logger.warning("get_recent_trading_day: 回溯 30 天未找到交易日，使用兜底逻辑")
        return self._weekday_fallback_recent(d)

    def get_next_trading_day(self, d: Optional[date] = None) -> date:
        """返回 d 之后第一个交易日（最多向前 30 天）。"""
        self._ensure_loaded()
        if d is None:
            d = date.today()
        for offset in range(1, 31):
            candidate = d + timedelta(days=offset)
            if candidate in self._dates:
                return candidate
        logger.warning("get_next_trading_day: 向前 30 天未找到交易日，使用兜底逻辑")
        return self._weekday_fallback_next(d)

    def get_trading_days_between(self, start: date, end: date) -> List[date]:
        """返回 [start, end] 区间内的所有交易日（含两端）。"""
        self._ensure_loaded()
        return [d for d in self._sorted if start <= d <= end]

    def get_latest_db_trade_date(self) -> Optional[date]:
        """从 daily_prices 表读取最新 trade_date。"""
        if not _DB_PATH.exists():
            return None
        try:
            conn = sqlite3.connect(str(_DB_PATH), timeout=10)
            row = conn.execute(
                "SELECT MAX(trade_date) FROM daily_prices"
            ).fetchone()
            conn.close()
            if row and row[0]:
                return datetime.strptime(str(row[0])[:10], "%Y-%m-%d").date()
        except Exception as exc:
            logger.warning("get_latest_db_trade_date 失败: %s", exc)
        return None

    def refresh(self) -> None:
        """强制从 Baostock 重新拉取，绕过 SQLite 缓存。"""
        logger.info("强制刷新：直接从 Baostock 重新拉取…")
        with self._rlock:
            # 直接调用 Baostock，不经过 _load()（避免命中刚写入的 SQLite 缓存）
            if self._load_from_baostock():
                self._save_to_sqlite_cache()
            else:
                logger.warning("Baostock 刷新失败，保留现有数据")

    @property
    def source(self) -> str:
        return self._source

    @property
    def count(self) -> int:
        return len(self._dates)

    # ── 内部方法 ─────────────────────────────────────────────────

    def _ensure_loaded(self, force: bool = False) -> None:
        with self._rlock:
            if not force and self._loaded_at is not None:
                age_days = (datetime.now() - self._loaded_at).days
                if age_days < _CACHE_REFRESH_DAYS and len(self._dates) > 100:
                    return
            self._load()

    def _load(self) -> None:
        """尝试两级加载。"""
        # Level-1: SQLite 缓存（如果新鲜）
        cached = self._load_from_sqlite_cache()
        if cached:
            logger.info("交易日历从 SQLite 缓存加载，共 %d 条", len(self._dates))
            return

        # Level-1: Baostock 在线
        logger.info("正在刷新 A 股交易日历…")
        if self._load_from_baostock():
            self._save_to_sqlite_cache()
            return

        # Level-2: 工作日兜底
        logger.warning("所有在线源均失败，使用周一至周五工作日近似")
        self._load_weekday_fallback()

    # ─── Baostock ────────────────────────────────────────────────

    def _load_from_baostock(self) -> bool:
        for attempt in range(1, _BAOSTOCK_MAX_RETRY + 1):
            try:
                import baostock as bs  # type: ignore
                lg = bs.login()
                if lg.error_code != "0":
                    raise RuntimeError(f"Baostock 登录失败: {lg.error_msg}")

                # 拉取到今天 +90 天，确保 get_next_trading_day 有数据
                future_end = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
                rs = bs.query_trade_dates(
                    start_date="2005-01-01",
                    end_date=future_end,
                )
                if rs.error_code != "0":
                    bs.logout()
                    raise RuntimeError(f"query_trade_dates 失败: {rs.error_msg}")

                dates: set[date] = set()
                while rs.next():
                    row = rs.get_row_data()
                    # row[0]=calendar_date, row[1]=is_trading_day
                    if len(row) >= 2 and str(row[1]).strip() == "1":
                        try:
                            dates.add(
                                datetime.strptime(str(row[0]).strip(), "%Y-%m-%d").date()
                            )
                        except ValueError:
                            pass

                bs.logout()

                if len(dates) < 100:
                    raise ValueError(f"数据量异常: {len(dates)} 条")

                with self._rlock:
                    self._dates = dates
                    self._sorted = sorted(dates)
                    self._source = "baostock"
                    self._loaded_at = datetime.now()

                logger.info(
                    "Baostock 交易日历获取成功，共 %d 条", len(dates)
                )
                return True

            except Exception as exc:
                logger.warning(
                    "Baostock 第 %d 次失败: %s，%.1fs 后重试",
                    attempt,
                    exc,
                    _BAOSTOCK_RETRY_DELAY * attempt,
                )
                time.sleep(_BAOSTOCK_RETRY_DELAY * attempt)

        logger.error("Baostock 全部 %d 次重试均失败", _BAOSTOCK_MAX_RETRY)
        return False

    # ─── SQLite 缓存 ─────────────────────────────────────────────

    def _load_from_sqlite_cache(self) -> bool:
        """从 DB 缓存读取，若缓存不存在或超期则返回 False。"""
        if not _DB_PATH.exists():
            return False
        try:
            conn = sqlite3.connect(str(_DB_PATH), timeout=10)
            # 建表（首次）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_calendar_cache (
                    trade_date TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

            # 检查缓存新鲜度
            row = conn.execute(
                "SELECT MAX(updated_at) FROM trading_calendar_cache"
            ).fetchone()
            if not row or not row[0]:
                conn.close()
                return False

            cache_dt = datetime.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S")
            age_days = (datetime.now() - cache_dt).days
            if age_days >= _CACHE_REFRESH_DAYS:
                conn.close()
                return False

            # 读取缓存
            rows = conn.execute(
                "SELECT trade_date FROM trading_calendar_cache"
            ).fetchall()
            conn.close()

            if len(rows) < 100:
                return False

            dates: set[date] = set()
            for (td,) in rows:
                try:
                    dates.add(datetime.strptime(str(td)[:10], "%Y-%m-%d").date())
                except ValueError:
                    pass

            with self._rlock:
                self._dates = dates
                self._sorted = sorted(dates)
                self._source = "sqlite_cache"
                self._loaded_at = cache_dt

            return True

        except Exception as exc:
            logger.warning("SQLite 缓存读取失败: %s", exc)
            return False

    def _save_to_sqlite_cache(self) -> None:
        """将当前 _dates 写入 SQLite 缓存。"""
        if not _DB_PATH.parent.exists():
            return
        try:
            conn = sqlite3.connect(str(_DB_PATH), timeout=10)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_calendar_cache (
                    trade_date TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL
                )
                """
            )
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("DELETE FROM trading_calendar_cache")
            conn.executemany(
                "INSERT INTO trading_calendar_cache VALUES (?, ?)",
                [(d.strftime("%Y-%m-%d"), now_str) for d in self._dates],
            )
            conn.commit()
            conn.close()
            logger.debug("交易日历已写入 SQLite 缓存，共 %d 条", len(self._dates))
        except Exception as exc:
            logger.warning("SQLite 缓存写入失败: %s", exc)

    # ─── 工作日兜底 ──────────────────────────────────────────────

    def _load_weekday_fallback(self) -> None:
        """生成 2010-01-01 至今后 30 天的工作日集合（无节假日排除）。"""
        start = date(2010, 1, 1)
        end = date.today() + timedelta(days=30)
        dates: set[date] = set()
        cur = start
        while cur <= end:
            if cur.weekday() < 5:  # 0=Mon … 4=Fri
                dates.add(cur)
            cur += timedelta(days=1)
        with self._rlock:
            self._dates = dates
            self._sorted = sorted(dates)
            self._source = "weekday_fallback"
            self._loaded_at = datetime.now()
        logger.warning(
            "工作日近似加载完成，共 %d 条（不含节假日）", len(dates)
        )

    @staticmethod
    def _weekday_fallback_recent(d: date) -> date:
        for offset in range(30):
            candidate = d - timedelta(days=offset)
            if candidate.weekday() < 5:
                return candidate
        return d

    @staticmethod
    def _weekday_fallback_next(d: date) -> date:
        for offset in range(1, 31):
            candidate = d + timedelta(days=offset)
            if candidate.weekday() < 5:
                return candidate
        return d + timedelta(days=1)


# ─────────────────────────── 模块级公开函数 ──────────────────────


def is_trading_day(d: Optional[date] = None) -> bool:
    if d is None:
        d = date.today()
    return _get_instance().is_trading_day(d)


def get_recent_trading_day(d: Optional[date] = None) -> date:
    return _get_instance().get_recent_trading_day(d)


def get_next_trading_day(d: Optional[date] = None) -> date:
    return _get_instance().get_next_trading_day(d)


def get_trading_days_between(start: date, end: date) -> List[date]:
    return _get_instance().get_trading_days_between(start, end)


def get_latest_db_trade_date() -> Optional[date]:
    return _get_instance().get_latest_db_trade_date()


def refresh_calendar() -> None:
    """强制刷新交易日历缓存（供 orchestrator 调用）。"""
    _get_instance().refresh()


def get_calendar_info() -> dict:
    inst = _get_instance()
    return {
        "source": inst.source,
        "count": inst.count,
        "loaded_at": inst._loaded_at.isoformat() if inst._loaded_at else None,
    }


# ─────────────────────────── CLI 入口 ────────────────────────────
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="A 股交易日历工具")
    parser.add_argument("--refresh", action="store_true", help="强制刷新缓存")
    parser.add_argument("--date", default=None, help="检查指定日期 YYYY-MM-DD")
    args = parser.parse_args()

    if args.refresh:
        refresh_calendar()

    check_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else date.today()
    )

    cal = _get_instance()
    print(f"{check_date} 是否交易日: {is_trading_day(check_date)}")
    print(f"最近交易日: {get_recent_trading_day(check_date)}")
    print(f"前一交易日: {get_recent_trading_day(check_date - timedelta(days=1))}")
    print(f"下一交易日: {get_next_trading_day(check_date)}")
    print(f"DB 最新数据日: {get_latest_db_trade_date()}")
    print(f"日历信息: {get_calendar_info()}")
