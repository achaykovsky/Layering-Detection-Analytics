"""
Layering detection algorithm implementation.

Implements the layering detection pattern as a registered algorithm,
wrapping the existing detection logic for use in the algorithm registry.
"""

from __future__ import annotations

from typing import Iterable, List

from ..detectors.layering_detector import detect_suspicious_sequences
from ..models import SuspiciousSequence, TransactionEvent
from .base import DetectionAlgorithm
from .registry import AlgorithmRegistry


@AlgorithmRegistry.register
class LayeringDetectionAlgorithm(DetectionAlgorithm):
    """
    Layering detection algorithm.
    
    Detects suspicious layering patterns where:
    - Multiple same-side orders are placed within a short time window
    - At least 3 of those orders are cancelled
    - An opposite-side trade occurs shortly after the cancellations
    
    This algorithm wraps the existing `detect_suspicious_sequences()` function
    to provide a registry-compatible interface while maintaining backward compatibility.
    
    Example:
        >>> algorithm = AlgorithmRegistry.get("layering")
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
            Algorithm name: "layering"
        """
        return "layering"

    @property
    def description(self) -> str:
        """
        Human-readable description of what this algorithm detects.
        
        Returns:
            Description of the layering detection pattern.
        """
        return (
            "Detects suspicious layering patterns: multiple same-side orders "
            "placed within a short window, followed by cancellations and an "
            "opposite-side trade. Identifies potential market manipulation "
            "where orders are placed to create false market signals."
        )

    def filter_events(
        self, events: Iterable[TransactionEvent]
    ) -> List[TransactionEvent]:
        """
        Filter events to ORDER_PLACED, ORDER_CANCELLED, and TRADE_EXECUTED events only.
        
        Layering detection requires orders (ORDER_PLACED), cancellations (ORDER_CANCELLED),
        and trades (TRADE_EXECUTED) to detect the pattern. This preprocessing step improves
        efficiency by filtering out irrelevant events before detection.
        
        Args:
            events: Iterable of transaction events to filter.
        
        Returns:
            Filtered list containing only ORDER_PLACED, ORDER_CANCELLED, and TRADE_EXECUTED events.
        
        Example:
            >>> algorithm = LayeringDetectionAlgorithm()
            >>> events = [
            ...     TransactionEvent(..., event_type="ORDER_PLACED"),
            ...     TransactionEvent(..., event_type="ORDER_CANCELLED"),
            ...     TransactionEvent(..., event_type="TRADE_EXECUTED"),
            ...     TransactionEvent(..., event_type="UNKNOWN"),
            ... ]
            >>> filtered = algorithm.filter_events(events)
            >>> len(filtered) == 3
            True
            >>> all(e.event_type in ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED") for e in filtered)
            True
        """
        return [
            e
            for e in events
            if e.event_type in ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED")
        ]

    def detect(
        self, events: Iterable[TransactionEvent]
    ) -> List[SuspiciousSequence]:
        """
        Detect suspicious layering sequences in the given events.
        
        Filters events to ORDER_PLACED, ORDER_CANCELLED, and TRADE_EXECUTED only,
        then calls `detect_suspicious_sequences()` which:
        - Groups events by (account_id, product_id)
        - Uses configurable timing windows (default: 10s orders, 5s cancel, 2s opposite trade)
        - Detects sequences meeting all criteria (≥3 same-side orders, ≥3 cancellations, opposite trade)
        
        Args:
            events: Iterable of transaction events to analyze.
                Events are filtered to relevant types, then grouped by (account_id, product_id)
                and analyzed for layering patterns within each group.
        
        Returns:
            List of detected suspicious sequences. Empty list if no sequences detected.
        
        Raises:
            ValueError: If events are invalid or detection configuration is invalid.
        
        Example:
            >>> algorithm = LayeringDetectionAlgorithm()
            >>> events = [
            ...     TransactionEvent(
            ...         timestamp=datetime.now(),
            ...         account_id="ACC001",
            ...         product_id="IBM",
            ...         side="BUY",
            ...         price=Decimal("100.0"),
            ...         quantity=1000,
            ...         event_type="ORDER_PLACED",
            ...     ),
            ... ]
            >>> sequences = algorithm.detect(events)
            >>> isinstance(sequences, list)
            True
        """
        # Filter to relevant event types (algorithm wrapper responsibility)
        filtered_events = self.filter_events(events)
        # Use default DetectionConfig (10s orders, 5s cancel, 2s opposite trade)
        # This maintains backward compatibility with existing code
        return detect_suspicious_sequences(filtered_events, config=None)


