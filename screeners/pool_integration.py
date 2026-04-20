"""
Pool integration module for screeners that run against the stock pool.

This module provides helper functions for screeners to:
- Query the stock pool
- Insert screening results into pool_screening_results table
- Get screener ID from screener_types table
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


def get_db_path(db_path: Optional[str] = None) -> Path:
    """Get database path with fallback."""
    if db_path:
        return Path(db_path).resolve()

    # Fallback to default config
    try:
        import config
        return Path(config.DB_PATH).resolve()
    except ImportError:
        return Path(__file__).parent.parent.parent / "data" / "stock_data.db"


def get_screener_id(db_conn: sqlite3.Connection, screener_code: str) -> Optional[int]:
    """
    Get screener ID from screener_types table.

    Args:
        db_conn: SQLite connection
        screener_code: Screener code string

    Returns:
        screener_id (int) or None
    """
    query = """
        SELECT id FROM screener_types
        WHERE code = ?
    """
    result = db_conn.execute(query, (screener_code,)).fetchone()

    if result:
        screener_id = result['id']
        logger.debug(f"Screener ID found: {screener_code} = {screener_id}")
        return screener_id

    logger.error(f"Screener {screener_code} not found in screener_types table")
    return None


def get_pool_stocks(db_conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """
    Get all stocks currently in LYT pool.

    Args:
        db_conn: SQLite connection

    Returns:
        List of tuples: (code, name)
    """
    query = """
        SELECT code, name
        FROM lao_ya_tou_pool
        ORDER BY entry_date DESC
    """
    results = db_conn.execute(query).fetchall()
    return [(row['code'], row['name']) for row in results]


def get_pool_stock_codes(db_conn: sqlite3.Connection) -> List[str]:
    """
    Get list of stock codes in pool.

    Args:
        db_conn: SQLite connection

    Returns:
        List of stock codes
    """
    query = "SELECT code FROM lao_ya_tou_pool"
    results = db_conn.execute(query).fetchall()
    return [row['code'] for row in results]


def insert_pool_screening_result(db_conn: sqlite3.Connection, screener_id: int,
                                 code: str, screen_date: str, result: Dict) -> None:
    """
    Insert screening result into unified table.

    Args:
        db_conn: SQLite connection
        screener_id: ID from screener_types
        code: Stock code
        screen_date: Date of screening
        result: Screening result dict from screener
    """
    query = """
        INSERT INTO pool_screening_results (
            screener_id, code, screen_date, signal_type,
            score, price, reason, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    db_conn.execute(query, (
        screener_id,
        code,
        screen_date,
        result.get('signal_type'),
        result.get('score', 0.0),
        result.get('price'),
        result.get('reason', ''),
        json.dumps(result.get('extra', {}))
    ))
    logger.debug(f"Inserted pool result for {code}: {result.get('signal_type', 'N/A')}")


def get_pool_size(db_conn: sqlite3.Connection) -> int:
    """Get current pool size (number of stocks)."""
    query = "SELECT COUNT(*) FROM lao_ya_tou_pool"
    result = db_conn.execute(query).fetchone()
    return result[0] if result else 0


def run_pool_screening(screener_instance, screener_code: str, screen_date: str) -> Tuple[List, Dict]:
    """
    Run screener against stock pool.

    This function provides the pool screening workflow for all 5 pool screeners.

    Args:
        screener_instance: Screener instance with screen_stock() method
        screener_code: Screener code for DB lookup
        screen_date: Date string YYYY-MM-DD

    Returns:
        Tuple of (results, summary)
    """
    db_path = get_db_path()
    db_conn = sqlite3.connect(str(db_path))
    db_conn.row_factory = sqlite3.Row
    db_conn.execute("PRAGMA foreign_keys = ON")

    # Get screener ID
    screener_id = get_screener_id(db_conn, screener_code)

    if screener_id is None:
        raise RuntimeError(f"Pool not initialized for {screener_code}")

    # Get stocks from pool
    pool_stocks = get_pool_stocks(db_conn)
    pool_size = len(pool_stocks)

    if pool_size == 0:
        logger.warning(f"{screener_code}: Pool is empty, no stocks to screen")
        db_conn.close()
        return [], {
            'screener': screener_code,
            'date': screen_date,
            'mode': 'pool',
            'pool_size': 0,
            'total_stocks': 0,
            'processed': 0,
            'errors': 0,
            'hits': 0
        }

    logger.info(
        f"[{screener_code}] 开始选股（from pool），基准日期={screen_date}, 池大小={pool_size}"
    )

    results_raw = []
    processed = errors = 0

    for code, name in pool_stocks:
        try:
            # Call screener's screen_stock method
            result = screener_instance.screen_stock(code, name)

            if result is not None:
                results_raw.append(result)

                # Insert into pool_screening_results
                insert_pool_screening_result(db_conn, screener_id, code, screen_date, result)

            processed += 1

        except Exception as exc:
            logger.warning(f"[{screener_code}] 处理 {code} 异常: {exc}")
            errors += 1

    # Commit all DB changes
    db_conn.commit()
    db_conn.close()

    # Build summary
    summary = {
        'screener': screener_code,
        'date': screen_date,
        'mode': 'pool',
        'pool_size': pool_size,
        'total_stocks': pool_size,
        'processed': processed,
        'errors': errors,
        'hits': len(results_raw)
    }

    logger.info(
        f"[{screener_code}] 选股完成: 命中={len(results_raw)} / 处理={processed} / 错误={errors}"
    )

    return results_raw, summary
