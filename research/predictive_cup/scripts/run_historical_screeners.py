#!/usr/bin/env python3
"""
Historical Screener Backfill Script

Runs all 11 screeners for each historical trading day to generate
missing screener results for Phase 1 research.

This script is designed to:
1. Read historical trading days from stock_data.db
2. Run each screener for each date
3. Track progress and handle errors gracefully
4. Skip dates that already have results
5. Avoid interference with running dashboard (port 8765)
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import signal

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
sys.path.insert(0, project_root)

# Configuration
TRADING_DAYS_FILE = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/historical_trading_days.txt')  # Full historical data
# TRADING_DAYS_FILE = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/test_trading_days.txt')  # Test with 5 days
SCREENERS_DIR = Path('/Users/mac/NeoTrade2/data/screeners')
PROGRESS_FILE = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/backfill_progress.json')
LOG_FILE = Path('/Users/mac/NeoTrade2/logs/historical_screener_backfill.log')

# All 11 screeners
SCREENERS = [
    'coffee_cup',
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'er_ban_hui_tiao',
    'zhang_ting_bei_liang_yin',
    'breakout_20day',
    'breakout_main',
    'daily_hot_cold',
    'shuang_shou_ban',
    'ashare_21'
]

# Screener script paths (absolute paths from NeoTrade2 root)
SCREENER_SCRIPTS = {
    'coffee_cup': '/Users/mac/NeoTrade2/screeners/coffee_cup_screener.py',
    'jin_feng_huang': '/Users/mac/NeoTrade2/screeners/jin_feng_huang_screener.py',
    'yin_feng_huang': '/Users/mac/NeoTrade2/screeners/yin_feng_huang_screener.py',
    'shi_pan_xian': '/Users/mac/NeoTrade2/screeners/shi_pan_xian_screener.py',
    'er_ban_hui_tiao': '/Users/mac/NeoTrade2/screeners/er_ban_hui_tiao_screener.py',
    'zhang_ting_bei_liang_yin': '/Users/mac/NeoTrade2/screeners/zhang_ting_bei_liang_yin_screener.py',
    'breakout_20day': '/Users/mac/NeoTrade2/screeners/breakout_20day_screener.py',
    'breakout_main': '/Users/mac/NeoTrade2/screeners/breakout_main_screener.py',
    'daily_hot_cold': '/Users/mac/NeoTrade2/screeners/daily_hot_cold_screener.py',
    'shuang_shou_ban': '/Users/mac/NeoTrade2/screeners/shuang_shou_ban_screener.py',
    'ashare_21': '/Users/mac/NeoTrade2/screeners/ashare_21_screener.py'
}

# Graceful shutdown handler
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print("\n\n🛑 Shutdown signal received. Saving progress...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log_message(message):
    """Write message to log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)
    print(message)

def load_progress():
    """Load previous progress from progress file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('completed_runs', 0), data.get('current_date', ''), data.get('current_screener', '')
    return 0, '', ''

def save_progress(completed_runs, current_date='', current_screener=''):
    """Save progress to file."""
    progress = {
        'completed_runs': completed_runs,
        'current_date': current_date,
        'current_screener': current_screener,
        'last_updated': datetime.now().isoformat()
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def screener_result_exists(screener, date):
    """Check if screener result already exists for given date."""
    screener_dir = SCREENERS_DIR / screener
    if not screener_dir.exists():
        return False

    # Check for xlsx or xls file with this date
    date_str = date.replace('-', '')
    xlsx_file = screener_dir / f'{date_str}.xlsx'
    xls_file = screener_dir / f'{date_str}.xls'

    return xlsx_file.exists() or xls_file.exists()

def run_screener(screener, date_str):
    """Run a single screener for a specific date."""
    script_path = SCREENER_SCRIPTS[screener]

    if not Path(script_path).exists():
        error_msg = f"Screener script not found: {script_path}"
        log_message(f"❌ {error_msg}")
        return False, error_msg

    try:
        log_message(f"🚀 Running {screener} for {date_str}")

        # Run the screener (with PYTHONPATH to find config.py)
        env = os.environ.copy()
        env['PYTHONPATH'] = '/Users/mac/NeoTrade2/scripts'

        result = subprocess.run(
            ['python3', script_path, '--date', date_str],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes max per screener
            cwd='/Users/mac/NeoTrade2',
            env=env
        )

        if result.returncode == 0:
            log_message(f"✅ {screener} completed for {date_str}")
            return True, None
        else:
            error_msg = f"{screener} failed with return code {result.returncode}"
            log_message(f"❌ {error_msg}")
            if result.stderr:
                log_message(f"   STDERR: {result.stderr[:200]}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = f"{screener} timed out after 5 minutes"
        log_message(f"⏱️  {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"{screener} failed with exception: {str(e)}"
        log_message(f"❌ {error_msg}")
        return False, error_msg

def calculate_progress(completed_runs, total_runs):
    """Calculate progress percentage."""
    if total_runs == 0:
        return 0
    return (completed_runs / total_runs) * 100

def estimate_remaining_time(completed_runs, total_runs, start_time):
    """Estimate remaining time based on completed runs."""
    if completed_runs == 0:
        return "Calculating..."

    elapsed = time.time() - start_time
    avg_time_per_run = elapsed / completed_runs
    remaining_runs = total_runs - completed_runs
    estimated_seconds = remaining_runs * avg_time_per_run

    hours = int(estimated_seconds // 3600)
    minutes = int((estimated_seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

def main():
    """Main execution function."""
    log_message("=" * 70)
    log_message("Historical Screener Backfill Started")
    log_message("=" * 70)

    # Create log directory
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load trading days
    if not TRADING_DAYS_FILE.exists():
        error_msg = f"Trading days file not found: {TRADING_DAYS_FILE}"
        log_message(f"❌ {error_msg}")
        print(error_msg)
        print("Please run trading days identification script first.")
        return

    with open(TRADING_DAYS_FILE, 'r') as f:
        trading_days = [line.strip() for line in f if line.strip()]

    log_message(f"📅 Found {len(trading_days)} trading days")
    log_message(f"📊 Total screeners: {len(SCREENERS)}")
    log_message(f"🎯 Total screener runs: {len(trading_days) * len(SCREENERS)}")

    # Calculate total runs (accounting for existing results)
    total_runs = 0
    pending_runs = 0

    for date in trading_days:
        for screener in SCREENERS:
            if not screener_result_exists(screener, date):
                pending_runs += 1
            total_runs += 1

    existing_runs = total_runs - pending_runs
    log_message(f"📁 Existing results: {existing_runs} runs")
    log_message(f"⏳ Pending runs: {pending_runs} runs")

    # Load previous progress
    completed_runs, current_date, current_screener = load_progress()
    log_message(f"📈 Loaded progress: {completed_runs} completed runs")
    if current_date:
        log_message(f"📍 Current: {current_screener} @ {current_date}")

    start_time = time.time()
    screener_count = 0
    date_count = 0
    error_count = 0

    # Process each trading day
    for date in trading_days:
        if shutdown_requested:
            log_message("🛑 Shutdown requested, saving progress...")
            break

        date_count += 1

        # Process each screener
        for screener in SCREENERS:
            if shutdown_requested:
                break

            screener_count += 1

            # Skip if already exists
            if screener_result_exists(screener, date):
                continue

            # Update progress
            save_progress(completed_runs, date, screener)

            # Run screener
            success, error = run_screener(screener, date)

            if success:
                completed_runs += 1
            else:
                error_count += 1

            # Progress report every 10 runs
            if screener_count % 10 == 0:
                progress = calculate_progress(completed_runs, pending_runs)
                remaining = estimate_remaining_time(completed_runs, pending_runs, start_time)
                log_message(f"📊 Progress: {progress:.1f}% | {completed_runs}/{pending_runs} completed | ETA: {remaining}")

                # Clear line for next update
                print(f"Progress: {progress:.1f}% | {completed_runs}/{pending_runs} | ETA: {remaining}           ", end='\r', flush=True)

    # Final progress report
    progress = calculate_progress(completed_runs, pending_runs)
    log_message("\n" + "=" * 70)
    log_message("Historical Screener Backfill Completed")
    log_message("=" * 70)
    log_message(f"📊 Total runs: {completed_runs + existing_runs}")
    log_message(f"✅ Successful runs: {completed_runs}")
    log_message(f"❌ Error runs: {error_count}")
    log_message(f"📈 Completion rate: {progress:.1f}%")

    elapsed_time = time.time() - start_time
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    log_message(f"⏱️  Total time: {hours}h {minutes}m")

    # Save final progress
    save_progress(completed_runs, 'COMPLETED', 'COMPLETED')

    print("\n✅ Backfill completed!")
    print(f"   Total runs: {completed_runs + existing_runs}")
    print(f"   Successful: {completed_runs}")
    print(f"   Errors: {error_count}")
    print(f"   Time: {hours}h {minutes}m")
    print(f"\n📄 Log file: {LOG_FILE}")

if __name__ == '__main__':
    main()
