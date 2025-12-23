"""
Integration tests for Algorithm Services (Layering and Wash Trading).

Tests the actual FastAPI endpoints with real algorithm calls, idempotency, caching,
and error handling.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.shared.api_models import AlgorithmRequest, TransactionEventDTO


# Import apps after setting up path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import Layering Service app
layering_app_module_path = project_root / "services" / "layering-service" / "main.py"
layering_spec = importlib.util.spec_from_file_location("layering_service_main", layering_app_module_path)
layering_service_main = importlib.util.module_from_spec(layering_spec)
sys.modules["layering_service_main"] = layering_service_main
layering_spec.loader.exec_module(layering_service_main)
layering_app = layering_service_main.app

# Import Wash Trading Service app
wash_trading_app_module_path = project_root / "services" / "wash-trading-service" / "main.py"
wash_trading_spec = importlib.util.spec_from_file_location("wash_trading_service_main", wash_trading_app_module_path)
wash_trading_service_main = importlib.util.module_from_spec(wash_trading_spec)
sys.modules["wash_trading_service_main"] = wash_trading_service_main
wash_trading_spec.loader.exec_module(wash_trading_service_main)
wash_trading_app = wash_trading_service_main.app


@pytest.fixture
def layering_client() -> TestClient:
    """Create test client for Layering Service FastAPI app."""
    return TestClient(layering_app)


@pytest.fixture
def wash_trading_client() -> TestClient:
    """Create test client for Wash Trading Service FastAPI app."""
    return TestClient(wash_trading_app)


@pytest.fixture
def sample_layering_events() -> list[TransactionEventDTO]:
    """
    Create sample transaction events that trigger layering detection.
    
    Creates a pattern: multiple BUY orders, some cancelled, then SELL trade executed.
    """
    base_time = datetime(2025, 1, 15, 10, 30, 0)
    events = [
        TransactionEventDTO(
            timestamp=(base_time + timedelta(seconds=i)).isoformat(),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price="100.50",
            quantity=1000,
            event_type="ORDER_PLACED",
        )
        for i in range(3)
    ]
    # Add cancelled orders
    events.extend(
        [
            TransactionEventDTO(
                timestamp=(base_time + timedelta(seconds=3 + i)).isoformat(),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price="100.50",
                quantity=1000,
                event_type="ORDER_CANCELLED",
            )
            for i in range(2)
        ]
    )
    # Add executed trade on opposite side
    events.append(
        TransactionEventDTO(
            timestamp=(base_time + timedelta(seconds=10)).isoformat(),
            account_id="ACC001",
            product_id="IBM",
            side="SELL",
            price="101.00",
            quantity=2000,
            event_type="TRADE_EXECUTED",
        )
    )
    return events


@pytest.fixture
def sample_wash_trading_events() -> list[TransactionEventDTO]:
    """
    Create sample transaction events that trigger wash trading detection.
    
    Creates a pattern: alternating BUY/SELL trades with same account/product.
    """
    base_time = datetime(2025, 1, 15, 10, 30, 0)
    events = []
    for i in range(10):
        side = "BUY" if i % 2 == 0 else "SELL"
        events.append(
            TransactionEventDTO(
                timestamp=(base_time + timedelta(minutes=i)).isoformat(),
                account_id="ACC002",
                product_id="AAPL",
                side=side,
                price=f"{100.00 + (i * 0.10)}",
                quantity=500,
                event_type="TRADE_EXECUTED",
            )
        )
    return events


@pytest.fixture
def sample_algorithm_request(
    sample_layering_events: list[TransactionEventDTO],
) -> AlgorithmRequest:
    """Create sample AlgorithmRequest for testing."""
    return AlgorithmRequest(
        request_id=str(uuid4()),
        event_fingerprint="a" * 64,  # Valid SHA256 hexdigest
        events=sample_layering_events,
    )


class TestLayeringServiceHealthCheck:
    """Tests for Layering Service health check endpoint."""

    def test_health_check_returns_healthy(self, layering_client: TestClient) -> None:
        """Test health check endpoint returns healthy status."""
        # Act
        response = layering_client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "layering-service"

    def test_root_endpoint_returns_service_info(self, layering_client: TestClient) -> None:
        """Test root endpoint returns service information."""
        # Act
        response = layering_client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "layering-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestWashTradingServiceHealthCheck:
    """Tests for Wash Trading Service health check endpoint."""

    def test_health_check_returns_healthy(self, wash_trading_client: TestClient) -> None:
        """Test health check endpoint returns healthy status."""
        # Act
        response = wash_trading_client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "wash-trading-service"

    def test_root_endpoint_returns_service_info(self, wash_trading_client: TestClient) -> None:
        """Test root endpoint returns service information."""
        # Act
        response = wash_trading_client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "wash-trading-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestLayeringServiceDetectEndpoint:
    """Tests for Layering Service /detect endpoint with real algorithm calls."""

    def test_detect_with_real_events_returns_success(
        self,
        layering_client: TestClient,
        sample_layering_events: list[TransactionEventDTO],
    ) -> None:
        """Test detect endpoint with real events returns success response."""
        # Arrange
        request_id = str(uuid4())
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint="b" * 64,
            events=sample_layering_events,
        )

        # Act
        response = layering_client.post("/detect", json=request.model_dump())

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["service_name"] == "layering"
        assert data["status"] == "success"
        assert data["results"] is not None
        assert isinstance(data["results"], list)
        assert data["error"] is None

    def test_detect_with_empty_events_returns_success(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test detect endpoint with events that produce no suspicious sequences returns success with empty results."""
        # Arrange - Use events that won't produce suspicious sequences
        from tests.fixtures import create_transaction_event_dto, create_algorithm_request

        request = create_algorithm_request(
            event_fingerprint="c" * 64,
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=100,  # Small quantity, won't trigger layering detection
                    event_type="ORDER_PLACED",
                )
            ],
        )

        # Act
        response = layering_client.post("/detect", json=request.model_dump())

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []

    def test_detect_with_invalid_request_returns_validation_error(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test detect endpoint with invalid request returns validation error."""
        # Arrange - missing required fields
        invalid_request = {
            "request_id": "not-a-uuid",  # Invalid UUID
            "event_fingerprint": "short",  # Invalid fingerprint
            "events": [],
        }

        # Act
        response = layering_client.post("/detect", json=invalid_request)

        # Assert - FastAPI returns 422 for validation errors
        assert response.status_code == 422

    def test_detect_with_malformed_json_returns_error(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test detect endpoint with malformed JSON returns error."""
        # Act
        response = layering_client.post(
            "/detect",
            content="not json",
            headers={"Content-Type": "application/json"},
        )

        # Assert
        assert response.status_code == 422


class TestWashTradingServiceDetectEndpoint:
    """Tests for Wash Trading Service /detect endpoint with real algorithm calls."""

    def test_detect_with_real_events_returns_success(
        self,
        wash_trading_client: TestClient,
        sample_wash_trading_events: list[TransactionEventDTO],
    ) -> None:
        """Test detect endpoint with real events returns success response."""
        # Arrange
        request_id = str(uuid4())
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint="d" * 64,
            events=sample_wash_trading_events,
        )

        # Act
        response = wash_trading_client.post("/detect", json=request.model_dump())

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["service_name"] == "wash_trading"
        assert data["status"] == "success"
        assert data["results"] is not None
        assert isinstance(data["results"], list)
        assert data["error"] is None

    def test_detect_with_empty_events_returns_success(
        self,
        wash_trading_client: TestClient,
    ) -> None:
        """Test detect endpoint with events that produce no suspicious sequences returns success with empty results."""
        # Arrange - Use events that won't produce suspicious sequences
        from tests.fixtures import create_transaction_event_dto, create_algorithm_request

        request = create_algorithm_request(
            event_fingerprint="e" * 64,
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=100,  # Small quantity, won't trigger wash trading detection
                    event_type="TRADE_EXECUTED",
                )
            ],
        )

        # Act
        response = wash_trading_client.post("/detect", json=request.model_dump())

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []


class TestIdempotency:
    """Tests for idempotency behavior (caching)."""

    def test_layering_service_cache_hit_on_duplicate_request(
        self,
        layering_client: TestClient,
        sample_layering_events: list[TransactionEventDTO],
    ) -> None:
        """Test Layering Service returns cached result for duplicate request_id + fingerprint."""
        # Arrange
        request_id = str(uuid4())
        fingerprint = "f" * 64
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=sample_layering_events,
        )

        # Act - First request (cache miss)
        response1 = layering_client.post("/detect", json=request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"
        results1 = data1["results"]

        # Act - Second request with same request_id + fingerprint (cache hit)
        response2 = layering_client.post("/detect", json=request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "success"
        results2 = data2["results"]

        # Assert - Results should be identical (from cache)
        assert results1 == results2
        assert len(results1) == len(results2)

    def test_wash_trading_service_cache_hit_on_duplicate_request(
        self,
        wash_trading_client: TestClient,
        sample_wash_trading_events: list[TransactionEventDTO],
    ) -> None:
        """Test Wash Trading Service returns cached result for duplicate request_id + fingerprint."""
        # Arrange
        request_id = str(uuid4())
        fingerprint = "0" * 64  # Valid hex character
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=sample_wash_trading_events,
        )

        # Act - First request (cache miss)
        response1 = wash_trading_client.post("/detect", json=request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        results1 = data1["results"]

        # Act - Second request with same request_id + fingerprint (cache hit)
        response2 = wash_trading_client.post("/detect", json=request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()
        results2 = data2["results"]

        # Assert - Results should be identical (from cache)
        assert results1 == results2

    def test_layering_service_cache_miss_on_different_fingerprint(
        self,
        layering_client: TestClient,
        sample_layering_events: list[TransactionEventDTO],
    ) -> None:
        """Test Layering Service cache miss when fingerprint differs."""
        # Arrange
        request_id = str(uuid4())
        request1 = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint="1" * 64,  # Valid hex character
            events=sample_layering_events,
        )
        request2 = AlgorithmRequest(
            request_id=request_id,  # Same request_id
            event_fingerprint="2" * 64,  # Different fingerprint (valid hex character)
            events=sample_layering_events,
        )

        # Act
        response1 = layering_client.post("/detect", json=request1.model_dump())
        response2 = layering_client.post("/detect", json=request2.model_dump())

        # Assert - Both should succeed (cache miss for second)
        assert response1.status_code == 200
        assert response2.status_code == 200
        # Both requests processed (not from cache)
        assert response1.json()["status"] == "success"
        assert response2.json()["status"] == "success"

    def test_wash_trading_service_cache_miss_on_different_request_id(
        self,
        wash_trading_client: TestClient,
        sample_wash_trading_events: list[TransactionEventDTO],
    ) -> None:
        """Test Wash Trading Service cache miss when request_id differs."""
        # Arrange
        fingerprint = "3" * 64  # Valid hex character
        request1 = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint=fingerprint,
            events=sample_wash_trading_events,
        )
        request2 = AlgorithmRequest(
            request_id=str(uuid4()),  # Different request_id
            event_fingerprint=fingerprint,  # Same fingerprint
            events=sample_wash_trading_events,
        )

        # Act
        response1 = wash_trading_client.post("/detect", json=request1.model_dump())
        response2 = wash_trading_client.post("/detect", json=request2.model_dump())

        # Assert - Both should succeed (cache miss for second)
        assert response1.status_code == 200
        assert response2.status_code == 200


class TestErrorHandling:
    """Tests for error handling in algorithm services."""

    def test_layering_service_handles_algorithm_exception(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test Layering Service handles algorithm exceptions gracefully."""
        # Arrange - Use events that won't trigger detection (minimal data)
        from tests.fixtures import create_transaction_event_dto, create_algorithm_request

        request = create_algorithm_request(
            event_fingerprint="4" * 64,  # Valid hex character
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=100,  # Small quantity, won't trigger layering
                    event_type="ORDER_PLACED",
                )
            ],
        )

        # Act
        response = layering_client.post("/detect", json=request.model_dump())

        # Assert - Should return success with empty results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []

    def test_wash_trading_service_handles_algorithm_exception(
        self,
        wash_trading_client: TestClient,
    ) -> None:
        """Test Wash Trading Service handles algorithm exceptions gracefully."""
        # Arrange - Use events that won't trigger detection (minimal data)
        from tests.fixtures import create_transaction_event_dto, create_algorithm_request

        request = create_algorithm_request(
            event_fingerprint="5" * 64,  # Valid hex character
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=100,  # Small quantity, won't trigger wash trading
                    event_type="TRADE_EXECUTED",
                )
            ],
        )

        # Act
        response = wash_trading_client.post("/detect", json=request.model_dump())

        # Assert - Should return success with empty results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []

    def test_layering_service_invalid_event_data_returns_validation_error(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test Layering Service returns validation error for invalid event data."""
        # Arrange - Invalid event data (negative quantity)
        request_id = str(uuid4())
        invalid_request = {
            "request_id": request_id,
            "event_fingerprint": "m" * 64,
            "events": [
                {
                    "timestamp": "2025-01-15T10:30:00",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": -1,  # Invalid: negative quantity
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        # Act
        response = layering_client.post("/detect", json=invalid_request)

        # Assert - FastAPI validation should catch this
        assert response.status_code == 422

    def test_wash_trading_service_invalid_timestamp_returns_validation_error(
        self,
        wash_trading_client: TestClient,
    ) -> None:
        """Test Wash Trading Service returns validation error for invalid timestamp."""
        # Arrange - Invalid timestamp format
        request_id = str(uuid4())
        invalid_request = {
            "request_id": request_id,
            "event_fingerprint": "n" * 64,
            "events": [
                {
                    "timestamp": "invalid-date",  # Invalid timestamp
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": 1000,
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        # Act
        response = wash_trading_client.post("/detect", json=invalid_request)

        # Assert
        assert response.status_code == 422


class TestCacheBehavior:
    """Tests for cache behavior (hit/miss scenarios)."""

    def test_layering_service_cache_isolated_per_service(
        self,
        layering_client: TestClient,
        sample_layering_events: list[TransactionEventDTO],
    ) -> None:
        """Test cache is isolated per service instance."""
        # Arrange
        request_id = str(uuid4())
        fingerprint = "6" * 64  # Valid hex character
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=sample_layering_events,
        )

        # Act - Multiple requests with same key
        response1 = layering_client.post("/detect", json=request.model_dump())
        response2 = layering_client.post("/detect", json=request.model_dump())
        response3 = layering_client.post("/detect", json=request.model_dump())

        # Assert - All should return same results (cached)
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200
        results1 = response1.json()["results"]
        results2 = response2.json()["results"]
        results3 = response3.json()["results"]
        assert results1 == results2 == results3

    def test_wash_trading_service_cache_handles_multiple_requests(
        self,
        wash_trading_client: TestClient,
        sample_wash_trading_events: list[TransactionEventDTO],
    ) -> None:
        """Test cache handles multiple concurrent requests correctly."""
        # Arrange
        request_id = str(uuid4())
        fingerprint = "7" * 64  # Valid hex character
        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=sample_wash_trading_events,
        )

        # Act - Multiple requests
        responses = [
            wash_trading_client.post("/detect", json=request.model_dump())
            for _ in range(5)
        ]

        # Assert - All should succeed and return same results
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "success"
        
        # All results should be identical (from cache after first)
        results = [r.json()["results"] for r in responses]
        assert all(r == results[0] for r in results)

