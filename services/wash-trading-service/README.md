# Wash Trading Detection Service

Microservice for detecting suspicious wash trading patterns in transaction data.

## Overview

The Wash Trading Detection Service is a FastAPI-based microservice that detects suspicious wash trading manipulation patterns. Wash trading is a market manipulation technique where traders execute buy and sell orders for the same security to create artificial trading volume and activity.

## Features

- **Health Check Endpoint**: `GET /health` - Returns service health status
- **Detection Endpoint**: `POST /detect` - Detects suspicious wash trading sequences (to be implemented in Task 2.5)
- **Structured Logging**: Includes request_id support for distributed tracing
- **Docker-Ready**: Configured for containerized deployment

## API Endpoints

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "wash-trading-service"
}
```

### `GET /`

Root endpoint with service information.

**Response:**
```json
{
  "service": "wash-trading-service",
  "version": "1.0.0",
  "status": "running"
}
```

## Configuration

The service uses environment variables for configuration:

- `PORT`: Service port (default: 8002)
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
uvicorn main:app --port 8002

# Or run main.py directly
python main.py
```

The service will start on port 8002 (or the port specified in the `PORT` environment variable).

## Docker

The service is designed to run in Docker. See the parent project's `docker-compose.yml` for orchestration.

### Building the Docker Image

Build from the project root directory:

```bash
docker build -f services/wash-trading-service/Dockerfile -t wash-trading-service .
```

### Running the Container

```bash
# Run in detached mode
docker run --rm -d -p 8002:8002 --name wash-trading-test wash-trading-service

# Verify health endpoint (PowerShell)
Start-Sleep -Seconds 3
curl http://localhost:8002/health

# Check logs
docker logs wash-trading-test

# Stop and remove container
docker stop wash-trading-test
```

### Testing the Container

Use the provided test script (PowerShell):

```powershell
.\services\wash-trading-service\test-container.ps1
```

Or manually verify:

```bash
# Start container
docker run --rm -d -p 8002:8002 --name wash-trading-test wash-trading-service

# Wait for startup, then test health endpoint
Start-Sleep -Seconds 3
curl http://localhost:8002/health

# Expected response: {"status":"healthy","service":"wash-trading-service"}

# Cleanup
docker stop wash-trading-test
```

## Architecture

- **Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **Logging**: Shared logging utilities with request_id support
- **Configuration**: Shared configuration utilities (12-factor app)

## Dependencies

- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `layering_detection`: Core detection algorithms (from parent project)
- `services.shared`: Shared utilities (API models, logging, config)

## Development

### Project Structure

```
wash-trading-service/
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Related Services

- **Orchestrator Service**: Coordinates the detection pipeline
- **Layering Service**: Detects layering manipulation patterns
- **Aggregator Service**: Aggregates results from all detection services

## Notes

- The service uses shared logging utilities that include request_id support for distributed tracing
- All configuration follows 12-factor app principles (environment variables only)
- The service is stateless and can be horizontally scaled

