# Feature: Docker Compose Infrastructure

## Overview

Docker Compose configuration for orchestrating all microservices, networking, volumes, and health checks. Enables local development and production deployment.

## Requirements

- [ ] Define Docker Compose file with all services
- [ ] Configure service networking (layering-network)
- [ ] Mount input volume (read-only) for orchestrator
- [ ] Mount output volume for aggregator
- [ ] Mount logs volume for aggregator
- [ ] Configure health checks for all services
- [ ] Set up service dependencies (depends_on with health conditions)
- [ ] Expose service ports for external access
- [ ] Configure environment variables per service
- [ ] Build context for each service Dockerfile

## Acceptance Criteria

- [ ] `docker-compose.yml` defines all 4 services
- [ ] Services communicate over `layering-network`
- [ ] Orchestrator has read-only access to `./input` directory
- [ ] Aggregator has write access to `./output` directory
- [ ] Aggregator has write access to `./logs` directory
- [ ] All services have health check endpoints configured
- [ ] Orchestrator depends on algorithm services (healthy condition)
- [ ] Orchestrator depends on aggregator (healthy condition)
- [ ] Ports exposed: 8000 (orchestrator), 8001 (layering), 8002 (wash trading), 8003 (aggregator)
- [ ] Environment variables configured per service
- [ ] `docker-compose up --build` starts all services successfully

## Technical Details

### Docker Compose Structure

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
    # Similar configuration

  orchestrator-service:
    # Similar configuration
    volumes:
      - ./input:/app/input:ro
    depends_on:
      layering-service:
        condition: service_healthy
      wash-trading-service:
        condition: service_healthy
      aggregator-service:
        condition: service_healthy

  aggregator-service:
    # Similar configuration
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs

networks:
  layering-network:
    driver: bridge

volumes:
  output:
  logs:
```

### Service Ports

- Orchestrator: 8000
- Layering Service: 8001
- Wash Trading Service: 8002
- Aggregator Service: 8003

### Volume Mounts

- `./input:/app/input:ro` - Read-only input CSV files
- `./output:/app/output` - Write output CSV files
- `./logs:/app/logs` - Write log files

### Health Checks

- All services implement `/health` endpoint
- Health check: `curl -f http://localhost:PORT/health`
- Interval: 10 seconds
- Timeout: 5 seconds
- Retries: 3

### Service Dependencies

- Orchestrator waits for all services to be healthy
- Prevents race conditions during startup
- Uses `depends_on` with `condition: service_healthy`

### Environment Variables

**Orchestrator**:
- `PORT=8000`
- `LAYERING_SERVICE_URL=http://layering-service:8001`
- `WASH_TRADING_SERVICE_URL=http://wash-trading-service:8002`
- `AGGREGATOR_SERVICE_URL=http://aggregator-service:8003`
- `MAX_RETRIES=3`
- `ALGORITHM_TIMEOUT_SECONDS=30`

**Aggregator**:
- `PORT=8003`
- `OUTPUT_DIR=/app/output`
- `LOGS_DIR=/app/logs`
- `VALIDATION_STRICT=true`

## Implementation Notes

- Use Docker Compose v3.8 format
- Service names resolve via Docker DNS
- Health checks prevent premature connections
- Volumes enable data persistence
- Consider .dockerignore files for build optimization

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Service Health Checks](./FEATURE-service-health-checks.md)

## Questions/Clarifications

- Should we add resource limits (CPU/memory)?
- Should we use Docker secrets for sensitive config?
- Should we add docker-compose.override.yml for local dev?

