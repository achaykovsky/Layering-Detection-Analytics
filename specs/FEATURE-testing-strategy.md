# Feature: Testing Strategy

## Overview

Comprehensive testing strategy covering unit tests, integration tests, and end-to-end tests for the microservices architecture. Ensures reliability, fault tolerance, and correctness of distributed system.

## Requirements

- [ ] Unit tests for each service (independent testing)
- [ ] Integration tests for service-to-service communication
- [ ] End-to-end tests for full pipeline
- [ ] Test retry logic and fault tolerance
- [ ] Test deduplication and idempotency
- [ ] Test completion validation
- [ ] Test error scenarios (service down, timeout)
- [ ] Mock external dependencies in unit tests
- [ ] Use test containers or mocks for integration tests
- [ ] Test docker-compose setup end-to-end

## Acceptance Criteria

- [ ] Unit tests for orchestrator (mocked algorithm services)
- [ ] Unit tests for algorithm services (mocked algorithms)
- [ ] Unit tests for aggregator (mocked orchestrator)
- [ ] Integration tests for orchestrator → algorithm service calls
- [ ] Integration tests for orchestrator → aggregator calls
- [ ] End-to-end test: Full pipeline with docker-compose
- [ ] Test: Retry logic with exponential backoff
- [ ] Test: Deduplication on retries
- [ ] Test: Completion validation (all services complete)
- [ ] Test: Fault isolation (one service fails, others continue)
- [ ] Test: Service timeout handling
- [ ] Test: Health check endpoints
- [ ] Test: Error response formats

## Technical Details

### Unit Tests

**Orchestrator**:
- Mock algorithm service HTTP calls
- Test retry logic with mocked failures
- Test completion validation
- Test event fingerprinting
- Test request ID generation

**Algorithm Services**:
- Mock detection algorithms
- Test idempotency (cache behavior)
- Test request validation
- Test error handling

**Aggregator**:
- Mock orchestrator responses
- Test completion validation
- Test result merging
- Test CSV writing
- Test error handling

### Integration Tests

- Use test containers or HTTP mocks
- Test service-to-service communication
- Test retry scenarios
- Test timeout scenarios
- Test parallel service calls

### End-to-End Tests

- Full docker-compose setup
- Real service communication
- Test complete pipeline flow
- Test failure scenarios
- Test deduplication across retries

### Test Structure

```
tests/
├── unit/
│   ├── test_orchestrator.py
│   ├── test_layering_service.py
│   ├── test_wash_trading_service.py
│   └── test_aggregator.py
├── integration/
│   ├── test_orchestrator_algorithm.py
│   ├── test_orchestrator_aggregator.py
│   └── test_retry_logic.py
└── e2e/
    ├── test_full_pipeline.py
    ├── test_fault_tolerance.py
    └── test_deduplication.py
```

### Testing Tools

- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **httpx**: HTTP client for testing
- **pytest-mock**: Mocking utilities
- **testcontainers**: Docker container testing (optional)

## Implementation Notes

- Use pytest fixtures for common test setup
- Mock external HTTP calls in unit tests
- Use test doubles for algorithm services
- Test error paths and edge cases
- Aim for >80% code coverage

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Retry & Fault Tolerance](./FEATURE-retry-fault-tolerance.md)
- [Deduplication Strategy](./FEATURE-deduplication.md)

## Questions/Clarifications

- Should we use testcontainers for integration tests?
- What is the target code coverage?
- Should we add performance/load tests?

