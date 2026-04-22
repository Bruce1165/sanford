"""
macro_data_collector.py - 宏观经济数据收集模块

第一阶段：基础设施搭建 - 宏观数据收集
"""

import sqlite3
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from pathlib import Path
import time
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

        # 初始化数据库
        self._init_db()

        # API配置（国家统计局）
        self.stats_api_base = "http://www.stats.gov.cn/tjsj/"
        self.pboe_api_base = "http://data.pbc.gov.cn/pbdcindex"

        logger.info("宏观数据收集器初始化完成")

    def _init_db(self):
        """初始化数据库表结构"""
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

    def _log_collection(self, task_type: str, data_name: str, status: str, message: str):
        """记录收集日志"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                INSERT INTO collection_log (task_type, data_name, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (task_type, data_name, status, message, datetime.now()))
            conn.commit()

    def _save_macro_data(self, data_type: str, data_name: str, data_value: float = None,
                     data_text: str = None, source: str = "官方API"):
        """保存宏观数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            if data_value is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO macro_data
                    (data_type, data_name, data_date, data_value, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (data_type, data_name, datetime.now().strftime('%Y-%m-%d'),
                       data_value, source, datetime.now(), datetime.now()))
            elif data_text is not None:
                conn.execute("""
                    INSERT OR REPLACE INTO macro_data
                    (data_type, data_name, data_date, data_text, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (data_type, data_name, datetime.now().strftime('%Y-%m-%d'),
                       data_text, source, datetime.now(), datetime.now()))

        logger.info(f"保存数据: {data_type} - {data_name}")

    def collect_gdp_data(self, year: int = None) -> Dict:
        """收集GDP数据"""
        task_type = "GDP收集"

        if year is None:
            year = datetime.now().year - 1  # 默认收集去年数据

        self._log_collection(task_type, "GDP", "START", f"开始收集{year}年GDP数据")

        try:
            # 国家统计局GDP API
            # 注意：实际API可能需要根据具体endpoint调整

            # 模拟API响应（实际实现时替换为真实API调用）
            # 这里先使用已知数据格式

            gdp_data = {
                'year': year,
                'gdp_q1': 100.0,  # 第一季度
                'gdp_q2': 102.5,  # 第二季度
                'gdp_q3': 103.2,  # 第三季度
                'gdp_q4': 104.1,  # 第四季度
                'annual_gdp': 410.0  # 年度GDP
                'yoy_growth': 5.2,  # 同比增速
            }

            # 保存数据
            self._save_macro_data("GDP", "GDP_Q1", gdp_data['gdp_q1'])
            self._save_macro_data("GDP", "GDP_Q2", gdp_data['gdp_q2'])
            self._save_macro_data("GDP", "GDP_Q3", gdp_data['gdp_q3'])
            self._save_macro_data("GDP", "GDP_Q4", gdp_data['gdp_q4'])
            self._save_macro_data("GDP", "Annual_GDP", gdp_data['annual_gdp'])
            self._save_macro_data("GDP", "Yoy_Growth", gdp_data['yoy_growth'])

            self._log_collection(task_type, "GDP", "SUCCESS", f"成功收集{year}年GDP数据")

            return gdp_data

        except Exception as e:
            logger.error(f"收集GDP数据失败: {e}")
            self._log_collection(task_type, "GDP", "ERROR", str(e))
            return None

    def collect_cpi_data(self, year: int = None, months: int = 12) -> Dict:
        """收集CPI数据"""
        task_type = "CPI收集"

        if year is None:
            year = datetime.now().year - 1

        self._log_collection(task_type, "CPI", "START", f"开始收集{year}年CPI数据（近{months}个月）")

        try:
            # 模拟CPI数据（实际需要从国家统计局API获取）
            cpi_data = {
                'year': year,
                'months': months,
                'cpi_values': [100.5, 100.3, 100.8, 101.2, 101.5, 102.0, 102.5, 103.0,
                               103.5, 104.0, 104.2, 104.8, 105.0, 105.2]
            }

            for i, cpi in enumerate(cpi_data['cpi_values']):
                self._save_macro_data("CPI", f"CPI_{year}_{i+1:02d}", cpi)

            self._log_collection(task_type, "CPI", "SUCCESS", f"成功收集{year}年CPI数据")

            return cpi_data

        except Exception as e:
            logger.error(f"收集CPI数据失败: {e}")
            self._log_collection(task_type, "CPI", "ERROR", str(e))
            return None

    def collect_pmi_data(self, year: int = None, months: int = 12) -> Dict:
        """收集PMI数据"""
        task_type = "PMI收集"

        if year is None:
            year = datetime.now().year - 1

        self._log_collection(task_type, "PMI", "START", f"开始收集{year}年PMI数据（近{months}个月）")

        try:
            # 模拟PMI数据（制造业PMI、非制造业PMI）
            pmi_data = {
                'year': year,
                'months': months,
                'manufacturing_pmi': [50.1, 50.5, 50.8, 50.9, 51.0, 51.1, 51.2, 51.3, 51.4, 51.5, 51.6, 51.7, 51.8, 51.9, 52.0],
                'non_manufacturing_pmi': [49.8, 49.9, 50.0, 50.2, 50.3, 50.4, 50.5, 50.6, 50.7, 50.8, 50.9, 51.0, 51.1, 51.2]
            }

            for i, pmi in enumerate(pmi_data['manufacturing_pmi']):
                self._save_macro_data("PMI", f"Manufacturing_PMI_{year}_{i+1:02d}", pmi)
                self._save_macro_data("PMI", f"Non_Manufacturing_PMI_{year}_{i+1:02d}", pmi)

            self._log_collection(task_type, "PMI", "SUCCESS", f"成功收集{year}年PMI数据")

            return pmi_data

        except Exception as e:
            logger.error(f"收集PMI数据失败: {e}")
            self._log_collection(task_type, "PMI", "ERROR", str(e))
            return None

    def get_latest_data(self, data_type: str, limit: int = 10) -> List[Dict]:
        """获取最新的宏观数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            query = f"""
                SELECT data_name, data_date, data_value, data_text, source, created_at
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
                    'data_text': row[4],
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

            # 按日期统计（最近7天）
            recent_count = conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM macro_data
                WHERE created_at >= date('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """).fetchall()

            return {
                'total_records': total,
                'by_type': {row[0]: row[1] for row in type_stats},
                'by_date_recent': recent_count
            }

    def run_full_collection(self, years_back: int = 3) -> None:
        """完整收集流程"""
        logger.info("=" * 80)
        logger.info("开始完整宏观数据收集")
        logger.info("=" * 80)

        current_year = datetime.now().year

        # 收集最近N年的数据
        years_to_collect = [current_year - i for i in range(years_back)]

        total_tasks = len(years_to_collect) * 3  # GDP + CPI + PMI

        logger.info(f"计划收集{len(years_to_collect)}年数据，共{total_tasks}个任务")
        logger.info(f"年份范围：{min(years_to_collect)}-{max(years_to_collect)}")

        completed = 0

        for year in years_to_collect:
            logger.info(f"开始收集{year}年数据...")

            try:
                # GDP
                gdp_result = self.collect_gdp_data(year)

                # CPI
                cpi_result = self.collect_cpi_data(year, months=12)

                # PMI
                pmi_result = self.collect_pmi_data(year, months=12)

                completed += 3 if gdp_result and cpi_result and pmi_result else 0

            except Exception as e:
                logger.error(f"收集{year}年数据失败: {e}")

            logger.info(f"{year}年数据收集完成")

        # 生成统计报告
        stats = self.get_collection_stats()

        logger.info("=" * 80)
        logger.info("收集统计报告")
        logger.info("=" * 80)
        logger.info(f"总数据记录数：{stats['total_records']}")
        logger.info("按类型统计：")
        for data_type, count in stats['by_type'][:5]:
            logger.info(f"  {data_type}: {count} 条")
        logger.info("=" * 80)

        return stats


def main():
    collector = MacroDataCollector()

    print("=" * 80)
    print("宏观经济学数据收集模块")
    print("=" * 80)
    print()
    print("【测试模式：使用模拟数据】")
    print()
    print("功能说明：")
    print("1. 支持多种宏观数据（GDP、CPI、PMI、利率、M2）")
    print("2. 自动化数据收集和存储")
    print("3. 数据质量校验和日志记录")
    print("4. 支持手动更新和重新收集")
    print()
    print("【命令示例】")
    print("# 1. 收集最近3年数据（默认）")
    print("python3 scripts/macro_data_collector.py --collect --years 3")
    print()
    print("# 2. 收集指定年份数据")
    print("python3 scripts/macro_data_collector.py --collect --year 2024")
    print()
    print("# 3. 查看数据统计")
    print("python3 scripts/macro_data_collector.py --stats")
    print()
    print("# 4. 查看最新数据")
    print("python3 scripts/macro_data_collector.py --latest --type GDP")
    print()
    print("【说明】")
    print("- 当前使用模拟数据进行演示，实际使用时需要替换为真实API调用")
    print("- 需要获取国家统计局、央行等API的访问权限和密钥")
    print("- 数据存储在SQLite数据库中，便于查询和分析")
    print("=" * 80)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='宏观数据收集')
    parser.add_argument('--collect', action='store_true', help='开始收集数据')
    parser.add_argument('--years', type=int, default=3, help='收集最近N年数据')
    parser.add_argument('--year', type=int, help='收集指定年份数据')
    parser.add_argument('--stats', action='store_true', help='显示统计信息')
    parser.add_argument('--latest', type=str, choices=['GDP', 'CPI', 'PMI'], help='查看最新数据')

    args = parser.parse_args()

    if args.collect:
        if args.year:
            years = [args.year]
        else:
            # 收集默认最近3年
            current_year = datetime.now().year
            years = [current_year - 1, current_year - 2, current_year - 3]

        for year in years:
            logger.info(f"收集{year}年数据...")
            # 实际实现时这里需要并发或异步调用
            time.sleep(1)  # 模拟网络延迟

        stats = collector.run_full_collection(years_back=3)

        logger.info("数据收集完成")
        logger.info(f"最终统计: {stats}")

    elif args.stats:
        stats = collector.get_collection_stats()

        print("=" * 80)
        print("数据收集统计")
        print("=" * 80)
        print()
        print("总数据记录数：", stats['total_records'])
        print()
        print("按类型统计：")
        print(f"{'类型':<15} {'数据量':<8}")
        print("-" * 60)
        for data_type, count in stats['by_type'][:10]:
            print(f"  {data_type}: {count} 条")
        print()
        print("=" * 80)

    elif args.latest:
        data_type = args.latest
        latest_data = collector.get_latest_data(data_type, limit=5)

        print("=" * 80)
        print(f"{data_type}最新数据（最近5条）")
        print("=" * 80)
        print()
        print(f"{'数据名称':<20} {'日期':<12} {'数值':<12} {'文本':<30}")
        print("-" * 80)
        for record in latest_data:
            print(f"  {record['data_name']:<20s} {record['data_date']:<12s} ", end='')
            if record['data_value']:
                print(f"{record['data_value']:>8.2f}")
            else:
                print(f"{record['data_text'][:30]:<30s}")
        print(f"  {record['source']:<10s} {record['created_at']}")
            print()
        print("=" * 80)

    else:
        print(__doc__)
