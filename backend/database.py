#!/usr/bin/env python3
"""
Database Utilities
Provides transaction management and common database operations
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"
STOCK_DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"


@contextmanager
def transaction(db_path: Optional[Path] = None):
    """
    Context manager for database transactions with automatic commit/rollback

    Usage:
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO ...")
            # Auto-commits on success, rolls back on exception
    """
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        conn.execute("BEGIN TRANSACTION")
        yield conn
        conn.commit()
        logger.debug(f"Transaction committed on {db_path.name}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction rolled back on {db_path.name}: {e}")
        raise
    finally:
        conn.close()


def execute_write(
    query: str,
    params: tuple = (),
    db_path: Optional[Path] = None
) -> int:
    """
    Execute a write operation in a transaction

    Args:
        query: SQL query with placeholders
        params: Query parameters
        db_path: Database path (defaults to dashboard.db)

    Returns:
        lastrowid if applicable, else -1
    """
    with transaction(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid or -1


def execute_many(
    query: str,
    params_list: List[tuple],
    db_path: Optional[Path] = None
) -> int:
    """
    Execute multiple write operations in a single transaction

    Args:
        query: SQL query with placeholders
        params_list: List of parameter tuples
        db_path: Database path (defaults to dashboard.db)

    Returns:
        Number of rows affected
    """
    with transaction(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, params_list)
        return cursor.rowcount


def execute_fetchone(
    query: str,
    params: tuple = (),
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Execute a query and fetch one row

    Args:
        query: SQL query with placeholders
        params: Query parameters
        db_path: Database path

    Returns:
        Row as dict or None
    """
    conn = sqlite3.connect(db_path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def execute_fetchall(
    query: str,
    params: tuple = (),
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Execute a query and fetch all rows

    Args:
        query: SQL query with placeholders
        params: Query parameters
        db_path: Database path

    Returns:
        List of rows as dicts
    """
    conn = sqlite3.connect(db_path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def upsert(
    table: str,
    data: Dict[str, Any],
    conflict_columns: List[str],
    db_path: Optional[Path] = None
) -> int:
    """
    Perform an upsert (insert or update) operation

    Args:
        table: Table name
        data: Dictionary of column: value pairs
        conflict_columns: Columns that define uniqueness
        db_path: Database path

    Returns:
        lastrowid
    """
    columns = list(data.keys())
    placeholders = ', '.join(['?'] * len(columns))
    values = tuple(data.values())

    conflict_cols = ', '.join(conflict_columns)
    updates = ', '.join([f"{col} = excluded.{col}" for col in columns if col not in conflict_columns])

    query = f'''
        INSERT INTO {table} ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT({conflict_cols}) DO UPDATE SET
            {updates}
    '''

    return execute_write(query, values, db_path)
