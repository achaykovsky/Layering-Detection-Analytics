# Orchestrator Service

Microservice for coordinating the detection pipeline: reading input CSV files, calling algorithm services in parallel, handling retries, and forwarding results to the aggregator.

## Overview

The Orchestrator Service is a FastAPI-based microservice that serves as the central coordination point for the entire detection pipeline. It reads input CSV files, generates request IDs and event fingerprints, calls algorithm services in parallel with retry logic, tracks completion status, and forwards results to the aggregator service.

## Features

- **Health Check Endpoint**: `GET /health` - Returns service health status
- **Pipeline Endpoint**: `POST /orchestrate` - Triggers the full detection pipeline (to be implemented in Task 4.10)
- **CSV Reading**: Reads input CSV files and parses TransactionEvent objects (to be implemented in Task 4.2)
- **Request ID Generation**: Generates unique UUID for each pipeline run (to be implemented in Task 4.3)
- **Event Fingerprinting**: Generates SHA256 hash for deduplication (to be implemented in Task 4.4)
- **Parallel Service Calls**: Calls algorithm services in parallel using asyncio (to be implemented in Task 4.5)
- **Retry Logic**: Implements exponential backoff retry logic (to be implemented in Task 4.6)
- **Completion Tracking**: Tracks final_status for all services (to be implemented in Task 4.7)
- **Structured Logging**: Includes request_id support for distributed tracing
- **Docker-Ready**: Configured for containerized deployment

## API Endpoints

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "orchestrator-service"
}
```

### `GET /`

Root endpoint with service information.

**Response:**
```json
{
  "service": "orchestrator-service",
  "version": "1.0.0",
  "status": "running",
  "input_dir": "/app/input",
  "layering_service_url": "http://layering-service:8001",
  "wash_trading_service_url": "http://wash-trading-service:8002",
  "aggregator_service_url": "http://aggregator-service:8003",
  "max_retries": 3,
  "timeout_seconds": 30
}
```

### `POST /orchestrate`

Trigger pipeline execution (to be implemented in Task 4.10).

**Request:**
```json
{
  "input_file": "transactions.csv"
}
```

**Response:**
```json
{
  "status": "completed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "sequences_found": 5
}
```

## Configuration

The service uses environment variables for configuration:

- `PORT`: Service port (default: 8000)
- `INPUT_DIR`: Input directory for CSV files (default: `/app/input`)
- `LAYERING_SERVICE_URL`: Layering Service URL (default: `http://layering-service:8001`)
- `WASH_TRADING_SERVICE_URL`: Wash Trading Service URL (default: `http://wash-trading-service:8002`)
- `AGGREGATOR_SERVICE_URL`: Aggregator Service URL (default: `http://aggregator-service:8003`)
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `ALGORITHM_TIMEOUT_SECONDS`: Timeout per service call (default: 30)
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: Log format - "JSON" for JSON logs, otherwise human-readable (default: human-readable)

## Running Locally

### Prerequisites

- Python 3.11+
- pip or poetry

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install the `layering_detection` package from the parent directory:
```bash
cd ../..
pip install -e .
```

### Running the Service

```bash
# Using uvicorn directly
uvicorn main:app --port 8000

# Or run main.py directly
python main.py
```

The service will start on port 8000 (or the port specified in the `PORT` environment variable).

## Docker

The service is designed to run in Docker. See the parent project's `docker-compose.yml` for orchestration.

## Architecture

- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **HTTP Client**: httpx for async HTTP calls
- **Logging**: Shared logging utilities with request_id support
- **Configuration**: Service-specific config utilities (12-factor app)

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `httpx`: Async HTTP client for calling other services
- `layering_detection`: Core detection algorithms and domain models (from parent project)
- `services.shared`: Shared utilities (API models, logging, config)

## Development

### Project Structure

```
orchestrator-service/
├── main.py              # FastAPI application
├── config.py            # Service-specific configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Related Services

- **Layering Service**: Detects layering manipulation patterns
- **Wash Trading Service**: Detects wash trading patterns
- **Aggregator Service**: Validates completion, merges results, and writes output files

## Notes

- The service uses shared logging utilities that include request_id support for distributed tracing
- All configuration follows 12-factor app principles (environment variables only)
- The service coordinates parallel algorithm execution for improved performance
- Retry logic with exponential backoff handles transient failures gracefully

