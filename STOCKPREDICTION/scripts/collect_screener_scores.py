"""
collect_screener_scores.py – 从 NeoTrade2 筛选器收集特征

运行 NeoTrade2 的各个筛选器，将结果作为特征保存到本地数据库。
这些筛选器结果将作为分类特征输入到预测模型中。
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    NEOTRADE_DB_PATH,
    NEOTRADE_SCREENERS_DIR,
    SCREENER_SCORES_DB,
    SCREENER_FEATURES,
)
from models.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScreenerFeatureCollector:
    """筛选器特征收集器"""

    def __init__(self, source_db: Path = NEOTRADE_DB_PATH,
                 screeners_dir: Path = NEOTRADE_SCREENERS_DIR,
                 target_db: Path = SCREENER_SCORES_DB):
        self.source_db = source_db
        self.screeners_dir = screeners_dir
        self.target_db = target_db
        self._init_target_db()
        self._load_screeners()

    def _init_target_db(self):
        """初始化目标数据库"""
        init_db(self.target_db)
        logger.info(f"目标数据库已初始化: {self.target_db}")

    def _load_screeners(self):
        """动态加载筛选器模块"""
        # 添加 screeners 目录到 Python 路径
        sys.path.insert(0, str(self.screeners_dir))

        self.screener_classes = {}
        self.available_screeners = []

        for screener_name in SCREENER_FEATURES:
            try:
                # 尝试导入筛选器
                module = __import__(screener_name)

                # 获取筛选器类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        hasattr(attr, 'screen_stock') and
                        hasattr(attr, 'screener_name')):
                        self.screener_classes[screener_name] = attr
                        self.available_screeners.append(screener_name)
                        logger.info(f"加载筛选器: {screener_name} -> {attr_name}")
                        break
            except Exception as e:
                logger.warning(f"无法加载筛选器 {screener_name}: {e}")

        logger.info(f"成功加载 {len(self.available_screeners)} 个筛选器")

    def get_all_stocks(self) -> List[tuple]:
        """获取所有有效股票列表"""
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, name
                FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND name NOT LIKE '%ST%'
                  AND name NOT LIKE '%*ST%'
                  AND name NOT LIKE '%退%'
                  AND name NOT LIKE '%指数%'
                  AND name NOT LIKE '%ETF%'
                  AND name NOT LIKE '%LOF%'
                  AND code NOT LIKE '43%'
                  AND code NOT LIKE '83%'
                  AND code NOT LIKE '87%'
                  AND code NOT LIKE '88%'
                  AND code NOT LIKE '399%'
                ORDER BY code
            """).fetchall()
        return rows

    def run_screener(self, screener_name: str, date_str: str) -> Dict[str, Dict]:
        """
        运行单个筛选器

        Returns:
            Dict: {code: {'hit': bool, 'score': float, 'reason': str, ...}}
        """
        if screener_name not in self.screener_classes:
            logger.warning(f"筛选器 {screener_name} 不可用")
            return {}

        ScreenerClass = self.screener_classes[screener_name]
        results = {}

        try:
            # 创建筛选器实例
            screener = ScreenerClass(db_path=str(self.source_db))
            screener.current_date = date_str

            # 获取所有股票
            stocks = self.get_all_stocks()

            logger.info(f"运行筛选器 {screener_name}，日期: {date_str}")

            # 逐个股票筛选
            for code, name in stocks:
                try:
                    result = screener.screen_stock(code, name)

                    if result is not None:
                        results[code] = {
                            'hit': True,
                            'score': result.get('score', 1.0),
                            'reason': result.get('reason', ''),
                            'extra': {k: v for k, v in result.items()
                                     if k not in ['code', 'name', 'score', 'reason']}
                        }
                    else:
                        results[code] = {
                            'hit': False,
                            'score': 0.0,
                            'reason': '',
                            'extra': {}
                        }
                except Exception as e:
                    logger.debug(f"筛选器 {screener_name} 处理 {code} 失败: {e}")
                    results[code] = {
                        'hit': False,
                        'score': 0.0,
                        'reason': f"Error: {str(e)}",
                        'extra': {}
                    }

        except Exception as e:
            logger.error(f"运行筛选器 {screener_name} 失败: {e}")
            return {}

        return results

    def save_screener_results(self, screener_name: str, date_str: str,
                              results: Dict[str, Dict]):
        """保存筛选器结果到数据库"""
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            for code, result in results.items():
                conn.execute("""
                    INSERT OR REPLACE INTO screener_features
                    (code, trade_date, screener_name, hit, score, reason, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    date_str,
                    screener_name,
                    result['hit'],
                    result['score'],
                    result['reason'],
                    json.dumps(result['extra'], ensure_ascii=False)
                ))
            conn.commit()

        hit_count = sum(1 for r in results.values() if r['hit'])
        logger.info(f"  {screener_name}: 命中 {hit_count}/{len(results)}")

    def collect_for_date(self, date_str: str, screeners: Optional[List[str]] = None):
        """为指定日期收集所有筛选器特征"""
        if screeners is None:
            screeners = self.available_screeners

        logger.info(f"开始收集日期 {date_str} 的筛选器特征")
        logger.info(f"待运行筛选器: {screeners}")

        for screener_name in screeners:
            results = self.run_screener(screener_name, date_str)
            if results:
                self.save_screener_results(screener_name, date_str, results)

        logger.info(f"日期 {date_str} 的筛选器特征收集完成")

    def collect_for_date_range(self, start_date: str, end_date: str,
                                screeners: Optional[List[str]] = None):
        """为日期范围收集筛选器特征"""
        # 获取交易日列表
        with sqlite3.connect(str(self.source_db), timeout=30) as conn:
            rows = conn.execute("""
                SELECT DISTINCT trade_date
                FROM daily_prices
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date
            """, (start_date, end_date)).fetchall()

        trading_dates = [r[0] for r in rows]

        logger.info(f"日期范围 {start_date} 到 {end_date} 共 {len(trading_dates)} 个交易日")

        for i, date_str in enumerate(trading_dates, 1):
            logger.info(f"\n处理日期 {i}/{len(trading_dates)}: {date_str}")
            self.collect_for_date(date_str, screeners)

    def get_screener_stats(self, date_str: Optional[str] = None) -> Dict:
        """获取筛选器统计信息"""
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            if date_str:
                # 指定日期的统计
                rows = conn.execute("""
                    SELECT screener_name,
                           COUNT(*) as total,
                           SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
                           AVG(score) as avg_score
                    FROM screener_features
                    WHERE trade_date = ?
                    GROUP BY screener_name
                    ORDER BY screener_name
                """, (date_str,)).fetchall()
            else:
                # 整体统计
                rows = conn.execute("""
                    SELECT screener_name,
                           COUNT(*) as total,
                           SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits,
                           AVG(score) as avg_score,
                           MIN(trade_date) as min_date,
                           MAX(trade_date) as max_date
                    FROM screener_features
                    GROUP BY screener_name
                    ORDER BY screener_name
                """).fetchall()

        stats = {}
        for row in rows:
            stats[row[0]] = {
                'total': row[1],
                'hits': row[2],
                'hit_rate': row[2] / row[1] if row[1] > 0 else 0,
                'avg_score': row[3],
            }
            if len(row) > 4:
                stats[row[0]]['date_range'] = f"{row[4]} 到 {row[5]}"

        return stats

    def get_stock_screener_features(self, code: str, date_str: str) -> Dict[str, Dict]:
        """获取某只股票在指定日期的筛选器特征"""
        with sqlite3.connect(str(self.target_db), timeout=30) as conn:
            rows = conn.execute("""
                SELECT screener_name, hit, score, reason, extra_data
                FROM screener_features
                WHERE code = ? AND trade_date = ?
            """, (code, date_str)).fetchall()

        features = {}
        for row in rows:
            features[row[0]] = {
                'hit': bool(row[1]),
                'score': row[2],
                'reason': row[3],
                'extra': json.loads(row[4]) if row[4] else {}
            }

        return features


def main():
    parser = argparse.ArgumentParser(description='收集筛选器特征')
    parser.add_argument('--date', type=str,
                        help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, default='2024-09-01',
                        help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--screeners', type=str, nargs='+',
                        help='指定要运行的筛选器列表')
    parser.add_argument('--stats', action='store_true',
                        help='显示统计信息')
    parser.add_argument('--overwrite', action='store_true',
                        help='清空现有数据')

    args = parser.parse_args()

    collector = ScreenerFeatureCollector()

    if args.overwrite:
        with sqlite3.connect(str(SCREENER_SCORES_DB), timeout=30) as conn:
            conn.execute("DELETE FROM screener_features")
            conn.commit()
        logger.info("已清空现有筛选器特征数据")

    if args.stats:
        date_str = args.date if args.date else None
        stats = collector.get_screener_stats(date_str)

        print("\n" + "="*60)
        print("筛选器特征统计")
        print("="*60)
        if date_str:
            print(f"日期: {date_str}")
        print(f"\n{'筛选器':<30} {'总数':<8} {'命中':<8} {'命中率':<8} {'平均分':<8}")
        print("-"*70)
        for name, s in stats.items():
            print(f"{name:<30} {s['total']:<8} {s['hits']:<8} {s['hit_rate']*100:.1f}%{' ':<5} {s['avg_score']:.2f}")
        return

    # 确定日期范围
    screeners = args.screeners if args.screeners else collector.available_screeners

    if args.date:
        collector.collect_for_date(args.date, screeners)
    else:
        end_date = args.end_date
        if not end_date:
            # 使用 NeoTrade2 数据库的最新日期
            with sqlite3.connect(str(NEOTRADE_DB_PATH), timeout=30) as conn:
                row = conn.execute("SELECT MAX(trade_date) FROM daily_prices").fetchone()
                end_date = row[0] if row and row[0] else datetime.now().strftime("%Y-%m-%d")

        logger.info(f"日期范围: {args.start_date} 到 {end_date}")
        collector.collect_for_date_range(args.start_date, end_date, screeners)


if __name__ == '__main__':
    main()
