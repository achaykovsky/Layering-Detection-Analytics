# Feature: Layering Detection Algorithm

## Overview

Detects suspicious layering manipulation patterns in transaction data. Layering is a market manipulation technique where traders place multiple orders on one side to create false market signals, cancel them, then execute trades on the opposite side.

## Detection Pattern

The algorithm detects a 3-step pattern:

1. **Order Placement**: ≥3 orders placed on the same side (BUY or SELL) within a 10-second window
2. **Order Cancellation**: All placed orders are cancelled within 5 seconds of their placement
3. **Opposite Trade**: An opposite-side trade is executed within 2 seconds after the last cancellation

### Timing Windows

- **Orders Window**: 10 seconds (configurable via `DetectionConfig.orders_window`)
- **Cancel Window**: 5 seconds (configurable via `DetectionConfig.cancel_window`)
- **Opposite Trade Window**: 2 seconds (configurable via `DetectionConfig.opposite_trade_window`)

## Architecture

### Implementation Location

- **Core Logic**: `src/layering_detection/detector.py` - `detect_suspicious_sequences()`
- **Algorithm Wrapper**: `src/layering_detection/algorithms/layering.py` - `LayeringDetectionAlgorithm`
- **Domain Models**: `src/layering_detection/models.py`

### Design Decisions

1. **Grouping Strategy**: Events grouped by `(account_id, product_id)` before detection
2. **Time-based Queries**: Uses indexed queries (O(n log n)) for efficient time window lookups
3. **Hybrid Approach**: Linear scan for small groups (<100 events), indexed queries for larger groups
4. **Immutability**: All domain models are frozen dataclasses

### Algorithm Interface

```python
@AlgorithmRegistry.register
class LayeringDetectionAlgorithm(DetectionAlgorithm):
    @property
    def name(self) -> str:
        return "layering"
    
    @property
    def description(self) -> str:
        return "Detects suspicious layering patterns..."
    
    def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        # Implementation
```

## API

### Function Signature

```python
def detect_suspicious_sequences(
    events: Iterable[TransactionEvent],
    config: DetectionConfig | None = None
) -> List[SuspiciousSequence]
```

### Parameters

- **events**: Iterable of `TransactionEvent` objects to analyze
- **config**: Optional `DetectionConfig` for custom timing windows (defaults to 10s/5s/2s)

### Returns

List of `SuspiciousSequence` objects with:
- `detection_type`: `"LAYERING"`
- `side`: The side of the orders (BUY or SELL)
- `num_cancelled_orders`: Count of cancelled orders (≥3)
- `order_timestamps`: List of timestamps for placed orders
- `account_id`, `product_id`: Identifiers
- `total_buy_qty`, `total_sell_qty`: Aggregated quantities
- `start_timestamp`, `end_timestamp`: Detection window boundaries

### Example Usage

```python
from layering_detection.algorithms import AlgorithmRegistry
from layering_detection.utils.transaction_io import read_transactions
from pathlib import Path

# Get algorithm from registry
algorithm = AlgorithmRegistry.get("layering")

# Read events
events = read_transactions(Path("input/transactions.csv"))

# Detect sequences
sequences = algorithm.detect(events)

# Process results
for seq in sequences:
    print(f"Detected layering: {seq.account_id} on {seq.product_id}")
    print(f"  Side: {seq.side}, Cancelled: {seq.num_cancelled_orders}")
```

## Performance Characteristics

### Complexity

- **Time**: O(n log n) where n is the number of events per `(account_id, product_id)` group
- **Space**: O(n) for event indexing and result storage

### Optimization Strategy

1. **Indexed Queries**: Build event index by `(event_type, side)` with sorted timestamps
2. **Binary Search**: Use binary search for time window queries instead of linear scans
3. **Hybrid Approach**: Use linear scan for small groups (cache-friendly), indexed queries for large groups

### Performance Tradeoffs

- **Index Building**: O(n log n) upfront cost for sorting
- **Query Efficiency**: O(log n) per query vs O(n) for linear scan
- **Memory**: Additional O(n) space for index structures

## Configuration

### DetectionConfig

```python
@dataclass(frozen=True)
class DetectionConfig:
    orders_window: timedelta = timedelta(seconds=10)
    cancel_window: timedelta = timedelta(seconds=5)
    opposite_trade_window: timedelta = timedelta(seconds=2)
```

All windows must be positive (non-zero, non-negative). Validation occurs in `__post_init__`.

## Edge Cases

1. **Partial Matches**: Only complete 3-step patterns are detected
2. **Overlapping Windows**: Each order participates in at most one detected sequence
3. **Boundary Conditions**: Time windows are inclusive (events at exact boundaries are included)
4. **Invalid Events**: Invalid rows are skipped during I/O, not during detection

## Testing

### Test Coverage

- Unit tests: `tests/test_layering_detector.py`
- Algorithm tests: `tests/test_algorithms_layering.py`
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **Basic Pattern**: Standard 3-step layering pattern
2. **Boundary Conditions**: Events at exact time window boundaries
3. **Multiple Groups**: Different `(account_id, product_id)` combinations
4. **No Matches**: Events that don't form layering patterns
5. **Configuration**: Custom timing windows

## Dependencies

- **Domain Models**: `TransactionEvent`, `SuspiciousSequence`, `DetectionConfig`
- **I/O**: `read_transactions()` for input
- **Registry**: `AlgorithmRegistry` for plugin architecture

## Extension Points

### Custom Timing Windows

```python
from datetime import timedelta
from layering_detection.models import DetectionConfig
from layering_detection.detectors.layering_detector import detect_suspicious_sequences

config = DetectionConfig(
    orders_window=timedelta(seconds=15),
    cancel_window=timedelta(seconds=7),
    opposite_trade_window=timedelta(seconds=3)
)

sequences = detect_suspicious_sequences(events, config=config)
```

### Algorithm Registry

The algorithm is automatically registered via `@AlgorithmRegistry.register` decorator and can be retrieved by name:

```python
algorithm = AlgorithmRegistry.get("layering")
```

## Security Considerations

- **Input Validation**: All events validated during I/O parsing
- **Type Safety**: Strict type hints prevent invalid data flow
- **Immutability**: Frozen dataclasses prevent accidental mutation

## Future Enhancements

1. **Multi-level Layering**: Detect patterns with multiple layers
2. **Cross-product Patterns**: Detect layering across related products
3. **Adaptive Thresholds**: Dynamic timing windows based on market conditions
4. **Parallel Processing**: Parallelize detection across account/product groups
