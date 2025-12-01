"""
Domain models for the layering detection analytics.

These models are intentionally kept framework-agnostic (plain dataclasses)
to keep dependencies minimal and make reasoning/testing straightforward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


Side = Literal["BUY", "SELL"]
EventType = Literal["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]


@dataclass(frozen=True)
class TransactionEvent:
    """
    Single row from `transactions.csv`, represented as a typed domain object.
    """

    timestamp: datetime
    account_id: str
    product_id: str
    side: Side
    price: Decimal
    quantity: int
    event_type: EventType


@dataclass(frozen=True)
class SuspiciousSequence:
    """
    Represents a single detected suspicious layering sequence.

    Aggregated metrics (total_buy_qty, etc.) are computed at detection time.
    """

    account_id: str
    product_id: str
    side: Side  # side of the non-bona-fide orders
    start_timestamp: datetime
    end_timestamp: datetime  # detection time (exact semantics documented in detector)
    total_buy_qty: int
    total_sell_qty: int
    num_cancelled_orders: int
    order_timestamps: list[datetime]


