# Aggregator Service

Microservice for validating completion, merging results from algorithm services, and writing output CSV files.

## Overview

The Aggregator Service is a FastAPI-based microservice that validates that all expected algorithm services completed successfully, merges their results, deduplicates suspicious sequences, and writes output CSV files. It ensures data integrity by validating completion before writing results.

## Features

- **Health Check Endpoint**: `GET /health` - Returns service health status
- **Aggregation Endpoint**: `POST /aggregate` - Validates completion and aggregates results (to be implemented in Task 3.2)
- **Completion Validation**: Ensures all expected services completed before processing
- **Result Merging**: Combines results from multiple algorithm services
- **CSV Writing**: Writes `suspicious_accounts.csv` and `detections.csv` to output directory
- **Structured Logging**: Includes request_id support for distributed tracing
- **Docker-Ready**: Configured for containerized deployment

## API Endpoints

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "aggregator-service"
}
```

### `GET /`

Root endpoint with service information.

**Response:**
```json
{
  "service": "aggregator-service",
  "version": "1.0.0",
  "status": "running",
  "output_dir": "/app/output",
  "validation_strict": true
}
```

### `POST /aggregate`

Aggregate results from algorithm services (to be implemented in Task 3.2).

**Request:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "expected_services": ["layering", "wash_trading"],
  "results": [
    {
      "request_id": "...",
      "service_name": "layering",
      "status": "success",
      "final_status": true,
      "results": [...],
      "error": null
    },
    ...
  ]
}
```

**Response:**
```json
{
  "status": "completed",
  "merged_count": 42,
  "failed_services": [],
  "error": null
}
```

## Configuration

The service uses environment variables for configuration:

- `PORT`: Service port (default: 8003)
- `OUTPUT_DIR`: Output directory for CSV files (default: `/app/output`)
- `LOGS_DIR`: Logs directory (default: `/app/logs`)
- `VALIDATION_STRICT`: Fail fast on validation errors (default: `true`)
- `ALLOW_PARTIAL_RESULTS`: Allow merging if some services failed (default: `false`)
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
uvicorn main:app --port 8003

# Or run main.py directly
python main.py
```

The service will start on port 8003 (or the port specified in the `PORT` environment variable).

## Docker

The service is designed to run in Docker. See the parent project's `docker-compose.yml` for orchestration.

### Building the Docker Image

Build from the project root directory:

```bash
docker build -f services/aggregator-service/Dockerfile -t aggregator-service .
```

### Running the Container

```bash
# Run in detached mode
docker run --rm -d -p 8003:8003 --name aggregator-test aggregator-service

# Verify health endpoint (PowerShell)
Start-Sleep -Seconds 3
curl http://localhost:8003/health

# Check logs
docker logs aggregator-test

# Stop and remove container
docker stop aggregator-test
```

### Testing the Container

Use the provided test script (PowerShell):

```powershell
.\services\aggregator-service\test-container.ps1
```

Or manually verify:

```bash
# Start container
docker run --rm -d -p 8003:8003 --name aggregator-test aggregator-service

# Wait for startup, then test health endpoint
Start-Sleep -Seconds 3
curl http://localhost:8003/health

# Expected response: {"status":"healthy","service":"aggregator-service"}

# Cleanup
docker stop aggregator-test
```

## Architecture

- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Logging**: Shared logging utilities with request_id support
- **Configuration**: Service-specific config utilities (12-factor app)

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `layering_detection`: Core detection algorithms and domain models (from parent project)
- `services.shared`: Shared utilities (API models, logging, config)

## Development

### Project Structure

```
aggregator-service/
├── main.py              # FastAPI application
├── config.py            # Service-specific configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Related Services

- **Orchestrator Service**: Coordinates the detection pipeline and sends results to aggregator
- **Layering Service**: Detects layering manipulation patterns
- **Wash Trading Service**: Detects wash trading patterns

## Notes

- The service uses shared logging utilities that include request_id support for distributed tracing
- All configuration follows 12-factor app principles (environment variables only)
- The service validates completion before writing results to ensure data integrity
- Output CSV files match the format of the monolithic implementation for compatibility

