"""
Completion Tracking and Validation.

Validates that all expected services have completed (final_status=True) before aggregation.
"""

from __future__ import annotations

from services.shared.logging import get_logger

logger = get_logger(__name__)


def validate_all_completed(
    service_status: dict[str, dict],
    expected_services: list[str],
    request_id: str | None = None,
) -> None:
    """
    Validate all expected services have completed (final_status=True) before aggregation.

    Checks that all expected services are present in service_status and have final_status=True.
    Raises RuntimeError if any services are missing or incomplete.

    Args:
        service_status: Dict mapping service_name to status dict with keys:
            - status: "success" or "exhausted"
            - final_status: bool (must be True)
            - result: AlgorithmResponse or None
            - error: str or None
            - retry_count: int
        expected_services: List of expected service names (e.g., ["layering", "wash_trading"])
        request_id: Optional request ID for logging context

    Raises:
        RuntimeError: If validation fails, with detailed error message including:
            - Missing service names (if any)
            - Incomplete service names (if any)

    Examples:
        >>> service_status = {
        ...     "layering": {
        ...         "status": "success",
        ...         "final_status": True,
        ...         "result": ...,
        ...         "retry_count": 0,
        ...     },
        ...     "wash_trading": {
        ...         "status": "exhausted",
        ...         "final_status": True,
        ...         "result": None,
        ...         "error": "...",
        ...         "retry_count": 3,
        ...     },
        ... }
        >>> validate_all_completed(service_status, ["layering", "wash_trading"])
        # No exception raised

        >>> validate_all_completed(service_status, ["layering", "wash_trading", "extra"])
        Traceback (most recent call last):
        ...
        RuntimeError: Services did not complete: ['extra']. All services must reach final_status=True
    """
    incomplete_services: list[str] = []

    # Check all expected services are present and have final_status=True
    for service_name in expected_services:
        if service_name not in service_status:
            incomplete_services.append(service_name)
            if request_id:
                logger.warning(
                    f"Service missing from service_status: service_name={service_name}, "
                    f"request_id={request_id}",
                    extra={"request_id": request_id},
                )
            else:
                logger.warning(
                    f"Service missing from service_status: service_name={service_name}"
                )
        else:
            status_dict = service_status[service_name]
            final_status = status_dict.get("final_status", False)
            if not final_status:
                incomplete_services.append(service_name)
                if request_id:
                    logger.warning(
                        f"Service incomplete: service_name={service_name}, "
                        f"final_status={final_status}, request_id={request_id}",
                        extra={"request_id": request_id},
                    )
                else:
                    logger.warning(
                        f"Service incomplete: service_name={service_name}, "
                        f"final_status={final_status}"
                    )

    if incomplete_services:
        error_message = (
            f"Services did not complete: {sorted(incomplete_services)}. "
            f"All services must reach final_status=True"
        )
        if request_id:
            logger.error(
                error_message,
                extra={"request_id": request_id},
            )
        else:
            logger.error(error_message)
        raise RuntimeError(error_message)

    # All services completed
    if request_id:
        logger.debug(
            f"All services completed validation passed: "
            f"expected_services={expected_services}, request_id={request_id}",
            extra={"request_id": request_id},
        )
    else:
        logger.debug(
            f"All services completed validation passed: expected_services={expected_services}"
        )

