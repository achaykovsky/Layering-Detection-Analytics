"""
Shared utility functions for layering detection analytics.

This module contains common functions used across multiple detection algorithms
to avoid code duplication and reduce coupling between modules.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, DefaultDict, Dict, Iterable, List, Tuple

if TYPE_CHECKING:
    from ..models import Side, TransactionEvent

AccountProductKey = Tuple[str, str]


def group_events_by_account_product(
    events: Iterable[TransactionEvent],
) -> Dict[AccountProductKey, List[TransactionEvent]]:
    """
    Group events by (account_id, product_id) and sort each group by timestamp.
    
    This utility function is used by multiple detection algorithms to organize
    events before processing. Each group is sorted by timestamp to enable
    time-based pattern detection.
    
    Args:
        events: Iterable of transaction events to group.
    
    Returns:
        Dictionary mapping (account_id, product_id) tuples to sorted lists
        of events. Each list is sorted by timestamp in ascending order.
    
    Example:
        >>> events = [
        ...     TransactionEvent(..., account_id="ACC1", product_id="IBM", ...),
        ...     TransactionEvent(..., account_id="ACC1", product_id="IBM", ...),
        ...     TransactionEvent(..., account_id="ACC2", product_id="GOOG", ...),
        ... ]
        >>> grouped = group_events_by_account_product(events)
        >>> len(grouped[("ACC1", "IBM")])
        2
        >>> len(grouped[("ACC2", "GOOG")])
        1
    """
    grouped: DefaultDict[AccountProductKey, List[TransactionEvent]] = defaultdict(list)
    for event in events:
        grouped[(event.account_id, event.product_id)].append(event)

    for key in grouped:
        grouped[key].sort(key=lambda e: e.timestamp)

    return dict(grouped)


def validate_positive(value: int | float | timedelta, name: str) -> None:
    """
    Validate that a value is positive (greater than zero).
    
    This utility function is used by configuration classes to validate
    positive values. Works with integers, floats, and timedelta objects.
    It determines the type at runtime and formats error messages appropriately.
    
    Args:
        value: The value to validate (int, float, or timedelta).
        name: The name of the field being validated (for error messages).
    
    Raises:
        ValueError: If the value is negative or zero, with a clear
            message indicating which field is invalid.
        TypeError: If the value type is not supported (int, float, or timedelta).
    
    Example:
        >>> validate_positive(10, "min_trades")
        >>> validate_positive(0, "min_trades")
        Traceback (most recent call last):
        ...
        ValueError: min_trades must be positive, got zero value: 0
        >>> validate_positive(60.0, "min_percentage")
        >>> validate_positive(-5.0, "min_percentage")
        Traceback (most recent call last):
        ...
        ValueError: min_percentage must be positive, got negative value: -5.0
        >>> from datetime import timedelta
        >>> validate_positive(timedelta(seconds=10), "orders_window")
        >>> validate_positive(timedelta(seconds=0), "orders_window")
        Traceback (most recent call last):
        ...
        ValueError: orders_window must be positive, got zero value: 0:00:00
    """
    # Determine zero threshold based on type
    if isinstance(value, timedelta):
        zero_threshold = timedelta(0)
        is_timedelta = True
    elif isinstance(value, (int, float)):
        zero_threshold = 0
        is_timedelta = False
    else:
        raise TypeError(
            f"Unsupported type for validation: {type(value).__name__}. "
            f"Expected int, float, or timedelta."
        )
    
    # Check if value is zero or negative (same logic for all types)
    if value <= zero_threshold:
        is_negative = value < zero_threshold
        error_type = "negative" if is_negative else "zero"
        
        # Format error value based on type
        if is_timedelta and is_negative:
            # Special formatting for negative timedelta: show seconds
            seconds = abs(value.total_seconds())
            error_value = f"-{seconds} seconds"
        else:
            # Simple formatting for zero timedelta or numeric types
            error_value = str(value)
        
        raise ValueError(
            f"{name} must be positive, got {error_type} value: {error_value}"
        )


def get_opposite_side(side: "Side") -> "Side":
    """
    Get the opposite side (BUY -> SELL, SELL -> BUY).
    
    This utility function provides type-safe conversion between sides
    without using type casts. Used in detection algorithms to find
    opposite-side trades.
    
    Args:
        side: The current side (BUY or SELL).
    
    Returns:
        The opposite side. BUY returns SELL, SELL returns BUY.
    
    Example:
        >>> get_opposite_side("BUY")
        'SELL'
        >>> get_opposite_side("SELL")
        'BUY'
    """
    return "SELL" if side == "BUY" else "BUY"
