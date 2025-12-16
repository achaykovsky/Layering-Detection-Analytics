"""
Retry Logic with Exponential Backoff.

Implements retry logic for algorithm service calls with exponential backoff.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path to import shared utilities
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import httpx

from layering_detection.models import TransactionEvent
from services.shared.api_models import AlgorithmRequest, AlgorithmResponse
from services.shared.converters import transaction_event_to_dto
from services.shared.logging import get_logger

# Import client and config
import importlib.util
client_path = Path(__file__).parent / "client.py"
spec = importlib.util.spec_from_file_location("orchestrator_client", client_path)
orchestrator_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_client)
call_algorithm_service = orchestrator_client.call_algorithm_service

config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("orchestrator_config", config_path)
orchestrator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_config)
get_max_retries = orchestrator_config.get_max_retries
get_timeout_seconds = orchestrator_config.get_timeout_seconds

logger = get_logger(__name__)


async def process_with_retries(
    service_name: str,
    request_id: str,
    event_fingerprint: str,
    events: list[TransactionEvent],
    service_status: dict[str, dict],
    max_retries: int | None = None,
    timeout: int | None = None,
) -> None:
    """
    Process algorithm service call with retry logic and exponential backoff.

    Retries up to MAX_RETRIES times on transient errors (TimeoutError, ConnectionError, HTTP 5xx).
    Does not retry on HTTP 4xx errors (client errors).
    Uses exponential backoff: 2^attempt seconds between retries (1s, 2s, 4s).

    Updates service_status dict with:
    - status: "success" or "exhausted"
    - final_status: True (always set after function completes)
    - result: AlgorithmResponse on success, None on failure
    - error: Error message on failure, None on success
    - retry_count: Number of retry attempts (0 = first attempt succeeded)

    Args:
        service_name: Service name ("layering" or "wash_trading")
        request_id: UUID request identifier
        event_fingerprint: SHA256 hexdigest of events
        events: List of TransactionEvent domain models
        service_status: Dict to update with service status (modified in-place)
        max_retries: Maximum retry attempts (defaults to config value)
        timeout: Timeout per service call in seconds (defaults to config value)

    Examples:
        >>> service_status = {}
        >>> await process_with_retries(
        ...     service_name="layering",
        ...     request_id="abc-123",
        ...     event_fingerprint="..." * 64,
        ...     events=[...],
        ...     service_status=service_status,
        ... )
        >>> service_status["layering"]["final_status"]
        True
    """
    if max_retries is None:
        max_retries = get_max_retries()
    if timeout is None:
        timeout = get_timeout_seconds()

    # Convert events to DTOs
    event_dtos = [transaction_event_to_dto(event) for event in events]

    # Create AlgorithmRequest
    algorithm_request = AlgorithmRequest(
        request_id=request_id,
        event_fingerprint=event_fingerprint,
        events=event_dtos,
    )

    # Retry loop: attempt 0 to max_retries (total attempts = max_retries + 1)
    for attempt in range(max_retries + 1):
        try:
            # Call algorithm service
            result = await call_algorithm_service(
                service_name=service_name,
                request=algorithm_request,
                timeout=timeout,
            )

            # Success - update service_status and return
            service_status[service_name] = {
                "status": "success",
                "final_status": True,
                "result": result,
                "error": None,
                "retry_count": attempt,
            }

            if attempt > 0:
                logger.info(
                    f"Algorithm service call succeeded after retry: "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"attempt={attempt + 1}, retry_count={attempt}",
                    extra={"request_id": request_id},
                )
            else:
                logger.debug(
                    f"Algorithm service call succeeded on first attempt: "
                    f"service_name={service_name}, request_id={request_id}",
                    extra={"request_id": request_id},
                )

            return

        except TimeoutError as e:
            # Timeout error - retry if attempts remaining
            if attempt < max_retries:
                backoff_seconds = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Algorithm service call timed out, retrying: "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"attempt={attempt + 1}/{max_retries + 1}, "
                    f"backoff={backoff_seconds}s",
                    extra={"request_id": request_id},
                )
                await asyncio.sleep(backoff_seconds)
                continue
            else:
                # Retries exhausted
                service_status[service_name] = {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": str(e),
                    "retry_count": attempt + 1,
                }
                logger.error(
                    f"Algorithm service call exhausted retries (timeout): "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"retry_count={attempt + 1}",
                    extra={"request_id": request_id},
                    exc_info=True,
                )
                return

        except ConnectionError as e:
            # Connection error - retry if attempts remaining
            if attempt < max_retries:
                backoff_seconds = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"Algorithm service connection failed, retrying: "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"attempt={attempt + 1}/{max_retries + 1}, "
                    f"backoff={backoff_seconds}s",
                    extra={"request_id": request_id},
                )
                await asyncio.sleep(backoff_seconds)
                continue
            else:
                # Retries exhausted
                service_status[service_name] = {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": str(e),
                    "retry_count": attempt + 1,
                }
                logger.error(
                    f"Algorithm service call exhausted retries (connection error): "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"retry_count={attempt + 1}",
                    extra={"request_id": request_id},
                    exc_info=True,
                )
                return

        except httpx.HTTPStatusError as e:
            # HTTP error - check if 5xx (retry) or 4xx (no retry)
            status_code = e.response.status_code

            if 500 <= status_code < 600:
                # 5xx error - retry if attempts remaining
                if attempt < max_retries:
                    backoff_seconds = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Algorithm service returned 5xx error, retrying: "
                        f"service_name={service_name}, request_id={request_id}, "
                        f"status_code={status_code}, "
                        f"attempt={attempt + 1}/{max_retries + 1}, "
                        f"backoff={backoff_seconds}s",
                        extra={"request_id": request_id},
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue
                else:
                    # Retries exhausted
                    service_status[service_name] = {
                        "status": "exhausted",
                        "final_status": True,
                        "result": None,
                        "error": f"HTTP {status_code}: {str(e)}",
                        "retry_count": attempt + 1,
                    }
                    logger.error(
                        f"Algorithm service call exhausted retries (5xx error): "
                        f"service_name={service_name}, request_id={request_id}, "
                        f"status_code={status_code}, retry_count={attempt + 1}",
                        extra={"request_id": request_id},
                        exc_info=True,
                    )
                    return
            else:
                # 4xx error - do not retry (client error)
                service_status[service_name] = {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": f"HTTP {status_code}: {str(e)}",
                    "retry_count": attempt + 1,
                }
                logger.error(
                    f"Algorithm service returned 4xx error (no retry): "
                    f"service_name={service_name}, request_id={request_id}, "
                    f"status_code={status_code}",
                    extra={"request_id": request_id},
                    exc_info=True,
                )
                return

        except Exception as e:
            # Unexpected error - do not retry
            service_status[service_name] = {
                "status": "exhausted",
                "final_status": True,
                "result": None,
                "error": str(e),
                "retry_count": attempt + 1,
            }
            logger.error(
                f"Algorithm service call failed with unexpected error (no retry): "
                f"service_name={service_name}, request_id={request_id}, "
                f"error={str(e)}",
                extra={"request_id": request_id},
                exc_info=True,
            )
            return

