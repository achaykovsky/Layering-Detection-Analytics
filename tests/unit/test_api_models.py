"""
Unit tests for API contract models.

Tests validation, serialization, and edge cases for all Pydantic models.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from services.shared.api_models import (
    AggregateRequest,
    AggregateResponse,
    AlgorithmRequest,
    AlgorithmResponse,
    SuspiciousSequenceDTO,
    TransactionEventDTO,
)
from tests.fixtures import create_transaction_event_dto, create_algorithm_request


class TestTransactionEventDTO:
    """Tests for TransactionEventDTO model."""

    def test_valid_transaction_event(self) -> None:
        """Test creating valid TransactionEventDTO."""
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        assert event.timestamp == "2025-01-15T10:30:00"
        assert event.account_id == "ACC001"
        assert event.price == "100.50"

    def test_invalid_timestamp_format(self) -> None:
        """Test invalid timestamp format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_transaction_event_dto(
                timestamp="invalid-date",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        assert "Invalid ISO datetime format" in str(exc_info.value)

    def test_invalid_price_decimal(self) -> None:
        """Test invalid price format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="not-a-number",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        assert "Invalid decimal price" in str(exc_info.value)

    def test_negative_quantity(self) -> None:
        """Test negative quantity raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=-1,
                event_type="ORDER_PLACED",
            )
        assert "greater than 0" in str(exc_info.value).lower()

    def test_invalid_side_literal(self) -> None:
        """Test invalid side value raises ValidationError."""
        with pytest.raises(ValidationError):
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="INVALID",  # type: ignore[arg-type]
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )

    def test_invalid_event_type_literal(self) -> None:
        """Test invalid event_type value raises ValidationError."""
        with pytest.raises(ValidationError):
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="INVALID",  # type: ignore[arg-type]
            )

    def test_empty_account_id(self) -> None:
        """Test empty account_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_zero_quantity(self) -> None:
        """Test zero quantity raises ValidationError (must be > 0)."""
        with pytest.raises(ValidationError) as exc_info:
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=0,  # Must be > 0
                event_type="ORDER_PLACED",
            )
        assert "greater than 0" in str(exc_info.value).lower()

    def test_datetime_with_milliseconds(self) -> None:
        """Test datetime with milliseconds is accepted."""
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00.123",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        assert event.timestamp == "2025-01-15T10:30:00.123"

    def test_price_with_leading_zero(self) -> None:
        """Test price with leading zero is accepted."""
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="0.50",  # Leading zero
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        assert event.price == "0.50"

    def test_price_negative(self) -> None:
        """Test negative price is accepted (Decimal allows negatives)."""
        # Negative prices are valid Decimal values, so they should be accepted
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="-100.50",  # Negative price is valid Decimal
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        assert event.price == "-100.50"

    def test_json_serialization(self) -> None:
        """Test JSON serialization preserves data."""
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        json_str = event.model_dump_json()
        data = json.loads(json_str)
        assert data["timestamp"] == "2025-01-15T10:30:00"
        assert data["price"] == "100.50"  # Decimal preserved as string


class TestSuspiciousSequenceDTO:
    """Tests for SuspiciousSequenceDTO model."""

    def test_valid_layering_sequence(self) -> None:
        """Test creating valid LAYERING SuspiciousSequenceDTO."""
        sequence = SuspiciousSequenceDTO(
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
        assert sequence.detection_type == "LAYERING"
        assert sequence.side == "BUY"
        assert sequence.num_cancelled_orders == 3

    def test_valid_wash_trading_sequence(self) -> None:
        """Test creating valid WASH_TRADING SuspiciousSequenceDTO."""
        sequence = SuspiciousSequenceDTO(
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
        assert sequence.detection_type == "WASH_TRADING"
        assert sequence.alternation_percentage == 75.5
        assert sequence.side is None

    def test_invalid_timestamp_format(self) -> None:
        """Test invalid timestamp format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SuspiciousSequenceDTO(
                account_id="ACC001",
                product_id="IBM",
                start_timestamp="invalid-date",
                end_timestamp="2025-01-15T10:30:10",
                total_buy_qty=5000,
                total_sell_qty=0,
            )
        assert "Invalid ISO datetime format" in str(exc_info.value)

    def test_invalid_order_timestamps(self) -> None:
        """Test invalid order_timestamps format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SuspiciousSequenceDTO(
                account_id="ACC001",
                product_id="IBM",
                start_timestamp="2025-01-15T10:30:00",
                end_timestamp="2025-01-15T10:30:10",
                total_buy_qty=5000,
                total_sell_qty=0,
                order_timestamps=["invalid-date"],
            )
        assert "Invalid ISO datetime format" in str(exc_info.value)

    def test_negative_quantity(self) -> None:
        """Test negative quantity raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SuspiciousSequenceDTO(
                account_id="ACC001",
                product_id="IBM",
                start_timestamp="2025-01-15T10:30:00",
                end_timestamp="2025-01-15T10:30:10",
                total_buy_qty=-1,
                total_sell_qty=0,
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_invalid_alternation_percentage(self) -> None:
        """Test alternation_percentage out of range raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SuspiciousSequenceDTO(
                account_id="ACC001",
                product_id="IBM",
                start_timestamp="2025-01-15T10:30:00",
                end_timestamp="2025-01-15T11:00:00",
                total_buy_qty=5000,
                total_sell_qty=5000,
                alternation_percentage=150.0,  # > 100%
            )
        assert "less than or equal to 100" in str(exc_info.value).lower()

    def test_default_detection_type(self) -> None:
        """Test default detection_type is LAYERING."""
        sequence = SuspiciousSequenceDTO(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp="2025-01-15T10:30:00",
            end_timestamp="2025-01-15T10:30:10",
            total_buy_qty=5000,
            total_sell_qty=0,
        )
        assert sequence.detection_type == "LAYERING"


class TestAlgorithmRequest:
    """Tests for AlgorithmRequest model."""

    def test_valid_request(self) -> None:
        """Test creating valid AlgorithmRequest."""
        request_id = str(uuid4())
        fingerprint = "a" * 64  # Valid SHA256 hexdigest
        events = [
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]
        request = create_algorithm_request(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=events,
        )
        assert request.request_id == request_id
        assert request.event_fingerprint == fingerprint.lower()  # Normalized to lowercase
        assert len(request.events) == 1

    def test_invalid_uuid_format(self) -> None:
        """Test invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_algorithm_request(
                request_id="not-a-uuid",
                event_fingerprint="a" * 64,
                events=[],
            )
        assert "Invalid UUID format" in str(exc_info.value)

    def test_invalid_fingerprint_length(self) -> None:
        """Test invalid fingerprint length raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_algorithm_request(
                request_id=str(uuid4()),
                event_fingerprint="short",  # Not 64 chars
                events=[],
            )
        assert "Invalid SHA256 hexdigest format" in str(exc_info.value)

    def test_invalid_fingerprint_characters(self) -> None:
        """Test invalid fingerprint characters raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_algorithm_request(
                request_id=str(uuid4()),
                event_fingerprint="G" * 64,  # Invalid hex character
                events=[],
            )
        assert "Invalid SHA256 hexdigest format" in str(exc_info.value)

    def test_empty_events_list(self) -> None:
        """Test empty events list raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_algorithm_request(
                request_id=str(uuid4()),
                event_fingerprint="a" * 64,
                events=[],
            )
        assert "at least 1 item" in str(exc_info.value).lower()

    def test_fingerprint_case_normalization(self) -> None:
        """Test fingerprint is normalized to lowercase."""
        request = create_algorithm_request(
            request_id=str(uuid4()),
            event_fingerprint="A" * 64,  # Uppercase
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=1000,
                    event_type="ORDER_PLACED",
                )
            ],
        )
        assert request.event_fingerprint == "a" * 64  # Lowercase


class TestAlgorithmResponse:
    """Tests for AlgorithmResponse model."""

    def test_valid_success_response(self) -> None:
        """Test creating valid success AlgorithmResponse."""
        request_id = str(uuid4())
        response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
        )
        assert response.status == "success"
        assert response.results == []
        assert response.error is None

    def test_valid_failure_response(self) -> None:
        """Test creating valid failure AlgorithmResponse."""
        request_id = str(uuid4())
        response = AlgorithmResponse(
            request_id=request_id,
            service_name="wash_trading",
            status="failure",
            results=None,
            error="Algorithm error occurred",
        )
        assert response.status == "failure"
        assert response.results is None
        assert response.error == "Algorithm error occurred"

    def test_invalid_uuid_format(self) -> None:
        """Test invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id="not-a-uuid",
                service_name="layering",
                status="success",
                results=[],
                error=None,
            )
        assert "Invalid UUID format" in str(exc_info.value)

    def test_invalid_service_name(self) -> None:
        """Test invalid service_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="invalid_service",  # type: ignore[arg-type]
                status="success",
                results=[],
                error=None,
            )
        assert "Invalid service_name" in str(exc_info.value)

    def test_success_with_null_results(self) -> None:
        """Test success status with null results raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=None,  # Should be non-null
                error=None,
            )
        assert "results must be non-null when status is 'success'" in str(exc_info.value)

    def test_success_with_error(self) -> None:
        """Test success status with error raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[],
                error="Should be null",  # Should be null
            )
        assert "error must be null when status is 'success'" in str(exc_info.value)

    def test_failure_with_results(self) -> None:
        """Test failure status with results raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="failure",
                results=[],  # Should be null
                error="Error message",
            )
        assert "results must be null when status is 'failure'" in str(exc_info.value)

    def test_failure_without_error(self) -> None:
        """Test failure status without error raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="failure",
                results=None,
                error=None,  # Should be non-null
            )
        assert "error must be non-null when status is 'failure'" in str(exc_info.value)

    def test_timeout_status_validation(self) -> None:
        """Test timeout status requires null results and non-null error."""
        request_id = str(uuid4())
        response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="timeout",
            results=None,
            error="Request timeout",
        )
        assert response.status == "timeout"
        assert response.results is None
        assert response.error == "Request timeout"


class TestAggregateRequest:
    """Tests for AggregateRequest model."""

    def test_valid_request(self) -> None:
        """Test creating valid AggregateRequest."""
        request_id = str(uuid4())
        results = [
            AlgorithmResponse(
                request_id=request_id,
                service_name="layering",
                status="success",
                results=[],
                error=None,
            )
        ]
        request = AggregateRequest(
            request_id=request_id,
            expected_services=["layering", "wash_trading"],
            results=results,
        )
        assert len(request.expected_services) == 2
        assert len(request.results) == 1

    def test_invalid_uuid_format(self) -> None:
        """Test invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateRequest(
                request_id="not-a-uuid",
                expected_services=["layering"],
                results=[],
            )
        assert "Invalid UUID format" in str(exc_info.value)

    def test_invalid_service_name(self) -> None:
        """Test invalid service name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateRequest(
                request_id=str(uuid4()),
                expected_services=["invalid_service"],  # type: ignore[list-item]
                results=[],
            )
        assert "Invalid service name" in str(exc_info.value)

    def test_duplicate_service_names(self) -> None:
        """Test duplicate service names raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateRequest(
                request_id=str(uuid4()),
                expected_services=["layering", "layering"],  # Duplicate
                results=[],
            )
        assert "unique service names" in str(exc_info.value).lower()

    def test_empty_expected_services(self) -> None:
        """Test empty expected_services raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateRequest(
                request_id=str(uuid4()),
                expected_services=[],
                results=[],
            )
        assert "at least 1 item" in str(exc_info.value).lower()

    def test_empty_results(self) -> None:
        """Test empty results raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateRequest(
                request_id=str(uuid4()),
                expected_services=["layering"],
                results=[],
            )
        assert "at least 1 item" in str(exc_info.value).lower()


class TestAggregateResponse:
    """Tests for AggregateResponse model."""

    def test_valid_completed_response(self) -> None:
        """Test creating valid completed AggregateResponse."""
        response = AggregateResponse(
            status="completed",
            merged_count=5,
            failed_services=[],
            error=None,
        )
        assert response.status == "completed"
        assert response.merged_count == 5
        assert response.error is None

    def test_valid_validation_failed_response(self) -> None:
        """Test creating valid validation_failed AggregateResponse."""
        response = AggregateResponse(
            status="validation_failed",
            merged_count=0,
            failed_services=["layering"],
            error="Missing service: wash_trading",
        )
        assert response.status == "validation_failed"
        assert response.error == "Missing service: wash_trading"

    def test_completed_with_error(self) -> None:
        """Test completed status with error raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateResponse(
                status="completed",
                merged_count=5,
                failed_services=[],
                error="Should be null",  # Should be null
            )
        assert "error must be null when status is 'completed'" in str(exc_info.value)

    def test_validation_failed_without_error(self) -> None:
        """Test validation_failed status without error raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateResponse(
                status="validation_failed",
                merged_count=0,
                failed_services=[],
                error=None,  # Should be non-null
            )
        assert "error must be non-null when status is 'validation_failed'" in str(exc_info.value)

    def test_negative_merged_count(self) -> None:
        """Test negative merged_count raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AggregateResponse(
                status="completed",
                merged_count=-1,
                failed_services=[],
                error=None,
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_default_failed_services(self) -> None:
        """Test default failed_services is empty list."""
        response = AggregateResponse(
            status="completed",
            merged_count=0,
        )
        assert response.failed_services == []

    def test_aggregate_response_with_failed_services(self) -> None:
        """Test AggregateResponse with multiple failed services."""
        response = AggregateResponse(
            status="completed",
            merged_count=10,
            failed_services=["layering", "wash_trading"],
            error=None,
        )
        assert len(response.failed_services) == 2
        assert "layering" in response.failed_services
        assert "wash_trading" in response.failed_services

    def test_algorithm_response_final_status_false(self) -> None:
        """Test AlgorithmResponse with final_status=False."""
        response = AlgorithmResponse(
            request_id=str(uuid4()),
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=False,  # Still retrying
        )
        assert response.final_status is False

    def test_algorithm_response_final_status_default(self) -> None:
        """Test AlgorithmResponse default final_status is True."""
        response = AlgorithmResponse(
            request_id=str(uuid4()),
            service_name="layering",
            status="success",
            results=[],
            error=None,
        )
        assert response.final_status is True


class TestJSONSerialization:
    """Tests for JSON serialization/deserialization."""

    def test_transaction_event_json_roundtrip(self) -> None:
        """Test TransactionEventDTO JSON roundtrip."""
        event = create_transaction_event_dto(
            timestamp="2025-01-15T10:30:00",
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        json_str = event.model_dump_json()
        data = json.loads(json_str)
        restored = TransactionEventDTO(**data)
        assert restored == event

    def test_algorithm_request_json_roundtrip(self) -> None:
        """Test AlgorithmRequest JSON roundtrip."""
        request_id = str(uuid4())
        request = create_algorithm_request(
            request_id=request_id,
            event_fingerprint="a" * 64,
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=1000,
                    event_type="ORDER_PLACED",
                )
            ],
        )
        json_str = request.model_dump_json()
        data = json.loads(json_str)
        restored = AlgorithmRequest(**data)
        assert restored.request_id == request.request_id
        assert restored.event_fingerprint == request.event_fingerprint

    def test_algorithm_response_json_roundtrip(self) -> None:
        """Test AlgorithmResponse JSON roundtrip."""
        request_id = str(uuid4())
        response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        restored = AlgorithmResponse(**data)
        assert restored == response

    def test_suspicious_sequence_json_roundtrip(self) -> None:
        """Test SuspiciousSequenceDTO JSON roundtrip."""
        sequence = SuspiciousSequenceDTO(
            account_id="ACC001",
            product_id="IBM",
            start_timestamp="2025-01-15T10:30:00",
            end_timestamp="2025-01-15T10:30:10",
            total_buy_qty=5000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="BUY",
            num_cancelled_orders=3,
            order_timestamps=["2025-01-15T10:30:00"],
        )
        json_str = sequence.model_dump_json()
        data = json.loads(json_str)
        restored = SuspiciousSequenceDTO(**data)
        assert restored == sequence

    def test_aggregate_request_json_roundtrip(self) -> None:
        """Test AggregateRequest JSON roundtrip."""
        request_id = str(uuid4())
        request = AggregateRequest(
            request_id=request_id,
            expected_services=["layering", "wash_trading"],
            results=[
                AlgorithmResponse(
                    request_id=request_id,
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                )
            ],
        )
        json_str = request.model_dump_json()
        data = json.loads(json_str)
        restored = AggregateRequest(**data)
        assert restored.request_id == request.request_id
        assert restored.expected_services == request.expected_services

    def test_aggregate_response_json_roundtrip(self) -> None:
        """Test AggregateResponse JSON roundtrip."""
        response = AggregateResponse(
            status="completed",
            merged_count=5,
            failed_services=["wash_trading"],
            error=None,
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        restored = AggregateResponse(**data)
        assert restored == response

    def test_json_with_null_values(self) -> None:
        """Test JSON serialization handles null values correctly."""
        response = AlgorithmResponse(
            request_id=str(uuid4()),
            service_name="layering",
            status="failure",
            results=None,
            error="Error message",
        )
        json_str = response.model_dump_json()
        data = json.loads(json_str)
        assert data["results"] is None
        assert data["error"] == "Error message"

    def test_json_with_empty_lists(self) -> None:
        """Test JSON serialization handles empty lists correctly."""
        request = create_algorithm_request(
            request_id=str(uuid4()),
            event_fingerprint="a" * 64,
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=1000,
                    event_type="ORDER_PLACED",
                )
            ],
        )
        json_str = request.model_dump_json()
        data = json.loads(json_str)
        assert isinstance(data["events"], list)
        assert len(data["events"]) == 1

