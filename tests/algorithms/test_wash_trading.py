"""
Unit tests for WashTradingDetectionAlgorithm.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import TransactionEvent
from tests.algorithms.test_algorithm_base import BaseAlgorithmTest
from tests.fixtures import create_transaction_event, create_wash_trading_pattern


class TestWashTradingDetectionAlgorithm(BaseAlgorithmTest):
    """Test suite for WashTradingDetectionAlgorithm."""

    @property
    def algorithm_name(self) -> str:
        """Algorithm name used in registry."""
        return "wash_trading"

    @property
    def expected_description_keywords(self) -> list[str]:
        """Expected keywords in algorithm description."""
        return ["wash trading", "wash"]

    def test_filter_events_returns_only_trade_executed(self) -> None:
        """Test that filter_events() returns only TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base_time,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=5),
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=10),
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert len(filtered) == 1
        assert filtered[0].event_type == "TRADE_EXECUTED"

    def test_detect_wraps_detect_wash_trading(self) -> None:
        """Test that detect() method wraps detect_wash_trading()."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = create_wash_trading_pattern(
            base_time=base_time,
            quantity=2000,
            price_start="100.0",
        )

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
        events = create_wash_trading_pattern(
            base_time=base_time,
            quantity=2000,
            price_start="100.0",
        )

        # Act
        algorithm_results = algorithm.detect(events)
        # detect_wash_trading() expects pre-filtered TRADE_EXECUTED events
        filtered_events = [e for e in events if e.event_type == "TRADE_EXECUTED"]
        direct_results = detect_wash_trading(filtered_events)

        # Assert
        assert len(algorithm_results) == len(direct_results)
        assert algorithm_results == direct_results

    def test_detect_filters_to_trade_executed_automatically(self) -> None:
        """Test that detect() automatically filters to TRADE_EXECUTED events."""
        # Arrange
        algorithm = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base_time,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=5),
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert sequences == []  # No TRADE_EXECUTED events, so no detection

    def test_both_algorithms_registered(self) -> None:
        """Test that both layering and wash_trading algorithms are registered."""
        # Act
        registered = AlgorithmRegistry.list_all()

        # Assert
        assert "layering" in registered
        assert "wash_trading" in registered
        assert len(registered) >= 2

