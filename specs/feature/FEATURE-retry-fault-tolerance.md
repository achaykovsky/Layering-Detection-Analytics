# Feature: Retry & Fault Tolerance

## Overview

Implements retry logic with exponential backoff in the Orchestrator Service to handle transient failures in algorithm service calls. Ensures fault isolation so one service failure doesn't stop the entire pipeline.

## Requirements

- [ ] Implement retry logic in orchestrator for algorithm service calls
- [ ] Exponential backoff: 2^attempt seconds between retries
- [ ] Maximum retries: 3 (configurable via MAX_RETRIES)
- [ ] Timeout per service call: 30 seconds (configurable)
- [ ] Retry on: `TimeoutError`, `ConnectionError`, HTTP 5xx errors
- [ ] Track retry count per service
- [ ] Mark service as `final_status=True` after retries exhausted
- [ ] Continue pipeline even if some services fail (fault isolation)
- [ ] Log retry attempts with `request_id`

## Acceptance Criteria

- [ ] Retries up to MAX_RETRIES times (default 3)
- [ ] Backoff delay: 2^0=1s, 2^1=2s, 2^2=4s between retries
- [ ] Each service call times out after ALGORITHM_TIMEOUT_SECONDS
- [ ] Retries on transient errors (timeout, connection, 5xx)
- [ ] Does not retry on 4xx errors (client errors)
- [ ] Tracks `retry_count` in service status
- [ ] Sets `final_status=True` after all retries exhausted
- [ ] Pipeline continues even if one service fails
- [ ] Logs include retry attempts and backoff delays
- [ ] Error messages include retry count and final status

## Technical Details

### Retry Implementation

```python
async def _process_with_retries(
    service_name: str,
    request_id: str,
    event_fingerprint: str,
    events: List[TransactionEvent],
    service_status: dict
):
    """Process algorithm with retry until success or exhausted."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await call_algorithm_service(
                service_name=service_name,
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
                timeout=ALGORITHM_TIMEOUT_SECONDS
            )
            service_status[service_name] = {
                "status": "success",
                "final_status": True,
                "result": result,
                "retry_count": attempt
            }
            return
            
        except (TimeoutError, ConnectionError, HTTPException) as e:
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE_SECONDS ** attempt
                await asyncio.sleep(backoff)
                continue
            else:
                service_status[service_name] = {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": str(e),
                    "retry_count": attempt + 1
                }
                return
```

### Configuration

```python
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2
ALGORITHM_TIMEOUT_SECONDS = 30
```

### Retry Conditions

**Retry on:**
- `TimeoutError`: Service call exceeded timeout
- `ConnectionError`: Network connection failed
- HTTP 5xx errors: Server errors (500, 502, 503, 504)

**Do not retry on:**
- HTTP 4xx errors: Client errors (400, 401, 404)
- Validation errors: Invalid request data
- Algorithm errors: Business logic failures

### Fault Isolation

- Each service call is independent
- Failure of one service doesn't stop others
- Orchestrator waits for all services to reach `final_status=True`
- Aggregator validates completion but can handle partial failures

## Implementation Notes

- Use asyncio for non-blocking retries
- Consider circuit breaker pattern (future enhancement)
- Add metrics for retry rates and failure patterns
- Consider jitter in backoff (future enhancement)

## Tradeoff Analysis

| Aspect | Fixed Interval | Exponential Backoff |
|--------|----------------|---------------------|
| Recovery Time | Predictable | Variable |
| Server Load | Constant | Decreasing |
| Implementation | Simple | Slightly complex |

**Decision**: Exponential backoff chosen to reduce server load on retries.

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Completion Validation](./FEATURE-completion-validation.md)
- [Deduplication Strategy](./FEATURE-deduplication.md)

## Questions/Clarifications

- Should we add jitter to backoff delays?
- Should we implement circuit breaker pattern?
- What is the maximum total retry time acceptable?

