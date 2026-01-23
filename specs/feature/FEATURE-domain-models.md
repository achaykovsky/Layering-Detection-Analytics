# Feature: Domain Models

## Overview

Immutable domain models representing core business entities: transaction events, suspicious sequences, and detection configuration. Framework-agnostic dataclasses providing type safety and clear data contracts.

## Models

### 1. TransactionEvent

Represents a single transaction event from the input CSV.

### 2. SuspiciousSequence

Represents a detected suspicious trading pattern.

### 3. DetectionConfig

Configuration for detection algorithm timing windows.

## TransactionEvent

### Definition

```python
@dataclass(frozen=True)
class TransactionEvent:
    timestamp: datetime
    account_id: str
    product_id: str
    side: Side  # Literal["BUY", "SELL"]
    price: Decimal
    quantity: int
    event_type: EventType  # Literal["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]
```

### Properties

- **Immutable**: Frozen dataclass (cannot be modified after creation)
- **Type Safe**: Strict type hints for all fields
- **Framework Agnostic**: Plain dataclass (no external dependencies)

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | ISO datetime of the event |
| `account_id` | `str` | Account identifier |
| `product_id` | `str` | Product/instrument identifier |
| `side` | `Side` | `"BUY"` or `"SELL"` |
| `price` | `Decimal` | Trade price (positive) |
| `quantity` | `int` | Trade quantity (positive) |
| `event_type` | `EventType` | `"ORDER_PLACED"`, `"ORDER_CANCELLED"`, or `"TRADE_EXECUTED"` |

### Type Aliases

```python
Side = Literal["BUY", "SELL"]
EventType = Literal["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]
```

### Example

```python
from datetime import datetime
from decimal import Decimal
from layering_detection.models import TransactionEvent

event = TransactionEvent(
    timestamp=datetime(2025, 1, 15, 10, 30, 0),
    account_id="ACC001",
    product_id="IBM",
    side="BUY",
    price=Decimal("100.50"),
    quantity=1000,
    event_type="ORDER_PLACED"
)
```

## SuspiciousSequence

### Definition

```python
@dataclass(frozen=True)
class SuspiciousSequence:
    account_id: str
    product_id: str
    start_timestamp: datetime
    end_timestamp: datetime
    total_buy_qty: int
    total_sell_qty: int
    detection_type: DetectionType = "LAYERING"  # Literal["LAYERING", "WASH_TRADING"]
    side: Side | None = None
    num_cancelled_orders: int | None = None
    order_timestamps: list[datetime] | None = None
    alternation_percentage: float | None = None
    price_change_percentage: float | None = None
```

### Properties

- **Polymorphic**: Fields vary by `detection_type`
- **Immutable**: Frozen dataclass
- **Type Safe**: Optional fields for algorithm-specific data

### Core Fields (All Detection Types)

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | `str` | Suspicious account identifier |
| `product_id` | `str` | Product where activity detected |
| `start_timestamp` | `datetime` | Start of detection window |
| `end_timestamp` | `datetime` | End of detection window (detection time) |
| `total_buy_qty` | `int` | Total BUY quantity in window |
| `total_sell_qty` | `int` | Total SELL quantity in window |
| `detection_type` | `DetectionType` | `"LAYERING"` or `"WASH_TRADING"` |

### Layering-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `side` | `Side` | Side of orders (BUY or SELL) |
| `num_cancelled_orders` | `int` | Count of cancelled orders (≥3) |
| `order_timestamps` | `list[datetime]` | Timestamps of placed orders |

### Wash Trading-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `alternation_percentage` | `float` | Percentage of side switches (≥60%) |
| `price_change_percentage` | `float \| None` | Price change (≥1% if present) |

### Field Semantics by Detection Type

**LAYERING**:
- `side`: Required (BUY or SELL)
- `num_cancelled_orders`: Required (≥3)
- `order_timestamps`: Required (list of order timestamps)
- `alternation_percentage`: `None` (not applicable)
- `price_change_percentage`: `None` (not applicable)

**WASH_TRADING**:
- `side`: `None` (not applicable)
- `num_cancelled_orders`: `None` (not applicable)
- `order_timestamps`: `None` (not applicable)
- `alternation_percentage`: Required (≥60%)
- `price_change_percentage`: Optional (≥1% if present, `None` otherwise)

### Example

```python
from datetime import datetime
from layering_detection.models import SuspiciousSequence

# Layering detection
layering_seq = SuspiciousSequence(
    account_id="ACC001",
    product_id="IBM",
    start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
    end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
    total_buy_qty=3000,
    total_sell_qty=2000,
    detection_type="LAYERING",
    side="BUY",
    num_cancelled_orders=3,
    order_timestamps=[datetime(2025, 1, 15, 10, 30, i) for i in [0, 5, 8]]
)

# Wash trading detection
wash_seq = SuspiciousSequence(
    account_id="ACC002",
    product_id="GOOG",
    start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
    total_buy_qty=12000,
    total_sell_qty=12000,
    detection_type="WASH_TRADING",
    alternation_percentage=80.0,
    price_change_percentage=1.25
)
```

## DetectionConfig

### Definition

```python
@dataclass(frozen=True)
class DetectionConfig:
    orders_window: timedelta = timedelta(seconds=10)
    cancel_window: timedelta = timedelta(seconds=5)
    opposite_trade_window: timedelta = timedelta(seconds=2)
```

### Properties

- **Immutable**: Frozen dataclass
- **Validated**: All windows must be positive (non-zero, non-negative)
- **Default Values**: Match original hard-coded timing windows

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `orders_window` | `timedelta` | 10 seconds | Window for finding same-side ORDER_PLACED events |
| `cancel_window` | `timedelta` | 5 seconds | Window for finding ORDER_CANCELLED events after last order |
| `opposite_trade_window` | `timedelta` | 2 seconds | Window for finding opposite-side TRADE_EXECUTED after last cancellation |

### Validation

All timing windows must be positive (greater than zero). Validation occurs in `__post_init__()`:

```python
def __post_init__(self) -> None:
    self._validate_window(self.orders_window, "orders_window")
    self._validate_window(self.cancel_window, "cancel_window")
    self._validate_window(self.opposite_trade_window, "opposite_trade_window")
```

**Raises**: `ValueError` if any window is negative or zero.

### Example

```python
from datetime import timedelta
from layering_detection.models import DetectionConfig

# Default config
config = DetectionConfig()

# Custom config
custom_config = DetectionConfig(
    orders_window=timedelta(seconds=15),
    cancel_window=timedelta(seconds=7),
    opposite_trade_window=timedelta(seconds=3)
)

# Invalid config (raises ValueError)
invalid_config = DetectionConfig(orders_window=timedelta(seconds=0))
```

## Design Decisions

### 1. Immutability

**Decision**: All models are frozen dataclasses.

**Rationale**:
- Prevents accidental mutation
- Enables safe sharing across threads
- Clear data contracts

**Tradeoff**: Cannot modify in place (must create new instances).

### 2. Framework Agnostic

**Decision**: Plain dataclasses, no external dependencies.

**Rationale**:
- Minimal dependencies
- Easy to test
- Portable across frameworks

**Tradeoff**: No automatic validation (must validate manually).

### 3. Polymorphic SuspiciousSequence

**Decision**: Single model with optional fields for different detection types.

**Rationale**:
- Unified output schema
- Simpler than separate models
- Easy to extend with new detection types

**Tradeoff**: Some fields are `None` for certain detection types (requires null checks).

### 4. Decimal for Prices

**Decision**: Use `Decimal` instead of `float` for prices.

**Rationale**:
- Avoids floating-point precision issues
- Accurate financial calculations
- Standard for financial data

**Tradeoff**: Slightly more complex than `float`.

### 5. Type Literals

**Decision**: Use `Literal` types for enums (`Side`, `EventType`, `DetectionType`).

**Rationale**:
- Type safety at compile time
- No runtime enum overhead
- Clear allowed values

**Tradeoff**: Less flexible than runtime enums.

## Usage Patterns

### Creating Events

```python
from datetime import datetime
from decimal import Decimal
from layering_detection.models import TransactionEvent

event = TransactionEvent(
    timestamp=datetime.fromisoformat("2025-01-15T10:30:00+00:00"),
    account_id="ACC001",
    product_id="IBM",
    side="BUY",
    price=Decimal("100.50"),
    quantity=1000,
    event_type="ORDER_PLACED"
)
```

### Pattern Matching (Python 3.10+)

```python
match sequence.detection_type:
    case "LAYERING":
        print(f"Layering: {sequence.side}, {sequence.num_cancelled_orders} cancelled")
    case "WASH_TRADING":
        print(f"Wash trading: {sequence.alternation_percentage}% alternation")
```

### Type Checking

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from layering_detection.models import TransactionEvent

def process_event(event: TransactionEvent) -> None:
    # Type checker validates event structure
    pass
```

## Testing

### Test Coverage

- Model tests: `tests/test_models.py`
- Integration tests: Various test files

### Test Scenarios

1. **Immutability**: Verify frozen dataclass behavior
2. **Validation**: Test `DetectionConfig` validation
3. **Type Safety**: Verify type hints work correctly
4. **Polymorphism**: Test `SuspiciousSequence` with different detection types

## Future Enhancements

1. **Pydantic Models**: Optional Pydantic models for automatic validation
2. **JSON Serialization**: Built-in JSON serialization/deserialization
3. **Versioning**: Model versioning for schema evolution
4. **Validation Helpers**: Additional validation methods
5. **Builder Pattern**: Builder for complex `SuspiciousSequence` construction
