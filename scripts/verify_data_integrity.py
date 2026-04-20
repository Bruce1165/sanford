#!/usr/bin/env python3
"""
数据完整性检查脚本 - Data Integrity Checker
检查所有股票的历史数据完整性，识别缺失的交易日
"""

import os
import sys
import sqlite3
import json
import argparse
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from trading_calendar import TradingCalendar

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent))) / 'data/stock_data.db'
REPORT_DIR = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent))) / 'logs'
START_DATE = '2024-09-02'
END_DATE = '2026-03-20'


@dataclass
class StockGapReport:
    """单只股票缺口报告"""
    code: str
    name: str
    is_delisted: bool
    expected_days: int
    actual_days: int
    missing_days: int
    missing_dates: List[str]
    data_coverage_pct: float


@dataclass
class IntegrityReport:
    """完整性检查总报告"""
    generated_at: str
    start_date: str
    end_date: str
    total_stocks_checked: int
    expected_trading_days: int
    
    # 统计
    stocks_with_gaps: int
    stocks_complete: int
    stocks_delisted: int
    total_missing_records: int
    
    # 覆盖率分布
    coverage_100pct: int
    coverage_95_99pct: int
    coverage_90_94pct: int
    coverage_below_90pct: int
    
    # 详细数据
    gap_reports: List[Dict]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class DataIntegrityChecker:
    """数据完整性检查器"""
    
    def __init__(self, db_path: str = None, start_date: str = None, end_date: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.start_date = start_date or START_DATE
        self.end_date = end_date or END_DATE
        self.calendar = TradingCalendar()
        self.expected_trading_days: List[str] = []
        self._load_expected_trading_days()
    
    def _load_expected_trading_days(self):
        """加载预期的交易日列表（Baostock via trading_calendar_cache）"""
        from trading_calendar import get_trading_days_between
        start = datetime.strptime(self.start_date, '%Y-%m-%d').date()
        end = datetime.strptime(self.end_date, '%Y-%m-%d').date()
        days = get_trading_days_between(start, end)
        self.expected_trading_days = [d.strftime('%Y-%m-%d') for d in days]
        logger.info(f"📅 预期交易日: {len(self.expected_trading_days)} 天 ({self.start_date} 至 {self.end_date})")
    
    def get_all_stocks(self) -> List[Tuple[str, str, int]]:
        """获取所有股票代码、名称和退市状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT code, name, is_delisted FROM stock_meta ORDER BY code"
        )
        stocks = [(row[0], row[1] or '', row[2] or 0) for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def get_sample_stocks(self, sample_size: int = 100) -> List[Tuple[str, str, int]]:
        """随机抽样股票进行检查"""
        all_stocks = self.get_all_stocks()
        if len(all_stocks) <= sample_size:
            return all_stocks
        return random.sample(all_stocks, sample_size)
    
    def check_stock_integrity(self, code: str, name: str, is_delisted: int) -> StockGapReport:
        """检查单只股票的数据完整性"""
        conn = sqlite3.connect(self.db_path)
        
        # 获取该股票在日期范围内的所有交易记录
        cursor = conn.execute(
            """SELECT DISTINCT trade_date FROM daily_prices 
               WHERE code = ? AND trade_date BETWEEN ? AND ?
               ORDER BY trade_date""",
            (code, self.start_date, self.end_date)
        )
        existing_dates = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        # 找出缺失的日期
        missing_dates = sorted([d for d in self.expected_trading_days if d not in existing_dates])
        
        actual_days = len(existing_dates)
        expected_days = len(self.expected_trading_days)
        missing_days = len(missing_dates)
        coverage_pct = (actual_days / expected_days * 100) if expected_days > 0 else 0
        
        # 对于已退市股票，调整预期（上市期间应该有的交易日）
        if is_delisted:
            # 尝试从数据库获取最后交易日期
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT MAX(trade_date) FROM daily_prices WHERE code = ?",
                (code,)
            )
            last_trade = cursor.fetchone()[0]
            conn.close()
            
            if last_trade and last_trade < self.end_date:
                # 只计算到退市日的预期交易日
                adjusted_expected = sum(1 for d in self.expected_trading_days if d <= last_trade)
                if adjusted_expected > 0:
                    coverage_pct = min(100.0, actual_days / adjusted_expected * 100)
        
        return StockGapReport(
            code=code,
            name=name,
            is_delisted=bool(is_delisted),
            expected_days=expected_days,
            actual_days=actual_days,
            missing_days=missing_days,
            missing_dates=missing_dates,
            data_coverage_pct=round(coverage_pct, 2)
        )
    
    def run_integrity_check(self, sample_size: Optional[int] = None, 
                           stocks_filter: Optional[List[str]] = None) -> IntegrityReport:
        """运行完整性检查"""
        
        # 获取待检查的股票列表
        if stocks_filter:
            all_stocks = self.get_all_stocks()
            stocks_to_check = [(c, n, d) for c, n, d in all_stocks if c in stocks_filter]
        elif sample_size:
            stocks_to_check = self.get_sample_stocks(sample_size)
            logger.info(f"🔍 随机抽样模式: 检查 {len(stocks_to_check)} 只股票")
        else:
            stocks_to_check = self.get_all_stocks()
            logger.info(f"🔍 全量检查模式: 检查 {len(stocks_to_check)} 只股票")
        
        # 执行检查
        gap_reports = []
        stocks_with_gaps = 0
        stocks_complete = 0
        stocks_delisted = 0
        total_missing = 0
        
        coverage_buckets = {
            '100': 0,
            '95_99': 0,
            '90_94': 0,
            'below_90': 0
        }
        
        total = len(stocks_to_check)
        for i, (code, name, is_delisted) in enumerate(stocks_to_check, 1):
            report = self.check_stock_integrity(code, name, is_delisted)
            gap_reports.append(report)
            
            if report.is_delisted:
                stocks_delisted += 1
            
            if report.missing_days > 0:
                stocks_with_gaps += 1
                total_missing += report.missing_days
            else:
                stocks_complete += 1
            
            # 覆盖率统计
            if report.data_coverage_pct >= 100:
                coverage_buckets['100'] += 1
            elif report.data_coverage_pct >= 95:
                coverage_buckets['95_99'] += 1
            elif report.data_coverage_pct >= 90:
                coverage_buckets['90_94'] += 1
            else:
                coverage_buckets['below_90'] += 1
            
            # 每100只显示进度
            if i % 100 == 0 or i == total:
                logger.info(f"  进度: {i}/{total} ({i/total*100:.1f}%)")
        
        # 生成报告
        integrity_report = IntegrityReport(
            generated_at=datetime.now().isoformat(),
            start_date=self.start_date,
            end_date=self.end_date,
            total_stocks_checked=total,
            expected_trading_days=len(self.expected_trading_days),
            stocks_with_gaps=stocks_with_gaps,
            stocks_complete=stocks_complete,
            stocks_delisted=stocks_delisted,
            total_missing_records=total_missing,
            coverage_100pct=coverage_buckets['100'],
            coverage_95_99pct=coverage_buckets['95_99'],
            coverage_90_94pct=coverage_buckets['90_94'],
            coverage_below_90pct=coverage_buckets['below_90'],
            gap_reports=[asdict(r) for r in gap_reports]
        )
        
        return integrity_report
    
    def save_report(self, report: IntegrityReport, filename: Optional[str] = None) -> Path:
        """保存报告到文件"""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            mode = 'sample' if report.total_stocks_checked < 4000 else 'full'
            filename = f"integrity_report_{mode}_{timestamp}.json"
        
        report_path = REPORT_DIR / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 报告已保存: {report_path}")
        return report_path
    
    def save_gap_csv(self, report: IntegrityReport, filename: Optional[str] = None) -> Path:
        """保存缺口摘要CSV（用于后续回填）"""
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            mode = 'sample' if report.total_stocks_checked < 4000 else 'full'
            filename = f"gap_summary_{mode}_{timestamp}.csv"
        
        csv_path = REPORT_DIR / filename
        
        # 只包含有缺口的股票
        gaps_only = [r for r in report.gap_reports if r['missing_days'] > 0]
        
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("code,name,is_delisted,missing_days,missing_dates\n")
            for r in gaps_only:
                dates_str = ';'.join(r['missing_dates'])
                f.write(f"{r['code']},{r['name']},{r['is_delisted']},{r['missing_days']},\"{dates_str}\"\n")
        
        logger.info(f"📄 缺口CSV已保存: {csv_path}")
        return csv_path
    
    def print_summary(self, report: IntegrityReport):
        """打印报告摘要"""
        print("\n" + "="*60)
        print("📊 数据完整性检查报告")
        print("="*60)
        print(f"生成时间: {report.generated_at}")
        print(f"检查范围: {report.start_date} 至 {report.end_date}")
        print(f"预期交易日: {report.expected_trading_days} 天")
        print(f"检查股票数: {report.total_stocks_checked}")
        print("-"*60)
        print("📈 数据完整度统计:")
        print(f"  ✅ 数据完整: {report.stocks_complete} 只 ({report.stocks_complete/report.total_stocks_checked*100:.1f}%)")
        print(f"  ⚠️  存在缺口: {report.stocks_with_gaps} 只 ({report.stocks_with_gaps/report.total_stocks_checked*100:.1f}%)")
        print(f"  📛 已退市:   {report.stocks_delisted} 只")
        print("-"*60)
        print("📊 覆盖率分布:")
        print(f"  100%:       {report.coverage_100pct} 只")
        print(f"  95%-99%:    {report.coverage_95_99pct} 只")
        print(f"  90%-94%:    {report.coverage_90_94pct} 只")
        print(f"  <90%:       {report.coverage_below_90pct} 只")
        print("-"*60)
        print(f"📉 总计缺失记录: {report.total_missing_records} 条")
        print("="*60)
        
        # 显示缺口最严重的10只股票
        if report.stocks_with_gaps > 0:
            print("\n🔴 缺口最严重的10只股票:")
            sorted_gaps = sorted(report.gap_reports, key=lambda x: x['missing_days'], reverse=True)[:10]
            for i, r in enumerate(sorted_gaps, 1):
                if r['missing_days'] > 0:
                    print(f"  {i}. {r['code']} ({r['name']}): 缺 {r['missing_days']} 天, 覆盖率 {r['data_coverage_pct']}%")


def main():
    parser = argparse.ArgumentParser(description='数据完整性检查工具')
    parser.add_argument('--sample', type=int, help='随机抽样检查N只股票（快速扫描）')
    parser.add_argument('--full', action='store_true', help='全量检查所有股票')
    parser.add_argument('--start-date', default=START_DATE, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', default=END_DATE, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--output', '-o', help='输出报告文件名')
    parser.add_argument('--csv', action='store_true', help='同时生成CSV格式的缺口摘要')
    
    args = parser.parse_args()
    
    if not args.sample and not args.full:
        logger.info("未指定检查模式，默认使用抽样100只")
        args.sample = 100
    
    checker = DataIntegrityChecker(
        start_date=args.start_date,
        end_date=args.end_date
    )
    
    report = checker.run_integrity_check(sample_size=args.sample)
    
    checker.print_summary(report)
    
    # 保存报告
    report_path = checker.save_report(report, args.output)
    
    if args.csv:
        csv_path = checker.save_gap_csv(report)
    
    # 返回建议
    print("\n" + "="*60)
    if report.stocks_with_gaps > 0:
        gap_ratio = report.stocks_with_gaps / report.total_stocks_checked
        if gap_ratio > 0.1:  # 超过10%有缺口
            print("⚠️  建议: 发现显著数据缺口，建议运行全量检查并执行Baostock回填")
            print(f"    python3 scripts/verify_data_integrity.py --full")
            print(f"    python3 scripts/backfill_baostock.py --report {report_path.name}")
        else:
            print("✅ 数据完整性良好，缺口比例较低")
    else:
        print("✅ 所有检查股票数据完整，无需回填")
    print("="*60)


if __name__ == '__main__':
    main()
