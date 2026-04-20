#!/usr/bin/env python3
"""
Test Adapter Check - Helper script for adapter testing

This script provides a simple interface to test the ScreenerAdapter
by inserting test data and calling check_stock() method.

Author: Claude Code
Date: 2026-04-19
"""

import sqlite3
import json
import sys
from pathlib import Path


def check_screener(db_path: str, screener_id: str, stock_code: str,
                 stock_name: str, date: str) -> dict:
    """
    Call ScreenerAdapter.check_stock() for a single stock.

    Args:
        db_path: Path to database
        screener_id: Screener identifier
        stock_code: Stock code
        stock_name: Stock name
        date: Screening date

    Returns:
        Dict with screener result
    """
    # Import adapter from current directory (scripts/)
    # Add parent directory (NeoTrade2 root) to path for screeners import
    scripts_dir = str(Path(__file__).parent)
    project_root = str(Path(__file__).parent.parent)
    sys.path.insert(0, scripts_dir)
    sys.path.insert(0, project_root)

    # Import adapter module
    from pool_screener_adapter import ScreenerAdapter

    # Create adapter instance
    adapter = ScreenerAdapter(db_path)

    # Call check_stock
    result = adapter.check_stock(
        screener_id=screener_id,
        stock_code=stock_code,
        stock_name=stock_name,
        date=date
    )

    # Output result - always return success=True if adapter ran
    output = {
        'success': True,  # Adapter ran successfully even if no match
        'result': result
    }

    # Print as JSON for subprocess to parse
    print(json.dumps(output))
    sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Test Adapter Check Script')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='Database path')
    parser.add_argument('--screener-id', type=str, required=True, help='Screener ID to test')
    parser.add_argument('--stock-code', type=str, required=True, help='Stock code')
    parser.add_argument('--stock-name', type=str, default='TEST STOCK', help='Stock name')
    parser.add_argument('--date', type=str, required=True, help='Screening date')

    args = parser.parse_args()

    # Call check function
    check_screener(
        db_path=args.db_path,
        screener_id=args.screener_id,
        stock_code=args.stock_code,
        stock_name=args.stock_name,
        date=args.date
    )


if __name__ == '__main__':
    main()
