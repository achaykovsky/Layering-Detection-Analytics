"""
Wash trading detection engine.

Implements detection of wash trading manipulation patterns where traders
repeatedly buy and sell the same instrument to create false market activity
without changing net position.
"""

from __future__ import annotations

from datetime import datetime
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
