# Feature: Orchestrator Service

## Overview

The Orchestrator Service is the central coordination service that manages the entire detection pipeline. It reads input CSV files, coordinates parallel algorithm service calls, handles retries and fault tolerance, and ensures completion before forwarding results to the aggregator.

## Requirements

- [ ] Read input CSV file from mounted volume
- [ ] Generate unique `request_id` (UUID) for each pipeline run
- [ ] Generate `event_fingerprint` (SHA256 hash) for deduplication
- [ ] Call algorithm services in parallel (Layering, Wash Trading)
- [ ] Implement retry logic with exponential backoff
- [ ] Track completion status for all expected services
- [ ] Collect results (success or failure) from all services
- [ ] Validate all services reached `final_status=True` before aggregation
- [ ] Send aggregated results to aggregator service
- [ ] Provide REST API endpoint: `POST /orchestrate`
- [ ] Provide health check endpoint: `GET /health`
- [ ] Support CLI entry point (backward compatibility)

## Acceptance Criteria

- [ ] Service starts on port 8000 (configurable via PORT env var)
- [ ] `POST /orchestrate` accepts input file path and triggers pipeline
- [ ] Generates unique `request_id` per request
- [ ] Calculates `event_fingerprint` from sorted event signatures
- [ ] Calls all algorithm services in parallel (asyncio.gather)
- [ ] Retries failed service calls up to MAX_RETRIES times
- [ ] Exponential backoff: 2^attempt seconds between retries
- [ ] Timeout per service call: ALGORITHM_TIMEOUT_SECONDS (default 30s)
- [ ] Tracks `final_status` for each service
- [ ] Only sends to aggregator when all services have `final_status=True`
- [ ] Returns error if services don't complete within timeout
- [ ] Health check returns 200 OK when service is ready
- [ ] Logs include `request_id` for tracing

## Technical Details

### Service Configuration

```python
EXPECTED_SERVICES = ["layering", "wash_trading"]
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2
ALGORITHM_TIMEOUT_SECONDS = 30
LAYERING_SERVICE_URL = "http://layering-service:8001"
WASH_TRADING_SERVICE_URL = "http://wash-trading-service:8002"
AGGREGATOR_SERVICE_URL = "http://aggregator-service:8003"
```

### Key Functions

- `orchestrate_pipeline(input_path: str) -> dict`: Main orchestration logic
- `_read_input_csv(path: str) -> List[TransactionEvent]`: Read and parse CSV
- `_generate_request_id() -> str`: Generate UUID
- `_hash_events(events: List[TransactionEvent]) -> str`: Generate fingerprint
- `_process_with_retries(...)`: Retry logic with exponential backoff
- `_call_algorithm_service(...)`: HTTP call to algorithm service
- `_validate_all_completed(...)`: Ensure all services finished
- `_send_to_aggregator(...)`: Forward results to aggregator

### Dependencies

- FastAPI for REST API
- `layering_detection` package for domain models (`TransactionEvent`)
- HTTP client (httpx or aiohttp) for service calls
- asyncio for parallel execution

### Error Handling

- Retry on: `TimeoutError`, `ConnectionError`, HTTP 5xx errors
- Fail fast if all retries exhausted
- Log errors with `request_id` for debugging
- Return structured error responses

## Implementation Notes

- Use async/await for parallel service calls
- Implement circuit breaker pattern (future enhancement)
- Consider request queuing for high-volume scenarios
- Memory-efficient CSV reading (streaming for large files)

## Related Specs

- [API Contracts](./FEATURE-api-contracts.md)
- [Retry & Fault Tolerance](./FEATURE-retry-fault-tolerance.md)
- [Deduplication Strategy](./FEATURE-deduplication.md)
- [Completion Validation](./FEATURE-completion-validation.md)
- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)

## Questions/Clarifications

- Should orchestrator support concurrent pipeline executions?
- What is the maximum input file size to handle?
- Should we implement request queuing or rate limiting?

