"""
Unit tests for WashTradingDetectionAlgorithm.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import TransactionEvent


class TestWashTradingDetectionAlgorithm:
    """Test suite for WashTradingDetectionAlgorithm."""

    def test_registered_in_registry(self) -> None:
        """Test that WashTradingDetectionAlgorithm is registered in AlgorithmRegistry."""
        # Act
        algorithm = AlgorithmRegistry.get("wash_trading")

        # Assert
        assert algorithm.name == "wash_trading"
        assert "wash_trading" in AlgorithmRegistry.list_all()

    def test_name_property_returns_wash_trading(self) -> None:
        """Test that name property returns 'wash_trading'."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")

        # Act
        name = algorithm.name

        # Assert
        assert name == "wash_trading"

    def test_description_property_returns_description(self) -> None:
        """Test that description property returns non-empty description."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")

        # Act
        description = algorithm.description

        # Assert
        assert isinstance(description, str)
        assert len(description) > 0
        assert "wash trading" in description.lower() or "wash" in description.lower()

    def test_filter_events_returns_only_trade_executed(self) -> None:
        """Test that filter_events() returns only TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
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
                timestamp=base_time + timedelta(seconds=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert len(filtered) == 1
        assert filtered[0].event_type == "TRADE_EXECUTED"

    def test_filter_events_handles_empty_list(self) -> None:
        """Test that filter_events() handles empty event list."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        events: list[TransactionEvent] = []

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert filtered == []

    def test_detect_wraps_detect_wash_trading(self) -> None:
        """Test that detect() method wraps detect_wash_trading()."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("102.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert isinstance(sequences, list)
        # Should detect wash trading pattern (3 BUY, 3 SELL, 100% alternation, 12000 volume)
        assert len(sequences) > 0
        assert sequences[0].detection_type == "WASH_TRADING"

    def test_detect_produces_same_results_as_direct_call(self) -> None:
        """Test that detect() produces same results as calling detect_wash_trading() directly."""
        from layering_detection.detectors.wash_trading_detector import detect_wash_trading

        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Create a valid wash trading pattern
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("102.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        algorithm_results = algorithm.detect(events)
        # detect_wash_trading() expects pre-filtered TRADE_EXECUTED events
        filtered_events = [e for e in events if e.event_type == "TRADE_EXECUTED"]
        direct_results = detect_wash_trading(filtered_events)

        # Assert
        assert len(algorithm_results) == len(direct_results)
        assert algorithm_results == direct_results

    def test_detect_handles_empty_event_list(self) -> None:
        """Test that detect() handles empty event list."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        events: list[TransactionEvent] = []

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert sequences == []

    def test_detect_filters_to_trade_executed_automatically(self) -> None:
        """Test that detect() automatically filters to TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
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
                timestamp=base_time + timedelta(seconds=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert sequences == []  # No TRADE_EXECUTED events, so no detection

    def test_can_be_retrieved_via_registry_get(self) -> None:
        """Test that algorithm can be retrieved via AlgorithmRegistry.get()."""
        # Act
        algorithm = AlgorithmRegistry.get("wash_trading")

        # Assert
        assert algorithm is not None
        assert algorithm.name == "wash_trading"
        assert hasattr(algorithm, "detect")
        assert callable(algorithm.detect)
        assert hasattr(algorithm, "filter_events")
        assert callable(algorithm.filter_events)

    def test_can_be_called_via_registry(self) -> None:
        """Test that algorithm can be called via registry."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert isinstance(sequences, list)

    def test_both_algorithms_registered(self) -> None:
        """Test that both layering and wash_trading algorithms are registered."""
        # Act
        registered = AlgorithmRegistry.list_all()

        # Assert
        assert "layering" in registered
        assert "wash_trading" in registered
        assert len(registered) >= 2

