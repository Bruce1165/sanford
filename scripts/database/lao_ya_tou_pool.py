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
from typing import List, Dict, Optional, Any
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database errors"""
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

    def _validate_stock_code(self, stock_code: str) -> None:
        """
        Validate stock code format.

        Args:
            stock_code: 6-digit stock code

        Raises:
            ValueError: If stock code is invalid
        """
        if not stock_code or len(stock_code) != 6:
            raise ValueError(f"Invalid stock code: {stock_code}. Must be 6 digits.")

    def _validate_stock_name(self, stock_name: str) -> None:
        """
        Validate stock name.

        Args:
            stock_name: Stock name

        Raises:
            ValueError: If stock name is invalid
        """
        if not stock_name or len(stock_name) > 10:
            raise ValueError(f"Invalid stock name: {stock_name}. Must be 1-10 characters.")

    def _validate_date_format(self, date_str: str, field_name: str) -> None:
        """
        Validate date format (YYYY-MM-DD).

        Args:
            date_str: Date string to validate
            field_name: Name of the date field for error messages

        Raises:
            ValueError: If date format is invalid
        """
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid {field_name} format: {date_str}. Must be YYYY-MM-DD.")

    def _validate_file_name(self, file_name: str) -> None:
        """
        Validate Excel file name.

        Args:
            file_name: Excel file name

        Raises:
            ValueError: If file name is invalid
        """
        if not file_name or not file_name.endswith('.xlsx'):
            raise ValueError(f"Invalid file name: {file_name}. Must end with .xlsx")

    @db_connection_error_handler
    def insert_pool_record(self, stock_code: str, stock_name: str,
                          start_date: str, end_date: str,
                          file_name: str) -> int:
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
        cursor.execute('''
            INSERT INTO lao_ya_tou_pool
            (stock_code, stock_name, start_date, end_date, file_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (stock_code, stock_name, start_date, end_date, file_name))

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

                cursor.execute('''
                    INSERT INTO lao_ya_tou_pool
                    (stock_code, stock_name, start_date, end_date, file_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    record['stock_code'],
                    record['stock_name'],
                    record['start_date'],
                    record['end_date'],
                    record['file_name']
                ))
                inserted_count += 1

            self.conn.commit()
            logger.info(f"Inserted {inserted_count} pool records")

        except Exception as e:
            self.conn.rollback()
            raise

        return inserted_count

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
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
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
    def get_all_pools(self) -> List[dict]:
        """
        Retrieve all pool records.

        Returns:
            List of all pool record dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
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
            SELECT id, stock_code, stock_name, start_date, end_date, file_name, upload_time, processed
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
