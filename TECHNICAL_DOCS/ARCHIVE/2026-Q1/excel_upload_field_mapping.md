# Excel Upload Field Mapping Document

## File Information

- **File Format**: Tab-delimited text file (`.xls` extension, but actually TSV)
- **Encoding**: GBK
- **Date Source**: Extracted from filename (format: `全部Ａ股YYYYMMDD.xls`)
- **Stock Coverage**: All A-shares (includes ST, indices, Beijing Exchange)
- **Purpose**: Update daily stock data (overwrite existing data for the same date)

---

## Table 1: Daily Price Data (`daily_prices` table)

| Excel Column | DB Field | Data Type | Conversion Logic | Notes |
|-------------|----------|-----------|------------------|-------|
| **代码** | `code` | VARCHAR(10) | Remove `="` and `"`, keep 6 digits | Example: `="301683"` → `301683` |
| **今开** | `open` | FLOAT | Convert string to float | |
| **最高** | `high` | FLOAT | Convert string to float | |
| **最低** | `low` | FLOAT | Convert string to float | |
| **现价** | `close` | FLOAT | Convert string to float | |
| **昨收** | `preclose` | FLOAT | Convert string to float | |
| **涨幅%** | `pct_change` | FLOAT | Convert string to float | |
| **总量** | `volume` | FLOAT | Use as-is (already in "手") | DB stores volume in "手", not shares |
| **总金额** | `amount` | FLOAT | Multiply by 10,000 (convert from "万元" to yuan) | 1万元 = 10,000 yuan |
| **换手%** | `turnover` | FLOAT | Convert string to float | Already in percentage |
| **Filename** | `trade_date` | DATE | Extract from filename, format as YYYY-MM-DD | `全部Ａ股20260401.xls` → `2026-04-01` |
| | `updated_at` | DATETIME | Set to current timestamp | |

### Special Handling:
- **NULL values**: `--` → convert to NULL
- **Invalid numbers**: Skip record, log warning

---

## Table 2: Stock Metadata (`stocks` table)

| Excel Column | DB Field | Data Type | Conversion Logic | Notes |
|-------------|----------|-----------|------------------|-------|
| **代码** | `code` | VARCHAR(10) | Remove `="` and `"`, keep 6 digits | Primary key |
| **名称** | `name` | VARCHAR(50) | Trim whitespace | |
| **一二级行业** | `sector_lv1`, `sector_lv2` | VARCHAR(50) | Split by `-`: first part → `sector_lv1`, second part → `sector_lv2` | Format: `一级行业-二级行业` |
| **细分行业** | `industry` | VARCHAR(50) | Use as-is | |
| **地区** | `area` | VARCHAR(50) | Use as-is | |
| **上市日期** | `list_date` | DATE | Format as YYYY-MM-DD | `20260401` → `2026-04-01` |
| **总市值** | `total_market_cap` | REAL | Remove "亿", multiply by 100,000,000 | `"79.97亿"` → `7997000000.0` |
| **流通市值** | `circulating_market_cap` | REAL | Remove "亿", multiply by 100,000,000 | `"18.08亿"` → `1808000000.0` |
| **市盈(动)** | `pe_ratio` | REAL | Convert string to float, `"--"` → NULL | |
| **市净率** | `pb_ratio` | REAL | Convert string to float, `"--"` → NULL | |
| | `updated_at` | DATETIME | Set to current timestamp | |

### Fields NOT in Excel (keep existing values):
- `roe`, `debt_ratio`, `revenue`, `profit` - financial metrics (not in upload)
- `ifind_updated_at` - obsoleted field (not in upload)
- `is_delisted` - status flag (not in upload)
- `last_trade_date` - last trading date (not in upload)
- `asset_type` - default 'stock'

---

## Table 3: Stock Meta (`stock_meta` table)

| Excel Column | DB Field | Data Type | Conversion Logic | Notes |
|-------------|----------|-----------|------------------|-------|
| **代码** | `code` | VARCHAR(10) | Remove `="` and `"`, keep 6 digits | Primary key |
| **名称** | `name` | VARCHAR(50) | Trim whitespace | |
| **一二级行业** | `sector_lv1`, `sector_lv2` | VARCHAR(50) | Split by `-`: first part → `sector_lv1`, second part → `sector_lv2` | Format: `一级行业-二级行业` |
| **细分行业** | `industry` | VARCHAR(50) | Use as-is | |
| **地区** | `area` | VARCHAR(50) | Use as-is | |
| **上市日期** | `list_date` | DATE | Format as YYYY-MM-DD | |
| | `asset_type` | VARCHAR(10) | Set to 'stock' | Default value |
| | `is_delisted` | INTEGER | Keep existing value (not in upload) | |
| | `meta_source` | VARCHAR(20) | Set to 'excel_upload' | New source type |
| | `updated_at` | DATETIME | Set to current timestamp | |

### Fields NOT in Excel (keep existing values):
- `out_date` - delisting date
- `checksum`, `checked_at` - validation fields

---

## Data Conversion Rules

### 1. Stock Code Cleaning
```
Excel: ="301683"
DB:    301683
```

### 2. Amount Conversion (Yuan)
```
Excel: 147411.19  (in "万元")
DB:    1474111900.0  (in yuan)
Formula: float(value) * 10,000
```

### 3. Market Cap Conversion (Yuan)
```
Excel: "79.97亿"
DB:    7997000000.0
Formula: float(remove_bai(value)) * 100,000,000
```

### 3. Volume Conversion (No conversion needed)
```
Excel: 108230.0  (in "手")
DB:    108230.0  (in "手")
Formula: Use as-is (DB stores volume in "手")
```

### 4. Sector Field Parsing
```
Excel: "可选消费-医药"
DB:    sector_lv1='可选消费', sector_lv2='医药'
Formula: split(value, '-')
```

### 6. Date Extraction
```
Filename: 全部Ａ股20260401.xls
DB Date:  2026-04-01
Pattern:  全部Ａ股(\d{8})\.xls
```

### 7. Null Value Handling
```
Excel: "--" (common for PE/PB ratios)
DB:    NULL (None in Python)
```

### 8. Type Conversions
```
Excel String → DB Float:
  "61.66"  → 61.66
  "126.71" → 126.71
  "20.01"  → 20.01
```

---

## Upload Workflow

### Step 1: File Validation
- [ ] File name matches pattern: `全部Ａ股YYYYMMDD.xls`
- [ ] File can be read with GBK encoding, tab delimiter
- [ ] File has required columns (code, name, open, high, low, close, preclose, pct_change, volume, amount, turnover)
- [ ] Date from filename is valid

### Step 2: Data Parsing
- [ ] Read file with pandas (encoding='gbk', delimiter='\t')
- [ ] Clean stock codes (remove `="` and `"`)
- [ ] Convert data types (string → float/int/date)
- [ ] Handle "--" as NULL
- [ ] Extract trade_date from filename

### Step 3: Data Validation
- [ ] Validate required fields (no NULL in critical columns)
- [ ] Validate numeric ranges (e.g., prices > 0, volume >= 0)
- [ ] Count valid vs invalid records
- [ ] If error rate > threshold, reject entire upload

### Step 4: Database Update
- [ ] Begin transaction
- [ ] Insert/Update `daily_prices` for the trade_date
  - Use `INSERT OR REPLACE` to handle duplicates
- [ ] Update `stocks` metadata
  - Use `INSERT OR REPLACE` to update existing stocks
  - Insert new stocks if they don't exist
- [ ] Update `stock_meta` metadata
  - Use `INSERT OR REPLACE` to update existing stocks
  - Insert new stocks if they don't exist
- [ ] Commit transaction (rollback on error)

### Step 5: Summary Report
- [ ] Total records processed
- [ ] Records inserted/updated successfully
- [ ] Records skipped/failed
- [ ] Warnings and errors

---

## Error Handling

### File-Level Errors (Reject Upload)
- Invalid file name format
- Cannot read file (wrong encoding or format)
- Missing required columns
- Invalid date in filename

### Record-Level Errors (Skip Record, Log Warning)
- Missing required fields (code, open, high, low, close)
- Invalid numeric values (cannot convert to float)
- Negative prices or volume
- Invalid stock code format

### Validation Thresholds
- **Error rate > 5%**: Reject entire upload
- **Error rate 1-5%**: Show warning, allow upload
- **Error rate < 1%**: Proceed normally

---

## Sample Records

### Daily Prices Example:
```
Excel Row:
  代码="301683", 名称=N慧谷, 涨幅%=61.66, 现价=126.71, 今开=128.00,
  最高=158.00, 最低=126.00, 昨收=78.38, 总量=108230.0,
  总金额=147411.19, 换手%=75.87

DB Insert (daily_prices):
  code: '301683'
  trade_date: '2026-04-01'
  open: 128.0
  high: 158.0
  low: 126.0
  close: 126.71
  preclose: 78.38
  pct_change: 61.66
  volume: 108230.0  (in "手", stored as-is)
  amount: 1474111900.0  (147411.19 * 10,000, in yuan)
  turnover: 75.87
  updated_at: '2026-04-03 16:30:00'
```

### Stock Metadata Example:
```
Excel Row:
  代码="301683", 名称=N慧谷, 一二级行业=可选消费-医药, 细分行业=染料涂料, 地区=,
  上市日期=20260401, 总市值=79.97亿, 流通市值=18.08亿,
  市盈(动)=38.68, 市净率=3.46

DB Insert/Update (stocks):
  code: '301683'
  name: 'N慧谷'
  sector_lv1: '可选消费'  (parsed from "可选消费-医药")
  sector_lv2: '医药'  (parsed from "可选消费-医药")
  industry: '染料涂料'
  area: NULL
  list_date: '2026-04-01'
  total_market_cap: 7997000000.0  (79.97 * 100,000,000)
  circulating_market_cap: 1808000000.0  (18.08 * 100,000,000)
  pe_ratio: 38.68
  pb_ratio: 3.46
  updated_at: '2026-04-03 16:30:00'
```

---

## Implementation Notes

1. **No Stock Code Validation**: Do not check if stock exists in DB before inserting. New stocks (newly listed) will be inserted automatically.

2. **Data Preservation**: Existing data for dates NOT in the upload file will be preserved. Only the specific trade_date from the upload file is updated.

3. **All Stocks Included**: Upload file includes ST stocks, indices, Beijing Exchange stocks. All should be uploaded to DB, but screeners will filter them out via `StockFilter` class.

4. **Units Consistency**: Ensure all numeric values are converted to match DB storage format:
   - Volume: "手" (store as-is)
   - Amount: "万元" → yuan (multiply by 10,000)
   - Market Cap: "亿" → yuan (multiply by 100,000,000)

5. **Transaction Safety**: Use database transaction to ensure all-or-nothing update. If any step fails, rollback all changes.

6. **Trading Calendar**: Keep BaoStock integration for trading day validation and calendar management. The upload file's date should be validated against BaoStock trading calendar to ensure it's a valid trading day.

---

## Question for Confirmation

1. ✅ Market cap conversion: `"79.97亿"` → `7997000000.0` (multiply by 100,000,000)
2. ✅ Volume conversion: `108230.0` (手) → `108230.0` (store as-is, DB uses "手")
3. ✅ Amount conversion: `147411.19` (万元) → `1474111900.0` (multiply by 10,000 to get yuan)
4. ✅ Date: Extract from filename format `全部Ａ股YYYYMMDD.xls`
5. ✅ Existing data: Keep all, only overwrite for the specific trade_date
6. ✅ Stock code: No validation, allow new stocks
7. ✅ Error handling: Reject file if invalid, skip records with warnings
8. ✅ Trading calendar: Keep BaoStock for trading day validation

**Please confirm this mapping is correct before I proceed with implementation.**
