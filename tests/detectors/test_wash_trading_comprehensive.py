"""
Integration tests for wash trading detection via algorithm registry.

Tests wash trading detection through the public API (AlgorithmRegistry) to verify
end-to-end integration. Unit tests for internal functions are in test_wash_trading_detector.py.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import SuspiciousSequence, TransactionEvent


class TestWashTradingRegistryIntegration:
    """Test suite for wash trading detection via algorithm registry."""

    def test_algorithm_retrievable_from_registry(self) -> None:
        """Test that wash trading algorithm is registered and retrievable."""
        # Act
        algorithm = AlgorithmRegistry.get("wash_trading")

        # Assert
        assert algorithm is not None
        assert algorithm.name == "wash_trading"
        assert "wash" in algorithm.description.lower()

    def test_positive_case_via_algorithm_registry(self) -> None:
        """Test positive case using algorithm registry."""
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
        assert len(sequences) > 0
        assert sequences[0].detection_type == "WASH_TRADING"

    def test_algorithm_produces_correct_output_format(self) -> None:
        """Test integration: algorithm produces correct output format."""
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

        # Assert: Verify output format
        assert isinstance(sequences, list)
        if len(sequences) > 0:
            seq = sequences[0]
            assert isinstance(seq, SuspiciousSequence)
            assert seq.detection_type == "WASH_TRADING"
            assert seq.account_id == "ACC001"
            assert seq.product_id == "IBM"
            assert seq.side is None
            assert seq.num_cancelled_orders is None
            assert seq.order_timestamps is None
            assert seq.alternation_percentage is not None
            assert isinstance(seq.alternation_percentage, float)
            assert seq.alternation_percentage >= 60.0
            assert seq.total_buy_qty + seq.total_sell_qty >= 10000

    def test_algorithm_filters_events_correctly(self) -> None:
        """Test that algorithm filters to TRADE_EXECUTED events only."""
        # Arrange: Mix of event types
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
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert: Only 1 TRADE_EXECUTED event, so no detection
        assert len(sequences) == 0


class TestWashTradingMultiAlgorithmIntegration:
    """Test suite for integration with multiple algorithms."""

    def test_both_algorithms_work_independently(self) -> None:
        """Test integration: both layering and wash_trading algorithms work independently."""
        # Arrange
        layering_alg = AlgorithmRegistry.get("layering")
        wash_trading_alg = AlgorithmRegistry.get("wash_trading")
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Layering events (ORDER_PLACED, ORDER_CANCELLED, TRADE_EXECUTED)
        layering_events = [
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
                timestamp=base_time + timedelta(seconds=2),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=4),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=6),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=7),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=8),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(seconds=9),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Wash trading events (only TRADE_EXECUTED)
        wash_trading_events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("150.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("150.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("151.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("151.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("152.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("152.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        layering_sequences = layering_alg.detect(layering_events)
        wash_trading_sequences = wash_trading_alg.detect(wash_trading_events)

        # Assert: Both algorithms work independently
        assert isinstance(layering_sequences, list)
        assert isinstance(wash_trading_sequences, list)
        # Layering should detect (has pattern)
        assert len(layering_sequences) > 0
        assert layering_sequences[0].detection_type == "LAYERING"
        # Wash trading should detect (has pattern)
        assert len(wash_trading_sequences) > 0
        assert wash_trading_sequences[0].detection_type == "WASH_TRADING"

    def test_algorithm_listed_in_registry(self) -> None:
        """Test that wash trading algorithm is listed in registry."""
        # Act
        all_algorithms = AlgorithmRegistry.list_all()

        # Assert
        assert "wash_trading" in all_algorithms
        assert "layering" in all_algorithms
