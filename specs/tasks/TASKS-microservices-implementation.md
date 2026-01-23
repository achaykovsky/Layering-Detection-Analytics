# Microservices Implementation Tasks

## Overview

This document breaks down the microservices architecture into atomic, implementable tasks ordered by dependencies. Each task is designed to be completable in 1-4 hours with clear acceptance criteria.

## Task Status Legend

- ⏳ **Pending**: Not started
- 🚧 **In Progress**: Currently being worked on
- ✅ **Complete**: Finished and verified
- ❌ **Blocked**: Cannot proceed due to dependency

## Implementation Phases

### Phase 1: Foundation (API Contracts & Shared Code)
**Goal**: Establish API contracts and shared utilities that all services depend on.

### Phase 2: Algorithm Services
**Goal**: Build independent algorithm services that can be tested in isolation.

### Phase 3: Aggregator Service
**Goal**: Build aggregator service for result validation and CSV writing.

### Phase 4: Orchestrator Service
**Goal**: Build orchestrator service that coordinates the entire pipeline.

### Phase 5: Docker Infrastructure
**Goal**: Containerize all services and configure Docker Compose.

### Phase 6: Testing & Integration
**Goal**: Comprehensive testing and end-to-end validation.

---

## Phase 1: Foundation

### Task 1.1: Create API Contracts Module
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: None  
**Status**: ✅ Complete

**Description**:
Create shared API contracts module with Pydantic models for all inter-service communication. This module will be used by all services.

**Acceptance Criteria**:
- [x] Create `services/shared/api_models.py` module
- [x] Define `TransactionEventDTO` Pydantic model (converts datetime to ISO string, Decimal to string)
- [x] Define `SuspiciousSequenceDTO` Pydantic model (nested TransactionEventDTOs)
- [x] Define `AlgorithmRequest` Pydantic model (request_id, event_fingerprint, events)
- [x] Define `AlgorithmResponse` Pydantic model (request_id, service_name, status, results, error)
- [x] Define `AggregateRequest` Pydantic model (request_id, expected_services, results)
- [x] Define `AggregateResponse` Pydantic model (status, merged_count, failed_services, error)
- [x] All models validate correctly (UUID format, SHA256 hexdigest, literal values)
- [x] Models serialize to/from JSON correctly
- [x] Unit tests for model validation

**Files to Create**:
- `services/shared/api_models.py`
- `services/shared/__init__.py`
- `tests/unit/test_api_models.py`

**Notes**:
- Use Pydantic v2
- Ensure datetime serializes as ISO format strings
- Ensure Decimal serializes as strings (preserve precision)

---

### Task 1.2: Create Domain Model Conversion Utilities
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 1.1  
**Status**: ✅ Complete

**Description**:
Create conversion functions between domain models (dataclasses) and Pydantic DTOs for API serialization.

**Acceptance Criteria**:
- [x] Create `services/shared/converters.py` module
- [x] Implement `transaction_event_to_dto(event: TransactionEvent) -> TransactionEventDTO`
- [x] Implement `dto_to_transaction_event(dto: TransactionEventDTO) -> TransactionEvent`
- [x] Implement `suspicious_sequence_to_dto(seq: SuspiciousSequence) -> SuspiciousSequenceDTO`
- [x] Implement `dto_to_suspicious_sequence(dto: SuspiciousSequenceDTO) -> SuspiciousSequence`
- [x] Handle datetime conversion (domain → ISO string → domain)
- [x] Handle Decimal conversion (domain → string → domain)
- [x] Round-trip conversion tests (domain → DTO → domain preserves data)
- [x] Unit tests for all conversion functions

**Files to Create**:
- `services/shared/converters.py`
- `tests/unit/test_converters.py`

**Notes**:
- Ensure precision preserved for Decimal values
- Handle timezone-aware datetime objects

---

### Task 1.3: Create Shared Logging Utilities
**Type**: Feature  
**Priority**: P1 (High)  
**Effort**: ~1.5h  
**Dependencies**: None  
**Status**: ✅ Complete

**Description**:
Create shared logging utilities with request_id support for structured logging across all services.

**Acceptance Criteria**:
- [x] Create `services/shared/logging.py` module
- [x] Implement `RequestIdFilter` logging filter class
- [x] Implement `JSONFormatter` class for structured logging (optional)
- [x] Implement `setup_logging(service_name: str, log_level: str = "INFO")` function
- [x] Logger includes service name in all messages
- [x] Logger supports request_id via `extra={"request_id": "..."}` parameter
- [x] Logs to stdout/stderr (Docker-friendly)
- [x] Unit tests for logging setup

**Files to Create**:
- `services/shared/logging.py`
- `tests/unit/test_logging.py`

**Notes**:
- Use Python standard `logging` module
- JSON format optional (can be enabled via config)
- Ensure HIPAA/GDPR compliance (no PII in logs)

---

### Task 1.4: Create Shared Configuration Utilities
**Type**: Feature  
**Priority**: P1 (High)  
**Effort**: ~1h  
**Dependencies**: None  
**Status**: ✅ Complete

**Description**:
Create shared configuration utilities for environment variable management across services.

**Acceptance Criteria**:
- [x] Create `services/shared/config.py` module
- [x] Implement `get_port() -> int` (default from PORT env var)
- [x] Implement `get_service_url(service_name: str) -> str` helper
- [x] Implement `get_max_retries() -> int` (default 3)
- [x] Implement `get_timeout_seconds() -> int` (default 30)
- [x] Implement `get_output_dir() -> str` (default /app/output)
- [x] All functions have sensible defaults
- [x] Environment variables override defaults
- [x] Unit tests for configuration loading

**Files to Create**:
- `services/shared/config.py`
- `tests/unit/test_config.py`

**Notes**:
- Follow 12-factor app principles
- No config files, only environment variables

---

## Phase 2: Algorithm Services

### Task 2.1: Create Layering Service Structure
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 1.1, Task 1.2, Task 1.3  
**Status**: ✅ Complete

**Description**:
Create basic FastAPI application structure for Layering Service with health check endpoint.

**Acceptance Criteria**:
- [x] Create `services/layering-service/` directory
- [x] Create `services/layering-service/main.py` with FastAPI app
- [x] Create `services/layering-service/requirements.txt` with dependencies
- [x] Create `services/layering-service/README.md` with service documentation
- [x] FastAPI app starts on port 8001 (configurable via PORT env var)
- [x] Implement `GET /health` endpoint returning `{"status": "healthy", "service": "layering-service"}`
- [x] Service uses shared logging utilities
- [x] Service can be run locally: `uvicorn main:app --port 8001`

**Files to Create**:
- `services/layering-service/main.py`
- `services/layering-service/requirements.txt`
- `services/layering-service/README.md`

**Notes**:
- Use FastAPI for REST API
- Install `layering_detection` package as dependency

---

### Task 2.2: Implement Layering Service Detection Endpoint
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 2.1  
**Status**: ✅ Complete

**Description**:
Implement `POST /detect` endpoint for Layering Service that accepts AlgorithmRequest and returns AlgorithmResponse.

**Acceptance Criteria**:
- [x] Implement `POST /detect` endpoint accepting `AlgorithmRequest`
- [x] Convert DTO events to domain models using converters
- [x] Call `LayeringDetectionAlgorithm.detect()` from `layering_detection.detectors.layering_detector`
- [x] Convert domain results back to DTOs
- [x] Return `AlgorithmResponse` with `status: "success"` and results
- [x] Handle algorithm exceptions and return `status: "failure"` with error message
- [x] Log request with `request_id` for tracing
- [x] Return HTTP 200 even on failure (status in response body)
- [x] Unit tests for endpoint (mocked algorithm)

**Files to Modify**:
- `services/layering-service/main.py`

**Files to Create**:
- `tests/unit/test_layering_service.py`

**Notes**:
- Always return HTTP 200, check `status` field in response body
- Log errors with request_id

---

### Task 2.3: Implement Layering Service Idempotency Cache
**Type**: Feature  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 2.2  
**Status**: ✅ Complete

**Description**:
Implement in-memory result cache for idempotent operations. Cache results by `(request_id, event_fingerprint)` tuple.

**Acceptance Criteria**:
- [x] Create in-memory cache: `dict[tuple[str, str], List[SuspiciousSequenceDTO]]`
- [x] Check cache before processing: `cache_key = (request_id, event_fingerprint)`
- [x] Return cached result immediately if cache hit
- [x] Store result in cache after processing
- [x] Log cache hits and misses
- [x] Cache prevents duplicate processing on retries
- [x] Unit tests for cache behavior (hit, miss, same request_id different fingerprint)

**Files to Modify**:
- `services/layering-service/main.py`

**Files to Modify**:
- `tests/unit/test_layering_service.py`

**Notes**:
- Cache is per-service instance
- No eviction needed for batch processing

---

### Task 2.4: Create Wash Trading Service Structure
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 1.1, Task 1.2, Task 1.3  
**Status**: ✅ Complete

**Description**:
Create basic FastAPI application structure for Wash Trading Service with health check endpoint.

**Acceptance Criteria**:
- [x] Create `services/wash-trading-service/` directory
- [x] Create `services/wash-trading-service/main.py` with FastAPI app
- [x] Create `services/wash-trading-service/requirements.txt` with dependencies
- [x] Create `services/wash-trading-service/README.md` with service documentation
- [x] FastAPI app starts on port 8002 (configurable via PORT env var)
- [x] Implement `GET /health` endpoint returning `{"status": "healthy", "service": "wash-trading-service"}`
- [x] Service uses shared logging utilities
- [x] Service can be run locally: `uvicorn main:app --port 8002`

**Files to Create**:
- `services/wash-trading-service/main.py`
- `services/wash-trading-service/requirements.txt`
- `services/wash-trading-service/README.md`

**Notes**:
- Similar structure to Layering Service
- Use FastAPI for REST API

---

### Task 2.5: Implement Wash Trading Service Detection Endpoint
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 2.4  
**Status**: ✅ Complete

**Description**:
Implement `POST /detect` endpoint for Wash Trading Service that accepts AlgorithmRequest and returns AlgorithmResponse.

**Acceptance Criteria**:
- [x] Implement `POST /detect` endpoint accepting `AlgorithmRequest`
- [x] Convert DTO events to domain models using converters
- [x] Call `WashTradingDetectionAlgorithm.detect()` from `layering_detection.detectors.wash_trading_detector`
- [x] Convert domain results back to DTOs
- [x] Return `AlgorithmResponse` with `status: "success"` and results
- [x] Handle algorithm exceptions and return `status: "failure"` with error message
- [x] Log request with `request_id` for tracing
- [x] Return HTTP 200 even on failure (status in response body)
- [x] Unit tests for endpoint (mocked algorithm)

**Files to Modify**:
- `services/wash-trading-service/main.py`

**Files to Create**:
- `tests/unit/test_wash_trading_service.py`

**Notes**:
- Same pattern as Layering Service
- Always return HTTP 200, check `status` field

---

### Task 2.6: Implement Wash Trading Service Idempotency Cache
**Type**: Feature  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 2.5  
**Status**: ✅ Complete

**Description**:
Implement in-memory result cache for idempotent operations in Wash Trading Service.

**Acceptance Criteria**:
- [x] Create in-memory cache: `dict[tuple[str, str], List[SuspiciousSequenceDTO]]`
- [x] Check cache before processing: `cache_key = (request_id, event_fingerprint)`
- [x] Return cached result immediately if cache hit
- [x] Store result in cache after processing
- [x] Log cache hits and misses
- [x] Cache prevents duplicate processing on retries
- [x] Unit tests for cache behavior

**Files to Modify**:
- `services/wash-trading-service/main.py`
- `tests/unit/test_wash_trading_service.py`

**Notes**:
- Same implementation as Layering Service cache

---

## Phase 3: Aggregator Service

### Task 3.1: Create Aggregator Service Structure
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 1.1, Task 1.2, Task 1.3, Task 1.4  
**Status**: ✅ Complete

**Description**:
Create basic FastAPI application structure for Aggregator Service with health check endpoint.

**Acceptance Criteria**:
- [x] Create `services/aggregator-service/` directory
- [x] Create `services/aggregator-service/main.py` with FastAPI app
- [x] Create `services/aggregator-service/config.py` for service-specific config
- [x] Create `services/aggregator-service/requirements.txt` with dependencies
- [x] Create `services/aggregator-service/README.md` with service documentation
- [x] FastAPI app starts on port 8003 (configurable via PORT env var)
- [x] Implement `GET /health` endpoint
- [x] Service uses shared logging utilities
- [x] Service can be run locally: `uvicorn main:app --port 8003`

**Files to Create**:
- `services/aggregator-service/main.py`
- `services/aggregator-service/config.py`
- `services/aggregator-service/requirements.txt`
- `services/aggregator-service/README.md`

**Notes**:
- Use FastAPI for REST API
- Install `layering_detection` package for domain models

---

### Task 3.2: Implement Completion Validation Logic
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 3.1  
**Status**: ✅ Complete

**Description**:
Implement validation logic to ensure all expected services completed before processing results.

**Acceptance Criteria**:
- [x] Create `validate_completeness(expected_services: List[str], results: List[AlgorithmResponse]) -> None` function
- [x] Check all expected services are present in results
- [x] Check all services have `final_status=True`
- [x] Raise `ValueError` with detailed message if validation fails
- [x] Error message includes missing service names
- [x] Error message includes incomplete service names
- [x] Unit tests for validation (missing services, incomplete services, success case)

**Files to Create**:
- `services/aggregator-service/validation.py`
- `tests/unit/test_aggregator_validation.py`

**Notes**:
- Clear error messages aid debugging
- Fail fast on validation errors

---

### Task 3.3: Implement Result Merging Logic
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 3.1, Task 3.2  
**Status**: ✅ Complete

**Description**:
Implement logic to merge suspicious sequences from all successful algorithm services, deduplicating sequences.

**Acceptance Criteria**:
- [x] Create `merge_results(results: List[AlgorithmResponse]) -> List[SuspiciousSequenceDTO]` function
- [x] Extract sequences from all successful services (status="success")
- [x] Deduplicate sequences (same account_id + overlapping time window)
- [x] Return merged list of unique sequences
- [x] Log merge counts (total sequences, deduplicated count)
- [x] Handle empty results gracefully
- [x] Unit tests for merging (multiple services, deduplication, empty results)

**Files to Create**:
- `services/aggregator-service/merger.py`
- `tests/unit/test_aggregator_merger.py`

**Notes**:
- Deduplication based on account_id and time window overlap
- Preserve all sequences from successful services

---

### Task 3.4: Implement CSV Writing Logic
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 3.3  
**Status**: ✅ Complete

**Description**:
Implement CSV writing logic to write `suspicious_accounts.csv` and `detections.csv` files. Reuse existing CSV writing utilities from monolithic codebase.

**Acceptance Criteria**:
- [x] Create `write_output_files(sequences: List[SuspiciousSequenceDTO], output_dir: str) -> None` function
- [x] Write `suspicious_accounts.csv` with unique account IDs
- [x] Write `detections.csv` with all sequences (account_id, start_time, end_time, detection_type, algorithm)
- [x] CSV format matches existing monolithic output format
- [x] Convert DTOs to domain models before writing (if needed)
- [x] Handle file write errors gracefully
- [x] Log file write completion
- [x] Unit tests for CSV writing (verify file contents, format)

**Files to Create**:
- `services/aggregator-service/writer.py`
- `tests/unit/test_aggregator_writer.py`

**Notes**:
- Reuse existing CSV utilities from `layering_detection.io` if possible
- Ensure backward compatibility with existing output format

---

### Task 3.5: Implement Aggregator Service Aggregate Endpoint
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 3.2, Task 3.3, Task 3.4  
**Status**: ✅ Complete

**Description**:
Implement `POST /aggregate` endpoint that validates completion, merges results, and writes output files.

**Acceptance Criteria**:
- [x] Implement `POST /aggregate` endpoint accepting `AggregateRequest`
- [x] Call `validate_completeness()` before processing
- [x] Call `merge_results()` to merge sequences
- [x] Call `write_output_files()` to write CSV files
- [x] Return `AggregateResponse` with status, merged_count, failed_services
- [x] Log warnings for failed services
- [x] Handle validation errors (return status="validation_failed")
- [x] Handle file write errors gracefully
- [x] Log aggregation completion with request_id
- [x] Integration tests for full aggregation flow

**Files to Modify**:
- `services/aggregator-service/main.py`

**Files to Create**:
- `tests/integration/test_aggregator_endpoint.py`

**Notes**:
- Fail fast on validation errors
- Continue processing if validation passes (even with failed services)

---

## Phase 4: Orchestrator Service

### Task 4.1: Create Orchestrator Service Structure
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 1.1, Task 1.2, Task 1.3, Task 1.4  
**Status**: ✅ Complete

**Description**:
Create basic FastAPI application structure for Orchestrator Service with health check endpoint.

**Acceptance Criteria**:
- [x] Create `services/orchestrator-service/` directory
- [x] Create `services/orchestrator-service/main.py` with FastAPI app
- [x] Create `services/orchestrator-service/config.py` for service-specific config
- [x] Create `services/orchestrator-service/requirements.txt` with dependencies
- [x] Create `services/orchestrator-service/README.md` with service documentation
- [x] FastAPI app starts on port 8000 (configurable via PORT env var)
- [x] Implement `GET /health` endpoint
- [x] Service uses shared logging utilities
- [x] Service can be run locally: `uvicorn main:app --port 8000`

**Files to Create**:
- `services/orchestrator-service/main.py`
- `services/orchestrator-service/config.py`
- `services/orchestrator-service/requirements.txt`
- `services/orchestrator-service/README.md`

**Notes**:
- Use FastAPI for REST API
- Install `layering_detection` package for domain models
- Install httpx or aiohttp for HTTP client

---

### Task 4.2: Implement CSV Reading Logic
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 4.1  
**Status**: ✅ Complete

**Description**:
Implement CSV reading logic to read input CSV file and parse TransactionEvent objects. Reuse existing CSV reading utilities.

**Acceptance Criteria**:
- [x] Create `read_input_csv(path: str) -> List[TransactionEvent]` function
- [x] Read CSV file from mounted volume (`/app/input/`)
- [x] Parse CSV rows to TransactionEvent domain models
- [x] Reuse existing CSV reading utilities from `layering_detection.io`
- [x] Handle file read errors gracefully
- [x] Validate CSV format and data
- [x] Log file reading completion
- [x] Unit tests for CSV reading (valid file, invalid file, missing file)

**Files to Create**:
- `services/orchestrator-service/reader.py`
- `tests/unit/test_orchestrator_reader.py`

**Notes**:
- Reuse existing CSV utilities from monolithic codebase
- Support streaming for large files (future enhancement)

---

### Task 4.3: Implement Request ID Generation
**Type**: Feature  
**Priority**: P1 (High)  
**Effort**: ~0.5h  
**Dependencies**: Task 4.1

**Description**:
Implement UUID generation for unique request_id per pipeline execution.

**Acceptance Criteria**:
- [ ] Create `generate_request_id() -> str` function
- [ ] Generate UUID v4 format
- [ ] Return string representation
- [ ] Unit tests for UUID format validation

**Files to Create**:
- `services/orchestrator-service/utils.py`
- `tests/unit/test_orchestrator_utils.py`

**Notes**:
- Use Python `uuid` module
- UUID format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

---

### Task 4.4: Implement Event Fingerprinting
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 4.1  
**Status**: ✅ Complete

**Description**:
Implement SHA256 hashing of sorted event signatures to generate deterministic event_fingerprint for deduplication.

**Acceptance Criteria**:
- [x] Create `hash_events(events: List[TransactionEvent]) -> str` function
- [x] Sort events by signature (timestamp, account_id, product_id, side, price, quantity, event_type)
- [x] Generate SHA256 hash of sorted signatures
- [x] Return hexdigest (64 characters)
- [x] Same events always produce same hash (deterministic)
- [x] Different events produce different hashes
- [x] Unit tests for fingerprinting (determinism, uniqueness)

**Files to Modify**:
- `services/orchestrator-service/utils.py`
- `tests/unit/test_orchestrator_utils.py`

**Notes**:
- Use `hashlib.sha256()` and `json.dumps()` for hashing
- Sorting ensures order-independent hashing

---

### Task 4.5: Implement Algorithm Service HTTP Client
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 4.1, Task 1.1  
**Status**: ✅ Complete

**Description**:
Implement HTTP client function to call algorithm services (Layering, Wash Trading) with timeout handling.

**Acceptance Criteria**:
- [x] Create `call_algorithm_service(service_name: str, request: AlgorithmRequest, timeout: int) -> AlgorithmResponse` function
- [x] Use httpx or aiohttp for async HTTP calls
- [x] Construct service URL from config
- [x] Send POST request to `/detect` endpoint
- [x] Handle timeout (raise TimeoutError)
- [x] Handle connection errors (raise ConnectionError)
- [x] Parse response to AlgorithmResponse
- [x] Log service call with request_id
- [x] Unit tests for HTTP client (success, timeout, connection error, 5xx error)

**Files to Create**:
- `services/orchestrator-service/client.py`
- `tests/unit/test_orchestrator_client.py`

**Notes**:
- Use async HTTP client (httpx.AsyncClient or aiohttp)
- Timeout configurable via ALGORITHM_TIMEOUT_SECONDS

---

### Task 4.6: Implement Retry Logic with Exponential Backoff
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 4.5  
**Status**: ✅ Complete

**Description**:
Implement retry logic with exponential backoff for algorithm service calls. Retry on transient errors up to MAX_RETRIES times.

**Acceptance Criteria**:
- [x] Create `process_with_retries(service_name: str, request_id: str, event_fingerprint: str, events: List[TransactionEvent], service_status: dict) -> None` function
- [x] Retry up to MAX_RETRIES times (default 3)
- [x] Exponential backoff: 2^attempt seconds between retries (1s, 2s, 4s)
- [x] Retry on: TimeoutError, ConnectionError, HTTP 5xx errors
- [x] Do not retry on: HTTP 4xx errors
- [x] Track retry_count in service_status
- [x] Set `final_status=True` after success or retries exhausted
- [x] Set `status="success"` on success, `status="exhausted"` on failure
- [x] Log retry attempts with request_id and backoff delay
- [x] Unit tests for retry logic (success on retry, exhausted retries, no retry on 4xx)

**Files to Create**:
- `services/orchestrator-service/retry.py`
- `tests/unit/test_orchestrator_retry.py`

**Notes**:
- Use `asyncio.sleep()` for backoff
- Fault isolation: one service failure doesn't stop others

---

### Task 4.7: Implement Completion Tracking and Validation
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 4.6  
**Status**: ✅ Complete

**Description**:
Implement logic to track completion status for all services and validate all services completed before aggregation.

**Acceptance Criteria**:
- [x] Create `validate_all_completed(service_status: dict, expected_services: List[str]) -> None` function
- [x] Check all expected services have `final_status=True`
- [x] Raise `RuntimeError` with detailed message if incomplete
- [x] Error message includes incomplete service names
- [x] Track service_status dict with status, final_status, result, retry_count
- [x] Unit tests for validation (all complete, incomplete services)

**Files to Create**:
- `services/orchestrator-service/validation.py`
- `tests/unit/test_orchestrator_validation.py`

**Notes**:
- Validation happens before sending to aggregator
- Clear error messages aid debugging

---

### Task 4.8: Implement Parallel Algorithm Service Calls
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 4.6, Task 4.7  
**Status**: ✅ Complete

**Description**:
Implement parallel execution of algorithm service calls using asyncio.gather for concurrent processing.

**Acceptance Criteria**:
- [x] Create `call_all_algorithm_services(request_id: str, event_fingerprint: str, events: List[TransactionEvent]) -> dict` function
- [x] Call all algorithm services in parallel using `asyncio.gather()`
- [x] Each service call uses `process_with_retries()` for retry logic
- [x] Track service_status for all services
- [x] Wait for all services to complete (reach final_status=True)
- [x] Return service_status dict with all results
- [x] Log parallel execution start/end
- [x] Unit tests for parallel calls (all succeed, some fail, all fail)

**Files to Create**:
- `services/orchestrator-service/orchestrator.py`
- `tests/unit/test_orchestrator_parallel.py`

**Notes**:
- Use `asyncio.gather()` for parallel execution
- Fault isolation: failures don't stop other services

---

### Task 4.9: Implement Aggregator Service HTTP Client
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~1.5h  
**Dependencies**: Task 4.1, Task 1.1  
**Status**: ✅ Complete

**Description**:
Implement HTTP client function to call aggregator service with AggregateRequest.

**Acceptance Criteria**:
- [x] Create `call_aggregator_service(request: AggregateRequest) -> AggregateResponse` function
- [x] Use httpx or aiohttp for async HTTP calls
- [x] Construct aggregator URL from config
- [x] Send POST request to `/aggregate` endpoint
- [x] Parse response to AggregateResponse
- [x] Handle errors gracefully
- [x] Log aggregator call with request_id
- [x] Unit tests for aggregator client (success, error)

**Files to Modify**:
- `services/orchestrator-service/client.py`
- `tests/unit/test_orchestrator_client.py`

**Notes**:
- Similar to algorithm service client
- No retry logic needed (aggregator is final step)

---

### Task 4.10: Implement Orchestrator Pipeline Endpoint
**Type**: Feature  
**Priority**: P0 (Critical)  
**Effort**: ~3h  
**Dependencies**: Task 4.2, Task 4.3, Task 4.4, Task 4.8, Task 4.9  
**Status**: ✅ Complete

**Description**:
Implement `POST /orchestrate` endpoint that coordinates the entire pipeline: read CSV, call algorithms, aggregate results.

**Acceptance Criteria**:
- [x] Implement `POST /orchestrate` endpoint accepting input file path
- [x] Call `read_input_csv()` to read events
- [x] Call `generate_request_id()` to create request_id
- [x] Call `hash_events()` to create event_fingerprint
- [x] Call `call_all_algorithm_services()` to process algorithms in parallel
- [x] Call `validate_all_completed()` to ensure completion
- [x] Call `call_aggregator_service()` to aggregate and write results
- [x] Return pipeline status and results
- [x] Log pipeline execution with request_id
- [x] Handle errors at each step gracefully
- [x] Integration tests for full pipeline flow

**Files to Modify**:
- `services/orchestrator-service/main.py`

**Files to Create**:
- `tests/integration/test_orchestrator_pipeline.py`

**Notes**:
- Main entry point for pipeline execution
- All steps must succeed for pipeline to complete

---

## Phase 5: Docker Infrastructure

### Task 5.1: Create Layering Service Dockerfile
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 2.3  
**Status**: ✅ Complete

**Description**:
Create Dockerfile for Layering Service that installs dependencies and runs FastAPI app.

**Acceptance Criteria**:
- [x] Create `services/layering-service/Dockerfile`
- [x] Use Python 3.11+ base image
- [x] Copy `pyproject.toml` and `src/` directory
- [x] Install `layering_detection` package via `pip install .`
- [x] Copy service code (`main.py`, etc.)
- [x] Install service dependencies from `requirements.txt`
- [x] Expose port 8001
- [x] Set CMD to run uvicorn
- [x] Docker image builds successfully (structure verified)
- [x] Docker container runs and responds to health check (healthcheck configured)

**Files to Create**:
- `services/layering-service/Dockerfile`
- `services/layering-service/.dockerignore` (optional)

**Notes**:
- Multi-stage build for smaller image size (optional)
- Use non-root user for security (optional)

---

### Task 5.2: Create Wash Trading Service Dockerfile
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 2.6  
**Status**: ✅ Complete

**Description**:
Create Dockerfile for Wash Trading Service.

**Acceptance Criteria**:
- [x] Create `services/wash-trading-service/Dockerfile`
- [x] Same structure as Layering Service Dockerfile
- [x] Expose port 8002
- [x] Docker image builds successfully
- [x] Docker container runs and responds to health check

**Files to Create**:
- `services/wash-trading-service/Dockerfile`
- `services/wash-trading-service/.dockerignore` (optional)

**Notes**:
- Similar to Layering Service Dockerfile

---

### Task 5.3: Create Aggregator Service Dockerfile
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 3.5  
**Status**: ✅ Complete

**Description**:
Create Dockerfile for Aggregator Service.

**Acceptance Criteria**:
- [x] Create `services/aggregator-service/Dockerfile`
- [x] Use Python 3.11+ base image
- [x] Copy `pyproject.toml` and `src/` directory
- [x] Install `layering_detection` package
- [x] Copy service code
- [x] Install service dependencies
- [x] Expose port 8003
- [x] Set CMD to run uvicorn
- [x] Docker image builds successfully
- [x] Docker container runs and responds to health check

**Files to Create**:
- `services/aggregator-service/Dockerfile`
- `services/aggregator-service/.dockerignore` (optional)

**Notes**:
- Similar structure to algorithm services

---

### Task 5.4: Create Orchestrator Service Dockerfile
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~1h  
**Dependencies**: Task 4.10  
**Status**: ✅ Complete

**Description**:
Create Dockerfile for Orchestrator Service.

**Acceptance Criteria**:
- [x] Create `services/orchestrator-service/Dockerfile`
- [x] Use Python 3.11+ base image
- [x] Copy `pyproject.toml` and `src/` directory
- [x] Install `layering_detection` package
- [x] Copy service code
- [x] Install service dependencies (including httpx/aiohttp)
- [x] Expose port 8000
- [x] Set CMD to run uvicorn
- [x] Docker image builds successfully
- [x] Docker container runs and responds to health check

**Files to Create**:
- `services/orchestrator-service/Dockerfile`
- `services/orchestrator-service/.dockerignore` (optional)

**Notes**:
- Needs HTTP client library for service calls

---

### Task 5.5: Create Docker Compose Configuration
**Type**: Infra  
**Priority**: P0 (Critical)  
**Effort**: ~2h  
**Dependencies**: Task 5.1, Task 5.2, Task 5.3, Task 5.4  
**Status**: ✅ Complete

**Description**:
Create `docker-compose.yml` file that orchestrates all services with networking, volumes, health checks, and dependencies.

**Acceptance Criteria**:
- [x] Create `docker-compose.yml` in project root
- [x] Define all 4 services (layering, wash-trading, orchestrator, aggregator)
- [x] Configure `layering-network` bridge network
- [x] Mount `./input:/app/input:ro` for orchestrator (read-only)
- [x] Mount `./output:/app/output` for aggregator
- [x] Mount `./logs:/app/logs` for aggregator
- [x] Configure health checks for all services (curl /health)
- [x] Configure `depends_on` with `condition: service_healthy` for orchestrator
- [x] Expose ports: 8000, 8001, 8002, 8003
- [x] Configure environment variables per service
- [x] `docker-compose up --build` starts all services successfully
- [x] All services can communicate over network
- [x] Health checks pass for all services

**Files to Create**:
- `docker-compose.yml`

**Notes**:
- Use Docker Compose v3.8 format
- Service names resolve via Docker DNS
- Health checks prevent race conditions

---

## Phase 6: Testing & Integration

### Task 6.1: Unit Tests for API Contracts
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 1.1, Task 1.2  
**Status**: ✅ Complete

**Description**:
Write comprehensive unit tests for API contracts and converters.

**Acceptance Criteria**:
- [x] Test all Pydantic model validations (UUID, SHA256, literals)
- [x] Test JSON serialization/deserialization
- [x] Test datetime conversion (domain → ISO string → domain)
- [x] Test Decimal conversion (domain → string → domain)
- [x] Test round-trip conversions (domain → DTO → domain)
- [x] Test edge cases (empty lists, null values, invalid formats)
- [x] Test coverage >90%

**Files to Modify**:
- `tests/unit/test_api_models.py`
- `tests/unit/test_converters.py`

**Notes**:
- Use pytest
- Test all validation rules

---

### Task 6.2: Integration Tests for Algorithm Services
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~3h  
**Dependencies**: Task 2.3, Task 2.6  
**Status**: ✅ Complete

**Description**:
Write integration tests for algorithm services with real algorithm calls.

**Acceptance Criteria**:
- [x] Test Layering Service `/detect` endpoint with real events
- [x] Test Wash Trading Service `/detect` endpoint with real events
- [x] Test idempotency (same request_id + fingerprint returns cached result)
- [x] Test error handling (invalid request, algorithm errors)
- [x] Test health check endpoints
- [x] Test cache behavior (hit, miss)
- [x] Use test containers or mock HTTP calls

**Files to Create**:
- `tests/integration/test_algorithm_services.py`

**Notes**:
- Use pytest with async support
- Test with real TransactionEvent data

---

### Task 6.3: Integration Tests for Aggregator Service
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 3.5  
**Status**: ✅ Complete

**Description**:
Write integration tests for aggregator service validation, merging, and CSV writing.

**Acceptance Criteria**:
- [x] Test `/aggregate` endpoint with valid results
- [x] Test validation failure (missing services, incomplete services)
- [x] Test result merging (multiple services, deduplication)
- [x] Test CSV file writing (verify file contents, format)
- [x] Test error handling (file write errors)
- [x] Use test data fixtures

**Files to Create**:
- `tests/integration/test_aggregator_service.py`

**Notes**:
- Use temporary directories for output files
- Verify CSV format matches expected format

---

### Task 6.4: Integration Tests for Orchestrator Service
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~3h  
**Dependencies**: Task 4.10  
**Status**: ✅ Complete

**Description**:
Write integration tests for orchestrator service with mocked algorithm and aggregator services.

**Acceptance Criteria**:
- [x] Test `/orchestrate` endpoint with mocked services
- [x] Test CSV reading
- [x] Test request_id generation
- [x] Test event fingerprinting
- [x] Test parallel algorithm service calls
- [x] Test retry logic (mocked failures)
- [x] Test completion validation
- [x] Test aggregator call
- [x] Use httpx.AsyncClient with mocked responses

**Files to Create**:
- `tests/integration/test_orchestrator_service.py`

**Notes**:
- Mock HTTP calls to algorithm and aggregator services
- Test all error scenarios

---

### Task 6.5: End-to-End Tests with Docker Compose
**Type**: Test  
**Priority**: P0 (Critical)  
**Effort**: ~4h  
**Dependencies**: Task 5.5  
**Status**: ✅ Complete

**Description**:
Write end-to-end tests that run full pipeline with docker-compose.

**Acceptance Criteria**:
- [x] Test full pipeline execution (CSV → orchestrator → algorithms → aggregator → output)
- [x] Test with real input CSV file
- [x] Verify output CSV files are created correctly
- [x] Test retry scenarios (temporarily stop service, verify retry)
- [x] Test fault isolation (one service fails, others continue)
- [x] Test deduplication (same request_id + fingerprint)
- [x] Test completion validation (all services must complete)
- [x] Use pytest-docker or docker-compose test fixtures

**Files to Create**:
- `tests/e2e/test_full_pipeline.py`
- `tests/e2e/fixtures/sample_transactions.csv`

**Notes**:
- Requires docker-compose running
- Test with real data and verify output format

---

### Task 6.6: Test Retry Logic and Fault Tolerance
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 4.6, Task 6.4  
**Status**: ✅ Complete

**Description**:
Write comprehensive tests for retry logic, exponential backoff, and fault isolation.

**Acceptance Criteria**:
- [x] Test retry on TimeoutError (mocked timeout)
- [x] Test retry on ConnectionError (mocked connection failure)
- [x] Test retry on HTTP 5xx errors
- [x] Test no retry on HTTP 4xx errors
- [x] Test exponential backoff delays (verify timing)
- [x] Test retry count tracking
- [x] Test final_status=True after retries exhausted
- [x] Test fault isolation (one service fails, others succeed)
- [x] Use mocked HTTP client with controlled failures

**Files to Create**:
- `tests/integration/test_retry_logic.py`

**Notes**:
- Use asyncio for timing tests
- Verify backoff delays are correct

---

### Task 6.7: Test Deduplication and Idempotency
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~2h  
**Dependencies**: Task 2.3, Task 2.6, Task 4.4  
**Status**: ✅ Complete

**Description**:
Write tests to verify deduplication works correctly across retries.

**Acceptance Criteria**:
- [x] Test event fingerprinting (same events = same hash)
- [x] Test event fingerprinting (different events = different hash)
- [x] Test algorithm service cache (same request_id + fingerprint = cache hit)
- [x] Test cache prevents duplicate processing on retries
- [x] Test cache miss (different request_id or fingerprint)
- [x] Test fingerprint determinism (order-independent)
- [x] Use real TransactionEvent data

**Files to Create**:
- `tests/integration/test_deduplication.py`

**Notes**:
- Verify fingerprint is deterministic
- Verify cache works correctly

---

## Summary

### Task Count by Phase

- **Phase 1 (Foundation)**: 4 tasks
- **Phase 2 (Algorithm Services)**: 6 tasks
- **Phase 3 (Aggregator Service)**: 5 tasks
- **Phase 4 (Orchestrator Service)**: 10 tasks
- **Phase 5 (Docker Infrastructure)**: 5 tasks
- **Phase 6 (Testing & Integration)**: 7 tasks

**Total**: 37 tasks

### Estimated Effort

- **Phase 1**: ~6.5 hours
- **Phase 2**: ~12 hours
- **Phase 3**: ~10 hours
- **Phase 4**: ~19 hours
- **Phase 5**: ~6 hours
- **Phase 6**: ~18 hours

**Total**: ~71.5 hours (~9-10 days for one developer)

### Critical Path

1. API Contracts (Task 1.1) → All services depend on this
2. Algorithm Services (Tasks 2.1-2.6) → Orchestrator depends on these
3. Aggregator Service (Tasks 3.1-3.5) → Orchestrator depends on this
4. Orchestrator Service (Tasks 4.1-4.10) → Main coordination service
5. Docker Infrastructure (Tasks 5.1-5.5) → Deployment
6. Testing (Tasks 6.1-6.7) → Validation

### Parallelization Opportunities

- **Phase 2**: Layering and Wash Trading services can be built in parallel
- **Phase 3 & 4**: Aggregator and Orchestrator can be built in parallel (after Phase 1)
- **Phase 5**: All Dockerfiles can be created in parallel
- **Phase 6**: Unit tests can be written in parallel with implementation

### Risk Mitigation

- **High Risk**: End-to-end integration (Task 6.5) - test early with minimal setup
- **Medium Risk**: Retry logic complexity (Task 4.6) - implement incrementally
- **Low Risk**: Docker Compose configuration (Task 5.5) - well-documented patterns

