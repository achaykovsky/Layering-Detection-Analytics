# Feature: Security Utilities

## Overview

Security and sanitization utilities to protect against CSV injection attacks and enable privacy-compliant account pseudonymization. Critical for production deployments handling sensitive financial data.

## Components

### 1. CSV Sanitization

**Function**: `sanitize_for_csv(value: str) -> str`  
**Location**: `src/layering_detection/security_utils.py`  
**Purpose**: Prevents formula injection in Excel/Google Sheets

### 2. Account Pseudonymization

**Function**: `pseudonymize_account_id(account_id: str, salt: str | None = None) -> str`  
**Location**: `src/layering_detection/security_utils.py`  
**Purpose**: Hash account IDs for privacy compliance

## CSV Sanitization

### Threat Model

**CSV Formula Injection**: Malicious CSV values starting with `=`, `+`, `-`, or `@` are interpreted as formulas by Excel/Google Sheets, potentially executing code or accessing external resources.

**Example Attack**:
```csv
account_id,product_id
=HYPERLINK("http://evil.com", "Click"),IBM
```

### Implementation

```python
def sanitize_for_csv(value: str) -> str:
    """
    Make a string safer for use in CSV cells.
    
    If the first character is =, +, -, or @, prefix with single quote
    to prevent formula interpretation.
    """
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value
```

### Protection Rules

**Prefix with `'` if value starts with**:
- `=` (formula)
- `+` (formula)
- `-` (formula or negative number)
- `@` (formula in older Excel)

**Result**: Excel/Sheets treat as literal string, not formula.

### Usage

Applied automatically in:
- `io.py`: `write_suspicious_accounts()` - all string fields
- `logging_utils.py`: `write_detection_logs()` - account_id, product_id

### Example

```python
from layering_detection.utils.security_utils import sanitize_for_csv

# Malicious input
sanitize_for_csv("=SUM(A1:A10)")  # Returns "'=SUM(A1:A10)"

# Normal input
sanitize_for_csv("ACC001")  # Returns "ACC001"

# Edge cases
sanitize_for_csv("")  # Returns ""
sanitize_for_csv("+123")  # Returns "'+123"
```

## Account Pseudonymization

### Purpose

**Privacy Compliance**: Hash account IDs to comply with:
- **HIPAA**: Healthcare data privacy
- **GDPR**: EU data protection
- **Internal Policies**: Data minimization

**Use Cases**:
- Log files shared with external auditors
- Analytics on sensitive accounts
- Compliance reporting

### Implementation

```python
def pseudonymize_account_id(account_id: str, salt: str | None = None) -> str:
    """
    Return pseudonymized representation using SHA-256.
    
    If salt provided, concatenated with account_id before hashing.
    Result is hex-encoded string (64 characters).
    """
    material = account_id if salt is None else f"{salt}:{account_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest
```

### Algorithm

1. **Material**: `account_id` or `salt:account_id` (if salt provided)
2. **Hash**: SHA-256 of UTF-8 encoded material
3. **Output**: Hex-encoded digest (64 characters)

### Salt Usage

**Purpose**: Enable consistent pseudonymization across runs.

**Without Salt**:
- Same account ID → same hash (deterministic)
- Enables correlation across files

**With Salt**:
- Same account ID + salt → same hash
- Different salt → different hash
- Enables environment-specific pseudonymization

### Example

```python
from layering_detection.utils.security_utils import pseudonymize_account_id

# Without salt
hash1 = pseudonymize_account_id("ACC001")
# Returns: "a1b2c3d4e5f6..." (64 hex chars)

# With salt
hash2 = pseudonymize_account_id("ACC001", salt="production_2025")
# Returns: "f6e5d4c3b2a1..." (different hash)

# Deterministic
hash1_again = pseudonymize_account_id("ACC001")
assert hash1 == hash1_again  # True
```

### Usage

**In Detection Logs**:
```python
write_detection_logs(
    path=Path("logs/detections.csv"),
    sequences=sequences,
    pseudonymize_accounts=True,
    salt="production_salt_2025"
)
```

**Manual Usage**:
```python
from layering_detection.utils.security_utils import pseudonymize_account_id

pseudonymized = pseudonymize_account_id("ACC001", salt="my_salt")
```

## Security Properties

### CSV Sanitization

- **Protection**: Prevents formula injection
- **Coverage**: All string fields in CSV output
- **Performance**: O(1) per string (single character check)
- **Limitation**: Only protects against formula injection, not other CSV issues

### Pseudonymization

- **Algorithm**: SHA-256 (cryptographically secure)
- **Irreversibility**: One-way hash (cannot recover original)
- **Determinism**: Same input → same output (with same salt)
- **Collision Resistance**: Extremely low probability of collisions

## Design Decisions

### 1. Prefix-Based Sanitization

**Decision**: Prefix dangerous characters with `'` instead of escaping.

**Rationale**:
- Simple and effective
- Excel/Sheets recognize `'` as literal prefix
- Minimal performance impact

**Tradeoff**: Doesn't handle all edge cases (e.g., tab characters), but covers common attacks.

### 2. SHA-256 for Pseudonymization

**Decision**: Use SHA-256 instead of MD5 or SHA-1.

**Rationale**:
- Cryptographically secure
- Widely supported
- Standard library (no dependencies)

**Tradeoff**: Slightly slower than MD5, but security is more important.

### 3. Optional Salt

**Decision**: Make salt optional, not required.

**Rationale**:
- Flexibility for different use cases
- Deterministic without salt (useful for correlation)
- Salt enables environment-specific hashing

**Tradeoff**: Without salt, same account IDs hash to same value (may be desired or not).

## Performance Considerations

### CSV Sanitization

- **Complexity**: O(1) per string
- **Overhead**: Single character check
- **Impact**: Negligible (<1% of I/O time)

### Pseudonymization

- **Complexity**: O(1) per account ID
- **Overhead**: SHA-256 hash computation
- **Impact**: ~1-10 microseconds per account ID

**Optimization**: Only called when `pseudonymize_accounts=True`, so zero overhead in default mode.

## Testing

### Test Coverage

- Unit tests: `tests/test_transaction_io.py` (includes security tests)
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **CSV Sanitization**:
   - Formula injection attempts (`=`, `+`, `-`, `@`)
   - Normal values (no sanitization needed)
   - Edge cases (empty strings, single characters)

2. **Pseudonymization**:
   - Without salt (deterministic)
   - With salt (consistent with same salt)
   - Different salts (different hashes)
   - Empty strings
   - Special characters

## Security Best Practices

### CSV Sanitization

- **Apply Everywhere**: All string fields in CSV output
- **Don't Skip**: Even "trusted" fields should be sanitized
- **Test Edge Cases**: Verify with actual Excel/Sheets

### Pseudonymization

- **Use Salt in Production**: Prevents rainbow table attacks
- **Store Salt Securely**: Use environment variables or secrets manager
- **Document Salt**: Record salt values for audit/correlation
- **One-Way Only**: Never attempt to reverse pseudonymization

## Limitations

### CSV Sanitization

- **Not Complete**: Only handles formula injection, not all CSV issues
- **Excel-Specific**: Primarily protects against Excel/Sheets
- **Visual Artifact**: `'` prefix visible in some viewers

### Pseudonymization

- **Irreversible**: Cannot recover original account IDs
- **No Correlation**: Without salt, cannot correlate across environments
- **Hash Length**: 64 characters (may be long for some systems)

## Future Enhancements

1. **Enhanced CSV Sanitization**: Handle tab characters, newlines, quotes
2. **Configurable Sanitization**: Allow disabling for trusted environments
3. **Multiple Hash Algorithms**: Support SHA-512, Blake2b
4. **Keyed Hashing**: Use HMAC for pseudonymization
5. **Tokenization**: Reversible tokenization for internal use
6. **Audit Logging**: Log when pseudonymization is applied
