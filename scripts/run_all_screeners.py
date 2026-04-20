#!/usr/bin/env python3
"""
Run All Screeners — 批量运行所有筛选器

自动运行所有14个活跃筛选器，生成当日结果并创建监控pick。
用于每日收盘后的全自动筛选流程。

Usage:
    python3 scripts/run_all_screeners.py
    python3 scripts/run_all_screeners.py --date 2026-03-20
    python3 scripts/run_all_screeners.py --dry-run  # 测试模式
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

WORKSPACE = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
SCRIPTS_DIR = WORKSPACE / 'scripts'
DATA_DIR = WORKSPACE / 'data'
LOGS_DIR = WORKSPACE / 'logs'

# 14个活跃筛选器 (与 dashboard 保持一致)
ACTIVE_SCREENERS = [
    'coffee_cup_screener',
    'jin_feng_huang_screener',
    'er_ban_hui_tiao_screener',
    'zhang_ting_bei_liang_yin_screener',
    'yin_feng_huang_screener',
    'breakout_main_screener',
    'shuang_shou_ban_screener',
    'high_tight_flag_screener',
    'double_bottom_screener',
    'breakout_20day_screener',
    'ascending_triangle_screener',
    'shi_pan_xian_screener',
    'a_share_21_screener',
    'daily_hot_cold_screener',
]


def run_screener(screener_name: str, date_str: str, timeout: int = 300) -> Dict:
    """运行单个筛选器"""
    script_path = SCRIPTS_DIR / f"{screener_name}.py"
    
    if not script_path.exists():
        return {
            'screener': screener_name,
            'success': False,
            'error': f'Script not found: {script_path}',
            'results_count': 0
        }
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), '--date', date_str],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE)
        )
        
        success = result.returncode == 0
        
        # Parse results count from output
        results_count = 0
        for line in result.stdout.split('\n'):
            if '匹配:' in line or 'Found:' in line:
                try:
                    results_count = int(''.join(filter(str.isdigit, line)))
                except:
                    pass
            if '共找到' in line:
                try:
                    parts = line.split('共找到')
                    if len(parts) > 1:
                        results_count = int(''.join(filter(str.isdigit, parts[1])))
                except:
                    pass
        
        return {
            'screener': screener_name,
            'success': success,
            'results_count': results_count,
            'stdout': result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
            'stderr': result.stderr[-200:] if result.stderr else ''
        }
        
    except subprocess.TimeoutExpired:
        return {
            'screener': screener_name,
            'success': False,
            'error': 'Timeout',
            'results_count': 0
        }
    except Exception as e:
        return {
            'screener': screener_name,
            'success': False,
            'error': str(e),
            'results_count': 0
        }


def run_all_screeners(date_str: str = None, dry_run: bool = False) -> Dict:
    """运行所有活跃筛选器"""
    date_str = date_str or datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n{'='*60}")
    print(f"🚀 Running All Screeners — {date_str}")
    print(f"{'='*60}")
    print(f"Total screeners: {len(ACTIVE_SCREENERS)}\n")
    
    if dry_run:
        print("[DRY RUN] Would run:")
        for screener in ACTIVE_SCREENERS:
            print(f"  - {screener}")
        return {'dry_run': True, 'screeners': ACTIVE_SCREENERS}
    
    results = []
    total_success = 0
    total_failed = 0
    total_picks = 0
    
    for i, screener in enumerate(ACTIVE_SCREENERS, 1):
        print(f"[{i}/{len(ACTIVE_SCREENERS)}] Running {screener}...")
        
        result = run_screener(screener, date_str)
        results.append(result)
        
        if result['success']:
            total_success += 1
            total_picks += result.get('results_count', 0)
            print(f"  ✅ Success — {result.get('results_count', 0)} picks")
        else:
            total_failed += 1
            error = result.get('error', 'Unknown error')
            print(f"  ❌ Failed — {error}")
    
    # Save report
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = LOGS_DIR / f"screener_run_{date_str}.json"
    
    report = {
        'date': date_str,
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total': len(ACTIVE_SCREENERS),
            'success': total_success,
            'failed': total_failed,
            'total_picks': total_picks
        },
        'results': results
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print("📊 Summary:")
    print(f"  Total screeners: {len(ACTIVE_SCREENERS)}")
    print(f"  ✅ Success: {total_success}")
    print(f"  ❌ Failed: {total_failed}")
    print(f"  🎯 Total picks: {total_picks}")
    print(f"\n📄 Report: {report_file}")
    print(f"{'='*60}")
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run All Screeners')
    parser.add_argument('--date', help='Date to run (YYYY-MM-DD)')
    parser.add_argument('--dry-run', action='store_true', help='Test mode')
    args = parser.parse_args()
    
    run_all_screeners(date_str=args.date, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
