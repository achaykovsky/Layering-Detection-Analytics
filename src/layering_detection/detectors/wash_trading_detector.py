"""
Wash trading detection engine.

Implements detection of wash trading manipulation patterns where traders
repeatedly buy and sell the same instrument to create false market activity
without changing net position.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, List

from ..models import Side, SuspiciousSequence, TransactionEvent, WashTradingConfig
from ..utils.detection_utils import group_events_by_account_product


def _calculate_alternation_percentage(trades: List[TransactionEvent]) -> float:
    """
    Calculate alternation percentage (percentage of side switches).
    
    Alternation % = (side_switches / (total_trades - 1)) * 100
    
    Args:
        trades: List of trades sorted by timestamp.
    
    Returns:
        Alternation percentage (0-100). Returns 0.0 if fewer than 2 trades.
    
    Example:
        BUY, SELL, BUY, SELL = 3 switches / 3 transitions = 100%
        BUY, BUY, SELL, SELL = 1 switch / 3 transitions = 33.33%
    """
    if len(trades) < 2:
        return 0.0
    
    side_switches = 0
    for i in range(1, len(trades)):
        if trades[i].side != trades[i - 1].side:
            side_switches += 1
    
    total_transitions = len(trades) - 1
    return (side_switches / total_transitions) * 100.0


def _calculate_price_change_percentage(trades: List[TransactionEvent]) -> float | None:
    """
    Calculate price change percentage during the window.
    
    Price change % = |(last_price - first_price) / first_price| * 100
    
    Args:
        trades: List of trades sorted by timestamp (non-empty).
    
    Returns:
        Price change percentage, or None if no trades.
    """
    if not trades:
        return None
    
    first_price = float(trades[0].price)
    last_price = float(trades[-1].price)
    
    if first_price == 0:
        return None
    
    price_change = abs((last_price - first_price) / first_price) * 100.0
    return price_change


def _collect_window_trades(
    trades: List[TransactionEvent],
    start_idx: int,
    window_size: timedelta,
) -> List[TransactionEvent]:
    """
    Collect trades within a sliding window using two-pointer technique.
    
    Uses an efficient O(n) algorithm where the end pointer only moves forward,
    avoiding the O(n²) nested loop approach.
    
    Args:
        trades: List of trades sorted by timestamp (non-empty).
        start_idx: Starting index for the window (0-indexed).
        window_size: Size of the time window (timedelta).
    
    Returns:
        List of trades within the window [start_trade.timestamp, start_trade.timestamp + window_size].
        Trades are inclusive of the window boundaries.
    
    Time Complexity: O(n) where n is the number of trades.
        Each trade is visited at most twice (once as start, once as end).
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> trades = [
        ...     TransactionEvent(timestamp=datetime(2024, 1, 1, 10, 0, 0), ...),
        ...     TransactionEvent(timestamp=datetime(2024, 1, 1, 10, 5, 0), ...),
        ...     TransactionEvent(timestamp=datetime(2024, 1, 1, 10, 35, 0), ...),
        ... ]
        >>> window_trades = _collect_window_trades(trades, start_idx=0, window_size=timedelta(minutes=30))
        >>> len(window_trades)
        2
    """
    if start_idx >= len(trades):
        return []
    
    start_trade = trades[start_idx]
    window_start = start_trade.timestamp
    window_end = window_start + window_size
    
    # Two-pointer approach: find end_idx where trades[end_idx].timestamp > window_end
    # Start end_idx from start_idx (inclusive boundary)
    end_idx = start_idx
    
    # Advance end_idx until we exceed the window
    while end_idx < len(trades):
        trade = trades[end_idx]
        if trade.timestamp > window_end:
            break
        end_idx += 1
    
    # Return trades from start_idx to end_idx (exclusive of end_idx)
    return trades[start_idx:end_idx]


def _validate_wash_trading_window(
    window_trades: List[TransactionEvent],
    config: WashTradingConfig,
) -> tuple[bool, List[TransactionEvent], List[TransactionEvent]]:
    """
    Validate a window of trades against wash trading detection criteria.
    
    Checks if the window meets all minimum requirements:
    - Minimum total trades (min_buy_trades + min_sell_trades)
    - Minimum buy trades (min_buy_trades)
    - Minimum sell trades (min_sell_trades)
    - Minimum total volume (min_total_volume)
    - Minimum alternation percentage (min_alternation_percentage)
    
    Args:
        window_trades: List of trades within the window, sorted by timestamp.
        config: Wash trading detection configuration.
    
    Returns:
        Tuple of (is_valid: bool, buy_trades: List[TransactionEvent], sell_trades: List[TransactionEvent]):
        - is_valid: True if window meets all criteria, False otherwise
        - buy_trades: List of BUY trades (separated for reuse)
        - sell_trades: List of SELL trades (separated for reuse)
    
    Example:
        >>> from datetime import datetime, timedelta
        >>> config = WashTradingConfig()
        >>> window_trades = [
        ...     TransactionEvent(timestamp=datetime.now(), side="BUY", ...),
        ...     TransactionEvent(timestamp=datetime.now(), side="SELL", ...),
        ... ]
        >>> is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)
        >>> is_valid
        False  # Not enough trades
    """
    # Early exit: check minimum total trades
    if len(window_trades) < config.min_buy_trades + config.min_sell_trades:
        return False, [], []
    
    # Separate BUY and SELL trades
    buy_trades = [t for t in window_trades if t.side == "BUY"]
    sell_trades = [t for t in window_trades if t.side == "SELL"]
    
    # Check minimum buy and sell trades
    if len(buy_trades) < config.min_buy_trades or len(sell_trades) < config.min_sell_trades:
        return False, buy_trades, sell_trades
    
    # Check minimum total volume
    total_volume = sum(t.quantity for t in window_trades)
    if total_volume < config.min_total_volume:
        return False, buy_trades, sell_trades
    
    # Check minimum alternation percentage
    alternation_pct = _calculate_alternation_percentage(window_trades)
    if alternation_pct < config.min_alternation_percentage:
        return False, buy_trades, sell_trades
    
    # All checks passed
    return True, buy_trades, sell_trades


def _detect_wash_trading_for_group(
    account_id: str,
    product_id: str,
    trades: List[TransactionEvent],
    config: WashTradingConfig,
) -> List[SuspiciousSequence]:
    """
    Detect wash trading sequences within a single (account_id, product_id) group.
    
    Uses a sliding window approach: for each trade, create a window
    starting at that trade's timestamp and check if the window meets all criteria.
    
    Args:
        account_id: Account identifier.
        product_id: Product identifier.
        trades: List of TRADE_EXECUTED events, sorted by timestamp.
        config: Wash trading detection configuration.
    
    Returns:
        List of detected suspicious wash trading sequences.
    """
    sequences: List[SuspiciousSequence] = []
    
    if len(trades) < config.min_buy_trades + config.min_sell_trades:
        # Not enough trades to meet minimum requirements
        return sequences
    
    # For each trade, create a sliding window starting at that trade
    for start_idx in range(len(trades)):
        start_trade = trades[start_idx]
        window_start = start_trade.timestamp
        window_end = window_start + config.window_size
        
        # Collect all trades within the window (inclusive of boundary)
        window_trades: List[TransactionEvent] = []
        for i in range(start_idx, len(trades)):
            trade = trades[i]
            if trade.timestamp > window_end:
                break
            window_trades.append(trade)
        
        if len(window_trades) < config.min_buy_trades + config.min_sell_trades:
            continue
        
        # Count BUY and SELL trades
        buy_trades = [t for t in window_trades if t.side == "BUY"]
        sell_trades = [t for t in window_trades if t.side == "SELL"]
        
        if len(buy_trades) < config.min_buy_trades or len(sell_trades) < config.min_sell_trades:
            continue
        
        # Calculate total volume
        total_volume = sum(t.quantity for t in window_trades)
        if total_volume < config.min_total_volume:
            continue
        
        # Calculate alternation percentage
        alternation_pct = _calculate_alternation_percentage(window_trades)
        if alternation_pct < config.min_alternation_percentage:
            continue
        
        # Calculate buy and sell quantities
        total_buy_qty = sum(t.quantity for t in buy_trades)
        total_sell_qty = sum(t.quantity for t in sell_trades)
        
        # Calculate optional price change percentage
        price_change_pct = _calculate_price_change_percentage(window_trades)
        
        # Create suspicious sequence
        sequences.append(
            SuspiciousSequence(
                account_id=account_id,
                product_id=product_id,
                start_timestamp=window_start,
                end_timestamp=window_trades[-1].timestamp,  # Last trade in window
                total_buy_qty=total_buy_qty,
                total_sell_qty=total_sell_qty,
                detection_type="WASH_TRADING",
                side=None,  # Not applicable for wash trading
                num_cancelled_orders=None,  # Not applicable for wash trading
                order_timestamps=None,  # Not applicable for wash trading
                alternation_percentage=alternation_pct,
                price_change_percentage=price_change_pct if price_change_pct is not None and price_change_pct >= config.optional_price_change_threshold else None,
            )
        )
    
    return sequences


def detect_wash_trading(
    events: Iterable[TransactionEvent],
    config: WashTradingConfig | None = None,
) -> List[SuspiciousSequence]:
    """
    Detect wash trading patterns in transaction events.
    
    Wash trading detection criteria (configurable via WashTradingConfig):
    - Same account executes ≥min_buy_trades BUY trades and ≥min_sell_trades SELL trades
    - Within a sliding window (default: 30 minutes)
    - With ≥min_alternation_percentage alternation (side switches, default: 60%)
    - With ≥min_total_volume total volume (default: 10,000)
    - (Optional) Price change ≥optional_price_change_threshold during window (default: 1%)
    
    NOTE: This function expects events to be pre-filtered to TRADE_EXECUTED only.
    The algorithm wrapper (WashTradingDetectionAlgorithm) handles filtering.
    
    Args:
        events: Iterable of TRADE_EXECUTED transaction events to analyze.
            Events should be pre-filtered by the caller (algorithm wrapper).
        config: Optional wash trading detection configuration. If None, uses default
            WashTradingConfig() with standard thresholds.
    
    Returns:
        List of detected suspicious wash trading sequences.
        Empty list if no sequences detected.
    
    Example:
        >>> events = [
        ...     TransactionEvent(
        ...         timestamp=datetime.now(),
        ...         account_id="ACC001",
        ...         product_id="IBM",
        ...         side="BUY",
        ...         price=Decimal("100.0"),
        ...         quantity=5000,
        ...         event_type="TRADE_EXECUTED",
        ...     ),
        ...     # ... more trades ...
        ... ]
        >>> sequences = detect_wash_trading(events)
        >>> len(sequences) >= 0
        True
    """
    if config is None:
        config = WashTradingConfig()
    
    # Group by (account_id, product_id)
    grouped = group_events_by_account_product(events)
    
    all_sequences: List[SuspiciousSequence] = []
    
    # Process each group
    for (account_id, product_id), group_trades in grouped.items():
        all_sequences.extend(
            _detect_wash_trading_for_group(account_id, product_id, group_trades, config)
        )
    
    return all_sequences
