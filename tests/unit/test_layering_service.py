"""
Unit tests for Layering Service detection endpoint.

Tests the POST /detect endpoint with mocked algorithm calls.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from layering_detection.models import SuspiciousSequence, TransactionEvent
from services.shared.api_models import AlgorithmRequest, AlgorithmResponse, TransactionEventDTO


# Import the app after setting up path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import app module (need to import as module to handle path setup)
app_module_path = project_root / "services" / "layering-service" / "main.py"
spec = importlib.util.spec_from_file_location("layering_service_main", app_module_path)
layering_service_main = importlib.util.module_from_spec(spec)
sys.modules["layering_service_main"] = layering_service_main
spec.loader.exec_module(layering_service_main)
app = layering_service_main.app


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_transaction_event_dto() -> TransactionEventDTO:
    """Create sample TransactionEventDTO for testing."""
    return TransactionEventDTO(
        timestamp="2025-01-15T10:30:00",
        account_id="ACC001",
        product_id="IBM",
        side="BUY",
        price="100.50",
        quantity=1000,
        event_type="ORDER_PLACED",
    )


@pytest.fixture
def sample_algorithm_request(sample_transaction_event_dto: TransactionEventDTO) -> AlgorithmRequest:
    """Create sample AlgorithmRequest for testing."""
    return AlgorithmRequest(
        request_id=str(uuid4()),
        event_fingerprint="a" * 64,  # Valid SHA256 hexdigest
        events=[sample_transaction_event_dto],
    )


@pytest.fixture
def sample_suspicious_sequence() -> SuspiciousSequence:
    """Create sample SuspiciousSequence for testing."""
    return SuspiciousSequence(
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


class TestDetectEndpoint:
    """Tests for POST /detect endpoint."""

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_success(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test successful detection returns AlgorithmResponse with status success."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = [sample_suspicious_sequence]
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=sample_algorithm_request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["service_name"] == "layering"
        assert data["request_id"] == sample_algorithm_request.request_id
        assert data["error"] is None
        assert data["results"] is not None
        assert len(data["results"]) == 1
        assert data["results"][0]["account_id"] == "ACC001"

        # Verify algorithm was called
        mock_algorithm_instance.detect.assert_called_once()
        call_args = mock_algorithm_instance.detect.call_args[0][0]
        assert len(list(call_args)) == 1

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_no_sequences(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """Test detection with no suspicious sequences returns empty results."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = []
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=sample_algorithm_request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []
        assert data["error"] is None

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_algorithm_exception(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """Test detection handles algorithm exceptions and returns failure status."""
        # Setup mock to raise exception
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.side_effect = ValueError("Invalid events provided")
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=sample_algorithm_request.model_dump())

        # Assertions - should still return HTTP 200
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failure"
        assert data["service_name"] == "layering"
        assert data["request_id"] == sample_algorithm_request.request_id
        assert data["results"] is None
        assert data["error"] == "Invalid events provided"

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_multiple_sequences(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test detection with multiple suspicious sequences."""
        # Create second sequence
        sequence2 = SuspiciousSequence(
            account_id="ACC002",
            product_id="GOOG",
            start_timestamp=datetime(2025, 1, 15, 11, 0, 0),
            end_timestamp=datetime(2025, 1, 15, 11, 0, 10),
            total_buy_qty=3000,
            total_sell_qty=0,
            detection_type="LAYERING",
            side="SELL",
            num_cancelled_orders=4,
            order_timestamps=[datetime(2025, 1, 15, 11, 0, 0)],
        )

        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = [sample_suspicious_sequence, sequence2]
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=sample_algorithm_request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["results"]) == 2
        assert data["results"][0]["account_id"] == "ACC001"
        assert data["results"][1]["account_id"] == "ACC002"

    def test_detect_invalid_request(self, client: TestClient) -> None:
        """Test detection with invalid request returns validation error."""
        # Make request with invalid data
        response = client.post("/detect", json={"invalid": "data"})

        # FastAPI should return 422 for validation error
        assert response.status_code == 422

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_conversion_error(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
    ) -> None:
        """Test detection handles conversion errors."""
        # Create request with invalid timestamp format that passes DTO validation
        # but fails during domain conversion (this scenario is unlikely since DTO
        # validation catches most issues, but we test algorithm exceptions instead)
        request = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint="a" * 64,
            events=[
                TransactionEventDTO(
                    timestamp="2025-01-15T10:30:00",  # Valid DTO
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=1000,
                    event_type="ORDER_PLACED",
                )
            ],
        )

        # Mock algorithm to raise ValueError (simulating conversion/algorithm error)
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.side_effect = ValueError("Conversion failed")
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request - algorithm error should be caught
        response = client.post("/detect", json=request.model_dump())

        # Should return failure status (error caught)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failure"
        assert data["error"] is not None
        assert "Conversion failed" in data["error"]

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_request_id_preserved(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """Test that request_id is preserved in response."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = []
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=sample_algorithm_request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == sample_algorithm_request.request_id

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_detect_empty_events(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
    ) -> None:
        """Test detection with empty events list (algorithm returns empty results)."""
        # Note: AlgorithmRequest requires at least 1 event, so we test with
        # a valid request but algorithm returns empty results
        request = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint="a" * 64,
            events=[
                TransactionEventDTO(
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

        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = []
        mock_algorithm_class.return_value = mock_algorithm_instance

        # Make request
        response = client.post("/detect", json=request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["results"] == []


class TestCacheBehavior:
    """Tests for idempotency cache behavior."""

    def setup_method(self) -> None:
        """Clear cache before each test."""
        # Access the cache from the imported module
        if hasattr(layering_service_main, "_result_cache"):
            layering_service_main._result_cache.clear()

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_cache_miss_then_hit(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test cache miss on first request, cache hit on second identical request."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = [sample_suspicious_sequence]
        mock_algorithm_class.return_value = mock_algorithm_instance

        # First request - cache miss
        response1 = client.post("/detect", json=sample_algorithm_request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"
        assert len(data1["results"]) == 1
        
        # Verify algorithm was called
        assert mock_algorithm_instance.detect.call_count == 1

        # Second request with same request_id and fingerprint - cache hit
        response2 = client.post("/detect", json=sample_algorithm_request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "success"
        assert len(data2["results"]) == 1
        assert data2["results"] == data1["results"]  # Same results
        
        # Verify algorithm was NOT called again (cache hit)
        assert mock_algorithm_instance.detect.call_count == 1

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_cache_different_fingerprint(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_transaction_event_dto: TransactionEventDTO,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test cache miss for same request_id but different event_fingerprint."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = [sample_suspicious_sequence]
        mock_algorithm_class.return_value = mock_algorithm_instance

        request_id = str(uuid4())
        
        # First request
        request1 = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint="a" * 64,  # First fingerprint
            events=[sample_transaction_event_dto],
        )
        response1 = client.post("/detect", json=request1.model_dump())
        assert response1.status_code == 200
        assert mock_algorithm_instance.detect.call_count == 1

        # Second request with same request_id but different fingerprint
        request2 = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint="b" * 64,  # Different fingerprint
            events=[sample_transaction_event_dto],
        )
        response2 = client.post("/detect", json=request2.model_dump())
        assert response2.status_code == 200
        
        # Should be cache miss (different fingerprint)
        assert mock_algorithm_instance.detect.call_count == 2

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_cache_different_request_id(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_transaction_event_dto: TransactionEventDTO,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test cache miss for different request_id but same event_fingerprint."""
        # Setup mock
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.return_value = [sample_suspicious_sequence]
        mock_algorithm_class.return_value = mock_algorithm_instance

        fingerprint = "a" * 64
        
        # First request
        request1 = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint=fingerprint,
            events=[sample_transaction_event_dto],
        )
        response1 = client.post("/detect", json=request1.model_dump())
        assert response1.status_code == 200
        assert mock_algorithm_instance.detect.call_count == 1

        # Second request with different request_id but same fingerprint
        request2 = AlgorithmRequest(
            request_id=str(uuid4()),  # Different request_id
            event_fingerprint=fingerprint,  # Same fingerprint
            events=[sample_transaction_event_dto],
        )
        response2 = client.post("/detect", json=request2.model_dump())
        assert response2.status_code == 200
        
        # Should be cache miss (different request_id)
        assert mock_algorithm_instance.detect.call_count == 2

    @patch("layering_service_main.LayeringDetectionAlgorithm")
    def test_cache_not_stored_on_error(
        self,
        mock_algorithm_class: MagicMock,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """Test that errors are not cached."""
        # Setup mock to raise exception
        mock_algorithm_instance = MagicMock()
        mock_algorithm_instance.detect.side_effect = ValueError("Test error")
        mock_algorithm_class.return_value = mock_algorithm_instance

        # First request - should fail
        response1 = client.post("/detect", json=sample_algorithm_request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "failure"

        # Second request - should fail again (not cached)
        response2 = client.post("/detect", json=sample_algorithm_request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "failure"
        
        # Algorithm should be called again (error not cached)
        assert mock_algorithm_instance.detect.call_count == 2


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint returns correct response."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "layering-service"

