"""
Unit tests for wash trading detection (Task 22).

Tests core wash trading detection logic including filtering, grouping,
sliding windows, alternation calculation, and detection conditions.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from layering_detection.models import TransactionEvent, WashTradingConfig
from layering_detection.detectors.wash_trading_detector import (
    _calculate_alternation_percentage,
    _calculate_price_change_percentage,
    _collect_window_trades,
    _detect_wash_trading_for_group,
    _validate_wash_trading_window,
    detect_wash_trading,
)
from tests.fixtures import create_transaction_event, create_wash_trading_pattern


class TestAlternationPercentageCalculation:
    """Test suite for alternation percentage calculation."""

    def test_perfect_alternation_100_percent(self) -> None:
        """Test that perfect alternation (BUY, SELL, BUY, SELL) gives 100%."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert
        assert alternation == 100.0

    def test_no_alternation_0_percent(self) -> None:
        """Test that no alternation (all BUY) gives 0%."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert
        assert alternation == 0.0

    def test_partial_alternation_50_percent(self) -> None:
        """Test that partial alternation gives correct percentage."""
        # Arrange: BUY, BUY, SELL, SELL = 1 switch / 3 transitions = 33.33%
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert
        assert alternation == pytest.approx(33.333, abs=0.1)

    def test_single_trade_returns_zero(self) -> None:
        """Test that single trade returns 0% alternation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert
        assert alternation == 0.0

    def test_empty_list_returns_zero(self) -> None:
        """Test that empty list returns 0% alternation."""
        # Arrange
        trades: list[TransactionEvent] = []

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert
        assert alternation == 0.0

    def test_exactly_60_percent_alternation(self) -> None:
        """Test that exactly 60% alternation is calculated correctly."""
        # Arrange: 6 trades with 3 switches = 3/5 = 60%
        # Pattern: BUY, SELL, BUY, SELL, BUY, SELL = 5 switches (wrong)
        # Pattern: BUY, BUY, SELL, BUY, SELL, SELL = 3 switches / 5 transitions = 60%
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="BUY",
                price="101.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        alternation = _calculate_alternation_percentage(trades)

        # Assert: 3 switches / 5 transitions = 60%
        # Switches: BUY->BUY (0), BUY->SELL (1), SELL->BUY (2), BUY->SELL (3), SELL->SELL (0)
        # Total: 3 switches out of 5 transitions = 60%
        assert alternation == pytest.approx(60.0, abs=0.1)


class TestPriceChangePercentageCalculation:
    """Test suite for price change percentage calculation."""

    def test_price_increase_calculated_correctly(self) -> None:
        """Test that price increase is calculated correctly."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        price_change = _calculate_price_change_percentage(trades)

        # Assert
        assert price_change == pytest.approx(1.0, abs=0.01)

    def test_price_decrease_calculated_correctly(self) -> None:
        """Test that price decrease is calculated correctly (absolute value)."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="99.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        price_change = _calculate_price_change_percentage(trades)

        # Assert
        assert price_change == pytest.approx(1.0, abs=0.01)

    def test_no_price_change_returns_zero(self) -> None:
        """Test that no price change returns 0%."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        price_change = _calculate_price_change_percentage(trades)

        # Assert
        assert price_change == pytest.approx(0.0, abs=0.01)

    def test_empty_list_returns_none(self) -> None:
        """Test that empty list returns None."""
        # Arrange
        trades: list[TransactionEvent] = []

        # Act
        price_change = _calculate_price_change_percentage(trades)

        # Assert
        assert price_change is None


class TestCollectWindowTrades:
    """Test suite for sliding window trade collection helper."""

    def test_collects_trades_within_window(self) -> None:
        """Test that trades within the window are collected correctly."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=35),  # Outside 30-minute window
                side="SELL",
                price="101.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        window_size = timedelta(minutes=30)

        # Act
        window_trades = _collect_window_trades(trades, start_idx=0, window_size=window_size)

        # Assert
        assert len(window_trades) == 3
        assert window_trades[0].timestamp == base_time
        assert window_trades[1].timestamp == base_time + timedelta(minutes=5)
        assert window_trades[2].timestamp == base_time + timedelta(minutes=10)

    def test_window_boundary_inclusive(self) -> None:
        """Test that trades exactly at window boundary are included."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_size = timedelta(minutes=30)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + window_size,  # Exactly at boundary
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + window_size + timedelta(seconds=1),  # Just outside
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        window_trades = _collect_window_trades(trades, start_idx=0, window_size=window_size)

        # Assert
        assert len(window_trades) == 2
        assert window_trades[0].timestamp == base_time
        assert window_trades[1].timestamp == base_time + window_size

    def test_window_boundary_exclusive(self) -> None:
        """Test that trades just after window boundary are excluded."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_size = timedelta(minutes=30)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + window_size + timedelta(seconds=1),  # Just outside
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        window_trades = _collect_window_trades(trades, start_idx=0, window_size=window_size)

        # Assert
        assert len(window_trades) == 1
        assert window_trades[0].timestamp == base_time

    def test_empty_list_returns_empty(self) -> None:
        """Test that empty trade list returns empty window."""
        # Arrange
        trades: list[TransactionEvent] = []
        window_size = timedelta(minutes=30)

        # Act
        window_trades = _collect_window_trades(trades, start_idx=0, window_size=window_size)

        # Assert
        assert len(window_trades) == 0

    def test_start_idx_out_of_bounds_returns_empty(self) -> None:
        """Test that start_idx beyond list length returns empty."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        window_size = timedelta(minutes=30)

        # Act
        window_trades = _collect_window_trades(trades, start_idx=10, window_size=window_size)

        # Assert
        assert len(window_trades) == 0

    def test_middle_start_idx_collects_from_that_point(self) -> None:
        """Test that starting from middle index collects trades from that point."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        window_size = timedelta(minutes=30)

        # Act
        window_trades = _collect_window_trades(trades, start_idx=1, window_size=window_size)

        # Assert
        assert len(window_trades) == 2
        assert window_trades[0].timestamp == base_time + timedelta(minutes=5)
        assert window_trades[1].timestamp == base_time + timedelta(minutes=10)

    def test_all_trades_within_window(self) -> None:
        """Test that all trades are collected when all are within window."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        window_size = timedelta(minutes=30)

        # Act
        window_trades = _collect_window_trades(trades, start_idx=0, window_size=window_size)

        # Assert
        assert len(window_trades) == 3
        assert all(trade in window_trades for trade in trades)


class TestValidateWashTradingWindow:
    """Test suite for window validation helper."""

    def test_valid_window_passes_all_checks(self) -> None:
        """Test that a valid window passes all validation checks."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_trades = create_wash_trading_pattern(base_time=base_time, quantity=2500)  # 6 trades * 2500 = 15000 volume
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is True
        assert len(buy_trades) == 3
        assert len(sell_trades) == 3
        assert all(t.side == "BUY" for t in buy_trades)
        assert all(t.side == "SELL" for t in sell_trades)

    def test_insufficient_total_trades_fails(self) -> None:
        """Test that window with insufficient total trades fails validation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]  # Only 2 trades, need at least 6 (3+3)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        # Early exit returns empty lists when insufficient total trades
        assert len(buy_trades) == 0
        assert len(sell_trades) == 0

    def test_insufficient_buy_trades_fails(self) -> None:
        """Test that window with insufficient buy trades fails validation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="101.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]  # 2 buy trades, 4 sell trades (total 6, but only 2 buy trades, need 3)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        assert len(buy_trades) == 2
        assert len(sell_trades) == 4

    def test_insufficient_sell_trades_fails(self) -> None:
        """Test that window with insufficient sell trades fails validation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        window_trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="BUY",
                price="102.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]  # 4 buy trades, 2 sell trades (total 6, but only 2 sell trades, need 3)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        assert len(buy_trades) == 4
        assert len(sell_trades) == 2

    def test_insufficient_volume_fails(self) -> None:
        """Test that window with insufficient volume fails validation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        # Create pattern with low volume: 6 trades * 800 = 4800 (below minimum of 10000)
        window_trades = create_wash_trading_pattern(base_time=base_time, quantity=800)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        assert len(buy_trades) == 3
        assert len(sell_trades) == 3

    def test_insufficient_alternation_fails(self) -> None:
        """Test that window with insufficient alternation fails validation."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        # Create pattern with low alternation: BUY, BUY, BUY, SELL, SELL, SELL = 1 switch / 5 transitions = 20%
        window_trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=2500,
                event_type="TRADE_EXECUTED",
            ),
        ]  # 1 switch / 5 transitions = 20% alternation (below 60%)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        assert len(buy_trades) == 3
        assert len(sell_trades) == 3

    def test_empty_window_returns_false(self) -> None:
        """Test that empty window returns False."""
        # Arrange
        window_trades: list[TransactionEvent] = []
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is False
        assert len(buy_trades) == 0
        assert len(sell_trades) == 0

    def test_exactly_minimum_thresholds_passes(self) -> None:
        """Test that window meeting exactly minimum thresholds passes."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        # Create pattern with exactly minimum volume: 6 trades * 1667 ≈ 10002 (above 10000)
        # Perfect alternation (100%) is above 60% minimum
        window_trades = create_wash_trading_pattern(base_time=base_time, quantity=1667)
        config = WashTradingConfig()

        # Act
        is_valid, buy_trades, sell_trades = _validate_wash_trading_window(window_trades, config)

        # Assert
        assert is_valid is True
        assert len(buy_trades) == 3
        assert len(sell_trades) == 3


class TestWashTradingDetectionForGroup:
    """Test suite for wash trading detection within a single group."""

    def test_detects_valid_wash_trading_pattern(self) -> None:
        """Test that valid wash trading pattern is detected."""
        # Arrange: 3 BUY, 3 SELL, 100% alternation, >10k volume, within 30 minutes
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = create_wash_trading_pattern(
            base_time=base_time,
            quantity=2000,
            price_start="100.0",
        )

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert
        assert len(sequences) > 0
        seq = sequences[0]
        assert seq.account_id == "ACC001"
        assert seq.product_id == "IBM"
        assert seq.detection_type == "WASH_TRADING"
        assert seq.side is None
        assert seq.num_cancelled_orders is None
        assert seq.order_timestamps is None
        assert seq.alternation_percentage == pytest.approx(100.0, abs=0.1)
        assert seq.total_buy_qty == 6000
        assert seq.total_sell_qty == 6000

    def test_insufficient_buy_trades_no_detection(self) -> None:
        """Test that insufficient BUY trades (<3) does not trigger detection."""
        # Arrange: Only 2 BUY trades, 3 SELL trades
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert
        assert len(sequences) == 0

    def test_insufficient_sell_trades_no_detection(self) -> None:
        """Test that insufficient SELL trades (<3) does not trigger detection."""
        # Arrange: 3 BUY trades, only 2 SELL trades
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert
        assert len(sequences) == 0

    def test_insufficient_alternation_no_detection(self) -> None:
        """Test that insufficient alternation (<60%) does not trigger detection."""
        # Arrange: 3 BUY, 3 SELL, but low alternation (all BUY first, then all SELL)
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Only 1 switch (BUY->SELL), so alternation = 1/5 = 20% < 60%
        assert len(sequences) == 0

    def test_insufficient_volume_no_detection(self) -> None:
        """Test that insufficient volume (<10k) does not trigger detection."""
        # Arrange: 3 BUY, 3 SELL, 100% alternation, but only 9k volume
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="BUY",
                price="102.0",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Total volume = 9000 < 10000
        assert len(sequences) == 0

    def test_exactly_60_percent_alternation_triggers_detection(self) -> None:
        """Test that exactly 60% alternation triggers detection (edge case)."""
        # Arrange: 6 trades with 3 switches = 3/5 = 60%
        # Pattern: BUY, BUY, SELL, BUY, SELL, SELL = 3 switches / 5 transitions = 60%
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="BUY",
                price="101.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="SELL",
                price="102.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: 3 switches / 5 transitions = 60% (should trigger)
        assert len(sequences) > 0
        assert sequences[0].alternation_percentage == pytest.approx(60.0, abs=0.1)

    def test_exactly_10k_volume_triggers_detection(self) -> None:
        """Test that exactly 10k volume triggers detection (edge case)."""
        # Arrange: 3 BUY, 3 SELL, 100% alternation, exactly 10k volume
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=1666,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=1666,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="BUY",
                price="102.0",
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="102.5",
                quantity=1667,  # Adjusted to make total exactly 10000
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Total volume = exactly 10000
        assert len(sequences) > 0
        assert sequences[0].total_buy_qty + sequences[0].total_sell_qty == 10000

    def test_window_boundary_included(self) -> None:
        """Test that trades at exactly 30 minutes are included in window."""
        # Arrange: First trade at 0, trades within 30 minutes (including at exactly 30 minutes)
        # Need 3 BUY and 3 SELL within the window starting at base_time
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="101.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="BUY",
                price="102.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=30),  # Exactly 30 minutes - should be included
                side="SELL",
                price="102.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Window starting at base_time should include trade at exactly 30 minutes
        # 3 BUY, 3 SELL, 100% alternation, 12000 volume - should detect
        assert len(sequences) > 0

    def test_window_boundary_excluded(self) -> None:
        """Test that trades after 30 minutes are excluded from window."""
        # Arrange: First trade at 0, last trade at 31 minutes (outside window)
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="SELL",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="BUY",
                price="101.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=31),
                side="SELL",
                price="101.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Window starting at base_time should NOT include trade at 31 minutes
        # Only 3 trades in window (2 BUY, 1 SELL) - insufficient
        assert len(sequences) == 0

    def test_price_change_percentage_included_when_above_threshold(self) -> None:
        """Test that price_change_percentage is included when ≥1%."""
        # Arrange: Valid pattern with >1% price change
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = create_wash_trading_pattern(
            base_time=base_time,
            quantity=2000,
            price_start="100.0",
        )

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Price change = (102.5 - 100.0) / 100.0 * 100 = 2.5% > 1%
        assert len(sequences) > 0
        assert sequences[0].price_change_percentage is not None
        assert sequences[0].price_change_percentage >= 1.0

    def test_price_change_percentage_excluded_when_below_threshold(self) -> None:
        """Test that price_change_percentage is None when <1%."""
        # Arrange: Valid pattern with <1% price change
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="SELL",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=10),
                side="BUY",
                price="100.3",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=15),
                side="SELL",
                price="100.4",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=20),
                side="BUY",
                price="100.2",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=25),
                side="SELL",
                price="100.1",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Price change < 1%, so price_change_percentage should be None
        assert len(sequences) > 0
        # Price change = (100.1 - 100.0) / 100.0 * 100 = 0.1% < 1%
        assert sequences[0].price_change_percentage is None


class TestDetectWashTradingTopLevel:
    """Test suite for top-level detect_wash_trading function."""

    def test_requires_pre_filtered_trade_executed_events(self) -> None:
        """Test that detect_wash_trading() expects pre-filtered TRADE_EXECUTED events only."""
        # Arrange: Only TRADE_EXECUTED events (filtering is done by algorithm wrapper)
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        sequences = detect_wash_trading(events)

        # Assert: Only 1 TRADE_EXECUTED event, so no detection
        assert len(sequences) == 0

    def test_groups_by_account_and_product(self) -> None:
        """Test that events are grouped by (account_id, product_id)."""
        # Arrange: Valid pattern for ACC001/IBM, but not enough for ACC002/IBM
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        # ACC001/IBM - valid pattern
        events = create_wash_trading_pattern(
            base_time=base_time,
            account_id="ACC001",
            quantity=2000,
            price_start="100.0",
        )
        # ACC002/IBM - insufficient trades
        events.extend([
            create_transaction_event(
                timestamp=base_time,
                account_id="ACC002",
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC002",
                side="SELL",
                price="100.5",
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ])

        # Act
        sequences = detect_wash_trading(events)

        # Assert: Only ACC001/IBM should be detected
        assert len(sequences) > 0
        assert all(seq.account_id == "ACC001" and seq.product_id == "IBM" for seq in sequences)

    def test_handles_empty_event_list(self) -> None:
        """Test that empty event list returns empty result."""
        # Arrange
        events: list[TransactionEvent] = []

        # Act
        sequences = detect_wash_trading(events)

        # Assert
        assert sequences == []

    def test_handles_no_trade_executed_events(self) -> None:
        """Test that events with no TRADE_EXECUTED return empty result."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            create_transaction_event(
                timestamp=base_time,
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=5),
                side="BUY",
                price="100.0",
                quantity=2000,
                event_type="ORDER_CANCELLED",
            ),
        ]

        # Act
        sequences = detect_wash_trading(events)

        # Assert
        assert sequences == []

    def test_multiple_windows_for_same_group(self) -> None:
        """Test that multiple overlapping windows can produce multiple sequences."""
        # Arrange: Two distinct 30-minute windows with valid patterns
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        # First window (0-30 minutes)
        events = create_wash_trading_pattern(
            base_time=base_time,
            quantity=2000,
            price_start="100.0",
        )
        # Second window (35-65 minutes) - distinct from first
        events.extend(
            create_wash_trading_pattern(
                base_time=base_time + timedelta(minutes=35),
                quantity=2000,
                price_start="103.0",
            )
        )

        # Act
        sequences = detect_wash_trading(events)

        # Assert: Should detect multiple sequences (sliding windows)
        assert len(sequences) >= 2

