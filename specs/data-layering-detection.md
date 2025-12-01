# Data Model – Layering Detection

## Overview
Defines the data structures, fields, and semantics for ingesting transactions and producing suspicious account outputs for the layering detection analytics.

## Requirements
- [ ] Accept a single input CSV `input/transactions.csv` with the PRD-defined schema.
- [ ] Treat each row as an event in a time-ordered event stream.
- [ ] Ensure robust parsing and validation of all fields (type, allowed values, missing data).
- [ ] Provide internal domain models for orders, cancellations, and trades.
- [ ] Generate a single output CSV `output/suspicious_accounts.csv` with the specified schema.

## Input Schema
- Source file: `input/transactions.csv`
- Columns:
  - `timestamp`: ISO datetime of event (e.g., `2024-01-01T09:30:00Z`).
  - `account_id`: Trader or account identifier (string).
  - `product_id`: Symbol or instrument traded (string).
  - `side`: `BUY` or `SELL`.
  - `price`: Order or trade price (numeric, decimal).
  - `quantity`: Order or trade size (integer).
  - `event_type`: One of `ORDER_PLACED`, `ORDER_CANCELLED`, `TRADE_EXECUTED`.

### Validation Rules
- [ ] Reject or log rows with invalid `timestamp` format.
- [ ] Enforce `side ∈ {BUY, SELL}`.
- [ ] Enforce `quantity > 0`.
- [ ] Enforce `price > 0`.
- [ ] Enforce `event_type ∈ {ORDER_PLACED, ORDER_CANCELLED, TRADE_EXECUTED}`.
- [ ] Decide on behavior for invalid rows (skip with log vs hard fail) and document it.

## Output Schema
- Target file: `output/suspicious_accounts.csv`
- Columns:
  - `account_id`: Suspicious account (string).
  - `product_id`: Product where activity was detected (string).
  - `total_buy_qty`: Total BUY quantity during the pattern window (integer).
  - `total_sell_qty`: Total SELL quantity during the pattern window (integer).
  - `num_cancelled_orders`: Count of cancelled orders in the sequence (integer).
  - `detected_timestamp`: Timestamp of detection (ISO datetime).

### Aggregation Semantics
- [ ] Define a “pattern window” per suspicious sequence, typically from the first `ORDER_PLACED` involved to the opposite-side `TRADE_EXECUTED`.
- [ ] `total_buy_qty` and `total_sell_qty` should aggregate only over events within this window.
- [ ] `num_cancelled_orders` counts `ORDER_CANCELLED` events that are part of the suspicious sequence.
- [ ] Clarify whether multiple sequences for the same `(account_id, product_id)` should:
  - Produce multiple rows; or
  - Be aggregated into one row with combined quantities.

## Internal Domain Model (Suggested)
- `TransactionEvent`:
  - `timestamp: datetime`
  - `account_id: str`
  - `product_id: str`
  - `side: Literal["BUY", "SELL"]`
  - `price: Decimal`
  - `quantity: int`
  - `event_type: Literal["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]`
- `SuspiciousSequence`:
  - `account_id: str`
  - `product_id: str`
  - `side: Literal["BUY", "SELL"]`  # side of fake orders
  - `start_timestamp: datetime`
  - `end_timestamp: datetime`  # detection timestamp
  - `total_buy_qty: int`
  - `total_sell_qty: int`
  - `num_cancelled_orders: int`
  - `order_timestamps: list[datetime]`

## Questions/Clarifications
- Are there any additional columns that might appear in `transactions.csv` and should be ignored rather than causing failures?
- Should we support multiple input files (e.g., one per day) in the future and how would outputs be partitioned?

## Related Specs
- `specs/requirements-layering-detection.md`
- `specs/feature-layering-detection.md`
- `specs/deployment-layering-detection.md`


