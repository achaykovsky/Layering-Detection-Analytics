"""
Unit tests for SuspiciousSequence model extensions (Task 21).

Tests new fields for wash trading detection and backward compatibility.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from layering_detection.models import DetectionType, SuspiciousSequence, TransactionEvent


class TestSuspiciousSequenceExtensions:
    """Test suite for SuspiciousSequence model extensions."""

    def test_layering_sequence_with_default_detection_type(self) -> None:
        """Test that detection_type defaults to 'LAYERING' for backward compatibility."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[base_time],
        )

        # Assert
        assert sequence.detection_type == "LAYERING"
        assert sequence.side == "BUY"
        assert sequence.num_cancelled_orders == 3
        assert sequence.order_timestamps == [base_time]
        assert sequence.alternation_percentage is None
        assert sequence.price_change_percentage is None

    def test_layering_sequence_explicit_detection_type(self) -> None:
        """Test that detection_type can be explicitly set to 'LAYERING'."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[base_time],
        )

        # Assert
        assert sequence.detection_type == "LAYERING"
        assert sequence.side == "BUY"
        assert sequence.num_cancelled_orders == 3

    def test_wash_trading_sequence_with_required_fields(self) -> None:
        """Test wash trading sequence with alternation_percentage."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=75.0,
            price_change_percentage=None,
        )

        # Assert
        assert sequence.detection_type == "WASH_TRADING"
        assert sequence.side is None
        assert sequence.num_cancelled_orders is None
        assert sequence.order_timestamps is None
        assert sequence.alternation_percentage == 75.0
        assert sequence.price_change_percentage is None

    def test_wash_trading_sequence_with_price_change(self) -> None:
        """Test wash trading sequence with alternation_percentage and price_change_percentage."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=80.0,
            price_change_percentage=1.5,
        )

        # Assert
        assert sequence.detection_type == "WASH_TRADING"
        assert sequence.alternation_percentage == 80.0
        assert sequence.price_change_percentage == 1.5

    def test_backward_compatibility_existing_code(self) -> None:
        """Test that existing code creating SuspiciousSequence still works."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act - Simulate existing code pattern (no detection_type specified)
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[base_time],
        )

        # Assert - Should default to LAYERING
        assert sequence.detection_type == "LAYERING"
        assert sequence.side == "BUY"
        assert sequence.num_cancelled_orders == 3

    def test_layering_sequence_fields_not_none(self) -> None:
        """Test that layering sequences have required fields set (not None)."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="SELL",
            num_cancelled_orders=5,
            order_timestamps=[base_time, base_time],
        )

        # Assert
        assert sequence.side is not None
        assert sequence.num_cancelled_orders is not None
        assert sequence.order_timestamps is not None
        assert sequence.alternation_percentage is None
        assert sequence.price_change_percentage is None

    def test_wash_trading_sequence_optional_fields(self) -> None:
        """Test that wash trading sequences can have None for layering-specific fields."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=10000,
            total_sell_qty=10000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=100.0,
        )

        # Assert
        assert sequence.side is None
        assert sequence.num_cancelled_orders is None
        assert sequence.order_timestamps is None
        assert sequence.alternation_percentage == 100.0
        assert sequence.price_change_percentage is None

    def test_detection_type_literal_values(self) -> None:
        """Test that detection_type only accepts valid literal values."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act & Assert - Valid values
        sequence1 = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[base_time],
        )
        assert sequence1.detection_type == "LAYERING"

        sequence2 = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=60.0,
        )
        assert sequence2.detection_type == "WASH_TRADING"

    def test_alternation_percentage_float_values(self) -> None:
        """Test that alternation_percentage accepts float values."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act & Assert
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=10000,
            total_sell_qty=10000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=65.5,
        )

        # Assert
        assert sequence.alternation_percentage == 65.5
        assert isinstance(sequence.alternation_percentage, float)

    def test_price_change_percentage_optional(self) -> None:
        """Test that price_change_percentage is optional for wash trading."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # Act - Without price_change_percentage
        sequence1 = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=10000,
            total_sell_qty=10000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=70.0,
        )

        # Act - With price_change_percentage
        sequence2 = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=10000,
            total_sell_qty=10000,
            detection_type="WASH_TRADING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=70.0,
            price_change_percentage=2.3,
        )

        # Assert
        assert sequence1.price_change_percentage is None
        assert sequence2.price_change_percentage == 2.3

    def test_immutability_preserved(self) -> None:
        """Test that SuspiciousSequence remains immutable (frozen dataclass)."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        sequence = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=base_time,
            end_timestamp=base_time,
            total_buy_qty=1000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[base_time],
        )

        # Act & Assert - Should raise FrozenInstanceError
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            sequence.detection_type = "WASH_TRADING"  # type: ignore[misc]

