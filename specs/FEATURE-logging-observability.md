# Feature: Logging & Observability

## Overview

Structured logging strategy with `request_id` tracing across all services. Enables distributed tracing, debugging, and monitoring of the microservices pipeline.

## Requirements

- [ ] Structured logging to stdout/stderr
- [ ] Include `request_id` in all log messages
- [ ] Log level configuration per service
- [ ] Log service name in all messages
- [ ] Log request/response details (sanitized)
- [ ] Log errors with stack traces
- [ ] Log retry attempts and backoff delays
- [ ] Docker aggregates logs automatically
- [ ] Consider JSON format for structured logs (optional)

## Acceptance Criteria

- [ ] All services log to stdout/stderr
- [ ] All log messages include `request_id` when available
- [ ] Log format: `{"request_id": "...", "level": "...", "message": "...", "service": "..."}`
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- [ ] Request/response logging (sanitized, no PII)
- [ ] Error logging includes stack traces
- [ ] Retry attempts logged with attempt number and backoff
- [ ] Docker Compose aggregates logs from all services
- [ ] Logs can be filtered by `request_id`

## Technical Details

### Logging Format

```python
import logging
import json
from datetime import datetime

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(record, 'request_id', 'N/A')
        return True

logger = logging.getLogger(__name__)
logger.addFilter(RequestIdFilter())

# Usage
logger.info("Processing request", extra={"request_id": request_id})
```

### Structured Logging (JSON)

```python
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": "layering-service",
            "request_id": getattr(record, 'request_id', 'N/A'),
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages (retries, partial failures)
- **ERROR**: Error messages (service failures, validation errors)
- **CRITICAL**: Critical errors (pipeline failures)

### Logging Points

**Orchestrator**:
- Pipeline start/end with `request_id`
- Service call start/end
- Retry attempts with backoff
- Completion validation
- Aggregator call

**Algorithm Services**:
- Request received with `request_id`
- Cache hit/miss
- Detection start/end
- Results count
- Errors

**Aggregator**:
- Aggregation start with `request_id`
- Validation results
- Merge counts
- File write completion
- Errors

## Implementation Notes

- Use Python `logging` module
- Docker handles log aggregation automatically
- Consider log rotation for production
- Sanitize PII in logs (HIPAA/GDPR compliance)
- Consider centralized logging (ELK, Loki) for production

## Future Enhancements

- Distributed tracing (OpenTelemetry)
- Metrics endpoint (Prometheus format)
- Log aggregation service (ELK stack)
- Alerting on error rates

## Related Specs

- [Orchestrator Service](./FEATURE-orchestrator-service.md)
- [Algorithm Services](./FEATURE-algorithm-services.md)
- [Aggregator Service](./FEATURE-aggregator-service.md)
- [Security Utilities](./FEATURE-security-utilities.md)

## Questions/Clarifications

- Should we use JSON logging format?
- Should we add distributed tracing (OpenTelemetry)?
- What is the log retention policy?

