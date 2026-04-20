"""
Pool Screener Orchestrator - Coordinate LYT and 5 pool screeners

This script runs:
1. LYT screener - builds/updates stock pool
2. 5 pool screeners - run against pool (once per date)

Tracks which dates have been screened to avoid duplicate runs.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import date, datetime

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "screeners"))

from screeners.pool_integration import get_db_path, run_pool_screening
from lao_ya_tou_zhou_xian_screener import LaoYaTouZhouXianScreener
from er_ban_hui_tiao_screener import ErBanHuiTiaoScreener
from shi_pan_xian_screener import ShiPanXianScreener
from jin_feng_huang_screener import JinFengHuangScreener
from yin_feng_huang_screener import YinFengHuangScreener
from zhang_ting_bei_liang_yin_screener import ZhangTingBeiLiangYinScreener

logger = logging.getLogger(__name__)

# Pool screener codes
POOL_SCREENER_CODES = {
    'er_ban_hui_tiao': ErBanHuiTiaoScreener,
    'shi_pan_xian': ShiPanXianScreener,
    'jin_feng_huang': JinFengHuangScreener,
    'yin_feng_huang': YinFengHuangScreener,
    'zhang_ting_bei_liang_yin': ZhangTingBeiLiangYinScreener
}


def get_screened_dates(db_path: Path) -> set[str]:
    """
    Get all dates that have been screened by LYT.

    Args:
        db_path: Path to database

    Returns:
        Set of date strings (YYYY-MM-DD)
    """
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    query = """
        SELECT DISTINCT screen_date
        FROM pool_screening_results
        WHERE screener_id = 1
        ORDER BY screen_date DESC
    """
    results = conn.execute(query).fetchall()
    conn.close()

    return {row['screen_date'] for row in results}


def run_lyt_screener(target_date: str) -> dict:
    """
    Run LYT screener to build/update pool.

    Args:
        target_date: Date string YYYY-MM-DD

    Returns:
        Summary dict with pool stats
    """
    logger.info("=" * 70)
    logger.info("STEP 1: Running LYT Screener (Pool Builder)")
    logger.info("=" * 70)
    logger.info(f"Target date: {target_date}")

    screener = LaoYaTouZhouXianScreener()
    screener.current_date = target_date

    results, summary = screener.run()

    logger.info(f"LYT Summary:")
    logger.info(f"  Processed: {summary.get('processed', 0)} stocks")
    logger.info(f"  Pool inserted: {summary.get('pool_inserted', 0)}")
    logger.info(f"  Pool updated: {summary.get('pool_updated', 0)}")
    logger.info(f"  Hits: {summary.get('hits', 0)}")
    logger.info(f"  Pool size: {summary.get('pool_size', 0)}")
    logger.info(f"  Signal distribution: {summary.get('pool_signal_distribution', {})}")

    return summary


def run_pool_screeners(target_date: str) -> dict:
    """
    Run 5 pool screeners against the pool.

    Args:
        target_date: Date string YYYY-MM-DD

    Returns:
        Summary dict with combined results
    """
    logger.info("=" * 70)
    logger.info("STEP 2: Running 5 Pool Screeners")
    logger.info("=" * 70)
    logger.info(f"Target date: {target_date}")

    all_results = []
    all_summaries = {}

    for screener_code, screener_class in POOL_SCREENER_CODES.items():
        logger.info(f"\n--- Running {screener_code} ---")

        # Create screener instance with use_pool=True
        screener_instance = screener_class(use_pool=True)

        # Set current date
        screener_instance.current_date = target_date

        # Run pool screening using pool_integration module
        results, summary = run_pool_screening(
            screener_instance,
            screener_code,
            target_date
        )

        all_results.extend(results)
        all_summaries[screener_code] = summary

        logger.info(f"{screener_code}: {summary.get('hits', 0)} hits")

    logger.info("\n--- Pool Screeners Complete ---")
    logger.info(f"Total pool screening hits: {len(all_results)}")

    return all_summaries


def run_daily_pool_system(target_date: str, force_rescreen: bool = False):
    """
    Run complete daily pool system:
    1. Check if date already screened
    2. If yes, skip LYT, only run pool screeners
    3. If no or force_rescreen, run LYT then pool screeners

    Args:
        target_date: Date string YYYY-MM-DD
        force_rescreen: If True, force LYT to run even if already screened

    Returns:
        Combined summary dict
    """
    db_path = get_db_path()
    screened_dates = get_screened_dates(db_path)

    lyt_already_screened = target_date in screened_dates

    if not lyt_already_screened or force_rescreen:
        # Run LYT to build/update pool
        lyt_summary = run_lyt_screener(target_date)
    else:
        logger.info(f"Date {target_date} already screened by LYT, skipping LYT run")
        logger.info(f"Screened dates: {sorted(screened_dates, reverse=True)}")
        lyt_summary = {'skipped': True, 'date': target_date}

    # Always run pool screeners (they should run daily)
    pool_summaries = run_pool_screeners(target_date)

    # Combine results
    combined_summary = {
        'target_date': target_date,
        'lyt': lyt_summary,
        'pool_screeners': pool_summaries,
        'lyt_already_screened': lyt_already_screened
    }

    logger.info("=" * 70)
    logger.info("DAILY POOL SYSTEM COMPLETE")
    logger.info("=" * 70)

    return combined_summary


def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    parser = argparse.ArgumentParser(description='Run LYT and 5 pool screeners')
    parser.add_argument(
        '--date',
        type=str,
        help='Target date YYYY-MM-DD (default: latest available)'
    )
    parser.add_argument(
        '--force-rescreen',
        action='store_true',
        help='Force LYT to re-run even if date already screened'
    )
    parser.add_argument(
        '--check-date',
        action='store_true',
        help='Check which dates have been screened'
    )

    args = parser.parse_args()

    # Check date mode
    if args.check_date:
        db_path = get_db_path()
        screened_dates = get_screened_dates(db_path)
        logger.info("Screened dates by LYT:")
        for d in sorted(screened_dates, reverse=True):
            logger.info(f"  {d}")
        return

    # Determine target date
    if args.date:
        target_date = args.date
    else:
        # Get latest date from daily_prices
        import sqlite3
        conn = sqlite3.connect(str(get_db_path()))
        result = conn.execute(
            "SELECT MAX(trade_date) FROM daily_prices"
        ).fetchone()
        conn.close()

        if result and result[0]:
            target_date = result[0]
        else:
            logger.error("No data available in database")
            return

    logger.info(f"Running daily pool system for date: {target_date}")

    # Run daily pool system
    summary = run_daily_pool_system(target_date, args.force_rescreen)

    # Print final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Target Date: {summary['target_date']}")
    print(f"\nLYT Screener:")
    lyt_summ = summary['lyt']
    if lyt_summ.get('skipped'):
        print(f"  Status: SKIPPED (already screened)")
    else:
        print(f"  Processed: {lyt_summ.get('processed', 0)} stocks")
        print(f"  Pool inserted: {lyt_summ.get('pool_inserted', 0)}")
        print(f"  Pool updated: {lyt_summ.get('pool_updated', 0)}")
        print(f"  Hits: {lyt_summ.get('hits', 0)}")
        print(f"  Pool size: {lyt_summ.get('pool_size', 0)}")

    print(f"\nPool Screeners:")
    for screener_code, summ in summary['pool_screeners'].items():
        print(f"  {screener_code}:")
        print(f"    Hits: {summ.get('hits', 0)}")
        print(f"    Processed: {summ.get('processed', 0)}")

    print("=" * 70)


if __name__ == "__main__":
    main()
