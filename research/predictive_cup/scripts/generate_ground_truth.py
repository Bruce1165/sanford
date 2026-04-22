#!/usr/bin/env python3
"""
Ground Truth Dataset Generator - SIMPLE VERSION

Generates CSV with stocks that appeared in er_ban_hui_tiao or breakout_20day
as positive ground truth labels for Sept 2024 - May 2025 period.
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys

# Direct paths - avoid heredoc issues
DB_PATH = "/Users/mac/NeoTrade2/data/stock_data.db"
SCREENERS_DIR = "/Users/mac/NeoTrade2/data/screeners"
OUTPUT_DIR = "/Users/mac/NeoTrade2/research/predictive_cup/output/analysis"

TARGET1 = "er_ban_hui_tiao"
TARGET2 = "breakout_20day"
START_DATE = "2024-09-01"
END_DATE = "2025-05-26"

def main():
    print("Ground Truth Dataset Generator")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Target screeners: {TARGET1}, {TARGET2}")
    print()
    print("=" * 60)

    # Connect to database
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH, timeout=30)

    # Get all stocks
    print("Loading stock list...")
    cursor = conn.execute("SELECT code FROM stocks WHERE is_delisted = 0 ORDER BY code")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    print(f"Total stocks: {len(stocks)}")

    # Load target screener results
    print(f"Loading target screener results...")
    all_positive_codes = set()

    # Load er_ban_hui_tiao
    print(f"  Loading {TARGET1} results...")
    target1_file = SCREENERS_DIR + "/" + TARGET1 + "/" + START_DATE + ".xlsx"
    if Path(target1_file).exists():
        try:
            df1 = pd.read_excel(target1_file)
            for date, codes in df1.items():
                for code in codes:
                    all_positive_codes.add(code)
                    break
            print(f"  Processed {date}: {len(codes)} codes")
        except Exception as e:
            print(f"Error loading TARGET1: {e}")
            df1 = None
    else:
        print(f"TARGET1 file not found")
    else:
        print("Skipping TARGET1")

    # Load breakout_20day
    print(f" Loading {TARGET2} results...")
    target2_file = SCREENERS_DIR + "/" + TARGET2 + "/" + START_DATE + ".xlsx"
    if Path(target2_file).exists():
        try:
            df2 = pd.read_excel(target2_file)
            for date, codes in df2.items():
                for code in codes:
                    all_positive_codes.add(code)
                    break
            print(f"  Processed {date}: {len(codes)} codes")
        except Exception as e:
            print(f"Error loading TARGET2: {e}")
            df2 = None
    else:
        print(f"TARGET2 file not found")

    print("Finding positive stocks...")
    for stock in stocks:
        if stock in all_positive_codes:
            print(f"  Positive: {stock}")
        else:
            print(f"  Negative: {stock}")

    # Build dataset
    print("Building dataset...")
    records = []
    for stock in stocks:
        is_positive = stock in all_positive_codes
        records.append([stock, int(is_positive)])

    print(f"Dataset built: {len(records)} records")

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR + "ground_truth_" + timestamp + ".csv"

    # Define columns
    columns = ["code", "is_positive"]

    df = pd.DataFrame(records, columns=columns)
    df.to_csv(output_file, index=False)

    print("=" * 60)
    print(f" Total stocks: {len(stocks)}")
    print(f" Positive stocks: {len(all_positive_codes)}")
    print(f"  Negative stocks: {len(stocks) - len(all_positive_codes)}")
    print(f"  Positive rate: {len(all_positive_codes) / len(stocks) * 100:.1f}%")
    print(f" Output: {output_file}")
    print("=" * 60)

    return output_file

if __name__ == "__main__":
    main()
