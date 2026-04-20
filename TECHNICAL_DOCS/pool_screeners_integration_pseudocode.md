# Pool Screeners Integration Pseudocode

## Purpose
Update 5 screeners to query stock pool and insert results into unified table.

## Screeners to Update
1. 二板回调 (er_ban_hui_tiao_screener)
2. 涨停试盘线 (shi_pan_xian_screener)
3. 金凤凰 (jin_feng_huang_screener)
4. 银凤凰 (yin_feng_huang_screener)
5. 涨停倍量阴 (zhang_ting_bei_liang_yin_screener)

## Constants
```python
SCREENER_CODES = {
    'er_ban_hui_tiao': '二板回调',
    'shi_pan_xian': '涨停试盘线',
    'jin_feng_huang': '金凤凰',
    'yin_feng_huang': '银凤凰',
    'zhang_ting_bei_liang_yin': '涨停倍量阴'
}
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
    if not result:
        logger.error(f"Screener {screener_code} not found in screener_types")
        return None
    return result['id']
```

### get_pool_stocks()
```python
def get_pool_stocks(db_conn):
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
```

### get_pool_stock_codes()
```python
def get_pool_stock_codes(db_conn):
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
```

### insert_pool_screening_result()
```python
def insert_pool_screening_result(db_conn, screener_id, code, screen_date, result):
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
        json.dumps(result.get('extra', {}))  # Additional screener-specific data
    ))
```

## Base Screener Modifications

All 5 screeners need the same modifications to work with pool system.

### 1. Add pool integration to __init__()

```python
def __init__(self, screener_name, use_pool=True):
    """
    Initialize screener with optional pool integration.

    Args:
        screener_name: Screener name
        use_pool: If True, run against pool; if False, run against all stocks
    """
    # Existing initialization
    super().__init__(screener_name)

    # New: Pool integration
    self.use_pool = use_pool
    self.pool_screener_id = None

    if self.use_pool:
        self._init_pool_integration()
```

### 2. Add _init_pool_integration()

```python
def _init_pool_integration(self):
    """
    Initialize pool integration: get screener ID, verify pool exists.
    """
    db_conn = get_db_connection()

    # Get screener ID from screener_types
    screener_code = self.get_screener_code()  # Each screener implements this
    self.pool_screener_id = get_screener_id(db_conn, screener_code)

    if self.pool_screener_id is None:
        logger.error(f"{screener_code}: Screener not found in screener_types")
        raise RuntimeError(f"Pool not initialized for {screener_code}")

    # Verify pool is not empty
    pool_size = get_pool_size(db_conn)
    if pool_size == 0:
        logger.warning(f"{screener_code}: Pool is empty, no stocks to screen")
        self.use_pool = False

    db_conn.close()
```

### 3. Add get_screener_code() (abstract method)

Each screener must implement this:
```python
@abstractmethod
def get_screener_code(self):
    """Return this screener's code for DB lookup."""
    pass
```

### 4. Modify run() method

```python
def run(self):
    """
    Run screener against pool or all stocks.

    Returns:
        results: List of ScreenResult
        summary: Dictionary with stats
    """
    cur = self.current_date
    screener_code = self.get_screener_code()

    if not self.use_pool:
        # Original behavior: screen all stocks
        return super().run()  # Use BaseScreener.run()

    # New behavior: screen only pool stocks
    logger.info(
        "[%s] 开始选股（from pool），基准日期=%s",
        screener_code, cur
    )

    # Get stocks from pool
    db_conn = get_db_connection()
    pool_stocks = get_pool_stocks(db_conn)
    db_conn.close()

    logger.info(
        "[%s] 从池中获取 %d 只股票",
        screener_code, len(pool_stocks)
    )

    results_raw = []
    processed = errors = 0

    for code, name in pool_stocks:
        try:
            # Call screen_stock for this stock
            result = self.screen_stock(code, name)

            if result is not None:
                # Convert to ScreenResult
                screen_result = ScreenResult(
                    code=result['code'],
                    name=result['name'],
                    score=result.get('score', 0.0),
                    reason=result.get('reason', ''),
                    extra={k: v for k, v in result.items()
                           if k not in ('code', 'name', 'score', 'reason')}
                )
                results_raw.append(screen_result)

                # Insert into pool_screening_results
                self._insert_pool_result(result)

            processed += 1

        except Exception as exc:
            logger.warning(
                "[%s] 处理 %s 异常: %s",
                screener_code, code, exc
            )
            errors += 1

    # Build summary
    summary = {
        'screener': screener_code,
        'date': cur,
        'mode': 'pool',
        'pool_size': len(pool_stocks),
        'total_stocks': len(pool_stocks),
        'processed': processed,
        'errors': errors,
        'hits': len(results_raw)
    }

    logger.info(
        "[%s] 选股完成: 命中=%d / 处理=%d / 错误=%d",
        screener_code, len(results_raw), processed, errors
    )

    return results_raw, summary
```

### 5. Add _insert_pool_result()

```python
def _insert_pool_result(self, result):
    """
    Insert screening result into pool_screening_results table.

    Args:
        result: Screening result dict from screen_stock()
    """
    if self.pool_screener_id is None:
        logger.warning("Screener ID not set, skipping pool insert")
        return

    try:
        db_conn = get_db_connection()
        insert_pool_screening_result(
            db_conn,
            self.pool_screener_id,
            result['code'],
            self.current_date,
            result
        )
        db_conn.commit()
        db_conn.close()

        logger.debug(
            "Inserted pool result for %s: %s",
            result['code'], result.get('signal_type', 'N/A')
        )
    except Exception as e:
        logger.error(f"Error inserting pool result: {e}")
```

## Screener-Specific Implementations

### ErBanHuiTiaoScreener (二板回调)

```python
class ErBanHuiTiaoScreener(BaseScreener):

    def get_screener_code(self):
        return 'er_ban_hui_tiao'

    def __init__(self, screener_name, use_pool=True):
        super().__init__(screener_name, use_pool=use_pool)

    # Rest of existing screen_stock() implementation unchanged
```

### ShiPanXianScreener (涨停试盘线)

```python
class ShiPanXianScreener(BaseScreener):

    def get_screener_code(self):
        return 'shi_pan_xian'

    def __init__(self, screener_name, use_pool=True):
        super().__init__(screener_name, use_pool=use_pool)

    # Rest of existing screen_stock() implementation unchanged
```

### JinFengHuangScreener (金凤凰)

```python
class JinFengHuangScreener(BaseScreener):

    def get_screener_code(self):
        return 'jin_feng_huang'

    def __init__(self, screener_name, use_pool=True):
        super().__init__(screener_name, use_pool=use_pool)

    # Rest of existing screen_stock() implementation unchanged
```

### YinFengHuangScreener (银凤凰)

```python
class YinFengHuangScreener(BaseScreener):

    def get_screener_code(self):
        return 'yin_feng_huang'

    def __init__(self, screener_name, use_pool=True):
        super().__init__(screener_name, use_pool=use_pool)

    # Rest of existing screen_stock() implementation unchanged
```

### ZhangTingBeiLiangYinScreener (涨停倍量阴)

```python
class ZhangTingBeiLiangYinScreener(BaseScreener):

    def get_screener_code(self):
        return 'zhang_ting_bei_liang_yin'

    def __init__(self, screener_name, use_pool=True):
        super().__init__(screener_name, use_pool=use_pool)

    # Rest of existing screen_stock() implementation unchanged
```

## Daily Pool Screening Workflow

```
For each of 5 screeners:
1. Initialize with use_pool=True
2. run() → get pool stocks from lao_ya_tou_pool
3. For each pool stock:
    a. Run screen_stock()
    b. If result found, insert into pool_screening_results
4. Return results with summary
```

## Backward Compatibility

If use_pool=False:
- Screener runs original behavior (all stocks)
- Does not query pool
- Does not insert into pool_screening_results

This allows existing non-pool usage if needed.
