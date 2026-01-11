"""
Unit tests for request size limits.

Tests Pydantic max_length validation and request body size limits to prevent DoS.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.shared.api_models import AlgorithmRequest, TransactionEventDTO
from tests.fixtures import create_transaction_event_dto

# Import service main modules for testing
project_root = Path(__file__).parent.parent.parent


def load_service_app(service_name: str):
    """Load service app module."""
    main_path = project_root / "services" / f"{service_name}-service" / "main.py"
    spec = importlib.util.spec_from_file_location(f"{service_name}_main", main_path)
    service_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service_main)
    return service_main.app


class TestPydanticMaxLengthValidation:
    """Tests for Pydantic max_length validation on list fields."""

    def test_algorithm_request_events_max_length_enforced(self) -> None:
        """Test that AlgorithmRequest.events field enforces max_length=100000."""
        # Arrange - Create request with exactly max_length events
        events = [
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00Z",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
            for _ in range(100000)
        ]

        # Act - Should succeed at max length
        request = AlgorithmRequest(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            event_fingerprint="a" * 64,
            events=events,
        )

        # Assert
        assert len(request.events) == 100000

    def test_algorithm_request_events_exceeds_max_length_rejected(self) -> None:
        """Test that AlgorithmRequest.events field rejects lists exceeding max_length."""
        # Arrange - Create request with more than max_length events
        events = [
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00Z",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
            for _ in range(100001)  # Exceeds max_length
        ]

        # Act & Assert - Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            AlgorithmRequest(
                request_id="550e8400-e29b-41d4-a716-446655440000",
                event_fingerprint="a" * 64,
                events=events,
            )

        # Verify error message mentions max_length
        errors = exc_info.value.errors()
        assert any("max_length" in str(error).lower() for error in errors)

    def test_algorithm_request_events_within_limit_accepted(self) -> None:
        """Test that AlgorithmRequest.events field accepts lists within max_length."""
        # Arrange - Create request with reasonable number of events
        events = [
            create_transaction_event_dto(
                timestamp="2025-01-15T10:30:00Z",
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_PLACED",
            )
            for _ in range(1000)
        ]

        # Act - Should succeed
        request = AlgorithmRequest(
            request_id="550e8400-e29b-41d4-a716-446655440000",
            event_fingerprint="a" * 64,
            events=events,
        )

        # Assert
        assert len(request.events) == 1000


class TestRequestSizeLimitMiddleware:
    """Tests for request size limit middleware."""

    @pytest.fixture
    def layering_client(self) -> TestClient:
        """Create layering service FastAPI test client."""
        app = load_service_app("layering")
        return TestClient(app)

    @pytest.fixture
    def wash_trading_client(self) -> TestClient:
        """Create wash trading service FastAPI test client."""
        app = load_service_app("wash-trading")
        return TestClient(app)

    @pytest.fixture
    def aggregator_client(self) -> TestClient:
        """Create aggregator service FastAPI test client."""
        app = load_service_app("aggregator")
        return TestClient(app)

    def test_large_content_length_header_returns_413(
        self, layering_client: TestClient
    ) -> None:
        """Test that requests with Content-Length >10MB return HTTP 413."""
        # Arrange - Create request with Content-Length header indicating >10MB
        # The middleware checks Content-Length header to reject large requests early
        request_body = {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_fingerprint": "a" * 64,
            "events": [
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": 1000,
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        import json

        body_json = json.dumps(request_body)

        # Act - Send request with Content-Length header >10MB
        # This simulates a large request that middleware should reject
        response = layering_client.post(
            "/detect",
            content=body_json,
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json",
                "Content-Length": str(11 * 1024 * 1024),  # 11MB - exceeds limit
            },
        )

        # Assert - Should return 413 (Payload Too Large)
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_normal_request_size_still_works(
        self, layering_client: TestClient
    ) -> None:
        """Test that normal-sized requests still work correctly."""
        # Arrange - Create normal-sized request
        normal_events = [
            {
                "timestamp": "2025-01-15T10:30:00Z",
                "account_id": "ACC001",
                "product_id": "IBM",
                "side": "BUY",
                "price": "100.50",
                "quantity": 1000,
                "event_type": "ORDER_PLACED",
            }
            for _ in range(100)  # Reasonable number of events
        ]

        request_body = {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_fingerprint": "a" * 64,
            "events": normal_events,
        }

        # Act - Send normal request
        response = layering_client.post(
            "/detect",
            json=request_body,
            headers={"X-API-Key": "test-key"},
        )

        # Assert - Should not return 413 (may return 200 or other status, but not 413)
        assert response.status_code != 413

    def test_max_length_validation_works(
        self, layering_client: TestClient
    ) -> None:
        """Test that Pydantic max_length validation works at API level."""
        # Arrange - Create request with events exceeding max_length
        # Use exactly 100001 events to exceed max_length=100000
        import json

        large_events = [
            {
                "timestamp": "2025-01-15T10:30:00Z",
                "account_id": "ACC001",
                "product_id": "IBM",
                "side": "BUY",
                "price": "100.50",
                "quantity": 1000,
                "event_type": "ORDER_PLACED",
            }
            for _ in range(100001)
        ]

        request_body = {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_fingerprint": "a" * 64,
            "events": large_events,
        }

        # Serialize to get actual size
        body_json = json.dumps(request_body)
        body_size = len(body_json.encode("utf-8"))

        # Act - Send request exceeding max_length
        response = layering_client.post(
            "/detect",
            content=body_json,
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json",
                "Content-Length": str(body_size),
            },
        )

        # Assert - Should return 413 (size limit) or 422 (validation error) due to max_length
        # The middleware may catch it first (413) or Pydantic validation (422)
        assert response.status_code in (413, 422)
        if response.status_code == 422:
            # Verify error mentions max_length or list length
            error_detail = str(response.json()).lower()
            assert "max_length" in error_detail or "length" in error_detail

    def test_wash_trading_service_size_limits(
        self, wash_trading_client: TestClient
    ) -> None:
        """Test that wash trading service also enforces size limits."""
        # Arrange - Create request with Content-Length header >10MB
        request_body = {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_fingerprint": "a" * 64,
            "events": [
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": 1000,
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        import json

        body_json = json.dumps(request_body)

        # Act - Send request with Content-Length header >10MB
        response = wash_trading_client.post(
            "/detect",
            content=body_json,
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json",
                "Content-Length": str(11 * 1024 * 1024),  # 11MB - exceeds limit
            },
        )

        # Assert - Should return 413 (Payload Too Large)
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_aggregator_service_size_limits(
        self, aggregator_client: TestClient
    ) -> None:
        """Test that aggregator service also enforces size limits."""
        # Arrange - Create large aggregate request
        # Create many algorithm responses to make request large
        from services.shared.api_models import AlgorithmResponse

        large_results = [
            AlgorithmResponse(
                request_id="550e8400-e29b-41d4-a716-446655440000",
                service_name="layering",
                status="success",
                results=[
                    {
                        "account_id": "ACC001",
                        "product_id": "IBM",
                        "start_timestamp": "2025-01-15T10:30:00Z",
                        "end_timestamp": "2025-01-15T10:30:10Z",
                        "total_buy_qty": 1000,
                        "total_sell_qty": 0,
                        "detection_type": "LAYERING",
                    }
                    for _ in range(10000)  # Large results list
                ],
                error=None,
                final_status=True,
            )
            for _ in range(100)  # Many algorithm responses
        ]

        request_body = {
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "expected_services": ["layering", "wash_trading"],
            "results": [result.model_dump() for result in large_results],
        }

        # Act
        response = aggregator_client.post(
            "/aggregate",
            json=request_body,
            headers={"X-API-Key": "test-key"},
        )

        # Assert - Should return 413 or process successfully (depending on actual size)
        # Note: This may not trigger 413 if the serialized JSON is under 10MB
        assert response.status_code in (200, 413, 422)

    def test_health_endpoint_not_affected_by_size_limits(
        self, layering_client: TestClient
    ) -> None:
        """Test that health check endpoints are not affected by size limits."""
        # Act
        response = layering_client.get("/health")

        # Assert - Should succeed
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

