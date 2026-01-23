# Feature: Transaction I/O

## Overview

Handles reading transaction data from CSV files and writing detection results. Provides robust parsing, validation, and CSV sanitization to prevent security issues.

## Components

### Input: CSV Reading

- **Function**: `read_transactions(path: Path) -> List[TransactionEvent]`
- **Location**: `src/layering_detection/io.py`
- **Input Format**: CSV with columns: `timestamp`, `account_id`, `product_id`, `side`, `price`, `quantity`, `event_type`

### Output: CSV Writing

- **Function**: `write_suspicious_accounts(path: Path, sequences: Iterable[SuspiciousSequence]) -> None`
- **Location**: `src/layering_detection/io.py`
- **Output Format**: CSV with detection results (see Output Format section)

## Input Parsing

### CSV Schema

**Required Columns**:
- `timestamp`: ISO datetime string (e.g., `2025-01-15T10:30:00Z`)
- `account_id`: String identifier
- `product_id`: String identifier
- `side`: `"BUY"` or `"SELL"` (case-insensitive)
- `price`: Decimal string (must be positive)
- `quantity`: Integer string (must be positive)
- `event_type`: `"ORDER_PLACED"`, `"ORDER_CANCELLED"`, or `"TRADE_EXECUTED"` (case-insensitive)

### Parsing Functions

```python
def _parse_timestamp(raw: str) -> datetime:
    """Parse ISO timestamp with 'Z' UTC designator"""
    
def _parse_side(raw: str) -> Side:
    """Parse and validate BUY/SELL"""
    
def _parse_event_type(raw: str) -> EventType:
    """Parse and validate event type"""
    
def _parse_price(raw: str) -> Decimal:
    """Parse decimal price, validate > 0"""
    
def _parse_quantity(raw: str) -> int:
    """Parse integer quantity, validate > 0"""
```

### Error Handling

**Invalid Rows**:
- Skipped with warning log message
- Does not abort entire pipeline
- Logs row number and error reason

**Missing File**:
- Raises `FileNotFoundError` with clear message

**Validation Rules**:
- Timestamps: Must be valid ISO format (handles trailing 'Z')
- Side: Must be exactly "BUY" or "SELL"
- Event Type: Must be one of the three allowed types
- Price: Must be positive decimal
- Quantity: Must be positive integer

### Example Input

```csv
timestamp,account_id,product_id,side,price,quantity,event_type
2025-01-15T10:30:00Z,ACC001,IBM,BUY,100.50,1000,ORDER_PLACED
2025-01-15T10:30:05Z,ACC001,IBM,BUY,100.75,2000,ORDER_PLACED
2025-01-15T10:30:08Z,ACC001,IBM,BUY,100.25,1500,ORDER_CANCELLED
```

## Output Writing

### CSV Schema

**Core Columns** (all detection types):
- `account_id`: Suspicious account identifier
- `product_id`: Product where activity detected
- `total_buy_qty`: Total BUY quantity (integer)
- `total_sell_qty`: Total SELL quantity (integer)
- `num_cancelled_orders`: Count of cancelled orders (integer, 0 for wash trading)
- `detected_timestamp`: ISO datetime of detection

**Additional Columns** (multi-algorithm support):
- `detection_type`: `"LAYERING"` or `"WASH_TRADING"`

**Wash Trading Columns** (empty for layering):
- `alternation_percentage`: Decimal (2 places) or empty string
- `price_change_percentage`: Decimal (2 places) or empty string

### Output Format

```python
def write_suspicious_accounts(
    path: Path,
    sequences: Iterable[SuspiciousSequence]
) -> None:
    """Write unified suspicious accounts CSV"""
```

### CSV Sanitization

**Security Feature**: Prevents formula injection in Excel/Sheets.

**Implementation**: `sanitize_for_csv()` in `security_utils.py`

**Rules**:
- If value starts with `=`, `+`, `-`, or `@`, prefix with single quote `'`
- Prevents Excel from interpreting as formula

**Example**:
```python
sanitize_for_csv("=SUM(A1:A10)")  # Returns "'=SUM(A1:A10)"
sanitize_for_csv("normal_value")  # Returns "normal_value"
```

### Example Output

```csv
account_id,product_id,total_buy_qty,total_sell_qty,num_cancelled_orders,detected_timestamp,detection_type,alternation_percentage,price_change_percentage
ACC001,IBM,3000,2000,3,2025-01-15T10:30:10Z,LAYERING,,
ACC002,GOOG,12000,12000,0,2025-01-15T11:00:00Z,WASH_TRADING,80.00,1.25
```

## API

### read_transactions()

```python
def read_transactions(path: Path) -> List[TransactionEvent]:
    """
    Read transactions CSV into TransactionEvent objects.
    
    Args:
        path: Path to input CSV file
        
    Returns:
        List of TransactionEvent objects (unsorted, ungrouped)
        
    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If CSV format is invalid (rare, usually skips rows)
    """
```

### write_suspicious_accounts()

```python
def write_suspicious_accounts(
    path: Path,
    sequences: Iterable[SuspiciousSequence]
) -> None:
    """
    Write suspicious accounts CSV.
    
    Args:
        path: Output file path (parent directory created if needed)
        sequences: Iterable of detected suspicious sequences
        
    Raises:
        IOError: If directory cannot be created or file cannot be written
    """
```

## Design Decisions

### 1. Fail-Safe Parsing

**Decision**: Skip invalid rows with warnings instead of aborting.

**Rationale**:
- Handles data quality issues gracefully
- Allows partial results from partially valid data
- Logs issues for investigation

**Tradeoff**: May hide systematic data quality problems.

### 2. CSV Sanitization

**Decision**: Sanitize all string values before writing.

**Rationale**:
- Prevents formula injection attacks
- Safe for Excel/Sheets opening
- Minimal performance impact

**Tradeoff**: Slight overhead on every string write.

### 3. Unified Output Schema

**Decision**: Single CSV with optional columns for different detection types.

**Rationale**:
- Simpler than separate files per algorithm
- Easy to filter by `detection_type`
- Maintains backward compatibility

**Tradeoff**: Some columns empty for certain detection types.

### 4. Decimal Precision

**Decision**: Use `Decimal` for prices, `int` for quantities.

**Rationale**:
- Avoids floating-point precision issues
- Accurate financial calculations
- Type safety

**Tradeoff**: Slightly more complex parsing.

## Performance Considerations

### Input Reading

- **Complexity**: O(n) where n is number of rows
- **Memory**: O(n) for storing all events
- **I/O**: Single pass through file

### Output Writing

- **Complexity**: O(m) where m is number of sequences
- **Memory**: O(1) (streaming write)
- **I/O**: Single pass write

### Optimization Opportunities

1. **Streaming**: For very large files, stream events instead of loading all
2. **Chunked Processing**: Process in chunks to reduce memory
3. **Parallel I/O**: Read/write in parallel (future enhancement)

## Testing

### Test Coverage

- Unit tests: `tests/test_transaction_io.py`
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **Valid Input**: Standard CSV parsing
2. **Invalid Rows**: Skipped with warnings
3. **Missing Columns**: Error handling
4. **Type Validation**: Invalid types rejected
5. **Edge Cases**: Empty file, single row, large file
6. **Output Format**: Correct CSV structure and sanitization

## Security Considerations

### Input Validation

- **Type Checking**: All fields validated and typed
- **Range Validation**: Prices and quantities must be positive
- **Enum Validation**: Side and event_type must be valid values

### Output Sanitization

- **Formula Injection**: Prevented via `sanitize_for_csv()`
- **CSV Injection**: Handled by proper CSV escaping
- **Encoding**: UTF-8 encoding for international characters

## Error Handling

### Input Errors

```python
# Missing file
read_transactions(Path("nonexistent.csv"))  # FileNotFoundError

# Invalid row (skipped with warning)
# Row with invalid price: logs warning, continues
```

### Output Errors

```python
# Permission denied
write_suspicious_accounts(Path("/readonly/file.csv"), [])  # IOError

# Invalid path
write_suspicious_accounts(Path(""), [])  # IOError
```

## Future Enhancements

1. **Streaming I/O**: Process large files without loading all into memory
2. **Compression**: Support gzip/bzip2 compressed input files
3. **Multiple Formats**: Support JSON, Parquet input formats
4. **Schema Validation**: Explicit schema validation with detailed errors
5. **Incremental Processing**: Process only new/changed rows
