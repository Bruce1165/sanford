#!/usr/bin/env python3
from __future__ import annotations
"""
每日热冷股筛选器 (V2 – 重构为继承 BaseScreener)

同时筛选：
- 热股：涨幅≥5%，成交额≥10亿
- 冷股：跌幅≤-5%，成交额≥10亿

变更记录
--------
* [BUG-FIX] 移除 SQLAlchemy / database.py 依赖，改用 sqlite3 + BaseScreener
* [BUG-FIX] 硬编码端口 5003 → FLASK_PORT（来自 config.py）
* [BUG-FIX] 硬编码 DB_PATH / OUTPUT_DIR → BaseScreener._db_path / DATA_DIR
* [IMPROVE] 继承 BaseScreener，保留涨跌停阈值、热冷判断、多周期收益计算逻辑不变
* [IMPROVE] 新增 _load_stock_extras() 缓存 industry / list_date，避免多次查库
"""

# 清除代理环境变量，避免网络请求失败
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import sqlite3
import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from base_screener import BaseScreener
from config import DATA_DIR, FLASK_PORT

logger = logging.getLogger(__name__)

class DailyHotColdScreener(BaseScreener):
    """每日热冷股筛选器 V2"""

    screener_name = 'daily_hot_cold'

    def __init__(self,
                 limit_up_main: float = 9.9,
                 limit_up_gem_star: float = 19.9,
                 limit_down_main: float = -9.9,
                 limit_down_gem_star: float = -19.9,
                 new_stock_days: int = 60,
                 min_amount: float = 10.0,
                 hot_pct_threshold: float = 5.0,
                 cold_pct_threshold: float = -5.0,
                 limit_stats_days: int = 20,
                 high_turnover_threshold: float = 15.0,
                 volume_surge_turnover: float = 5.0,
                 breakout_threshold: float = 0.99,
                 breakdown_threshold: float = 1.01,
                 min_history_days: int = 5,
                 db_path: Optional[str] = None):
        super().__init__()
        self.screener_name = 'daily_hot_cold'
        # { code: {'industry': str, 'list_date': str|None} }
        self._stock_extras: Dict[str, Dict] = {}

        # 参数
        self.limit_up_main = limit_up_main
        self.limit_up_gem_star = limit_up_gem_star
        self.limit_down_main = limit_down_main
        self.limit_down_gem_star = limit_down_gem_star
        self.new_stock_days = new_stock_days
        self.min_amount = min_amount * 1e8  # 转换为元
        self.hot_pct_threshold = hot_pct_threshold
        self.cold_pct_threshold = cold_pct_threshold
        self.limit_stats_days = limit_stats_days
        self.high_turnover_threshold = high_turnover_threshold
        self.volume_surge_turnover = volume_surge_turnover
        self.breakout_threshold = breakout_threshold
        self.breakdown_threshold = breakdown_threshold
        self.min_history_days = max(1, int(min_history_days))

    @classmethod
    def get_parameter_schema(cls) -> Dict:
        """返回筛选器的参数Schema"""
        return {
            'LIMIT_UP_MAIN': {
                'type': 'float',
                'default': 9.9,
                'min': 9.0,
                'max': 10.0,
                'step': 0.1,
                'display_name': '主板涨停阈值',
                'description': '主板股票涨停判断阈值（%）',
                'group': '涨跌停阈值'
            },
            'LIMIT_UP_GEM_STAR': {
                'type': 'float',
                'default': 19.9,
                'min': 18.0,
                'max': 20.0,
                'step': 0.1,
                'display_name': '创业板/科创板涨停阈值',
                'description': '创业板和科创板涨停判断阈值（%）',
                'group': '涨跌停阈值'
            },
            'LIMIT_DOWN_MAIN': {
                'type': 'float',
                'default': -9.9,
                'min': -10.0,
                'max': -9.0,
                'step': 0.1,
                'display_name': '主板跌停阈值',
                'description': '主板股票跌停判断阈值（%）',
                'group': '涨跌停阈值'
            },
            'LIMIT_DOWN_GEM_STAR': {
                'type': 'float',
                'default': -19.9,
                'min': -20.0,
                'max': -18.0,
                'step': 0.1,
                'display_name': '创业板/科创板跌停阈值',
                'description': '创业板和科创板跌停判断阈值（%）',
                'group': '涨跌停阈值'
            },
            'NEW_STOCK_DAYS': {
                'type': 'int',
                'default': 60,
                'min': 30,
                'max': 120,
                'display_name': '新股过滤天数',
                'description': '上市不足此天数的股票将被过滤',
                'group': '基础设置'
            },
            'MIN_AMOUNT': {
                'type': 'float',
                'default': 10.0,
                'min': 5.0,
                'max': 50.0,
                'step': 1.0,
                'display_name': '最小成交额',
                'description': '筛选股票的最小成交额（亿元）',
                'group': '筛选条件'
            },
            'HOT_PCT_THRESHOLD': {
                'type': 'float',
                'default': 5.0,
                'min': 3.0,
                'max': 10.0,
                'step': 0.5,
                'display_name': '热股涨幅阈值',
                'description': '判断为热股的最小涨幅百分比',
                'group': '筛选条件'
            },
            'COLD_PCT_THRESHOLD': {
                'type': 'float',
                'default': -5.0,
                'min': -10.0,
                'max': -3.0,
                'step': 0.5,
                'display_name': '冷股跌幅阈值',
                'description': '判断为冷股的最大跌幅百分比',
                'group': '筛选条件'
            },
            'LIMIT_STATS_DAYS': {
                'type': 'int',
                'default': 20,
                'min': 10,
                'max': 60,
                'display_name': '涨跌停统计天数',
                'description': '统计近N日的涨跌停次数',
                'group': '统计设置'
            },
            'HIGH_TURNOVER_THRESHOLD': {
                'type': 'float',
                'default': 15.0,
                'min': 10.0,
                'max': 30.0,
                'step': 1.0,
                'display_name': '高换手阈值',
                'description': '判断为高换手的最小换手率百分比',
                'group': '异动判断'
            },
            'VOLUME_SURGE_TURNOVER': {
                'type': 'float',
                'default': 5.0,
                'min': 3.0,
                'max': 10.0,
                'step': 0.5,
                'display_name': '放量换手阈值',
                'description': '判断为放量的最小换手率百分比',
                'group': '异动判断'
            },
            'BREAKOUT_THRESHOLD': {
                'type': 'float',
                'default': 0.99,
                'min': 0.95,
                'max': 0.999,
                'step': 0.005,
                'display_name': '突破阈值',
                'description': '突破近N日高点的判断比例（0.99=99%）',
                'group': '异动判断'
            },
            'BREAKDOWN_THRESHOLD': {
                'type': 'float',
                'default': 1.01,
                'min': 1.001,
                'max': 1.05,
                'step': 0.005,
                'display_name': '破位阈值',
                'description': '跌破近N日低点的判断比例（1.01=101%）',
                'group': '异动判断'
            },
            'MIN_HISTORY_DAYS': {
                'type': 'int',
                'default': 5,
                'min': 1,
                'max': 120,
                'display_name': '最小历史天数',
                'description': '计算统计项前要求的最少历史数据天数',
                'group': '基础设置'
            }
        }

    def get_limit_up_threshold(self, board: str) -> float:
        """获取指定板块的涨停阈值"""
        if board in ('创业板', '科创板'):
            return self.limit_up_gem_star
        return self.limit_up_main

    def get_limit_down_threshold(self, board: str) -> float:
        """获取指定板块的跌停阈值"""
        if board in ('创业板', '科创板'):
            return self.limit_down_gem_star
        return self.limit_down_main

    # ─── 辅助：板块判断 ────────────────────────────────────────────────────────

    @staticmethod
    def get_stock_board(code: str) -> str:
        """判断股票所属板块"""
        if code.startswith('68'):
            return '科创板'
        elif code.startswith('30'):
            return '创业板'
        elif code.startswith('00') or code.startswith('60'):
            return '主板'
        else:
            return '其他'

    # ─── 辅助：从 DB 加载 industry / list_date ─────────────────────────────────

    def _load_stock_extras(self) -> None:
        """查询 stocks 表，缓存 industry / list_date 字段。"""
        try:
            with self.get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT code,
                           COALESCE(industry, '') AS industry,
                           COALESCE(list_date,  '') AS list_date
                    FROM stocks
                    """
                ).fetchall()
            self._stock_extras = {
                r["code"]: {"industry": r["industry"], "list_date": r["list_date"]}
                for r in rows
            }
        except Exception as exc:
            logger.warning("_load_stock_extras 失败: %s", exc)
            self._stock_extras = {}

    # ─── 指标计算 ──────────────────────────────────────────────────────────────

    def calculate_limit_up_stats(self, df: pd.DataFrame, code: str) -> Dict:
        """计算近N日涨跌停次数"""
        if df is None or len(df) < self.min_history_days:
            return {'total_limit_up': 0, 'total_limit_down': 0,
                    'board': self.get_stock_board(code)}

        board = self.get_stock_board(code)
        threshold_up   = self.get_limit_up_threshold(board)
        threshold_down = self.get_limit_down_threshold(board)

        recent_df = df.tail(self.limit_stats_days)
        total_limit_up   = int((recent_df['pct_change'] >= threshold_up).sum())
        total_limit_down = int((recent_df['pct_change'] <= threshold_down).sum())

        return {
            'total_limit_up':   total_limit_up,
            'total_limit_down': total_limit_down,
            'board':            board,
        }

    def calculate_returns(self, df: pd.DataFrame) -> Dict:
        """计算多周期收益率"""
        if df is None or len(df) < self.min_history_days:
            return {'return_5d': 0, 'return_10d': 0, 'return_20d': 0, 'return_60d': 0}

        latest_close = df.iloc[-1]['close']

        def calc_return(days: int) -> float:
            if len(df) < days + 1:
                return 0.0
            past_close = df.iloc[-(days + 1)]['close']
            if past_close == 0:
                return 0.0
            return round((latest_close - past_close) / past_close * 100, 2)

        return {
            'return_5d':  calc_return(5),
            'return_10d': calc_return(10),
            'return_20d': calc_return(20),
            'return_60d': calc_return(60),
        }

    def detect_anomaly_type(self, row: Dict, df: Optional[pd.DataFrame],
                            is_hot: bool = True) -> str:
        """检测异动类型"""
        anomaly_types = []
        pct_change = row.get('pct_change', 0) or 0
        code = row.get('code', '')
        board = self.get_stock_board(code)

        if is_hot:
            if row.get('turnover', 0) > self.volume_surge_turnover and pct_change > self.hot_pct_threshold:
                anomaly_types.append('放量大涨')
            threshold = self.get_limit_up_threshold(board)
            if pct_change >= threshold:
                anomaly_types.append('涨停')
            if df is not None and len(df) >= self.limit_stats_days:
                high_nd = df.tail(self.limit_stats_days)['high'].max()
                if row.get('high', 0) >= high_nd * self.breakout_threshold:
                    anomaly_types.append('突破')
            if row.get('turnover', 0) > self.high_turnover_threshold:
                anomaly_types.append('高换手')
        else:
            if row.get('turnover', 0) > self.volume_surge_turnover and pct_change < self.cold_pct_threshold:
                anomaly_types.append('放量大跌')
            threshold = self.get_limit_down_threshold(board)
            if pct_change <= threshold:
                anomaly_types.append('跌停')
            if df is not None and len(df) >= self.limit_stats_days:
                low_nd = df.tail(self.limit_stats_days)['low'].min()
                if row.get('low', 0) <= low_nd * self.breakdown_threshold:
                    anomaly_types.append('破位')
            if row.get('turnover', 0) > self.high_turnover_threshold:
                anomaly_types.append('高换手')

        return ' + '.join(anomaly_types) if anomaly_types else ('异动' if is_hot else '异动下跌')

    # ─── BaseScreener 抽象方法实现 ─────────────────────────────────────────────

    def screen_stock(self, code: str, name: str) -> Optional[Dict]:
        """
        实现 BaseScreener.screen_stock 抽象方法。
        返回含 _type='hot'|'cold' 的 dict，供 run_screening 分类；
        不符合条件返回 None。
        """
        # 新股过滤
        extra = self._stock_extras.get(code, {})
        list_date_str = extra.get('list_date', '')
        if list_date_str:
            try:
                listing = datetime.strptime(list_date_str[:10], '%Y-%m-%d')
                if (datetime.now() - listing).days < self.new_stock_days:
                    return None
            except Exception:
                pass

        # 获取当日行情数据
        df = self.get_stock_data(code, days=max(self.limit_stats_days, self.new_stock_days) + 10)
        if df is None or df.empty:
            return None

        # 只取截止 current_date 的数据
        df['date_str'] = df['trade_date'].dt.strftime('%Y-%m-%d')
        df_up_to_date = df[df['date_str'] <= self.current_date].copy()

        if df_up_to_date.empty:
            return None

        # 找 current_date 当天的行
        date_row = df_up_to_date[df_up_to_date['date_str'] == self.current_date]
        if date_row.empty:
            return None

        latest = date_row.iloc[0]
        pct_change = float(latest.get('pct_change', 0) or 0)
        amount     = float(latest.get('amount', 0) or 0)

        # 成交额必须 >= 最小成交额
        if amount < self.min_amount:
            return None

        # 判断热/冷
        is_hot  = pct_change >= self.hot_pct_threshold
        is_cold = pct_change <= self.cold_pct_threshold
        if not is_hot and not is_cold:
            return None

        # 指标计算
        limit_stats  = self.calculate_limit_up_stats(df_up_to_date, code)
        returns      = self.calculate_returns(df_up_to_date)
        anomaly_type = self.detect_anomaly_type({
            'code':     code,
            'turnover': latest.get('turnover', 0),
            'pct_change': pct_change,
            'high':     latest.get('high', 0),
            'low':      latest.get('low', 0),
        }, df_up_to_date, is_hot=is_hot)

        return {
            'code':         code,
            'name':         name,
            'board':        limit_stats['board'],
            'industry':     extra.get('industry', '-') or '-',
            'close':        round(float(latest['close']), 2),
            'pct_change':   round(pct_change, 2),
            'amount':       round(amount / 1e8, 2),   # 亿元
            'turnover':     round(float(latest.get('turnover', 0) or 0), 2),
            'total_market_cap':  '-',
            'circulating_cap':   '-',
            'pe': '-',
            'pb': '-',
            'total_limit_up':    limit_stats['total_limit_up'],
            'total_limit_down':  limit_stats['total_limit_down'],
            'return_5d':   returns['return_5d'],
            'return_10d':  returns['return_10d'],
            'return_20d':  returns['return_20d'],
            'return_60d':  returns['return_60d'],
            'listing_date': extra.get('list_date', '-') or '-',
            'anomaly_type': anomaly_type,
            '_type': 'hot' if is_hot else 'cold',
        }

    # ─── 筛选入口 ──────────────────────────────────────────────────────────────

    def run_screening(self, trade_date: Optional[str] = None, no_check: bool = False) -> Dict:
        """
        运行筛选，返回 {'hot': [...], 'cold': [...]}。
        """
        if trade_date:
            self.current_date = trade_date
        else:
            # 回落到 DB 最新日期
            _ = self.current_date

        # 检查数据是否存在
        if not no_check:
            try:
                with self.get_conn() as conn:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM daily_prices WHERE trade_date = ?",
                        (self.current_date,)
                    ).fetchone()
                if not row or row[0] == 0:
                    logger.warning("⚠️  无可用数据 (%s) - 市场尚未收盘或数据未下载", self.current_date)
                    return {'hot': [], 'cold': []}
            except Exception as exc:
                logger.error("check_data_availability 失败: %s", exc)

        logger.info("=" * 60)
        logger.info("每日热冷股筛选器 V2")
        logger.info("日期: %s", self.current_date)
        logger.info("=" * 60)

        # 预加载 industry / list_date
        self._load_stock_extras()

        # 通过 StockFilter 获取过滤后股票列表
        stocks = self.get_all_stocks()
        logger.info("Total stocks (after StockFilter): %d", len(stocks))

        hot_results: List[Dict] = []
        cold_results: List[Dict] = []

        for i, stock in enumerate(stocks):
            if (i + 1) % 500 == 0:
                logger.info("[PROGRESS] Checked %d stocks (hot/cold): %d (%d/%d)",
                            i + 1, len(hot_results), len(cold_results))
            try:
                result = self.screen_stock(stock.code, stock.name)
                if result is None:
                    continue
                if result['_type'] == 'hot':
                    hot_results.append(result)
                    logger.info("✓ Hot:  %s %s - 涨幅%.1f%%",
                                stock.code, stock.name, result['pct_change'])
                else:
                    cold_results.append(result)
                    logger.info("✓ Cold: %s %s - 跌幅%.1f%%",
                                stock.code, stock.name, result['pct_change'])
            except Exception as exc:
                logger.error("Error screening %s: %s", stock.code, exc)

        logger.info("\n%s", "=" * 60)
        logger.info("筛选完成!")
        logger.info("热股: %d 只  冷股: %d 只", len(hot_results), len(cold_results))
        logger.info("=" * 60)

        return {'hot': hot_results, 'cold': cold_results}

    # ─── 保存结果 ──────────────────────────────────────────────────────────────

    def save_results(self, results: Dict, trade_date: Optional[str] = None) -> Optional[str]:
        """保存结果到 Excel（两个 Sheet）"""
        if not results or (not results.get('hot') and not results.get('cold')):
            logger.warning("没有结果需要保存")
            return None

        if trade_date is None:
            trade_date = self.current_date

        output_dir = Path(DATA_DIR) / "screeners" / "daily_hot_cold"
        output_dir.mkdir(parents=True, exist_ok=True)
        excel_path = output_dir / f"{trade_date}.xlsx"

        columns = [
            'code', 'name', 'board', 'industry',
            'close', 'pct_change', 'amount', 'turnover',
            'total_market_cap', 'circulating_cap', 'pe', 'pb',
            'total_limit_up', 'total_limit_down',
            'return_5d', 'return_10d', 'return_20d', 'return_60d',
            'listing_date', 'anomaly_type',
        ]
        column_names = [
            '代码', '名称', '板块', '行业',
            '收盘价', '涨幅%', '成交额(亿)', '换手率%',
            '总市值(亿)', '流通市值(亿)', '市盈率', '市净率',
            '累计涨停', '累计跌停',
            '5日涨幅%', '10日涨幅%', '20日涨幅%', '60日涨幅%',
            '上市日期', '异动类型',
        ]

        try:
            with pd.ExcelWriter(str(excel_path), engine='xlsxwriter') as writer:
                if results.get('hot'):
                    df_hot = pd.DataFrame(results['hot'])
                    avail = [c for c in columns if c in df_hot.columns]
                    df_hot = df_hot[avail].copy()
                    df_hot.columns = [column_names[columns.index(c)] for c in avail]
                    df_hot = df_hot.sort_values(['涨幅%', '成交额(亿)'], ascending=[False, False])
                    df_hot.to_excel(writer, sheet_name='热股', index=False)
                    logger.info("热股已保存: %d 只", len(results['hot']))

                if results.get('cold'):
                    df_cold = pd.DataFrame(results['cold'])
                    avail = [c for c in columns if c in df_cold.columns]
                    df_cold = df_cold[avail].copy()
                    df_cold.columns = [column_names[columns.index(c)] for c in avail]
                    df_cold = df_cold.sort_values(['涨幅%', '成交额(亿)'], ascending=[True, False])
                    df_cold.to_excel(writer, sheet_name='冷股', index=False)
                    logger.info("冷股已保存: %d 只", len(results['cold']))

            logger.info("Excel结果已保存: %s", excel_path)
        except Exception as exc:
            logger.warning("xlsxwriter 失败，改用 openpyxl: %s", exc)
            with pd.ExcelWriter(str(excel_path)) as writer:
                if results.get('hot'):
                    df_hot = pd.DataFrame(results['hot'])
                    avail = [c for c in columns if c in df_hot.columns]
                    df_hot[avail].to_excel(writer, sheet_name='热股', index=False)
                if results.get('cold'):
                    df_cold = pd.DataFrame(results['cold'])
                    avail = [c for c in columns if c in df_cold.columns]
                    df_cold[avail].to_excel(writer, sheet_name='冷股', index=False)

        return str(excel_path)


def main():
    """主函数"""
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description='每日热冷股筛选器')
    parser.add_argument('--date', type=str, help='交易日期 (YYYY-MM-DD)')
    parser.add_argument('--no-check', action='store_true', help='跳过数据检查（兼容参数）')
    parser.add_argument('--db-path', type=str, default='', help='数据库路径（默认 config.DATA_DIR）')
    args = parser.parse_args()

    screener = DailyHotColdScreener(db_path=args.db_path if args.db_path else None)
    results = screener.run_screening(args.date, no_check=args.no_check)

    if results.get('hot') or results.get('cold'):
        output_path = screener.save_results(results, args.date)

        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)

        if results.get('hot'):
            print(f"\n【热股】共 {len(results['hot'])} 只:")
            for r in results['hot'][:5]:
                print(f"  {r['code']} {r['name']} ({r['board']}): "
                      f"涨幅{r['pct_change']:.1f}%, 成交额{r['amount']:.1f}亿")
            if len(results['hot']) > 5:
                print(f"  ... 共 {len(results['hot'])} 只")

        if results.get('cold'):
            print(f"\n【冷股】共 {len(results['cold'])} 只:")
            for r in results['cold'][:5]:
                print(f"  {r['code']} {r['name']} ({r['board']}): "
                      f"跌幅{r['pct_change']:.1f}%, 成交额{r['amount']:.1f}亿")
            if len(results['cold']) > 5:
                print(f"  ... 共 {len(results['cold'])} 只")

        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'daily_hot_cold_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:{FLASK_PORT}/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:{FLASK_PORT}/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()
