"""
Algorithm Service HTTP Client.

HTTP client for calling algorithm services (Layering, Wash Trading) with timeout handling.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path to import shared utilities
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import httpx

from services.shared.api_models import (
    AggregateRequest,
    AggregateResponse,
    AlgorithmRequest,
    AlgorithmResponse,
)
from services.shared.logging import get_logger

# Import service-specific config
import importlib.util
config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("orchestrator_config", config_path)
orchestrator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_config)
get_layering_service_url = orchestrator_config.get_layering_service_url
get_wash_trading_service_url = orchestrator_config.get_wash_trading_service_url
get_aggregator_service_url = orchestrator_config.get_aggregator_service_url

logger = get_logger(__name__)


def _get_service_url(service_name: str) -> str:
    """
    Get service URL for given service name.

    Args:
        service_name: Service name ("layering" or "wash_trading")

    Returns:
        Service URL

    Raises:
        ValueError: If service_name is invalid
    """
    if service_name == "layering":
        return get_layering_service_url()
    elif service_name == "wash_trading":
        return get_wash_trading_service_url()
    else:
        raise ValueError(f"Invalid service_name: {service_name} (must be 'layering' or 'wash_trading')")


async def call_algorithm_service(
    service_name: str,
    request: AlgorithmRequest,
    timeout: int,
) -> AlgorithmResponse:
    """
    Call algorithm service with AlgorithmRequest and return AlgorithmResponse.

    Makes async HTTP POST request to algorithm service `/detect` endpoint.
    Handles timeouts, connection errors, and HTTP errors gracefully.

    Args:
        service_name: Service name ("layering" or "wash_trading")
        request: AlgorithmRequest with request_id, event_fingerprint, and events
        timeout: Timeout in seconds for the HTTP request

    Returns:
        AlgorithmResponse from the algorithm service

    Raises:
        TimeoutError: If request times out
        ConnectionError: If connection fails
        ValueError: If service_name is invalid or response parsing fails
        httpx.HTTPStatusError: If HTTP status code indicates error (5xx)

    Examples:
        >>> from services.shared.api_models import AlgorithmRequest, TransactionEventDTO
        >>> request = AlgorithmRequest(
        ...     request_id="abc-123",
        ...     event_fingerprint="..." * 64,
        ...     events=[...],
        ... )
        >>> response = await call_algorithm_service("layering", request, timeout=30)
        >>> isinstance(response, AlgorithmResponse)
        True
    """
    request_id = request.request_id

    # Get service URL
    try:
        service_url = _get_service_url(service_name)
    except ValueError as e:
        logger.error(
            f"Invalid service name: {service_name}",
            extra={"request_id": request_id},
        )
        raise

    detect_url = f"{service_url}/detect"

    # Log service call start
    logger.info(
        f"Calling algorithm service: service_name={service_name}, "
        f"request_id={request_id}, url={detect_url}, timeout={timeout}s",
        extra={"request_id": request_id},
    )

    try:
        # Make async HTTP POST request
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                detect_url,
                json=request.model_dump(),
                headers={"Content-Type": "application/json"},
            )

            # Raise exception for HTTP error status codes
            response.raise_for_status()

            # Parse response to AlgorithmResponse
            try:
                algorithm_response = AlgorithmResponse.model_validate(response.json())
            except Exception as e:
                error_msg = f"Failed to parse AlgorithmResponse: {str(e)}"
                logger.error(
                    error_msg,
                    extra={"request_id": request_id},
                    exc_info=True,
                )
                raise ValueError(error_msg) from e

            # Log successful response
            logger.info(
                f"Algorithm service call succeeded: service_name={service_name}, "
                f"request_id={request_id}, status={algorithm_response.status}",
                extra={"request_id": request_id},
            )

            return algorithm_response

    except httpx.TimeoutException as e:
        # Timeout error
        error_msg = f"Algorithm service call timed out: service_name={service_name}, timeout={timeout}s"
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise TimeoutError(error_msg) from e

    except httpx.ConnectError as e:
        # Connection error
        error_msg = f"Failed to connect to algorithm service: service_name={service_name}, url={detect_url}"
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise ConnectionError(error_msg) from e

    except httpx.HTTPStatusError as e:
        # HTTP error status (4xx, 5xx)
        error_msg = (
            f"Algorithm service returned error status: service_name={service_name}, "
            f"status_code={e.response.status_code}, url={detect_url}"
        )
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        # Re-raise as HTTPStatusError (caller can handle 5xx vs 4xx differently)
        raise

    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error calling algorithm service: service_name={service_name}, error={str(e)}"
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise


async def call_aggregator_service(
    request: AggregateRequest,
    timeout: int = 60,
) -> AggregateResponse:
    """
    Call aggregator service with AggregateRequest and return AggregateResponse.

    Makes async HTTP POST request to aggregator service `/aggregate` endpoint.
    Handles timeouts, connection errors, and HTTP errors gracefully.

    Args:
        request: AggregateRequest with request_id, expected_services, and results
        timeout: Timeout in seconds for the HTTP request (default: 60s)

    Returns:
        AggregateResponse from the aggregator service

    Raises:
        TimeoutError: If request times out
        ConnectionError: If connection fails
        ValueError: If response parsing fails
        httpx.HTTPStatusError: If HTTP status code indicates error

    Examples:
        >>> from services.shared.api_models import AggregateRequest, AlgorithmResponse
        >>> request = AggregateRequest(
        ...     request_id="abc-123",
        ...     expected_services=["layering", "wash_trading"],
        ...     results=[...],
        ... )
        >>> response = await call_aggregator_service(request, timeout=60)
        >>> isinstance(response, AggregateResponse)
        True
    """
    request_id = request.request_id

    # Get aggregator service URL
    try:
        aggregator_url = get_aggregator_service_url()
    except Exception as e:
        logger.error(
            f"Failed to get aggregator service URL: {str(e)}",
            extra={"request_id": request_id},
        )
        raise

    aggregate_url = f"{aggregator_url}/aggregate"

    # Log aggregator call start
    logger.info(
        f"Calling aggregator service: request_id={request_id}, "
        f"url={aggregate_url}, timeout={timeout}s, "
        f"expected_services={request.expected_services}, "
        f"results_count={len(request.results)}",
        extra={"request_id": request_id},
    )

    try:
        # Make async HTTP POST request
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                aggregate_url,
                json=request.model_dump(),
                headers={"Content-Type": "application/json"},
            )

            # Raise exception for HTTP error status codes
            response.raise_for_status()

            # Parse response to AggregateResponse
            try:
                aggregate_response = AggregateResponse.model_validate(response.json())
            except Exception as e:
                error_msg = f"Failed to parse AggregateResponse: {str(e)}"
                logger.error(
                    error_msg,
                    extra={"request_id": request_id},
                    exc_info=True,
                )
                raise ValueError(error_msg) from e

            # Log successful response
            logger.info(
                f"Aggregator service call succeeded: request_id={request_id}, "
                f"status={aggregate_response.status}, "
                f"merged_count={aggregate_response.merged_count}, "
                f"failed_services={aggregate_response.failed_services}",
                extra={"request_id": request_id},
            )

            return aggregate_response

    except httpx.TimeoutException as e:
        # Timeout error
        error_msg = f"Aggregator service call timed out: request_id={request_id}, timeout={timeout}s"
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise TimeoutError(error_msg) from e

    except httpx.ConnectError as e:
        # Connection error
        error_msg = (
            f"Failed to connect to aggregator service: request_id={request_id}, url={aggregate_url}"
        )
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise ConnectionError(error_msg) from e

    except httpx.HTTPStatusError as e:
        # HTTP error status (4xx, 5xx)
        error_msg = (
            f"Aggregator service returned error status: request_id={request_id}, "
            f"status_code={e.response.status_code}, url={aggregate_url}"
        )
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        # Re-raise as HTTPStatusError
        raise

    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error calling aggregator service: request_id={request_id}, error={str(e)}"
        logger.error(
            error_msg,
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise

