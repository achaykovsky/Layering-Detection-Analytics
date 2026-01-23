# Feature: Wash Trading Detection Algorithm

## Overview

Detects suspicious wash trading manipulation patterns in transaction data. Wash trading occurs when traders repeatedly buy and sell the same instrument to create false market activity without changing their net position.

## Detection Pattern

The algorithm detects wash trading when all of the following conditions are met within a 30-minute sliding window:

1. **Volume Threshold**: ≥3 BUY trades and ≥3 SELL trades executed
2. **Alternation**: ≥60% alternation (side switches between consecutive trades)
3. **Total Volume**: ≥10,000 total volume (sum of all trade quantities)
4. **Price Change** (optional): ≥1% price change during the window (bonus criterion)

### Timing Window

- **Detection Window**: 30 minutes (sliding window)
- **Event Filter**: Only `TRADE_EXECUTED` events are considered (orders and cancellations ignored)

### Metrics

- **Alternation Percentage**: Calculated as `(side_switches / (total_trades - 1)) * 100`
- **Price Change Percentage**: `((max_price - min_price) / min_price) * 100`

## Architecture

### Implementation Location

- **Core Logic**: `src/layering_detection/wash_trading_detector.py` - `detect_wash_trading()`
- **Algorithm Wrapper**: `src/layering_detection/algorithms/wash_trading.py` - `WashTradingDetectionAlgorithm`
- **Domain Models**: `src/layering_detection/models.py`

### Design Decisions

1. **Event Filtering**: Pre-filters to `TRADE_EXECUTED` events only (via `filter_events()`)
2. **Sliding Window**: Uses 30-minute sliding windows to detect patterns
3. **Grouping**: Events grouped by `(account_id, product_id)` before detection
4. **Optional Criteria**: Price change is optional (bonus), not required for detection

### Algorithm Interface

```python
@AlgorithmRegistry.register
class WashTradingDetectionAlgorithm(DetectionAlgorithm):
    @property
    def name(self) -> str:
        return "wash_trading"
    
    def filter_events(self, events: Iterable[TransactionEvent]) -> List[TransactionEvent]:
        # Filter to TRADE_EXECUTED only
    
    def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        # Implementation
```

## API

### Function Signature

```python
def detect_wash_trading(
    events: Iterable[TransactionEvent]
) -> List[SuspiciousSequence]
```

### Parameters

- **events**: Iterable of `TransactionEvent` objects (should be filtered to `TRADE_EXECUTED`)

### Returns

List of `SuspiciousSequence` objects with:
- `detection_type`: `"WASH_TRADING"`
- `alternation_percentage`: Percentage of side switches (≥60%)
- `price_change_percentage`: Optional price change (≥1% if present, None otherwise)
- `account_id`, `product_id`: Identifiers
- `total_buy_qty`, `total_sell_qty`: Aggregated quantities (≥3 each)
- `start_timestamp`, `end_timestamp`: 30-minute window boundaries
- `side`: `None` (not applicable to wash trading)
- `num_cancelled_orders`: `None` (not applicable)
- `order_timestamps`: `None` (not applicable)

### Example Usage

```python
from layering_detection.algorithms import AlgorithmRegistry
from layering_detection.utils.transaction_io import read_transactions
from pathlib import Path

# Get algorithm from registry
algorithm = AlgorithmRegistry.get("wash_trading")

# Read events
events = read_transactions(Path("input/transactions.csv"))

# Detect sequences (automatically filters to TRADE_EXECUTED)
sequences = algorithm.detect(events)

# Process results
for seq in sequences:
    print(f"Detected wash trading: {seq.account_id} on {seq.product_id}")
    print(f"  Alternation: {seq.alternation_percentage:.2f}%")
    if seq.price_change_percentage:
        print(f"  Price change: {seq.price_change_percentage:.2f}%")
```

## Performance Characteristics

### Complexity

- **Time**: O(n²) where n is the number of `TRADE_EXECUTED` events per `(account_id, product_id)` group
- **Space**: O(n) for event storage and sliding window tracking

### Optimization Opportunities

1. **Event Filtering**: Pre-filtering reduces input size before detection
2. **Sliding Window**: Efficient window management for 30-minute intervals
3. **Early Termination**: Can skip groups with insufficient volume

## Configuration

Currently hardcoded thresholds:
- **Min BUY trades**: 3
- **Min SELL trades**: 3
- **Min alternation**: 60%
- **Min total volume**: 10,000
- **Window size**: 30 minutes
- **Optional price change**: 1%

Future enhancement: Extract to `WashTradingConfig` similar to `DetectionConfig`.

## Edge Cases

1. **Insufficient Volume**: Groups with <10,000 total volume are skipped
2. **Low Alternation**: Groups with <60% alternation are not detected
3. **Boundary Conditions**: Sliding window boundaries handled correctly
4. **Price Change**: Price change is optional; detection occurs even if <1%

## Testing

### Test Coverage

- Unit tests: `tests/test_wash_trading_detector.py`
- Algorithm tests: `tests/test_algorithms_wash_trading.py`
- Comprehensive tests: `tests/test_wash_trading_comprehensive.py`
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **Basic Pattern**: Standard wash trading with high alternation
2. **Volume Thresholds**: Exactly 3 BUY/SELL trades, exactly 10,000 volume
3. **Alternation Edge Cases**: Exactly 60% alternation, 100% alternation
4. **Price Change**: With and without ≥1% price change
5. **Sliding Windows**: Multiple overlapping windows
6. **No Matches**: Events that don't form wash trading patterns

## Dependencies

- **Domain Models**: `TransactionEvent`, `SuspiciousSequence`
- **I/O**: `read_transactions()` for input
- **Registry**: `AlgorithmRegistry` for plugin architecture

## Extension Points

### Algorithm Registry

The algorithm is automatically registered via `@AlgorithmRegistry.register` decorator:

```python
algorithm = AlgorithmRegistry.get("wash_trading")
```

### Custom Filtering

The algorithm implements `filter_events()` to pre-filter events:

```python
algorithm = WashTradingDetectionAlgorithm()
filtered = algorithm.filter_events(events)  # Only TRADE_EXECUTED
sequences = algorithm.detect(filtered)
```

## Output Format

### SuspiciousSequence Fields

For wash trading detections:
- `detection_type`: `"WASH_TRADING"`
- `alternation_percentage`: Float (e.g., 80.0 for 80%)
- `price_change_percentage`: Float | None (None if <1% or not calculated)
- `side`: `None`
- `num_cancelled_orders`: `None`
- `order_timestamps`: `None`

### CSV Output

In `suspicious_accounts.csv`:
- `alternation_percentage`: Decimal with 2 places (empty string for LAYERING)
- `price_change_percentage`: Decimal with 2 places (empty string if <1% or LAYERING)

## Security Considerations

- **Input Validation**: All events validated during I/O parsing
- **Type Safety**: Strict type hints prevent invalid data flow
- **Immutability**: Frozen dataclasses prevent accidental mutation

## Future Enhancements

1. **Configurable Thresholds**: Extract thresholds to `WashTradingConfig`
2. **Performance Optimization**: Optimize sliding window algorithm (currently O(n²))
3. **Multi-product Patterns**: Detect wash trading across related products
4. **Adaptive Thresholds**: Dynamic thresholds based on market conditions
5. **Volume-weighted Metrics**: Consider trade sizes in alternation calculation
