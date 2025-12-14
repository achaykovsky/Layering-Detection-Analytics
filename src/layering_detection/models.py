"""
Domain models for the layering detection analytics.

These models are intentionally kept framework-agnostic (plain dataclasses)
to keep dependencies minimal and make reasoning/testing straightforward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from .utils.detection_utils import validate_positive


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
class DetectionConfig:
    """
    Configuration for layering detection timing windows.

    Default values match current hard-coded timing windows:
    - orders_window: 10 seconds (window for finding same-side ORDER_PLACED events)
    - cancel_window: 5 seconds (window for finding ORDER_CANCELLED events after last order)
    - opposite_trade_window: 2 seconds (window for finding opposite-side TRADE_EXECUTED after last cancellation)

    All timing windows must be positive (greater than zero). Negative or zero values
    will raise ValueError during initialization.
    """

    orders_window: timedelta = timedelta(seconds=10)
    cancel_window: timedelta = timedelta(seconds=5)
    opposite_trade_window: timedelta = timedelta(seconds=2)

    def __post_init__(self) -> None:
        """
        Validate that all timing windows are positive (not negative or zero).

        Raises:
            ValueError: If any timing window is negative or zero, with a clear
                message indicating which window is invalid.
        """
        validate_positive(self.orders_window, "orders_window")
        validate_positive(self.cancel_window, "cancel_window")
        validate_positive(self.opposite_trade_window, "opposite_trade_window")


@dataclass(frozen=True)
class WashTradingConfig:
    """
    Configuration for wash trading detection thresholds and timing windows.

    Default values match current hard-coded thresholds:
    - min_buy_trades: 3 (minimum number of BUY trades required)
    - min_sell_trades: 3 (minimum number of SELL trades required)
    - min_alternation_percentage: 60.0 (minimum alternation percentage required)
    - min_total_volume: 10000 (minimum total volume required)
    - window_size: 30 minutes (sliding window size for detection)
    - optional_price_change_threshold: 1.0 (optional bonus threshold for price change percentage)

    All numeric thresholds must be positive (greater than zero). Negative or zero values
    will raise ValueError during initialization.
    """

    min_buy_trades: int = 3
    min_sell_trades: int = 3
    min_alternation_percentage: float = 60.0
    min_total_volume: int = 10000
    window_size: timedelta = timedelta(minutes=30)
    optional_price_change_threshold: float = 1.0

    def __post_init__(self) -> None:
        """
        Validate that all thresholds are positive (greater than zero).

        Raises:
            ValueError: If any threshold is negative or zero, with a clear
                message indicating which threshold is invalid.
        """
        validate_positive(self.min_buy_trades, "min_buy_trades")
        validate_positive(self.min_sell_trades, "min_sell_trades")
        validate_positive(
            self.min_alternation_percentage, "min_alternation_percentage"
        )
        validate_positive(self.min_total_volume, "min_total_volume")
        validate_positive(self.window_size, "window_size")
        validate_positive(
            self.optional_price_change_threshold, "optional_price_change_threshold"
        )


DetectionType = Literal["LAYERING", "WASH_TRADING"]


@dataclass(frozen=True)
class SuspiciousSequence:
    """
    Represents a single detected suspicious sequence (layering or wash trading).

    Aggregated metrics (total_buy_qty, etc.) are computed at detection time.

    Fields vary by detection type:
    - LAYERING: side, num_cancelled_orders, order_timestamps are required
    - WASH_TRADING: side, num_cancelled_orders, order_timestamps are None
                   alternation_percentage is required, price_change_percentage is optional
    """

    account_id: str
    product_id: str
    start_timestamp: datetime
    end_timestamp: datetime  # detection time (exact semantics documented in detector)
    total_buy_qty: int
    total_sell_qty: int
    detection_type: DetectionType = "LAYERING"  # Default for backward compatibility
    side: Side | None = None  # Required for LAYERING, None for WASH_TRADING
    num_cancelled_orders: int | None = None  # Required for LAYERING, None for WASH_TRADING
    order_timestamps: list[datetime] | None = None  # Required for LAYERING, None for WASH_TRADING
    alternation_percentage: float | None = None  # Required for WASH_TRADING, None for LAYERING
    price_change_percentage: float | None = None  # Optional for WASH_TRADING, None for LAYERING


