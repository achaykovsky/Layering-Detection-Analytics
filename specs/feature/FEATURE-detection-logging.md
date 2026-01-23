# Feature: Detection Logging

## Overview

Writes per-sequence detection logs to CSV for audit and analysis purposes. Provides detailed timing information for each detected suspicious sequence, enabling forensic analysis and pattern investigation.

## Purpose

Detection logs serve multiple purposes:
- **Audit Trail**: Record when and how patterns were detected
- **Forensic Analysis**: Investigate suspicious sequences in detail
- **Performance Monitoring**: Track detection timing and duration
- **Debugging**: Troubleshoot detection algorithm behavior

## Log Schema

### CSV Columns

1. **account_id**: Account identifier (may be pseudonymized)
2. **product_id**: Product identifier
3. **order_timestamps**: Semicolon-separated ISO timestamps of orders in sequence
4. **duration_seconds**: Float seconds between start and end timestamps

### Log Format

```csv
account_id,product_id,order_timestamps,duration_seconds
ACC001,IBM,2025-01-15T10:30:00+00:00;2025-01-15T10:30:05+00:00;2025-01-15T10:30:08+00:00,8.000
ACC002,GOOG,,1800.500
```

**Notes**:
- `order_timestamps`: Empty string for wash trading (not applicable)
- `duration_seconds`: Formatted to 3 decimal places
- Timestamps: ISO format with timezone

## Implementation

### Location

- **Module**: `src/layering_detection/logging_utils.py`
- **Function**: `write_detection_logs()`

### Function Signature

```python
def write_detection_logs(
    path: Path,
    sequences: Iterable[SuspiciousSequence],
    pseudonymize_accounts: bool = False,
    salt: str | None = None
) -> None:
    """
    Write detection logs for each suspicious sequence.
    
    Args:
        path: Output CSV file path
        sequences: Iterable of detected suspicious sequences
        pseudonymize_accounts: If True, hash account IDs (privacy)
        salt: Optional salt for pseudonymization
    """
```

## Features

### 1. Per-Sequence Logging

Each detected sequence generates one log row with:
- Account and product identifiers
- Order timestamps (for layering) or empty (for wash trading)
- Duration of the detection window

### 2. Account Pseudonymization

**Privacy Feature**: Optionally hash account IDs for privacy compliance.

**Usage**:
```python
write_detection_logs(
    path=Path("logs/detections.csv"),
    sequences=sequences,
    pseudonymize_accounts=True,
    salt="optional_salt"
)
```

**Implementation**: Uses SHA-256 hashing via `pseudonymize_account_id()` in `security_utils.py`.

**Format**: Hex-encoded SHA-256 digest (64 characters).

### 3. CSV Sanitization

All string values sanitized via `sanitize_for_csv()` to prevent formula injection.

### 4. Duration Calculation

Calculated as `(end_timestamp - start_timestamp).total_seconds()`:
- **Layering**: Time from first order placement to opposite trade execution
- **Wash Trading**: Time span of the 30-minute detection window

## API

### Basic Usage

```python
from layering_detection.utils.logging_utils import write_detection_logs
from pathlib import Path

# Write logs
write_detection_logs(
    path=Path("logs/detections.csv"),
    sequences=detected_sequences
)
```

### With Pseudonymization

```python
write_detection_logs(
    path=Path("logs/detections.csv"),
    sequences=sequences,
    pseudonymize_accounts=True,
    salt="production_salt_2025"
)
```

## Design Decisions

### 1. Separate Log File

**Decision**: Separate `detections.csv` from `suspicious_accounts.csv`.

**Rationale**:
- Different audiences (audit vs. business)
- Different schemas (detailed vs. summary)
- Different update frequencies

**Tradeoff**: Two files to manage instead of one.

### 2. Semicolon-Separated Timestamps

**Decision**: Use semicolons to separate multiple timestamps.

**Rationale**:
- Avoids conflicts with CSV comma delimiter
- Simple parsing for analysis tools
- Human-readable

**Tradeoff**: Requires custom parsing for timestamp lists.

### 3. Optional Order Timestamps

**Decision**: Empty string for wash trading (not applicable).

**Rationale**:
- Wash trading doesn't track individual order timestamps
- Unified schema for both detection types
- Clear indication when not applicable

**Tradeoff**: Requires null handling in analysis.

### 4. Pseudonymization Flag

**Decision**: Optional pseudonymization with configurable salt.

**Rationale**:
- Privacy compliance (HIPAA/GDPR)
- Configurable per environment
- Salt enables consistent hashing across runs

**Tradeoff**: Cannot reverse pseudonymization (by design).

## Data Flow

```
SuspiciousSequence
    ↓
write_detection_logs()
    ↓
Extract: account_id, product_id, order_timestamps, duration
    ↓
(Optional) Pseudonymize account_id
    ↓
Sanitize all strings
    ↓
Write CSV row
```

## Example Output

### Layering Detection Log

```csv
account_id,product_id,order_timestamps,duration_seconds
ACC001,IBM,2025-01-15T10:30:00+00:00;2025-01-15T10:30:05+00:00;2025-01-15T10:30:08+00:00,10.000
```

### Wash Trading Detection Log

```csv
account_id,product_id,order_timestamps,duration_seconds
ACC002,GOOG,,1800.000
```

### Pseudonymized Log

```csv
account_id,product_id,order_timestamps,duration_seconds
a1b2c3d4e5f6...,GOOG,,1800.000
```

## Performance Considerations

### Complexity

- **Time**: O(n) where n is number of sequences
- **Space**: O(1) (streaming write)
- **I/O**: Single pass write

### Optimization

- **Streaming**: Writes directly to file (no buffering)
- **Minimal Processing**: Simple string formatting
- **Efficient Hashing**: SHA-256 only when pseudonymization enabled

## Testing

### Test Coverage

- Unit tests: `tests/test_transaction_io.py` (includes logging tests)
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **Basic Logging**: Standard sequence logging
2. **Layering Logs**: Order timestamps populated
3. **Wash Trading Logs**: Order timestamps empty
4. **Pseudonymization**: Account IDs hashed correctly
5. **Duration Calculation**: Correct time differences
6. **CSV Format**: Valid CSV structure

## Security Considerations

### Privacy

- **Pseudonymization**: Optional account ID hashing
- **Salt Support**: Configurable salt for consistent hashing
- **No PII in Logs**: Only account/product IDs (no names, addresses)

### CSV Security

- **Sanitization**: All strings sanitized to prevent formula injection
- **Encoding**: UTF-8 encoding for international characters

## Error Handling

### File Errors

```python
# Permission denied
write_detection_logs(Path("/readonly/logs.csv"), [])  # IOError

# Invalid path
write_detection_logs(Path(""), [])  # IOError
```

### Data Errors

- **Missing Timestamps**: Handled gracefully (empty string for wash trading)
- **Invalid Duration**: Calculated from timestamps (should always be valid)

## Integration

### Pipeline Integration

Called from `runner.py` after detection:

```python
logs_path = logs_dir / "detections.csv"
write_detection_logs(logs_path, all_sequences)
```

### Directory Creation

Automatically creates parent directory if it doesn't exist:

```python
path.parent.mkdir(parents=True, exist_ok=True)
```

## Future Enhancements

1. **Structured Logging**: JSON format for machine parsing
2. **Log Rotation**: Automatic rotation for large log files
3. **Compression**: Gzip compression for archived logs
4. **Additional Metadata**: Algorithm version, config parameters
5. **Query Interface**: SQLite database for log querying
6. **Real-time Logging**: Stream logs to external systems (Kafka, etc.)
