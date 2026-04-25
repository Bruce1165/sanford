#!/usr/bin/env python3
from __future__ import annotations
"""
涨停试盘线筛选器 - Shi Pan Xian Screener
=========================================
策略逻辑：
  1. 低位横盘阶段，出现高量阳线（近期最大量）— 主力吸筹
  2. 随后出现涨停，成交量低于高量阳线    — 快速脱离成本区
  3. 回调过程中，股价在涨停板区间内波动
  4. 成交量逐步缩量到高量柱的 1/4 以下  — 抛压很轻
  5. 再次出现放量                        — 买入信号

修复记录（v2）：
  - 移除 SQLAlchemy / database.py 依赖，统一使用原生 sqlite3
  - 继承 StockFilter（base_screener）：复用市值过滤、ST/指数排除
  - 修复 check_data_availability 未定义导致必崩问题
  - 修复 get_stock_data() 忽略 db_path 参数，改为使用 self.db_path
  - 修复 self.current_date 在 __init__ 未初始化
  - 修复 000 开头深市主板股被错误排除
  - 修复 is_limit_up() ST 判断：df 增加 name 列
  - 下载链接端口 5003 → 8765
  - 市值过滤：流通市值 30 亿～1500 亿（来自 config.py）
"""

import os
import sys
import sqlite3
import logging
import argparse
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path

# ── 清除代理环境变量 ──────────────────────────────────────────────────────────
for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
    os.environ.pop(_k, None)

# ── 路径设置 ──────────────────────────────────────────────────────────────────
_SCRIPTS_DIR = Path(__file__).parent.parent / 'scripts'  # config.py 在 scripts/ 目录
sys.path.insert(0, str(_SCRIPTS_DIR))

from config import DB_PATH, FLASK_PORT  # FLASK_PORT from config, not hardcoded
from base_screener import BaseScreener, StockFilter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
class ShiPanXianScreener(BaseScreener):
    """涨停试盘线筛选器（v2，继承 BaseScreener + StockFilter 市值过滤）"""

    def __init__(
        self,
        db_path: str = None,
        consolidation_days: int = 20,
        high_volume_lookback: int = 30,
        max_consolidation_gain: float = 0.10,
        volume_shrink_threshold: float = 0.25,
        callback_max_days: int = 10,
        breakout_volume_ratio: float = 1.5,
        limit_up_search_days: int = 5,
        high_volume_peak_tolerance: float = 0.95,
        min_history_days: int = 50,
        min_days_after_high_volume: int = 3,
        main_board_limit_up_pct: float = 9.5,
        gem_star_limit_up_pct: float = 19.5,
        bse_limit_up_pct: float = 29.5,
        st_limit_up_pct: float = 4.5,
        check_data_update: bool = True,
        use_pool: bool = False,
    ):
        super().__init__(
            screener_name='shi_pan_xian',
            db_path=str(Path(db_path or DB_PATH).resolve()),
        )
        self.consolidation_days = consolidation_days
        self.high_volume_lookback = high_volume_lookback
        self.max_consolidation_gain = max_consolidation_gain
        self.volume_shrink_threshold = volume_shrink_threshold
        self.callback_max_days = callback_max_days
        self.breakout_volume_ratio = breakout_volume_ratio
        self.limit_up_search_days = max(1, int(limit_up_search_days))
        self.high_volume_peak_tolerance = float(high_volume_peak_tolerance)
        self.min_history_days = max(1, int(min_history_days))
        self.min_days_after_high_volume = max(1, int(min_days_after_high_volume))
        self.main_board_limit_up_pct = float(main_board_limit_up_pct)
        self.gem_star_limit_up_pct = float(gem_star_limit_up_pct)
        self.bse_limit_up_pct = float(bse_limit_up_pct)
        self.st_limit_up_pct = float(st_limit_up_pct)
        self.check_data_update = check_data_update
        self.use_pool = use_pool
        # StockFilter 是纯静态工具类，直接用类方法，无需实例化

    def get_screener_code(self) -> str:
        """Return this screener's code for DB lookup."""
        return 'shi_pan_xian'

    # ── 数据可用性检查 ────────────────────────────────────────────────────────

    def check_data_availability(self, check_date: str) -> bool:
        """检查数据库中是否有 check_date 当天或之前的数据"""
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            row = conn.execute(
                "SELECT MAX(trade_date) FROM daily_prices"
            ).fetchone()
            conn.close()
            if not row or not row[0]:
                return False
            latest = str(row[0])[:10]
            return latest >= check_date[:10]
        except Exception as exc:
            logger.warning("check_data_availability 失败: %s", exc)
            return False

    # ── 原生 sqlite3 数据读取 ─────────────────────────────────────────────────

    def get_stock_data(self, code: str, days: int = 150) -> pd.DataFrame | None:
        """读取股票近 N 天日线数据（含 name 列，供 is_limit_up ST 判断）"""
        sql = """
            SELECT
                dp.trade_date, dp.open, dp.high, dp.low, dp.close,
                dp.volume, dp.amount, dp.turnover, dp.pct_change,
                COALESCE(s.name, '') AS name
            FROM daily_prices dp
            LEFT JOIN stocks s ON s.code = dp.code
            WHERE dp.code = ?
              AND dp.trade_date <= ?
            ORDER BY dp.trade_date DESC
            LIMIT ?
        """
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            df = pd.read_sql_query(
                sql, conn, params=(code, self.current_date, days)
            )
            conn.close()
        except Exception as exc:
            logger.debug("get_stock_data(%s) 失败: %s", code, exc)
            return None

        if df.empty:
            return None

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        df['code'] = code
        return df

    def _get_all_stocks(self) -> list[dict]:
        """从 stocks 表读取全部股票，StockFilter 负责过滤"""
        sql = """
            SELECT code, name,
                   COALESCE(circulating_market_cap, 0) AS circulating_market_cap
            FROM stocks
            WHERE code IS NOT NULL
        """
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            rows = conn.execute(sql).fetchall()
            conn.close()
            return [
                {'code': r[0], 'name': r[1], 'circulating_market_cap': r[2]}
                for r in rows
            ]
        except Exception as exc:
            logger.error("_get_all_stocks 失败: %s", exc)
            return []

    # ── 策略逻辑 ──────────────────────────────────────────────────────────────

    def is_limit_up(self, row: pd.Series, prev_close: float) -> bool:
        """判断是否涨停（支持各板块涨幅规则）"""
        if prev_close <= 0:
            return False
        pct = row['pct_change']
        code = row['code']
        name = str(row.get('name', ''))

        if code.startswith(('300', '301', '688', '689')):
            return pct >= self.gem_star_limit_up_pct
        if code.startswith(('43', '83', '87', '88')):
            return pct >= self.bse_limit_up_pct
        if 'ST' in name or '*ST' in name:
            return pct >= self.st_limit_up_pct
        return pct >= self.main_board_limit_up_pct

    def is_low_consolidation(self, df: pd.DataFrame, high_volume_idx: int) -> bool:
        """判断高量阳线前是否为低位横盘"""
        if high_volume_idx < self.consolidation_days:
            return False
        period = df.iloc[high_volume_idx - self.consolidation_days:high_volume_idx]
        if len(period) < self.consolidation_days:
            return False
        gain = (period.iloc[-1]['close'] - period.iloc[0]['close']) / period.iloc[0]['close']
        return abs(gain) <= self.max_consolidation_gain

    def find_high_volume_yang_line(self, df: pd.DataFrame) -> int | None:
        """寻找低位横盘后的高量阳线，返回索引"""
        if len(df) < self.high_volume_lookback + self.callback_max_days:
            return None
        for i in range(len(df) - self.min_days_after_high_volume, self.consolidation_days, -1):
            row = df.iloc[i]
            if row['close'] <= row['open']:
                continue
            lookback = df.iloc[max(0, i - self.high_volume_lookback):i]
            if lookback.empty:
                continue
            if row['volume'] < lookback['volume'].max() * self.high_volume_peak_tolerance:
                continue
            if not self.is_low_consolidation(df, i):
                continue
            return i
        return None

    def check_limit_up_and_callback(
        self, df: pd.DataFrame, high_volume_idx: int
    ) -> dict | None:
        """检查涨停 + 缩量回调 + 再次放量"""
        if high_volume_idx >= len(df) - self.min_days_after_high_volume:
            return None

        hv_row = df.iloc[high_volume_idx]
        high_volume = hv_row['volume']

        # 寻找随后 N 天内的涨停（量低于高量阳线）
        limit_up_idx = None
        for i in range(
            high_volume_idx + 1,
            min(high_volume_idx + 1 + self.limit_up_search_days, len(df))
        ):
            row = df.iloc[i]
            prev_close = df.iloc[i - 1]['close']
            if self.is_limit_up(row, prev_close) and row['volume'] < high_volume:
                limit_up_idx = i
                break

        if limit_up_idx is None:
            return None

        lu_row = df.iloc[limit_up_idx]
        lu_high = lu_row['high']
        lu_low = lu_row['low']

        # 回调阶段：股价须在涨停板区间内；缩量至高量 1/4；再次放量
        shrink_found = False
        shrink_idx = None
        min_vol = float('inf')

        for i in range(limit_up_idx + 1,
                       min(limit_up_idx + 1 + self.callback_max_days, len(df))):
            day_row = df.iloc[i]

            if day_row['low'] < lu_low or day_row['high'] > lu_high:
                break

            if day_row['volume'] < min_vol:
                min_vol = day_row['volume']

            if day_row['volume'] < high_volume * self.volume_shrink_threshold:
                shrink_found = True
                shrink_idx = i

            if shrink_found and i > shrink_idx:
                shrink_period = df.iloc[shrink_idx:i]
                if not shrink_period.empty:
                    avg_shrink_vol = shrink_period['volume'].mean()
                    if day_row['volume'] > avg_shrink_vol * self.breakout_volume_ratio:
                        return self._build_result(
                            hv_row, lu_row, lu_high, lu_low,
                            i - limit_up_idx, shrink_idx, min_vol,
                            day_row, high_volume,
                        )

        if shrink_found:
            return self._build_result(
                hv_row, lu_row, lu_high, lu_low,
                len(df) - limit_up_idx - 1, shrink_idx, min_vol,
                None, high_volume,
            )
        return None

    @staticmethod
    def _build_result(
        hv_row, lu_row, lu_high, lu_low,
        callback_days, shrink_idx, min_vol,
        breakout_row, high_volume,
    ) -> dict:
        return {
            'high_volume_date':  hv_row['trade_date'].strftime('%Y-%m-%d'),
            'high_volume_price': hv_row['close'],
            'high_volume':       hv_row['volume'],
            'limit_up_date':     lu_row['trade_date'].strftime('%Y-%m-%d'),
            'limit_up_price':    lu_row['close'],
            'limit_up_high':     lu_high,
            'limit_up_low':      lu_low,
            'limit_up_volume':   lu_row['volume'],
            'callback_days':     callback_days,
            'shrink_volume_found': True,
            'shrink_volume_idx': shrink_idx,
            'min_volume_during_callback': min_vol,
            'volume_shrink_ratio': min_vol / high_volume if high_volume else 0,
            'breakout_date':  breakout_row['trade_date'].strftime('%Y-%m-%d') if breakout_row is not None else None,
            'breakout_price': breakout_row['close']  if breakout_row is not None else None,
            'breakout_volume':breakout_row['volume'] if breakout_row is not None else None,
        }

    # ── 单股检查 ──────────────────────────────────────────────────────────────

    def screen_stock(self, code: str, name: str) -> dict | None:
        """筛选单只股票，返回结果 dict 或 None"""
        df = self.get_stock_data(code)
        if df is None or len(df) < self.min_history_days:
            return None

        hv_idx = self.find_high_volume_yang_line(df)
        if hv_idx is None:
            return None

        result = self.check_limit_up_and_callback(df, hv_idx)
        if result is None:
            return None

        latest = df.iloc[-1]
        return {
            'code': code,
            'name': name,
            **result,
            'current_price':       latest['close'],
            'current_change':      latest['pct_change'],
            'days_since_limit_up': len(df) - 1 - hv_idx,
        }

    def check_single_stock(self, code: str, date_str: str = None) -> dict:
        """检查单只股票（Dashboard API 兼容接口）"""
        if date_str:
            self.current_date = date_str

        # 读取股票名称和市值，再过滤
        info = self._get_stock_info(code)
        name = info.get('name', '')
        cap  = info['circulating_market_cap']

        reason = StockFilter.get_exclusion_reason(
            code, name, is_delisted=False, circulating_market_cap=cap
        )
        if reason:
            return {
                'match': False, 'code': code, 'name': name,
                'date': self.current_date,
                'reasons': [f'股票被过滤: {reason}'],
                'details': {},
            }

        df = self.get_stock_data(code)
        if df is None or len(df) < self.min_history_days:
            return {
                'match': False, 'code': code, 'name': name,
                'date': self.current_date,
                'reasons': [f'无法获取足够的历史数据（需要至少 {self.min_history_days} 天）'],
                'details': {},
            }

        result = self.screen_stock(code, name)
        if result is None:
            return {
                'match': False, 'code': code, 'name': name,
                'date': self.current_date,
                'reasons': ['未找到涨停试盘线形态（需满足：高量阳线→涨停→缩量回调→再次放量）'],
                'details': {},
            }

        return {
            'match': True, 'code': code, 'name': name,
            'date': self.current_date,
            'reasons': [],
            'details': result,
        }

    def _get_stock_info(self, code: str) -> dict:
        """返回 {name, circulating_market_cap}，一次查询同时取得过滤所需字段。"""
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=10)
            row = conn.execute(
                "SELECT name, circulating_market_cap FROM stocks WHERE code = ?",
                (code,),
            ).fetchone()
            conn.close()
            if row:
                return {'name': row[0] or '', 'circulating_market_cap': row[1]}
        except Exception:
            pass
        return {'name': '', 'circulating_market_cap': None}

    # 保留向后兼容别名
    def _get_stock_name(self, code: str) -> str:
        return self._get_stock_info(code)['name']

    # ── 主筛选流程 ────────────────────────────────────────────────────────────

    def run_screening(self, date: str = None) -> list[dict]:
        """运行全市场筛选"""
        if date:
            self.current_date = date


        logger.info("=" * 60)
        logger.info("涨停试盘线筛选  date=%s", self.current_date)
        logger.info(
            "参数: 横盘%d天, 缩量阈值%.2f, 最大回调%d天",
            self.consolidation_days, self.volume_shrink_threshold, self.callback_max_days,
        )
        logger.info("=" * 60)

        all_stocks = self._get_all_stocks()
        # StockFilter 统一过滤：市值 + ST + 指数 + 退市
        valid_stocks = [
            s for s in all_stocks
            if not StockFilter.get_exclusion_reason(
                s['code'],
                s['name'] or '',
                is_delisted=False,
                circulating_market_cap=s['circulating_market_cap'],
            )
        ]
        logger.info("全市场 %d 只 → 过滤后 %d 只", len(all_stocks), len(valid_stocks))

        results = []
        for idx, stock in enumerate(valid_stocks, 1):
            if idx % 500 == 0:
                logger.info("已检查 %d / %d，找到 %d 只", idx, len(valid_stocks), len(results))
            result = self.screen_stock(stock['code'], stock['name'])
            if result:
                bo = result['breakout_date'] or '未突破'
                logger.info(
                    "✓ %s %s  高量%s 涨停%s 缩量%.1f%%  %s",
                    result['code'], result['name'],
                    result['high_volume_date'], result['limit_up_date'],
                    result['volume_shrink_ratio'] * 100, bo,
                )
                results.append(result)

        logger.info("=" * 60)
        logger.info("筛选完成  检查: %d  命中: %d", len(valid_stocks), len(results))
        logger.info("=" * 60)
        return results

    # ── 保存结果 ──────────────────────────────────────────────────────────────

    def save_results(self, results: list[dict], filename: str = None) -> str | None:
        """保存结果到 Excel"""
        if not results:
            logger.warning("No results to save")
            return None

        if filename is None:
            out_dir = Path(str(self._db_path)).parent.parent / 'data' / 'screeners' / 'shi_pan_xian'
            out_dir.mkdir(parents=True, exist_ok=True)
            filename = str(out_dir / f"{self.current_date}.xlsx")

        df = pd.DataFrame(results)
        col_order = [
            'code', 'name', 'current_price', 'current_change',
            'high_volume_date', 'high_volume_price', 'high_volume',
            'limit_up_date', 'limit_up_price', 'limit_up_high', 'limit_up_low', 'limit_up_volume',
            'callback_days', 'shrink_volume_found', 'min_volume_during_callback', 'volume_shrink_ratio',
            'breakout_date', 'breakout_price', 'breakout_volume',
            'days_since_limit_up',
        ]
        existing_cols = [c for c in col_order if c in df.columns]
        df = df[existing_cols]
        df.columns = [
            '股票代码', '股票名称', '当前价格', '当前涨幅%',
            '高量日期', '高量收盘价', '高量成交量',
            '涨停日期', '涨停收盘价', '涨停最高价', '涨停最低价', '涨停成交量',
            '回调天数', '是否缩量', '回调期最小量', '缩量比例',
            '突破日期', '突破价格', '突破成交量',
            '距高量天数',
        ][:len(existing_cols)]

        df.to_excel(filename, index=False, engine='xlsxwriter')
        logger.info("结果已保存: %s", filename)
        return filename


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='涨停试盘线筛选器')
    parser.add_argument('--date',                type=str,   help='分析日期 YYYY-MM-DD，默认今天')
    parser.add_argument('--consolidation-days',  type=int,   default=20,   help='低位横盘判断天数')
    parser.add_argument('--high-volume-lookback',type=int,   default=30,   help='高量阳线回看周期')
    parser.add_argument('--max-consolidation-gain', type=float, default=0.10, help='横盘期最大涨幅')
    parser.add_argument('--shrink-threshold',    type=float, default=0.25, help='缩量阈值（相对高量，默认0.25）')
    parser.add_argument('--callback-max-days',   type=int,   default=10,   help='最大回调天数')
    parser.add_argument('--breakout-ratio',      type=float, default=1.5,  help='再次放量倍数')
    parser.add_argument('--output',              type=str,   help='输出文件名')
    parser.add_argument('--no-check',            action='store_true', help='跳过数据可用性检查')
    args = parser.parse_args()

    screener = ShiPanXianScreener(
        consolidation_days=args.consolidation_days,
        high_volume_lookback=args.high_volume_lookback,
        max_consolidation_gain=args.max_consolidation_gain,
        volume_shrink_threshold=args.shrink_threshold,
        callback_max_days=args.callback_max_days,
        breakout_volume_ratio=args.breakout_ratio,
        check_data_update=not args.no_check,
    )

    run_date = args.date or datetime.now().strftime('%Y-%m-%d')
    results = screener.run_screening(run_date)

    if results:
        screener.save_results(results, args.output)
        print("\n" + "=" * 80)
        print(f"筛选结果（{run_date}）：共 {len(results)} 只")
        print("=" * 80)
        for r in results:
            bo = f"突破于{r['breakout_date']}@{r['breakout_price']:.2f}" \
                 if r.get('breakout_date') else "未突破"
            print(
                f"  {r['code']} {r['name']}  "
                f"高量{r['high_volume_date']}  涨停{r['limit_up_date']}  "
                f"缩量至{r['volume_shrink_ratio']:.1%}  {bo}"
            )
        print(f"\n{'='*60}")
        print(f"📥 下载链接（Dashboard）:")
        print(f"  Excel: http://localhost:{FLASK_PORT}/api/download/shi_pan_xian_screener/{run_date}")
        print(f"  CSV:   http://localhost:{FLASK_PORT}/api/download/csv/shi_pan_xian_screener/{run_date}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
