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
    _detect_wash_trading_for_group,
    detect_wash_trading,
)


class TestAlternationPercentageCalculation:
    """Test suite for alternation percentage calculation."""

    def test_perfect_alternation_100_percent(self) -> None:
        """Test that perfect alternation (BUY, SELL, BUY, SELL) gives 100%."""
        # Arrange
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.5"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.5"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.0"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("99.0"),
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.0"),
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


class TestWashTradingDetectionForGroup:
    """Test suite for wash trading detection within a single group."""

    def test_detects_valid_wash_trading_pattern(self) -> None:
        """Test that valid wash trading pattern is detected."""
        # Arrange: 3 BUY, 3 SELL, 100% alternation, >10k volume, within 30 minutes
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.5"),
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
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
                side="SELL",
                price=Decimal("102.0"),
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
                side="BUY",
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
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.0"),
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
                side="BUY",
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
                side="SELL",
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
        config = WashTradingConfig()
        sequences = _detect_wash_trading_for_group("ACC001", "IBM", trades, config)

        # Assert: Only 1 switch (BUY->SELL), so alternation = 1/5 = 20% < 60%
        assert len(sequences) == 0

    def test_insufficient_volume_no_detection(self) -> None:
        """Test that insufficient volume (<10k) does not trigger detection."""
        # Arrange: 3 BUY, 3 SELL, 100% alternation, but only 9k volume
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        trades = [
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("102.0"),
                quantity=1500,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
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
                side="BUY",
                price=Decimal("100.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
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
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=1666,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
                quantity=1666,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("102.0"),
                quantity=1667,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
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
                timestamp=base_time + timedelta(minutes=30),  # Exactly 30 minutes - should be included
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("102.5"),
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
                timestamp=base_time + timedelta(minutes=10),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("101.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=31),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("101.5"),
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
        trades = [
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
                price=Decimal("100.3"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=15),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.4"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=20),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.2"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=25),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.1"),
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
        sequences = detect_wash_trading(events)

        # Assert: Only 1 TRADE_EXECUTED event, so no detection
        assert len(sequences) == 0

    def test_groups_by_account_and_product(self) -> None:
        """Test that events are grouped by (account_id, product_id)."""
        # Arrange: Valid pattern for ACC001/IBM, but not enough for ACC002/IBM
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        events = [
            # ACC001/IBM - valid pattern
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
            # ACC002/IBM - insufficient trades
            TransactionEvent(
                timestamp=base_time,
                account_id="ACC002",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=5),
                account_id="ACC002",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

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
        events = [
            # First window (0-30 minutes)
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
            # Second window (35-65 minutes) - distinct from first
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=35),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("103.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=40),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("103.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=45),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("104.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=50),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("104.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=55),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("105.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=60),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("105.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        sequences = detect_wash_trading(events)

        # Assert: Should detect multiple sequences (sliding windows)
        assert len(sequences) >= 2

