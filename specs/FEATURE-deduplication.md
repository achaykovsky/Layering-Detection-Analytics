# Feature: Deduplication Strategy

## Overview

Implements event fingerprinting and result caching to prevent duplicate processing of the same events during retries. Ensures idempotent operations across algorithm services.

## Requirements

- [ ] Generate deterministic `event_fingerprint` from event set
- [ ] Use SHA256 hash of sorted event signatures
- [ ] Cache algorithm results by `(request_id, event_fingerprint)` tuple
- [ ] Return cached result if same request received
- [ ] Prevent duplicate processing on retries
- [ ] Clear cache after pipeline completion (or per-request cleanup)

## Acceptance Criteria

- [ ] `event_fingerprint` is deterministic (same events = same hash)
- [ ] Hash includes: timestamp, account_id, product_id, side, price, quantity, event_type
- [ ] Events are sorted before hashing
- [ ] Algorithm services cache results by `(request_id, event_fingerprint)`
- [ ] Cached result returned immediately (no re-processing)
- [ ] Cache prevents duplicate processing on retries
- [ ] Cache cleared after request completion
- [ ] Hash is SHA256 hexdigest (64 characters)

## Technical Details

### Event Fingerprinting

```python
def _hash_events(events: List[TransactionEvent]) -> str:
    """Generate deterministic fingerprint for event set."""
    event_signatures = sorted([
        (
            e.timestamp.isoformat(),
            e.account_id,
            e.product_id,
            e.side,
            str(e.price),
            e.quantity,
            e.event_type
        )
        for e in events
    ])
    return hashlib.sha256(
        json.dumps(event_signatures).encode()
    ).hexdigest()
```

### Algorithm Service Idempotency

```python
# In algorithm service
cache: dict[tuple[str, str], List[SuspiciousSequence]] = {}

async def detect(request: AlgorithmRequest):
    cache_key = (request.request_id, request.event_fingerprint)
    
    if cache_key in cache:
        return cache[cache_key]  # Deduplicate
    
    result = algorithm.detect(request.events)
    cache[cache_key] = result
    return result
```

### Cache Key Structure

- Key: `(request_id: str, event_fingerprint: str)`
- Value: `List[SuspiciousSequence]`
- Scope: Per-service, in-memory

### Cache Management

- **Current**: Simple in-memory dictionary
- **Eviction**: None (cleared after pipeline completion)
- **Size**: Limited by memory (acceptable for batch processing)
- **Future**: Consider LRU eviction or TTL for long-running services

## Implementation Notes

- Fingerprint must be deterministic (same input = same hash)
- Sorting ensures order-independent hashing
- Cache is per-service instance (not shared across instances)
- Consider distributed cache (Redis) for multi-instance scenarios (future)

## Tradeoff Analysis

| Aspect | In-Memory Cache | Distributed Cache (Redis) |
|--------|----------------|--------------------------|
| Simplicity | High | Low |
| Multi-Instance | No | Yes |
| Latency | Zero | ~1-5ms |
| Infrastructure | None | Redis required |

**Decision**: In-memory cache chosen for simplicity and batch processing use case.

## Related Specs

- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Retry & Fault Tolerance](./FEATURE-retry-fault-tolerance.md)
- [Orchestrator Service](./FEATURE-orchestrator-service.md)

## Questions/Clarifications

- Should cache persist across service restarts?
- What is the maximum cache size before eviction needed?
- Should we add cache metrics (hit rate, size)?

