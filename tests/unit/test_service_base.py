"""
Base test class for service endpoint tests.

This module provides a base class that contains shared test methods for service
endpoint tests, eliminating duplicate test code between wash trading and layering
service tests.

## When to Use BaseServiceTest

**Use BaseServiceTest when:**
- Writing tests for a new service endpoint that follows the same pattern
- You need shared test methods (detect endpoint, caching, health checks)
- You want to reduce duplicate test code between similar services

**Don't use BaseServiceTest when:**
- Your service has completely different endpoints or behavior
- Shared test methods don't apply to your service
- You need to test service-specific functionality not covered by base class

## Usage

Subclass BaseServiceTest and implement the required abstract properties:

```python
class TestMyServiceEndpoint(BaseServiceTest):
    @property
    def service_name(self) -> str:
        return "my_service"
    
    @property
    def algorithm_class_path(self) -> str:
        return "my_service_main.MyDetectionAlgorithm"
    
    @property
    def detection_type(self) -> str:
        return "MY_DETECTION_TYPE"
    
    @property
    def health_service_name(self) -> str:
        return "my-service"
    
    @property
    def create_suspicious_sequence(self):
        return create_suspicious_sequence_my_type
```

The base class provides 12 shared test methods that automatically work with
your service configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from layering_detection.models import SuspiciousSequence
from services.shared.api_models import AlgorithmRequest, TransactionEventDTO
from tests.fixtures import (
    create_algorithm_request,
    create_suspicious_sequence_layering,
    create_suspicious_sequence_wash_trading,
    create_transaction_event_dto,
    patch_algorithm_class,
)


class BaseServiceTest(ABC):
    """
    Abstract base class for service endpoint tests.

    Subclasses must implement abstract properties to provide service-specific
    configuration values.

    ## Inherited Test Methods

    The base class provides these shared test methods:
    - `test_detect_success()` - Successful detection
    - `test_detect_no_sequences()` - No sequences detected
    - `test_detect_algorithm_exception()` - Algorithm raises exception
    - `test_detect_multiple_sequences()` - Multiple sequences detected
    - `test_detect_invalid_request()` - Invalid request handling
    - `test_detect_conversion_error()` - Conversion error handling
    - `test_detect_request_id_preserved()` - Request ID preservation
    - `test_cache_miss_then_hit()` - Cache miss then hit
    - `test_cache_different_fingerprint()` - Different fingerprint handling
    - `test_cache_different_request_id()` - Different request ID handling
    - `test_cache_not_stored_on_error()` - Cache not stored on error
    - `test_health_check()` - Health endpoint

    ## Service-Specific Tests

    Keep service-specific tests in your subclass. For example:
    - Tests for service-specific sequence fields
    - Tests for service-specific validation logic
    - Tests for service-specific error handling

    Example:
        >>> class TestWashTradingService(BaseServiceTest):
        ...     @property
        ...     def service_name(self) -> str:
        ...         return "wash_trading"
        ...     
        ...     def test_wash_trading_specific_field(self):
        ...         # Service-specific test
        ...         pass
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """
        Service name used in AlgorithmResponse (e.g., "wash_trading", "layering").

        Returns:
            Service name string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def algorithm_class_path(self) -> str:
        """
        Full module path to algorithm class for mocking (e.g., "wash_trading_service_main.WashTradingDetectionAlgorithm").

        Returns:
            Module path string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def detection_type(self) -> str:
        """
        Detection type string (e.g., "WASH_TRADING", "LAYERING").

        Returns:
            Detection type string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def health_service_name(self) -> str:
        """
        Service name used in health check response (e.g., "wash-trading-service", "layering-service").

        Returns:
            Health service name string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def create_suspicious_sequence(self):
        """
        Factory function for creating SuspiciousSequence objects for this detection type.

        Returns:
            Factory function (create_suspicious_sequence_layering or create_suspicious_sequence_wash_trading).
        """
        raise NotImplementedError


    def test_detect_success(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """
        Test successful detection returns AlgorithmResponse with status success.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
            sample_suspicious_sequence: Sample suspicious sequence fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[sample_suspicious_sequence],
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=sample_algorithm_request.model_dump())

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["service_name"] == self.service_name
            assert data["request_id"] == sample_algorithm_request.request_id
            assert data["error"] is None
            assert data["results"] is not None
            assert len(data["results"]) == 1
            assert data["results"][0]["account_id"] == "ACC001"
            assert data["results"][0]["detection_type"] == self.detection_type

            # Verify algorithm was called
            mock_algorithm_instance.detect.assert_called_once()
            call_args = mock_algorithm_instance.detect.call_args[0][0]
            assert len(list(call_args)) == 1

    def test_detect_no_sequences(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """
        Test detection with no suspicious sequences returns empty results.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[],
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=sample_algorithm_request.model_dump())

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["results"] == []
            assert data["error"] is None

    def test_detect_algorithm_exception(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """
        Test detection handles algorithm exceptions and returns failure status.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_side_effect=ValueError("Invalid events provided"),
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=sample_algorithm_request.model_dump())

            # Assertions - should still return HTTP 200
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failure"
            assert data["service_name"] == self.service_name
            assert data["request_id"] == sample_algorithm_request.request_id
            assert data["results"] is None
            assert data["error"] == "Invalid events provided"

    def test_detect_multiple_sequences(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """
        Test detection with multiple suspicious sequences.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
            sample_suspicious_sequence: Sample suspicious sequence fixture.
        """
        # Create second sequence
        from datetime import datetime

        if self.detection_type == "WASH_TRADING":
            sequence2 = create_suspicious_sequence_wash_trading(
                account_id="ACC002",
                product_id="GOOG",
                start_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                end_timestamp=datetime(2025, 1, 15, 11, 30, 0),
                total_buy_qty=3000,
                total_sell_qty=3000,
                alternation_percentage=80.0,
                price_change_percentage=1.5,
            )
        else:  # LAYERING
            sequence2 = create_suspicious_sequence_layering(
                account_id="ACC002",
                product_id="GOOG",
                start_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                end_timestamp=datetime(2025, 1, 15, 11, 0, 10),
                total_buy_qty=3000,
                total_sell_qty=0,
                side="SELL",
                num_cancelled_orders=4,
                order_timestamps=[datetime(2025, 1, 15, 11, 0, 0)],
            )

        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[sample_suspicious_sequence, sequence2],
        ) as (mock_algorithm_class, mock_algorithm_instance):
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
        """
        Test detection with invalid request returns validation error.

        Args:
            client: FastAPI test client.
        """
        # Make request with invalid data
        response = client.post("/detect", json={"invalid": "data"})

        # FastAPI should return 422 for validation error
        assert response.status_code == 422

    def test_detect_conversion_error(
        self,
        client: TestClient,
    ) -> None:
        """
        Test detection handles conversion errors.

        Args:
            client: FastAPI test client.
        """
        # Create request with valid event data
        request = create_algorithm_request(
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    event_type="TRADE_EXECUTED" if self.detection_type == "WASH_TRADING" else "ORDER_PLACED",
                )
            ],
        )

        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_side_effect=ValueError("Conversion failed"),
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request - algorithm error should be caught
            response = client.post("/detect", json=request.model_dump())

            # Should return failure status (error caught)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failure"
            assert data["error"] is not None
            assert "Conversion failed" in data["error"]

    def test_detect_request_id_preserved(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """
        Test that request_id is preserved in response.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[],
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=sample_algorithm_request.model_dump())

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["request_id"] == sample_algorithm_request.request_id

    def test_cache_miss_then_hit(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """
        Test cache miss on first request, cache hit on second identical request.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
            sample_suspicious_sequence: Sample suspicious sequence fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[sample_suspicious_sequence],
        ) as (mock_algorithm_class, mock_algorithm_instance):
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

    def test_cache_different_fingerprint(
        self,
        client: TestClient,
        sample_transaction_event_dto: TransactionEventDTO,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """
        Test cache miss for same request_id but different event_fingerprint.

        Args:
            client: FastAPI test client.
            sample_transaction_event_dto: Sample transaction event DTO fixture.
            sample_suspicious_sequence: Sample suspicious sequence fixture.
        """
        request_id = str(uuid4())

        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[sample_suspicious_sequence],
        ) as (mock_algorithm_class, mock_algorithm_instance):

            # First request
            request1 = create_algorithm_request(
                request_id=request_id,
                event_fingerprint="a" * 64,  # First fingerprint
                events=[sample_transaction_event_dto],
            )
            response1 = client.post("/detect", json=request1.model_dump())
            assert response1.status_code == 200
            assert mock_algorithm_instance.detect.call_count == 1

            # Second request with same request_id but different fingerprint
            request2 = create_algorithm_request(
                request_id=request_id,
                event_fingerprint="b" * 64,  # Different fingerprint
                events=[sample_transaction_event_dto],
            )
            response2 = client.post("/detect", json=request2.model_dump())
            assert response2.status_code == 200

            # Should be cache miss (different fingerprint)
            assert mock_algorithm_instance.detect.call_count == 2

    def test_cache_different_request_id(
        self,
        client: TestClient,
        sample_transaction_event_dto: TransactionEventDTO,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """
        Test cache miss for different request_id but same event_fingerprint.

        Args:
            client: FastAPI test client.
            sample_transaction_event_dto: Sample transaction event DTO fixture.
            sample_suspicious_sequence: Sample suspicious sequence fixture.
        """
        fingerprint = "a" * 64

        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_return_value=[sample_suspicious_sequence],
        ) as (mock_algorithm_class, mock_algorithm_instance):

            # First request
            request1 = create_algorithm_request(
                event_fingerprint=fingerprint,
                events=[sample_transaction_event_dto],
            )
            response1 = client.post("/detect", json=request1.model_dump())
            assert response1.status_code == 200
            assert mock_algorithm_instance.detect.call_count == 1

            # Second request with different request_id but same fingerprint
            request2 = create_algorithm_request(
                event_fingerprint=fingerprint,  # Same fingerprint
                events=[sample_transaction_event_dto],
            )
            response2 = client.post("/detect", json=request2.model_dump())
            assert response2.status_code == 200

            # Should be cache miss (different request_id)
            assert mock_algorithm_instance.detect.call_count == 2

    def test_cache_not_stored_on_error(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
    ) -> None:
        """
        Test that errors are not cached.

        Args:
            client: FastAPI test client.
            sample_algorithm_request: Sample algorithm request fixture.
        """
        with patch_algorithm_class(
            self.algorithm_class_path,
            detect_side_effect=ValueError("Test error"),
        ) as (mock_algorithm_class, mock_algorithm_instance):
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

    def test_health_check(self, client: TestClient) -> None:
        """
        Test health check endpoint returns correct response.

        Args:
            client: FastAPI test client.
        """
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == self.health_service_name

