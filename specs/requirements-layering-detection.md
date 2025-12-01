# Layering Detection Analytics – Requirements

## Overview
Python-based batch analytics that scans intraday transactions data to detect potential layering manipulations and outputs suspicious accounts with supporting logs, packaged and runnable via Docker.

## Requirements
- [ ] Ingest intraday transaction data from `input/transactions.csv` with the specified schema.
- [ ] Implement detection logic for simplified layering sequences as defined in the PRD.
- [ ] Generate an output CSV `output/suspicious_accounts.csv` with the required columns.
- [ ] Treat each detected layering sequence as a separate event and output **one row per sequence** (multiple rows are allowed for the same `(account_id, product_id)`).
- [ ] Compute total BUY and SELL quantities per sequence using:
  - Spoof-side volume = sum of quantities of the cancelled spoof orders (side of fake orders).
  - Opposite-side volume = sum of quantities of the opposite-side executed trades that complete the pattern.
- [ ] Count cancelled orders participating in each suspicious sequence.
- [ ] Record a clear `detected_timestamp` per suspicious sequence as the timestamp of the opposite-side `TRADE_EXECUTED` event that completes the pattern.
- [ ] Log each suspicious detection event with required context into `logs/`, with one log entry per detection sequence.
- [ ] Package the solution as a Python package installable via `pip`.
- [ ] Provide a Docker image that installs the package and runs the detection.
- [ ] Ensure the container writes results to `output/` and logs to `logs/` on the host volume.
- [ ] Provide a README with clear “How to run” instructions (local + Docker).
- [ ] Ensure the system is deterministic and reproducible for a given CSV input.

## Acceptance Criteria
- [ ] Given a CSV with transactions matching the column definitions, the system completes without runtime errors.
- [ ] For any sequence satisfying the PRD’s 3-step layering definition, the corresponding `account_id`/`product_id` pair appears in `output/suspicious_accounts.csv` **once per detected sequence**.
- [ ] `suspicious_accounts.csv` includes **exactly** the columns: `account_id`, `product_id`, `total_buy_qty`, `total_sell_qty`, `num_cancelled_orders`, `detected_timestamp`.
- [ ] Log files are created under `logs/` and contain at least, per detection sequence:
  - `account_id`, `product_id`
  - A compact sequence of order timestamps (encoded as a single `order_timestamps` field)
  - `duration_seconds` (duration of the sequence in seconds)
- [ ] The project can be installed as a package and executed inside Docker with a single documented command.
- [ ] Running the solution multiple times on the same input produces identical outputs.

## Technical Details
- Input file: `input/transactions.csv` with columns:
  - `timestamp` (ISO datetime)
  - `account_id`
  - `product_id`
  - `side` (`BUY` or `SELL`)
  - `price`
  - `quantity`
  - `event_type` (`ORDER_PLACED`, `ORDER_CANCELLED`, `TRADE_EXECUTED`)
- Output file: `output/suspicious_accounts.csv`.
- Logs directory: `logs/`.
- Execution environment:
  - Python 3.11+ (assumed)
  - Packaged as installable Python package.
  - Docker image that installs the package via `pip install .` and runs a CLI entrypoint.
- Non-functional:
  - Maintainable, readable code (modular design separating parsing, detection, I/O).
  - Reasonable performance for intraday data scale (single-day CSV).

## Clarifications from Interviewer
- `transactions.csv` is expected to be on the order of \\(10^5 - 10^6\\) rows; the solution should operate efficiently in a single or near-single pass on a standard machine.
- Overlapping or multiple sequences for the same `(account_id, product_id)` should produce multiple rows (one per sequence); an individual order belongs to at most one detection window.
- `detected_timestamp` is the timestamp of the opposite-side `TRADE_EXECUTED` that completes the pattern (the first instant when all conditions are satisfied).
- Volume semantics:
  - Spoof side = sum of quantities of the cancelled spoof orders.
  - Opposite side = sum of quantities of the opposite-side executed trades.

## Related Specs
- `specs/feature-layering-detection.md`
- `specs/data-layering-detection.md`
- `specs/deployment-layering-detection.md`


