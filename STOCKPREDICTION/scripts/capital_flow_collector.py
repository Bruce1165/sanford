"""
capital_flow_collector.py - 资金面数据收集模块

第一阶段：基础设施搭建 - 资金面数据收集
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import time
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/capital_flow_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CapitalFlowCollector:
    """资金流向数据收集器"""

    def __init__(self, db_path: str = "data/capital_flow.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # API配置（模拟真实API）
        self.northbound_api_base = "https://api.example.com/northbound"
        self.southbound_api_base = "https://api.example.com/southbound"
        self.api_key = "DEMO_API_KEY"  # 实际需要配置

        logger.info("资金流向数据收集器初始化完成")

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS capital_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date DATE NOT NULL,
                    northbound_inflow REAL,
                    northbound_outflow REAL,
                    northbound_net REAL,
                    southbound_inflow REAL,
                    southbound_outflow REAL,
                    southbound_net REAL,
                    total_net_flow REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS sector_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date DATE NOT NULL,
                    sector_name TEXT NOT NULL,
                    net_inflow REAL,
                    turnover_rate REAL,
                    sector_return REAL,
                    hot_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS market_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_date DATE NOT NULL,
                    limit_up_count INTEGER,
                    limit_down_count INTEGER,
                    total_stocks INTEGER,
                    limit_up_rate REAL,
                    avg_turnover_rate REAL,
                    fear_greed_index REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS collection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    data_name TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_capital_flow_date ON capital_flow(trade_date);
                CREATE INDEX IF NOT EXISTS idx_sector_flow_date ON sector_flow(trade_date, sector_name);
                CREATE INDEX IF NOT EXISTS idx_sentiment_date ON market_sentiment(trade_date);
                CREATE INDEX IF NOT EXISTS idx_collection_log_created ON collection_log(created_at);
            """)
            conn.commit()
            logger.info("资金流向数据库初始化完成")

    def _log_task(self, task_type: str, data_name: str, status: str, message: str):
        """记录任务日志"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                INSERT INTO collection_log (task_type, data_name, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (task_type, data_name, status, message, datetime.now()))
            conn.commit()

    def collect_northbound_capital(self, start_date: str = None, end_date: str = None) -> Dict:
        """收集北向资金数据（沪深股通）"""
        self._log_task("北向资金", "北向资金收集", "START", "开始收集北向资金数据")

        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')

            # 模拟API调用（实际应从真实API获取）
            # 数据格式：日期、北向资金流入、流出、净流入
            dates = self._generate_date_range(start_date, end_date)

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                for date in dates:
                    # 模拟数据（实际从API获取）
                    if datetime.strptime(date, '%Y-%m-%d').weekday() < 5:  # 只在交易日
                        inflow = random.uniform(50, 150)  # 50-150亿流入
                        outflow = random.uniform(30, 120)
                        net_flow = inflow - outflow

                        conn.execute("""
                            INSERT OR REPLACE INTO capital_flow
                            (trade_date, northbound_inflow, northbound_outflow, northbound_net,
                             southbound_inflow, southbound_outflow, southbound_net,
                             total_net_flow, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
                        """, (date, inflow, outflow, net_flow, net_flow,
                               datetime.now(), datetime.now()))

                    if len(dates) % 5 == 0:
                        conn.commit()

                conn.commit()

            self._log_task("北向资金", "北向资金收集", "SUCCESS",
                          f"成功收集{len(dates)}天北向资金数据")

            return {
                'start_date': start_date,
                'end_date': end_date,
                'days_collected': len(dates)
            }

        except Exception as e:
            logger.error(f"收集北向资金数据失败: {e}")
            self._log_task("北向资金", "北向资金收集", "ERROR", str(e))
            return None

    def collect_southbound_capital(self, start_date: str = None, end_date: str = None) -> Dict:
        """收集南向资金数据（港股通）"""
        self._log_task("南向资金", "南向资金收集", "START", "开始收集南向资金数据")

        try:
            if start_date is None:
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if end_date is None:
                end_date = datetime.now().strftime('%Y-%m-%d')

            dates = self._generate_date_range(start_date, end_date)

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                for date in dates:
                    if datetime.strptime(date, '%Y-%m-%d').weekday() < 5:
                        # 模拟南向资金数据（港股通数据通常较小）
                        inflow = random.uniform(10, 50)  # 10-50亿流入
                        outflow = random.uniform(8, 40)
                        net_flow = inflow - outflow

                        # 更新现有记录（如果存在）
                        conn.execute("""
                            INSERT OR REPLACE INTO capital_flow
                            (trade_date, northbound_inflow, northbound_outflow, northbound_net,
                             southbound_inflow, southbound_outflow, southbound_net,
                             total_net_flow, created_at, updated_at)
                            VALUES (?,?,?, ?,?,?, ?,
                            (SELECT COALESCE((northbound_inflow - northbound_outflow) + (? - ?), 0) FROM capital_flow WHERE trade_date = ?),
                            ?, ?)
                        """, (date, 0, 0, 0, inflow, outflow, net_flow,
                               date, datetime.now(), datetime.now()))

                    if len(dates) % 5 == 0:
                        conn.commit()

                conn.commit()

            self._log_task("南向资金", "南向资金收集", "SUCCESS",
                          f"成功收集{len(dates)}天南向资金数据")

            return {
                'start_date': start_date,
                'end_date': end_date,
                'days_collected': len(dates)
            }

        except Exception as e:
            logger.error(f"收集南向资金数据失败: {e}")
            self._log_task("南向资金", "南向资金收集", "ERROR", str(e))
            return None

    def collect_sector_flow(self, date: str = None) -> Dict:
        """收集板块资金流向"""
        self._log_task("板块资金", "板块资金流向", "START", f"开始收集板块资金流向")

        try:
            if date is None:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # 主要板块列表
            sectors = [
                '人工智能', '半导体', '新能源', '生物医药', '高端制造',
                '大金融', '大消费', '大科技', '军工', '环保',
                '钢铁', '煤炭', '有色金属', '石化', '电力'
            ]

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                for sector in sectors:
                    # 模拟板块资金数据
                    net_inflow = random.uniform(-50, 200)  # 净流入，可能为负
                    turnover_rate = random.uniform(1.0, 8.0)  # 换手率 1%-8%
                    sector_return = random.uniform(-3.0, 5.0)  # 板块涨幅 -3% 到 +5%

                    # 热度评分（综合考虑净流入、涨幅、换手率）
                    hot_score = 0
                    if net_inflow > 50:
                        hot_score += 30
                    elif net_inflow > 0:
                        hot_score += 15

                    if sector_return > 2.0:
                        hot_score += 30
                    elif sector_return > 0:
                        hot_score += 15

                    if turnover_rate > 4.0:
                        hot_score += 25
                    elif turnover_rate > 2.0:
                        hot_score += 10

                    hot_score = min(100, max(0, hot_score))

                    conn.execute("""
                        INSERT OR REPLACE INTO sector_flow
                        (trade_date, sector_name, net_inflow, turnover_rate, sector_return, hot_score, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (date, sector, net_inflow, turnover_rate, sector_return, hot_score, datetime.now()))

                conn.commit()

            self._log_task("板块资金", "板块资金流向", "SUCCESS",
                          f"成功收集{len(sectors)}个板块资金流向")

            return {
                'date': date,
                'sectors_collected': len(sectors)
            }

        except Exception as e:
            logger.error(f"收集板块资金流向失败: {e}")
            self._log_task("板块资金", "板块资金流向", "ERROR", str(e))
            return None

    def collect_market_sentiment(self, date: str = None) -> Dict:
        """收集市场情绪指标（涨跌停、换手率、恐贪指数）"""
        self._log_task("市场情绪", "市场情绪指标", "START", f"开始收集市场情绪指标")

        try:
            if date is None:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # 模拟市场数据
            total_stocks = 4663  # A股总数
            limit_up_count = random.randint(20, 80)  # 涨停股票数
            limit_down_count = random.randint(10, 50)  # 跌停股票数
            limit_up_rate = (limit_up_count / total_stocks) * 100  # 涨停率

            # 平均换手率
            avg_turnover_rate = random.uniform(1.5, 4.0)

            # 恐贪指数（0-100，100代表极度贪婪）
            fear_greed_index = random.uniform(30, 70)

            # 根据多个指标计算恐贪指数
            # 涨停率高 → 贪婪，跌停率高 → 恐惧
            # 换手率高 → 活跃，可能贪婪
            fg_score = 50  # 中性
            fg_score += limit_up_rate * 10  # 涨停率正向贡献
            fg_score -= (limit_down_count / total_stocks) * 100 * 5  # 跌停率负向贡献
            fg_score += (avg_turnover_rate - 2.5) * 5  # 换手率调整

            fear_greed_index = max(0, min(100, fg_score))

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO market_sentiment
                    (trade_date, limit_up_count, limit_down_count, total_stocks,
                     limit_up_rate, avg_turnover_rate, fear_greed_index, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, limit_up_count, limit_down_count, total_stocks,
                       limit_up_rate, avg_turnover_rate, fear_greed_index, datetime.now()))
                conn.commit()

            self._log_task("市场情绪", "市场情绪指标", "SUCCESS",
                          f"成功收集市场情绪指标，恐贪指数: {fear_greed_index:.1f}")

            return {
                'date': date,
                'limit_up_count': limit_up_count,
                'limit_down_count': limit_down_count,
                'limit_up_rate': limit_up_rate,
                'avg_turnover_rate': avg_turnover_rate,
                'fear_greed_index': fear_greed_index
            }

        except Exception as e:
            logger.error(f"收集市场情绪指标失败: {e}")
            self._log_task("市场情绪", "市场情绪指标", "ERROR", str(e))
            return None

    def get_latest_capital_flow(self, days: int = 10) -> List[Dict]:
        """获取最新资金流向数据"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT trade_date, northbound_inflow, northbound_outflow, northbound_net,
                       southbound_inflow, southbound_outflow, southbound_net, total_net_flow
                FROM capital_flow
                ORDER BY trade_date DESC
                LIMIT ?
            """, (days,)).fetchall()

            return [
                {
                    'trade_date': row[0],
                    'northbound_inflow': row[1],
                    'northbound_outflow': row[2],
                    'northbound_net': row[3],
                    'southbound_inflow': row[4],
                    'southbound_outflow': row[5],
                    'southbound_net': row[6],
                    'total_net_flow': row[7]
                }
                for row in rows
            ]

    def get_hot_sectors(self, date: str = None, top_n: int = 5) -> List[Dict]:
        """获取热门板块"""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT sector_name, net_inflow, turnover_rate, sector_return, hot_score
                FROM sector_flow
                WHERE trade_date = ?
                ORDER BY hot_score DESC
                LIMIT ?
            """, (date, top_n)).fetchall()

            return [
                {
                    'sector_name': row[0],
                    'net_inflow': row[1],
                    'turnover_rate': row[2],
                    'sector_return': row[3],
                    'hot_score': row[4]
                }
                for row in rows
            ]

    def get_market_sentiment(self, date: str = None) -> Dict:
        """获取市场情绪指标"""
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            row = conn.execute("""
                SELECT limit_up_count, limit_down_count, total_stocks, limit_up_rate,
                       avg_turnover_rate, fear_greed_index
                FROM market_sentiment
                WHERE trade_date = ?
            """, (date,)).fetchone()

            if row:
                return {
                    'date': date,
                    'limit_up_count': row[0],
                    'limit_down_count': row[1],
                    'total_stocks': row[2],
                    'limit_up_rate': row[3],
                    'avg_turnover_rate': row[4],
                    'fear_greed_index': row[5]
                }
            return None

    def run_full_collection(self, days_back: int = 30) -> Dict:
        """完整收集流程"""
        logger.info("=" * 80)
        logger.info("资金面数据收集模块")
        logger.info("=" * 80)

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        logger.info(f"计划收集{days_back}天数据，日期范围：{start_date} - {end_date}")

        results = {}

        # 收集北向资金
        north_result = self.collect_northbound_capital(start_date, end_date)
        if north_result:
            results['northbound'] = north_result

        # 收集南向资金
        south_result = self.collect_southbound_capital(start_date, end_date)
        if south_result:
            results['southbound'] = south_result

        # 收集板块资金流向（最近一天）
        sector_result = self.collect_sector_flow(end_date)
        if sector_result:
            results['sector'] = sector_result

        # 收集市场情绪指标（最近一天）
        sentiment_result = self.collect_market_sentiment(end_date)
        if sentiment_result:
            results['sentiment'] = sentiment_result

        # 生成统计报告
        logger.info("=" * 80)
        logger.info("数据收集统计报告")
        logger.info("=" * 80)

        for key, value in results.items():
            logger.info(f"{key}: {value}")

        # 显示热门板块
        hot_sectors = self.get_hot_sectors(end_date, top_n=5)
        if hot_sectors:
            logger.info("\n热门板块排名：")
            for i, sector in enumerate(hot_sectors, 1):
                logger.info(f"  {i}. {sector['sector_name']} (热度: {sector['hot_score']:.1f})")

        # 显示市场情绪
        sentiment = self.get_market_sentiment(end_date)
        if sentiment:
            fg_status = "极度贪婪" if sentiment['fear_greed_index'] > 75 else \
                       "贪婪" if sentiment['fear_greed_index'] > 60 else \
                       "中性" if sentiment['fear_greed_index'] > 40 else \
                       "恐惧" if sentiment['fear_greed_index'] > 25 else "极度恐惧"
            logger.info(f"\n市场情绪：{fg_status} (恐贪指数: {sentiment['fear_greed_index']:.1f})")

        logger.info("=" * 80)

        return results

    def _generate_date_range(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        date_list = []
        current = start
        while current <= end:
            date_list.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)

        return date_list


def main():
    parser = argparse.ArgumentParser(description='资金面数据收集器')
    parser.add_argument('--collect', action='store_true', help='开始数据收集')
    parser.add_argument('--days', type=int, default=30, help='收集最近N天数据')
    parser.add_argument('--capital', action='store_true', help='收集资金流向数据')
    parser.add_argument('--sector', action='store_true', help='收集板块资金流向')
    parser.add_argument('--sentiment', action='store_true', help='收集市场情绪指标')
    parser.add_argument('--latest', action='store_true', help='查看最新数据')

    args = parser.parse_args()

    if args.collect:
        collector = CapitalFlowCollector()
        results = collector.run_full_collection(days_back=args.days)
        print(f"数据收集完成：{len(results)}/{4}个任务")

    elif args.capital:
        collector = CapitalFlowCollector()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
        collector.collect_northbound_capital(start_date, end_date)
        collector.collect_southbound_capital(start_date, end_date)

    elif args.sector:
        collector = CapitalFlowCollector()
        collector.collect_sector_flow()

    elif args.sentiment:
        collector = CapitalFlowCollector()
        collector.collect_market_sentiment()

    elif args.latest:
        collector = CapitalFlowCollector()

        print("=" * 80)
        print("最新资金流向数据（最近10天）")
        print("=" * 80)

        capital_flow = collector.get_latest_capital_flow(days=10)
        print(f"{'日期':<12} {'北向净流入':<12} {'南向净流入':<12} {'总净流入':<12}")
        print("-" * 80)
        for flow in capital_flow:
            print(f"{flow['trade_date']:<12s} {flow['northbound_net']:>10.2f} {flow['southbound_net']:>10.2f} {flow['total_net_flow']:>10.2f}")

        print("\n热门板块：")
        hot_sectors = collector.get_hot_sectors(top_n=5)
        for sector in hot_sectors:
            print(f"  {sector['sector_name']:<15s} 净流入: {sector['net_inflow']:>8.2f} 热度: {sector['hot_score']:>5.1f}")

        print("\n市场情绪：")
        sentiment = collector.get_market_sentiment()
        if sentiment:
            fg_status = "极度贪婪" if sentiment['fear_greed_index'] > 75 else \
                       "贪婪" if sentiment['fear_greed_index'] > 60 else \
                       "中性" if sentiment['fear_greed_index'] > 40 else \
                       "恐惧" if sentiment['fear_greed_index'] > 25 else "极度恐惧"
            print(f"  恐贪指数: {sentiment['fear_greed_index']:.1f} ({fg_status})")
            print(f"  涨停数: {sentiment['limit_up_count']} 跌停数: {sentiment['limit_down_count']}")
            print(f"  涨停率: {sentiment['limit_up_rate']:.2f}% 平均换手率: {sentiment['avg_turnover_rate']:.2f}%")

        print("=" * 80)

    else:
        print(__doc__)


if __name__ == '__main__':
    main()
