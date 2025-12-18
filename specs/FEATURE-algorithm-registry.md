# Feature: Algorithm Registry Pattern

## Overview

Plugin-based architecture enabling extensible detection algorithm addition without modifying core pipeline code. New algorithms can be added by implementing the `DetectionAlgorithm` interface and registering with the decorator.

## Architecture Pattern

### Registry Pattern

The registry pattern provides:
- **Centralized Registration**: Single point for algorithm discovery
- **Loose Coupling**: Algorithms don't depend on pipeline implementation
- **Extensibility**: New algorithms added without modifying existing code
- **Type Safety**: Interface enforcement via abstract base class

### Component Diagram

```
┌─────────────────────────────────────┐
│   AlgorithmRegistry (Singleton)     │
│   - register() decorator            │
│   - get(name) → Algorithm instance  │
│   - get_all() → List[Algorithm]     │
│   - list_all() → List[str]          │
└─────────────────────────────────────┘
              ▲
              │ implements
              │
┌─────────────────────────────────────┐
│   DetectionAlgorithm (ABC)          │
│   - name: str (property)            │
│   - description: str (property)     │
│   - detect() → List[SuspiciousSeq]  │
│   - filter_events() (optional)      │
└─────────────────────────────────────┘
              ▲
              │
    ┌─────────┴─────────┐
    │                   │
┌───────────┐    ┌──────────────┐
│ Layering  │    │ Wash Trading │
│ Algorithm │    │  Algorithm   │
└───────────┘    └──────────────┘
```

## Implementation

### Location

- **Base Class**: `src/layering_detection/algorithms/base.py`
- **Registry**: `src/layering_detection/algorithms/registry.py`
- **Algorithm Implementations**: `src/layering_detection/algorithms/layering.py`, `wash_trading.py`

### DetectionAlgorithm Interface

```python
class DetectionAlgorithm(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique algorithm identifier"""
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description"""
    
    @abstractmethod
    def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        """Core detection logic"""
    
    def filter_events(self, events: Iterable[TransactionEvent]) -> List[TransactionEvent]:
        """Optional preprocessing (default: no filtering)"""
```

### AlgorithmRegistry API

```python
class AlgorithmRegistry:
    @classmethod
    def register(cls, algorithm_class: Type[T]) -> Type[T]:
        """Decorator to register algorithm class"""
    
    @classmethod
    def get(cls, name: str) -> DetectionAlgorithm:
        """Retrieve algorithm by name (creates new instance)"""
    
    @classmethod
    def get_all(cls, enabled: List[str] | None = None) -> List[DetectionAlgorithm]:
        """Get all algorithms, optionally filtered"""
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered algorithm names"""
    
    @classmethod
    def clear(cls) -> None:
        """Clear registry (testing only)"""
```

## Usage

### Registering an Algorithm

```python
from layering_detection.algorithms import AlgorithmRegistry, DetectionAlgorithm
from layering_detection.models import TransactionEvent, SuspiciousSequence

@AlgorithmRegistry.register
class MyCustomAlgorithm(DetectionAlgorithm):
    @property
    def name(self) -> str:
        return "my_custom"
    
    @property
    def description(self) -> str:
        return "Detects custom manipulation patterns"
    
    def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        # Implementation
        return []
```

### Retrieving Algorithms

```python
# Get single algorithm
algorithm = AlgorithmRegistry.get("layering")
sequences = algorithm.detect(events)

# Get all algorithms
all_algorithms = AlgorithmRegistry.get_all()
for algo in all_algorithms:
    sequences = algo.detect(events)

# Get filtered algorithms
enabled = AlgorithmRegistry.get_all(enabled=["layering", "wash_trading"])

# List names
names = AlgorithmRegistry.list_all()  # ["layering", "wash_trading"]
```

### Pipeline Integration

```python
# In runner.py
layering_algorithm = AlgorithmRegistry.get("layering")
wash_trading_algorithm = AlgorithmRegistry.get("wash_trading")

layering_sequences = layering_algorithm.detect(events)
wash_trading_sequences = wash_trading_algorithm.detect(events)
```

## Design Decisions

### 1. Class-based Registration

**Decision**: Register algorithm classes, not instances.

**Rationale**:
- Algorithms are stateless (pure functions)
- Registry creates fresh instances on demand
- Enables lazy instantiation

**Tradeoff**: Slight overhead of instantiation, but enables stateless design.

### 2. Decorator-based Registration

**Decision**: Use `@AlgorithmRegistry.register` decorator.

**Rationale**:
- Declarative and explicit
- Automatic registration at import time
- No manual registration calls needed

**Tradeoff**: Requires importing algorithm modules to trigger registration.

### 3. Name-based Retrieval

**Decision**: Retrieve algorithms by string name.

**Rationale**:
- Enables configuration-driven algorithm selection
- Decouples pipeline from specific algorithm classes
- Supports dynamic algorithm loading

**Tradeoff**: String names are not type-checked at compile time.

### 4. Validation on Registration

**Decision**: Validate algorithm interface and uniqueness on registration.

**Rationale**:
- Fail fast on invalid algorithms
- Prevent duplicate registrations
- Clear error messages

**Implementation**:
- Checks `issubclass(DetectionAlgorithm)`
- Validates `name` property exists and is non-empty
- Ensures name uniqueness

## Error Handling

### Registration Errors

```python
# Duplicate name
@AlgorithmRegistry.register
class Algorithm1(DetectionAlgorithm):
    @property
    def name(self) -> str:
        return "duplicate"

@AlgorithmRegistry.register
class Algorithm2(DetectionAlgorithm):
    @property
    def name(self) -> str:
        return "duplicate"  # Raises ValueError
```

### Retrieval Errors

```python
# Unregistered algorithm
algorithm = AlgorithmRegistry.get("nonexistent")  # Raises KeyError
```

## Testing

### Test Coverage

- Unit tests: `tests/test_algorithms_registry.py`
- Base class tests: `tests/test_algorithms_base.py`
- Integration tests: `tests/test_runner.py`

### Test Scenarios

1. **Registration**: Valid algorithm registration
2. **Duplicate Names**: Error on duplicate registration
3. **Invalid Interface**: Error on non-DetectionAlgorithm class
4. **Retrieval**: Get by name, get all, filtered get
5. **Isolation**: Registry state isolation in tests (using `clear()`)

## Extension Points

### Adding New Algorithms

1. Create algorithm class inheriting from `DetectionAlgorithm`
2. Implement required methods (`name`, `description`, `detect`)
3. Optionally override `filter_events()` for preprocessing
4. Register with `@AlgorithmRegistry.register` decorator
5. Import the module to trigger registration

**No changes needed to**:
- Pipeline code (`runner.py`)
- I/O layer
- Other algorithms
- Registry implementation

### Configuration-driven Selection

```python
# Future: Enable algorithms via config
enabled_algorithms = config.get("enabled_algorithms", ["layering", "wash_trading"])
algorithms = AlgorithmRegistry.get_all(enabled=enabled_algorithms)
```

## Performance Considerations

### Registration

- **Cost**: O(1) per algorithm (dictionary insertion)
- **Timing**: Occurs at import time (one-time cost)

### Retrieval

- **Get by name**: O(1) dictionary lookup + instantiation
- **Get all**: O(n) where n is number of registered algorithms
- **Instantiation**: O(1) per algorithm (stateless)

### Memory

- **Storage**: O(n) for algorithm class registry
- **Instances**: Created on-demand, not cached (stateless design)

## Security Considerations

- **Input Validation**: Algorithm names validated on registration
- **Type Safety**: Interface enforcement prevents invalid implementations
- **Isolation**: Algorithms are stateless and isolated from each other

## Future Enhancements

1. **Lazy Loading**: Load algorithm modules on-demand
2. **Plugin Discovery**: Auto-discover algorithms from package
3. **Algorithm Metadata**: Version, author, configuration schema
4. **Dependency Management**: Algorithm dependencies and ordering
5. **Hot Reloading**: Reload algorithms without restart (development)







