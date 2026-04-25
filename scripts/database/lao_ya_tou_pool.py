#!/usr/bin/env python3
"""
LaoYaTou Pool Repository - Database access layer for lao_ya_tou_pool table

This module provides CRUD operations for the lao_ya_tou_pool table which stores
stock pool records uploaded via Excel files.

Author: Claude Code
Date: 2026-04-19
"""

import sqlite3
import logging
import hashlib
from typing import List, Dict, Optional
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass


class ValidationError(ValueError):
    """Custom exception for input validation errors"""
    pass


def db_connection_error_handler(func):
    """Decorator to handle database connection errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            raise DatabaseError(f"Database operation failed: {e}")
    return wrapper


class LaoYaTouPoolRepository:
    """Repository for lao_ya_tou_pool table operations"""

    def __init__(self, db_path: str = 'data/stock_data.db'):
        """
        Initialize repository with database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._ensure_schema()

    def _connect(self):
        """Establish database connection with timeout and retry logic"""
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                self.conn = sqlite3.connect(self.db_path, timeout=30)
                self.conn.row_factory = sqlite3.Row
                logger.info(f"Connected to database: {self.db_path}")
                return
            except sqlite3.Error as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1}/{max_retries} failed: {e}")
                    import time
                    time.sleep(retry_delay)
                else:
                    raise DatabaseError(f"Database connection failed: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def _ensure_schema(self):
        """
        Ensure compatibility columns exist on lao_ya_tou_pool.

        We keep this in repository init so old DB files can be upgraded lazily.
        """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(lao_ya_tou_pool)")
        columns = {str(row[1]) for row in cursor.fetchall()}
        if 'last_screened_date' not in columns:
            cursor.execute('ALTER TABLE lao_ya_tou_pool ADD COLUMN last_screened_date DATE')
            logger.info("Added column lao_ya_tou_pool.last_screened_date")
        self.conn.commit()

    def _validate_stock_code(self, stock_code: str) -> None:
        """
        Validate stock code format.

        Args:
            stock_code: 6-digit stock code

        Raises:
            ValueError: If stock code is invalid
        """
        if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
            raise ValidationError("Stock code must be 6 digits")

    def _validate_stock_name(self, stock_name: str) -> None:
        """
        Validate stock name.

        Args:
            stock_name: Stock name

        Raises:
            ValueError: If stock name is invalid
        """
        cleaned = (stock_name or "").strip()
        if not cleaned:
            raise ValidationError("Stock name cannot be empty")
        if len(cleaned) > 10:
            raise ValidationError("Stock name must be 1-10 characters")

    def _validate_date_format(self, date_str: str, field_name: str) -> None:
        """
        Validate date format (YYYY-MM-DD).

        Args:
            date_str: Date string to validate
            field_name: Name of the date field for error messages

        Raises:
            ValueError: If date format is invalid
        """
        if not date_str:
            raise ValidationError(f"{field_name} cannot be empty")
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValidationError(f"{field_name} must be in YYYY-MM-DD format")

    def _validate_file_name(self, file_name: str) -> None:
        """
        Validate Excel file name.

        Args:
            file_name: Excel file name

        Raises:
            ValueError: If file name is invalid
        """
        if not file_name:
            raise ValidationError("file_name cannot be empty")
        if not file_name.endswith('.xlsx'):
            raise ValidationError("file_name must end with .xlsx")

    def _build_pool_biz_key(self, stock_code: str, start_date: str,
                            end_date: str, file_name: str) -> str:
        """
        Build deterministic idempotent key for pool ingestion.
        """
        raw = f"{stock_code}|{start_date}|{end_date}|{file_name}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

    @db_connection_error_handler
    def insert_pool_record(self, stock_code: str, stock_name: str,
                          start_date: str, end_date: str,
                          file_name: str,
                          pool_biz_key: Optional[str] = None) -> int:
        """
        Insert a single pool record.

        Args:
            stock_code: 6-digit stock code
            stock_name: Stock name
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            file_name: Excel file name

        Returns:
            Inserted record ID

        Raises:
            ValueError: If any field is invalid
            DatabaseError: If database operation fails
        """
        # Validate all fields
        self._validate_stock_code(stock_code)
        self._validate_stock_name(stock_name)
        self._validate_date_format(start_date, 'start_date')
        self._validate_date_format(end_date, 'end_date')
        self._validate_file_name(file_name)

        cursor = self.conn.cursor()
        biz_key = pool_biz_key or self._build_pool_biz_key(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            file_name=file_name
        )
        cursor.execute('''
            INSERT INTO lao_ya_tou_pool
            (pool_biz_key, stock_code, stock_name, start_date, end_date, file_name)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (biz_key, stock_code, stock_name, start_date, end_date, file_name))

        self.conn.commit()
        return cursor.lastrowid

    @db_connection_error_handler
    def insert_pool_batch(self, records: List[dict]) -> int:
        """
        Insert multiple pool records in a single transaction.

        Args:
            records: List of pool record dictionaries

        Returns:
            Number of records inserted
        """
        cursor = self.conn.cursor()
        inserted_count = 0

        try:
            for record in records:
                # Validate all fields
                self._validate_stock_code(record['stock_code'])
                self._validate_stock_name(record['stock_name'])
                self._validate_date_format(record['start_date'], 'start_date')
                self._validate_date_format(record['end_date'], 'end_date')
                self._validate_file_name(record['file_name'])

                biz_key = record.get('pool_biz_key') or self._build_pool_biz_key(
                    stock_code=record['stock_code'],
                    start_date=record['start_date'],
                    end_date=record['end_date'],
                    file_name=record['file_name']
                )

                cursor.execute('''
                    INSERT INTO lao_ya_tou_pool
                    (pool_biz_key, stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    biz_key,
                    record['stock_code'],
                    record['stock_name'],
                    record['start_date'],
                    record['end_date'],
                    record['file_name']
                ))
                inserted_count += 1

            self.conn.commit()
            logger.info(f"Inserted {inserted_count} pool records")

        except Exception:
            self.conn.rollback()
            raise

        return inserted_count

    @db_connection_error_handler
    def upsert_pool_batch(self, records: List[dict]) -> Dict[str, int]:
        """
        Incremental mode: insert new records by pool_biz_key and ignore duplicates.

        Returns:
            {'inserted': int, 'skipped': int}
        """
        cursor = self.conn.cursor()
        inserted = 0
        skipped = 0

        try:
            for record in records:
                self._validate_stock_code(record['stock_code'])
                self._validate_stock_name(record['stock_name'])
                self._validate_date_format(record['start_date'], 'start_date')
                self._validate_date_format(record['end_date'], 'end_date')
                self._validate_file_name(record['file_name'])

                biz_key = record.get('pool_biz_key') or self._build_pool_biz_key(
                    stock_code=record['stock_code'],
                    start_date=record['start_date'],
                    end_date=record['end_date'],
                    file_name=record['file_name']
                )

                cursor.execute('''
                    INSERT OR IGNORE INTO lao_ya_tou_pool
                    (pool_biz_key, stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    biz_key,
                    record['stock_code'],
                    record['stock_name'],
                    record['start_date'],
                    record['end_date'],
                    record['file_name']
                ))
                if cursor.rowcount == 1:
                    inserted += 1
                else:
                    skipped += 1

            self.conn.commit()
            return {'inserted': inserted, 'skipped': skipped}
        except Exception:
            self.conn.rollback()
            raise

    @db_connection_error_handler
    def force_overwrite_pool(self, records: List[dict]) -> Dict[str, int]:
        """
        Force overwrite mode:
        1) clear five-flags results
        2) clear pool table
        3) rebuild pool from upload records

        Returns:
            {'deleted_results': int, 'deleted_pools': int, 'inserted': int}
        """
        cursor = self.conn.cursor()
        inserted = 0
        deleted_results = 0
        deleted_pools = 0

        try:
            cursor.execute('DELETE FROM lao_ya_tou_five_flags')
            deleted_results = cursor.rowcount if cursor.rowcount != -1 else 0

            cursor.execute('DELETE FROM lao_ya_tou_pool')
            deleted_pools = cursor.rowcount if cursor.rowcount != -1 else 0

            for record in records:
                self._validate_stock_code(record['stock_code'])
                self._validate_stock_name(record['stock_name'])
                self._validate_date_format(record['start_date'], 'start_date')
                self._validate_date_format(record['end_date'], 'end_date')
                self._validate_file_name(record['file_name'])

                biz_key = record.get('pool_biz_key') or self._build_pool_biz_key(
                    stock_code=record['stock_code'],
                    start_date=record['start_date'],
                    end_date=record['end_date'],
                    file_name=record['file_name']
                )

                cursor.execute('''
                    INSERT INTO lao_ya_tou_pool
                    (pool_biz_key, stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    biz_key,
                    record['stock_code'],
                    record['stock_name'],
                    record['start_date'],
                    record['end_date'],
                    record['file_name']
                ))
                inserted += 1

            self.conn.commit()
            return {
                'deleted_results': deleted_results,
                'deleted_pools': deleted_pools,
                'inserted': inserted
            }
        except Exception:
            self.conn.rollback()
            raise

    @db_connection_error_handler
    def find_unprocessed_pools(self, limit: Optional[int] = None) -> List[dict]:
        """
        Find unprocessed pool records.

        Args:
            limit: Optional limit on number of records to return

        Returns:
            List of pool record dictionaries
        """
        cursor = self.conn.cursor()
        if limit:
            cursor.execute('''
                SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
                FROM lao_ya_tou_pool
                WHERE processed = 0
                ORDER BY upload_time ASC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
                FROM lao_ya_tou_pool
                WHERE processed = 0
                ORDER BY upload_time ASC
            ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def find_all_pools_for_screening(self, limit: Optional[int] = None) -> List[dict]:
        """
        Find all pool records for daily catch-up screening.
        """
        cursor = self.conn.cursor()
        if limit:
            cursor.execute('''
                SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
                FROM lao_ya_tou_pool
                ORDER BY upload_time ASC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
                FROM lao_ya_tou_pool
                ORDER BY upload_time ASC
            ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def find_pools_by_ids(self, pool_ids: List[int]) -> List[dict]:
        """
        Find pools by their IDs.

        Args:
            pool_ids: List of pool IDs to retrieve

        Returns:
            List of pool record dictionaries
        """
        if not pool_ids:
            return []

        placeholders = ', '.join(['?' for _ in pool_ids])
        cursor = self.conn.cursor()
        cursor.execute(f'''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
            FROM lao_ya_tou_pool
            WHERE id IN ({placeholders})
            ORDER BY upload_time ASC
        ''', pool_ids)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def mark_as_processed(self, pool_id: int) -> bool:
        """
        Mark a pool record as processed.

        Args:
            pool_id: Pool record ID to mark as processed

        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE lao_ya_tou_pool
            SET processed = 1
            WHERE id = ?
        ''', (pool_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    @db_connection_error_handler
    def mark_pool_as_processed(self, pool_id: int) -> bool:
        return self.mark_as_processed(pool_id)

    @db_connection_error_handler
    def get_unprocessed_pools(self) -> List[dict]:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
            FROM lao_ya_tou_pool
            WHERE processed = 0
            ORDER BY upload_time DESC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def get_pools_by_stock_code(self, stock_code: str) -> List[dict]:
        self._validate_stock_code(stock_code)
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
            FROM lao_ya_tou_pool
            WHERE stock_code = ?
            ORDER BY upload_time DESC
        ''', (stock_code,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def update_last_screened_date(self, pool_id: int, last_screened_date: str) -> bool:
        """
        Update screening progress date for a pool row.
        """
        self._validate_date_format(last_screened_date, 'last_screened_date')
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE lao_ya_tou_pool
            SET last_screened_date = ?, processed = 1
            WHERE id = ?
        ''', (last_screened_date, pool_id))
        self.conn.commit()
        return cursor.rowcount > 0

    @db_connection_error_handler
    def get_all_pools(self) -> List[dict]:
        """
        Retrieve all pool records.

        Returns:
            List of all pool record dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
            FROM lao_ya_tou_pool
            ORDER BY upload_time DESC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    @db_connection_error_handler
    def get_pool_by_id(self, pool_id: int) -> Optional[dict]:
        """
        Retrieve a single pool record by ID.

        Args:
            pool_id: Pool record ID

        Returns:
            Pool record dictionary or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed, last_screened_date
            FROM lao_ya_tou_pool
            WHERE id = ?
        ''', (pool_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    @db_connection_error_handler
    def delete_pool(self, pool_id: int) -> bool:
        """
        Delete a pool record.

        Args:
            pool_id: Pool record ID to delete

        Returns:
            True if deleted, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM lao_ya_tou_pool
            WHERE id = ?
        ''', (pool_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    @db_connection_error_handler
    def count_unprocessed_pools(self) -> int:
        """
        Count unprocessed pool records.

        Returns:
            Number of unprocessed pool records
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM lao_ya_tou_pool
            WHERE processed = 0
        ''')
        result = cursor.fetchone()
        return result['count'] if result else 0

    @db_connection_error_handler
    def count_total_pools(self) -> int:
        """
        Count total pool records.

        Returns:
            Total number of pool records
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM lao_ya_tou_pool
        ''')
        result = cursor.fetchone()
        return result['count'] if result else 0


if __name__ == '__main__':
    """Test repository functionality"""
    logging.basicConfig(level=logging.INFO)

    repo = LaoYaTouPoolRepository('data/stock_data.db')

    # Test insert
    pool_id = repo.insert_pool_record(
        stock_code='000001',
        stock_name='平安银行',
        start_date='2026-04-01',
        end_date='2026-04-10',
        file_name='test.xlsx'
    )
    print(f"Inserted pool ID: {pool_id}")

    # Test query
    unprocessed = repo.find_unprocessed_pools()
    print(f"Unprocessed pools: {len(unprocessed)}")

    # Test count
    count = repo.count_unprocessed_pools()
    print(f"Unprocessed count: {count}")

    repo.close()
