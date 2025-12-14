"""
I/O utilities for the layering detection analytics.

This module handles reading the input CSV into `TransactionEvent` instances.
Writing of outputs (suspicious_accounts.csv) will be added in a later task.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, List

from ..models import EventType, Side, TransactionEvent, SuspiciousSequence
from .security_utils import sanitize_for_csv


def _parse_timestamp(raw: str) -> datetime:
    """
    Parse ISO-like timestamps used in `transactions.csv`.

    The sample data uses a trailing 'Z' (UTC designator), which
    `datetime.fromisoformat` does not accept directly, so we normalise it.
    """
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Invalid timestamp format: {raw!r}") from exc


def _parse_side(raw: str) -> Side:
    from typing import cast

    value = raw.strip().upper()
    if value not in ("BUY", "SELL"):
        raise ValueError(f"Invalid side: {raw!r}")
    # Cast is safe after validation - value is guaranteed to be "BUY" or "SELL"
    return cast(Side, value)


def _parse_event_type(raw: str) -> EventType:
    from typing import cast

    value = raw.strip().upper()
    allowed: tuple[str, ...] = ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED")
    if value not in allowed:
        raise ValueError(f"Invalid event_type: {raw!r}")
    # Cast is safe after validation - value is guaranteed to be one of the allowed types
    return cast(EventType, value)


def _parse_price(raw: str) -> Decimal:
    try:
        price = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid price: {raw!r}") from exc
    if price <= 0:
        raise ValueError(f"Price must be positive, got {price!r}")
    return price


def _parse_quantity(raw: str) -> int:
    try:
        qty = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid quantity: {raw!r}") from exc
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty!r}")
    return qty


logger = logging.getLogger(__name__)


def read_transactions(path: Path) -> List[TransactionEvent]:
    """
    Read `transactions.csv` into a list of `TransactionEvent` instances.

    - Invalid rows are skipped with a simple printed warning (no logging framework yet).
    - The caller is responsible for grouping and sorting.
    """
    events: list[TransactionEvent] = []

    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_fields = {
            "timestamp",
            "account_id",
            "product_id",
            "side",
            "price",
            "quantity",
            "event_type",
        }
        missing = required_fields.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        for idx, row in enumerate(reader, start=2):  # header is line 1
            try:
                timestamp = _parse_timestamp(row["timestamp"])
                account_id = (row["account_id"] or "").strip()
                product_id = (row["product_id"] or "").strip()
                side = _parse_side(row["side"])
                price = _parse_price(row["price"])
                quantity = _parse_quantity(row["quantity"])
                event_type = _parse_event_type(row["event_type"])

                if not account_id:
                    raise ValueError("Empty account_id")
                if not product_id:
                    raise ValueError("Empty product_id")

                events.append(
                    TransactionEvent(
                        timestamp=timestamp,
                        account_id=account_id,
                        product_id=product_id,
                        side=side,
                        price=price,
                        quantity=quantity,
                        event_type=event_type,
                    )
                )
            except Exception as exc:
                # Emit a structured warning so callers can control log handling.
                logger.warning(
                    "Skipping invalid row %d in %s: %s", idx, path, exc
                )

    return events


def write_suspicious_accounts(path: Path, sequences: Iterable[SuspiciousSequence]) -> None:
    """
    Write detected suspicious sequences to `suspicious_accounts.csv`.

    Output CSV Schema:
    
    **Required Columns (all detection types):**
    - `account_id` (str): Suspicious account identifier
    - `product_id` (str): Product where activity was detected
    - `total_buy_qty` (int): Total BUY quantity during the pattern window
    - `total_sell_qty` (int): Total SELL quantity during the pattern window
    - `num_cancelled_orders` (int): Count of cancelled orders in the sequence
        - For LAYERING: Actual count of cancelled orders
        - For WASH_TRADING: Always 0 (not applicable)
    - `detected_timestamp` (ISO datetime): Timestamp when detection occurred
        - For LAYERING: Timestamp of the opposite-side trade that completes the pattern
        - For WASH_TRADING: Timestamp of the last trade in the 30-minute window
    
    **Additional Columns (for multi-algorithm support):**
    - `detection_type` (str): Type of detection pattern
        - `"LAYERING"`: Layering manipulation pattern (≥3 orders, cancellations, opposite trade)
        - `"WASH_TRADING"`: Wash trading pattern (repeated buy/sell with high alternation)
    
    **Wash Trading Specific Columns (empty for LAYERING):**
    - `alternation_percentage` (float | empty): Percentage of side switches between consecutive trades
        - Format: Decimal number with 2 decimal places (e.g., "60.00")
        - Empty string ("") for LAYERING detections
        - Only populated for WASH_TRADING when ≥60% alternation is detected
    
    - `price_change_percentage` (float | empty): Price change during the detection window
        - Format: Decimal number with 2 decimal places (e.g., "1.50")
        - Empty string ("") if:
            - Detection type is LAYERING (not applicable)
            - Price change is <1% (optional bonus threshold not met)
            - No price change occurred
        - Only populated for WASH_TRADING when price change ≥1% (optional bonus criterion)
    
    Examples:
        Layering detection row:
            account_id,product_id,total_buy_qty,total_sell_qty,num_cancelled_orders,detected_timestamp,detection_type,alternation_percentage,price_change_percentage
            ACC001,IBM,3000,2000,3,2025-01-15T10:30:00Z,LAYERING,,
        
        Wash trading detection row:
            account_id,product_id,total_buy_qty,total_sell_qty,num_cancelled_orders,detected_timestamp,detection_type,alternation_percentage,price_change_percentage
            ACC002,GOOG,12000,12000,0,2025-01-15T11:00:00Z,WASH_TRADING,80.00,1.25
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "account_id",
        "product_id",
        "total_buy_qty",
        "total_sell_qty",
        "num_cancelled_orders",
        "detected_timestamp",
        "detection_type",
        "alternation_percentage",
        "price_change_percentage",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for seq in sequences:
            # Handle optional fields (None for wash trading)
            num_cancelled_orders = (
                seq.num_cancelled_orders if seq.num_cancelled_orders is not None else 0
            )
            alternation_pct = (
                f"{seq.alternation_percentage:.2f}"
                if seq.alternation_percentage is not None
                else ""
            )
            price_change_pct = (
                f"{seq.price_change_percentage:.2f}"
                if seq.price_change_percentage is not None
                else ""
            )
            writer.writerow(
                {
                    "account_id": sanitize_for_csv(seq.account_id),
                    "product_id": sanitize_for_csv(seq.product_id),
                    "total_buy_qty": seq.total_buy_qty,
                    "total_sell_qty": seq.total_sell_qty,
                    "num_cancelled_orders": num_cancelled_orders,
                    "detected_timestamp": seq.end_timestamp.isoformat(),
                    "detection_type": seq.detection_type,
                    "alternation_percentage": alternation_pct,
                    "price_change_percentage": price_change_pct,
                }
            )
