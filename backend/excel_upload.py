#!/usr/bin/env python3
"""
Excel Upload Handler - Process uploaded stock data Excel files

Handles:
- File validation (format, encoding, columns)
- Data parsing and conversion
- Database updates (daily_prices, stocks, stock_meta)
- Error handling and reporting
"""
import pandas as pd
import sqlite3
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Database paths
WORKSPACE_ROOT = Path(__file__).parent.parent
DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"


class ExcelUploadHandler:
    """Handle Excel file upload and database update"""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or DB_PATH)
        self.conn: sqlite3.Connection = None

    def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def validate_file_format(self, file_path: str) -> Tuple[bool, str, Dict]:
        """
        Validate file format before processing

        Returns:
            (is_valid, error_message, metadata)
        """
        file_path = Path(file_path)
        metadata = {}

        # Check file extension
        if file_path.suffix not in ['.xls', '.xlsx']:
            return False, "文件格式错误：只支持 .xls 或 .xlsx 文件", metadata

        # Extract date from filename
        filename = file_path.name
        date_match = re.search(r'全部Ａ股(\d{8})\.', filename)
        if not date_match:
            return False, "文件名格式错误：应为 '全部Ａ股YYYYMMDD.xls'", metadata

        date_str = date_match.group(1)
        try:
            trade_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            datetime.strptime(trade_date, '%Y-%m-%d')
            metadata['trade_date'] = trade_date
        except ValueError:
            return False, f"文件名中的日期格式错误: {date_str}", metadata

        return True, "", metadata

    def read_excel_file(self, file_path: str) -> Tuple[bool, str, pd.DataFrame]:
        """
        Read Excel/TSV file with multiple encoding support

        Returns:
            (is_valid, error_message, dataframe)
        """
        encodings = ['gbk', 'utf-8', 'gb18030', 'gb2312', 'iso-8859-1']
        logger.info(f"Attempting to read file: {file_path}")

        for encoding in encodings:
            try:
                logger.info(f"Trying encoding: {encoding} with C engine")
                # Try with different error handling for pandas
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    delimiter='\t',
                    low_memory=False,
                    on_bad_lines='warn',  # Skip problematic lines
                    engine='c'  # Use C engine for better performance
                )

                # Validate required columns
                required_columns = ['代码', '名称', '今开', '最高', '最低', '现价', '昨收', '涨幅%', '总量', '总金额', '换手%']
                missing_columns = [col for col in required_columns if col not in df.columns]

                if missing_columns:
                    return False, f"缺少必需列: {', '.join(missing_columns)}", df

                logger.info(f"Successfully read file with encoding: {encoding}, rows: {len(df)}")
                return True, "", df

            except UnicodeDecodeError as ue:
                logger.warning(f"UnicodeDecodeError with {encoding}: {ue}")
                continue
            except Exception as e:
                error_str = str(e)
                logger.warning(f"Exception with {encoding} (C engine): {error_str}")
                if "required columns" in error_str.lower():
                    return False, f"缺少必需列: {error_str}", df
                # Try with python engine as fallback
                try:
                    logger.info(f"Trying encoding: {encoding} with Python engine")
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        delimiter='\t',
                        low_memory=False,
                        on_bad_lines='warn',
                        engine='python'  # Use python engine as fallback
                    )

                    required_columns = ['代码', '名称', '今开', '最高', '最低', '现价', '昨收', '涨幅%', '总量', '总金额', '换手%']
                    missing_columns = [col for col in required_columns if col not in df.columns]

                    if missing_columns:
                        return False, f"缺少必需列: {', '.join(missing_columns)}", df

                    logger.info(f"Successfully read file with encoding: {encoding} (Python engine), rows: {len(df)}")
                    return True, "", df
                except Exception as e2:
                    logger.warning(f"Failed with python engine ({encoding}): {e2}")
                    continue

        return False, "文件编码或格式错误：无法读取文件（尝试过 GBK/UTF-8/GB18030/GB2312/ISO-8859-1）", None

    def clean_stock_code(self, code: str) -> str:
        """Clean stock code: remove =" and " wrapping"""
        if pd.isna(code):
            return None
        code = str(code).strip()
        # Remove Excel formula formatting
        code = code.replace('="', '').replace('"', '')
        return code if code else None

    def parse_sector_field(self, sector: str) -> Tuple[str, str]:
        """
        Parse sector field: '一级行业-二级行业' → ('一级行业', '二级行业')
        """
        if pd.isna(sector) or not sector:
            return None, None

        sector = str(sector).strip()
        if '-' in sector:
            parts = sector.split('-', 1)
            return parts[0].strip(), parts[1].strip()
        return sector, None

    def convert_value(self, value, field_type: str) -> Any:
        """
        Convert string value to appropriate type

        Args:
            value: Raw string value from Excel
            field_type: Type to convert to ('float', 'int', 'amount', 'market_cap', 'date')

        Returns:
            Converted value or None if invalid
        """
        if pd.isna(value) or value == '--' or value == '':
            return None

        value = str(value).strip()

        try:
            if field_type == 'float':
                return float(value)
            elif field_type == 'int':
                return int(float(value))
            elif field_type == 'amount':
                # Excel uses 万元 (10,000 yuan)
                return float(value) * 10000
            elif field_type == 'market_cap':
                # Excel uses 亿 (100,000,000 yuan)
                return float(value.replace('亿', '')) * 100000000
            elif field_type == 'date':
                # Format: 20260401 → 2026-04-01
                if len(value) == 8:
                    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
                return value
            else:
                return value
        except (ValueError, AttributeError):
            return None

    def validate_record(self, row: pd.Series) -> Tuple[bool, str]:
        """
        Validate a single record

        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        code = self.clean_stock_code(row['代码'])
        if not code or len(code) != 6:
            return False, f"股票代码格式错误: {row['代码']}"

        # Check if stock is suspended (开盘、最高、最低都是 --)
        # 停牌股票：今开、最高、最低 都是 --  （现价和昨收可能有值）
        realtime_fields = ['今开', '最高', '最低']
        is_suspended = all(
            self.convert_value(row[field], 'float') is None
            for field in realtime_fields
        )

        # If not suspended, validate numeric fields
        if not is_suspended:
            for field in ['今开', '最高', '最低', '现价', '昨收']:
                value = self.convert_value(row[field], 'float')
                if value is None:
                    return False, f"{field} 值无效: {row[field]}"
                if value < 0:
                    return False, f"{field} 不能为负数: {value}"

        # Validate volume (停牌股票 volume 也不一定是 0)
        volume = self.convert_value(row['总量'], 'float')
        if volume is not None and volume < 0:
            return False, f"总量不能为负数: {volume}"

        return True, ""

    def process_daily_prices(self, df: pd.DataFrame, trade_date: str) -> Dict[str, Any]:
        """
        Process and update daily_prices table

        Returns:
            Processing result with counts
        """
        results = {
            'total': len(df),
            'success': 0,
            'failed': 0,
            'errors': [],
            'warnings': []  # Add warnings list
        }

        try:
            cursor = self.conn.cursor()

            for idx, row in df.iterrows():
                # Validate record
                is_valid, error_msg = self.validate_record(row)
                if not is_valid:
                    results['failed'] += 1
                    results['errors'].append(f"Row {idx+2}: {error_msg}")
                    continue

                # Clean and convert data
                code = self.clean_stock_code(row['代码'])

                # Convert numeric fields
                open_price = self.convert_value(row['今开'], 'float')
                high_price = self.convert_value(row['最高'], 'float')
                low_price = self.convert_value(row['最低'], 'float')
                close_price = self.convert_value(row['现价'], 'float')
                preclose = self.convert_value(row['昨收'], 'float')
                pct_change = self.convert_value(row['涨幅%'], 'float')
                volume = self.convert_value(row['总量'], 'float')
                amount = self.convert_value(row['总金额'], 'amount')
                turnover = self.convert_value(row['换手%'], 'float')

                # Check if stock is suspended (realtime fields: open, high, low are None)
                realtime_prices = [open_price, high_price, low_price]
                is_suspended = all(v is None for v in realtime_prices)

                # Insert or replace
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_prices
                    (code, trade_date, open, high, low, close, preclose, pct_change, volume, amount, turnover, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code, trade_date, open_price, high_price, low_price, close_price,
                    preclose, pct_change, volume, amount, turnover, datetime.now()
                ))

                # If not suspended, update last_trade_date in stocks table
                if not is_suspended:
                    cursor.execute('''
                        UPDATE stocks
                        SET last_trade_date = ?, updated_at = ?
                        WHERE code = ?
                    ''', (trade_date, datetime.now(), code))

                results['success'] += 1
                if is_suspended:
                    results['warnings'].append(f"{code} {row.get('名称', '')} 停牌")

            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to process daily_prices: {e}")
            raise

        return results

    def process_stock_metadata(self, df: pd.DataFrame, force_update: bool = False) -> Dict[str, Any]:
        """
        Process and update stocks and stock_meta tables

        Args:
            df: DataFrame with stock data
            force_update: If True, completely replace records (Record-level)
                          If False, only update fields with values (Attribute-level)

        Returns:
            Processing result with counts
        """
        results = {
            'total': len(df),
            'success': 0,
            'failed': 0,
            'errors': []
        }

        try:
            cursor = self.conn.cursor()

            for idx, row in df.iterrows():
                code = self.clean_stock_code(row['代码'])
                if not code:
                    continue

                if force_update:
                    # Force update mode: Replace entire record (Record-level)
                    sector_lv1, sector_lv2 = self.parse_sector_field(row.get('一二级行业'))

                    name = str(row['名称']).strip() if pd.notna(row['名称']) else None
                    industry = str(row['细分行业']).strip() if '细分行业' in row and pd.notna(row['细分行业']) else None
                    area = str(row['地区']).strip() if '地区' in row and pd.notna(row['地区']) else None
                    list_date = self.convert_value(row.get('上市日期'), 'date')
                    total_mcap = self.convert_value(row.get('总市值'), 'market_cap')
                    circ_mcap = self.convert_value(row.get('流通市值'), 'market_cap')
                    pe_ratio = self.convert_value(row.get('市盈(动)'), 'float')
                    pb_ratio = self.convert_value(row.get('市净率'), 'float')

                    # INSERT OR REPLACE - completely replaces the record
                    cursor.execute('''
                        INSERT OR REPLACE INTO stocks
                        (code, name, sector_lv1, sector_lv2, industry, area, list_date,
                         total_market_cap, circulating_market_cap, pe_ratio, pb_ratio, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        code, name, sector_lv1, sector_lv2, industry, area, list_date,
                        total_mcap, circ_mcap, pe_ratio, pb_ratio, datetime.now()
                    ))

                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_meta
                        (code, name, industry, area, list_date, sector_lv1, sector_lv2,
                         asset_type, is_delisted, meta_source, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        code, name, industry, area, list_date, sector_lv1, sector_lv2,
                        'stock', 0, 'excel_upload', datetime.now()
                    ))

                else:
                    # Normal mode: Only update fields with values (Attribute-level)
                    sector_lv1, sector_lv2 = None, None
                    if '一二级行业' in row and pd.notna(row['一二级行业']):
                        sector_lv1, sector_lv2 = self.parse_sector_field(row['一二级行业'])

                    # Convert metadata fields (only if present)
                    updates = {}
                    updates['name'] = str(row['名称']).strip() if pd.notna(row['名称']) else None
                    updates['industry'] = str(row['细分行业']).strip() if '细分行业' in row and pd.notna(row['细分行业']) else None
                    updates['area'] = str(row['地区']).strip() if '地区' in row and pd.notna(row['地区']) else None
                    updates['list_date'] = self.convert_value(row.get('上市日期'), 'date')
                    updates['total_market_cap'] = self.convert_value(row.get('总市值'), 'market_cap')
                    updates['circulating_market_cap'] = self.convert_value(row.get('流通市值'), 'market_cap')
                    updates['pe_ratio'] = self.convert_value(row.get('市盈(动)'), 'float')
                    updates['pb_ratio'] = self.convert_value(row.get('市净率'), 'float')

                    # Build dynamic UPDATE query - only update fields that have values
                    update_fields = []
                    update_values = []

                    for field, value in updates.items():
                        if field == 'name' and value is not None:
                            update_fields.append(f"{field} = ?")
                            update_values.append(value)
                        elif value is not None:
                            update_fields.append(f"{field} = ?")
                            update_values.append(value)

                    # Update sector fields only if they have values
                    if sector_lv1 is not None:
                        update_fields.append("sector_lv1 = ?")
                        update_values.append(sector_lv1)
                    if sector_lv2 is not None:
                        update_fields.append("sector_lv2 = ?")
                        update_values.append(sector_lv2)

                    if update_fields:
                        update_fields.append("updated_at = ?")
                        update_values.append(datetime.now())
                        update_values.append(code)

                        # Use UPDATE to preserve existing data for missing fields
                        cursor.execute(f'''
                            UPDATE stocks
                            SET {', '.join(update_fields)}
                            WHERE code = ?
                        ''', update_values)

                    # Update stock_meta table similarly
                    meta_update_fields = []
                    meta_update_values = []

                    if updates['name'] is not None:
                        meta_update_fields.append("name = ?")
                        meta_update_values.append(updates['name'])
                    if updates['industry'] is not None:
                        meta_update_fields.append("industry = ?")
                        meta_update_values.append(updates['industry'])
                    if updates['area'] is not None:
                        meta_update_fields.append("area = ?")
                        meta_update_values.append(updates['area'])
                    if updates['list_date'] is not None:
                        meta_update_fields.append("list_date = ?")
                        meta_update_values.append(updates['list_date'])
                    if sector_lv1 is not None:
                        meta_update_fields.append("sector_lv1 = ?")
                        meta_update_values.append(sector_lv1)
                    if sector_lv2 is not None:
                        meta_update_fields.append("sector_lv2 = ?")
                        meta_update_values.append(sector_lv2)

                    if meta_update_fields:
                        meta_update_fields.append("updated_at = ?")
                        meta_update_values.append(datetime.now())
                        meta_update_values.append(code)

                        cursor.execute(f'''
                            UPDATE stock_meta
                            SET {', '.join(meta_update_fields)}
                            WHERE code = ?
                        ''', meta_update_values)

                results['success'] += 1

            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to process stock metadata: {e}")
            raise

        return results

    def process_upload(self, file_path: str, force_update: bool = False) -> Dict[str, Any]:
        """
        Process complete upload workflow

        Args:
            file_path: Path to uploaded file
            force_update: If True, completely replace records (Record-level)
                          If False, only update fields with values (Attribute-level)

        Returns:
            Result dictionary with status and details
        """
        result = {
            'status': 'error',
            'message': '',
            'trade_date': None,
            'daily_prices': None,
            'stock_metadata': None,
            'errors': []
        }

        # Step 1: Validate file format
        is_valid, error_msg, metadata = self.validate_file_format(file_path)
        if not is_valid:
            result['message'] = error_msg
            return result

        trade_date = metadata['trade_date']
        result['trade_date'] = trade_date

        # Step 2: Read Excel file
        is_valid, error_msg, df = self.read_excel_file(file_path)
        if not is_valid:
            result['message'] = error_msg
            return result

        # Step 3: Connect to database
        if not self.connect():
            result['message'] = "数据库连接失败"
            return result

        try:
            # Step 4: Process daily prices
            daily_result = self.process_daily_prices(df, trade_date)
            result['daily_prices'] = daily_result

            # Step 5: Process stock metadata
            meta_result = self.process_stock_metadata(df, force_update=force_update)
            result['stock_metadata'] = meta_result

            # Step 6: Check overall result
            total_errors = daily_result['failed'] + meta_result['failed']
            suspended_count = len(daily_result.get('warnings', []))
            total_records = len(df)

            if total_errors == 0:
                result['status'] = 'success'
                if suspended_count > 0:
                    result['message'] = f"成功导入 {total_records} 条股票数据 ({trade_date})，其中 {suspended_count} 只停牌"
                else:
                    result['message'] = f"成功导入 {total_records} 条股票数据 ({trade_date})"
            elif total_errors < total_records * 0.05:  # Less than 5% errors
                result['status'] = 'warning'
                msg = f"导入完成，但有 {total_errors} 条记录失败"
                if suspended_count > 0:
                    msg += f"，{suspended_count} 只停牌"
                msg += f" (共 {total_records} 条)"
                result['message'] = msg
            else:
                result['status'] = 'error'
                result['message'] = f"导入失败：{total_errors} 条记录错误 (共 {total_records} 条)"

            result['errors'] = daily_result['errors'][:10]  # First 10 errors
            result['warnings'] = daily_result.get('warnings', [])  # Include warnings

        except Exception as e:
            result['status'] = 'error'
            result['message'] = f"处理失败: {str(e)}"
            logger.error(f"Upload processing failed: {e}")
        finally:
            self.disconnect()

        return result


def handle_excel_upload(file_path: str, force_update: bool = False) -> Dict[str, Any]:
    """
    Handle Excel file upload

    Args:
        file_path: Path to uploaded file
        force_update: If True, completely replace records (Record-level)
                      If False, only update fields with values (Attribute-level)

    Returns:
        Result dictionary
    """
    handler = ExcelUploadHandler()
    return handler.process_upload(file_path, force_update=force_update)
