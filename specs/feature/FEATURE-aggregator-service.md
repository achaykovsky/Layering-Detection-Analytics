# Feature: Aggregator Service

## Overview

The Aggregator Service validates completion of all algorithm services, merges results from successful services, and writes output CSV files. It ensures data integrity by validating that all expected services completed before writing results.

## Requirements

- [ ] Validate all expected services have `final_status=True`
- [ ] Verify all expected services responded (no missing services)
- [ ] Merge successful results from all algorithm services
- [ ] Deduplicate suspicious sequences across services
- [ ] Write `suspicious_accounts.csv` with unique account IDs
- [ ] Write `detections.csv` with all suspicious sequences
- [ ] Log warnings for failed services (but continue if validation passes)
- [ ] Provide `POST /aggregate` endpoint
- [ ] Provide `GET /health` endpoint
- [ ] Fail fast with clear error if validation fails

## Acceptance Criteria

- [ ] Service starts on port 8003 (configurable via PORT env var)
- [ ] `POST /aggregate` accepts `AggregateRequest`
- [ ] Validates all expected services are present in results
- [ ] Validates all services have `final_status=True`
- [ ] Raises `ValueError` with detailed message if validation fails
- [ ] Merges `SuspiciousSequence` results from successful services
- [ ] Deduplicates sequences (same account_id + time window)
- [ ] Writes `suspicious_accounts.csv` to OUTPUT_DIR
- [ ] Writes `detections.csv` to OUTPUT_DIR
- [ ] CSV format matches existing monolithic output format
- [ ] Logs warnings for failed services
- [ ] Returns `AggregateResponse` with status and counts
- [ ] Health check returns 200 OK when service is ready

## Technical Details

### Request/Response Models

**AggregateRequest**:
```python
{
  "request_id": str,
  "expected_services": List[str],  # ["layering", "wash_trading"]
  "results": [
    {
      "service_name": str,
      "status": "success" | "failure" | "exhausted",
      "final_status": bool,  # True = no more retries
      "results": List[SuspiciousSequence] | null,
      "error": str | null,
      "retry_count": int
    },
    ...
  ]
}
```

**AggregateResponse**:
```python
{
  "status": "completed" | "validation_failed",
  "merged_count": int,
  "failed_services": List[str],
  "error": str | null
}
```

### Validation Logic

```python
def validate_completeness(
    expected_services: List[str],
    results: List[AlgorithmResponse]
) -> None:
    """Validate all expected services completed."""
    received_services = {r["service_name"] for r in results}
    missing = set(expected_services) - received_services
    
    if missing:
        raise ValueError(
            f"Missing services: {missing}. "
            f"Expected: {expected_services}, Got: {received_services}"
        )
    
    incomplete = [
        r for r in results
        if not r.get("final_status", False)
    ]
    if incomplete:
        raise ValueError(
            f"Services not completed: {[s['service_name'] for s in incomplete]}. "
            f"All must have final_status=True"
        )
```

### Configuration

```python
VALIDATION_STRICT = True  # Fail if services missing
ALLOW_PARTIAL_RESULTS = False  # Only merge if all completed
OUTPUT_DIR = "/app/output"
LOGS_DIR = "/app/logs"
```

### Service Structure

```
services/
└── aggregator-service/
    ├── Dockerfile
    ├── main.py (FastAPI + validation + I/O)
    ├── config.py
    ├── requirements.txt
    └── README.md
```

### Dependencies

- FastAPI for REST API
- `layering_detection` package for domain models
- CSV writing utilities (inherited from existing code)
- Pydantic for request/response validation

### Output File Format

**suspicious_accounts.csv**:
- Columns: `account_id`
- Unique account IDs from all suspicious sequences

**detections.csv**:
- Columns: `account_id`, `start_time`, `end_time`, `detection_type`, `algorithm`
- All suspicious sequences from all services

## Implementation Notes

- I/O-bound operation (CSV writing)
- Consider file locking for concurrent writes (future)
- Preserve existing CSV format for backward compatibility
- Log all validation failures with details
- Consider streaming for large result sets (future)

## Error Handling

- Fail fast on validation errors (no partial output)
- Log warnings for failed services
- Return structured error responses
- Include `request_id` in all logs

## Related Specs

- [API Contracts](./FEATURE-api-contracts.md)
- [Completion Validation](./FEATURE-completion-validation.md)
- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)
- [Transaction I/O](./FEATURE-transaction-io.md)

## Questions/Clarifications

- Should aggregator support partial results mode?
- What is the maximum result size to handle?
- Should we add file locking for concurrent aggregations?

