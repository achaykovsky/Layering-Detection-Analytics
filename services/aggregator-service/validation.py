"""
Completion Validation Logic.

Validates that all expected algorithm services have completed before processing results.
"""

from __future__ import annotations

from services.shared.api_models import AlgorithmResponse


def validate_completeness(
    expected_services: list[str],
    results: list[AlgorithmResponse],
) -> None:
    """
    Validate all expected services completed before processing results.

    Checks:
    1. All expected services are present in results
    2. All services have final_status=True (indicating no more retries)

    Args:
        expected_services: List of expected service names (e.g., ["layering", "wash_trading"])
        results: List of AlgorithmResponse objects from algorithm services

    Raises:
        ValueError: If validation fails, with detailed error message including:
            - Missing service names (if any)
            - Incomplete service names (if any)

    Examples:
        >>> from services.shared.api_models import AlgorithmResponse, AlgorithmStatus
        >>> results = [
        ...     AlgorithmResponse(
        ...         request_id="abc",
        ...         service_name="layering",
        ...         status=AlgorithmStatus.SUCCESS,
        ...         results=[],
        ...         final_status=True,
        ...     ),
        ...     AlgorithmResponse(
        ...         request_id="abc",
        ...         service_name="wash_trading",
        ...         status=AlgorithmStatus.SUCCESS,
        ...         results=[],
        ...         final_status=True,
        ...     ),
        ... ]
        >>> validate_completeness(["layering", "wash_trading"], results)
        # No exception raised

        >>> validate_completeness(["layering", "wash_trading"], [results[0]])
        Traceback (most recent recent call last):
        ...
        ValueError: Missing services: {'wash_trading'}. Expected: ['layering', 'wash_trading'], Got: {'layering'}
    """
    # Check all expected services are present
    received_services = {result.service_name for result in results}
    missing_services = set(expected_services) - received_services

    if missing_services:
        raise ValueError(
            f"Missing services: {sorted(missing_services)}. "
            f"Expected: {sorted(expected_services)}, Got: {sorted(received_services)}"
        )

    # Check all services have final_status=True
    incomplete_services: list[str] = []
    for result in results:
        if not result.final_status:
            incomplete_services.append(result.service_name)

    if incomplete_services:
        raise ValueError(
            f"Services not completed: {sorted(incomplete_services)}. "
            f"All services must have final_status=True"
        )

