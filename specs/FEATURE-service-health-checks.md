# Feature: Service Health Checks

## Overview

Health check endpoints for all microservices to enable monitoring, service discovery, and dependency management in Docker Compose.

## Requirements

- [ ] Implement `GET /health` endpoint in all services
- [ ] Return HTTP 200 OK when service is ready
- [ ] Return HTTP 503 when service is not ready
- [ ] Include service name and status in response
- [ ] Configure Docker Compose health checks
- [ ] Health checks prevent premature service connections

## Acceptance Criteria

- [ ] All services expose `GET /health` endpoint
- [ ] Returns 200 OK with `{"status": "healthy"}` when ready
- [ ] Returns 503 Service Unavailable when not ready
- [ ] Response includes service name
- [ ] Docker Compose health checks configured per service
- [ ] Health check interval: 10 seconds
- [ ] Health check timeout: 5 seconds
- [ ] Health check retries: 3
- [ ] Services wait for dependencies to be healthy

## Technical Details

### Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "layering-service",  # or wash-trading, orchestrator, aggregator
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Docker Compose Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
  interval: 10s
  timeout: 5s
  retries: 3
```

### Service Readiness

**Ready when:**
- FastAPI app started
- Service can accept requests
- Dependencies initialized (if any)

**Not ready when:**
- Service starting up
- Dependencies unavailable
- Critical errors occurred

### Dependency Management

- Orchestrator waits for algorithm services to be healthy
- Orchestrator waits for aggregator to be healthy
- Prevents connection errors during startup

## Implementation Notes

- Simple health check (no deep dependency checks)
- Consider adding readiness vs liveness probes (future)
- Add metrics endpoint for detailed health (future)
- Health checks should be lightweight (fast response)

## Related Specs

- [Docker Infrastructure](./FEATURE-docker-infrastructure.md)
- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)

## Questions/Clarifications

- Should we add readiness vs liveness probes?
- Should health check verify dependencies?
- Should we add health check metrics?

