"""
Test data factory functions for creating test objects.

This module provides factory functions to reduce duplication of test data
creation across test files. All factories use sensible defaults that match
common test patterns, while allowing full customization via parameters.

## When to Use Factories

**Use factories when:**
- Creating multiple similar objects in a test file (reduces duplication)
- Default values are acceptable or can be easily overridden
- You want consistent test data patterns across the codebase
- You need to create complex objects (patterns, sequences) with minimal code

**Use inline creation when:**
- Creating a single one-off object with very specific values
- The object is unique to a single test and unlikely to be reused
- Factory defaults don't match your needs and would require many overrides
- You're testing object construction itself (not using the object)

## Best Practices

1. **Prefer factories for common patterns**: Use `create_wash_trading_pattern()` 
   instead of manually creating 6 TransactionEvent objects.

2. **Override only what's needed**: Use factory defaults and override only 
   parameters that matter for your test.

3. **Use pattern factories**: For complete patterns (wash trading, layering), 
   use pattern factories rather than creating individual events.

4. **Keep tests readable**: If inline creation is clearer for a specific test, 
   use it. Readability trumps consistency.

Example:
    >>> from tests.fixtures import create_transaction_event
    >>> # Use factory for common case
    >>> event = create_transaction_event(
    ...     account_id="ACC002",
    ...     product_id="AAPL",
    ...     side="SELL"
    ... )
    >>> assert event.account_id == "ACC002"
    
    >>> # Inline creation acceptable for one-off unique cases
    >>> from layering_detection.models import TransactionEvent
    >>> unique_event = TransactionEvent(
    ...     timestamp=datetime(2025, 1, 1, 12, 0, 0),
    ...     account_id="SPECIAL_ACC",
    ...     product_id="UNIQUE_PRODUCT",
    ...     side="BUY",
    ...     price=Decimal("999.99"),
    ...     quantity=1,
    ...     event_type="TRADE_EXECUTED"
    ... )
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from layering_detection.models import SuspiciousSequence, TransactionEvent
    from services.shared.api_models import (
        AlgorithmRequest,
        AlgorithmResponse,
        TransactionEventDTO,
    )


# Default values matching common test patterns
_DEFAULT_TIMESTAMP = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
_DEFAULT_TIMESTAMP_STR = "2025-01-15T10:30:00"
_DEFAULT_ACCOUNT_ID = "ACC001"
_DEFAULT_PRODUCT_ID = "IBM"
_DEFAULT_SIDE = "BUY"
_DEFAULT_PRICE = Decimal("100.0")
_DEFAULT_PRICE_STR = "100.50"
_DEFAULT_QUANTITY = 1000
_DEFAULT_EVENT_TYPE = "ORDER_PLACED"


def create_transaction_event(
    timestamp: datetime | None = None,
    account_id: str | None = None,
    product_id: str | None = None,
    side: str | None = None,
    price: str | Decimal | None = None,
    quantity: int | None = None,
    event_type: str | None = None,
) -> TransactionEvent:
    """
    Factory function for creating TransactionEvent test data.

    Creates a TransactionEvent with sensible defaults that can be overridden
    via parameters. All parameters are optional.

    Args:
        timestamp: Event timestamp. Defaults to 2025-01-01 09:00:00 UTC.
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        side: Trade side ("BUY" or "SELL"). Defaults to "BUY".
        price: Price as Decimal or string. Defaults to Decimal("100.0").
        quantity: Trade quantity. Defaults to 1000.
        event_type: Event type ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED").
            Defaults to "ORDER_PLACED".

    Returns:
        TransactionEvent instance with specified or default values.

    Example:
        >>> event = create_transaction_event(
        ...     account_id="ACC002",
        ...     side="SELL",
        ...     event_type="TRADE_EXECUTED"
        ... )
        >>> assert event.account_id == "ACC002"
        >>> assert event.side == "SELL"
        >>> assert event.event_type == "TRADE_EXECUTED"
    """
    from layering_detection.models import TransactionEvent

    if timestamp is None:
        timestamp = _DEFAULT_TIMESTAMP
    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if side is None:
        side = _DEFAULT_SIDE
    if price is None:
        price = _DEFAULT_PRICE
    elif isinstance(price, str):
        price = Decimal(price)
    if quantity is None:
        quantity = _DEFAULT_QUANTITY
    if event_type is None:
        event_type = _DEFAULT_EVENT_TYPE

    return TransactionEvent(
        timestamp=timestamp,
        account_id=account_id,
        product_id=product_id,
        side=side,  # type: ignore[arg-type]
        price=price,
        quantity=quantity,
        event_type=event_type,  # type: ignore[arg-type]
    )


def create_transaction_event_dto(
    timestamp: str | None = None,
    account_id: str | None = None,
    product_id: str | None = None,
    side: str | None = None,
    price: str | None = None,
    quantity: int | None = None,
    event_type: str | None = None,
) -> TransactionEventDTO:
    """
    Factory function for creating TransactionEventDTO test data.

    Creates a TransactionEventDTO (Pydantic model) with sensible defaults.
    All parameters are optional.

    Args:
        timestamp: ISO format datetime string. Defaults to "2025-01-15T10:30:00".
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        side: Trade side ("BUY" or "SELL"). Defaults to "BUY".
        price: Price as string. Defaults to "100.50".
        quantity: Trade quantity. Defaults to 1000.
        event_type: Event type ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED").
            Defaults to "ORDER_PLACED".

    Returns:
        TransactionEventDTO instance with specified or default values.

    Example:
        >>> dto = create_transaction_event_dto(
        ...     account_id="ACC002",
        ...     side="SELL",
        ...     event_type="TRADE_EXECUTED"
        ... )
        >>> assert dto.account_id == "ACC002"
        >>> assert dto.side == "SELL"
    """
    from services.shared.api_models import TransactionEventDTO

    if timestamp is None:
        timestamp = _DEFAULT_TIMESTAMP_STR
    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if side is None:
        side = _DEFAULT_SIDE
    if price is None:
        price = _DEFAULT_PRICE_STR
    if quantity is None:
        quantity = _DEFAULT_QUANTITY
    if event_type is None:
        event_type = _DEFAULT_EVENT_TYPE

    return TransactionEventDTO(
        timestamp=timestamp,
        account_id=account_id,
        product_id=product_id,
        side=side,  # type: ignore[arg-type]
        price=price,
        quantity=quantity,
        event_type=event_type,  # type: ignore[arg-type]
    )


def create_algorithm_request(
    request_id: str | None = None,
    event_fingerprint: str | None = None,
    events: list[TransactionEventDTO] | None = None,
) -> AlgorithmRequest:
    """
    Factory function for creating AlgorithmRequest test data.

    Creates an AlgorithmRequest with sensible defaults. All parameters are optional.

    Args:
        request_id: UUID string. Defaults to a new UUID4.
        event_fingerprint: SHA256 hexdigest (64 hex characters). Defaults to "a" * 64.
        events: List of TransactionEventDTO. Defaults to a single default event.

    Returns:
        AlgorithmRequest instance with specified or default values.

    Example:
        >>> request = create_algorithm_request(
        ...     request_id="550e8400-e29b-41d4-a716-446655440000",
        ...     events=[create_transaction_event_dto()]
        ... )
        >>> assert len(request.events) == 1
    """
    from services.shared.api_models import AlgorithmRequest

    if request_id is None:
        request_id = str(uuid4())
    if event_fingerprint is None:
        event_fingerprint = "a" * 64  # Valid SHA256 hexdigest
    if events is None:
        events = [create_transaction_event_dto()]

    return AlgorithmRequest(
        request_id=request_id,
        event_fingerprint=event_fingerprint,
        events=events,
    )


def create_algorithm_response(
    request_id: str | None = None,
    service_name: str = "layering",
    status: str = "success",
    results: list | None = None,
    error: str | None = None,
    final_status: bool = True,
) -> AlgorithmResponse:
    """
    Factory function for creating AlgorithmResponse test data.

    Creates an AlgorithmResponse with sensible defaults. Validates status/error/results
    consistency according to AlgorithmResponse rules.

    Args:
        request_id: UUID string. Defaults to a new UUID4.
        service_name: Service name ("layering" or "wash_trading"). Defaults to "layering".
        status: Response status ("success", "failure", "timeout"). Defaults to "success".
        results: List of SuspiciousSequenceDTO. Defaults to empty list for success, None for failure.
        error: Error message. Defaults to None for success, required for failure.
        final_status: Whether service completed (no more retries). Defaults to True.

    Returns:
        AlgorithmResponse instance with specified or default values.

    Example:
        >>> response = create_algorithm_response(
        ...     service_name="wash_trading",
        ...     status="success",
        ...     results=[]
        ... )
        >>> assert response.service_name == "wash_trading"
        >>> assert response.status == "success"
    """
    from services.shared.api_models import AlgorithmResponse

    if request_id is None:
        request_id = str(uuid4())

    # Set defaults based on status
    if status == "success":
        if results is None:
            results = []
        if error is not None:
            error = None  # Override if provided but should be None
    elif status in ("failure", "timeout"):
        if results is not None:
            results = None  # Override if provided but should be None
        if error is None:
            error = "Test error"  # Provide default error if not specified

    return AlgorithmResponse(
        request_id=request_id,
        service_name=service_name,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        results=results,
        error=error,
        final_status=final_status,
    )


def create_suspicious_sequence_layering(
    account_id: str | None = None,
    product_id: str | None = None,
    start_timestamp: datetime | None = None,
    end_timestamp: datetime | None = None,
    total_buy_qty: int | None = None,
    total_sell_qty: int | None = None,
    side: str | None = None,
    num_cancelled_orders: int | None = None,
    order_timestamps: list[datetime] | None = None,
) -> SuspiciousSequence:
    """
    Factory function for creating LAYERING SuspiciousSequence test data.

    Creates a SuspiciousSequence with detection_type="LAYERING" and required
    layering-specific fields (side, num_cancelled_orders, order_timestamps).

    Args:
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        start_timestamp: Sequence start time. Defaults to 2025-01-15 10:30:00 UTC.
        end_timestamp: Sequence end time. Defaults to start_timestamp + 10 seconds.
        total_buy_qty: Total BUY quantity. Defaults to 5000.
        total_sell_qty: Total SELL quantity. Defaults to 0.
        side: Trade side ("BUY" or "SELL"). Defaults to "BUY".
        num_cancelled_orders: Number of cancelled orders. Defaults to 3.
        order_timestamps: List of order timestamps. Defaults to [start_timestamp, start_timestamp + 5s].

    Returns:
        SuspiciousSequence instance with detection_type="LAYERING".

    Example:
        >>> sequence = create_suspicious_sequence_layering(
        ...     account_id="ACC002",
        ...     side="SELL",
        ...     num_cancelled_orders=5
        ... )
        >>> assert sequence.detection_type == "LAYERING"
        >>> assert sequence.side == "SELL"
        >>> assert sequence.num_cancelled_orders == 5
    """
    from layering_detection.models import SuspiciousSequence

    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if start_timestamp is None:
        start_timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    if end_timestamp is None:
        end_timestamp = start_timestamp + timedelta(seconds=10)
    if total_buy_qty is None:
        total_buy_qty = 5000
    if total_sell_qty is None:
        total_sell_qty = 0
    if side is None:
        side = _DEFAULT_SIDE
    if num_cancelled_orders is None:
        num_cancelled_orders = 3
    if order_timestamps is None:
        order_timestamps = [
            start_timestamp,
            start_timestamp + timedelta(seconds=5),
        ]

    return SuspiciousSequence(
        account_id=account_id,
        product_id=product_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        total_buy_qty=total_buy_qty,
        total_sell_qty=total_sell_qty,
        detection_type="LAYERING",
        side=side,  # type: ignore[arg-type]
        num_cancelled_orders=num_cancelled_orders,
        order_timestamps=order_timestamps,
    )


def create_suspicious_sequence_wash_trading(
    account_id: str | None = None,
    product_id: str | None = None,
    start_timestamp: datetime | None = None,
    end_timestamp: datetime | None = None,
    total_buy_qty: int | None = None,
    total_sell_qty: int | None = None,
    alternation_percentage: float | None = None,
    price_change_percentage: float | None = None,
) -> SuspiciousSequence:
    """
    Factory function for creating WASH_TRADING SuspiciousSequence test data.

    Creates a SuspiciousSequence with detection_type="WASH_TRADING" and required
    wash trading-specific fields (alternation_percentage). Layering-specific fields
    (side, num_cancelled_orders, order_timestamps) are set to None.

    Args:
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        start_timestamp: Sequence start time. Defaults to 2025-01-15 10:30:00 UTC.
        end_timestamp: Sequence end time. Defaults to start_timestamp + 30 minutes.
        total_buy_qty: Total BUY quantity. Defaults to 5000.
        total_sell_qty: Total SELL quantity. Defaults to 5000.
        alternation_percentage: Alternation percentage (0-100). Defaults to 75.5.
        price_change_percentage: Price change percentage. Defaults to 2.5.

    Returns:
        SuspiciousSequence instance with detection_type="WASH_TRADING".

    Example:
        >>> sequence = create_suspicious_sequence_wash_trading(
        ...     account_id="ACC002",
        ...     alternation_percentage=80.0,
        ...     price_change_percentage=1.5
        ... )
        >>> assert sequence.detection_type == "WASH_TRADING"
        >>> assert sequence.alternation_percentage == 80.0
        >>> assert sequence.side is None
    """
    from layering_detection.models import SuspiciousSequence

    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if start_timestamp is None:
        start_timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    if end_timestamp is None:
        end_timestamp = start_timestamp + timedelta(minutes=30)
    if total_buy_qty is None:
        total_buy_qty = 5000
    if total_sell_qty is None:
        total_sell_qty = 5000
    if alternation_percentage is None:
        alternation_percentage = 75.5
    # price_change_percentage can be None (optional field)

    return SuspiciousSequence(
        account_id=account_id,
        product_id=product_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        total_buy_qty=total_buy_qty,
        total_sell_qty=total_sell_qty,
        detection_type="WASH_TRADING",
        side=None,
        num_cancelled_orders=None,
        order_timestamps=None,
        alternation_percentage=alternation_percentage,
        price_change_percentage=price_change_percentage,
    )


def create_suspicious_sequence(
    detection_type: str = "LAYERING",
    **kwargs: object,
) -> SuspiciousSequence:
    """
    Convenience factory function that delegates to type-specific factories.

    Creates a SuspiciousSequence by delegating to either
    create_suspicious_sequence_layering() or create_suspicious_sequence_wash_trading()
    based on detection_type.

    Args:
        detection_type: "LAYERING" or "WASH_TRADING". Defaults to "LAYERING".
        **kwargs: Additional arguments passed to the appropriate factory function.

    Returns:
        SuspiciousSequence instance with the specified detection_type.

    Example:
        >>> layering_seq = create_suspicious_sequence("LAYERING", side="BUY")
        >>> wash_seq = create_suspicious_sequence("WASH_TRADING", alternation_percentage=80.0)
    """
    if detection_type == "LAYERING":
        return create_suspicious_sequence_layering(**kwargs)  # type: ignore[arg-type]
    elif detection_type == "WASH_TRADING":
        return create_suspicious_sequence_wash_trading(**kwargs)  # type: ignore[arg-type]
    else:
        raise ValueError(f"Invalid detection_type: {detection_type} (must be 'LAYERING' or 'WASH_TRADING')")


def create_wash_trading_pattern(
    base_time: datetime | None = None,
    account_id: str | None = None,
    product_id: str | None = None,
    quantity: int = 2000,
    price_start: Decimal | str = "100.0",
    time_interval_minutes: int = 5,
) -> list[TransactionEvent]:
    """
    Factory function for creating a complete wash trading test pattern.

    Creates 6 alternating BUY/SELL trades that form a valid wash trading pattern:
    - 3 BUY trades and 3 SELL trades
    - 100% alternation (perfect BUY/SELL alternation)
    - Total volume >= 10,000 (6 trades * 2000 = 12,000)
    - All trades within 30 minutes (5 minutes apart = 25 minutes total)
    - Prices increment slightly for each trade

    Args:
        base_time: Starting timestamp. Defaults to 2025-01-01 09:00:00 UTC.
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        quantity: Quantity per trade. Defaults to 2000 (total volume = 12,000).
        price_start: Starting price. Defaults to Decimal("100.0").
        time_interval_minutes: Minutes between trades. Defaults to 5.

    Returns:
        List of 6 TransactionEvent instances forming a wash trading pattern.

    Example:
        >>> events = create_wash_trading_pattern(
        ...     account_id="ACC002",
        ...     product_id="AAPL",
        ...     quantity=3000
        ... )
        >>> assert len(events) == 6
        >>> assert events[0].side == "BUY"
        >>> assert events[1].side == "SELL"
        >>> assert all(e.event_type == "TRADE_EXECUTED" for e in events)
    """
    from decimal import Decimal

    if base_time is None:
        base_time = _DEFAULT_TIMESTAMP
    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if isinstance(price_start, str):
        price_start = Decimal(price_start)

    events: list[TransactionEvent] = []
    sides = ["BUY", "SELL", "BUY", "SELL", "BUY", "SELL"]  # Perfect alternation

    for i, side in enumerate(sides):
        # Price increments by 0.5 for each trade
        price = price_start + Decimal(str(i * 0.5))
        timestamp = base_time + timedelta(minutes=i * time_interval_minutes)

        event = create_transaction_event(
            timestamp=timestamp,
            account_id=account_id,
            product_id=product_id,
            side=side,  # type: ignore[arg-type]
            price=price,
            quantity=quantity,
            event_type="TRADE_EXECUTED",  # type: ignore[arg-type]
        )
        events.append(event)

    return events


def create_layering_pattern(
    base_time: datetime | None = None,
    account_id: str | None = None,
    product_id: str | None = None,
    side: str = "BUY",
    order_quantity: int = 1000,
    order_price_start: Decimal | str = "100.0",
    cancel_price_start: Decimal | str = "100.0",
    trade_quantity: int = 5000,
    trade_price: Decimal | str | None = None,
    opposite_side: str | None = None,
) -> list[TransactionEvent]:
    """
    Factory function for creating a complete layering test pattern.

    Creates a valid layering pattern with:
    - 3 ORDER_PLACED events on the same side (within 10 seconds)
    - 3 ORDER_CANCELLED events (within 5 seconds of last order)
    - 1 TRADE_EXECUTED event on opposite side (within 2 seconds of last cancellation)

    All events are for the same account_id and product_id.

    Args:
        base_time: Starting timestamp for first order. Defaults to 2025-01-01 09:00:00 UTC.
        account_id: Account identifier. Defaults to "ACC001".
        product_id: Product identifier. Defaults to "IBM".
        side: Side for orders and cancellations ("BUY" or "SELL"). Defaults to "BUY".
        order_quantity: Quantity for each order. Defaults to 1000.
        order_price_start: Starting price for orders. Defaults to Decimal("100.0").
        cancel_price_start: Starting price for cancellations. Defaults to Decimal("100.0").
        trade_quantity: Quantity for opposite-side trade. Defaults to 5000.
        trade_price: Price for opposite-side trade. Defaults to order_price_start - 0.5 for BUY,
            order_price_start + 0.5 for SELL.
        opposite_side: Side for opposite trade. Defaults to "SELL" if side is "BUY", "BUY" if side is "SELL".

    Returns:
        List of 7 TransactionEvent instances forming a layering pattern:
        [3 ORDER_PLACED, 3 ORDER_CANCELLED, 1 TRADE_EXECUTED]

    Example:
        >>> events = create_layering_pattern(
        ...     account_id="ACC002",
        ...     product_id="AAPL",
        ...     side="SELL"
        ... )
        >>> assert len(events) == 7
        >>> assert all(e.event_type == "ORDER_PLACED" for e in events[:3])
        >>> assert all(e.event_type == "ORDER_CANCELLED" for e in events[3:6])
        >>> assert events[6].event_type == "TRADE_EXECUTED"
        >>> assert events[6].side == "BUY"  # Opposite of SELL
    """
    from decimal import Decimal

    if base_time is None:
        base_time = _DEFAULT_TIMESTAMP
    if account_id is None:
        account_id = _DEFAULT_ACCOUNT_ID
    if product_id is None:
        product_id = _DEFAULT_PRODUCT_ID
    if isinstance(order_price_start, str):
        order_price_start = Decimal(order_price_start)
    if isinstance(cancel_price_start, str):
        cancel_price_start = Decimal(cancel_price_start)
    if opposite_side is None:
        opposite_side = "SELL" if side == "BUY" else "BUY"
    if trade_price is None:
        # Default trade price: slightly lower for BUY orders, slightly higher for SELL orders
        if side == "BUY":
            trade_price = order_price_start - Decimal("0.5")
        else:
            trade_price = order_price_start + Decimal("0.5")
    elif isinstance(trade_price, str):
        trade_price = Decimal(trade_price)

    events: list[TransactionEvent] = []

    # 3 ORDER_PLACED events within 10 seconds (at 0s, 1s, 2s)
    for i in range(3):
        price = order_price_start + Decimal(str(i * 0.5))
        timestamp = base_time + timedelta(seconds=i)
        event = create_transaction_event(
            timestamp=timestamp,
            account_id=account_id,
            product_id=product_id,
            side=side,  # type: ignore[arg-type]
            price=price,
            quantity=order_quantity,
            event_type="ORDER_PLACED",  # type: ignore[arg-type]
        )
        events.append(event)

    # 3 ORDER_CANCELLED events within 5 seconds of last order (at 3s, 4s, 5s)
    # Last order is at base_time + 2s, so cancellations must be <= base_time + 7s
    for i in range(3):
        price = cancel_price_start + Decimal(str(i * 0.5))
        timestamp = base_time + timedelta(seconds=3 + i)
        event = create_transaction_event(
            timestamp=timestamp,
            account_id=account_id,
            product_id=product_id,
            side=side,  # type: ignore[arg-type]
            price=price,
            quantity=order_quantity,
            event_type="ORDER_CANCELLED",  # type: ignore[arg-type]
        )
        events.append(event)

    # 1 TRADE_EXECUTED event on opposite side within 2 seconds of last cancellation
    # Last cancellation is at base_time + 5s, so trade must be <= base_time + 7s
    # We'll place it at base_time + 6s to be safe
    trade_timestamp = base_time + timedelta(seconds=6)
    trade_event = create_transaction_event(
        timestamp=trade_timestamp,
        account_id=account_id,
        product_id=product_id,
        side=opposite_side,  # type: ignore[arg-type]
        price=trade_price,
        quantity=trade_quantity,
        event_type="TRADE_EXECUTED",  # type: ignore[arg-type]
    )
    events.append(trade_event)

    return events

