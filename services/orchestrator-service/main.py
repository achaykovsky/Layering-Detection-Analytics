"""
Orchestrator Service.

FastAPI microservice for coordinating the detection pipeline: reading input CSV,
calling algorithm services in parallel, handling retries, and forwarding results to aggregator.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path to import shared utilities
# In Docker, this will be /app, in local dev it's the project root
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

from services.shared.config import get_port, get_rate_limit_per_minute
from services.shared.error_sanitization import log_error_with_context, sanitize_error_message
from services.shared.logging import setup_logging
from services.shared.rate_limiting import RateLimitMiddleware
from services.shared.request_limits import RequestSizeLimitMiddleware

# Import service-specific config
# Note: orchestrator-service directory name has hyphen, so we import via path manipulation
import importlib.util
config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("orchestrator_config", config_path)
orchestrator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_config)
get_layering_service_url = orchestrator_config.get_layering_service_url
get_wash_trading_service_url = orchestrator_config.get_wash_trading_service_url
get_aggregator_service_url = orchestrator_config.get_aggregator_service_url
get_max_retries = orchestrator_config.get_max_retries
get_timeout_seconds = orchestrator_config.get_timeout_seconds
get_input_dir = orchestrator_config.get_input_dir
get_api_key = orchestrator_config.get_api_key

# Import orchestrator modules
reader_path = Path(__file__).parent / "reader.py"
spec = importlib.util.spec_from_file_location("orchestrator_reader", reader_path)
orchestrator_reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_reader)
read_input_csv = orchestrator_reader.read_input_csv

utils_path = Path(__file__).parent / "utils.py"
spec = importlib.util.spec_from_file_location("orchestrator_utils", utils_path)
orchestrator_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_utils)
generate_request_id = orchestrator_utils.generate_request_id
hash_events = orchestrator_utils.hash_events

path_validation_path = Path(__file__).parent / "path_validation.py"
spec = importlib.util.spec_from_file_location("orchestrator_path_validation", path_validation_path)
orchestrator_path_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_path_validation)
validate_input_path = orchestrator_path_validation.validate_input_path

orchestrator_path = Path(__file__).parent / "orchestrator.py"
spec = importlib.util.spec_from_file_location("orchestrator", orchestrator_path)
orchestrator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_module)
call_all_algorithm_services = orchestrator_module.call_all_algorithm_services
EXPECTED_SERVICES = orchestrator_module.EXPECTED_SERVICES

validation_path = Path(__file__).parent / "validation.py"
spec = importlib.util.spec_from_file_location("orchestrator_validation", validation_path)
orchestrator_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_validation)
validate_all_completed = orchestrator_validation.validate_all_completed

client_path = Path(__file__).parent / "client.py"
spec = importlib.util.spec_from_file_location("orchestrator_client", client_path)
orchestrator_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_client)
call_aggregator_service = orchestrator_client.call_aggregator_service

from services.shared.api_models import AggregateRequest, AggregateResponse, AlgorithmResponse

# Setup logging
logger = setup_logging("orchestrator-service", log_level="INFO")

# Create FastAPI app
app = FastAPI(
    title="Orchestrator Service",
    description="Microservice for coordinating the detection pipeline",
    version="1.0.0",
)

# Add request size limit middleware (10MB max)
app.add_middleware(RequestSizeLimitMiddleware, max_request_size=10 * 1024 * 1024)

# Add rate limiting middleware (100 requests/minute per IP, configurable)
rate_limit = get_rate_limit_per_minute(default=100)
app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit, excluded_paths={"/health"})

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """
    Verify API key from request header.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        API key if valid

    Raises:
        HTTPException: If API key is missing or invalid (HTTP 401)
    """
    expected_api_key = get_api_key()

    # If no API key configured, skip authentication (development only)
    if expected_api_key is None:
        logger.warning("API_KEY not configured - authentication disabled (development mode)")
        return ""

    # Check if API key is provided
    if api_key is None:
        logger.warning("API key missing from request")
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header.",
        )

    # Verify API key matches
    if api_key != expected_api_key:
        logger.warning(f"Invalid API key provided (first 8 chars: {api_key[:8]}...)")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    return api_key


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with status and service name
    """
    logger.info("Health check requested")
    return {"status": "healthy", "service": "orchestrator-service"}


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Minimal service information (service name, version, status only)
    """
    return {
        "service": "orchestrator-service",
        "version": "1.0.0",
        "status": "running",
    }


class OrchestrateRequest(BaseModel):
    """Request model for orchestrate endpoint."""

    input_file: str = Field(
        ...,
        max_length=255,
        description="Path to input CSV file (relative to INPUT_DIR or absolute). Filename must contain only alphanumeric characters, hyphens, underscores, and dots. No path separators allowed.",
    )

    @field_validator("input_file")
    @classmethod
    def validate_input_file(cls, v: str) -> str:
        """
        Validate input_file to prevent path injection attacks.

        Args:
            v: Input file path/name

        Returns:
            Validated filename

        Raises:
            ValueError: If filename contains invalid characters or path separators
        """
        import re

        # Check for path separators (absolute security risk)
        if "/" in v or "\\" in v:
            raise ValueError(
                "Path separators (/, \\) are not allowed in filename. "
                "Provide only the filename, not a path."
            )

        # Validate filename contains only allowed characters
        # Allowed: alphanumeric, hyphens, underscores, dots
        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError(
                "Filename must contain only alphanumeric characters, "
                "hyphens (-), underscores (_), and dots (.). "
                f"Invalid filename: {v}"
            )

        # Check filename is not empty (after stripping)
        if not v.strip():
            raise ValueError("Filename cannot be empty or whitespace only.")

        # Check filename doesn't start or end with dot (potential hidden file or extension issue)
        if v.startswith(".") or v.endswith("."):
            raise ValueError("Filename cannot start or end with a dot (.).")

        return v


class OrchestrateResponse(BaseModel):
    """Response model for orchestrate endpoint."""

    request_id: str = Field(..., description="UUID request identifier")
    status: str = Field(..., description="Pipeline status: 'completed' or 'failed'")
    event_count: int = Field(..., ge=0, description="Number of events processed")
    aggregated_count: int = Field(default=0, ge=0, description="Number of merged sequences")
    failed_services: list[str] = Field(default_factory=list, description="Failed service names")
    error: str | None = Field(default=None, description="Error message (null on success)")


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(
    request: OrchestrateRequest,
    http_request: Request,
    api_key: str = Depends(verify_api_key),
) -> OrchestrateResponse:
    """
    Orchestrate the full detection pipeline: read CSV, call algorithms, aggregate results.

    This endpoint coordinates the entire pipeline:
    1. Reads input CSV file and parses TransactionEvent objects
    2. Generates unique request_id for this pipeline run
    3. Generates event_fingerprint (SHA256 hash) for deduplication
    4. Calls all algorithm services in parallel with retry logic
    5. Validates all services completed (final_status=True)
    6. Sends results to aggregator service for merging and output writing

    Args:
        request: OrchestrateRequest containing input_file path
        http_request: FastAPI request object (for logging context)

    Returns:
        OrchestrateResponse with request_id, status, event_count, aggregated_count, and error (if any)

    Raises:
        HTTPException: If pipeline execution fails at any step

    Example:
        POST /orchestrate
        {
            "input_file": "transactions.csv"
        }
    """
    # Step 1: Generate request_id
    request_id = generate_request_id()
    logger.info(
        f"Pipeline execution started: request_id={request_id}, input_file={request.input_file}",
        extra={"request_id": request_id},
    )

    try:
        # Step 2: Validate and resolve input file path (prevent path traversal)
        input_dir = get_input_dir()
        try:
            input_path = validate_input_path(request.input_file, input_dir)
        except ValueError as e:
            # Path traversal attempt or invalid path
            error_msg = "Path must be within INPUT_DIR"
            logger.warning(
                f"Path traversal attempt blocked: request_id={request_id}, "
                f"input_file={request.input_file}, error={str(e)}",
                extra={"request_id": request_id},
            )
            raise HTTPException(status_code=400, detail=error_msg)

        # Step 3: Read input CSV
        try:
            events = read_input_csv(input_path, request_id=request_id)
        except FileNotFoundError as e:
            error_msg = "Input file not found"
            logger.error(
                f"Input file not found: request_id={request_id}, path={input_path}, error={str(e)}",
                extra={"request_id": request_id},
                exc_info=True,
            )
            raise HTTPException(status_code=404, detail=error_msg)
        except (IOError, ValueError) as e:
            error_msg = "Failed to read input CSV"
            logger.error(
                f"Failed to read input CSV: request_id={request_id}, path={input_path}, error={str(e)}",
                extra={"request_id": request_id},
                exc_info=True,
            )
            raise HTTPException(status_code=400, detail=error_msg)

        if not events:
            error_msg = "Input CSV file contains no events"
            logger.error(error_msg, extra={"request_id": request_id})
            raise HTTPException(status_code=400, detail=error_msg)

        logger.info(
            f"CSV reading completed: request_id={request_id}, event_count={len(events)}",
            extra={"request_id": request_id},
        )

        # Step 4: Generate event fingerprint
        event_fingerprint = hash_events(events)
        logger.debug(
            f"Event fingerprint generated: request_id={request_id}, "
            f"fingerprint={event_fingerprint[:16]}...",
            extra={"request_id": request_id},
        )

        # Step 5: Call all algorithm services in parallel
        try:
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )
        except Exception as e:
            error_msg = f"Failed to call algorithm services: {str(e)}"
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)

        # Step 6: Validate all services completed
        try:
            validate_all_completed(
                service_status=service_status,
                expected_services=EXPECTED_SERVICES,
                request_id=request_id,
            )
        except RuntimeError as e:
            error_msg = f"Services did not complete: {str(e)}"
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)

        # Step 7: Prepare results for aggregator
        algorithm_results: list[AlgorithmResponse] = []
        failed_services: list[str] = []

        for service_name in EXPECTED_SERVICES:
            status_dict = service_status[service_name]
            if status_dict["status"] == "success" and status_dict["result"] is not None:
                algorithm_results.append(status_dict["result"])
            else:
                failed_services.append(service_name)

        # Step 8: Call aggregator service
        # Note: AggregateRequest requires at least 1 result, but we've validated all services completed
        # If all services failed, we still need to send empty results (validation will catch this)
        try:
            aggregate_request = AggregateRequest(
                request_id=request_id,
                expected_services=EXPECTED_SERVICES,
                results=algorithm_results if algorithm_results else [
                    AlgorithmResponse(
                        request_id=request_id,
                        service_name=EXPECTED_SERVICES[0],
                        status="failure",
                        results=[],
                        error="No successful services",
                        final_status=True,
                    )
                ],
            )

            aggregate_response = await call_aggregator_service(aggregate_request, timeout=60)
        except Exception as e:
            error_msg = f"Failed to call aggregator service: {str(e)}"
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
            raise HTTPException(status_code=500, detail=error_msg)

        # Step 9: Check aggregator response
        if aggregate_response.status == "validation_failed":
            error_msg = f"Aggregator validation failed: {aggregate_response.error}"
            logger.error(error_msg, extra={"request_id": request_id})
            raise HTTPException(status_code=500, detail=error_msg)

        # Pipeline completed successfully
        logger.info(
            f"Pipeline execution completed: request_id={request_id}, "
            f"event_count={len(events)}, aggregated_count={aggregate_response.merged_count}, "
            f"failed_services={aggregate_response.failed_services}",
            extra={"request_id": request_id},
        )

        return OrchestrateResponse(
            request_id=request_id,
            status="completed",
            event_count=len(events),
            aggregated_count=aggregate_response.merged_count,
            failed_services=aggregate_response.failed_services,
            error=None,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Unexpected errors - sanitize before returning to client
        log_error_with_context(
            logger,
            "Unexpected error during pipeline execution",
            e,
            request_id=request_id,
        )
        error_msg = sanitize_error_message(e, "An unexpected error occurred")
        raise HTTPException(status_code=500, detail=error_msg)


if __name__ == "__main__":
    import uvicorn

    port = get_port(default=8000)
    logger.info(f"Starting Orchestrator Service on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        limit_concurrency=100,
        limit_max_requests=1000,
    )

