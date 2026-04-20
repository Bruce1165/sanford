# LYT Screener - Pool Integration Pseudocode

## Purpose
Update Lao Ya Tou screener to:
1. Manage stock pool (INSERT/UPDATE lao_ya_tou_pool)
2. Track signal changes (INSERT lao_ya_tou_signal_history)
3. Store screening results (INSERT pool_screening_results)

## Constants
```python
LYT_SCREENER_ID = 1  # From screener_types table
LYT_SCREENER_CODE = 'lao_ya_tou'

# Signal type constants
SIGNAL_1 = 'signal_1'
SIGNAL_2 = 'signal_2'
SIGNAL_3 = 'signal_3'
```

## Database Helper Functions

### get_screener_id()
```python
def get_screener_id(db_conn, screener_code):
    """
    Get screener ID from screener_types table.

    Args:
        db_conn: SQLite connection
        screener_code: Screener code string

    Returns:
        screener_id (int)
    """
    query = """
        SELECT id FROM screener_types
        WHERE code = ?
    """
    result = db_conn.execute(query, (screener_code,)).fetchone()
    return result['id'] if result else None
```

### check_pool_stock_exists()
```python
def check_pool_stock_exists(db_conn, stock_code):
    """
    Check if stock already exists in pool.

    Args:
        db_conn: SQLite connection
        stock_code: Stock code

    Returns:
        bool: True if exists, False otherwise
    """
    query = """
        SELECT code FROM lao_ya_tou_pool
        WHERE code = ?
    """
    result = db_conn.execute(query, (stock_code,)).fetchone()
    return result is not None
```

### get_current_pool_signal()
```python
def get_current_pool_signal(db_conn, stock_code):
    """
    Get current signal type for a stock in pool.

    Args:
        db_conn: SQLite connection
        stock_code: Stock code

    Returns:
        current_signal (str) or None
    """
    query = """
        SELECT current_signal FROM lao_ya_tou_pool
        WHERE code = ?
    """
    result = db_conn.execute(query, (stock_code,)).fetchone()
    return result['current_signal'] if result else None
```

## Main Screening Logic

### screen_and_manage_pool()
```python
def screen_and_manage_pool(screener, target_date):
    """
    Main function: Run LYT screener and manage pool state.

    Args:
        screener: LaoYaTouZhouXianScreener instance
        target_date: Date string YYYY-MM-DD

    Returns:
        results: List of screening results
        summary: Dictionary with stats
    """
    db_conn = get_db_connection()
    screener_id = get_screener_id(db_conn, LYT_SCREENER_CODE)
    current_date = target_date

    # Get all stocks to screen
    stocks = screener.get_all_stocks()
    processed = 0
    pool_inserted = 0
    pool_updated = 0
    errors = 0

    results = []

    for stock in stocks:
        try:
            # Stage 1: Check LYT pattern
            has_pattern, df = screener.base_detector.screen(
                stock.code, stock.name, current_date
            )

            if not has_pattern:
                # Stock lost LYT pattern - should we remove from pool?
                # For now, keep in pool but don't update signal
                logger.debug(f"{stock.code}: No pattern detected, keeping in pool")
                processed += 1
                continue

            # Stage 2: Classify signal type
            signal_result = screener.signal_classifier.classify(df)

            if signal_result is None:
                # Has pattern but no specific signal detected
                logger.debug(f"{stock.code}: Has pattern but no specific signal")
                processed += 1
                continue

            signal_type = signal_result['signal_type']

            # Check if stock already in pool
            stock_in_pool = check_pool_stock_exists(db_conn, stock.code)

            if stock_in_pool:
                # Stock exists in pool - check for signal change
                current_signal = get_current_pool_signal(db_conn, stock.code)

                if current_signal != signal_type:
                    # Signal changed - UPDATE pool + INSERT history
                    update_pool_stock(db_conn, stock, signal_type, current_date, signal_result)
                    insert_signal_history(db_conn, stock, current_signal, signal_type, current_date)
                    pool_updated += 1
                    logger.info(f"{stock.code}: Signal changed {current_signal} → {signal_type}")
                else:
                    # No change - UPDATE last_screened_date only
                    update_pool_screen_date(db_conn, stock.code, current_date)
                    logger.debug(f"{stock.code}: No signal change, updated screen date")
            else:
                # New stock enters pool - INSERT
                insert_pool_stock(db_conn, stock, signal_type, current_date, signal_result)
                insert_signal_history(db_conn, stock, None, signal_type, current_date)
                pool_inserted += 1
                logger.info(f"{stock.code}: New stock entered pool with {signal_type}")

            # Always insert screening result
            insert_screening_result(
                db_conn, screener_id, stock, current_date, signal_result
            )

            # Build result for return
            results.append(build_screening_result(stock, signal_result))
            processed += 1

        except Exception as e:
            logger.warning(f"Error processing {stock.code}: {e}")
            errors += 1

    db_conn.commit()
    db_conn.close()

    # Build summary
    summary = {
        'screener': 'lao_ya_tou',
        'date': current_date,
        'total_stocks': len(stocks),
        'processed': processed,
        'pool_inserted': pool_inserted,
        'pool_updated': pool_updated,
        'errors': errors,
        'hits': len(results)
    }

    return results, summary
```

## Pool Management Functions

### insert_pool_stock()
```python
def insert_pool_stock(db_conn, stock, signal_type, screen_date, signal_result):
    """
    Insert new stock into pool.

    Args:
        db_conn: SQLite connection
        stock: Stock object
        signal_type: Current signal type
        screen_date: Date of screening
        signal_result: Signal classification result dict
    """
    query = """
        INSERT INTO lao_ya_tou_pool (
            code, name, entry_date, current_signal,
            last_screened_date, last_updated
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """
    db_conn.execute(query, (
        stock.code,
        stock.name,
        screen_date,
        signal_type,
        screen_date
    ))
```

### update_pool_stock()
```python
def update_pool_stock(db_conn, stock, signal_type, screen_date, signal_result):
    """
    Update existing stock in pool with new signal.

    Args:
        db_conn: SQLite connection
        stock: Stock object
        signal_type: New signal type
        screen_date: Date of screening
        signal_result: Signal classification result dict
    """
    query = """
        UPDATE lao_ya_tou_pool
        SET current_signal = ?,
            last_screened_date = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE code = ?
    """
    db_conn.execute(query, (
        signal_type,
        screen_date,
        stock.code
    ))
```

### update_pool_screen_date()
```python
def update_pool_screen_date(db_conn, stock_code, screen_date):
    """
    Update only the last_screened_date for a pool stock.

    Args:
        db_conn: SQLite connection
        stock_code: Stock code
        screen_date: Date of screening
    """
    query = """
        UPDATE lao_ya_tou_pool
        SET last_screened_date = ?,
            last_updated = CURRENT_TIMESTAMP
        WHERE code = ?
    """
    db_conn.execute(query, (screen_date, stock_code))
```

### insert_signal_history()
```python
def insert_signal_history(db_conn, stock, old_signal, new_signal, change_date):
    """
    Insert signal change history record.

    Args:
        db_conn: SQLite connection
        stock: Stock object
        old_signal: Previous signal type (NULL if new entry)
        new_signal: New signal type
        change_date: Date of change
    """
    query = """
        INSERT INTO lao_ya_tou_signal_history (
            code, old_signal, new_signal, change_date, changed_by_screener
        ) VALUES (?, ?, ?, ?, ?)
    """
    db_conn.execute(query, (
        stock.code,
        old_signal,
        new_signal,
        change_date,
        LYT_SCREENER_CODE
    ))
```

### insert_screening_result()
```python
def insert_screening_result(db_conn, screener_id, stock, screen_date, signal_result):
    """
    Insert screening result into unified results table.

    Args:
        db_conn: SQLite connection
        screener_id: ID from screener_types
        stock: Stock object
        screen_date: Date of screening
        signal_result: Signal classification result dict
    """
    query = """
        INSERT INTO pool_screening_results (
            screener_id, code, screen_date, signal_type,
            score, price, stop_loss, position_size,
            action, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    db_conn.execute(query, (
        screener_id,
        stock.code,
        screen_date,
        signal_result['signal_type'],
        signal_result['confidence'],
        signal_result['price'],
        signal_result.get('stop_loss'),
        signal_result.get('position_size'),
        signal_result.get('action'),
        signal_result['description']
    ))
```

### build_screening_result()
```python
def build_screening_result(stock, signal_result):
    """
    Build screening result dict for display/API.

    Args:
        stock: Stock object
        signal_result: Signal classification result dict

    Returns:
        result_dict: Dictionary with screening result
    """
    return {
        'code': stock.code,
        'name': stock.name,
        'score': signal_result['confidence'],
        'signal_type': signal_result['signal_type'],
        'confidence': signal_result['confidence'],
        'price': signal_result['price'],
        'gap': signal_result['gap'],
        'volume_ratio': signal_result['volume_ratio'],
        'stop_loss': signal_result.get('stop_loss'),
        'position_size': signal_result.get('position_size'),
        'action': signal_result.get('action'),
        'description': signal_result['description'],
        'reason': f"{signal_result['signal_type']}: {signal_result['description']}"
    }
```

## Integration Points

### 1. Update LaoYaTouZhouXianScreener.__init__()
Add DB connection and screener_id initialization:
```python
def __init__(self, screener_name):
    super().__init__(screener_name)
    self.lyt_screener_id = None
    self._init_pool_integration()
```

### 2. Add _init_pool_integration()
```python
def _init_pool_integration(self):
    """
    Initialize pool integration by checking tables and getting screener ID.
    """
    self.db_conn = get_db_connection()
    self.lyt_screener_id = get_screener_id(self.db_conn, LYT_SCREENER_CODE)

    if self.lyt_screener_id is None:
        logger.error("LYT screener not found in screener_types table")
        raise RuntimeError("Pool not initialized")
```

### 3. Update run() method
Replace existing run() with pool-aware version:
```python
def run(self):
    """
    Run LYT screener with pool management.

    Returns:
        results: List of ScreenResult
        summary: Dictionary with stats including pool stats
    """
    target_date = self.current_date

    # Run two-stage screening with pool management
    results, summary = screen_and_manage_pool(self, target_date)

    # Add pool-specific stats to summary
    summary['pool_size'] = get_pool_size(self.db_conn)
    summary['pool_signal_distribution'] = get_pool_signal_distribution(self.db_conn)

    return results, summary
```

### 4. Add utility functions
```python
def get_pool_size(db_conn):
    """Get current pool size (number of stocks)."""
    query = "SELECT COUNT(*) FROM lao_ya_tou_pool"
    result = db_conn.execute(query).fetchone()
    return result[0]

def get_pool_signal_distribution(db_conn):
    """Get distribution of signal types in pool."""
    query = """
        SELECT current_signal, COUNT(*) as count
        FROM lao_ya_tou_pool
        GROUP BY current_signal
    """
    results = db_conn.execute(query).fetchall()
    return {row['current_signal']: row['count'] for row in results}
```

## Daily Workflow

```
1. Initialize screener
2. Run run() → screen_and_manage_pool()
   a. For each stock:
      i. Stage 1: Check LYT pattern
     ii. Stage 2: Classify signal type
    iii. Check pool status
     iv. INSERT/UPDATE lao_ya_tou_pool
      v. INSERT lao_ya_tou_signal_history (if signal changed)
     vi. INSERT pool_screening_results
3. Commit all DB changes
4. Return results with pool stats
```
