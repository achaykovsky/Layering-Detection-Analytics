# Feature: Completion Validation

## Overview

Ensures all algorithm services have completed (reached `final_status=True`) before aggregating results. Prevents partial or incomplete results from being written to output files.

## Requirements

- [ ] Orchestrator tracks `final_status` for each service
- [ ] Orchestrator validates all services reached `final_status=True` before sending to aggregator
- [ ] Aggregator validates all expected services responded
- [ ] Aggregator validates all services have `final_status=True`
- [ ] Fail fast with clear error if validation fails
- [ ] Block pipeline until all services complete (even if exhausted retries)

## Acceptance Criteria

- [ ] Orchestrator tracks `final_status` in service status dict
- [ ] `final_status=True` set when service succeeds or retries exhausted
- [ ] `final_status=False` set during retry attempts
- [ ] Orchestrator raises `RuntimeError` if services incomplete before aggregation
- [ ] Aggregator validates all expected services present in results
- [ ] Aggregator validates all services have `final_status=True`
- [ ] Aggregator raises `ValueError` with detailed message if validation fails
- [ ] Error messages include missing/incomplete service names
- [ ] Pipeline blocks until all services reach final status
- [ ] No partial output files written on validation failure

## Technical Details

### Orchestrator Validation

```python
def _validate_all_completed(service_status: dict, expected_services: List[str]):
    """Ensure all services have final_status=True."""
    incomplete = [
        name for name in expected_services
        if not service_status.get(name, {}).get("final_status", False)
    ]
    if incomplete:
        raise RuntimeError(
            f"Services did not complete: {incomplete}. "
            f"All services must reach final_status=True"
        )
```

### Aggregator Validation

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

### Final Status States

- **`final_status=False`**: Service call in progress or retrying
- **`final_status=True`**: Service completed (success or exhausted retries)

### Validation Flow

1. Orchestrator calls algorithm services in parallel
2. Each service call tracks `final_status` in service_status dict
3. Orchestrator waits for all services to reach `final_status=True`
4. Orchestrator validates all completed before sending to aggregator
5. Aggregator validates completeness again (defense in depth)
6. Aggregator processes results only if validation passes

## Implementation Notes

- Two-level validation (orchestrator + aggregator) for defense in depth
- Clear error messages aid debugging
- Pipeline blocks until completion (no partial results)
- Consider timeout for completion validation (future)

## Tradeoff Analysis

| Aspect | Block Until Complete | Allow Partial Results |
|--------|---------------------|----------------------|
| Data Integrity | High | Low |
| Pipeline Latency | Higher (waits for all) | Lower (first available) |
| Error Handling | Clear (all or nothing) | Complex (partial handling) |

**Decision**: Block until complete chosen for data integrity and simplicity.

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Retry & Fault Tolerance](./FEATURE-retry-fault-tolerance.md)

## Questions/Clarifications

- Should we add timeout for completion validation?
- Should we support partial results mode (configurable)?
- What is the maximum wait time acceptable?

