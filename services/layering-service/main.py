"""
Layering Detection Service.

FastAPI microservice for detecting suspicious layering patterns in transaction data.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path to import shared utilities
# In Docker, this will be /app, in local dev it's the project root
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request

from layering_detection.algorithms import LayeringDetectionAlgorithm
from services.shared.api_models import AlgorithmRequest, AlgorithmResponse, SuspiciousSequenceDTO
from services.shared.config import get_port
from services.shared.converters import (
    dto_to_suspicious_sequence,
    dto_to_transaction_event,
    suspicious_sequence_to_dto,
    transaction_event_to_dto,
)
from services.shared.logging import get_logger, setup_logging

# Setup logging
logger = setup_logging("layering-service", log_level="INFO")
service_logger = get_logger(__name__)

# In-memory cache for idempotent operations
# Key: (request_id, event_fingerprint) tuple
# Value: List of SuspiciousSequenceDTO results
_result_cache: dict[tuple[str, str], list[SuspiciousSequenceDTO]] = {}

# Create FastAPI app
app = FastAPI(
    title="Layering Detection Service",
    description="Microservice for detecting suspicious layering patterns",
    version="1.0.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with status and service name
    """
    logger.info("Health check requested")
    return {"status": "healthy", "service": "layering-service"}


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Service information
    """
    return {
        "service": "layering-service",
        "version": "1.0.0",
        "status": "running",
    }


@app.post("/detect", response_model=AlgorithmResponse)
async def detect(request: AlgorithmRequest, http_request: Request) -> AlgorithmResponse:
    """
    Detect suspicious layering patterns in transaction events.

    Accepts AlgorithmRequest with events and returns AlgorithmResponse with detected sequences.
    Always returns HTTP 200; check the 'status' field in the response body for success/failure.

    Args:
        request: AlgorithmRequest containing request_id, event_fingerprint, and events
        http_request: FastAPI request object (for logging context)

    Returns:
        AlgorithmResponse with status, results, and error (if any)

    Example:
        POST /detect
        {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_fingerprint": "a1b2c3d4...",
            "events": [...]
        }
    """
    request_id = request.request_id
    event_fingerprint = request.event_fingerprint
    
    # Check cache for idempotent operations
    cache_key = (request_id, event_fingerprint)
    
    if cache_key in _result_cache:
        # Cache hit - return cached result immediately
        cached_results = _result_cache[cache_key]
        service_logger.info(
            f"Cache hit: request_id={request_id}, event_fingerprint={event_fingerprint[:8]}..., "
            f"cached_results_count={len(cached_results)}",
            extra={"request_id": request_id},
        )
        return AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=cached_results,
            error=None,
        )
    
    # Cache miss - log and proceed with processing
    service_logger.info(
        f"Cache miss: request_id={request_id}, event_fingerprint={event_fingerprint[:8]}..., "
        f"events_count={len(request.events)}",
        extra={"request_id": request_id},
    )

    try:
        # Convert DTO events to domain models
        domain_events = [dto_to_transaction_event(dto) for dto in request.events]
        service_logger.debug(
            f"Converted {len(domain_events)} events to domain models",
            extra={"request_id": request_id},
        )

        # Call detection algorithm
        algorithm = LayeringDetectionAlgorithm()
        domain_sequences = algorithm.detect(domain_events)
        service_logger.info(
            f"Detection completed: found {len(domain_sequences)} suspicious sequences",
            extra={"request_id": request_id},
        )

        # Convert domain results back to DTOs
        result_dtos = [suspicious_sequence_to_dto(seq) for seq in domain_sequences]
        
        # Store result in cache for idempotency
        _result_cache[cache_key] = result_dtos
        service_logger.debug(
            f"Cached result: request_id={request_id}, event_fingerprint={event_fingerprint[:8]}..., "
            f"results_count={len(result_dtos)}",
            extra={"request_id": request_id},
        )

        # Return success response
        return AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=result_dtos,
            error=None,
        )

    except Exception as e:
        # Log error with request_id
        service_logger.error(
            f"Detection failed: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True,
        )

        # Return failure response (still HTTP 200)
        return AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="failure",
            results=None,
            error=str(e),
        )


if __name__ == "__main__":
    import uvicorn

    port = get_port(default=8001)
    logger.info(f"Starting Layering Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

