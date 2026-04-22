"""
macro_data_collector_v2.py - 宏观经济数据收集模块（修复版）

第一阶段：基础设施搭建 - 宏观数据收集
"""

import sqlite3
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/macro_data_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MacroDataCollector:
    """宏观数据收集器"""

    def __init__(self, db_path: str = "data/macro.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS macro_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT NOT NULL,
                    data_name TEXT NOT NULL,
                    data_date DATE NOT NULL,
                    data_value REAL,
                    data_text TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS collection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    data_name TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_macro_type_date ON macro_data(data_type, data_date);
                CREATE INDEX IF NOT EXISTS idx_collection_log_created ON collection_log(created_at);
            """)
            conn.commit()
            logger.info("数据库初始化完成")

    def _log_task(self, task_type: str, data_name: str, status: str, message: str):
        """记录任务日志"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                INSERT INTO collection_log (task_type, data_name, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (task_type, data_name, status, message, datetime.now()))
            conn.commit()

    def _save_macro_data(self, data_type: str, data_name: str,
                     data_value: float = None, data_text: str = None,
                     source: str = "模拟数据"):
        """保存宏观数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            if data_value is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO macro_data
                    (data_type, data_name, data_date, data_value, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data_type, data_name, datetime.now().strftime('%Y-%m-%d'),
                       data_value, source, datetime.now(), datetime.now()))
            elif data_text is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO macro_data
                    (data_type, data_name, data_date, data_text, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data_type, data_name, datetime.now().strftime('%Y-%m-%d'),
                       data_text, source, datetime.now(), datetime.now()))

        logger.info(f"保存数据: {data_type} - {data_name}")

    def collect_gdp_data(self, year: int) -> Dict:
        """收集GDP数据（模拟）"""
        self._log_task("GDP", "GDP收集", "START", f"开始收集{year}年GDP数据")

        try:
            # 模拟GDP数据（实际应从国家统计局API获取）
            gdp_data = {
                'year': year,
                'gdp_q1': 100.0,  # 第一季度
                'gdp_q2': 102.5,  # 第二季度
                'gdp_q3': 103.2,  # 第三季度
                'gdp_q4': 104.1,  # 第四季度
                'annual_gdp': 410.0,  # 年度GDP（万亿元）
                'yoy_growth': 5.2,  # 同比增速
            }

            # 保存各季度数据
            self._save_macro_data("GDP", "GDP_Q1", gdp_data['gdp_q1'])
            self._save_macro_data("GDP", "GDP_Q2", gdp_data['gdp_q2'])
            self._save_macro_data("GDP", "GDP_Q3", gdp_data['gdp_q3'])
            self._save_macro_data("GDP", "GDP_Q4", gdp_data['gdp_q4'])
            self._save_macro_data("GDP", "Annual_GDP", gdp_data['annual_gdp'])
            self._save_macro_data("GDP", "Yoy_Growth", gdp_data['yoy_growth'])

            self._log_task("GDP", "GDP收集", "SUCCESS", f"成功收集{year}年GDP数据")

            return gdp_data

        except Exception as e:
            logger.error(f"收集GDP数据失败: {e}")
            self._log_task("GDP", "GDP收集", "ERROR", str(e))
            return None

    def collect_cpi_data(self, year: int) -> Dict:
        """收集CPI数据（模拟）"""
        self._log_task("CPI", "CPI收集", "START", f"开始收集{year}年CPI数据")

        try:
            # 模拟CPI数据（12个月）
            cpi_data = {
                'year': year,
                'months': list(range(1, 13))
            }

            for month in cpi_data['months']:
                # 模拟CPI数据（实际应从国家统计局API获取）
                month_cpi = 100.0 + (month * 0.5)  # 简化模拟

            # 保存每月CPI
            data_name = f"CPI_{year}_{month:02d}"
            self._save_macro_data("CPI", data_name, month_cpi)

            self._log_task("CPI", "CPI收集", "SUCCESS", f"成功收集{year}年{month}月CPI数据")

            return cpi_data

        except Exception as e:
            logger.error(f"收集CPI数据失败: {e}")
            self._log_task("CPI", "CPI收集", "ERROR", str(e))
            return None

    def collect_pmi_data(self, year: int, months: int = 12) -> Dict:
        """收集PMI数据（模拟）"""
        self._log_task("PMI", "PMI收集", "START", f"开始收集{year}年PMI数据（近{months}个月）")

        try:
            # 模拟PMI数据（实际应从国家统计局API获取）
            pmi_data = {
                'year': year,
                'months': list(range(1, months + 1))
            }

            # 制造业PMI
            manufacturing_pmi_values = [
                50.1, 50.5, 50.8, 50.9, 51.0, 51.2, 51.3, 51.4, 51.5, 51.6,
                51.7, 51.8, 51.9, 52.0, 52.1, 52.2, 52.3, 52.4, 52.5, 52.6,
                52.7, 52.8, 52.9, 53.0, 53.1, 53.2
            ]

            for i, pmi in enumerate(manufacturing_pmi_values):
                data_name = f"Manufacturing_PMI_{year}_{i+1:02d}"
                self._save_macro_data("PMI", data_name, pmi)

            # 非制造业PMI
            non_manufacturing_pmi_values = [
                49.8, 49.9, 50.0, 50.1, 50.2, 50.3, 50.4, 50.5, 50.6, 50.7, 50.8, 50.9, 51.0, 51.1,
                51.2, 51.3, 51.4, 51.5, 51.6, 51.7, 51.8, 51.9, 52.0, 52.1, 52.2, 52.3, 52.4,
                52.5, 52.6, 52.7, 52.8, 52.9, 53.0, 53.1
            ]

            for i, pmi in enumerate(non_manufacturing_pmi_values):
                data_name = f"Non_Manufacturing_PMI_{year}_{i+1:02d}"
                self._save_macro_data("PMI", data_name, pmi)

            self._log_task("PMI", "PMI收集", "SUCCESS", f"成功收集{year}年PMI数据")

            return pmi_data

        except Exception as e:
            logger.error(f"收集PMI数据失败: {e}")
            self._log_task("PMI", "PMI收集", "ERROR", str(e))
            return None

    def get_latest_data(self, data_type: str, limit: int = 10) -> List[Dict]:
        """获取最新数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            query = f"""
                SELECT data_name, data_date, data_value, source, created_at
                FROM macro_data
                WHERE data_type = ?
                ORDER BY data_date DESC
                LIMIT ?
            """
            rows = conn.execute(query, (data_type, limit)).fetchall()

            return [
                {
                    'data_name': row[1],
                    'data_date': row[2],
                    'data_value': row[3],
                    'source': row[5],
                    'created_at': row[6]
                }
                for row in rows
            ]

    def get_collection_stats(self) -> Dict:
        """获取收集统计"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            # 总数据量
            total = conn.execute("SELECT COUNT(*) FROM macro_data").fetchone()[0]

            # 按类型统计
            type_stats = conn.execute("""
                SELECT data_type, COUNT(*) as count
                FROM macro_data
                GROUP BY data_type
                ORDER BY count DESC
            """).fetchall()

            # 最近7天统计
            recent = conn.execute("""
                SELECT COUNT(*)
                FROM macro_data
                WHERE created_at >= date('now', '-7 days')
                GROUP BY 1
            """).fetchone()[0]

            return {
                'total_records': total,
                'by_type': {row[0]: row[1] for row in type_stats},
                'recent_7days': recent
            }

    def run_full_collection(self, years_back: int = 3) -> Dict:
        """完整收集流程"""
        logger.info("=" * 80)
        logger.info("宏观经济学数据收集模块")
        logger.info("=" * 80)

        current_year = datetime.now().year

        years_to_collect = [current_year - i for i in range(years_back)]
        total_tasks = len(years_to_collect) * 3  # GDP + CPI + PMI

        logger.info(f"计划收集{len(years_to_collect)}年数据，共{total_tasks}个任务")
        logger.info(f"年份范围：{min(years_to_collect)}-{max(years_to_collect)}")

        completed = 0

        for year in years_to_collect:
            logger.info(f"开始收集{year}年数据...")

            try:
                # GDP数据
                gdp_result = self.collect_gdp_data(year)

                # CPI数据（简化版，只收集年度数据）
                cpi_data = self.collect_cpi_data(year)

                # PMI数据
                pmi_result = self.collect_pmi_data(year, months=12)

                if gdp_result and cpi_data and pmi_result:
                    completed += 3
                else:
                    completed += 0

                logger.info(f"{year}年数据收集完成")

            except Exception as e:
                logger.error(f"{year}年数据收集失败: {e}")

        # 生成统计报告
        stats = self.get_collection_stats()

        logger.info("=" * 80)
        logger.info("数据收集统计报告")
        logger.info("=" * 80)
        logger.info(f"总数据记录数：{stats['total_records']}")
        logger.info()
        logger.info("按类型统计：")
        for data_type, count in stats['by_type'][:10]:
            logger.info(f"  {data_type}: {count} 条")

        logger.info(f"最近7天新增：{stats['recent_7days']} 条")

        logger.info("=" * 80)

        return {
            'years_collected': years_to_collect,
            'total_tasks': total_tasks,
            'completed_tasks': completed,
            'stats': stats
        }


def main():
    parser = argparse.ArgumentParser(description='宏观经济数据收集器')
    parser.add_argument('--collect', action='store_true', help='开始数据收集')
    parser.add_argument('--years', type=int, default=3, help='收集最近N年数据')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--latest', type=str, choices=['GDP', 'CPI', 'PMI'], help='查看最新数据')

    args = parser.parse_args()

    if args.collect:
        collector = MacroDataCollector()

        if args.years:
            results = collector.run_full_collection(years_back=args.years)
            print(f"数据收集完成：{results['completed_tasks']}/{results['total_tasks']}个任务")
        else:
            logger.info("默认收集最近3年数据")
            results = collector.run_full_collection(years_back=3)

    elif args.stats:
        stats = collector.get_collection_stats()
        print("=" * 80)
        print("数据收集统计")
        print("=" * 80)
        print(f"总数据记录数：{stats['total_records']}")
        print()
        print("按类型统计：")
        print(f"{'类型':<15} {'数据量':<10}")
        print("-" * 80)
        for data_type, count in stats['by_type'][:10]:
            print(f"  {data_type}: {count} 条")
        print()
        print("=" * 80)

    elif args.latest:
        collector = MacroDataCollector()
        latest_data = collector.get_latest_data(args.latest, limit=5)
        print("=" * 80)
        print(f"{args.latest}最新数据（最近5条）")
        print("=" * 80)
        print()
        print(f"{'数据名称':<20} {'日期':<12} {'数值':<12} {'来源':<10}")
        print("-" * 80)
        for record in latest_data:
            print(f"{record['data_name']:<20s} {record['data_date']:<12s} ", end='')
            if record['data_value'] is not None:
                print(f"{record['data_value']:>10.2f}")
            else:
                print(f"{record['data_text'][:30]:<30s}")
            print(f"{record['source']:<10s} {record['created_at']}")
            print()
        print("=" * 80)

    else:
        print(__doc__)


if __name__ == '__main__':
    main()
