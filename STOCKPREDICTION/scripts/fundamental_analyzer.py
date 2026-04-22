"""
fundamental_analyzer.py - 基本面分析模块

第一阶段：基础设施搭建 - 基本面分析
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fundamental_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    """基本面分析器"""

    def __init__(self, db_path: str = "data/fundamentals.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # API配置（模拟真实API）
        self.financial_api_base = "https://api.example.com/financial"
        self.api_key = "DEMO_API_KEY"  # 实际需要配置

        logger.info("基本面分析器初始化完成")

    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financial_statements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    report_period TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    revenue REAL,
                    net_profit REAL,
                    total_assets REAL,
                    total_liabilities REAL,
                    net_assets REAL,
                    eps REAL,
                    roe REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, report_period, report_type)
                );

                CREATE TABLE IF NOT EXISTS fundamental_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    score_date DATE NOT NULL,
                    revenue_growth_score REAL,
                    profit_growth_score REAL,
                    roe_score REAL,
                    pe_score REAL,
                    industry_prospect_score REAL,
                    total_score REAL,
                    score_details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, score_date)
                );

                CREATE TABLE IF NOT EXISTS industry_prospects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    industry_name TEXT NOT NULL,
                    outlook_score REAL,
                    growth_potential REAL,
                    risk_level REAL,
                    policy_support REAL,
                    evaluation_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(industry_name, evaluation_date)
                );

                CREATE TABLE IF NOT EXISTS collection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    code TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_financial_code ON financial_statements(code, report_period);
                CREATE INDEX IF NOT EXISTS idx_fundamental_code ON fundamental_scores(code, score_date);
                CREATE INDEX IF NOT EXISTS idx_industry_date ON industry_prospects(industry_name, evaluation_date);
                CREATE INDEX IF NOT EXISTS idx_collection_log_created ON collection_log(created_at);
            """)
            conn.commit()
            logger.info("基本面数据库初始化完成")

    def _log_task(self, task_type: str, code: str, status: str, message: str):
        """记录任务日志"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                INSERT INTO collection_log (task_type, code, status, message, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (task_type, code, status, message, datetime.now()))
            conn.commit()

    def collect_financial_statements(self, code: str, quarters: int = 12) -> Dict:
        """收集财报数据"""
        self._log_task("财报收集", code, "START", f"开始收集{code}财报数据")

        try:
            # 模拟API调用获取财报数据
            # 实际应从真实API获取：东方财富、同花顺等
            report_types = ['Q1', 'Q2', 'Q3', 'Q4', 'Year']

            with sqlite3.connect(self.db_path, timeout=30) as conn:
                for i in range(quarters):
                    # 模拟财报数据
                    revenue = random.uniform(10, 500) * (1 + i * 0.1)  # 营收增长趋势
                    net_profit = revenue * random.uniform(0.05, 0.15)  # 净利润率5%-15%
                    total_assets = revenue * random.uniform(1.5, 3.0)
                    total_liabilities = total_assets * random.uniform(0.4, 0.7)
                    net_assets = total_assets - total_liabilities
                    roe = (net_profit / net_assets * 100) if net_assets > 0 else 0
                    eps = net_profit / random.uniform(10, 50)  # 每股收益

                    # 生成报告期
                    year = datetime.now().year - (i // 4)
                    quarter = i % 4 + 1
                    report_period = f"{year}-Q{quarter}" if i % 4 != 0 else f"{year}-Year"

                    conn.execute("""
                        INSERT OR REPLACE INTO financial_statements
                        (code, report_period, report_type, revenue, net_profit, total_assets,
                         total_liabilities, net_assets, eps, roe, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code, report_period, report_types[i % 5], revenue, net_profit,
                           total_assets, total_liabilities, net_assets, eps, roe,
                           datetime.now(), datetime.now()))

                    if (i + 1) % 4 == 0:
                        conn.commit()

                conn.commit()

            self._log_task("财报收集", code, "SUCCESS",
                          f"成功收集{quarters}个季度财报数据")

            return {
                'code': code,
                'quarters_collected': quarters
            }

        except Exception as e:
            logger.error(f"收集{code}财报数据失败: {e}")
            self._log_task("财报收集", code, "ERROR", str(e))
            return None

    def calculate_revenue_growth_score(self, code: str, periods: int = 4) -> float:
        """计算营收增速评分"""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                # 获取最近N个季度的营收数据
                rows = conn.execute("""
                    SELECT report_period, revenue
                    FROM financial_statements
                    WHERE code = ?
                    ORDER BY report_period DESC
                    LIMIT ?
                """, (code, periods)).fetchall()

                if len(rows) < 2:
                    return 0.0

                # 计算营收增长率
                revenue_values = [row[1] for row in rows]
                growth_rates = []

                for i in range(len(revenue_values) - 1):
                    if revenue_values[i] > 0:
                        growth = (revenue_values[i + 1] / revenue_values[i] - 1) * 100
                        growth_rates.append(growth)

                if not growth_rates:
                    return 0.0

                avg_growth = sum(growth_rates) / len(growth_rates)

                # 评分逻辑：增速>30%得满分，负增速得0分
                score = max(0, min(100, avg_growth / 0.3 * 100))

                return score

        except Exception as e:
            logger.error(f"计算{code}营收增速评分失败: {e}")
            return 0.0

    def calculate_profit_growth_score(self, code: str, periods: int = 4) -> float:
        """计算利润增速评分"""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                rows = conn.execute("""
                    SELECT report_period, net_profit
                    FROM financial_statements
                    WHERE code = ?
                    ORDER BY report_period DESC
                    LIMIT ?
                """, (code, periods)).fetchall()

                if len(rows) < 2:
                    return 0.0

                profit_values = [row[1] for row in rows]
                growth_rates = []

                for i in range(len(profit_values) - 1):
                    if profit_values[i] > 0:
                        growth = (profit_values[i + 1] / profit_values[i] - 1) * 100
                        growth_rates.append(growth)

                if not growth_rates:
                    return 0.0

                avg_growth = sum(growth_rates) / len(growth_rates)

                # 利润增速评分
                score = max(0, min(100, avg_growth / 0.25 * 100))

                return score

        except Exception as e:
            logger.error(f"计算{code}利润增速评分失败: {e}")
            return 0.0

    def calculate_roe_score(self, code: str, periods: int = 4) -> float:
        """计算ROE评分"""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                rows = conn.execute("""
                    SELECT roe
                    FROM financial_statements
                    WHERE code = ? AND roe IS NOT NULL
                    ORDER BY report_period DESC
                    LIMIT ?
                """, (code, periods)).fetchall()

                if not rows:
                    return 0.0

                roe_values = [row[0] for row in rows]
                avg_roe = sum(roe_values) / len(roe_values)

                # ROE评分：>20%得满分，<5%得0分
                if avg_roe > 20:
                    score = 100
                elif avg_roe > 15:
                    score = 80 + (avg_roe - 15) * 4
                elif avg_roe > 10:
                    score = 60 + (avg_roe - 10) * 4
                elif avg_roe > 5:
                    score = 40 + (avg_roe - 5) * 4
                else:
                    score = avg_roe * 8

                return max(0, min(100, score))

        except Exception as e:
            logger.error(f"计算{code} ROE评分失败: {e}")
            return 0.0

    def calculate_pe_score(self, code: str, pe_ratio: float) -> float:
        """计算PE评分（基于历史分位）"""
        try:
            # 这里简化处理，实际应基于历史PE分位分析
            # 合理PE范围：10-30
            if pe_ratio is None or pe_ratio <= 0:
                return 50.0  # 中性评分

            if 10 <= pe_ratio <= 30:
                return 100  # 完美区间
            elif 5 <= pe_ratio < 10:
                return 80  # 偏低但可接受
            elif 30 < pe_ratio <= 50:
                return 60  # 偏高但可接受
            elif pe_ratio > 50:
                return 30  # 估值过高
            else:
                return 50  # 未知情况

        except Exception as e:
            logger.error(f"计算{code} PE评分失败: {e}")
            return 50.0

    def evaluate_industry_prospect(self, industry: str) -> float:
        """评估行业前景"""
        try:
            # 行业前景评分（模拟，实际应基于政策、行业数据等）
            industry_scores = {
                '人工智能': 85, '半导体': 80, '新能源': 75,
                '生物医药': 70, '高端制造': 72, '大金融': 55,
                '大消费': 60, '大科技': 75, '军工': 68,
                '环保': 65, '钢铁': 45, '煤炭': 40,
                '有色金属': 50, '石化': 48, '电力': 60
            }

            # 模糊匹配
            for key, score in industry_scores.items():
                if key in industry or industry in key:
                    return score

            return 60.0  # 默认中性评分

        except Exception as e:
            logger.error(f"评估{industry}行业前景失败: {e}")
            return 60.0

    def calculate_comprehensive_score(self, code: str, pe_ratio: float = None, industry: str = None) -> Dict:
        """计算综合基本面评分"""
        try:
            # 各维度评分
            revenue_score = self.calculate_revenue_growth_score(code, periods=4)
            profit_score = self.calculate_profit_growth_score(code, periods=4)
            roe_score = self.calculate_roe_score(code, periods=4)
            pe_score = self.calculate_pe_score(code, pe_ratio)
            industry_score = self.evaluate_industry_prospect(industry) if industry else 60.0

            # 权重配置
            weights = {
                'revenue_growth': 0.25,   # 营收增速 25%
                'profit_growth': 0.25,     # 利润增速 25%
                'roe': 0.20,              # ROE 20%
                'pe': 0.15,                # PE 15%
                'industry_prospect': 0.15     # 行业前景 15%
            }

            # 综合评分
            total_score = (
                revenue_score * weights['revenue_growth'] +
                profit_score * weights['profit_growth'] +
                roe_score * weights['roe'] +
                pe_score * weights['pe'] +
                industry_score * weights['industry_prospect']
            )

            # 生成评分详情
            score_details = {
                'revenue_growth': revenue_score,
                'profit_growth': profit_score,
                'roe': roe_score,
                'pe': pe_score,
                'industry_prospect': industry_score,
                'weights': weights
            }

            # 保存评分结果
            score_date = datetime.now().strftime('%Y-%m-%d')
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO fundamental_scores
                    (code, score_date, revenue_growth_score, profit_growth_score, roe_score,
                     pe_score, industry_prospect_score, total_score, score_details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, score_date, revenue_score, profit_score, roe_score,
                       pe_score, industry_score, total_score,
                       str(score_details), datetime.now()))
                conn.commit()

            return {
                'code': code,
                'score_date': score_date,
                'revenue_growth_score': revenue_score,
                'profit_growth_score': profit_score,
                'roe_score': roe_score,
                'pe_score': pe_score,
                'industry_prospect_score': industry_score,
                'total_score': total_score,
                'score_details': score_details
            }

        except Exception as e:
            logger.error(f"计算{code}综合基本面评分失败: {e}")
            return None

    def batch_calculate_scores(self, codes: List[str], pe_ratios: Dict[str, float] = None,
                            industries: Dict[str, str] = None) -> List[Dict]:
        """批量计算基本面评分"""
        results = []
        processed = 0

        for code in codes:
            try:
                pe_ratio = pe_ratios.get(code) if pe_ratios else None
                industry = industries.get(code) if industries else None

                score = self.calculate_comprehensive_score(code, pe_ratio, industry)
                if score:
                    results.append(score)
                    processed += 1

                    if processed % 100 == 0:
                        logger.info(f"已处理 {processed}/{len(codes)} 只股票")

            except Exception as e:
                logger.warning(f"处理股票 {code} 时出错: {e}")
                continue

        logger.info(f"批量评分完成，共处理 {processed}/{len(codes)} 只股票")
        return results

    def get_top_stocks_by_score(self, date: str = None, top_n: int = 50) -> List[Dict]:
        """获取基本面评分最高的股票"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path, timeout=30) as conn:
            rows = conn.execute("""
                SELECT code, score_date, revenue_growth_score, profit_growth_score, roe_score,
                       pe_score, industry_prospect_score, total_score
                FROM fundamental_scores
                WHERE score_date = ?
                ORDER BY total_score DESC
                LIMIT ?
            """, (date, top_n)).fetchall()

            return [
                {
                    'code': row[0],
                    'score_date': row[1],
                    'revenue_growth_score': row[2],
                    'profit_growth_score': row[3],
                    'roe_score': row[4],
                    'pe_score': row[5],
                    'industry_prospect_score': row[6],
                    'total_score': row[7]
                }
                for row in rows
            ]

    def get_stock_fundamental_details(self, code: str) -> Dict:
        """获取个股基本面详情"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            # 获取最新财报数据
            financial_rows = conn.execute("""
                SELECT report_period, revenue, net_profit, eps, roe
                FROM financial_statements
                WHERE code = ?
                ORDER BY report_period DESC
                LIMIT 4
            """, (code,)).fetchall()

            # 获取最新评分
            score_row = conn.execute("""
                SELECT revenue_growth_score, profit_growth_score, roe_score,
                       pe_score, industry_prospect_score, total_score, score_details
                FROM fundamental_scores
                WHERE code = ?
                ORDER BY score_date DESC
                LIMIT 1
            """, (code,)).fetchone()

            if not financial_rows:
                return None

            financial_data = [
                {
                    'report_period': row[0],
                    'revenue': row[1],
                    'net_profit': row[2],
                    'eps': row[3],
                    'roe': row[4]
                }
                for row in financial_rows
            ]

            return {
                'code': code,
                'financial_statements': financial_data,
                'score': score_row[0:7] if score_row else None,
                'score_details': score_row[7] if score_row else None
            }


def main():
    import argparse

    parser = argparse.ArgumentParser(description='基本面分析器')
    parser.add_argument('--collect', action='store_true', help='收集财报数据')
    parser.add_argument('--code', type=str, help='指定股票代码')
    parser.add_argument('--score', action='store_true', help='计算基本面评分')
    parser.add_argument('--batch', action='store_true', help='批量计算评分')
    parser.add_argument('--top', type=int, default=50, help='查看前N名股票')
    parser.add_argument('--detail', type=str, help='查看个股基本面详情')

    args = parser.parse_args()

    analyzer = FundamentalAnalyzer()

    if args.collect and args.code:
        result = analyzer.collect_financial_statements(args.code, quarters=12)
        if result:
            print(f"财报数据收集完成：{result}")

    elif args.score and args.code:
        score = analyzer.calculate_comprehensive_score(args.code)
        if score:
            print(f"{args.code} 基本面评分：")
            print(f"  总分: {score['total_score']:.1f}")
            print(f"  营收增速: {score['revenue_growth_score']:.1f}")
            print(f"  利润增速: {score['profit_growth_score']:.1f}")
            print(f"  ROE评分: {score['roe_score']:.1f}")
            print(f"  PE评分: {score['pe_score']:.1f}")
            print(f"  行业前景: {score['industry_prospect_score']:.1f}")

    elif args.batch:
        # 从NeoTrade2数据库获取股票列表
        neo_db_path = "/Users/mac/NeoTrade2/data/stock_data.db"
        with sqlite3.connect(neo_db_path, timeout=30) as conn:
            stocks = conn.execute("""
                SELECT code, pe_ratio, industry
                FROM stocks
                WHERE COALESCE(is_delisted, 0) = 0
                  AND name NOT LIKE '%ST%' AND name NOT LIKE '%*ST%'
                  AND code NOT LIKE '399%'
                LIMIT 500
            """).fetchall()

        codes = [row[0] for row in stocks]
        pe_ratios = {row[0]: row[1] for row in stocks}
        industries = {row[0]: row[2] for row in stocks}

        print(f"开始批量计算 {len(codes)} 只股票的基本面评分...")
        results = analyzer.batch_calculate_scores(codes, pe_ratios, industries)

        if results:
            print(f"批量评分完成，共处理 {len(results)} 只股票")

            # 显示前10名
            print("\n【基本面评分前10名】")
            print(f"{'排名':<5} {'代码':<8} {'总分':<8} {'营收增速':<8} {'利润增速':<8} {'ROE':<8} {'PE':<8} {'行业前景':<8}")
            print("-" * 80)
            for i, score in enumerate(sorted(results, key=lambda x: x['total_score'], reverse=True)[:10], 1):
                print(f"{i:<5d} {score['code']:<8s} {score['total_score']:<8.1f} "
                      f"{score['revenue_growth_score']:<8.1f} {score['profit_growth_score']:<8.1f} "
                      f"{score['roe_score']:<8.1f} {score['pe_score']:<8.1f} "
                      f"{score['industry_prospect_score']:<8.1f}")

    elif args.detail:
        details = analyzer.get_stock_fundamental_details(args.detail)
        if details:
            print(f"\n【{args.detail} 基本面详情】")
            print("=" * 80)
            print(f"评分日期: {details['score']['score_date'] if details['score'] else 'N/A'}")
            print(f"综合评分: {details['score']['total_score']:.1f}" if details['score'] else "评分: N/A")

            if details['score']:
                print(f"\n各维度评分:")
                print(f"  营收增速: {details['score']['revenue_growth_score']:.1f}")
                print(f"  利润增速: {details['score']['profit_growth_score']:.1f}")
                print(f"  ROE评分: {details['score']['roe_score']:.1f}")
                print(f"  PE评分: {details['score']['pe_score']:.1f}")
                print(f"  行业前景: {details['score']['industry_prospect_score']:.1f}")

            print(f"\n最近4期财报:")
            print(f"{'报告期':<15} {'营收':<12} {'净利润':<12} {'EPS':<10} {'ROE':<10}")
            print("-" * 80)
            for fs in details['financial_statements']:
                print(f"{fs['report_period']:<15s} {fs['revenue']:>10.2f} {fs['net_profit']:>10.2f} "
                      f"{fs['eps']:>8.2f} {fs['roe']:>8.2f}%")

            print("=" * 80)

    elif args.top:
        top_stocks = analyzer.get_top_stocks_by_score(top_n=args.top)
        if top_stocks:
            print("=" * 80)
            print(f"基本面评分前{args.top}名股票")
            print("=" * 80)
            print(f"{'排名':<5} {'代码':<8} {'总分':<8} {'营收增速':<8} {'利润增速':<8} {'ROE':<8} {'PE':<8} {'行业前景':<8}")
            print("-" * 80)
            for i, stock in enumerate(top_stocks, 1):
                print(f"{i:<5d} {stock['code']:<8s} {stock['total_score']:<8.1f} "
                      f"{stock['revenue_growth_score']:<8.1f} {stock['profit_growth_score']:<8.1f} "
                      f"{stock['roe_score']:<8.1f} {stock['pe_score']:<8.1f} "
                      f"{stock['industry_prospect_score']:<8.1f}")
            print("=" * 80)

    else:
        print(__doc__)


if __name__ == '__main__':
    main()
