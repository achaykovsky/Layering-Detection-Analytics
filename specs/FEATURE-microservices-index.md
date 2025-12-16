# Microservices Architecture - Feature Specs Index

## Overview

This document indexes all feature specifications for the microservices architecture migration. Each spec covers a specific component or concern of the distributed system.

## Architecture Document

- [ARCHITECTURE-MICROSERVICES.md](./ARCHITECTURE-MICROSERVICES.md) - Complete architecture documentation

## Core Services

### 1. [Orchestrator Service](./FEATURE-orchestrator-service.md)
**Purpose**: Central coordination service that manages pipeline execution, algorithm service calls, retries, and fault tolerance.

**Key Features**:
- CSV input reading
- Request ID generation
- Event fingerprinting
- Parallel algorithm service calls
- Retry logic with exponential backoff
- Completion tracking

**Status**: 🚧 Pending implementation

### 2. [Algorithm Services](./FEATURE-algorithm-services.md)
**Purpose**: Independent detection microservices (Layering and Wash Trading) implementing specific algorithms.

**Key Features**:
- Stateless design
- Idempotent operations
- Result caching
- Independent scaling
- Fault isolation

**Status**: 🚧 Pending implementation

### 3. [Aggregator Service](./FEATURE-aggregator-service.md)
**Purpose**: Validates completion, merges results from all algorithm services, and writes output CSV files.

**Key Features**:
- Completion validation
- Result merging
- CSV writing
- Error handling

**Status**: 🚧 Pending implementation

## Cross-Cutting Concerns

### 4. [Retry & Fault Tolerance](./FEATURE-retry-fault-tolerance.md)
**Purpose**: Implements retry logic with exponential backoff and fault isolation.

**Key Features**:
- Exponential backoff (2^attempt seconds)
- Maximum retries (configurable)
- Timeout handling
- Fault isolation

**Status**: 🚧 Pending implementation

### 5. [Deduplication Strategy](./FEATURE-deduplication.md)
**Purpose**: Prevents duplicate processing through event fingerprinting and result caching.

**Key Features**:
- SHA256 event fingerprinting
- Result caching by (request_id, event_fingerprint)
- Idempotent operations

**Status**: 🚧 Pending implementation

### 6. [Completion Validation](./FEATURE-completion-validation.md)
**Purpose**: Ensures all services completed before aggregating results.

**Key Features**:
- Final status tracking
- Orchestrator validation
- Aggregator validation
- Fail-fast on incomplete results

**Status**: 🚧 Pending implementation

### 7. [API Contracts](./FEATURE-api-contracts.md)
**Purpose**: Defines Pydantic models for all inter-service API contracts.

**Key Features**:
- Type-safe serialization
- Request/response validation
- Domain model conversion
- JSON compatibility

**Status**: 🚧 Pending implementation

## Infrastructure

### 8. [Docker Infrastructure](./FEATURE-docker-infrastructure.md)
**Purpose**: Docker Compose configuration for orchestrating all microservices.

**Key Features**:
- Service definitions
- Networking configuration
- Volume mounts
- Health checks
- Dependencies

**Status**: 🚧 Pending implementation

### 9. [Service Health Checks](./FEATURE-service-health-checks.md)
**Purpose**: Health check endpoints for monitoring and dependency management.

**Key Features**:
- `/health` endpoints
- Docker Compose health checks
- Service readiness

**Status**: 🚧 Pending implementation

### 10. [Logging & Observability](./FEATURE-logging-observability.md)
**Purpose**: Structured logging with request_id tracing across services.

**Key Features**:
- Structured logging
- Request ID tracing
- Error logging
- Docker log aggregation

**Status**: 🚧 Pending implementation

## Testing & Migration

### 11. [Testing Strategy](./FEATURE-testing-strategy.md)
**Purpose**: Comprehensive testing strategy for microservices architecture.

**Key Features**:
- Unit tests
- Integration tests
- End-to-end tests
- Fault tolerance testing

**Status**: 🚧 Pending implementation

### 12. [Migration Path](./FEATURE-migration-path.md)
**Purpose**: Phased migration strategy from monolith to microservices.

**Key Features**:
- 4-phase migration plan
- Backward compatibility
- Incremental rollout
- Rollback strategy

**Status**: 🚧 Pending implementation

## Implementation Order

Recommended implementation order:

1. **API Contracts** - Define interfaces first
2. **Algorithm Services** - Extract and test independently
3. **Docker Infrastructure** - Set up basic service containers
4. **Service Health Checks** - Enable dependency management
5. **Deduplication Strategy** - Implement idempotency
6. **Retry & Fault Tolerance** - Add resilience
7. **Orchestrator Service** - Coordinate services
8. **Completion Validation** - Ensure data integrity
9. **Aggregator Service** - Merge and write results
10. **Logging & Observability** - Add tracing
11. **Testing Strategy** - Comprehensive test coverage
12. **Migration Path** - Execute phased migration

## Related Specs

### Existing Feature Specs (Monolithic)
- [Algorithm Registry](./FEATURE-algorithm-registry.md)
- [Layering Detection](./FEATURE-layering-detection.md)
- [Wash Trading Detection](./FEATURE-wash-trading-detection.md)
- [Domain Models](./FEATURE-domain-models.md)
- [Transaction I/O](./FEATURE-transaction-io.md)
- [Pipeline Orchestration](./FEATURE-pipeline-orchestration.md)
- [Security Utilities](./FEATURE-security-utilities.md)
- [Performance Optimization](./FEATURE-performance-optimization.md)
- [Detection Logging](./FEATURE-detection-logging.md)

## Status Legend

- ✅ Complete
- 🚧 In Progress
- ⏳ Pending
- ❌ Blocked

## Questions & Clarifications

See individual spec files for component-specific questions. General architecture questions should be addressed in [ARCHITECTURE-MICROSERVICES.md](./ARCHITECTURE-MICROSERVICES.md).

