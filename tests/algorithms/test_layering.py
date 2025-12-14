"""
Unit tests for LayeringDetectionAlgorithm.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import DetectionConfig, TransactionEvent


class TestLayeringDetectionAlgorithm:
    """Test suite for LayeringDetectionAlgorithm."""

    def test_registered_in_registry(self) -> None:
        """Test that LayeringDetectionAlgorithm is registered in AlgorithmRegistry."""
        # Act
        algorithm = AlgorithmRegistry.get("layering")

        # Assert
        assert algorithm.name == "layering"
        assert "layering" in AlgorithmRegistry.list_all()

    def test_name_property_returns_layering(self) -> None:
        """Test that name property returns 'layering'."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")

        # Act
        name = algorithm.name

        # Assert
        assert name == "layering"

    def test_description_property_returns_description(self) -> None:
        """Test that description property returns non-empty description."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")

        # Act
        description = algorithm.description

        # Assert
        assert isinstance(description, str)
        assert len(description) > 0
        assert "layering" in description.lower() or "pattern" in description.lower()

    def test_filter_events_returns_relevant_event_types(self) -> None:
        """Test that filter_events() returns only ORDER_PLACED, ORDER_CANCELLED, and TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
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

    def test_filter_events_handles_empty_list(self) -> None:
        """Test that filter_events() handles empty event list."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        events: list[TransactionEvent] = []

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert filtered == []

    def test_detect_wraps_detect_suspicious_sequences(self) -> None:
        """Test that detect() method wraps detect_suspicious_sequences()."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        events = [
            TransactionEvent(
                timestamp=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
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
        events = [
            # 3 BUY orders within 10 seconds
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=8),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # 3 cancellations within 5 seconds of last order
            TransactionEvent(
                timestamp=base_time.replace(second=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=11),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=12),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade within 2 seconds of last cancellation
            TransactionEvent(
                timestamp=base_time.replace(second=13),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        algorithm_results = algorithm.detect(events)
        # Direct call should also work with same events (they're already filtered)
        direct_results = detect_suspicious_sequences(events, config=None)

        # Assert
        # Results should match because algorithm filters to same event types
        assert len(algorithm_results) == len(direct_results)
        assert algorithm_results == direct_results

    def test_detect_handles_empty_event_list(self) -> None:
        """Test that detect() handles empty event list."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        events: list[TransactionEvent] = []

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert sequences == []

    def test_detect_uses_default_config(self) -> None:
        """Test that detect() uses default DetectionConfig."""
        from layering_detection.detectors.layering_detector import detect_suspicious_sequences

        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Create events that would match with default config (10s orders window)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=8),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=11),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=12),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=13),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        algorithm_results = algorithm.detect(events)
        # Direct call with None config should use default
        direct_results = detect_suspicious_sequences(events, config=None)

        # Assert
        assert algorithm_results == direct_results

    def test_can_be_retrieved_via_registry_get(self) -> None:
        """Test that algorithm can be retrieved via AlgorithmRegistry.get()."""
        # Act
        algorithm = AlgorithmRegistry.get("layering")

        # Assert
        assert algorithm is not None
        assert algorithm.name == "layering"
        assert hasattr(algorithm, "detect")
        assert callable(algorithm.detect)
        assert hasattr(algorithm, "filter_events")
        assert callable(algorithm.filter_events)

    def test_can_be_called_via_registry(self) -> None:
        """Test that algorithm can be called via registry."""
        # Arrange
        algorithm = AlgorithmRegistry.get("layering")
        events = [
            TransactionEvent(
                timestamp=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert isinstance(sequences, list)


