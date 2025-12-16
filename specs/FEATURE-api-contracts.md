# Feature: API Contracts & Data Models

## Overview

Defines Pydantic models for all inter-service API contracts. Ensures type-safe serialization, validation, and clear separation between domain models and API DTOs.

## Requirements

- [ ] Define Pydantic models for all request/response DTOs
- [ ] Convert between domain models and Pydantic models at service boundaries
- [ ] Validate all request data using Pydantic
- [ ] Handle `datetime` and `Decimal` serialization correctly
- [ ] Ensure JSON compatibility for all models
- [ ] Document all API contracts
- [ ] Version API models (future consideration)

## Acceptance Criteria

- [ ] `AlgorithmRequest` model defined with validation
- [ ] `AlgorithmResponse` model defined with validation
- [ ] `AggregateRequest` model defined with validation
- [ ] `AggregateResponse` model defined with validation
- [ ] `TransactionEvent` Pydantic model for API serialization
- [ ] `SuspiciousSequence` Pydantic model for API serialization
- [ ] Conversion functions: domain → Pydantic, Pydantic → domain
- [ ] All models serialize to/from JSON correctly
- [ ] `datetime` serialized as ISO format strings
- [ ] `Decimal` serialized as strings (preserve precision)
- [ ] FastAPI automatically validates requests/responses

## Technical Details

### Request/Response Models

**AlgorithmRequest** (Orchestrator → Algorithm Service):
```python
class AlgorithmRequest(BaseModel):
    request_id: str  # UUID
    event_fingerprint: str  # SHA256 hash
    events: List[TransactionEventDTO]  # Pydantic model
```

**AlgorithmResponse** (Algorithm Service → Orchestrator):
```python
class AlgorithmResponse(BaseModel):
    request_id: str
    service_name: str  # "layering" or "wash_trading"
    status: Literal["success", "failure", "timeout"]
    results: Optional[List[SuspiciousSequenceDTO]] = None
    error: Optional[str] = None
```

**AggregateRequest** (Orchestrator → Aggregator):
```python
class AggregateRequest(BaseModel):
    request_id: str
    expected_services: List[str]
    results: List[AlgorithmResponse]
```

**AggregateResponse** (Aggregator → Orchestrator):
```python
class AggregateResponse(BaseModel):
    status: Literal["completed", "validation_failed"]
    merged_count: int
    failed_services: List[str]
    error: Optional[str] = None
```

### Domain Model Conversion

**TransactionEvent**:
- Domain: `dataclass` with `datetime`, `Decimal`
- DTO: Pydantic model with ISO string timestamps, string prices

**SuspiciousSequence**:
- Domain: `dataclass` with `datetime`, `List[TransactionEvent]`
- DTO: Pydantic model with ISO strings, nested DTOs

### Serialization Strategy

- `datetime`: ISO format strings (`datetime.isoformat()`)
- `Decimal`: String representation (preserve precision)
- `List`: JSON arrays
- `Optional`: `null` in JSON

### Validation Rules

- `request_id`: UUID format
- `event_fingerprint`: SHA256 hexdigest (64 chars)
- `service_name`: Enum or literal values
- `status`: Literal values only
- `events`: Non-empty list
- `results`: Optional, validated if present

## Implementation Notes

- Use Pydantic v2 for modern features
- Create separate DTO modules per service
- Conversion functions in service boundary layers
- FastAPI automatically handles Pydantic serialization
- Consider API versioning (v1, v2) for future changes

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Domain Models](./FEATURE-domain-models.md)

## Questions/Clarifications

- Should we version APIs (e.g., `/v1/detect`)?
- Should we add OpenAPI/Swagger documentation?
- What is the maximum request/response size?

