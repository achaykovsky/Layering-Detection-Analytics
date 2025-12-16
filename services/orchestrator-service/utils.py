"""
Orchestrator Service Utility Functions.

Utility functions for request ID generation, event fingerprinting, and other helpers.
"""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from layering_detection.models import TransactionEvent


def generate_request_id() -> str:
    """
    Generate unique request ID for pipeline execution.

    Returns:
        UUID v4 string representation

    Examples:
        >>> request_id = generate_request_id()
        >>> len(request_id)
        36
        >>> request_id.count('-')
        4
    """
    return str(uuid4())


def hash_events(events: list[TransactionEvent]) -> str:
    """
    Generate deterministic SHA256 fingerprint for event set.

    Creates a deterministic hash by:
    1. Extracting event signatures (timestamp, account_id, product_id, side, price, quantity, event_type)
    2. Sorting signatures to ensure order-independent hashing
    3. Generating SHA256 hash of sorted signatures
    4. Returning hexdigest (64 characters)

    Same events always produce the same hash, regardless of order.
    Different events produce different hashes.

    Args:
        events: List of TransactionEvent domain models

    Returns:
        SHA256 hexdigest string (64 characters, lowercase)

    Examples:
        >>> from datetime import datetime
        >>> from decimal import Decimal
        >>> from layering_detection.models import TransactionEvent
        >>> events = [
        ...     TransactionEvent(
        ...         timestamp=datetime(2025, 1, 15, 10, 30, 0),
        ...         account_id="ACC001",
        ...         product_id="IBM",
        ...         side="BUY",
        ...         price=Decimal("100.50"),
        ...         quantity=1000,
        ...         event_type="ORDER_PLACED",
        ...     ),
        ... ]
        >>> fingerprint = hash_events(events)
        >>> len(fingerprint)
        64
        >>> isinstance(fingerprint, str)
        True
    """
    # Extract event signatures (all fields that uniquely identify an event)
    event_signatures = [
        (
            event.timestamp.isoformat(),
            event.account_id,
            event.product_id,
            event.side,
            str(event.price),  # Convert Decimal to string for consistent serialization
            event.quantity,
            event.event_type,
        )
        for event in events
    ]

    # Sort signatures to ensure order-independent hashing
    # This ensures same events in different order produce same hash
    sorted_signatures = sorted(event_signatures)

    # Generate SHA256 hash of sorted signatures
    # Use JSON serialization for consistent string representation
    signatures_json = json.dumps(sorted_signatures, sort_keys=False)  # Already sorted
    hash_bytes = hashlib.sha256(signatures_json.encode("utf-8"))

    # Return hexdigest (64 characters, lowercase)
    return hash_bytes.hexdigest()

