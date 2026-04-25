"""
Lao Ya Tou Five Flags Database Repository

This module provides database access layer for lao_ya_tou_five_flags table,
implementing CRUD operations with foreign key references to lao_ya_tou_pool.

Author: Claude Code
Date: 2026-04-19
"""

import sqlite3
import logging
import time
from datetime import datetime
from datetime import date as dt_date
from typing import List, Optional
import re
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass


class ValidationError(Exception):
    """Custom exception for input validation"""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry database operations on failure.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (sqlite3.OperationalError, sqlite3.InterfaceError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
            logger.error(f"All {max_retries} attempts failed for {func.__name__}: {last_exception}")
            raise DatabaseError(f"Database operation failed after {max_retries} attempts: {last_exception}")

        return wrapper

    return decorator


class LaoYaTouFiveFlagsRepository:
    """Repository for lao_ya_tou_five_flags table operations"""

    def __init__(self, db_path: str = 'data/stock_data.db'):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file

        Raises:
            DatabaseError: If connection fails after retries
        """
        self.db_path = db_path
        self.conn = None
        self._is_trading_day = None
        self._connect()
        self._init_business_constraints()

    def _load_trading_day_checker(self):
        """Lazy-load trading day checker to avoid import-order issues."""
        if self._is_trading_day is not None:
            return self._is_trading_day
        try:
            from scripts.trading_calendar import is_trading_day  # type: ignore
            self._is_trading_day = is_trading_day
            return self._is_trading_day
        except Exception:
            from trading_calendar import is_trading_day  # type: ignore
            self._is_trading_day = is_trading_day
            return self._is_trading_day

    def _init_business_constraints(self) -> None:
        """
        Ensure business-key uniqueness:
        stock_code + screen_date + screener_id.
        """
        self._dedupe_by_business_key()
        self._create_business_key_unique_index()

    def _dedupe_by_business_key(self) -> None:
        """Drop duplicate rows and keep the newest one for each business key."""
        cursor = self.conn.cursor()
        cursor.execute(
            '''
            DELETE FROM lao_ya_tou_five_flags
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM lao_ya_tou_five_flags
                GROUP BY stock_code, screen_date, screener_id
            )
            '''
        )
        deleted = cursor.rowcount if cursor.rowcount is not None else 0
        if deleted > 0:
            logger.warning(
                "Deduplicated lao_ya_tou_five_flags by (stock_code, screen_date, screener_id), removed=%s",
                deleted
            )
        self.conn.commit()

    def _create_business_key_unique_index(self) -> None:
        """Create composite unique index for business key."""
        self.conn.execute(
            '''
            CREATE UNIQUE INDEX IF NOT EXISTS ux_five_flags_stock_date_screener
            ON lao_ya_tou_five_flags(stock_code, screen_date, screener_id)
            '''
        )
        self.conn.commit()

    def _connect(self):
        """Establish database connection with proper settings."""
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=30)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute('PRAGMA foreign_keys = ON')
            self.conn.execute('PRAGMA journal_mode = WAL')
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to database {self.db_path}: {e}")
            raise DatabaseError(f"Database connection failed: {e}")

    def _validate_pool_id(self, pool_id: int) -> None:
        """
        Validate pool_id exists in lao_ya_tou_pool.

        Args:
            pool_id: Pool ID to validate

        Raises:
            ValidationError: If pool_id is invalid
        """
        if pool_id <= 0:
            raise ValidationError(f"Pool ID must be positive: {pool_id}")

        # Check if pool exists
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM lao_ya_tou_pool WHERE id = ?', (pool_id,))
        result = cursor.fetchone()
        if not result:
            raise ValidationError(f"Pool ID {pool_id} does not exist in lao_ya_tou_pool")

    def _validate_screener_id(self, screener_id: str) -> None:
        """
        Validate screener_id.

        Args:
            screener_id: Screener identifier

        Raises:
            ValidationError: If screener_id is invalid
        """
        if not screener_id or not screener_id.strip():
            raise ValidationError("Screener ID cannot be empty")

    def _validate_stock_code(self, stock_code: str) -> None:
        """
        Validate stock code format.

        Args:
            stock_code: Stock code to validate

        Raises:
            ValidationError: If stock code is invalid
        """
        if not re.match(r'^\d{6}$', stock_code):
            raise ValidationError(f"Stock code must be 6 digits: {stock_code}")

    def _validate_stock_name(self, stock_name: str) -> None:
        """
        Validate stock name.

        Args:
            stock_name: Stock name to validate

        Raises:
            ValidationError: If stock name is invalid
        """
        if not stock_name or not stock_name.strip():
            raise ValidationError("Stock name cannot be empty")

        # Remove trailing numbers and parentheses
        cleaned_name = re.sub(r'\s*\d*\s*$', '', stock_name)
        cleaned_name = re.sub(r'[()（）]', '', cleaned_name)

        if not cleaned_name.strip():
            raise ValidationError(f"Stock name cannot be empty after cleaning: {stock_name}")

    def _validate_date_format(self, date_str: str, field_name: str) -> None:
        """
        Validate date format.

        Args:
            date_str: Date string to validate
            field_name: Name of the date field (for error message)

        Raises:
            ValidationError: If date format is invalid
        """
        if not date_str or not date_str.strip():
            raise ValidationError(f"{field_name} cannot be empty")

        try:
            parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError(
                f"{field_name} must be in YYYY-MM-DD format: {date_str}"
            )

        checker = self._load_trading_day_checker()
        if not checker(parsed if isinstance(parsed, dt_date) else parsed):
            raise ValidationError(
                f"{field_name} must be a valid exchange trading day: {date_str}"
            )

    def _validate_price(self, price: Optional[float], field_name: str) -> None:
        """
        Validate price value.

        Args:
            price: Price to validate
            field_name: Name of the price field (for error message)

        Raises:
            ValidationError: If price is invalid
        """
        # Price validation is minimal - screening logic doesn't depend on price
        # If price is None, use 0.0 as default
        if price is None:
            price = 0.0

        # Check if price is NaN
        import math
        if isinstance(price, float) and math.isnan(price):
            raise ValidationError(f"{field_name} cannot be NaN")

        if price < 0:
            raise ValidationError(f"{field_name} must be non-negative: {price}")

    def _validate_extra_data(self, extra_data: dict) -> None:
        """
        Validate extra_data JSON.

        Args:
            extra_data: Extra data dictionary to validate

        Raises:
            ValidationError: If extra_data is invalid
        """
        if extra_data:
            try:
                json.dumps(extra_data)  # Validate JSON serializable
            except (TypeError, ValueError) as e:
                raise ValidationError(f"Extra data must be JSON serializable: {e}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def insert_flag_result(self, pool_id: int, screener_id: str,
                              stock_code: str, stock_name: str,
                              screen_date: str, close_price: float,
                              match_reason: str, extra_data: dict = None) -> int:
        """
        Insert single flag result.

        Args:
            pool_id: Pool ID (must exist in lao_ya_tou_pool)
            screener_id: Screener identifier
            stock_code: 6-digit stock code
            stock_name: Stock name (will be cleaned)
            screen_date: Screen date in YYYY-MM-DD format
            close_price: Closing price
            match_reason: Match reason description
            extra_data: Optional JSON data

        Returns:
            Inserted record ID

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        self._validate_pool_id(pool_id)
        self._validate_screener_id(screener_id)
        self._validate_stock_code(stock_code)
        self._validate_stock_name(stock_name)
        self._validate_date_format(screen_date, 'screen_date')
        self._validate_price(close_price, 'close_price')
        if extra_data:
            self._validate_extra_data(extra_data)

        # Clean stock name
        cleaned_name = re.sub(r'\s*\d*\s*$', '', stock_name)
        cleaned_name = re.sub(r'[()（）]', '', cleaned_name)

        try:
            cursor = self.conn.cursor()
            extra_json = json.dumps(extra_data) if extra_data is not None else None
            cursor.execute('''
                INSERT INTO lao_ya_tou_five_flags
                    (pool_id, screener_id, stock_code, stock_name,
                     screen_date, close_price, match_reason, extra_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stock_code, screen_date, screener_id) DO UPDATE SET
                    pool_id = excluded.pool_id,
                    stock_name = excluded.stock_name,
                    close_price = excluded.close_price,
                    match_reason = excluded.match_reason,
                    extra_data = excluded.extra_data,
                    created_at = CURRENT_TIMESTAMP
            ''', (
                pool_id,
                screener_id,
                stock_code,
                cleaned_name,
                screen_date,
                close_price,
                match_reason,
                extra_json
            ))

            flag_id = cursor.lastrowid
            self.conn.commit()
            logger.info(
                f"Upserted flag result: pool={pool_id}, stock={cleaned_name}, "
                f"screener={screener_id}, id={flag_id}"
            )
            return flag_id

        except sqlite3.Error as e:
            logger.error(f"Failed to insert flag result: {e}")
            self.conn.rollback()
            raise DatabaseError(f"Failed to insert flag result: {e}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def insert_flag_results_batch(self, results: List[dict]) -> int:
        """
        Batch insert flag results.

        Args:
            results: List of dictionaries with keys:
                - pool_id: Pool ID
                - screener_id: Screener identifier
                - stock_code: 6-digit stock code
                - stock_name: Stock name
                - screen_date: Screen date in YYYY-MM-DD format
                - close_price: Closing price
                - match_reason: Match reason
                - extra_data: Optional JSON data

        Returns:
            Number of records inserted

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        if not results:
            logger.warning("No records to insert in batch")
            return 0

        # Validate all records
        for i, record in enumerate(results):
            try:
                self._validate_pool_id(record['pool_id'])
                self._validate_screener_id(record['screener_id'])
                self._validate_stock_code(record['stock_code'])
                self._validate_stock_name(record['stock_name'])
                self._validate_date_format(record['screen_date'], 'screen_date')
                self._validate_price(record['close_price'], 'close_price')
                if 'extra_data' in record:
                    self._validate_extra_data(record['extra_data'])
            except ValidationError as e:
                raise ValidationError(
                    f"Record {i + 1}/{len(results)} validation failed: {e}"
                )

        # Prepare data for batch insert
        # Use list to ensure consistent parameter count for executemany()
        data_to_insert = []
        for record in results:
            cleaned_name = re.sub(r'\s*\d*\s*$', '', record['stock_name'])
            cleaned_name = re.sub(r'[()（）]', '', cleaned_name)

            extra_json = None
            if 'extra_data' in record:
                extra_json = json.dumps(record['extra_data'])

            params = [
                record['pool_id'],
                record['screener_id'],
                record['stock_code'],
                cleaned_name,
                record['screen_date'],
                record['close_price'],
                record['match_reason'],
                extra_json
            ]
            data_to_insert.append(params)

        try:
            cursor = self.conn.cursor()
            cursor.executemany('''
                INSERT INTO lao_ya_tou_five_flags
                    (pool_id, screener_id, stock_code, stock_name,
                     screen_date, close_price, match_reason, extra_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(stock_code, screen_date, screener_id) DO UPDATE SET
                    pool_id = excluded.pool_id,
                    stock_name = excluded.stock_name,
                    close_price = excluded.close_price,
                    match_reason = excluded.match_reason,
                    extra_data = excluded.extra_data,
                    created_at = CURRENT_TIMESTAMP
                ''', data_to_insert)

            inserted_count = cursor.rowcount
            self.conn.commit()
            logger.info(f"Batch upsert attempted {len(results)}, affected rows={inserted_count}")
            return inserted_count

        except sqlite3.Error as e:
            logger.error(f"Failed to batch insert flag results: {e}")
            self.conn.rollback()
            raise DatabaseError(f"Failed to batch insert {len(results)} results: {e}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def get_results_by_pool_id(self, pool_id: int) -> List[dict]:
        """
        Get all flag results for a specific pool ID.

        Args:
            pool_id: Pool ID

        Returns:
            List of dictionaries representing flag results
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, pool_id, screener_id, stock_code, stock_name,
                       screen_date, close_price, match_reason, extra_data, created_at
                FROM lao_ya_tou_five_flags
                WHERE pool_id = ?
                ORDER BY created_at DESC
            ''', (pool_id,))

            results = cursor.fetchall()
            flags = [dict(row) for row in results]
            logger.info(f"Retrieved {len(flags)} flag results for pool_id={pool_id}")
            return flags

        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve flag results by pool ID: {e}")
            raise DatabaseError(f"Failed to retrieve flag results by pool ID: {e}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def get_results_by_screener(self, screener_id: str,
                               start_date: str = None,
                               end_date: str = None) -> List[dict]:
        """
        Get flag results by screener ID, with optional date range filter.

        Args:
            screener_id: Screener identifier
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering

        Returns:
            List of dictionaries representing flag results
        """
        try:
            cursor = self.conn.cursor()
            if start_date and end_date:
                cursor.execute('''
                    SELECT id, pool_id, screener_id, stock_code, stock_name,
                           screen_date, close_price, match_reason, extra_data, created_at
                    FROM lao_ya_tou_five_flags
                    WHERE screener_id = ? AND screen_date >= ? AND screen_date <= ?
                    ORDER BY created_at DESC
                ''', (screener_id, start_date, end_date))
            elif start_date:
                cursor.execute('''
                    SELECT id, pool_id, screener_id, stock_code, stock_name,
                           screen_date, close_price, match_reason, extra_data, created_at
                    FROM lao_ya_tou_five_flags
                    WHERE screener_id = ? AND screen_date >= ?
                    ORDER BY created_at DESC
                ''', (screener_id, start_date))
            elif end_date:
                cursor.execute('''
                    SELECT id, pool_id, screener_id, stock_code, stock_name,
                           screen_date, close_price, match_reason, extra_data, created_at
                    FROM lao_ya_tou_five_flags
                    WHERE screener_id = ? AND screen_date <= ?
                    ORDER BY created_at DESC
                ''', (screener_id, end_date))
            else:
                cursor.execute('''
                    SELECT id, pool_id, screener_id, stock_code, stock_name,
                           screen_date, close_price, match_reason, extra_data, created_at
                    FROM lao_ya_tou_five_flags
                    WHERE screener_id = ?
                    ORDER BY created_at DESC
                ''', (screener_id,))

            results = cursor.fetchall()
            flags = [dict(row) for row in results]
            logger.info(f"Retrieved {len(flags)} flag results for screener_id={screener_id}")
            return flags

        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve flag results by screener ID: {e}")
            raise DatabaseError(f"Failed to retrieve flag results by screener ID: {e}")

    @retry_on_failure(max_retries=3, delay=1.0)
    def get_results_by_stock_code(self, stock_code: str) -> List[dict]:
        """
        Get all flag results for a specific stock code.

        Args:
            stock_code: 6-digit stock code

        Returns:
            List of dictionaries representing flag results
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT id, pool_id, screener_id, stock_code, stock_name,
                       screen_date, close_price, match_reason, extra_data, created_at
                    FROM lao_ya_tou_five_flags
                    WHERE stock_code = ?
                    ORDER BY created_at DESC
            ''', (stock_code,))

            results = cursor.fetchall()
            flags = [dict(row) for row in results]
            logger.info(f"Retrieved {len(flags)} flag results for stock={stock_code}")
            return flags

        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve flag results by stock code: {e}")
            raise DatabaseError(f"Failed to retrieve flag results by stock code: {e}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
