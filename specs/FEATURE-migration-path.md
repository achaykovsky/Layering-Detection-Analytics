# Feature: Migration Path from Monolith to Microservices

## Overview

Phased migration strategy from monolithic architecture to microservices. Ensures backward compatibility and smooth transition without disrupting existing functionality.

## Requirements

- [ ] Phase 1: Extract algorithm services
- [ ] Phase 2: Implement orchestrator
- [ ] Phase 3: Implement aggregator
- [ ] Phase 4: Docker Compose setup
- [ ] Maintain backward compatibility with existing CLI
- [ ] Keep monolithic architecture functional during transition
- [ ] Test each phase before proceeding
- [ ] Document migration steps

## Acceptance Criteria

- [ ] Phase 1: Algorithm services extracted and tested independently
- [ ] Phase 2: Orchestrator coordinates algorithm services
- [ ] Phase 3: Aggregator validates and merges results
- [ ] Phase 4: Docker Compose runs full pipeline
- [ ] Existing `main.py` CLI still works (backward compatible)
- [ ] Monolithic architecture remains functional
- [ ] Both architectures produce identical output
- [ ] Migration can be done incrementally
- [ ] Rollback possible at any phase

## Technical Details

### Phase 1: Service Extraction

1. Create `services/layering-service/` directory
2. Extract `LayeringDetectionAlgorithm` to service
3. Create FastAPI app with `/detect` endpoint
4. Create Dockerfile
5. Test service independently
6. Repeat for wash-trading-service

**Deliverables**:
- Two algorithm services running independently
- Dockerfiles for each service
- Health check endpoints

### Phase 2: Orchestration

1. Create `services/orchestrator-service/` directory
2. Implement CSV reading (reuse existing code)
3. Implement parallel algorithm service calls
4. Implement retry logic
5. Create FastAPI app with `/orchestrate` endpoint
6. Test orchestrator with algorithm services

**Deliverables**:
- Orchestrator service coordinating algorithm services
- Retry logic implemented
- Completion tracking implemented

### Phase 3: Aggregation

1. Create `services/aggregator-service/` directory
2. Implement completion validation
3. Implement result merging
4. Implement CSV writing (reuse existing code)
5. Create FastAPI app with `/aggregate` endpoint
6. Test full pipeline (orchestrator → aggregator)

**Deliverables**:
- Aggregator service validating and merging results
- Output files written correctly
- Validation logic tested

### Phase 4: Docker Compose

1. Create `docker-compose.yml`
2. Configure networking
3. Configure volumes
4. Configure health checks
5. Configure dependencies
6. Test end-to-end pipeline

**Deliverables**:
- Full docker-compose setup
- All services communicating correctly
- End-to-end pipeline working

### Backward Compatibility

- Keep existing `main.py` as CLI wrapper
- `main.py` can call orchestrator service (HTTP or direct import)
- Same command-line interface
- Same output format
- Users can continue using `python main.py`

## Implementation Notes

- Test each phase thoroughly before proceeding
- Keep monolithic code until migration complete
- Use feature flags if needed (future)
- Document rollback procedures
- Consider parallel running (monolith + microservices) for validation

## Rollback Strategy

- Each phase can be rolled back independently
- Keep monolithic code until migration verified
- Docker Compose can be removed without affecting monolith
- Services can be disabled individually

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)

## Questions/Clarifications

- Should we run both architectures in parallel for validation?
- What is the timeline for each phase?
- Should we use feature flags for gradual rollout?

