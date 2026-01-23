# Feature: Pipeline Orchestration

## Overview

End-to-end orchestration of the detection pipeline, coordinating input reading, algorithm execution, result merging, and output writing. Provides a single entry point for running the complete analytics workflow.

## Pipeline Flow

```
Input CSV
    ↓
Read Transactions
    ↓
Get Algorithms from Registry
    ↓
Run Layering Algorithm
    ↓
Run Wash Trading Algorithm
    ↓
Merge Results
    ↓
Write Suspicious Accounts CSV
    ↓
Write Detection Logs CSV
    ↓
Complete
```

## Implementation

### Location

- **Module**: `src/layering_detection/runner.py`
- **Function**: `run_pipeline()`

### Function Signature

```python
def run_pipeline(
    input_path: Path,
    output_dir: Path,
    logs_dir: Path,
) -> None:
    """
    Run the full detection pipeline with both layering and wash trading algorithms.
    
    Args:
        input_path: Path to transactions.csv input file
        output_dir: Directory for suspicious_accounts.csv
        logs_dir: Directory for detections.csv
        
    Raises:
        FileNotFoundError: If input_path doesn't exist
        KeyError: If required algorithms not registered
        ValueError: If input data is invalid
        IOError: If output directories cannot be created
    """
```

## Pipeline Steps

### 1. Read Transactions

```python
events = read_transactions(input_path)
```

- Reads CSV file into `TransactionEvent` objects
- Validates and parses all fields
- Skips invalid rows with warnings
- Returns list of events (unsorted, ungrouped)

### 2. Get Algorithms

```python
layering_algorithm = AlgorithmRegistry.get("layering")
wash_trading_algorithm = AlgorithmRegistry.get("wash_trading")
```

- Retrieves algorithms from registry by name
- Creates fresh algorithm instances (stateless)
- Raises `KeyError` if algorithms not registered

### 3. Run Detection Algorithms

```python
layering_sequences = layering_algorithm.detect(events)
wash_trading_sequences = wash_trading_algorithm.detect(events)
```

- Each algorithm processes the same event stream
- Algorithms handle their own filtering/grouping
- Returns lists of `SuspiciousSequence` objects

### 4. Merge Results

```python
all_sequences: List[SuspiciousSequence] = []
all_sequences.extend(layering_sequences)
all_sequences.extend(wash_trading_sequences)
```

- Combines results from all algorithms
- Maintains unified list for output
- Preserves algorithm-specific fields via `detection_type`

### 5. Ensure Directories Exist

```python
output_dir.mkdir(parents=True, exist_ok=True)
logs_dir.mkdir(parents=True, exist_ok=True)
```

- Creates output directories if they don't exist
- Creates parent directories as needed
- No error if directories already exist

### 6. Write Output Files

```python
suspicious_path = output_dir / "suspicious_accounts.csv"
write_suspicious_accounts(suspicious_path, all_sequences)

logs_path = logs_dir / "detections.csv"
write_detection_logs(logs_path, all_sequences)
```

- Writes unified suspicious accounts CSV
- Writes per-sequence detection logs
- Both files contain results from all algorithms

## Usage

### Programmatic Usage

```python
from pathlib import Path
from layering_detection.orchestrator import run_pipeline

run_pipeline(
    input_path=Path("input/transactions.csv"),
    output_dir=Path("output"),
    logs_dir=Path("logs")
)
```

### Command-Line Usage

Via `main.py`:

```bash
python main.py
# Uses defaults: input/transactions.csv, output/, logs/

python main.py input/transactions.csv output logs
# Custom paths
```

### Docker Usage

```bash
docker run --rm \
  -v ${PWD}/input:/app/input \
  -v ${PWD}/output:/app/output \
  -v ${PWD}/logs:/app/logs \
  layering-detection:latest
```

## Design Decisions

### 1. Single Function Entry Point

**Decision**: Single `run_pipeline()` function orchestrates entire workflow.

**Rationale**:
- Simple API for users
- Encapsulates complexity
- Easy to test end-to-end

**Tradeoff**: Less flexibility for custom workflows.

### 2. Sequential Algorithm Execution

**Decision**: Run algorithms sequentially, not in parallel.

**Rationale**:
- Simpler implementation
- Easier error handling
- Algorithms are CPU-bound (no I/O blocking)

**Tradeoff**: Slower than parallel execution (future optimization).

### 3. Unified Output Files

**Decision**: Merge results from all algorithms into single output files.

**Rationale**:
- Simpler for users (one file to analyze)
- Unified schema with `detection_type` discriminator
- Maintains backward compatibility

**Tradeoff**: Larger output files, but manageable.

### 4. Directory Auto-Creation

**Decision**: Automatically create output directories if missing.

**Rationale**:
- User-friendly (no manual directory creation)
- Prevents common errors
- Safe operation (no overwrite)

**Tradeoff**: May create unexpected directories if path is wrong.

## Error Handling

### Input Errors

```python
# Missing input file
run_pipeline(Path("nonexistent.csv"), Path("output"), Path("logs"))
# Raises: FileNotFoundError
```

### Algorithm Errors

```python
# Unregistered algorithm
# (If registry is cleared or algorithm not imported)
# Raises: KeyError
```

### Output Errors

```python
# Permission denied
run_pipeline(Path("input.csv"), Path("/readonly"), Path("logs"))
# Raises: IOError
```

### Data Errors

```python
# Invalid CSV format
# (Handled gracefully: invalid rows skipped with warnings)
# Continues processing valid rows
```

## Performance Characteristics

### Complexity

- **Time**: O(n log n) where n is number of events (dominated by detection algorithms)
- **Space**: O(n) for events and results
- **I/O**: Single read, two writes

### Bottlenecks

1. **CSV Reading**: O(n) - linear scan
2. **Detection Algorithms**: O(n log n) - indexed queries
3. **CSV Writing**: O(m) where m is number of sequences

### Optimization Opportunities

1. **Parallel Algorithm Execution**: Run algorithms in parallel (future)
2. **Streaming I/O**: Process events in chunks (future)
3. **Incremental Processing**: Process only new events (future)

## Testing

### Test Coverage

- Integration tests: `tests/test_runner.py`
- End-to-end tests: `tests/test_runner.py`

### Test Scenarios

1. **Happy Path**: Complete pipeline execution
2. **Missing Input**: FileNotFoundError handling
3. **Invalid Data**: Graceful handling of invalid rows
4. **Output Creation**: Directory auto-creation
5. **Multiple Algorithms**: Results from both algorithms merged
6. **Empty Results**: Handles no detections gracefully

## Extension Points

### Adding New Algorithms

1. Implement algorithm following `DetectionAlgorithm` interface
2. Register with `@AlgorithmRegistry.register`
3. Import algorithm module (triggers registration)
4. Update `run_pipeline()` to retrieve and run new algorithm
5. Results automatically merged with existing algorithms

**Example**:
```python
# In runner.py
new_algorithm = AlgorithmRegistry.get("new_algorithm")
new_sequences = new_algorithm.detect(events)
all_sequences.extend(new_sequences)
```

### Custom Workflows

For custom workflows, call pipeline components directly:

```python
from layering_detection.utils.transaction_io import read_transactions, write_suspicious_accounts
from layering_detection.algorithms import AlgorithmRegistry

events = read_transactions(Path("input.csv"))
algorithm = AlgorithmRegistry.get("layering")
sequences = algorithm.detect(events)
write_suspicious_accounts(Path("output.csv"), sequences)
```

## Integration

### Main Entry Point

`main.py` provides command-line interface:

```python
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    input_path = Path(sys.argv[1] if len(sys.argv) > 1 else "input/transactions.csv")
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "output")
    logs_dir = Path(sys.argv[3] if len(sys.argv) > 3 else "logs")
    
    run_pipeline(input_path, output_dir, logs_dir)
```

### Docker Integration

Dockerfile sets default command:

```dockerfile
CMD ["python", "-m", "layering_detection.runner"]
```

Or via `main.py`:

```dockerfile
CMD ["python", "main.py"]
```

## Future Enhancements

1. **Parallel Execution**: Run algorithms in parallel threads/processes
2. **Progress Reporting**: Progress bars or logging for long-running pipelines
3. **Checkpointing**: Save intermediate results for resume capability
4. **Configuration File**: YAML/JSON config for algorithm selection and parameters
5. **Streaming Mode**: Process events as they arrive (real-time detection)
6. **Multi-file Input**: Process multiple CSV files in batch
7. **Result Filtering**: Filter results by detection type, account, etc.
8. **Metrics Collection**: Collect and report detection metrics
