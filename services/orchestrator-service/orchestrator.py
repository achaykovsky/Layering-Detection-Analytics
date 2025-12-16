"""
Orchestrator Logic for Parallel Algorithm Service Calls.

Coordinates parallel execution of algorithm services using asyncio.gather.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path to import shared utilities
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from layering_detection.models import TransactionEvent
from services.shared.logging import get_logger

# Import retry logic and config
import importlib.util

retry_path = Path(__file__).parent / "retry.py"
spec = importlib.util.spec_from_file_location("orchestrator_retry", retry_path)
orchestrator_retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_retry)
process_with_retries = orchestrator_retry.process_with_retries

config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("orchestrator_config", config_path)
orchestrator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_config)
get_max_retries = orchestrator_config.get_max_retries
get_timeout_seconds = orchestrator_config.get_timeout_seconds

logger = get_logger(__name__)

# Expected algorithm services
EXPECTED_SERVICES = ["layering", "wash_trading"]


async def call_all_algorithm_services(
    request_id: str,
    event_fingerprint: str,
    events: list[TransactionEvent],
    max_retries: int | None = None,
    timeout: int | None = None,
) -> dict[str, dict]:
    """
    Call all algorithm services in parallel using asyncio.gather.

    Executes algorithm service calls concurrently, with each service using
    process_with_retries() for retry logic. Waits for all services to complete
    (reach final_status=True) before returning.

    Args:
        request_id: UUID request identifier
        event_fingerprint: SHA256 hexdigest of events
        events: List of TransactionEvent domain models
        max_retries: Maximum retry attempts (defaults to config value)
        timeout: Timeout per service call in seconds (defaults to config value)

    Returns:
        service_status dict mapping service_name to status dict with keys:
            - status: "success" or "exhausted"
            - final_status: True (always set)
            - result: AlgorithmResponse on success, None on failure
            - error: Error message on failure, None on success
            - retry_count: Number of retry attempts

    Examples:
        >>> from layering_detection.models import TransactionEvent
        >>> events = [...]
        >>> service_status = await call_all_algorithm_services(
        ...     request_id="abc-123",
        ...     event_fingerprint="..." * 64,
        ...     events=events,
        ... )
        >>> service_status["layering"]["final_status"]
        True
        >>> service_status["wash_trading"]["final_status"]
        True
    """
    if max_retries is None:
        max_retries = get_max_retries()
    if timeout is None:
        timeout = get_timeout_seconds()

    # Initialize service_status dict (shared across all service calls)
    service_status: dict[str, dict] = {}

    # Log parallel execution start
    logger.info(
        f"Starting parallel algorithm service calls: "
        f"request_id={request_id}, "
        f"services={EXPECTED_SERVICES}, "
        f"event_count={len(events)}, "
        f"max_retries={max_retries}, "
        f"timeout={timeout}s",
        extra={"request_id": request_id},
    )

    # Create tasks for parallel execution
    tasks = []
    for service_name in EXPECTED_SERVICES:
        task = process_with_retries(
            service_name=service_name,
            request_id=request_id,
            event_fingerprint=event_fingerprint,
            events=events,
            service_status=service_status,
            max_retries=max_retries,
            timeout=timeout,
        )
        tasks.append(task)

    # Execute all tasks in parallel using asyncio.gather
    # Note: process_with_retries updates service_status in-place, so we don't need return values
    try:
        await asyncio.gather(*tasks, return_exceptions=False)
    except Exception as e:
        # This should not happen as process_with_retries handles all exceptions internally
        # But log it just in case
        logger.error(
            f"Unexpected error during parallel service calls: "
            f"request_id={request_id}, error={str(e)}",
            extra={"request_id": request_id},
            exc_info=True,
        )
        raise

    # Log parallel execution completion
    successful_services = [
        name
        for name in EXPECTED_SERVICES
        if service_status.get(name, {}).get("status") == "success"
    ]
    exhausted_services = [
        name
        for name in EXPECTED_SERVICES
        if service_status.get(name, {}).get("status") == "exhausted"
    ]

    logger.info(
        f"Parallel algorithm service calls completed: "
        f"request_id={request_id}, "
        f"successful={successful_services}, "
        f"exhausted={exhausted_services}, "
        f"total_services={len(EXPECTED_SERVICES)}",
        extra={"request_id": request_id},
    )

    return service_status

