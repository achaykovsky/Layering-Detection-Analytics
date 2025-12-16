"""
Conversion utilities between domain models and API DTOs.

Provides bidirectional conversion functions for serialization at service boundaries.
Handles datetime → ISO string and Decimal → string conversions with precision preservation.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from layering_detection.models import (
    DetectionType,
    EventType,
    Side,
    SuspiciousSequence,
    TransactionEvent,
)

from .api_models import SuspiciousSequenceDTO, TransactionEventDTO


def transaction_event_to_dto(event: TransactionEvent) -> TransactionEventDTO:
    """
    Convert domain TransactionEvent to API DTO.

    Converts datetime to ISO format string and Decimal to string to preserve precision.

    Args:
        event: Domain TransactionEvent model

    Returns:
        TransactionEventDTO with serialized datetime and Decimal fields

    Example:
        >>> from datetime import datetime
        >>> from decimal import Decimal
        >>> event = TransactionEvent(
        ...     timestamp=datetime(2025, 1, 15, 10, 30, 0),
        ...     account_id="ACC001",
        ...     product_id="IBM",
        ...     side="BUY",
        ...     price=Decimal("100.50"),
        ...     quantity=1000,
        ...     event_type="ORDER_PLACED"
        ... )
        >>> dto = transaction_event_to_dto(event)
        >>> dto.timestamp
        '2025-01-15T10:30:00'
        >>> dto.price
        '100.50'
    """
    return TransactionEventDTO(
        timestamp=event.timestamp.isoformat(),
        account_id=event.account_id,
        product_id=event.product_id,
        side=event.side,
        price=str(event.price),
        quantity=event.quantity,
        event_type=event.event_type,
    )


def dto_to_transaction_event(dto: TransactionEventDTO) -> TransactionEvent:
    """
    Convert API DTO to domain TransactionEvent.

    Converts ISO format datetime string to datetime and string to Decimal.

    Args:
        dto: TransactionEventDTO from API

    Returns:
        TransactionEvent domain model

    Raises:
        ValueError: If datetime or Decimal conversion fails

    Example:
        >>> dto = TransactionEventDTO(
        ...     timestamp="2025-01-15T10:30:00",
        ...     account_id="ACC001",
        ...     product_id="IBM",
        ...     side="BUY",
        ...     price="100.50",
        ...     quantity=1000,
        ...     event_type="ORDER_PLACED"
        ... )
        >>> event = dto_to_transaction_event(dto)
        >>> isinstance(event.timestamp, datetime)
        True
        >>> isinstance(event.price, Decimal)
        True
    """
    # Parse ISO datetime string (handles timezone-aware strings)
    timestamp_str = dto.timestamp
    if timestamp_str.endswith("Z"):
        timestamp_str = timestamp_str.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(timestamp_str)

    # Parse Decimal from string (preserves precision)
    price = Decimal(dto.price)

    return TransactionEvent(
        timestamp=timestamp,
        account_id=dto.account_id,
        product_id=dto.product_id,
        side=dto.side,
        price=price,
        quantity=dto.quantity,
        event_type=dto.event_type,
    )


def suspicious_sequence_to_dto(seq: SuspiciousSequence) -> SuspiciousSequenceDTO:
    """
    Convert domain SuspiciousSequence to API DTO.

    Converts datetime fields to ISO format strings and handles optional fields
    based on detection type (LAYERING vs WASH_TRADING).

    Args:
        seq: Domain SuspiciousSequence model

    Returns:
        SuspiciousSequenceDTO with serialized datetime fields

    Example:
        >>> from datetime import datetime
        >>> seq = SuspiciousSequence(
        ...     account_id="ACC001",
        ...     product_id="IBM",
        ...     start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
        ...     end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
        ...     total_buy_qty=5000,
        ...     total_sell_qty=0,
        ...     detection_type="LAYERING",
        ...     side="BUY",
        ...     num_cancelled_orders=3,
        ...     order_timestamps=[datetime(2025, 1, 15, 10, 30, 0)]
        ... )
        >>> dto = suspicious_sequence_to_dto(seq)
        >>> dto.start_timestamp
        '2025-01-15T10:30:00'
    """
    # Convert order_timestamps list if present
    order_timestamps: list[str] | None = None
    if seq.order_timestamps is not None:
        order_timestamps = [ts.isoformat() for ts in seq.order_timestamps]

    return SuspiciousSequenceDTO(
        account_id=seq.account_id,
        product_id=seq.product_id,
        start_timestamp=seq.start_timestamp.isoformat(),
        end_timestamp=seq.end_timestamp.isoformat(),
        total_buy_qty=seq.total_buy_qty,
        total_sell_qty=seq.total_sell_qty,
        detection_type=seq.detection_type,
        side=seq.side,
        num_cancelled_orders=seq.num_cancelled_orders,
        order_timestamps=order_timestamps,
        alternation_percentage=seq.alternation_percentage,
        price_change_percentage=seq.price_change_percentage,
    )


def dto_to_suspicious_sequence(dto: SuspiciousSequenceDTO) -> SuspiciousSequence:
    """
    Convert API DTO to domain SuspiciousSequence.

    Converts ISO format datetime strings to datetime objects and handles optional fields.

    Args:
        dto: SuspiciousSequenceDTO from API

    Returns:
        SuspiciousSequence domain model

    Raises:
        ValueError: If datetime conversion fails

    Example:
        >>> dto = SuspiciousSequenceDTO(
        ...     account_id="ACC001",
        ...     product_id="IBM",
        ...     start_timestamp="2025-01-15T10:30:00",
        ...     end_timestamp="2025-01-15T10:30:10",
        ...     total_buy_qty=5000,
        ...     total_sell_qty=0,
        ...     detection_type="LAYERING",
        ...     side="BUY",
        ...     num_cancelled_orders=3,
        ...     order_timestamps=["2025-01-15T10:30:00"]
        ... )
        >>> seq = dto_to_suspicious_sequence(dto)
        >>> isinstance(seq.start_timestamp, datetime)
        True
    """
    # Parse ISO datetime strings (handles timezone-aware strings)
    def parse_datetime(ts_str: str) -> datetime:
        """Parse ISO datetime string, handling Z suffix."""
        if ts_str.endswith("Z"):
            ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)

    start_timestamp = parse_datetime(dto.start_timestamp)
    end_timestamp = parse_datetime(dto.end_timestamp)

    # Convert order_timestamps list if present
    order_timestamps: list[datetime] | None = None
    if dto.order_timestamps is not None:
        order_timestamps = [parse_datetime(ts) for ts in dto.order_timestamps]

    return SuspiciousSequence(
        account_id=dto.account_id,
        product_id=dto.product_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        total_buy_qty=dto.total_buy_qty,
        total_sell_qty=dto.total_sell_qty,
        detection_type=dto.detection_type,
        side=dto.side,
        num_cancelled_orders=dto.num_cancelled_orders,
        order_timestamps=order_timestamps,
        alternation_percentage=dto.alternation_percentage,
        price_change_percentage=dto.price_change_percentage,
    )

