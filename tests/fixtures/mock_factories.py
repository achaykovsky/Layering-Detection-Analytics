"""
Mock factory functions for creating common mock objects used in tests.

This module provides helper functions for creating and configuring mock objects,
reducing duplication and standardizing mock setup across test files.

## When to Use Mock Factories

**Use mock factories when:**
- Mocking algorithm classes in service tests (use `patch_algorithm_class()`)
- Creating mock algorithms with common behaviors (success, failure, empty results)
- You need consistent mock setup across multiple tests
- You want to reduce boilerplate in test setup

**Use inline mocking when:**
- Creating a one-off mock with very specific behavior
- The mock setup is unique to a single test
- You're testing mock behavior itself (not using the mock)
- Factory doesn't support your specific use case

## Best Practices

1. **Use `patch_algorithm_class()` for service tests**: This context manager
   handles patching and cleanup automatically.

2. **Prefer context managers over decorators**: `patch_algorithm_class()` works
   as a context manager, making test flow clearer.

3. **Configure mocks explicitly**: Pass `detect_return_value` or `detect_side_effect`
   to make test intent clear.

4. **Keep mocks simple**: If mock setup becomes complex, consider if the test
   is testing too much.

Example:
    >>> # Use factory for common mock setup
    >>> with patch_algorithm_class(
    ...     "wash_trading_service_main.WashTradingDetectionAlgorithm",
    ...     detect_return_value=[sequence]
    ... ) as (mock_class, mock_instance):
    ...     # Test code here
    ...     pass
    
    >>> # Inline mocking acceptable for unique cases
    >>> from unittest.mock import MagicMock, patch
    >>> with patch("module.Class") as mock:
    ...     mock.return_value.special_method.return_value = "unique_value"
    ...     # Test code here
    ...     pass
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from layering_detection.models import SuspiciousSequence


def create_mock_algorithm(
    detect_return_value: list[SuspiciousSequence] | None = None,
    detect_side_effect: Exception | Callable[[], Any] | None = None,
) -> MagicMock:
    """
    Create a configured MagicMock instance for an algorithm.

    This factory function creates a mock algorithm instance with the `detect` method
    configured to return a specific value or raise an exception.

    Args:
        detect_return_value: List of SuspiciousSequence objects to return from detect().
            If None, returns empty list by default.
        detect_side_effect: Exception or callable to use as side_effect for detect().
            If provided, takes precedence over detect_return_value.

    Returns:
        MagicMock instance configured as an algorithm with detect() method.

    Examples:
        >>> # Return empty list (default)
        >>> mock = create_mock_algorithm()
        >>> assert mock.detect([]) == []

        >>> # Return specific sequences
        >>> sequences = [create_suspicious_sequence_wash_trading()]
        >>> mock = create_mock_algorithm(detect_return_value=sequences)
        >>> assert mock.detect([]) == sequences

        >>> # Raise exception
        >>> mock = create_mock_algorithm(detect_side_effect=ValueError("Invalid"))
        >>> mock.detect([])  # Raises ValueError
    """
    mock_algorithm = MagicMock()
    if detect_side_effect is not None:
        mock_algorithm.detect.side_effect = detect_side_effect
    else:
        mock_algorithm.detect.return_value = detect_return_value if detect_return_value is not None else []
    return mock_algorithm


@contextmanager
def patch_algorithm_class(
    algorithm_class_path: str,
    detect_return_value: list[SuspiciousSequence] | None = None,
    detect_side_effect: Exception | Callable[[], Any] | None = None,
):
    """
    Context manager for patching an algorithm class and returning a configured mock.

    This function patches the algorithm class at the given path and configures
    the mock instance to return specific values or raise exceptions from its
    detect() method.

    Args:
        algorithm_class_path: Full module path to algorithm class (e.g.,
            "wash_trading_service_main.WashTradingDetectionAlgorithm").
        detect_return_value: List of SuspiciousSequence objects to return from detect().
            If None, returns empty list by default.
        detect_side_effect: Exception or callable to use as side_effect for detect().
            If provided, takes precedence over detect_return_value.

    Yields:
        Tuple of (mock_algorithm_class, mock_algorithm_instance):
            - mock_algorithm_class: The patched class mock
            - mock_algorithm_instance: The configured instance mock

    Examples:
        >>> # Use as context manager
        >>> with patch_algorithm_class(
        ...     "wash_trading_service_main.WashTradingDetectionAlgorithm",
        ...     detect_return_value=[sequence]
        ... ) as (mock_class, mock_instance):
        ...     # Use the patched algorithm
        ...     algorithm = mock_class()
        ...     result = algorithm.detect(events)
        ...     assert result == [sequence]

        >>> # Use with decorator pattern (via functools.wraps)
        >>> @patch_algorithm_class("...", detect_return_value=[])
        ... def test_something(mock_class, mock_instance):
        ...     pass
    """
    with patch(algorithm_class_path) as mock_algorithm_class:
        mock_algorithm_instance = create_mock_algorithm(
            detect_return_value=detect_return_value,
            detect_side_effect=detect_side_effect,
        )
        mock_algorithm_class.return_value = mock_algorithm_instance
        yield mock_algorithm_class, mock_algorithm_instance


def create_mock_async_function(
    return_value: Any = None,
    side_effect: Exception | Callable[[], Any] | None = None,
) -> AsyncMock:
    """
    Create a configured AsyncMock instance for async functions.

    This factory function creates an AsyncMock with configured return value or
    side effect, useful for mocking async service calls.

    Args:
        return_value: Value to return from the async function. If None, returns None.
        side_effect: Exception or callable to use as side_effect. If provided,
            takes precedence over return_value.

    Returns:
        AsyncMock instance configured with return_value or side_effect.

    Examples:
        >>> # Return specific value
        >>> mock = create_mock_async_function(return_value={"status": "success"})
        >>> result = await mock()
        >>> assert result == {"status": "success"}

        >>> # Raise exception
        >>> mock = create_mock_async_function(side_effect=ValueError("Error"))
        >>> await mock()  # Raises ValueError
    """
    mock_async = AsyncMock()
    if side_effect is not None:
        mock_async.side_effect = side_effect
    else:
        mock_async.return_value = return_value
    return mock_async

