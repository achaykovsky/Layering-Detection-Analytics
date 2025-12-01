# Layering Detection Feature

## Overview
Implements detection of simplified layering manipulation patterns in intraday order/trade data and produces a summary of suspicious accounts and products.

## Requirements
- [ ] Detect sequences where a trader places ≥3 orders on one side (BUY or SELL) within a 10-second window.
- [ ] Ensure those orders are cancelled before execution, with each cancellation occurring within 5 seconds of the corresponding placement.
- [ ] Confirm a trade on the opposite side (relative to the non-bona-fide orders) is executed within 2 seconds after the last cancellation.
- [ ] Treat each qualifying sequence as a suspicious layering event and flag the associated `account_id` and `product_id`.
- [ ] For each suspicious sequence, compute spoof-side and opposite-side volumes:
  - Spoof side = sum of quantities of the cancelled spoof orders.
  - Opposite side = sum of quantities of the opposite-side executed trades that complete the pattern.
- [ ] For each suspicious sequence, count cancelled orders involved in the suspicious sequence.

## Acceptance Criteria
- [ ] Given synthetic data that exactly matches the 3-step pattern, the system flags the correct `account_id` and `product_id`.
- [ ] Given data with ≥3 orders on one side that are not cancelled or where timings exceed thresholds, no layering detection is triggered.
- [ ] The detection respects strict timing constraints:
  - Orders must be placed within 10 seconds of each other on the same side.
  - Cancellations must occur within 5 seconds of each order’s placement.
  - The opposite-side trade must occur within 2 seconds after the last cancellation.
- [ ] Multiple distinct suspicious sequences for the same account/product are handled deterministically (see data spec for aggregation rules).
- [ ] Unit tests cover positive cases (true layering), negative cases (similar but non-qualifying patterns), and the `ACC 050` override.

## Technical Details
- Time windows:
  - Use `timestamp` as ISO datetime; parse into timezone-aware `datetime` objects.
  - Define time deltas:
    - `orders_window = 10 seconds`
    - `cancel_window = 5 seconds` from placement
    - `opposite_trade_window = 2 seconds` from last cancellation
- Detection approach (high-level):
  - Group records by `(account_id, product_id)`.
  - Within each group, sort by `timestamp`.
  - Identify candidate sequences of `ORDER_PLACED` events on the same `side` within 10 seconds.
  - Verify that each candidate order is followed by an `ORDER_CANCELLED` within 5 seconds **and that the order was not executed before cancellation** (partially executed orders do **not** count toward the ≥3 cancelled orders condition).
  - Search for a `TRADE_EXECUTED` on the opposite side within 2 seconds after the last cancellation.
  - Once a sequence is detected for a given `(account_id, product_id)`, advance the detection window so that an individual order belongs to at most one detection sequence.
- Sequence aggregation:
  - For each detected suspicious sequence, compute:
    - `total_buy_qty`: spoof-side + opposite-side executed volume on BUY, as applicable:
      - If BUY is spoof side: sum of quantities of cancelled BUY spoof orders.
      - If BUY is opposite side: sum of quantities of BUY `TRADE_EXECUTED` trades that complete the pattern.
    - `total_sell_qty`: spoof-side + opposite-side executed volume on SELL, symmetric to BUY.
    - `num_cancelled_orders`: count of spoof-side cancelled orders in the sequence.
  - Define the `detected_timestamp` as the timestamp of the opposite-side `TRADE_EXECUTED` that completes the pattern.

## Clarifications from Interviewer
- If the same `(account_id, product_id)` produces more than one layering episode, multiple rows may appear in `suspicious_accounts.csv`—one row per sequence.
- An individual order should belong to at most one detection window (once a sequence is detected, move the window forward).
- `detected_timestamp` is the timestamp of the opposite-side `TRADE_EXECUTED` event that completes the pattern.
- Partially executed orders do **not** count toward the “≥3 cancelled orders” condition because they were not cancelled before execution.

## Related Specs
- `specs/requirements-layering-detection.md`
- `specs/data-layering-detection.md`
- `specs/deployment-layering-detection.md`


