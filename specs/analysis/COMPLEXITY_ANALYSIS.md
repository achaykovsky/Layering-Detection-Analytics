# Codebase Complexity Analysis

**Date**: 2025-12-21  
**Analyzer**: Performance Engineer Agent  
**Scope**: Production codebase (excluding tests)

## Executive Summary

The codebase demonstrates **good complexity management** overall, with most functions under complexity thresholds. However, there are **3 key areas for improvement**:

1. **Retry Logic Function** (`services/orchestrator-service/retry.py:process_with_retries`) - High cyclomatic complexity (15+)
2. **Wash Trading Detection** (`src/layering_detection/detectors/wash_trading_detector.py:_detect_wash_trading_for_group`) - O(n²) nested loops
3. **Layering Detection** (`src/layering_detection/detectors/layering_detector.py:_detect_sequences_for_group`) - Already optimized to O(n log n) ✅

---

## Complexity Metrics

### Function Length Analysis

| File | Function | Lines | Status |
|------|---------|------|--------|
| `retry.py` | `process_with_retries` | 227 | ⚠️ **LONG** (prefer < 50) |
| `layering_detector.py` | `_detect_sequences_for_group` | 164 | ⚠️ **LONG** (prefer < 50) |
| `wash_trading_detector.py` | `_detect_wash_trading_for_group` | 87 | ✅ OK |
| `layering_detector.py` | `_query_events_in_window` | 65 | ⚠️ **LONG** (prefer < 50) |

**Recommendation**: Extract helper functions to reduce function length.

### Cyclomatic Complexity Analysis

#### 1. `process_with_retries` (HIGH PRIORITY)

**File**: `services/orchestrator-service/retry.py`  
**Lines**: 43-270 (227 lines)  
**Estimated Complexity**: **15+** (exceeds threshold of 10)

**Issues**:
- Multiple nested exception handlers (4 different exception types)
- Each exception handler has nested if/else (attempt < max_retries)
- Deep nesting: `try` → `except` → `if` → `else` (4 levels)
- Duplicate error handling logic across exception types

**Current Structure**:
```python
for attempt in range(max_retries + 1):
    try:
        # ... success path ...
    except TimeoutError as e:
        if attempt < max_retries:
            # ... retry logic ...
        else:
            # ... exhaustion logic ...
    except ConnectionError as e:
        if attempt < max_retries:
            # ... retry logic ...
        else:
            # ... exhaustion logic ...
    except httpx.HTTPStatusError as e:
        if 500 <= status_code < 600:
            if attempt < max_retries:
                # ... retry logic ...
            else:
                # ... exhaustion logic ...
        else:
            # ... 4xx error logic ...
    except Exception as e:
        # ... unexpected error logic ...
```

**Optimization Strategy**:
1. Extract error handling into helper functions
2. Use early returns to reduce nesting
3. Consolidate duplicate retry/exhaustion logic

**Expected Improvement**: Complexity 15+ → ~8-10

#### 2. `_detect_wash_trading_for_group` (MEDIUM PRIORITY)

**File**: `src/layering_detection/detectors/wash_trading_detector.py`  
**Lines**: 72-158 (87 lines)  
**Estimated Complexity**: **8-10** (within threshold, but can improve)

**Issues**:
- Nested loops: `for start_idx` → `for i` (O(n²) complexity)
- Multiple early `continue` statements (good for readability)
- Guard clauses could be extracted

**Current Structure**:
```python
for start_idx in range(len(trades)):  # O(n)
    # ... window setup ...
    for i in range(start_idx, len(trades)):  # O(n) - nested!
        # ... collect window trades ...
    # Multiple guard clauses with continue
    if len(window_trades) < min:
        continue
    if len(buy_trades) < min or len(sell_trades) < min:
        continue
    # ... more guards ...
```

**Optimization Strategy**:
1. Use sliding window optimization (two pointers) to reduce to O(n)
2. Extract validation logic into helper function
3. Consider early termination optimizations

**Expected Improvement**: Time complexity O(n²) → O(n), Complexity 8-10 → ~6-8

#### 3. `_detect_sequences_for_group` (LOW PRIORITY - Already Optimized)

**File**: `src/layering_detection/detectors/layering_detector.py`  
**Lines**: 204-367 (164 lines)  
**Estimated Complexity**: **10-12** (slightly above threshold)

**Status**: ✅ **Already optimized** (O(n²) → O(n log n))

**Issues**:
- Long function (164 lines, prefer < 50)
- Multiple responsibilities (detection + aggregation)
- Could benefit from extraction of helper functions

**Optimization Strategy**:
1. Extract aggregation logic into separate function
2. Extract sequence creation into helper
3. Consider splitting into smaller functions

**Expected Improvement**: Complexity 10-12 → ~6-8, Better maintainability

---

## Algorithm Complexity Analysis

### Time Complexity

| Function | Current | Optimal | Status |
|----------|---------|---------|--------|
| `_detect_wash_trading_for_group` | O(n²) | O(n) | ⚠️ **Can optimize** |
| `_detect_sequences_for_group` | O(n log n) | O(n log n) | ✅ **Optimal** |
| `_query_events_in_window` | O(log n) | O(log n) | ✅ **Optimal** |
| `process_with_retries` | O(1) per call | O(1) | ✅ **Optimal** |

### Space Complexity

| Function | Current | Optimal | Status |
|----------|---------|---------|--------|
| `_detect_wash_trading_for_group` | O(n) | O(n) | ✅ **Optimal** |
| `_detect_sequences_for_group` | O(n) | O(n) | ✅ **Optimal** |
| `_query_events_in_window` | O(n) | O(n) | ✅ **Optimal** |

---

## Deep Nesting Analysis

### Nesting Levels

| File | Function | Max Nesting | Threshold | Status |
|------|----------|-------------|-----------|--------|
| `retry.py` | `process_with_retries` | 4 levels | 3-4 | ⚠️ **At limit** |
| `wash_trading_detector.py` | `_detect_wash_trading_for_group` | 3 levels | 3-4 | ✅ **OK** |
| `layering_detector.py` | `_detect_sequences_for_group` | 3 levels | 3-4 | ✅ **OK** |

**Recommendation**: Use guard clauses and early returns to reduce nesting in `process_with_retries`.

---

## Recommendations

### Priority 1: Refactor Retry Logic (HIGH IMPACT)

**File**: `services/orchestrator-service/retry.py`

**Changes**:
1. Extract `_handle_retry_error()` helper function
2. Extract `_handle_exhaustion()` helper function
3. Use early returns to reduce nesting
4. Consolidate duplicate error handling logic

**Expected Benefits**:
- Cyclomatic complexity: 15+ → ~8-10
- Function length: 227 lines → ~100 lines (main) + helpers
- Maintainability: Significantly improved
- Testability: Easier to test individual error handlers

**Estimated Effort**: 2-3 hours

### Priority 2: Optimize Wash Trading Detection (MEDIUM IMPACT)

**File**: `src/layering_detection/detectors/wash_trading_detector.py`

**Changes**:
1. Implement sliding window with two pointers (O(n) instead of O(n²))
2. Extract validation logic into `_validate_window()` helper
3. Consider early termination optimizations

**Expected Benefits**:
- Time complexity: O(n²) → O(n)
- Performance: 10-100x faster for large datasets
- Cyclomatic complexity: 8-10 → ~6-8

**Estimated Effort**: 3-4 hours

### Priority 3: Extract Helper Functions (LOW IMPACT)

**File**: `src/layering_detection/detectors/layering_detector.py`

**Changes**:
1. Extract `_compute_aggregation_metrics()` helper
2. Extract `_create_sequence()` helper
3. Split `_detect_sequences_for_group` into smaller functions

**Expected Benefits**:
- Function length: 164 lines → ~80 lines (main) + helpers
- Cyclomatic complexity: 10-12 → ~6-8
- Maintainability: Improved readability

**Estimated Effort**: 2-3 hours

---

## Code Quality Metrics

### Overall Assessment

| Metric | Target | Current | Status |
|--------|-------|---------|--------|
| **Average Function Length** | < 50 lines | ~60 lines | ⚠️ **Slightly high** |
| **Max Cyclomatic Complexity** | < 10 | 15+ | ⚠️ **Needs improvement** |
| **Max Nesting Depth** | 3-4 levels | 4 levels | ⚠️ **At limit** |
| **Algorithm Complexity** | Optimal | Mostly optimal | ✅ **Good** |
| **Code Duplication** | Minimal | Low | ✅ **Good** |

### Strengths

1. ✅ **Layering detection already optimized** (O(n log n))
2. ✅ **Good use of guard clauses** in most functions
3. ✅ **Clear separation of concerns** (detectors, algorithms, services)
4. ✅ **Minimal code duplication**
5. ✅ **Good documentation** and type hints

### Areas for Improvement

1. ⚠️ **Retry logic has high complexity** (needs refactoring)
2. ⚠️ **Wash trading has O(n²) complexity** (can optimize to O(n))
3. ⚠️ **Some functions are too long** (prefer < 50 lines)
4. ⚠️ **Deep nesting in retry logic** (use early returns)

---

## Implementation Plan

### Phase 1: Refactor Retry Logic (Week 1)
1. Extract `_handle_retry_error()` helper
2. Extract `_handle_exhaustion()` helper
3. Refactor main function with early returns
4. Add unit tests for extracted functions
5. Verify all integration tests pass

### Phase 2: Optimize Wash Trading (Week 2)
1. Implement sliding window algorithm
2. Extract validation logic
3. Add performance benchmarks
4. Verify correctness with existing tests
5. Measure performance improvement

### Phase 3: Extract Helpers (Week 3)
1. Extract aggregation helpers from layering detector
2. Extract sequence creation helpers
3. Refactor main detection function
4. Verify all tests pass

---

## Conclusion

The codebase is **well-structured** with good algorithmic complexity overall. The main improvements are:

1. **Refactor retry logic** to reduce cyclomatic complexity (15+ → ~8-10)
2. **Optimize wash trading** from O(n²) to O(n) using sliding window
3. **Extract helper functions** to improve maintainability

These improvements will enhance **maintainability**, **testability**, and **performance** without changing functionality.

