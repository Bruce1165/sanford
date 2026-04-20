#!/usr/bin/env python3
"""
Upload Lao Ya Tou Pool - Command line Excel file uploader

This script allows uploading Excel files to the lao_ya_tou_pool database table
from the command line, useful before frontend UI is ready.

Usage:
    python3 scripts/upload_lao_ya_tou_pool.py <excel_file_path>

Author: Claude Code
Date: 2026-04-19
"""

import sys
import logging
from pathlib import Path

import pandas as pd

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from database.lao_ya_tou_pool import LaoYaTouPoolRepository


def parse_excel_date_format(date_value):
    """
    Parse various Excel date formats to string format.

    Args:
        date_value: Date value from Excel (could be various formats)

    Returns:
        str: Date in 'YYYY-MM-DD' format
    """
    if pd.isna(date_value) or date_value is None:
        return None

    # If already a string, try to parse it
    if isinstance(date_value, str):
        date_value = date_value.strip()
        try:
            # Try common Chinese date formats
            if '年' in date_value:
                # Format: 2026年4月1日 or 2026年04月01日
                date_value = date_value.replace('年', '-').replace('月', '-').replace('日', '')
            from datetime import datetime
            dt = datetime.strptime(date_value, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            pass
        return date_value

    # If it's an Excel serial date
    if isinstance(date_value, (int, float)):
        from datetime import datetime, timedelta
        # Excel epoch is 1900-01-01, but Excel incorrectly treats 1900 as a leap year
        # So we use 1899-12-30 as the epoch
        excel_epoch = datetime(1899, 12, 30)
        dt = excel_epoch + timedelta(days=int(date_value))
        return dt.strftime('%Y-%m-%d')

    # If it's a datetime object
    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%Y-%m-%d')

    return str(date_value)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def upload_excel_file(excel_file_path: str) -> dict:
    """
    Upload Excel file to lao_ya_tou_pool database table.

    Args:
        excel_file_path: Path to Excel file

    Returns:
        dict with upload results
    """
    # Initialize repository
    repo = LaoYaTouPoolRepository('data/stock_data.db')

    # Check file exists
    file_path = Path(excel_file_path)
    if not file_path.exists():
        logger.error(f"Excel file not found: {excel_file_path}")
        return {'success': False, 'error': 'File not found'}

    # Parse Excel file
    logger.info(f"Parsing Excel file: {excel_file_path}")
    try:
        import pandas as pd
        df = pd.read_excel(excel_file_path, dtype={'股票代码': str})  # Ensure stock codes are strings
    except Exception as e:
        logger.error(f"Failed to read Excel file: {e}")
        return {'success': False, 'error': str(e)}

    # Validate required columns
    # Support both Chinese and simplified column names
    column_mappings = {
        '股票代码': ['代码', '股票代码', 'stock_code', 'code'],
        '股票名称': ['名称', '股票名称', '名称(1039)', 'stock_name', 'name'],
        '开始日期': ['开始日期', 'start_date'],
        '结束日期': ['结束日期', 'end_date']
    }

    # Find the actual column names in the Excel
    stock_code_col = None
    stock_name_col = None
    start_date_col = None
    end_date_col = None

    for target_name, possible_names in column_mappings.items():
        for col in df.columns:
            for possible_name in possible_names:
                if possible_name.lower() in str(col).lower():
                    if target_name == '股票代码':
                        stock_code_col = col
                    elif target_name == '股票名称':
                        stock_name_col = col
                    elif target_name == '开始日期':
                        start_date_col = col
                    elif target_name == '结束日期':
                        end_date_col = col
                    break
            if locals().get(f'{target_name[:-3]}_col'):
                break

    if not stock_code_col or not stock_name_col:
        missing = []
        if not stock_code_col:
            missing.append('股票代码')
        if not stock_name_col:
            missing.append('股票名称')
        logger.error(f"Missing required columns: {missing}")
        logger.info(f"Available columns: {list(df.columns)}")
        return {'success': False, 'error': f'Missing columns: {missing}'}

    # Process each row
    success_count = 0
    error_count = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            stock_code = str(row[stock_code_col]).strip()
            stock_name = str(row[stock_name_col]).strip()

            # Extract start_date and end_date if available
            start_date = None
            end_date = None

            if start_date_col:
                start_date = parse_excel_date_format(row[start_date_col])
            if end_date_col:
                end_date = parse_excel_date_format(row[end_date_col])

            # Default date range if not specified
            if not start_date:
                start_date = '2026-04-01'
            if not end_date:
                end_date = '2026-04-30'

            # Insert into database
            pool_id = repo.insert_pool_record(
                stock_code=stock_code,
                stock_name=stock_name,
                start_date=start_date,
                end_date=end_date,
                file_name=file_path.name
            )

            success_count += 1
            logger.info(f"✓ Uploaded: {stock_code} {stock_name} (ID: {pool_id})")

        except Exception as e:
            error_count += 1
            error_msg = f"Row {idx}: {e}"
            errors.append(error_msg)
            logger.error(f"✗ Error: {error_msg}")

    # Summary
    total_count = success_count + error_count

    logger.info(f"=" * 60)
    logger.info(f"Upload Complete:")
    logger.info(f"  Total: {total_count}")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors: {error_count}")

    if errors:
        logger.info(f"First error: {errors[0]}")

    return {
        'success': True,
        'total': total_count,
        'uploaded': success_count,
        'errors': error_count,
        'error_details': errors[:5]  # First 5 errors
    }


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/upload_lao_ya_tou_pool.py <excel_file_path>")
        print("\nExample:")
        print("  python3 scripts/upload_lao_ya_tou_pool.py data/my_stock_pool.xlsx")
        print("\nRequired Excel columns:")
        print("  - 股票代码 (Stock Code)")
        print("  - 股票名称 (Stock Name)")
        print("Optional columns:")
        print("  - 开始日期 (Start Date)")
        print("  - 结束日期 (End Date)")
        sys.exit(1)

    excel_file_path = sys.argv[1]
    result = upload_excel_file(excel_file_path)

    if result['success']:
        print(f"\n✓ Successfully uploaded {result['uploaded']} stock(s) to 老鸭头股票池")
        sys.exit(0)
    else:
        print(f"\n✗ Upload failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
