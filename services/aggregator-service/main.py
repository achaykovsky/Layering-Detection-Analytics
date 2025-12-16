"""
Aggregator Service.

FastAPI microservice for validating completion, merging results from algorithm services,
and writing output CSV files.
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

from services.shared.api_models import AggregateRequest, AggregateResponse
from services.shared.config import get_port
from services.shared.logging import get_logger, setup_logging

# Import service-specific config
# Note: aggregator-service directory name has hyphen, so we import via path manipulation
import importlib.util
config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("aggregator_config", config_path)
aggregator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_config)
get_output_dir = aggregator_config.get_output_dir
get_logs_dir = aggregator_config.get_logs_dir
get_validation_strict = aggregator_config.get_validation_strict

# Import aggregator service modules
validation_path = Path(__file__).parent / "validation.py"
spec = importlib.util.spec_from_file_location("aggregator_validation", validation_path)
aggregator_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_validation)
validate_completeness = aggregator_validation.validate_completeness

merger_path = Path(__file__).parent / "merger.py"
spec = importlib.util.spec_from_file_location("aggregator_merger", merger_path)
aggregator_merger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_merger)
merge_results = aggregator_merger.merge_results

writer_path = Path(__file__).parent / "writer.py"
spec = importlib.util.spec_from_file_location("aggregator_writer", writer_path)
aggregator_writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_writer)
write_output_files_from_dtos = aggregator_writer.write_output_files_from_dtos

# Setup logging
logger = setup_logging("aggregator-service", log_level="INFO")
service_logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Aggregator Service",
    description="Microservice for validating completion and aggregating results from algorithm services",
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
    return {"status": "healthy", "service": "aggregator-service"}


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Service information
    """
    return {
        "service": "aggregator-service",
        "version": "1.0.0",
        "status": "running",
        "output_dir": get_output_dir(),
        "validation_strict": get_validation_strict(),
    }


@app.post("/aggregate", response_model=AggregateResponse)
async def aggregate(request: AggregateRequest, http_request: Request) -> AggregateResponse:
    """
    Aggregate results from algorithm services, validate completion, merge sequences, and write output files.

    This endpoint:
    1. Validates all expected services completed (final_status=True)
    2. Merges sequences from successful services, deduplicating overlaps
    3. Writes suspicious_accounts.csv and detections.csv to output directory

    Always returns HTTP 200; check the 'status' field in the response body for success/failure.

    Args:
        request: AggregateRequest containing request_id, expected_services, and results
        http_request: FastAPI request object (for logging context)

    Returns:
        AggregateResponse with status, merged_count, failed_services, and error (if any)

    Example:
        POST /aggregate
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
    """
    request_id = request.request_id
    service_logger.info(
        f"Aggregation request received: request_id={request_id}, "
        f"expected_services={request.expected_services}, "
        f"results_count={len(request.results)}",
        extra={"request_id": request_id},
    )

    # Step 1: Validate completeness
    try:
        validate_completeness(request.expected_services, request.results)
        service_logger.debug(
            f"Validation passed: request_id={request_id}",
            extra={"request_id": request_id},
        )
    except ValueError as e:
        # Validation failed - return validation_failed status
        error_message = str(e)
        service_logger.warning(
            f"Validation failed: request_id={request_id}, error={error_message}",
            extra={"request_id": request_id},
        )
        return AggregateResponse(
            status="validation_failed",
            merged_count=0,
            failed_services=[],
            error=error_message,
        )

    # Step 2: Identify failed services (for logging and response)
    failed_services: list[str] = [
        result.service_name
        for result in request.results
        if result.status != "success"
    ]

    if failed_services:
        service_logger.warning(
            f"Some services failed: request_id={request_id}, failed_services={failed_services}",
            extra={"request_id": request_id},
        )

    # Step 3: Merge results from successful services
    try:
        merged_sequences = merge_results(request.results, request_id=request_id)
        merged_count = len(merged_sequences)
        service_logger.info(
            f"Merged sequences: request_id={request_id}, merged_count={merged_count}",
            extra={"request_id": request_id},
        )
    except Exception as e:
        # Merge failed - return error
        error_message = f"Failed to merge results: {str(e)}"
        service_logger.error(
            error_message,
            extra={"request_id": request_id},
            exc_info=True,
        )
        return AggregateResponse(
            status="validation_failed",
            merged_count=0,
            failed_services=failed_services,
            error=error_message,
        )

    # Step 4: Write output files
    try:
        output_dir = get_output_dir()
        logs_dir = get_logs_dir()
        write_output_files_from_dtos(merged_sequences, output_dir, logs_dir, request_id=request_id)
        service_logger.info(
            f"Output files written: request_id={request_id}, "
            f"output_dir={output_dir}, logs_dir={logs_dir}",
            extra={"request_id": request_id},
        )
    except (IOError, OSError, ValueError) as e:
        # File write failed - return error
        error_message = f"Failed to write output files: {str(e)}"
        service_logger.error(
            error_message,
            extra={"request_id": request_id},
            exc_info=True,
        )
        return AggregateResponse(
            status="validation_failed",
            merged_count=merged_count,  # Include merged count even if write failed
            failed_services=failed_services,
            error=error_message,
        )

    # Step 5: Return success response
    service_logger.info(
        f"Aggregation completed: request_id={request_id}, "
        f"merged_count={merged_count}, failed_services={failed_services}",
        extra={"request_id": request_id},
    )
    return AggregateResponse(
        status="completed",
        merged_count=merged_count,
        failed_services=failed_services,
        error=None,
    )


if __name__ == "__main__":
    import uvicorn

    port = get_port(default=8003)
    logger.info(f"Starting Aggregator Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

