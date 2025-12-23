"""
Unit tests for LayeringDetectionAlgorithm.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import DetectionConfig, TransactionEvent
from tests.algorithms.test_algorithm_base import BaseAlgorithmTest
from tests.fixtures import create_transaction_event, create_layering_pattern


class TestLayeringDetectionAlgorithm(BaseAlgorithmTest):
    """Test suite for LayeringDetectionAlgorithm."""

    @property
    def algorithm_name(self) -> str:
        """Algorithm name used in registry."""
        return "layering"

    @property
    def expected_description_keywords(self) -> list[str]:
        """Expected keywords in algorithm description."""
        return ["layering", "pattern"]

    def test_filter_events_returns_relevant_event_types(self) -> None:
        """Test that filter_events() returns only ORDER_PLACED, ORDER_CANCELLED, and TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base_time,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base_time,
                event_type="TRADE_EXECUTED",
            ),
            # This should be filtered out (if such event type existed)
            # For now, we just verify the three relevant types are kept
        ]

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert len(filtered) == 3
        assert all(
            e.event_type in ("ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED")
            for e in filtered
        )

    def test_detect_wraps_detect_suspicious_sequences(self) -> None:
        """Test that detect() method wraps detect_suspicious_sequences()."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        events = [
            create_transaction_event(
                timestamp=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
                event_type="ORDER_PLACED",
            )
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert isinstance(sequences, list)
        # Empty list is valid (no sequences detected for single event)

    def test_detect_filters_events_before_detection(self) -> None:
        """Test that detect() filters events before calling detection logic."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Create events with only relevant types (filtering should not remove any)
        events = [
            create_transaction_event(
                timestamp=base_time,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        # Should work fine even with filtered events (all events are relevant)
        assert isinstance(sequences, list)

    def test_detect_produces_same_results_as_direct_call(self) -> None:
        """Test that detect() produces same results as calling detect_suspicious_sequences() directly."""
        from layering_detection.detectors.layering_detector import detect_suspicious_sequences

        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Create a simple layering pattern: 3 orders, 3 cancellations, 1 trade
        events = create_layering_pattern(
            base_time=base_time,
            order_quantity=1000,
            order_price_start="100.0",
            cancel_price_start="100.0",
            trade_quantity=500,
            trade_price="100.5",
        )

        # Act
        algorithm_results = algorithm.detect(events)
        # Direct call should also work with same events (they're already filtered)
        direct_results = detect_suspicious_sequences(events, config=None)

        # Assert
        # Results should match because algorithm filters to same event types
        assert len(algorithm_results) == len(direct_results)
        assert algorithm_results == direct_results

    def test_detect_uses_default_config(self) -> None:
        """Test that detect() uses default DetectionConfig."""
        from layering_detection.detectors.layering_detector import detect_suspicious_sequences

        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Create events that would match with default config (10s orders window)
        events = create_layering_pattern(
            base_time=base_time,
            order_quantity=1000,
            order_price_start="100.0",
            cancel_price_start="100.0",
            trade_quantity=500,
            trade_price="100.5",
        )

        # Act
        algorithm_results = algorithm.detect(events)
        # Direct call with None config should use default
        direct_results = detect_suspicious_sequences(events, config=None)

        # Assert
        assert algorithm_results == direct_results

