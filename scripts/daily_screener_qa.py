#!/usr/bin/env python3
"""
每日筛选器 QA 检查脚本 - Daily Screener QA

功能:
1. 检查所有11个筛选器的执行状态
2. 分析日志文件中的错误、异常
3. 检查输出文件是否存在且非空
4. 检查执行时间是否异常
5. 生成每日 QA 报告和告警

11个筛选器:
1. coffee_cup_screener (咖啡杯形态)
2. jin_feng_huang_screener (涨停金凤凰)
3. yin_feng_huang_screener (涨停银凤凰)
4. shi_pan_xian_screener (涨停试盘线)
5. er_ban_hui_tiao_screener (二板回调)
6. zhang_ting_bei_liang_yin_screener (涨停倍量阴)
7. breakout_20day_screener (20日突破)
8. breakout_main_screener (主升突破)
9. daily_hot_cold_screener (每日热冷股)
10. shuang_shou_ban_screener (双收板)
11. ashare_21_screener (A股21选股)
"""

import os
import sys
import re
import json
import sqlite3
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
LOGS_DIR = PROJECT_ROOT / "logs"
ALERTS_DIR = PROJECT_ROOT / "alerts"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "stock_data.db"

# 确保目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ALERTS_DIR.mkdir(parents=True, exist_ok=True)

# 11个筛选器配置
SCREENER_CONFIG = {
    'coffee_cup_screener': {
        'name': '咖啡杯形态',
        'description': 'Coffee Cup Pattern Screener',
        'script_path': SCRIPTS_DIR / 'coffee_cup_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'coffee_cup',
        'expected_runtime': (30, 300),  # 正常执行时间范围 (秒)
    },
    'jin_feng_huang_screener': {
        'name': '涨停金凤凰',
        'description': 'Jin Feng Huang Pattern',
        'script_path': SCRIPTS_DIR / 'jin_feng_huang_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'jin_feng_huang',
        'expected_runtime': (20, 180),
    },
    'yin_feng_huang_screener': {
        'name': '涨停银凤凰',
        'description': 'Yin Feng Huang Pattern',
        'script_path': SCRIPTS_DIR / 'yin_feng_huang_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'yin_feng_huang',
        'expected_runtime': (20, 180),
    },
    'shi_pan_xian_screener': {
        'name': '涨停试盘线',
        'description': 'Shi Pan Xian Pattern',
        'script_path': SCRIPTS_DIR / 'shi_pan_xian_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'shi_pan_xian',
        'expected_runtime': (15, 120),
    },
    'er_ban_hui_tiao_screener': {
        'name': '二板回调',
        'description': 'Er Ban Hui Tiao Pattern',
        'script_path': SCRIPTS_DIR / 'er_ban_hui_tiao_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'er_ban_hui_tiao',
        'expected_runtime': (15, 120),
    },
    'zhang_ting_bei_liang_yin_screener': {
        'name': '涨停倍量阴',
        'description': 'Zhang Ting Bei Liang Yin Pattern',
        'script_path': SCRIPTS_DIR / 'zhang_ting_bei_liang_yin_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'zhang_ting_bei_liang_yin',
        'expected_runtime': (20, 150),
    },
    'breakout_20day_screener': {
        'name': '20日突破',
        'description': '20-Day Breakout Screener',
        'script_path': SCRIPTS_DIR / 'breakout_20day_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'breakout_20day',
        'expected_runtime': (15, 120),
    },
    'breakout_main_screener': {
        'name': '主升突破',
        'description': 'Main Breakout Screener',
        'script_path': SCRIPTS_DIR / 'breakout_main_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'breakout_main',
        'expected_runtime': (20, 180),
    },
    'daily_hot_cold_screener': {
        'name': '每日热冷股',
        'description': 'Daily Hot/Cold Stocks',
        'script_path': SCRIPTS_DIR / 'daily_hot_cold_screener.py',
        'output_dir': DATA_DIR / '每日热冷股',
        'expected_runtime': (10, 90),
    },
    'shuang_shou_ban_screener': {
        'name': '双收板',
        'description': 'Shuang Shou Ban Pattern',
        'script_path': SCRIPTS_DIR / 'shuang_shou_ban_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'shuang_shou_ban',
        'expected_runtime': (15, 120),
    },
    'ashare_21_screener': {
        'name': 'A股21选股',
        'description': 'A-Share 2.1 Selection',
        'script_path': SCRIPTS_DIR / 'ashare_21_screener.py',
        'output_dir': DATA_DIR / 'screeners' / 'ashare_21',
        'expected_runtime': (25, 240),
    },
}


@dataclass
class ScreenerCheckResult:
    """单个筛选器检查结果"""
    name: str
    screener_id: str
    status: str = 'unknown'  # 'passed', 'failed', 'warning', 'not_run'
    script_exists: bool = False
    script_executable: bool = False
    output_exists: bool = False
    output_valid: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    last_run_time: Optional[str] = None
    execution_time: Optional[float] = None
    matches_count: Optional[int] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QAReport:
    """QA 报告"""
    date: str
    timestamp: str
    summary: Dict
    screeners: List[Dict]
    alerts: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            'date': self.date,
            'timestamp': self.timestamp,
            'summary': self.summary,
            'screeners': self.screeners,
            'alerts': self.alerts
        }


class ScreenerQAChecker:
    """筛选器 QA 检查器"""
    
    def __init__(self, date_str: Optional[str] = None):
        self.date_str = date_str or datetime.now().strftime('%Y-%m-%d')
        self.check_date = self.date_str.replace('-', '')
        self.results: List[ScreenerCheckResult] = []
        self.alerts: List[Dict] = []
        
    def check_all_screeners(self) -> List[ScreenerCheckResult]:
        """检查所有筛选器"""
        logger.info(f"开始检查 {len(SCREENER_CONFIG)} 个筛选器...")
        
        for screener_id, config in SCREENER_CONFIG.items():
            result = self.check_screener(screener_id, config)
            self.results.append(result)
            
        return self.results
    
    def check_screener(self, screener_id: str, config: Dict) -> ScreenerCheckResult:
        """检查单个筛选器"""
        result = ScreenerCheckResult(
            name=config['name'],
            screener_id=screener_id
        )
        
        logger.info(f"检查筛选器: {config['name']} ({screener_id})")
        
        # 1. 检查脚本文件是否存在
        script_path = config['script_path']
        result.script_exists = script_path.exists()
        if not result.script_exists:
            result.errors.append(f"脚本文件不存在: {script_path}")
            result.status = 'failed'
            return result
        
        # 2. 检查脚本是否可执行
        result.script_executable = os.access(script_path, os.R_OK)
        if not result.script_executable:
            result.warnings.append(f"脚本文件不可读: {script_path}")
        
        # 3. 检查日志文件中的错误
        log_errors = self.check_screener_logs(screener_id)
        result.errors.extend(log_errors)
        
        # 4. 检查输出文件
        output_dir = config['output_dir']
        if output_dir:
            result.output_exists = output_dir.exists()
            if result.output_exists:
                # 检查最近是否有输出
                recent_files = self.get_recent_output_files(output_dir)
                result.output_valid = len(recent_files) > 0
                if not result.output_valid:
                    result.warnings.append(f"输出目录存在但无近期文件: {output_dir}")
            else:
                result.warnings.append(f"输出目录不存在: {output_dir}")
        else:
            # 无特定输出目录的筛选器，检查数据库
            result.output_exists = self.check_database_output(screener_id)
            result.output_valid = result.output_exists
        
        # 5. 检查最近执行时间
        last_run = self.get_last_execution_time(screener_id)
        if last_run:
            result.last_run_time = last_run.isoformat()
        
        # 6. 确定状态
        if result.errors:
            result.status = 'failed'
        elif result.warnings:
            result.status = 'warning'
        elif result.output_valid or result.output_exists:
            result.status = 'passed'
        else:
            result.status = 'not_run'
        
        return result
    
    def check_screener_logs(self, screener_id: str) -> List[str]:
        """检查筛选器相关日志文件中的错误"""
        errors = []
        
        # 检查日志目录中相关的日志文件
        log_patterns = [
            f"*{screener_id}*.log",
            f"*screener*.log",
            "cron_*.log",
        ]
        
        checked_files = set()
        for pattern in log_patterns:
            for log_file in LOGS_DIR.glob(pattern):
                if log_file in checked_files:
                    continue
                checked_files.add(log_file)
                
                # 只检查最近2天的日志
                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if datetime.now() - mtime > timedelta(days=2):
                        continue
                except:
                    continue
                
                file_errors = self.analyze_log_file(log_file, screener_id)
                errors.extend(file_errors)
        
        return errors
    
    def analyze_log_file(self, log_file: Path, screener_id: str) -> List[str]:
        """分析单个日志文件中的错误"""
        errors = []
        
        # 错误模式
        error_patterns = [
            (r'ERROR.*?' + re.escape(screener_id), 'ERROR'),
            (r'CRITICAL.*?' + re.escape(screener_id), 'CRITICAL'),
            (r'Traceback.*?\n(?:  File ".*?".*?\n)*.*?Error:.*', 'TRACEBACK'),
            (r'Exception.*?' + re.escape(screener_id), 'EXCEPTION'),
            (r'Failed.*?run_screening', 'FAILED'),
            (r'Error running.*?' + screener_id.replace('_', '[_\-]?'), 'RUN_ERROR'),
        ]
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for pattern, error_type in error_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                for match in matches[:3]:  # 每种错误类型最多记录3条
                    error_msg = f"[{error_type}] {log_file.name}: {match[:200]}"
                    if error_msg not in errors:
                        errors.append(error_msg)
        except Exception as e:
            logger.warning(f"无法读取日志文件 {log_file}: {e}")
        
        return errors
    
    def get_recent_output_files(self, output_dir: Path, days: int = 2) -> List[Path]:
        """获取最近几天的输出文件"""
        recent_files = []
        cutoff_time = datetime.now() - timedelta(days=days)
        
        try:
            for file_path in output_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if mtime > cutoff_time:
                            recent_files.append(file_path)
                    except:
                        pass
        except Exception as e:
            logger.warning(f"无法扫描输出目录 {output_dir}: {e}")
        
        return recent_files
    
    def check_database_output(self, screener_id: str) -> bool:
        """检查数据库中是否有该筛选器的输出记录"""
        try:
            if not DB_PATH.exists():
                return False
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 检查 screener_results 表
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='screener_results'
            """)
            if not cursor.fetchone():
                conn.close()
                return False
            
            # 检查最近2天是否有结果
            cutoff_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) FROM screener_results 
                WHERE screener_name LIKE ? AND trade_date >= ?
            """, (f'%{screener_id}%', cutoff_date))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.warning(f"数据库检查失败: {e}")
            return False
    
    def get_last_execution_time(self, screener_id: str) -> Optional[datetime]:
        """获取筛选器最后执行时间"""
        # 从 progress 文件中获取
        progress_dir = SCRIPTS_DIR / 'data' / 'progress'
        if progress_dir.exists():
            progress_file = progress_dir / f"{screener_id}_progress.json"
            if progress_file.exists():
                try:
                    with open(progress_file, 'r') as f:
                        data = json.load(f)
                        last_update = data.get('last_update')
                        if last_update:
                            return datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                except:
                    pass
        
        # 从输出文件修改时间推断
        config = SCREENER_CONFIG.get(screener_id)
        if config and config['output_dir']:
            recent_files = self.get_recent_output_files(config['output_dir'], days=7)
            if recent_files:
                return datetime.fromtimestamp(max(f.stat().st_mtime for f in recent_files))
        
        return None
    
    def generate_alerts(self) -> List[Dict]:
        """生成告警"""
        alerts = []
        
        failed_count = sum(1 for r in self.results if r.status == 'failed')
        warning_count = sum(1 for r in self.results if r.status == 'warning')
        not_run_count = sum(1 for r in self.results if r.status == 'not_run')
        
        # 严重告警: 多个筛选器失败
        if failed_count >= 3:
            alerts.append({
                'severity': 'critical',
                'type': 'multiple_screener_failures',
                'message': f'多个筛选器失败: {failed_count}个',
                'timestamp': datetime.now().isoformat(),
                'details': {
                    'failed_count': failed_count,
                    'failed_screeners': [
                        r.screener_id for r in self.results if r.status == 'failed'
                    ]
                }
            })
        
        # 警告: 有筛选器失败
        if failed_count > 0:
            alerts.append({
                'severity': 'error',
                'type': 'screener_failure',
                'message': f'{failed_count}个筛选器运行失败',
                'timestamp': datetime.now().isoformat(),
                'details': {
                    'count': failed_count,
                    'screeners': [
                        {'id': r.screener_id, 'name': r.name, 'errors': r.errors}
                        for r in self.results if r.status == 'failed'
                    ]
                }
            })
        
        # 警告: 有筛选器未运行
        if not_run_count >= 5:
            alerts.append({
                'severity': 'warning',
                'type': 'screeners_not_run',
                'message': f'多个筛选器未运行: {not_run_count}个',
                'timestamp': datetime.now().isoformat(),
                'details': {
                    'count': not_run_count,
                    'screeners': [
                        r.screener_id for r in self.results if r.status == 'not_run'
                    ]
                }
            })
        
        # 警告: 有筛选器有警告
        if warning_count > 0:
            alerts.append({
                'severity': 'warning',
                'type': 'screener_warnings',
                'message': f'{warning_count}个筛选器有警告',
                'timestamp': datetime.now().isoformat(),
                'details': {
                    'count': warning_count,
                    'screeners': [
                        {'id': r.screener_id, 'name': r.name, 'warnings': r.warnings}
                        for r in self.results if r.status == 'warning'
                    ]
                }
            })
        
        self.alerts = alerts
        return alerts
    
    def generate_report(self) -> QAReport:
        """生成 QA 报告"""
        # 统计数据
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == 'passed')
        failed = sum(1 for r in self.results if r.status == 'failed')
        warning = sum(1 for r in self.results if r.status == 'warning')
        not_run = sum(1 for r in self.results if r.status == 'not_run')
        
        # 收集所有错误
        all_errors = []
        for r in self.results:
            for error in r.errors:
                all_errors.append({
                    'screener': r.screener_id,
                    'name': r.name,
                    'error': error
                })
        
        summary = {
            'total': total,
            'passed': passed,
            'failed': failed,
            'warning': warning,
            'not_run': not_run,
            'success_rate': round(passed / total * 100, 1) if total > 0 else 0,
            'total_errors': len(all_errors)
        }
        
        # 转换结果为字典
        screeners_data = [r.to_dict() for r in self.results]
        
        # 生成告警
        alerts = self.generate_alerts()
        
        report = QAReport(
            date=self.date_str,
            timestamp=datetime.now().isoformat(),
            summary=summary,
            screeners=screeners_data,
            alerts=alerts
        )
        
        return report
    
    def save_report(self, report: QAReport) -> Path:
        """保存 QA 报告"""
        report_file = LOGS_DIR / f"daily_qa_report_{self.date_str}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"QA 报告已保存: {report_file}")
        return report_file
    
    def save_alerts(self) -> Optional[Path]:
        """保存告警文件"""
        if not self.alerts:
            return None
        
        alert_file = ALERTS_DIR / f"screener_{self.date_str}.json"
        
        alert_data = {
            'date': self.date_str,
            'timestamp': datetime.now().isoformat(),
            'alert_count': len(self.alerts),
            'alerts': self.alerts
        }
        
        with open(alert_file, 'w', encoding='utf-8') as f:
            json.dump(alert_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"告警文件已保存: {alert_file}")
        return alert_file
    
    def print_summary(self, report: QAReport):
        """打印摘要"""
        print("\n" + "="*80)
        print(f"📊 每日筛选器 QA 报告 - {self.date_str}")
        print("="*80)
        
        summary = report.summary
        print(f"\n总计: {summary['total']} 个筛选器")
        print(f"  ✅ 通过: {summary['passed']}")
        print(f"  ❌ 失败: {summary['failed']}")
        print(f"  ⚠️  警告: {summary['warning']}")
        print(f"  ⏸️  未运行: {summary['not_run']}")
        print(f"  📈 成功率: {summary['success_rate']}%")
        
        if summary['total_errors'] > 0:
            print(f"\n⚠️  发现 {summary['total_errors']} 个错误")
        
        # 打印失败的筛选器
        failed = [r for r in self.results if r.status == 'failed']
        if failed:
            print("\n❌ 失败的筛选器:")
            for r in failed:
                print(f"  - {r.name} ({r.screener_id})")
                for error in r.errors[:2]:
                    print(f"    • {error[:100]}...")
        
        # 打印告警
        if self.alerts:
            print("\n🚨 告警:")
            for alert in self.alerts:
                emoji = '🔴' if alert['severity'] == 'critical' else '🟠' if alert['severity'] == 'error' else '🟡'
                print(f"  {emoji} [{alert['severity'].upper()}] {alert['message']}")
        
        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='每日筛选器 QA 检查')
    parser.add_argument('--date', type=str, help='检查日期 (YYYY-MM-DD)，默认为今天')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建检查器
    checker = ScreenerQAChecker(date_str=args.date)
    
    # 执行检查
    logger.info("开始每日筛选器 QA 检查...")
    checker.check_all_screeners()
    
    # 生成报告
    report = checker.generate_report()
    
    # 保存报告
    report_file = checker.save_report(report)
    
    # 保存告警
    alert_file = checker.save_alerts()
    
    # 打印摘要
    checker.print_summary(report)
    
    # 返回退出码
    failed_count = report.summary['failed']
    if failed_count >= 3:
        logger.error(f"严重: {failed_count}个筛选器失败")
        sys.exit(2)
    elif failed_count > 0:
        logger.warning(f"警告: {failed_count}个筛选器失败")
        sys.exit(1)
    else:
        logger.info("所有筛选器检查通过")
        sys.exit(0)


if __name__ == '__main__':
    main()
