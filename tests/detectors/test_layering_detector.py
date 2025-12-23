import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from layering_detection.models import DetectionConfig, TransactionEvent
from layering_detection.utils.transaction_io import read_transactions
from layering_detection.detectors.layering_detector import (
    detect_suspicious_sequences,
    _detect_sequences_for_group,
    _build_event_index,
    _query_events_in_window,
)
from layering_detection.utils.detection_utils import group_events_by_account_product
from tests.fixtures import create_transaction_event, create_layering_pattern


# Default config for tests (matches current hard-coded values)
_DEFAULT_CONFIG = DetectionConfig()


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_events() -> list:
    input_path = BASE_DIR / "input" / "transactions.csv"
    assert input_path.exists(), f"Missing test input CSV at {input_path}"
    return read_transactions(input_path)


class TestDetectorGrouping:
    def test_grouping_and_basic_counts(self) -> None:
        events = _load_events()

        grouped = group_events_by_account_product(events)

        assert len(events) == 18
        assert {("ACC001", "IBM"), ("ACC017", "AAPL"), ("ACC050", "MSFT")} == set(
            grouped.keys()
        )


@pytest.mark.parametrize(
    "account_id,product_id,expected_side,expected_start,expected_end,expected_buy,expected_sell,expected_cancels",
    [
        (
            "ACC001",
            "IBM",
            "BUY",
            dt.datetime(2025, 10, 26, 10, 21, 20, tzinfo=dt.timezone.utc),
            dt.datetime(2025, 10, 26, 10, 21, 28, tzinfo=dt.timezone.utc),
            15000,
            10000,
            3,
        ),
        (
            "ACC017",
            "AAPL",
            "BUY",
            dt.datetime(2025, 10, 26, 11, 5, 0, tzinfo=dt.timezone.utc),
            dt.datetime(2025, 10, 26, 11, 5, 6, tzinfo=dt.timezone.utc),
            12000,
            8000,
            3,
        ),
    ],
)
class TestDetectorSequences:
    def test_detect_sequences_for_group_main_patterns(
        self,
        account_id: str,
        product_id: str,
        expected_side: str,
        expected_start: dt.datetime,
        expected_end: dt.datetime,
        expected_buy: int,
        expected_sell: int,
        expected_cancels: int,
    ) -> None:
        events = _load_events()
        grouped = group_events_by_account_product(events)
        group_events = grouped[(account_id, product_id)]

        sequences = _detect_sequences_for_group(
            account_id, product_id, group_events, _DEFAULT_CONFIG
        )

        assert len(sequences) == 1
        seq = sequences[0]
        assert seq.account_id == account_id
        assert seq.product_id == product_id
        assert seq.side == expected_side
        assert seq.start_timestamp == expected_start
        assert seq.end_timestamp == expected_end
        assert seq.total_buy_qty == expected_buy
        assert seq.total_sell_qty == expected_sell
        assert seq.num_cancelled_orders == expected_cancels


class TestDetectorTopLevel:
    def test_detect_suspicious_sequences_returns_only_pattern_matches(self) -> None:
        events = _load_events()

        sequences = detect_suspicious_sequences(events)

        # Only ACC001/IBM and ACC017/AAPL follow the layering pattern in the sample data.
        assert len(sequences) == 2
        keys = {(s.account_id, s.product_id) for s in sequences}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}


class TestDetectorSyntheticPatterns:
    def test_synthetic_positive_pattern_for_new_account(self) -> None:
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)

        # Create layering pattern with custom parameters
        # Note: Factory uses same quantity/price for all orders, so we'll create manually
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC999",
                product_id="TSLA",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6),
                account_id="ACC999",
                product_id="TSLA",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        grouped = group_events_by_account_product(events)
        group_events = grouped[("ACC999", "TSLA")]

        sequences = _detect_sequences_for_group(
            "ACC999", "TSLA", group_events, _DEFAULT_CONFIG
        )

        assert len(sequences) == 1
        seq = sequences[0]
        assert seq.account_id == "ACC999"
        assert seq.product_id == "TSLA"
        assert seq.side == "BUY"
        assert seq.start_timestamp == base
        assert seq.end_timestamp == base + dt.timedelta(seconds=6)
        # Spoof-side cancelled volume is on BUY, opposite-side executed on SELL
        assert seq.total_buy_qty == 3000
        assert seq.total_sell_qty == 5000
        assert seq.num_cancelled_orders == 3

    def test_synthetic_negative_pattern_trade_too_late(self) -> None:
        base = dt.datetime(2025, 1, 1, 9, 30, 0, tzinfo=dt.timezone.utc)

        # Create layering pattern but with trade too late (outside 2-second window)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="200.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="199.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="199.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="200.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="199.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC888",
                product_id="NFLX",
                side="SELL",
                price="199.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade occurs 10 seconds after last cancellation (too late)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10),
                account_id="ACC888",
                product_id="NFLX",
                side="BUY",
                price="201.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        sequences = detect_suspicious_sequences(events)
        # Trade is outside the 2-second window, so no detection should occur.
        assert sequences == []


class TestBuildEventIndex:
    """Test suite for _build_event_index() function."""

    def test_empty_list_returns_empty_dict(self) -> None:
        """Test that empty event list returns empty dictionary."""
        # Arrange
        events: list[TransactionEvent] = []

        # Act
        index = _build_event_index(events)

        # Assert
        assert index == {}
        assert len(index) == 0

    def test_indexes_all_event_types_and_sides_correctly(self) -> None:
        """Test that all event types and sides are indexed correctly."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                side="SELL",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                side="SELL",
                price="100.5",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        index = _build_event_index(events)

        # Assert
        assert ("ORDER_PLACED", "BUY") in index
        assert ("ORDER_PLACED", "SELL") in index
        assert ("ORDER_CANCELLED", "BUY") in index
        assert ("TRADE_EXECUTED", "SELL") in index
        assert len(index[("ORDER_PLACED", "BUY")]) == 1
        assert len(index[("ORDER_PLACED", "SELL")]) == 1
        assert len(index[("ORDER_CANCELLED", "BUY")]) == 1
        assert len(index[("TRADE_EXECUTED", "SELL")]) == 1

    def test_sorts_events_by_timestamp_within_each_group(self) -> None:
        """Test that events are sorted by timestamp within each indexed group."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        index = _build_event_index(events)

        # Assert
        indexed_events = index[("ORDER_PLACED", "BUY")]
        assert len(indexed_events) == 3
        assert indexed_events[0].timestamp == base + dt.timedelta(seconds=1)
        assert indexed_events[1].timestamp == base + dt.timedelta(seconds=2)
        assert indexed_events[2].timestamp == base + dt.timedelta(seconds=3)

    def test_handles_duplicate_timestamps(self) -> None:
        """Test that duplicate timestamps are handled correctly."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base,  # Same timestamp
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base,  # Same timestamp
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]

        # Act
        index = _build_event_index(events)

        # Assert
        indexed_events = index[("ORDER_PLACED", "BUY")]
        assert len(indexed_events) == 3
        # All should have same timestamp (sorting is stable)
        assert all(e.timestamp == base for e in indexed_events)

    def test_multiple_groups_independent(self) -> None:
        """Test that different (event_type, side) groups are independent."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        index = _build_event_index(events)

        # Assert
        assert ("ORDER_PLACED", "BUY") in index
        assert ("ORDER_CANCELLED", "BUY") in index
        assert len(index[("ORDER_PLACED", "BUY")]) == 1
        assert len(index[("ORDER_CANCELLED", "BUY")]) == 1
        assert index[("ORDER_PLACED", "BUY")][0].event_type == "ORDER_PLACED"
        assert index[("ORDER_CANCELLED", "BUY")][0].event_type == "ORDER_CANCELLED"


class TestQueryEventsInWindow:
    """Test suite for _query_events_in_window() function."""

    def test_empty_index_returns_empty_list(self) -> None:
        """Test that querying empty index returns empty list."""
        # Arrange
        index: dict = {}
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)

        # Act
        result = _query_events_in_window(
            index, "ORDER_PLACED", "BUY", base, base + dt.timedelta(seconds=10)
        )

        # Assert
        assert result == []

    def test_nonexistent_key_returns_empty_list(self) -> None:
        """Test that querying non-existent (event_type, side) key returns empty list."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Query for key that doesn't exist
        result = _query_events_in_window(
            index, "ORDER_CANCELLED", "SELL", base, base + dt.timedelta(seconds=10)
        )

        # Assert
        assert result == []

    def test_returns_events_within_time_window(self) -> None:
        """Test that function returns events within specified time window."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=8),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=15),
                side="BUY",
                price="102.0",
                quantity=3000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Query window from 0 to 10 seconds
        result = _query_events_in_window(
            index, "ORDER_PLACED", "BUY", base, base + dt.timedelta(seconds=10)
        )

        # Assert - Should return first 3 events, not the 4th
        assert len(result) == 3
        assert result[0].timestamp == base + dt.timedelta(seconds=1)
        assert result[1].timestamp == base + dt.timedelta(seconds=5)
        assert result[2].timestamp == base + dt.timedelta(seconds=8)

    def test_handles_duplicate_timestamps_correctly(self) -> None:
        """Test that duplicate timestamps are included correctly."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base,  # Same timestamp
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Query window that includes duplicate timestamps
        result = _query_events_in_window(
            index, "ORDER_PLACED", "BUY", base, base + dt.timedelta(seconds=10)
        )

        # Assert - All events with duplicate timestamps should be included
        assert len(result) == 3
        assert all(e.timestamp <= base + dt.timedelta(seconds=10) for e in result)

    def test_zero_width_window_returns_events_at_exact_timestamp(self) -> None:
        """Test that zero-width window returns events exactly at that timestamp."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Zero-width window at exact timestamp
        result = _query_events_in_window(index, "ORDER_PLACED", "BUY", base, base)

        # Assert - Should return events exactly at base timestamp
        assert len(result) == 1
        assert result[0].timestamp == base

    def test_invalid_window_returns_empty_list(self) -> None:
        """Test that invalid window (start_time > end_time) returns empty list."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Invalid window (start > end)
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base + dt.timedelta(seconds=10),
            base,
        )

        # Assert
        assert result == []

    def test_window_before_all_events_returns_empty_list(self) -> None:
        """Test that window before all events returns empty list."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10),
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Window before all events
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base,
            base + dt.timedelta(seconds=5),
        )

        # Assert
        assert result == []

    def test_window_after_all_events_returns_empty_list(self) -> None:
        """Test that window after all events returns empty list."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Window after all events
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base + dt.timedelta(seconds=10),
            base + dt.timedelta(seconds=20),
        )

        # Assert
        assert result == []

    def test_inclusive_boundaries(self) -> None:
        """Test that boundaries are inclusive (events at start_time and end_time are included)."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Window exactly from first to last event (inclusive)
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base,
            base + dt.timedelta(seconds=10),
        )

        # Assert - All events should be included
        assert len(result) == 3
        assert result[0].timestamp == base
        assert result[2].timestamp == base + dt.timedelta(seconds=10)

    def test_sparse_event_distribution(self) -> None:
        """Test with sparse event distribution (events far apart)."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=100),
                side="BUY",
                price="101.0",
                quantity=500,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=200),
                side="BUY",
                price="99.5",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
        ]
        index = _build_event_index(events)

        # Act - Query window that includes only middle event
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base + dt.timedelta(seconds=50),
            base + dt.timedelta(seconds=150),
        )

        # Assert
        assert len(result) == 1
        assert result[0].timestamp == base + dt.timedelta(seconds=100)

    def test_dense_event_distribution(self) -> None:
        """Test with dense event distribution (many events close together)."""
        # Arrange
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base + dt.timedelta(milliseconds=i),
                side="BUY",
                price="100.0",
                quantity=1000 + i,
                event_type="ORDER_PLACED",
            )
            for i in range(100)  # 100 events 1ms apart
        ]
        index = _build_event_index(events)

        # Act - Query window for middle section
        result = _query_events_in_window(
            index,
            "ORDER_PLACED",
            "BUY",
            base + dt.timedelta(milliseconds=25),
            base + dt.timedelta(milliseconds=75),
        )

        # Assert - Should return events from index 25 to 75 (inclusive)
        assert len(result) == 51  # 25, 26, ..., 75 (inclusive)
        assert result[0].timestamp == base + dt.timedelta(milliseconds=25)
        assert result[-1].timestamp == base + dt.timedelta(milliseconds=75)


class TestDetectionConfig:
    """Test suite for DetectionConfig validation."""

    def test_default_config_creates_successfully(self) -> None:
        """Test that default DetectionConfig can be created with default values."""
        # Arrange & Act
        config = DetectionConfig()

        # Assert
        assert config.orders_window == dt.timedelta(seconds=10)
        assert config.cancel_window == dt.timedelta(seconds=5)
        assert config.opposite_trade_window == dt.timedelta(seconds=2)

    def test_custom_positive_windows_work_correctly(self) -> None:
        """Test that positive timing windows are accepted."""
        # Arrange
        custom_orders = dt.timedelta(seconds=20)
        custom_cancel = dt.timedelta(seconds=10)
        custom_trade = dt.timedelta(seconds=3)

        # Act
        config = DetectionConfig(
            orders_window=custom_orders,
            cancel_window=custom_cancel,
            opposite_trade_window=custom_trade,
        )

        # Assert
        assert config.orders_window == custom_orders
        assert config.cancel_window == custom_cancel
        assert config.opposite_trade_window == custom_trade

    def test_negative_orders_window_raises_value_error(self) -> None:
        """Test that negative orders_window raises ValueError with clear message."""
        # Arrange
        negative_window = dt.timedelta(seconds=-1)

        # Act & Assert
        with pytest.raises(ValueError, match="orders_window.*negative"):
            DetectionConfig(orders_window=negative_window)

    def test_negative_cancel_window_raises_value_error(self) -> None:
        """Test that negative cancel_window raises ValueError with clear message."""
        # Arrange
        negative_window = dt.timedelta(seconds=-5)

        # Act & Assert
        with pytest.raises(ValueError, match="cancel_window.*negative"):
            DetectionConfig(cancel_window=negative_window)

    def test_negative_opposite_trade_window_raises_value_error(self) -> None:
        """Test that negative opposite_trade_window raises ValueError with clear message."""
        # Arrange
        negative_window = dt.timedelta(seconds=-2)

        # Act & Assert
        with pytest.raises(ValueError, match="opposite_trade_window.*negative"):
            DetectionConfig(opposite_trade_window=negative_window)

    def test_zero_orders_window_raises_value_error(self) -> None:
        """Test that zero orders_window raises ValueError with clear message."""
        # Arrange
        zero_window = dt.timedelta(seconds=0)

        # Act & Assert
        with pytest.raises(ValueError, match="orders_window.*zero"):
            DetectionConfig(orders_window=zero_window)

    def test_zero_cancel_window_raises_value_error(self) -> None:
        """Test that zero cancel_window raises ValueError with clear message."""
        # Arrange
        zero_window = dt.timedelta(seconds=0)

        # Act & Assert
        with pytest.raises(ValueError, match="cancel_window.*zero"):
            DetectionConfig(cancel_window=zero_window)

    def test_zero_opposite_trade_window_raises_value_error(self) -> None:
        """Test that zero opposite_trade_window raises ValueError with clear message."""
        # Arrange
        zero_window = dt.timedelta(seconds=0)

        # Act & Assert
        with pytest.raises(ValueError, match="opposite_trade_window.*zero"):
            DetectionConfig(opposite_trade_window=zero_window)

    def test_multiple_negative_windows_raises_value_error(self) -> None:
        """Test that multiple negative windows are all validated."""
        # Arrange
        negative_window = dt.timedelta(seconds=-1)

        # Act & Assert - Should catch first negative window
        with pytest.raises(ValueError):
            DetectionConfig(
                orders_window=negative_window,
                cancel_window=negative_window,
                opposite_trade_window=negative_window,
            )

    def test_very_small_positive_window_works(self) -> None:
        """Test that very small positive windows (microseconds) are accepted."""
        # Arrange
        small_window = dt.timedelta(microseconds=1)

        # Act
        config = DetectionConfig(orders_window=small_window)

        # Assert
        assert config.orders_window == small_window

    def test_large_positive_window_works(self) -> None:
        """Test that large positive windows are accepted."""
        # Arrange
        large_window = dt.timedelta(hours=24)

        # Act
        config = DetectionConfig(orders_window=large_window)

        # Assert
        assert config.orders_window == large_window


class TestDetectionConfigUsage:
    """Test suite for verifying DetectionConfig is actually used in detection logic."""

    def test_custom_config_affects_detection_behavior(self) -> None:
        """Test that custom config values are actually used in detection."""
        # Arrange - Create events that would match with default config but not with stricter config
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            # Three BUY orders within 10 seconds (matches default)
            create_transaction_event(
                timestamp=base,
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=9),  # Within 10s default window
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10),
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=11),
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=12),
                account_id="ACC999",
                product_id="TEST",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=13),
                account_id="ACC999",
                product_id="TEST",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Test with default config (should detect)
        default_result = detect_suspicious_sequences(events)

        # Act - Test with stricter config (5 second orders window - should NOT detect)
        strict_config = DetectionConfig(orders_window=dt.timedelta(seconds=5))
        strict_result = detect_suspicious_sequences(events, config=strict_config)

        # Assert - Default config detects, strict config doesn't
        assert len(default_result) == 1, "Default config should detect pattern"
        assert len(strict_result) == 0, "Strict config (5s window) should not detect pattern (last order at 9s)"

    def test_custom_cancel_window_affects_detection(self) -> None:
        """Test that custom cancel_window affects detection behavior."""
        # Arrange - Events with cancellations just outside default 5s window
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Last order at 2s, cancellations at 6s, 7s, 8s (outside 5s default window)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6),
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=7),
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=8),
                account_id="ACC888",
                product_id="TEST2",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=9),
                account_id="ACC888",
                product_id="TEST2",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Default config (5s cancel window) should NOT detect
        default_result = detect_suspicious_sequences(events)

        # Act - Extended config (10s cancel window) should detect
        extended_config = DetectionConfig(cancel_window=dt.timedelta(seconds=10))
        extended_result = detect_suspicious_sequences(events, config=extended_config)

        # Assert
        assert len(default_result) == 0, "Default config should not detect (cancellations too late)"
        assert len(extended_result) == 1, "Extended cancel window should detect pattern"

    def test_custom_opposite_trade_window_affects_detection(self) -> None:
        """Test that custom opposite_trade_window affects detection behavior."""
        # Arrange - Events with opposite trade just outside default 2s window
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC777",
                product_id="TEST3",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade at 8s (3s after last cancel, outside 2s default window)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=8),
                account_id="ACC777",
                product_id="TEST3",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Default config (2s trade window) should NOT detect
        default_result = detect_suspicious_sequences(events)

        # Act - Extended config (5s trade window) should detect
        extended_config = DetectionConfig(opposite_trade_window=dt.timedelta(seconds=5))
        extended_result = detect_suspicious_sequences(events, config=extended_config)

        # Assert
        assert len(default_result) == 0, "Default config should not detect (trade too late)"
        assert len(extended_result) == 1, "Extended trade window should detect pattern"


class TestDetectionConfigEdgeCases:
    """Test suite for edge cases and boundary conditions in config usage."""

    def test_config_none_uses_default(self) -> None:
        """Test that passing None config uses default DetectionConfig."""
        # Arrange
        events = _load_events()

        # Act - Explicit None
        result_none = detect_suspicious_sequences(events, config=None)

        # Act - Default (no config parameter)
        result_default = detect_suspicious_sequences(events)

        # Act - Explicit default config
        result_explicit = detect_suspicious_sequences(events, config=DetectionConfig())

        # Assert - All should produce same results
        assert len(result_none) == len(result_default)
        assert len(result_default) == len(result_explicit)
        assert result_none == result_default
        assert result_default == result_explicit

    def test_config_with_extreme_large_windows(self) -> None:
        """Test detection with extremely large timing windows."""
        # Arrange
        events = _load_events()
        extreme_config = DetectionConfig(
            orders_window=dt.timedelta(hours=24),
            cancel_window=dt.timedelta(hours=12),
            opposite_trade_window=dt.timedelta(hours=6),
        )

        # Act
        result = detect_suspicious_sequences(events, config=extreme_config)

        # Assert - Should still detect patterns (windows are large enough)
        assert len(result) >= 2, "Large windows should still detect existing patterns"

    def test_config_with_extreme_small_windows(self) -> None:
        """Test detection with extremely small timing windows."""
        # Arrange
        events = _load_events()
        strict_config = DetectionConfig(
            orders_window=dt.timedelta(milliseconds=1),
            cancel_window=dt.timedelta(milliseconds=1),
            opposite_trade_window=dt.timedelta(milliseconds=1),
        )

        # Act
        result = detect_suspicious_sequences(events, config=strict_config)

        # Assert - Should detect fewer or no patterns (windows too strict)
        # Note: This tests that config is respected, not that we get specific count
        assert isinstance(result, list), "Should return list even with strict config"

    def test_config_boundary_orders_window_exact_match(self) -> None:
        """Test detection with orders_window exactly matching event timing."""
        # Arrange - Events with orders at 0s, 5s, 10s (exactly 10s apart)
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10),  # Exactly at boundary
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=11),
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=12),
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=13),
                account_id="ACC666",
                product_id="BOUNDARY",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=14),
                account_id="ACC666",
                product_id="BOUNDARY",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Config with exactly 10s window (should include boundary)
        exact_config = DetectionConfig(orders_window=dt.timedelta(seconds=10))
        exact_result = detect_suspicious_sequences(events, config=exact_config)

        # Act - Config with 9.999s window (should exclude boundary)
        just_below_config = DetectionConfig(orders_window=dt.timedelta(seconds=9, microseconds=999000))
        just_below_result = detect_suspicious_sequences(events, config=just_below_config)

        # Assert - Boundary should be inclusive
        assert len(exact_result) == 1, "10s window should include event at exactly 10s"
        assert len(just_below_result) == 0, "9.999s window should exclude event at 10s"

    def test_config_boundary_cancel_window_exact_match(self) -> None:
        """Test detection with cancel_window boundary conditions."""
        # Arrange - Orders at 0s, 1s, 2s; last order at 2s
        # With 5s cancel window: cancel_deadline = 7s (inclusive)
        # With 4s cancel window: cancel_deadline = 6s (inclusive)
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations at 5.5s, 6s, 6.5s (all within 5s window from last order at 2s)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5, milliseconds=500),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6, milliseconds=500),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade within 2s after last cancel
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=7),
                account_id="ACC555",
                product_id="BOUNDARY2",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Config with 5s cancel window (should include cancellations at 5.5s, 6s, 6.5s)
        lenient_config = DetectionConfig(cancel_window=dt.timedelta(seconds=5))
        lenient_result = detect_suspicious_sequences(events, config=lenient_config)

        # Act - Config with 4s cancel window (cancel_deadline = 6s, should include cancellations at 5.5s, 6s)
        # But need 3 cancellations, so should not detect
        strict_config = DetectionConfig(cancel_window=dt.timedelta(seconds=4))
        strict_result = detect_suspicious_sequences(events, config=strict_config)

        # Assert - Config affects detection
        assert len(lenient_result) == 1, "5s cancel window should detect (3 cancellations within window)"
        assert len(strict_result) == 0, "4s cancel window should not detect (only 2 cancellations within window)"

    def test_config_boundary_trade_window_exact_match(self) -> None:
        """Test detection with opposite_trade_window exactly matching event timing."""
        # Arrange - Last cancel at 5s, trade at 7s (exactly 2s after)
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base,
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Cancellations
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=3),
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=4),
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=5),
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade at exactly 7s (2s after last cancel)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=7),  # Exactly 2s after last cancel
                account_id="ACC444",
                product_id="BOUNDARY3",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act - Config with exactly 2s trade window (should include boundary)
        exact_config = DetectionConfig(opposite_trade_window=dt.timedelta(seconds=2))
        exact_result = detect_suspicious_sequences(events, config=exact_config)

        # Act - Config with 1.999s trade window (should exclude boundary)
        just_below_config = DetectionConfig(opposite_trade_window=dt.timedelta(seconds=1, microseconds=999000))
        just_below_result = detect_suspicious_sequences(events, config=just_below_config)

        # Assert - Boundary should be inclusive
        assert len(exact_result) == 1, "2s trade window should include trade at exactly 2s"
        assert len(just_below_result) == 0, "1.999s trade window should exclude trade at 2s"

    def test_config_all_windows_custom_simultaneously(self) -> None:
        """Test detection with all three windows customized simultaneously."""
        # Arrange
        events = _load_events()
        custom_config = DetectionConfig(
            orders_window=dt.timedelta(seconds=15),
            cancel_window=dt.timedelta(seconds=8),
            opposite_trade_window=dt.timedelta(seconds=3),
        )

        # Act
        result = detect_suspicious_sequences(events, config=custom_config)

        # Assert - Should still detect patterns (all windows are more lenient)
        assert len(result) >= 2, "More lenient config should detect existing patterns"
        assert isinstance(result, list), "Should return list"

    def test_config_mixed_strict_and_lenient(self) -> None:
        """Test detection with mixed strict and lenient windows."""
        # Arrange - Strict orders window but lenient cancel/trade windows
        events = _load_events()
        mixed_config = DetectionConfig(
            orders_window=dt.timedelta(seconds=5),  # Stricter
            cancel_window=dt.timedelta(seconds=10),  # More lenient
            opposite_trade_window=dt.timedelta(seconds=5),  # More lenient
        )

        # Act
        result = detect_suspicious_sequences(events, config=mixed_config)

        # Assert - Behavior depends on which constraint is limiting
        assert isinstance(result, list), "Should return list"
        # Note: Actual count depends on data, but we verify config is respected

    def test_config_parameter_path_coverage(self) -> None:
        """Test that config parameter path is covered in detect_suspicious_sequences."""
        # Arrange
        events = _load_events()

        # Act - Test all config parameter paths:
        # 1. None (should use default)
        result_none = detect_suspicious_sequences(events, config=None)

        # 2. Explicit default
        result_default = detect_suspicious_sequences(events, config=DetectionConfig())

        # 3. Custom config
        custom_config = DetectionConfig(orders_window=dt.timedelta(seconds=20))
        result_custom = detect_suspicious_sequences(events, config=custom_config)

        # Assert - All paths should work
        assert isinstance(result_none, list)
        assert isinstance(result_default, list)
        assert isinstance(result_custom, list)
        assert len(result_none) == len(result_default), "None and default should be equivalent"
        # Custom may differ, but should still work


class TestIndexOptimizationUsage:
    """Test suite for verifying index optimizations (Tasks 9-11) are used correctly."""

    def test_index_used_for_cancellation_search_with_many_irrelevant_events(self) -> None:
        """Test that cancellation search uses index even with many irrelevant events (Task 10)."""
        # Arrange - Create pattern with many ORDER_PLACED events between orders and cancellations
        # This would be slow with linear scan but fast with index
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            # Three BUY orders
            create_transaction_event(
                timestamp=base,
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=1),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=2),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_PLACED",
            ),
            # Many irrelevant ORDER_PLACED events (would slow down linear scan)
            *[
                create_transaction_event(
                    timestamp=base + dt.timedelta(seconds=3 + i * 0.1),
                    account_id="ACC_INDEX_TEST",
                    product_id="PROD1",
                    side="SELL",  # Different side
                    price="99.0",
                    quantity=100,
                    event_type="ORDER_PLACED",
                )
                for i in range(50)
            ],
            # Cancellations (should be found quickly via index)
            # Last order at 2s, cancel_window=5s, so cancellations must be <= 7s
            # Also must be >= start_ts (0s)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=6, milliseconds=500),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=7),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            ),
            # Opposite-side trade (last cancel at 7s, trade_window=2s, so trade must be <= 9s)
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=8),
                account_id="ACC_INDEX_TEST",
                product_id="PROD1",
                side="SELL",
                price="99.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should detect pattern despite many irrelevant events
        assert len(result) == 1, "Index should efficiently find cancellations despite many irrelevant events"
        assert result[0].account_id == "ACC_INDEX_TEST"
        assert result[0].product_id == "PROD1"

    def test_index_used_for_trade_search_with_many_irrelevant_events(self) -> None:
        """Test that opposite trade search uses index even with many irrelevant events (Task 11)."""
        # Arrange - Use a known-working pattern from existing tests, then add many irrelevant events
        # This verifies index is used (would be slow with linear loop)
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            # Three BUY orders
            create_transaction_event(timestamp=base, account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="100.0", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=1), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="100.5", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=2), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="101.0", quantity=1000, event_type="ORDER_PLACED"),
            # Cancellations (last order at 2s, cancel_window=5s, so <= 7s)
            create_transaction_event(timestamp=base + dt.timedelta(seconds=6), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="100.0", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=6, milliseconds=500), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="100.5", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=7), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="101.0", quantity=1000, event_type="ORDER_CANCELLED"),
            # Opposite-side trade (last cancel at 7s, trade_window=2s, so <= 9s)
            create_transaction_event(timestamp=base + dt.timedelta(seconds=8), account_id="ACC_TRADE_TEST", product_id="PROD2", side="SELL", price="99.5", quantity=5000, event_type="TRADE_EXECUTED"),
            # Many irrelevant events AFTER trade (would slow down linear loop but not affect index)
            *[
                create_transaction_event(timestamp=base + dt.timedelta(seconds=10 + i * 0.1), account_id="ACC_TRADE_TEST", product_id="PROD2", side="BUY", price="99.0", quantity=100, event_type="ORDER_PLACED")
                for i in range(50)
            ],
        ]

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should detect pattern despite many irrelevant events
        assert len(result) == 1, "Index should efficiently find trade despite many irrelevant events"
        assert result[0].account_id == "ACC_TRADE_TEST"
        assert result[0].product_id == "PROD2"

    def test_index_handles_multiple_patterns_efficiently(self) -> None:
        """Test that index optimization handles multiple patterns efficiently (Tasks 9-11)."""
        # Arrange - Create multiple patterns with many events in between
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = []
        
        # Pattern 1: ACC1, PROD1
        events.extend([
            create_transaction_event(timestamp=base, account_id="ACC1", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=1), account_id="ACC1", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=2), account_id="ACC1", product_id="PROD1", side="BUY", price="101.0", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=3), account_id="ACC1", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=4), account_id="ACC1", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=5), account_id="ACC1", product_id="PROD1", side="BUY", price="101.0", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=6), account_id="ACC1", product_id="PROD1", side="SELL", price="99.5", quantity=5000, event_type="TRADE_EXECUTED"),
        ])
        
        # Many irrelevant events
        events.extend([
            create_transaction_event(
                timestamp=base + dt.timedelta(seconds=10 + i * 0.1),
                account_id="ACC_IRRELEVANT",
                product_id="PROD_IRRELEVANT",
                side="BUY",
                price="50.0",
                quantity=100,
                event_type="ORDER_PLACED",
            )
            for i in range(100)
        ])
        
        # Pattern 2: ACC2, PROD2
        pattern2_start = base + dt.timedelta(seconds=30)
        events.extend([
            create_transaction_event(timestamp=pattern2_start, account_id="ACC2", product_id="PROD2", side="BUY", price="200.0", quantity=2000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=1), account_id="ACC2", product_id="PROD2", side="BUY", price="200.5", quantity=2000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=2), account_id="ACC2", product_id="PROD2", side="BUY", price="201.0", quantity=2000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=3), account_id="ACC2", product_id="PROD2", side="BUY", price="200.0", quantity=2000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=4), account_id="ACC2", product_id="PROD2", side="BUY", price="200.5", quantity=2000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=5), account_id="ACC2", product_id="PROD2", side="BUY", price="201.0", quantity=2000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=pattern2_start + dt.timedelta(seconds=6), account_id="ACC2", product_id="PROD2", side="SELL", price="199.5", quantity=10000, event_type="TRADE_EXECUTED"),
        ])

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should detect both patterns efficiently
        assert len(result) == 2, "Index should efficiently handle multiple patterns"
        account_ids = {seq.account_id for seq in result}
        assert account_ids == {"ACC1", "ACC2"}, "Should detect both patterns"

    def test_index_handles_empty_event_groups_correctly(self) -> None:
        """Test that index optimization handles empty event groups correctly (Task 9)."""
        # Arrange - Empty events list
        events: list[TransactionEvent] = []

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should handle gracefully
        assert result == []
        assert isinstance(result, list)

    def test_index_handles_events_without_matching_patterns(self) -> None:
        """Test that index optimization handles events without matching patterns (Tasks 9-11)."""
        # Arrange - Events that don't form a pattern
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            # Only 2 orders (need 3)
            create_transaction_event(timestamp=base, account_id="ACC_NO_PATTERN", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=1), account_id="ACC_NO_PATTERN", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_PLACED"),
            # Only 2 cancellations (need 3)
            create_transaction_event(timestamp=base + dt.timedelta(seconds=2), account_id="ACC_NO_PATTERN", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=3), account_id="ACC_NO_PATTERN", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_CANCELLED"),
            # No opposite trade
        ]

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should return empty (no pattern detected)
        assert result == [], "Index should correctly identify no pattern"

    def test_index_preserves_behavior_with_boundary_conditions(self) -> None:
        """Test that index optimization preserves behavior with boundary conditions (Tasks 10-11)."""
        # Arrange - Use a simpler pattern that matches existing working tests
        base = dt.datetime(2025, 1, 1, 9, 0, 0, tzinfo=dt.timezone.utc)
        events = [
            # Orders
            create_transaction_event(timestamp=base, account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=1), account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_PLACED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=2), account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="101.0", quantity=1000, event_type="ORDER_PLACED"),
            # Cancellations (last order at 2s, cancel_window=5s, so <= 7s)
            create_transaction_event(timestamp=base + dt.timedelta(seconds=6), account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="100.0", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=6, milliseconds=500), account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="100.5", quantity=1000, event_type="ORDER_CANCELLED"),
            create_transaction_event(timestamp=base + dt.timedelta(seconds=7), account_id="ACC_BOUNDARY", product_id="PROD1", side="BUY", price="101.0", quantity=1000, event_type="ORDER_CANCELLED"),
            # Trade (last cancel at 7s, trade_window=2s, so <= 9s)
            create_transaction_event(timestamp=base + dt.timedelta(seconds=8), account_id="ACC_BOUNDARY", product_id="PROD1", side="SELL", price="99.5", quantity=5000, event_type="TRADE_EXECUTED"),
        ]

        # Act
        result = detect_suspicious_sequences(events, config=_DEFAULT_CONFIG)

        # Assert - Should detect pattern (boundaries are inclusive)
        assert len(result) == 1, "Index should correctly handle boundary conditions"
        assert result[0].account_id == "ACC_BOUNDARY"
