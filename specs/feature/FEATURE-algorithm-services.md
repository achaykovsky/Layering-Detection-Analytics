# Feature: Algorithm Services (Layering & Wash Trading)

## Overview

Independent detection microservices that implement specific detection algorithms. Each service is stateless, independently scalable, and implements idempotent detection operations. Currently includes Layering Service and Wash Trading Service, with architecture supporting easy addition of new algorithm services.

## Requirements

### Layering Service

- [ ] Implement FastAPI service on port 8001
- [ ] Expose `POST /detect` endpoint
- [ ] Accept `AlgorithmRequest` with `request_id`, `event_fingerprint`, `events`
- [ ] Implement idempotent detection (cache results by `(request_id, event_fingerprint)`)
- [ ] Use `LayeringDetectionAlgorithm` from `layering_detection.detectors.layering_detector`
- [ ] Return `AlgorithmResponse` with results or error
- [ ] Provide `GET /health` endpoint

### Wash Trading Service

- [ ] Implement FastAPI service on port 8002
- [ ] Expose `POST /detect` endpoint
- [ ] Accept `AlgorithmRequest` with `request_id`, `event_fingerprint`, `events`
- [ ] Implement idempotent detection (cache results by `(request_id, event_fingerprint)`)
- [ ] Use `WashTradingDetectionAlgorithm` from `layering_detection.detectors.wash_trading_detector`
- [ ] Return `AlgorithmResponse` with results or error
- [ ] Provide `GET /health` endpoint

### Common Requirements (Both Services)

- [ ] Stateless design (except result cache for idempotency)
- [ ] Independent scaling capability
- [ ] Fault isolation (service failure doesn't affect others)
- [ ] Idempotent operations (same input = same output)
- [ ] Structured logging with `request_id`
- [ ] Error handling and validation

## Acceptance Criteria

- [ ] Layering service responds on port 8001
- [ ] Wash Trading service responds on port 8002
- [ ] `POST /detect` accepts valid `AlgorithmRequest`
- [ ] Returns cached result if `(request_id, event_fingerprint)` seen before
- [ ] Processes events and returns `List[SuspiciousSequence]`
- [ ] Returns HTTP 200 with `status: "success"` on success
- [ ] Returns HTTP 200 with `status: "failure"` and error message on failure
- [ ] Health check returns 200 OK when service is ready
- [ ] Service can be scaled horizontally (multiple instances)
- [ ] Cache prevents duplicate processing on retries

## Technical Details

### Request/Response Models

**AlgorithmRequest**:
```python
{
  "request_id": str,  # UUID
  "event_fingerprint": str,  # SHA256 hash
  "events": List[TransactionEvent]  # Serialized as JSON
}
```

**AlgorithmResponse**:
```python
{
  "request_id": str,
  "service_name": str,  # "layering" or "wash_trading"
  "status": "success" | "failure" | "timeout",
  "results": List[SuspiciousSequence] | null,
  "error": str | null
}
```

### Idempotency Implementation

```python
cache: dict[tuple[str, str], List[SuspiciousSequence]] = {}

async def detect(request: AlgorithmRequest):
    cache_key = (request.request_id, request.event_fingerprint)
    
    if cache_key in cache:
        return cache[cache_key]  # Deduplicate
    
    result = algorithm.detect(request.events)
    cache[cache_key] = result
    return result
```

### Service Structure

```
services/
├── layering-service/
│   ├── Dockerfile
│   ├── main.py (FastAPI app)
│   ├── requirements.txt
│   └── README.md
└── wash-trading-service/
    ├── Dockerfile
    ├── main.py (FastAPI app)
    ├── requirements.txt
    └── README.md
```

### Dependencies

- FastAPI for REST API
- `layering_detection` package (installed via pip)
- Pydantic for request/response validation
- Domain models: `TransactionEvent`, `SuspiciousSequence`

### Error Handling

- Validate input data (Pydantic models)
- Handle algorithm exceptions gracefully
- Return structured error responses
- Log errors with `request_id` for tracing

## Implementation Notes

- Cache is in-memory (no eviction needed for batch processing)
- Cache cleared after pipeline completion
- Services are CPU-intensive (detection algorithms)
- Consider adding metrics endpoint for monitoring
- Future: Add distributed cache (Redis) for multi-instance scenarios

## Extension Points

### Adding New Algorithm Service

1. Create new service directory: `services/new-algorithm-service/`
2. Implement FastAPI app with `/detect` endpoint
3. Add service to `docker-compose.yml`
4. Update orchestrator config: Add to `EXPECTED_SERVICES`
5. No changes needed to other services

## Related Specs

- [API Contracts](./FEATURE-api-contracts.md)
- [Deduplication Strategy](./FEATURE-deduplication.md)
- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)
- [Service Health Checks](./FEATURE-service-health-checks.md)

## Questions/Clarifications

- Should cache be persistent across service restarts?
- What is the maximum cache size before eviction needed?
- Should we add metrics endpoint (Prometheus format)?

