#!/usr/bin/env python3
"""
Daily Screener Monitoring — Automatic Evaluation

Runs daily after market close to evaluate all active screener picks.
For Coffee Cup: Automatically checks failure/success conditions.

Usage:
    python3 scripts/daily_screener_monitor.py
    python3 scripts/daily_screener_monitor.py --dry-run  # Test mode
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# Setup paths
WORKSPACE = Path(os.environ.get('WORKSPACE_ROOT', str(Path(__file__).parent.parent)))
sys.path.insert(0, str(WORKSPACE / 'scripts'))

from screener_monitor import ScreenerMonitor

DB_PATH = WORKSPACE / 'data' / 'stock_data.db'


def get_today_close_price(stock_code: str, trade_date: str) -> float:
    """Get today's closing price for a stock"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "SELECT close FROM daily_prices WHERE code = ? AND trade_date = ?",
            (stock_code, trade_date)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def run_daily_evaluation(dry_run: bool = False):
    """Run daily evaluation for all active picks"""
    monitor = ScreenerMonitor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n{'='*60}")
    print(f"📊 Daily Screener Monitoring — {today}")
    print(f"{'='*60}")
    
    # Get all active picks
    active_picks = monitor.get_active_picks()
    
    if not active_picks:
        print("✅ No active picks to evaluate")
        return
    
    print(f"Found {len(active_picks)} active picks\n")
    
    evaluated = 0
    graduated = 0
    failed = 0
    continued = 0
    errors = 0
    
    for pick in active_picks:
        print(f"#{pick.id}: {pick.screener_id}/{pick.stock_code} (Day {pick.get_current_day() + 1}/25)")
        
        if dry_run:
            print("  [DRY RUN] Skipping evaluation")
            continue
        
        try:
            # Get today's close price
            close_price = get_today_close_price(pick.stock_code, today)
            
            if close_price is None:
                print(f"  ⚠️ No price data for today, skipping")
                continue
            
            # Process daily check with automatic evaluation
            result = monitor.process_daily_check(
                pick_id=pick.id,
                check_date=today,
                close_price=close_price
            )
            
            if 'error' in result:
                print(f"  ❌ Error: {result['error']}")
                errors += 1
                continue
            
            action = result['action']
            
            if action == 'graduate_early':
                print(f"  🎓 EARLY GRADUATION! {result['note']}")
                graduated += 1
            elif action == 'fail':
                print(f"  ❌ FAILED: {result['note']}")
                failed += 1
            else:
                print(f"  ✓ Continue tracking @ ¥{close_price:.2f}")
                continued += 1
            
            evaluated += 1
            
        except Exception as e:
            print(f"  ❌ Exception: {e}")
            errors += 1
    
    print(f"\n{'='*60}")
    print("📈 Summary:")
    print(f"  Evaluated: {evaluated}")
    print(f"  Graduated (early): {graduated}")
    print(f"  Failed: {failed}")
    print(f"  Continue tracking: {continued}")
    print(f"  Errors: {errors}")
    print(f"{'='*60}")
    
    # Auto-check normal graduations (reached 25 days)
    auto_graduated = monitor.auto_check_graduations(today)
    if auto_graduated:
        print(f"\n🎓 Auto-graduated (reached 25 days): {len(auto_graduated)} picks")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Daily Screener Monitoring')
    parser.add_argument('--dry-run', action='store_true', help='Test mode (no actual updates)')
    args = parser.parse_args()
    
    run_daily_evaluation(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
