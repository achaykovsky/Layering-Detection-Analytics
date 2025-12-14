"""
Wash trading detection algorithm implementation.

Implements the wash trading detection pattern as a registered algorithm,
wrapping the existing detection logic for use in the algorithm registry.
"""

from __future__ import annotations

from typing import Iterable, List

from ..detectors.wash_trading_detector import detect_wash_trading
from ..models import SuspiciousSequence, TransactionEvent
from .base import DetectionAlgorithm
from .registry import AlgorithmRegistry


@AlgorithmRegistry.register
class WashTradingDetectionAlgorithm(DetectionAlgorithm):
    """
    Wash trading detection algorithm.
    
    Detects suspicious wash trading patterns where:
    - Same account executes ≥3 BUY trades and ≥3 SELL trades
    - Within a 30-minute sliding window
    - With ≥60% alternation (side switches between consecutive trades)
    - With ≥10,000 total volume
    - (Optional) Price change ≥1% during window
    
    This algorithm wraps the existing `detect_wash_trading()` function
    to provide a registry-compatible interface while maintaining backward compatibility.
    
    Example:
        >>> algorithm = AlgorithmRegistry.get("wash_trading")
        >>> events = [...]  # TransactionEvent instances
        >>> sequences = algorithm.detect(events)
        >>> len(sequences) >= 0
        True
    """

    @property
    def name(self) -> str:
        """
        Unique identifier for this algorithm.
        
        Returns:
            Algorithm name: "wash_trading"
        """
        return "wash_trading"

    @property
    def description(self) -> str:
        """
        Human-readable description of what this algorithm detects.
        
        Returns:
            Description of the wash trading detection pattern.
        """
        return (
            "Detects suspicious wash trading patterns: same account repeatedly "
            "buys and sells the same instrument within a configurable sliding window "
            "(default: 30 minutes) with high alternation (≥60% side switches, configurable) "
            "and significant volume (≥10k, configurable). Identifies potential market "
            "manipulation where traders create false market activity without changing net position."
        )

    def filter_events(
        self, events: Iterable[TransactionEvent]
    ) -> List[TransactionEvent]:
        """
        Filter events to TRADE_EXECUTED events only.
        
        Wash trading detection only considers executed trades, not orders or cancellations.
        This preprocessing step improves efficiency by filtering out irrelevant events
        before detection.
        
        Args:
            events: Iterable of transaction events to filter.
        
        Returns:
            Filtered list containing only TRADE_EXECUTED events.
        
        Example:
            >>> algorithm = WashTradingDetectionAlgorithm()
            >>> events = [
            ...     TransactionEvent(..., event_type="ORDER_PLACED"),
            ...     TransactionEvent(..., event_type="TRADE_EXECUTED"),
            ...     TransactionEvent(..., event_type="ORDER_CANCELLED"),
            ... ]
            >>> filtered = algorithm.filter_events(events)
            >>> len(filtered) == 1
            True
            >>> filtered[0].event_type == "TRADE_EXECUTED"
            True
        """
        return [
            e for e in events if e.event_type == "TRADE_EXECUTED"
        ]

    def detect(
        self, events: Iterable[TransactionEvent]
    ) -> List[SuspiciousSequence]:
        """
        Detect suspicious wash trading sequences in the given events.
        
        Filters events to TRADE_EXECUTED only, then calls `detect_wash_trading()` which:
        - Groups events by (account_id, product_id)
        - Uses 30-minute sliding windows (configurable via WashTradingConfig)
        - Detects sequences meeting all criteria (≥3 BUY, ≥3 SELL, ≥60% alternation, ≥10k volume)
        
        Args:
            events: Iterable of transaction events to analyze.
                Events are filtered to TRADE_EXECUTED only, then grouped by
                (account_id, product_id) and analyzed for wash trading patterns.
        
        Returns:
            List of detected suspicious sequences. Empty list if no sequences detected.
        
        Raises:
            ValueError: If events are invalid.
        
        Example:
            >>> algorithm = WashTradingDetectionAlgorithm()
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
            >>> sequences = algorithm.detect(events)
            >>> isinstance(sequences, list)
            True
        """
        # Filter to TRADE_EXECUTED events only (algorithm wrapper responsibility)
        filtered_events = self.filter_events(events)
        # detect_wash_trading() expects pre-filtered TRADE_EXECUTED events
        return detect_wash_trading(filtered_events)

