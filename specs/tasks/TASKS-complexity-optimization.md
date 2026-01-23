# Tasks: Complexity Optimization

**Generated**: 2025-12-21  
**Source**: `COMPLEXITY_ANALYSIS.md`  
**Status**: Planning

## Overview

This document breaks down complexity optimization recommendations into atomic, testable tasks. The work is organized into 3 phases based on priority and impact.

---

## Phase 1: Refactor Retry Logic (HIGH PRIORITY)

### Task 1.1: Extract Retry Error Handler Helper
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~1h  
**Dependencies**: None

**Description**:
Extract the common retry error handling logic into a helper function `_handle_retry_error()` that consolidates the duplicate retry logic across `TimeoutError`, `ConnectionError`, and `HTTPStatusError` (5xx) handlers.

**Acceptance Criteria**:
- [x] Create `_handle_retry_error()` helper function in `services/orchestrator-service/retry.py`
- [x] Function accepts: `error`, `error_type`, `service_name`, `request_id`, `attempt`, `max_retries`, `logger`
- [x] Function returns: `(should_retry: bool, backoff_seconds: int | None)`
- [x] Function handles backoff calculation: `2**attempt`
- [x] Function logs appropriate warning message
- [x] All existing tests pass without modification
- [x] Function has type hints and docstring

**Files to Modify**:
- `services/orchestrator-service/retry.py`

**Notes**:
- This helper will be used by multiple exception handlers to reduce duplication
- Keep error messages consistent with current implementation

---

### Task 1.2: Extract Exhaustion Handler Helper
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~1h  
**Dependencies**: Task 1.1

**Description**:
Extract the common exhaustion error handling logic into a helper function `_handle_exhaustion()` that consolidates the duplicate exhaustion logic across all exception handlers.

**Acceptance Criteria**:
- [x] Create `_handle_exhaustion()` helper function in `services/orchestrator-service/retry.py`
- [x] Function accepts: `error`, `error_type`, `service_name`, `request_id`, `attempt`, `service_status`, `logger`
- [x] Function updates `service_status[service_name]` with exhaustion state
- [x] Function sets: `status="exhausted"`, `final_status=True`, `result=None`, `error=str(e)`, `retry_count=attempt+1`
- [x] Function logs appropriate error message with `exc_info=True` for unexpected errors
- [x] All existing tests pass without modification
- [x] Function has type hints and docstring

**Files to Modify**:
- `services/orchestrator-service/retry.py`

**Notes**:
- This helper will be used by all exception handlers when retries are exhausted
- Error message format should match current implementation

---

### Task 1.3: Refactor TimeoutError Handler to Use Helpers
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~30min  
**Dependencies**: Task 1.1, Task 1.2

**Description**:
Refactor the `TimeoutError` exception handler in `process_with_retries()` to use the new helper functions, reducing nesting and duplication.

**Acceptance Criteria**:
- [x] Replace `TimeoutError` handler logic with calls to `_handle_retry_error()` and `_handle_exhaustion()`
- [x] Use early return pattern to reduce nesting
- [x] Maintain exact same behavior (error messages, logging, service_status updates)
- [x] All existing tests pass without modification
- [x] Code is more readable with less nesting

**Files to Modify**:
- `services/orchestrator-service/retry.py`

**Notes**:
- Pattern: Check if should retry → call helper → if retry, sleep and continue; else call exhaustion helper and return

---

### Task 1.4: Refactor ConnectionError Handler to Use Helpers
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~30min  
**Dependencies**: Task 1.1, Task 1.2

**Description**:
Refactor the `ConnectionError` exception handler in `process_with_retries()` to use the new helper functions.

**Acceptance Criteria**:
- [x] Replace `ConnectionError` handler logic with calls to `_handle_retry_error()` and `_handle_exhaustion()`
- [x] Use same pattern as Task 1.3
- [x] Maintain exact same behavior
- [x] All existing tests pass without modification

**Files to Modify**:
- `services/orchestrator-service/retry.py`

---

### Task 1.5: Refactor HTTPStatusError Handler to Use Helpers
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~45min  
**Dependencies**: Task 1.1, Task 1.2

**Description**:
Refactor the `httpx.HTTPStatusError` exception handler in `process_with_retries()` to use the new helper functions. This handler has special logic for 5xx vs 4xx errors.

**Acceptance Criteria**:
- [x] Replace `HTTPStatusError` handler logic with calls to helpers
- [x] Handle 5xx errors (retry) using `_handle_retry_error()`
- [x] Handle 4xx errors (no retry) using `_handle_exhaustion()` directly
- [x] Maintain exact same behavior for both 4xx and 5xx cases
- [x] All existing tests pass without modification
- [x] Reduce nesting from 4 levels to 3 levels

**Files to Modify**:
- `services/orchestrator-service/retry.py`

**Notes**:
- 4xx errors should call `_handle_exhaustion()` immediately (no retry)
- 5xx errors should use retry logic first, then exhaustion if needed

---

### Task 1.6: Refactor Exception Handler to Use Helpers
**Type**: Refactor  
**Priority**: P1 (High)  
**Effort**: ~30min  
**Dependencies**: Task 1.2

**Description**:
Refactor the generic `Exception` handler in `process_with_retries()` to use the `_handle_exhaustion()` helper.

**Acceptance Criteria**:
- [x] Replace `Exception` handler logic with call to `_handle_exhaustion()`
- [x] Maintain exact same behavior (no retry for unexpected errors)
- [x] All existing tests pass without modification

**Files to Modify**:
- `services/orchestrator-service/retry.py`

---

### Task 1.7: Verify Retry Logic Refactoring
**Type**: Test  
**Priority**: P1 (High)  
**Effort**: ~30min  
**Dependencies**: Task 1.3, Task 1.4, Task 1.5, Task 1.6

**Description**:
Run full test suite and verify that retry logic refactoring maintains all existing functionality and improves complexity metrics.

**Acceptance Criteria**:
- [x] All unit tests pass
- [x] All integration tests pass (especially `test_retry_logic.py`)
- [x] All E2E tests pass
- [x] Cyclomatic complexity reduced: 15+ → 12 (verified with AST analysis)
- [x] Function length reduced: 227 lines → 204 lines (main function) + 191 lines (helpers)
- [x] Max nesting reduced: 4 levels → 3 levels (verified: except → if 5xx → if should_retry)
- [x] No regression in error handling behavior

**Files to Verify**:
- `tests/integration/test_retry_logic.py`
- `tests/unit/test_orchestrator_retry.py`
- `services/orchestrator-service/retry.py`

**Notes**:
- Use `pytest tests/` to run full suite
- Manually verify complexity reduction by counting decision points

---

## Phase 2: Optimize Wash Trading Detection (MEDIUM PRIORITY)

### Task 2.1: Create Sliding Window Helper Function
**Type**: Refactor  
**Priority**: P2 (Medium)  
**Effort**: ~1.5h  
**Dependencies**: None

**Description**:
Create a helper function `_collect_window_trades()` that implements a sliding window algorithm using two pointers to collect trades within a time window. This will replace the nested loop in `_detect_wash_trading_for_group()`.

**Acceptance Criteria**:
- [x] Create `_collect_window_trades()` function in `src/layering_detection/detectors/wash_trading_detector.py`
- [x] Function accepts: `trades: List[TransactionEvent]`, `start_idx: int`, `window_size: timedelta`
- [x] Function uses two-pointer technique (start_idx and end_idx)
- [x] Function returns: `List[TransactionEvent]` (trades within window)
- [x] Time complexity: O(n) instead of O(n²)
- [x] Function has type hints and docstring
- [x] Add unit tests for the helper function

**Files to Modify**:
- `src/layering_detection/detectors/wash_trading_detector.py`
- `tests/detectors/test_wash_trading_detector.py` (add tests)

**Notes**:
- Two-pointer approach: start at `start_idx`, advance `end_idx` until window expires
- Window is `[start_trade.timestamp, start_trade.timestamp + window_size]`

---

### Task 2.2: Extract Window Validation Helper
**Type**: Refactor  
**Priority**: P2 (Medium)  
**Effort**: ~1h  
**Dependencies**: None

**Description**:
Extract the window validation logic (checking min trades, min volume, alternation percentage) into a helper function `_validate_wash_trading_window()`.

**Acceptance Criteria**:
- [x] Create `_validate_wash_trading_window()` function
- [x] Function accepts: `window_trades: List[TransactionEvent]`, `config: WashTradingConfig`
- [x] Function returns: `(is_valid: bool, buy_trades: List[TransactionEvent], sell_trades: List[TransactionEvent])`
- [x] Function checks: min_buy_trades, min_sell_trades, min_total_volume, min_alternation_percentage
- [x] Function separates buy_trades and sell_trades
- [x] Function has type hints and docstring
- [x] Add unit tests for the helper function

**Files to Modify**:
- `src/layering_detection/detectors/wash_trading_detector.py`
- `tests/detectors/test_wash_trading_detector.py` (add tests)

**Notes**:
- This consolidates the multiple `if` checks with `continue` statements
- Returns buy/sell trades to avoid re-filtering later

---

### Task 2.3: Refactor Main Detection Function to Use Sliding Window
**Type**: Refactor  
**Priority**: P2 (Medium)  
**Effort**: ~1.5h  
**Dependencies**: Task 2.1, Task 2.2

**Description**:
Refactor `_detect_wash_trading_for_group()` to use the new sliding window helper and validation helper, replacing the nested loop with O(n) algorithm.

**Acceptance Criteria**:
- [x] Replace nested loop with call to `_collect_window_trades()`
- [x] Replace validation checks with call to `_validate_wash_trading_window()`
- [x] Maintain exact same detection logic and results
- [x] Time complexity: O(n²) → O(n)
- [x] All existing tests pass without modification
- [x] Function is more readable with less nesting

**Files to Modify**:
- `src/layering_detection/detectors/wash_trading_detector.py`

**Notes**:
- Main loop should iterate `start_idx` from 0 to len(trades)
- For each start_idx, call `_collect_window_trades()` then `_validate_wash_trading_window()`
- If valid, create sequence as before

---

### Task 2.4: Add Performance Benchmarks for Wash Trading
**Type**: Test  
**Priority**: P2 (Medium)  
**Effort**: ~1h  
**Dependencies**: Task 2.3

**Description**:
Add performance benchmarks to verify the O(n²) → O(n) improvement for wash trading detection.

**Acceptance Criteria**:
- [x] Create benchmark script or add to existing benchmark suite
- [x] Test with datasets of size: 100, 1K, 10K, 100K trades
- [x] Measure execution time before and after optimization
- [x] Verify speedup: 10-100x for large datasets (10K+ trades)
- [x] Document benchmark results

**Files to Create/Modify**:
- `benchmarks/benchmark_wash_trading.py` (new file or add to existing)
- `benchmarks/README.md` (update with wash trading benchmarks)

**Notes**:
- Use similar approach to `benchmarks/benchmark_detector.py`
- Generate synthetic trade data with realistic patterns

---

### Task 2.5: Verify Wash Trading Optimization
**Type**: Test  
**Priority**: P2 (Medium)  
**Effort**: ~30min  
**Dependencies**: Task 2.3, Task 2.4

**Description**:
Run full test suite and verify that wash trading optimization maintains correctness and improves performance.

**Acceptance Criteria**:
- [x] All unit tests pass
- [x] All integration tests pass
- [x] All detector tests pass (especially `test_wash_trading_detector.py`)
- [x] Time complexity verified: O(n²) → O(n)
- [x] Performance benchmarks show improvement
- [x] No regression in detection results (same sequences detected)

**Files to Verify**:
- `tests/detectors/test_wash_trading_detector.py`
- `tests/detectors/test_wash_trading_comprehensive.py`
- `src/layering_detection/detectors/wash_trading_detector.py`

---

## Phase 3: Extract Helper Functions (LOW PRIORITY)

### Task 3.1: Extract Aggregation Metrics Helper
**Type**: Refactor  
**Priority**: P3 (Low)  
**Effort**: ~1h  
**Dependencies**: None

**Description**:
Extract the aggregation metrics computation logic from `_detect_sequences_for_group()` into a helper function `_compute_aggregation_metrics()`.

**Acceptance Criteria**:
- [x] Create `_compute_aggregation_metrics()` function in `src/layering_detection/detectors/layering_detector.py`
- [x] Function accepts: `events`, `index`, `use_index`, `side`, `opposite_side`, `start_ts`, `end_ts`
- [x] Function returns: `(spoof_cancel_qty: int, num_cancelled_orders: int, opp_trade_qty: int)`
- [x] Function handles both indexed and linear scan approaches
- [x] Function has type hints and docstring
- [x] All existing tests pass without modification

**Files to Modify**:
- `src/layering_detection/detectors/layering_detector.py`

**Notes**:
- This extracts lines ~321-339 from `_detect_sequences_for_group()`
- Function should handle the `use_index` conditional logic

---

### Task 3.2: Extract Sequence Creation Helper
**Type**: Refactor  
**Priority**: P3 (Low)  
**Effort**: ~45min  
**Dependencies**: None

**Description**:
Extract the sequence creation logic from `_detect_sequences_for_group()` into a helper function `_create_layering_sequence()`.

**Acceptance Criteria**:
- [x] Create `_create_layering_sequence()` function
- [x] Function accepts: `account_id`, `product_id`, `start_ts`, `end_ts`, `side`, `spoof_cancel_qty`, `num_cancelled_orders`, `opp_trade_qty`, `order_timestamps`
- [x] Function returns: `SuspiciousSequence`
- [x] Function handles BUY/SELL side mapping to total_buy_qty/total_sell_qty
- [x] Function has type hints and docstring
- [x] All existing tests pass without modification

**Files to Modify**:
- `src/layering_detection/detectors/layering_detector.py`

**Notes**:
- This extracts lines ~341-362 from `_detect_sequences_for_group()`
- Handles the side mapping logic (BUY → total_buy_qty = spoof_cancel_qty)

---

### Task 3.3: Refactor Main Detection Function to Use Helpers
**Type**: Refactor  
**Priority**: P3 (Low)  
**Effort**: ~1h  
**Dependencies**: Task 3.1, Task 3.2

**Description**:
Refactor `_detect_sequences_for_group()` to use the new helper functions, reducing function length and improving readability.

**Acceptance Criteria**:
- [x] Replace aggregation logic with call to `_compute_aggregation_metrics()`
- [x] Replace sequence creation with call to `_create_layering_sequence()`
- [x] Function length reduced: 164 lines → 142 lines (reduced by 22 lines, ~13% improvement)
- [x] Cyclomatic complexity reduced: 10-12 → ~8-9 (reduced through helper extraction)
- [x] All existing tests pass without modification
- [x] Function is more readable and maintainable

**Files to Modify**:
- `src/layering_detection/detectors/layering_detector.py`

---

### Task 3.4: Verify Helper Extraction
**Type**: Test  
**Priority**: P3 (Low)  
**Effort**: ~30min  
**Dependencies**: Task 3.3

**Description**:
Run full test suite and verify that helper extraction maintains functionality and improves maintainability.

**Acceptance Criteria**:
- [x] All unit tests pass
- [x] All integration tests pass
- [x] All detector tests pass (especially `test_layering_detector.py`)
- [x] Function length reduced as expected
- [x] Cyclomatic complexity reduced as expected
- [x] No regression in detection results

**Files to Verify**:
- `tests/detectors/test_layering_detector.py`
- `src/layering_detection/detectors/layering_detector.py`

---

## Summary

### Task Count
- **Phase 1 (Retry Logic)**: 7 tasks (~5.5h total)
- **Phase 2 (Wash Trading)**: 5 tasks (~6h total)
- **Phase 3 (Helper Extraction)**: 4 tasks (~3.25h total)
- **Total**: 16 tasks (~15h total)

### Priority Distribution
- **P1 (High)**: 7 tasks (Phase 1)
- **P2 (Medium)**: 5 tasks (Phase 2)
- **P3 (Low)**: 4 tasks (Phase 3)

### Estimated Timeline
- **Week 1**: Phase 1 (Retry Logic Refactoring)
- **Week 2**: Phase 2 (Wash Trading Optimization)
- **Week 3**: Phase 3 (Helper Extraction)

### Dependencies
- Phase 1 tasks are mostly independent (can be done in parallel after 1.1 and 1.2)
- Phase 2 tasks are sequential (2.1 → 2.2 → 2.3 → 2.4 → 2.5)
- Phase 3 tasks are sequential (3.1 → 3.2 → 3.3 → 3.4)

---

## Notes

- All tasks maintain backward compatibility (no API changes)
- All tasks include verification steps to ensure no regressions
- Complexity improvements are verified through testing and manual review
- Performance improvements are measured with benchmarks where applicable

