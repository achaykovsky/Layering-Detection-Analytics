# Architecture: Microservices Deployment

## Overview

The system is decomposed into independent microservices, each with its own Docker container, enabling independent deployment, scaling, and fault isolation. The architecture follows a distributed pipeline pattern with retry logic, deduplication, and completion validation.

## Architecture Evolution

**Current Architecture**: Microservices (this document)

**Legacy Architecture**: Monolithic (see [ARCHITECTURE.md](./ARCHITECTURE.md))

This microservices architecture evolved from a monolithic design to address scalability, fault isolation, and independent deployment needs.

**Migration Status**: 
- ✅ Microservices architecture designed and documented
- 🚧 Implementation in progress
- ⏳ Monolithic architecture remains functional during transition

**When to use Microservices**:
- Production deployments requiring scalability
- Independent algorithm scaling needs
- Fault isolation requirements
- High availability requirements
- Need for parallel algorithm execution

**When Monolithic is acceptable**:
- Development/testing (simpler setup)
- Small-scale deployments
- Single-machine execution
- Rapid prototyping

**Performance Comparison**:

| Aspect | Monolithic | Microservices |
|--------|-----------|---------------|
| Network Latency | Zero (in-process) | ~10-50ms per service call |
| Execution | Sequential (sum of times) | Parallel (max of times) |
| Scaling | Single point | Independent per service |
| Fault Isolation | None (single failure point) | Per-service isolation |
| **Net Benefit** | Simpler, faster for small workloads | Better for production, parallelization typically outweighs network overhead |

## System Architecture

### High-Level Flow

```
CSV Input → Orchestrator → [Algorithm Services (parallel)] → Aggregator → Output
```

**Components:**
1. **Orchestrator Service**: Reads input, coordinates algorithm calls, handles retries
2. **Algorithm Services**: Independent detection microservices (Layering, Wash Trading)
3. **Aggregator Service**: Validates completion, merges results, writes output

### Architecture Diagram

```mermaid
graph TD
    A[CSV Input<br/>transactions.csv] -->|read| B[Orchestrator Service<br/>:8000]
    B -->|POST /detect<br/>request_id + events| C[Layering Service<br/>:8001]
    B -->|POST /detect<br/>request_id + events| D[Wash Trading Service<br/>:8002]
    C -->|SuspiciousSequence[]| B
    D -->|SuspiciousSequence[]| B
    B -->|POST /aggregate<br/>all results + metadata| E[Aggregator Service<br/>:8003]
    E -->|write| F[suspicious_accounts.csv]
    E -->|write| G[detections.csv]
    
    subgraph "Docker Compose Network"
        B
        C
        D
        E
    end
    
    subgraph "Algorithm Services"
        C
        D
    end
    
    style C fill:#e1f5ff
    style D fill:#e1f5ff
    style B fill:#fff4e1
    style E fill:#e8f5e9
```

## Service Responsibilities

### 1. Orchestrator Service (`orchestrator-service/`)

**Purpose**: Coordinate pipeline execution, manage algorithm service calls, handle retries and fault tolerance.

**Responsibilities:**
- Read input CSV file
- Generate unique `request_id` for each pipeline run
- Hash events to create `event_fingerprint` for deduplication
- Call algorithm services in parallel with retry logic
- Track completion status for all expected services
- Collect results (success or failure) from all services
- Send aggregated results to aggregator service only when all services have final status

**Endpoints:**
- `POST /orchestrate` - Trigger pipeline execution (CLI entry point)
- `GET /health` - Health check

**Key Features:**
- Retry logic with exponential backoff
- Timeout handling per service call
- Completion tracking (all services must reach `final_status=True`)
- Fault isolation (one service failure doesn't stop others)

**Configuration:**
```python
EXPECTED_SERVICES = ["layering", "wash_trading"]
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 2
ALGORITHM_TIMEOUT_SECONDS = 30
LAYERING_SERVICE_URL = "http://layering-service:8001"
WASH_TRADING_SERVICE_URL = "http://wash-trading-service:8002"
AGGREGATOR_SERVICE_URL = "http://aggregator-service:8003"
```

### 2. Algorithm Services (Layering & Wash Trading)

**Purpose**: Independent detection microservices, each implementing a single algorithm.

**Responsibilities:**
- Accept detection requests with `request_id` and events
- Implement idempotent detection (same `request_id` + `event_fingerprint` = same result)
- Return `List[SuspiciousSequence]` or error
- Cache results by `(request_id, event_fingerprint)` to prevent duplicate processing

**Endpoints:**
- `POST /detect` - Run detection algorithm
  - Request: `{request_id, event_fingerprint, events}`
  - Response: `{request_id, service_name, results: List[SuspiciousSequence]}`
- `GET /health` - Health check

**Layering Service** (`layering-service/`):
- Port: 8001
- Implements: `LayeringDetectionAlgorithm`
- Dependencies: `layering_detection.detectors.layering_detector`

**Wash Trading Service** (`wash-trading-service/`):
- Port: 8002
- Implements: `WashTradingDetectionAlgorithm`
- Dependencies: `layering_detection.detectors.wash_trading_detector`

**Key Features:**
- Stateless (except result cache for idempotency)
- Independent scaling
- Fault isolation
- Idempotent operations

### 3. Aggregator Service (`aggregator-service/`)

**Purpose**: Validate completion, merge results from all algorithm services, write output files.

**Responsibilities:**
- Validate all expected services have `final_status=True`
- Verify all services responded (no missing services)
- Merge successful results from all algorithm services
- Write `suspicious_accounts.csv` and `detections.csv`
- Log warnings for failed services (but continue if validation passes)

**Endpoints:**
- `POST /aggregate` - Aggregate and write results
  - Request: `{request_id, expected_services, results: [AlgorithmResponse]}`
  - Response: `{status, merged_count, failed_services}`
- `GET /health` - Health check

**Key Features:**
- Completion validation (blocks until all services finished)
- Result merging
- CSV writing (I/O operations)
- Error logging for failed services

**Configuration:**
```python
VALIDATION_STRICT = True  # Fail if services missing
ALLOW_PARTIAL_RESULTS = False  # Only merge if all completed
OUTPUT_DIR = "/app/output"
LOGS_DIR = "/app/logs"
```

## Data Models

### Request/Response Models

**Note**: All API request/response models use Pydantic for serialization and validation. Domain models (`TransactionEvent`, `SuspiciousSequence`) are converted to/from Pydantic DTOs at service boundaries.

**AlgorithmRequest** (Orchestrator → Algorithm Service):
```python
{
  "request_id": str,  # UUID
  "event_fingerprint": str,  # SHA256 hash of events
  "events": List[TransactionEvent]  # Serialized as JSON
}
```

**AlgorithmResponse** (Algorithm Service → Orchestrator):
```python
{
  "request_id": str,
  "service_name": str,  # "layering" or "wash_trading"
  "status": "success" | "failure" | "timeout",
  "results": List[SuspiciousSequence] | null,
  "error": str | null
}
```

**AggregateRequest** (Orchestrator → Aggregator):
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

**AggregateResponse** (Aggregator → Orchestrator):
```python
{
  "status": "completed" | "validation_failed",
  "merged_count": int,
  "failed_services": List[str],
  "error": str | null
}
```

## Fault Tolerance & Retry Logic

### Orchestrator Retry Strategy

**Implementation:**
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

**Retry Configuration:**
- Max retries: 3 (configurable)
- Backoff: Exponential (2^attempt seconds)
- Timeout per call: 30 seconds
- Retry on: TimeoutError, ConnectionError, HTTP 5xx errors

### Deduplication Strategy

**Event Fingerprinting:**
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

**Algorithm Service Idempotency:**
- Cache results by `(request_id, event_fingerprint)`
- Return cached result if same request received
- Prevents duplicate processing on retries

**Implementation:**
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

## Completion Validation

### Orchestrator Validation

**Requirement**: All expected services must reach `final_status=True` before sending to aggregator.

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

**Requirement**: Validate all expected services responded and have final status.

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

## Service Structure

```
services/
├── layering-service/
│   ├── Dockerfile
│   ├── main.py (FastAPI app)
│   ├── requirements.txt
│   └── README.md
├── wash-trading-service/
│   ├── Dockerfile
│   ├── main.py (FastAPI app)
│   ├── requirements.txt
│   └── README.md
├── orchestrator-service/
│   ├── Dockerfile
│   ├── main.py (FastAPI + orchestration logic)
│   ├── config.py
│   ├── requirements.txt
│   └── README.md
└── aggregator-service/
    ├── Dockerfile
    ├── main.py (FastAPI + validation + I/O)
    ├── config.py
    ├── requirements.txt
    └── README.md
```

## Docker Compose Configuration

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  layering-service:
    build:
      context: ./services/layering-service
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    networks:
      - layering-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    environment:
      - PORT=8001

  wash-trading-service:
    build:
      context: ./services/wash-trading-service
      dockerfile: Dockerfile
    ports:
      - "8002:8002"
    networks:
      - layering-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    environment:
      - PORT=8002

  orchestrator-service:
    build:
      context: ./services/orchestrator-service
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    networks:
      - layering-network
    volumes:
      - ./input:/app/input:ro
    depends_on:
      layering-service:
        condition: service_healthy
      wash-trading-service:
        condition: service_healthy
      aggregator-service:
        condition: service_healthy
    environment:
      - PORT=8000
      - LAYERING_SERVICE_URL=http://layering-service:8001
      - WASH_TRADING_SERVICE_URL=http://wash-trading-service:8002
      - AGGREGATOR_SERVICE_URL=http://aggregator-service:8003
      - MAX_RETRIES=3
      - ALGORITHM_TIMEOUT_SECONDS=30

  aggregator-service:
    build:
      context: ./services/aggregator-service
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    networks:
      - layering-network
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs
    environment:
      - PORT=8003
      - OUTPUT_DIR=/app/output
      - LOGS_DIR=/app/logs
      - VALIDATION_STRICT=true

networks:
  layering-network:
    driver: bridge

volumes:
  output:
  logs:
```

## Decision Records (ADR)

### ADR-001: Microservices Architecture

**Status**: Accepted

**Context**: Need independent deployment, scaling, and fault isolation for detection algorithms.

**Decision**: Decompose monolithic application into 4 microservices:
- Orchestrator (coordination)
- Layering Service (detection)
- Wash Trading Service (detection)
- Aggregator (merging & I/O)

**Consequences**:
- **Pros**: Independent scaling, fault isolation, technology flexibility, parallel execution
- **Cons**: Network latency, deployment complexity, distributed debugging

### ADR-002: Retry with Exponential Backoff

**Status**: Accepted

**Context**: Algorithm services may fail due to transient network issues or temporary overload.

**Decision**: Implement retry logic in orchestrator with exponential backoff (max 3 retries, 2^attempt seconds).

**Consequences**:
- **Pros**: Handles transient failures, improves reliability
- **Cons**: Increased latency on failures, potential duplicate processing (mitigated by deduplication)

### ADR-003: Event Fingerprinting for Deduplication

**Status**: Accepted

**Context**: Retries may cause duplicate event processing.

**Decision**: Generate SHA256 hash of sorted event signatures as `event_fingerprint`. Algorithm services cache results by `(request_id, event_fingerprint)`.

**Consequences**:
- **Pros**: Prevents duplicate processing, enables idempotent operations
- **Cons**: Memory overhead for cache (acceptable for batch processing)

### ADR-004: Completion Validation Before Aggregation

**Status**: Accepted

**Context**: Aggregator must ensure all algorithm services completed before merging results.

**Decision**: Orchestrator tracks `final_status` for each service. Aggregator validates all expected services have `final_status=True` before processing.

**Consequences**:
- **Pros**: Guarantees completeness, prevents partial results
- **Cons**: Pipeline blocks until all services complete (even if exhausted retries)

### ADR-005: REST API over gRPC

**Status**: Accepted

**Context**: Need inter-service communication protocol.

**Decision**: Use REST APIs (FastAPI) with JSON serialization.

**Rationale**:
- Simpler debugging (human-readable JSON)
- No code generation required
- Sufficient for batch processing (not high-frequency)
- Easier integration with existing Python codebase

**Consequences**:
- **Pros**: Simplicity, debuggability, no protobuf maintenance
- **Cons**: Higher overhead than gRPC (acceptable for batch workloads)

## Implementation Decisions

This section documents specific implementation choices made to resolve open questions during architecture design.

### IMP-001: Shared Code Distribution

**Decision**: Package `layering_detection` as a pip-installable dependency and install in each service.

**Rationale**:
- Enables independent versioning per service (if needed in future)
- Standard Python packaging approach
- Each service Dockerfile installs the package from source or wheel
- Maintains service independence while sharing domain logic

**Implementation**:
- Each service Dockerfile copies `pyproject.toml`, `src/`, and installs via `pip install .`
- Services can optionally pin versions if needed
- Shared models, detectors, and utilities available to all services

### IMP-002: JSON Serialization Strategy

**Decision**: Use Pydantic models for API boundaries (DTOs).

**Rationale**:
- Type-safe serialization/deserialization
- Automatic validation of request/response data
- Handles `datetime` and `Decimal` types correctly
- Clear separation between domain models and API contracts

**Implementation**:
- Create Pydantic models for `TransactionEvent`, `SuspiciousSequence` in API layer
- Convert between domain models (dataclasses) and Pydantic models at service boundaries
- FastAPI automatically handles Pydantic serialization

### IMP-003: Orchestrator Entry Point

**Decision**: Support both CLI and REST API.

**Rationale**:
- CLI maintains backward compatibility with existing `main.py` interface
- REST API enables programmatic access and future integration
- Flexible deployment options

**Implementation**:
- CLI: `POST /orchestrate` endpoint accepts input path parameter
- REST: Same endpoint can be called programmatically
- Keep existing `main.py` as CLI wrapper that calls orchestrator service

### IMP-004: Aggregator Validation Failure Behavior

**Decision**: Fail fast with clear error message.

**Rationale**:
- Prevents partial/incomplete results from being written
- Clear error messages aid debugging
- Aligns with `VALIDATION_STRICT=true` configuration

**Implementation**:
- Aggregator raises `ValueError` with detailed message on validation failure
- Orchestrator catches and propagates error to caller
- Pipeline fails immediately, no partial output files written

### IMP-005: Algorithm Service Cache Management

**Decision**: Simple in-memory cache, no eviction needed for batch processing.

**Rationale**:
- Batch processing runs single pipeline per execution
- Cache only needed for retry deduplication within same request
- No need for complex eviction strategies
- Memory overhead acceptable for batch workloads

**Implementation**:
- In-memory dictionary: `cache: dict[tuple[str, str], List[SuspiciousSequence]]`
- Key: `(request_id, event_fingerprint)`
- Cache cleared after pipeline completion (or per-request cleanup)
- No size limits or eviction policies

### IMP-006: Docker Compose Health Check Dependencies

**Decision**: Add health check conditions to prevent race conditions.

**Rationale**:
- Ensures services are ready before dependent services start
- Prevents connection errors during startup
- Standard Docker Compose best practice

**Implementation**:
- Use `depends_on` with `condition: service_healthy` in docker-compose.yml
- All services implement `/health` endpoint
- Health checks verify service is ready to accept requests

### IMP-007: Logging Strategy

**Decision**: Structured logging to stdout with `request_id`; Docker handles aggregation.

**Rationale**:
- Structured logs enable easy filtering and tracing
- `request_id` allows tracking requests across services
- Docker Compose aggregates stdout/stderr automatically
- Simple, no additional infrastructure needed

**Implementation**:
- Use Python `logging` module with JSON formatter (optional)
- Include `request_id` in all log messages
- Log to stdout/stderr (Docker best practice)
- Format: `{"request_id": "...", "level": "...", "message": "...", ...}`

### IMP-008: Error Response Format

**Decision**: HTTP 200 with status in response body.

**Rationale**:
- Allows orchestrator to handle success/failure uniformly
- Error details included in response body
- Simplifies retry logic (all responses are 200, check status field)

**Implementation**:
- Algorithm services always return HTTP 200
- Response body includes `status: "success" | "failure" | "timeout"`
- Error details in `error` field when status != "success"
- Orchestrator checks `status` field to determine success/failure

### IMP-009: Configuration Management

**Decision**: Environment variables only.

**Rationale**:
- Simple and Docker-friendly
- No config file parsing needed
- Easy to override per environment
- Standard 12-factor app approach

**Implementation**:
- All configuration via environment variables
- Default values in code (with clear documentation)
- Environment variables override defaults
- No config files required

### IMP-010: Testing Approach

**Decision**: All three levels - unit, integration, and end-to-end.

**Rationale**:
- Comprehensive test coverage
- Unit tests for fast feedback
- Integration tests verify service communication
- E2E tests validate full pipeline

**Implementation**:
- **Unit tests**: Each service tested independently with mocked dependencies
- **Integration tests**: Test service-to-service communication with test containers or mocks
- **End-to-end tests**: Full pipeline with docker-compose, test failure scenarios

### IMP-011: Backward Compatibility

**Decision**: Keep `main.py` as CLI wrapper that calls orchestrator service.

**Rationale**:
- Maintains existing CLI interface
- Users can continue using `python main.py` command
- Smooth migration path

**Implementation**:
- `main.py` remains as entry point
- Internally calls orchestrator service via HTTP or direct import
- Same command-line arguments and behavior
- Can be refactored to call orchestrator service REST API

### IMP-012: Service Discovery

**Decision**: Hardcoded URLs using Docker Compose DNS.

**Rationale**:
- Docker Compose provides DNS resolution for service names
- Simple and sufficient for current needs
- No additional infrastructure required
- Can migrate to service discovery later if needed

**Implementation**:
- Service URLs: `http://layering-service:8001`, `http://wash-trading-service:8002`, etc.
- Docker Compose DNS resolves service names to container IPs
- Environment variables for service URLs (allows override if needed)
- No service discovery mechanism required

## Tradeoff Analysis

### Microservices vs Monolith

| Aspect | Microservices | Monolith |
|--------|--------------|----------|
| **Deployment** | Independent | Single unit |
| **Scaling** | Per-service | All-or-nothing |
| **Fault Isolation** | High | Low |
| **Latency** | Network overhead | In-process calls |
| **Complexity** | High (orchestration) | Low |
| **Debugging** | Distributed | Centralized |

**Decision**: Microservices chosen for scalability and fault isolation requirements.

### Synchronous vs Asynchronous Communication

| Aspect | Synchronous (REST) | Asynchronous (Message Queue) |
|--------|-------------------|------------------------------|
| **Simplicity** | High | Low |
| **Latency** | Request-response | Eventual consistency |
| **Error Handling** | Immediate feedback | Requires compensation |
| **Scalability** | Limited by blocking | High (decoupled) |

**Decision**: Synchronous REST chosen for simplicity and immediate feedback in batch processing.

### Retry Strategy: Fixed vs Exponential Backoff

| Aspect | Fixed Interval | Exponential Backoff |
|--------|----------------|---------------------|
| **Recovery Time** | Predictable | Variable |
| **Server Load** | Constant | Decreasing |
| **Implementation** | Simple | Slightly complex |

**Decision**: Exponential backoff chosen to reduce server load on retries.

## Scalability Considerations

### Horizontal Scaling

**Algorithm Services**:
- Stateless design enables horizontal scaling
- Load balancer can distribute requests
- Each instance can process independent requests

**Orchestrator Service**:
- Can scale for concurrent pipeline executions
- Each request is independent

**Aggregator Service**:
- I/O-bound (CSV writing)
- Can scale for concurrent aggregations
- Consider file locking for concurrent writes

### Resource Allocation

**Algorithm Services**:
- CPU-intensive (detection algorithms)
- Memory: Moderate (event processing)
- Scale based on detection workload

**Orchestrator Service**:
- Network I/O intensive (calling multiple services)
- Memory: Low (coordination only)
- Scale based on concurrent pipeline executions

**Aggregator Service**:
- I/O-intensive (CSV writing)
- Memory: Low (result merging)
- Scale based on output volume

## Security Considerations

### Network Security

- Services communicate over internal Docker network
- No external exposure (except orchestrator entry point)
- Health checks for service monitoring

### Input Validation

- All services validate input data
- Event fingerprinting prevents injection
- CSV sanitization in aggregator (inherited from existing code)

### Service Authentication

- **Current**: None (internal network)
- **Future**: Consider service mesh (Istio) or API keys for production

## Deployment Strategy

### Development

```bash
docker-compose up --build
```

### Production

1. Build images: `docker-compose build`
2. Push to registry: Tag and push each service image
3. Deploy: Use orchestration platform (Kubernetes, ECS) or docker-compose
4. Scaling: Configure replicas per service based on load

### Monitoring

- Health checks: `/health` endpoint per service
- Logging: Structured logs with `request_id` for tracing
- Metrics: Request count, latency, error rate per service

## Migration Path

### Phase 1: Service Extraction
1. Extract algorithm logic to separate services
2. Create Dockerfiles for each service
3. Implement REST APIs

### Phase 2: Orchestration
1. Create orchestrator service
2. Implement retry logic and completion tracking
3. Replace direct algorithm calls with HTTP calls

### Phase 3: Aggregation
1. Create aggregator service
2. Move I/O operations to aggregator
3. Implement validation logic

### Phase 4: Docker Compose
1. Create `docker-compose.yml`
2. Configure networking and volumes
3. Test end-to-end pipeline

## Extension Points

### Adding New Algorithm Service

1. Create new service directory: `services/new-algorithm-service/`
2. Implement FastAPI app with `/detect` endpoint
3. Add service to `docker-compose.yml`
4. Update orchestrator config: Add to `EXPECTED_SERVICES`
5. No changes needed to other services

**Comparison with Monolithic Architecture**:
- **Monolithic**: Add algorithm class, register with `@AlgorithmRegistry.register` decorator
- **Microservices**: Create new service (more setup, but enables independent scaling/deployment)

### Configuration Management

- Environment variables per service
- Centralized config service (future)
- Secrets management (future: Vault, AWS Secrets Manager)

## Performance Considerations

### Network Latency

- **Impact**: HTTP calls add ~10-50ms per service call
- **Mitigation**: Parallel calls in orchestrator
- **Acceptable**: Batch processing tolerates network overhead

### Caching

- Algorithm services cache results for idempotency
- Cache size: Limited by memory (acceptable for batch)
- Cache eviction: LRU or TTL (future enhancement)

### Parallel Execution

- Orchestrator calls algorithm services in parallel
- Reduces total pipeline time
- Tradeoff: Higher resource usage

## Testing Strategy

**Comparison with Monolithic Architecture**:
- **Monolithic**: Unit tests for algorithms/I/O, integration test for `run_pipeline()` end-to-end
- **Microservices**: Additional service-to-service communication tests, retry logic, fault tolerance, distributed system integration tests

### Unit Tests

- Each service tested independently
- Mock external dependencies
- Test retry logic, validation, deduplication

### Integration Tests

- Test service-to-service communication
- Test retry scenarios
- Test completion validation

### End-to-End Tests

- Full pipeline with docker-compose
- Test failure scenarios (service down, timeout)
- Test deduplication on retries

## Future Enhancements

1. **Service Mesh**: Istio for advanced routing, retry policies
2. **Message Queue**: Async processing for high-volume workloads
3. **Distributed Tracing**: OpenTelemetry for request tracking
4. **Circuit Breaker**: Prevent cascading failures
5. **Rate Limiting**: Protect services from overload
6. **Metrics & Observability**: Prometheus, Grafana dashboards
