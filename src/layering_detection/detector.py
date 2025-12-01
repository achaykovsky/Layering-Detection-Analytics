"""
Detection engine for simplified layering patterns.

Implements T5–T8 from the planning:
- Group events by (account_id, product_id) and sort by timestamp.
- Detect layering sequences according to the PRD timing rules.
- Compute per-sequence aggregation metrics.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import DefaultDict, Dict, Iterable, List, Tuple

from .models import Side, SuspiciousSequence, TransactionEvent


AccountProductKey = Tuple[str, str]


def group_events_by_account_product(
    events: Iterable[TransactionEvent],
) -> Dict[AccountProductKey, List[TransactionEvent]]:
    """
    Group events by (account_id, product_id) and sort each group by timestamp.
    """
    grouped: DefaultDict[AccountProductKey, List[TransactionEvent]] = defaultdict(list)
    for event in events:
        grouped[(event.account_id, event.product_id)].append(event)

    for key in grouped:
        grouped[key].sort(key=lambda e: e.timestamp)

    return dict(grouped)


def _detect_sequences_for_group(
    account_id: str,
    product_id: str,
    events: List[TransactionEvent],
) -> List[SuspiciousSequence]:
    """
    Detect suspicious layering sequences within a single (account_id, product_id) group.

    Notes / assumptions (see specs for clarified behavior):
    - Orders lack explicit IDs, so we approximate "cancelled before execution" by
      counting ORDER_CANCELLED events within the timing window on the spoof side.
    - `detected_timestamp` is the timestamp of the opposite-side trade that completes
      the pattern.
    - Once a sequence is detected, we move the detection window forward so that an
      individual spoof-side order belongs to at most one sequence.
    """
    sequences: list[SuspiciousSequence] = []

    orders_window = timedelta(seconds=10)
    cancel_window = timedelta(seconds=5)
    opposite_trade_window = timedelta(seconds=2)

    n = len(events)
    idx = 0

    # Events are already sorted by timestamp at the group level.
    while idx < n:
        ev = events[idx]
        if ev.event_type != "ORDER_PLACED":
            idx += 1
            continue

        side: Side = ev.side  # type: ignore[assignment]
        start_ts = ev.timestamp

        # 1) Find all same-side ORDER_PLACED within 10 seconds of the first.
        window_orders: list[TransactionEvent] = [ev]
        last_order_idx = idx

        j = idx + 1
        while j < n and events[j].timestamp - start_ts <= orders_window:
            cand = events[j]
            if cand.event_type == "ORDER_PLACED" and cand.side == side:
                window_orders.append(cand)
                last_order_idx = j
            j += 1

        if len(window_orders) < 3:
            idx += 1
            continue

        # 2) Ensure there are at least 3 cancellations for that side
        # within 5 seconds of the last placed order in the window.
        last_order_time = window_orders[-1].timestamp
        cancel_deadline = last_order_time + cancel_window
        cancellations: list[TransactionEvent] = [
            e
            for e in events
            if e.event_type == "ORDER_CANCELLED"
            and e.side == side
            and start_ts <= e.timestamp <= cancel_deadline
        ]
        if len(cancellations) < 3:
            idx += 1
            continue

        last_cancel_time: datetime = max(e.timestamp for e in cancellations)

        # 3) Find opposite-side trade within 2 seconds after last cancellation.
        opposite_side: Side = "SELL" if side == "BUY" else "BUY"  # type: ignore[assignment]
        trade_deadline = last_cancel_time + opposite_trade_window
        opposite_trade: TransactionEvent | None = None
        for e in events:
            if (
                e.event_type == "TRADE_EXECUTED"
                and e.side == opposite_side
                and last_cancel_time <= e.timestamp <= trade_deadline
            ):
                opposite_trade = e
                break

        if opposite_trade is None:
            idx += 1
            continue

        # Compute aggregation metrics over the pattern window.
        end_ts = opposite_trade.timestamp
        spoof_cancel_qty = 0
        opp_trade_qty = 0
        num_cancelled_orders = 0
        order_timestamps: list[datetime] = [e.timestamp for e in window_orders]

        for e in events:
            if not (start_ts <= e.timestamp <= end_ts):
                continue

            if e.event_type == "ORDER_CANCELLED" and e.side == side:
                # Spoof-side cancelled orders.
                spoof_cancel_qty += e.quantity
                num_cancelled_orders += 1
            elif e.event_type == "TRADE_EXECUTED" and e.side == opposite_side:
                # Opposite-side executed trades completing the pattern.
                opp_trade_qty += e.quantity

        # Map spoof/opposite volumes into total_buy_qty and total_sell_qty.
        if side == "BUY":
            total_buy_qty = spoof_cancel_qty
            total_sell_qty = opp_trade_qty
        else:  # side == "SELL"
            total_sell_qty = spoof_cancel_qty
            total_buy_qty = opp_trade_qty

        sequences.append(
            SuspiciousSequence(
                account_id=account_id,
                product_id=product_id,
                side=side,
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                total_buy_qty=total_buy_qty,
                total_sell_qty=total_sell_qty,
                num_cancelled_orders=num_cancelled_orders,
                order_timestamps=order_timestamps,
            )
        )

        # Move index forward so spoof orders used in this sequence are not reused.
        idx = last_order_idx + 1

    return sequences


def detect_suspicious_sequences(
    events: Iterable[TransactionEvent],
) -> List[SuspiciousSequence]:
    """
    Top-level detection function:

    - Groups events by (account_id, product_id).
    - Runs layering pattern detection per group.
    """
    grouped = group_events_by_account_product(events)
    all_sequences: list[SuspiciousSequence] = []

    for (account_id, product_id), group_events in grouped.items():
        all_sequences.extend(
            _detect_sequences_for_group(account_id, product_id, group_events)
        )

    return all_sequences


