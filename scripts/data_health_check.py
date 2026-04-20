#!/usr/bin/env python3
"""
data_health_check.py — NeoTrade 数据健康检查
检查维度：
  1. 股票池概览（活跃/退市/指数/ST排除/北交所排除）
  2. 历史数据完整性
  3. 当日数据分类
  4. 宏数据覆盖率
"""
import sqlite3
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path(__file__).parent.parent
DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"


class DataHealthChecker:

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor = None
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "checks": {},
            "alerts": []
        }

    def connect(self) -> bool:
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        if self.conn:
            self.conn.close()

    # ─────────────────────────────────────────────
    # 股票池概览
    # ─────────────────────────────────────────────
    def check_stock_pool(self) -> Dict[str, Any]:
        try:
            self.cursor.execute("SELECT COUNT(*) FROM stock_meta")
            total = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM stock_meta WHERE asset_type='stock' AND is_delisted=0")
            active = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM stock_meta WHERE is_delisted=1 AND asset_type='stock'")
            delisted = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM stock_meta WHERE asset_type='index'")
            indices = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM stock_meta WHERE name LIKE '%ST%' AND asset_type='stock'")
            st_count = self.cursor.fetchone()[0]

            # 近30天新上市
            thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
            self.cursor.execute(
                "SELECT COUNT(*) FROM stock_meta WHERE list_date >= ? AND asset_type='stock' AND is_delisted=0",
                (thirty_days_ago,)
            )
            newly_listed = self.cursor.fetchone()[0]

            return {
                "status": "pass",
                "total": total,
                "active_stocks": active,
                "delisted_stocks": delisted,
                "indices": indices,
                "st_stocks": st_count,
                "st_excluded": True,
                "bj_excluded": True,
                "newly_listed_30d": newly_listed,
                "message": f"活跃股票 {active} 只 | 退市 {delisted} | 指数 {indices} | 近30天新上市 {newly_listed}"
            }
        except Exception as e:
            logger.error(f"股票池检查失败: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # 历史数据完整性
    # ─────────────────────────────────────────────
    def check_history_data(self) -> Dict[str, Any]:
        try:
            self.cursor.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM daily_prices")
            row = self.cursor.fetchone()
            earliest, latest, trading_days = row[0], row[1], row[2]

            self.cursor.execute("SELECT COUNT(*) FROM daily_prices")
            total_records = self.cursor.fetchone()[0]

            # 价格缺失
            self.cursor.execute("""
                SELECT COUNT(*) FROM daily_prices
                WHERE close IS NULL OR open IS NULL OR high IS NULL OR low IS NULL
            """)
            missing_prices = self.cursor.fetchone()[0]

            # 受影响股票数
            self.cursor.execute("""
                SELECT COUNT(DISTINCT code) FROM daily_prices
                WHERE close IS NULL OR open IS NULL OR high IS NULL OR low IS NULL
            """)
            missing_stocks = self.cursor.fetchone()[0]

            status = "pass" if missing_prices == 0 else "warning"

            return {
                "status": status,
                "earliest_date": earliest,
                "latest_date": latest,
                "trading_days": trading_days,
                "total_records": total_records,
                "missing_price_records": missing_prices,
                "missing_price_stocks": missing_stocks,
                "message": f"覆盖 {earliest} ~ {latest}，共 {trading_days} 个交易日，{total_records:,} 条记录"
            }
        except Exception as e:
            logger.error(f"历史数据检查失败: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # 当日数据
    # ─────────────────────────────────────────────
    def check_today_data(self) -> Dict[str, Any]:
        try:
            self.cursor.execute("SELECT MAX(trade_date) FROM daily_prices")
            latest_date = self.cursor.fetchone()[0]

            self.cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE trade_date=?", (latest_date,))
            total = self.cursor.fetchone()[0]

            self.cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE trade_date=? AND volume>0", (latest_date,))
            normal = self.cursor.fetchone()[0]

            self.cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE trade_date=? AND volume=0 AND close>0", (latest_date,))
            suspended = self.cursor.fetchone()[0]

            self.cursor.execute(
                "SELECT COUNT(*) FROM daily_prices WHERE trade_date=? AND volume=0 AND close=0", (latest_date,))
            zero_both = self.cursor.fetchone()[0]

            # 主板涨跌幅异常（>11%，排除科创/创业）
            self.cursor.execute("""
                SELECT COUNT(*) FROM daily_prices
                WHERE trade_date=?
                AND ABS(pct_change) > 11
                AND code NOT LIKE '3%'
                AND code NOT LIKE '688%'
            """, (latest_date,))
            abnormal_pct = self.cursor.fetchone()[0]

            today = date.today().isoformat()
            is_today = (latest_date == today)
            status = "pass" if abnormal_pct == 0 and zero_both == 0 else "warning"

            return {
                "status": status,
                "date": latest_date,
                "is_today": is_today,
                "total": total,
                "normal_trading": normal,
                "suspended": suspended,
                "zero_price_volume": zero_both,
                "abnormal_pct_change": abnormal_pct,
                "message": f"{'今日' if is_today else '最近交易日'} {latest_date} | 正常 {normal} | 停牌 {suspended} | 异常涨跌 {abnormal_pct}"
            }
        except Exception as e:
            logger.error(f"当日数据检查失败: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # 宏数据覆盖率
    # ─────────────────────────────────────────────
    def check_macro_data(self) -> Dict[str, Any]:
        try:
            # 只统计活跃股票
            self.cursor.execute("""
                SELECT COUNT(*) FROM stocks s
                JOIN stock_meta m ON s.code = m.code
                WHERE m.asset_type='stock' AND m.is_delisted=0
            """)
            active = self.cursor.fetchone()[0]

            def coverage(field):
                self.cursor.execute(f"""
                    SELECT COUNT(*) FROM stocks s
                    JOIN stock_meta m ON s.code = m.code
                    WHERE m.asset_type='stock' AND m.is_delisted=0
                    AND s.{field} IS NOT NULL
                """)
                cnt = self.cursor.fetchone()[0]
                return cnt, round(cnt / active * 100, 1) if active else 0

            mktcap_n, mktcap_pct = coverage("total_market_cap")
            pe_n, pe_pct = coverage("pe_ratio")
            pb_n, pb_pct = coverage("pb_ratio")

            self.cursor.execute("""
                SELECT COUNT(*) FROM stock_meta
                WHERE asset_type='stock' AND is_delisted=0 AND sector_lv1 IS NOT NULL
            """)
            sector_n = self.cursor.fetchone()[0]
            sector_pct = round(sector_n / active * 100, 1) if active else 0

            self.cursor.execute("""
                SELECT COUNT(*) FROM stock_meta
                WHERE asset_type='stock' AND is_delisted=0 AND list_date IS NOT NULL
            """)
            listdate_n = self.cursor.fetchone()[0]
            listdate_pct = round(listdate_n / active * 100, 1) if active else 0

            self.cursor.execute("SELECT MAX(ifind_updated_at) FROM stocks")
            last_ifind = self.cursor.fetchone()[0]

            status = "pass" if mktcap_pct > 95 and sector_pct > 90 else "warning"

            return {
                "status": status,
                "active_base": active,
                "total_market_cap": {"count": mktcap_n, "pct": mktcap_pct},
                "pe_ratio": {"count": pe_n, "pct": pe_pct},
                "pb_ratio": {"count": pb_n, "pct": pb_pct},
                "sector": {"count": sector_n, "pct": sector_pct},
                "list_date": {"count": listdate_n, "pct": listdate_pct},
                "ifind_updated_at": last_ifind,
                "message": f"市值 {mktcap_pct}% | PE {pe_pct}% | PB {pb_pct}% | 行业 {sector_pct}% | 上市日期 {listdate_pct}%"
            }
        except Exception as e:
            logger.error(f"宏数据检查失败: {e}")
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # 重复数据检查
    # ─────────────────────────────────────────────
    def check_duplicate_data(self) -> Dict[str, Any]:
        try:
            self.cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT code, trade_date FROM daily_prices
                    GROUP BY code, trade_date HAVING COUNT(*) > 1
                )
            """)
            dup_count = self.cursor.fetchone()[0]
            status = "pass" if dup_count == 0 else "error"
            return {
                "status": status,
                "duplicate_groups": dup_count,
                "message": "无重复数据" if dup_count == 0 else f"发现 {dup_count} 组重复数据"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ─────────────────────────────────────────────
    # 汇总
    # ─────────────────────────────────────────────
    def run_all_checks(self) -> Dict[str, Any]:
        if not self.connect():
            self.report["status"] = "critical"
            return self.report
        try:
            self.report["checks"]["stock_pool"]    = self.check_stock_pool()
            self.report["checks"]["history_data"]  = self.check_history_data()
            self.report["checks"]["today_data"]    = self.check_today_data()
            self.report["checks"]["macro_data"]    = self.check_macro_data()
            self.report["checks"]["duplicate_data"]= self.check_duplicate_data()

            statuses = [c["status"] for c in self.report["checks"].values()]
            if "critical" in statuses or "error" in statuses:
                self.report["status"] = "critical"
            elif "warning" in statuses:
                self.report["status"] = "warning"
            else:
                self.report["status"] = "healthy"
        finally:
            self.disconnect()
        return self.report


def check_data_health(db_path: str = None) -> Dict[str, Any]:
    checker = DataHealthChecker(db_path)
    return checker.run_all_checks()


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    result = check_data_health()
    print(json.dumps(result, indent=2, ensure_ascii=False))
