"""
Unit tests for detection_utils module.

Tests shared utility functions used across detection algorithms.
"""

from datetime import datetime, timedelta, timezone

import pytest

from layering_detection.utils.detection_utils import (
    get_opposite_side,
    group_events_by_account_product,
    validate_positive,
)
from layering_detection.models import TransactionEvent


class TestGroupEventsByAccountProduct:
    """Test suite for group_events_by_account_product() function."""

    def test_groups_events_by_account_and_product(self) -> None:
        """Test that events are grouped by (account_id, product_id) tuple."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=101.0,
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC002",
                product_id="GOOG",
                side="BUY",
                price=200.0,
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        assert len(grouped) == 2
        assert ("ACC001", "IBM") in grouped
        assert ("ACC002", "GOOG") in grouped
        assert len(grouped[("ACC001", "IBM")]) == 2
        assert len(grouped[("ACC002", "GOOG")]) == 1

    def test_sorts_events_by_timestamp_within_group(self) -> None:
        """Test that events within each group are sorted by timestamp."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time.replace(second=30),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=101.0,
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time.replace(second=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.5,
                quantity=750,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        group_events = grouped[("ACC001", "IBM")]
        assert len(group_events) == 3
        assert group_events[0].timestamp == base_time.replace(second=10)
        assert group_events[1].timestamp == base_time.replace(second=20)
        assert group_events[2].timestamp == base_time.replace(second=30)

    def test_handles_empty_event_list(self) -> None:
        """Test that empty event list returns empty dictionary."""
        # Arrange
        events: list[TransactionEvent] = []

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        assert grouped == {}

    def test_handles_single_event(self) -> None:
        """Test that single event is grouped correctly."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        assert len(grouped) == 1
        assert ("ACC001", "IBM") in grouped
        assert len(grouped[("ACC001", "IBM")]) == 1

    def test_handles_multiple_accounts_same_product(self) -> None:
        """Test that different accounts with same product are grouped separately."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC002",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        assert len(grouped) == 2
        assert ("ACC001", "IBM") in grouped
        assert ("ACC002", "IBM") in grouped

    def test_handles_same_account_different_products(self) -> None:
        """Test that same account with different products are grouped separately."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="GOOG",
                side="BUY",
                price=200.0,
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        assert len(grouped) == 2
        assert ("ACC001", "IBM") in grouped
        assert ("ACC001", "GOOG") in grouped

    def test_handles_events_with_identical_timestamps(self) -> None:
        """Test that events with identical timestamps are handled correctly."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=100.0,
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=base_time,  # Same timestamp
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=101.0,
                quantity=500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        grouped = group_events_by_account_product(events)

        # Assert
        group_events = grouped[("ACC001", "IBM")]
        assert len(group_events) == 2
        # Both events should be in the group (order may vary for identical timestamps)


class TestValidatePositive:
    """Test suite for validate_positive() function."""

    def test_validates_positive_integer(self) -> None:
        """Test that positive integer passes validation."""
        # Arrange
        value = 10
        name = "min_trades"

        # Act & Assert
        validate_positive(value, name)  # Should not raise

    def test_validates_positive_float(self) -> None:
        """Test that positive float passes validation."""
        # Arrange
        value = 60.5
        name = "min_percentage"

        # Act & Assert
        validate_positive(value, name)  # Should not raise

    def test_validates_positive_timedelta(self) -> None:
        """Test that positive timedelta passes validation."""
        # Arrange
        value = timedelta(seconds=10)
        name = "orders_window"

        # Act & Assert
        validate_positive(value, name)  # Should not raise

    def test_raises_value_error_for_zero_integer(self) -> None:
        """Test that zero integer raises ValueError."""
        # Arrange
        value = 0
        name = "min_trades"

        # Act & Assert
        with pytest.raises(ValueError, match="min_trades must be positive, got zero value: 0"):
            validate_positive(value, name)

    def test_raises_value_error_for_zero_float(self) -> None:
        """Test that zero float raises ValueError."""
        # Arrange
        value = 0.0
        name = "min_percentage"

        # Act & Assert
        with pytest.raises(ValueError, match="min_percentage must be positive, got zero value: 0.0"):
            validate_positive(value, name)

    def test_raises_value_error_for_zero_timedelta(self) -> None:
        """Test that zero timedelta raises ValueError."""
        # Arrange
        value = timedelta(0)
        name = "orders_window"

        # Act & Assert
        with pytest.raises(ValueError, match="orders_window must be positive, got zero value: 0:00:00"):
            validate_positive(value, name)

    def test_raises_value_error_for_negative_integer(self) -> None:
        """Test that negative integer raises ValueError."""
        # Arrange
        value = -5
        name = "min_trades"

        # Act & Assert
        with pytest.raises(ValueError, match="min_trades must be positive, got negative value: -5"):
            validate_positive(value, name)

    def test_raises_value_error_for_negative_float(self) -> None:
        """Test that negative float raises ValueError."""
        # Arrange
        value = -10.5
        name = "min_percentage"

        # Act & Assert
        with pytest.raises(ValueError, match="min_percentage must be positive, got negative value: -10.5"):
            validate_positive(value, name)

    def test_raises_value_error_for_negative_timedelta(self) -> None:
        """Test that negative timedelta raises ValueError."""
        # Arrange
        value = timedelta(seconds=-5)
        name = "orders_window"

        # Act & Assert
        with pytest.raises(ValueError, match="orders_window must be positive, got negative value: -5.0 seconds"):
            validate_positive(value, name)

    def test_raises_type_error_for_unsupported_type(self) -> None:
        """Test that unsupported type raises TypeError."""
        # Arrange
        value = "invalid"
        name = "test_field"

        # Act & Assert
        with pytest.raises(TypeError, match="Unsupported type for validation: str"):
            validate_positive(value, name)

    def test_raises_type_error_for_none(self) -> None:
        """Test that None raises TypeError."""
        # Arrange
        value = None
        name = "test_field"

        # Act & Assert
        with pytest.raises(TypeError):
            validate_positive(value, name)

    def test_handles_very_small_positive_float(self) -> None:
        """Test that very small positive float passes validation."""
        # Arrange
        value = 0.0001
        name = "min_percentage"

        # Act & Assert
        validate_positive(value, name)  # Should not raise

    def test_handles_very_large_positive_integer(self) -> None:
        """Test that very large positive integer passes validation."""
        # Arrange
        value = 999999999
        name = "min_trades"

        # Act & Assert
        validate_positive(value, name)  # Should not raise

    def test_handles_very_small_positive_timedelta(self) -> None:
        """Test that very small positive timedelta passes validation."""
        # Arrange
        value = timedelta(microseconds=1)
        name = "orders_window"

        # Act & Assert
        validate_positive(value, name)  # Should not raise


class TestGetOppositeSide:
    """Test suite for get_opposite_side() function."""

    def test_returns_sell_for_buy(self) -> None:
        """Test that BUY returns SELL."""
        # Arrange
        side = "BUY"

        # Act
        result = get_opposite_side(side)

        # Assert
        assert result == "SELL"

    def test_returns_buy_for_sell(self) -> None:
        """Test that SELL returns BUY."""
        # Arrange
        side = "SELL"

        # Act
        result = get_opposite_side(side)

        # Assert
        assert result == "BUY"

    @pytest.mark.parametrize(
        "side,expected",
        [
            ("BUY", "SELL"),
            ("SELL", "BUY"),
        ],
    )
    def test_opposite_side_round_trip(self, side: str, expected: str) -> None:
        """Test that opposite side conversion works both ways."""
        # Act
        result = get_opposite_side(side)

        # Assert
        assert result == expected
        # Round trip: opposite of opposite should be original
        assert get_opposite_side(result) == side
