"""
Unit tests for domain model ↔ DTO conversion functions.

Tests bidirectional conversion, precision preservation, and round-trip integrity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from layering_detection.models import SuspiciousSequence, TransactionEvent
from services.shared.api_models import SuspiciousSequenceDTO, TransactionEventDTO
from services.shared.converters import (
    dto_to_suspicious_sequence,
    dto_to_transaction_event,
    suspicious_sequence_to_dto,
    transaction_event_to_dto,
)
from tests.fixtures import create_transaction_event, create_transaction_event_dto


class TestTransactionEventConversions:
    """Tests for TransactionEvent ↔ TransactionEventDTO conversions."""

    def test_transaction_event_to_dto(self) -> None:
        """Test converting TransactionEvent to DTO."""
        event = create_transaction_event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        assert isinstance(dto, TransactionEventDTO)
        assert dto.timestamp == "2025-01-15T10:30:00"
        assert dto.account_id == "ACC001"
        assert dto.product_id == "IBM"
        assert dto.side == "BUY"
        assert dto.price == "100.50"  # String representation
        assert dto.quantity == 1000
        assert dto.event_type == "ORDER_PLACED"

    def test_dto_to_transaction_event(self) -> None:
        """Test converting DTO to TransactionEvent."""
        dto = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        event = dto_to_transaction_event(dto)
        assert isinstance(event, TransactionEvent)
        assert event.timestamp == datetime(2025, 1, 15, 10, 30, 0)
        assert event.account_id == "ACC001"
        assert isinstance(event.price, Decimal)
        assert event.price == Decimal("100.50")
        assert event.quantity == 1000

    def test_datetime_timezone_aware(self) -> None:
        """Test conversion handles timezone-aware datetime."""
        tz_aware_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        event = create_transaction_event(
            timestamp=tz_aware_dt,
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        # ISO format includes timezone info
        assert "+00:00" in dto.timestamp or dto.timestamp.endswith("Z")

    def test_datetime_with_z_suffix(self) -> None:
        """Test conversion handles Z suffix in ISO datetime."""
        dto = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00Z",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        event = dto_to_transaction_event(dto)
        assert isinstance(event.timestamp, datetime)

    def test_decimal_precision_preserved(self) -> None:
        """Test Decimal precision is preserved through conversion."""
        # Use a Decimal with many decimal places
        precise_price = Decimal("123.45678901234567890")
        event = create_transaction_event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=precise_price,
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        assert dto.price == "123.45678901234567890"
        restored_event = dto_to_transaction_event(dto)
        assert restored_event.price == precise_price

    def test_round_trip_conversion(self) -> None:
        """Test round-trip conversion preserves all data."""
        original_event = create_transaction_event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(original_event)
        restored_event = dto_to_transaction_event(dto)
        assert restored_event == original_event

    def test_round_trip_all_event_types(self) -> None:
        """Test round-trip conversion for all event types."""
        event_types = ["ORDER_PLACED", "ORDER_CANCELLED", "TRADE_EXECUTED"]
        for event_type in event_types:
            event = create_transaction_event(
                timestamp=datetime(2025, 1, 15, 10, 30, 0),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.50"),
                quantity=1000,
                event_type=event_type,  # type: ignore[arg-type]
            )
            dto = transaction_event_to_dto(event)
            restored = dto_to_transaction_event(dto)
            assert restored == event

    def test_round_trip_all_sides(self) -> None:
        """Test round-trip conversion for both sides."""
        for side in ["BUY", "SELL"]:
            event = create_transaction_event(
                timestamp=datetime(2025, 1, 15, 10, 30, 0),
                account_id="ACC001",
                product_id="IBM",
                side=side,  # type: ignore[arg-type]
                price=Decimal("100.50"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
            dto = transaction_event_to_dto(event)
            restored = dto_to_transaction_event(dto)
            assert restored == event


class TestSuspiciousSequenceConversions:
    """Tests for SuspiciousSequence ↔ SuspiciousSequenceDTO conversions."""

    def test_layering_sequence_to_dto(self) -> None:
        """Test converting LAYERING SuspiciousSequence to DTO."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[
                datetime(2025, 1, 15, 10, 30, 0),
                datetime(2025, 1, 15, 10, 30, 5),
            ],
        )
        dto = suspicious_sequence_to_dto(seq)
        assert isinstance(dto, SuspiciousSequenceDTO)
        assert dto.account_id == "ACC001"
        assert dto.detection_type == "LAYERING"
        assert dto.side == "BUY"
        assert dto.num_cancelled_orders == 3
        assert dto.order_timestamps == [
            "2025-01-15T10:30:00",
            "2025-01-15T10:30:05",
        ]
        assert dto.alternation_percentage is None

    def test_wash_trading_sequence_to_dto(self) -> None:
        """Test converting WASH_TRADING SuspiciousSequence to DTO."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            alternation_percentage=75.5,
            price_change_percentage=2.5,
        )
        dto = suspicious_sequence_to_dto(seq)
        assert isinstance(dto, SuspiciousSequenceDTO)
        assert dto.detection_type == "WASH_TRADING"
        assert dto.side is None
        assert dto.num_cancelled_orders is None
        assert dto.order_timestamps is None
        assert dto.alternation_percentage == 75.5
        assert dto.price_change_percentage == 2.5

    def test_dto_to_layering_sequence(self) -> None:
        """Test converting DTO to LAYERING SuspiciousSequence."""
        dto = SuspiciousSequenceDTO(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp="2025-01-15T10:30:00",
            end_timestamp="2025-01-15T10:30:10",
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=["2025-01-15T10:30:00", "2025-01-15T10:30:05"],
        )
        seq = dto_to_suspicious_sequence(dto)
        assert isinstance(seq, SuspiciousSequence)
        assert seq.detection_type == "LAYERING"
        assert seq.side == "BUY"
        assert seq.num_cancelled_orders == 3
        assert seq.order_timestamps == [
            datetime(2025, 1, 15, 10, 30, 0),
            datetime(2025, 1, 15, 10, 30, 5),
        ]
        assert isinstance(seq.start_timestamp, datetime)

    def test_dto_to_wash_trading_sequence(self) -> None:
        """Test converting DTO to WASH_TRADING SuspiciousSequence."""
        dto = SuspiciousSequenceDTO(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp="2025-01-15T10:30:00",
            end_timestamp="2025-01-15T11:00:00",
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            alternation_percentage=75.5,
            price_change_percentage=2.5,
        )
        seq = dto_to_suspicious_sequence(dto)
        assert isinstance(seq, SuspiciousSequence)
        assert seq.detection_type == "WASH_TRADING"
        assert seq.side is None
        assert seq.num_cancelled_orders is None
        assert seq.order_timestamps is None
        assert seq.alternation_percentage == 75.5
        assert seq.price_change_percentage == 2.5

    def test_order_timestamps_none(self) -> None:
        """Test conversion handles None order_timestamps."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="WASH_TRADING",
            order_timestamps=None,
        )
        dto = suspicious_sequence_to_dto(seq)
        assert dto.order_timestamps is None
        restored = dto_to_suspicious_sequence(dto)
        assert restored.order_timestamps is None

    def test_order_timestamps_empty_list(self) -> None:
        """Test conversion handles empty order_timestamps list."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=0,
            order_timestamps=[],
        )
        dto = suspicious_sequence_to_dto(seq)
        assert dto.order_timestamps == []
        restored = dto_to_suspicious_sequence(dto)
        assert restored.order_timestamps == []

    def test_timezone_aware_datetime(self) -> None:
        """Test conversion handles timezone-aware datetime."""
        tz_aware_start = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        tz_aware_end = datetime(2025, 1, 15, 10, 30, 10, tzinfo=timezone.utc)
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=tz_aware_start,
            end_timestamp=tz_aware_end,
            total_buy_qty=5000,
            total_sell_qty=0,
        )
        dto = suspicious_sequence_to_dto(seq)
        # ISO format includes timezone info
        assert "+00:00" in dto.start_timestamp or dto.start_timestamp.endswith("Z")

    def test_datetime_with_z_suffix(self) -> None:
        """Test conversion handles Z suffix in ISO datetime."""
        dto = SuspiciousSequenceDTO(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp="2025-01-15T10:30:00Z",
            end_timestamp="2025-01-15T10:30:10Z",
            total_buy_qty=5000,
            total_sell_qty=0,
        )
        seq = dto_to_suspicious_sequence(dto)
        assert isinstance(seq.start_timestamp, datetime)
        assert isinstance(seq.end_timestamp, datetime)

    def test_round_trip_layering_sequence(self) -> None:
        """Test round-trip conversion for LAYERING sequence."""
        original_seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=[
                datetime(2025, 1, 15, 10, 30, 0),
                datetime(2025, 1, 15, 10, 30, 5),
            ],
        )
        dto = suspicious_sequence_to_dto(original_seq)
        restored_seq = dto_to_suspicious_sequence(dto)
        assert restored_seq == original_seq

    def test_round_trip_wash_trading_sequence(self) -> None:
        """Test round-trip conversion for WASH_TRADING sequence."""
        original_seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            alternation_percentage=75.5,
            price_change_percentage=2.5,
        )
        dto = suspicious_sequence_to_dto(original_seq)
        restored_seq = dto_to_suspicious_sequence(dto)
        assert restored_seq == original_seq

    def test_round_trip_minimal_sequence(self) -> None:
        """Test round-trip conversion with minimal fields (defaults)."""
        original_seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            # Uses defaults: detection_type="LAYERING", side=None, etc.
        )
        dto = suspicious_sequence_to_dto(original_seq)
        restored_seq = dto_to_suspicious_sequence(dto)
        assert restored_seq == original_seq

    def test_optional_fields_preserved(self) -> None:
        """Test optional fields are preserved through conversion."""
        # Test with all optional fields set
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=5,
            order_timestamps=[datetime(2025, 1, 15, 10, 30, 0)],
            alternation_percentage=None,
            price_change_percentage=None,
        )
        dto = suspicious_sequence_to_dto(seq)
        restored = dto_to_suspicious_sequence(dto)
        assert restored.side == seq.side
        assert restored.num_cancelled_orders == seq.num_cancelled_orders
        assert restored.order_timestamps == seq.order_timestamps

    def test_wash_trading_with_price_change(self) -> None:
        """Test WASH_TRADING sequence with price_change_percentage."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            alternation_percentage=80.0,
            price_change_percentage=3.5,
        )
        dto = suspicious_sequence_to_dto(seq)
        restored = dto_to_suspicious_sequence(dto)
        assert restored.price_change_percentage == 3.5

    def test_wash_trading_without_price_change(self) -> None:
        """Test WASH_TRADING sequence without price_change_percentage."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
            total_buy_qty=5000,
            total_sell_qty=5000,
            detection_type="WASH_TRADING",
            alternation_percentage=80.0,
            price_change_percentage=None,
        )
        dto = suspicious_sequence_to_dto(seq)
        restored = dto_to_suspicious_sequence(dto)
        assert restored.price_change_percentage is None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_datetime_microseconds_preserved(self) -> None:
        """Test datetime microseconds are preserved."""
        dt_with_microseconds = datetime(2025, 1, 15, 10, 30, 0, 123456)
        event = create_transaction_event(
            timestamp=dt_with_microseconds,
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        restored = dto_to_transaction_event(dto)
        assert restored.timestamp == dt_with_microseconds

    def test_decimal_scientific_notation(self) -> None:
        """Test Decimal handles scientific notation strings."""
        dto = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="1.5e2",  # Scientific notation
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        event = dto_to_transaction_event(dto)
        assert event.price == Decimal("150")

    def test_datetime_with_timezone_offset(self) -> None:
        """Test datetime with timezone offset."""
        dto = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00+05:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        event = dto_to_transaction_event(dto)
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_decimal_zero_value(self) -> None:
        """Test Decimal zero value is preserved."""
        event = create_transaction_event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("0"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        assert dto.price == "0"
        restored = dto_to_transaction_event(dto)
        assert restored.price == Decimal("0")

    def test_decimal_very_large_value(self) -> None:
        """Test Decimal with very large value preserves precision."""
        large_price = Decimal("999999999999999.999999999999999")
        event = create_transaction_event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=large_price,
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        restored = dto_to_transaction_event(dto)
        assert restored.price == large_price

    def test_datetime_min_value(self) -> None:
        """Test datetime with minimum valid value."""
        min_dt = datetime(1970, 1, 1, 0, 0, 0)
        event = create_transaction_event(
            timestamp=min_dt,
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        restored = dto_to_transaction_event(dto)
        assert restored.timestamp == min_dt

    def test_datetime_max_value(self) -> None:
        """Test datetime with maximum valid value."""
        max_dt = datetime(9999, 12, 31, 23, 59, 59)
        event = create_transaction_event(
            timestamp=max_dt,
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        dto = transaction_event_to_dto(event)
        restored = dto_to_transaction_event(dto)
        assert restored.timestamp == max_dt

    def test_empty_string_fields(self) -> None:
        """Test conversion handles empty string fields (should fail validation)."""
        # Empty account_id should fail validation
        with pytest.raises(Exception):  # ValidationError from Pydantic
            dto = create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="",  # Empty string
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
            dto_to_transaction_event(dto)

    def test_sequence_with_all_none_optional_fields(self) -> None:
        """Test SuspiciousSequence with all optional fields as None."""
        seq = SuspiciousSequence(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
            end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side=None,
            num_cancelled_orders=None,
            order_timestamps=None,
            alternation_percentage=None,
            price_change_percentage=None,
        )
        dto = suspicious_sequence_to_dto(seq)
        restored = dto_to_suspicious_sequence(dto)
        assert restored.side is None
        assert restored.num_cancelled_orders is None
        assert restored.order_timestamps is None
        assert restored.alternation_percentage is None
        assert restored.price_change_percentage is None

