#!/usr/bin/env python3
"""
Step 1: Survey available screener data.

Scans data/screeners/ directory to identify:
- Which screeners have historical results
- Date ranges available for each screener
- Data completeness (missing dates, file corruption)
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add project root to path (NeoTrade2 directory)
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.insert(0, project_root)

from scripts.database import init_db, get_session

# Configuration
SCREENERS_DIR = Path('/Users/mac/NeoTrade2/data/screeners')
OUTPUT_DIR = Path('/Users/mac/NeoTrade2/research/predictive_cup/output/analysis')
OUTPUT_FILE = OUTPUT_DIR / f'screener_data_coverage_{datetime.now().strftime("%Y%m%d")}.csv'

# Known screeners (11 total)
KNOWN_SCREENERS = [
    'coffee_cup',
    'er_ban_hui_tiao',
    'jin_feng_huang',
    'yin_feng_huang',
    'shi_pan_xian',
    'zhang_ting_bei_liang_yin',
    'breakout_20day',
    'breakout_main',
    'daily_hot_cold',
    'shuang_shou_ban',
    'ashare_21'
]


def parse_date_from_filename(filename):
    """Extract date from filename like '2026-04-07.xlsx'"""
    try:
        base = filename.replace('.xlsx', '').replace('.xls', '')
        return datetime.strptime(base, '%Y-%m-%d').date()
    except ValueError:
        return None


def scan_screener_directory():
    """Scan all screener directories and collect metadata."""
    results = []

    for screener_name in KNOWN_SCREENERS:
        screener_path = SCREENERS_DIR / screener_name

        if not screener_path.exists():
            results.append({
                'screener': screener_name,
                'directory_exists': False,
                'total_files': 0,
                'date_range': 'N/A',
                'missing_days': 'N/A',
                'file_corruption': 'N/A',
                'notes': f'Directory not found: {screener_path}'
            })
            continue

        # Get all Excel files
        excel_files = list(screener_path.glob('*.xlsx')) + list(screener_path.glob('*.xls'))

        if not excel_files:
            results.append({
                'screener': screener_name,
                'directory_exists': True,
                'total_files': 0,
                'date_range': 'No files',
                'missing_days': 'N/A',
                'file_corruption': 'N/A',
                'notes': 'No Excel files found'
            })
            continue

        # Parse dates from filenames
        dates = [parse_date_from_filename(f.name) for f in excel_files]
        dates = [d for d in dates if d is not None]

        if not dates:
            results.append({
                'screener': screener_name,
                'directory_exists': True,
                'total_files': len(excel_files),
                'date_range': 'No valid dates',
                'missing_days': 'N/A',
                'file_corruption': 'N/A',
                'notes': f'{len(excel_files)} files but no valid date format'
            })
            continue

        dates.sort()

        # Calculate date range
        min_date = min(dates)
        max_date = max(dates)
        date_range_str = f"{min_date} to {max_date}"

        # Check for missing days (weekends excluded)
        date_set = set(dates)
        total_possible = (max_date - min_date).days + 1
        weekday_count = sum(1 for i in range(total_possible)
                          if (min_date + timedelta(days=i)).weekday() < 5)
        missing_days = weekday_count - len(dates)
        missing_pct = (missing_days / weekday_count * 100) if weekday_count > 0 else 0

        # Check for file corruption
        corrupted = []
        for excel_file in excel_files:
            try:
                pd.read_excel(excel_file, nrows=1)
            except Exception as e:
                corrupted.append(excel_file.name)

        results.append({
            'screener': screener_name,
            'directory_exists': True,
            'total_files': len(excel_files),
            'date_range': date_range_str,
            'missing_days': f'{missing_days} ({missing_pct:.1f}%)',
            'file_corruption': f'{len(corrupted)} files' if corrupted else 'None',
            'notes': ', '.join(corrupted) if corrupted else 'OK'
        })

    return pd.DataFrame(results)


def get_trading_calendar():
    """Get trading calendar from stock_data.db."""
    engine = init_db('/Users/mac/NeoTrade2/data/stock_data.db')
    session = get_session(engine)

    try:
        result = session.execute('''
            SELECT DISTINCT trade_date
            FROM daily_prices
            WHERE trade_date >= '2024-09-01'
            ORDER BY trade_date
        ''')
        trading_days = [row[0] for row in result.fetchall()]
        return set(trading_days)
    finally:
        session.close()


def main():
    """Main execution function."""
    print("=" * 60)
    print("Step 1: Surveying Screener Data Coverage")
    print("=" * 60)
    print()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Scan screeners
    df = scan_screener_directory()

    # Add summary statistics
    print("\n📊 Screener Data Coverage Summary:")
    print(df.to_string(index=False))

    print("\n📈 Coverage Statistics:")
    print(f"   Total screeners known: {len(KNOWN_SCREENERS)}")
    print(f"   Screeners with data: {df['directory_exists'].sum()}")
    print(f"   Screeners missing data: {(~df['directory_exists']).sum()}")
    print()

    # Check date coverage overlap
    if df['directory_exists'].sum() > 0:
        valid_df = df[df['directory_exists'] == True].copy()
        print("📅 Date Coverage (screeners with data):")

        for _, row in valid_df.iterrows():
            parts = row['date_range'].split(' to ')
            if len(parts) == 2:
                start = datetime.strptime(parts[0], '%Y-%m-%d')
                end = datetime.strptime(parts[1], '%Y-%m-%d')
                days = (end - start).days
                print(f"   {row['screener']:30} {days:3} days, {row['total_files']:3} files")

    # Check overall data quality
    print("\n⚠️  Data Quality Issues:")

    has_issues = False

    # Check for missing screeners
    missing_screeners = df[~df['directory_exists']]['screener'].tolist()
    if missing_screeners:
        print(f"   Missing screeners: {', '.join(missing_screeners)}")
        has_issues = True

    # Check for corrupt files
    corrupt_rows = df[df['file_corruption'] != 'None']
    if not corrupt_rows.empty:
        print("   Screeners with corrupt files:")
        for _, row in corrupt_rows.iterrows():
            print(f"      {row['screener']}: {row['file_corruption']}")
        has_issues = True

    # Check for high missing day percentages
    if 'missing_days' in df.columns:
        # Filter for rows with valid missing_days data (containing percentage)
        valid_missing = df[df['missing_days'].str.contains(r'\(\d+\.\d+%\)', na=False)]
        for _, row in valid_missing.iterrows():
            # Extract percentage from string like "3 (50.0%)"
            missing_str = row['missing_days']
            try:
                if '(' in missing_str and '%' in missing_str:
                    missing_pct = float(missing_str.split('(')[1].split('%')[0])
                    if missing_pct > 20:
                        print(f"   {row['screener']}: High missing data ({row['missing_days']})")
                        has_issues = True
            except (ValueError, IndexError):
                pass

    if not has_issues:
        print("   No major data quality issues detected.")

    # Save results
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"\n✅ Results saved to: {OUTPUT_FILE}")

    # Summary for Phase 1 planning
    print("\n" + "=" * 60)
    print("Phase 1 Planning Summary:")
    print("=" * 60)

    # Find date range coverage
    if df['directory_exists'].sum() > 0:
        valid_df = df[df['directory_exists'] == True]
        all_dates = []
        for _, row in valid_df.iterrows():
            parts = row['date_range'].split(' to ')
            if len(parts) == 2:
                start = datetime.strptime(parts[0], '%Y-%m-%d')
                end = datetime.strptime(parts[1], '%Y-%m-%d')
                all_dates.append((start, end))

        if all_dates:
            min_start = min(d[0] for d in all_dates)
            max_end = max(d[1] for d in all_dates)
            total_days = (max_end - min_start).days
            months = total_days / 30.44  # Average days per month

            print(f"\n📅 Overall Data Coverage:")
            print(f"   Start date: {min_start}")
            print(f"   End date: {max_end}")
            print(f"   Total span: {total_days} days (~{months:.1f} months)")

            if months >= 18:
                print(f"   ✅ Meets 18+ month requirement")
            else:
                print(f"   ⚠️  Below 18 month requirement ({months:.1f} months available)")

    print()


if __name__ == '__main__':
    main()
