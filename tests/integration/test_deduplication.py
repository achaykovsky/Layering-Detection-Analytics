"""
Integration tests for deduplication and idempotency.

Tests event fingerprinting, cache behavior, and idempotent operations.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from layering_detection.models import TransactionEvent
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

# Import orchestrator utils for fingerprinting
orchestrator_utils_path = project_root / "services" / "orchestrator-service" / "utils.py"
utils_spec = importlib.util.spec_from_file_location("orchestrator_utils", orchestrator_utils_path)
orchestrator_utils = importlib.util.module_from_spec(utils_spec)
utils_spec.loader.exec_module(orchestrator_utils)
hash_events = orchestrator_utils.hash_events


@pytest.fixture
def layering_client() -> TestClient:
    """Create test client for Layering Service FastAPI app."""
    return TestClient(layering_app)


@pytest.fixture
def wash_trading_client() -> TestClient:
    """Create test client for Wash Trading Service FastAPI app."""
    return TestClient(wash_trading_app)


@pytest.fixture
def sample_events() -> list[TransactionEvent]:
    """Create sample TransactionEvent list for testing."""
    base_time = datetime(2025, 1, 15, 10, 0, 0)
    return [
        TransactionEvent(
            timestamp=base_time,
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.00"),
            quantity=1000,
            event_type="ORDER_PLACED",
        ),
        TransactionEvent(
            timestamp=base_time + timedelta(minutes=1),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.10"),
            quantity=2000,
            event_type="ORDER_PLACED",
        ),
        TransactionEvent(
            timestamp=base_time + timedelta(minutes=2),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.20"),
            quantity=3000,
            event_type="ORDER_CANCELLED",
        ),
    ]


@pytest.fixture
def sample_events_different() -> list[TransactionEvent]:
    """Create different sample TransactionEvent list for testing."""
    base_time = datetime(2025, 1, 15, 11, 0, 0)
    return [
        TransactionEvent(
            timestamp=base_time,
            account_id="ACC002",
            product_id="GOOG",
            side="SELL",
            price=Decimal("150.00"),
            quantity=500,
            event_type="ORDER_PLACED",
        ),
    ]


class TestEventFingerprinting:
    """Tests for event fingerprinting."""

    def test_same_events_produce_same_fingerprint(
        self,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test event fingerprinting: same events = same hash."""
        # Arrange
        fingerprint1 = hash_events(sample_events)
        fingerprint2 = hash_events(sample_events)

        # Assert
        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 64  # SHA256 hexdigest length
        assert len(fingerprint2) == 64

    def test_different_events_produce_different_fingerprint(
        self,
        sample_events: list[TransactionEvent],
        sample_events_different: list[TransactionEvent],
    ) -> None:
        """Test event fingerprinting: different events = different hash."""
        # Arrange
        fingerprint1 = hash_events(sample_events)
        fingerprint2 = hash_events(sample_events_different)

        # Assert
        assert fingerprint1 != fingerprint2
        assert len(fingerprint1) == 64
        assert len(fingerprint2) == 64

    def test_fingerprint_determinism_order_independent(
        self,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test fingerprint determinism: order-independent (same events in different order = same hash)."""
        # Arrange
        events_reversed = list(reversed(sample_events))
        events_shuffled = [sample_events[1], sample_events[2], sample_events[0]]

        fingerprint_original = hash_events(sample_events)
        fingerprint_reversed = hash_events(events_reversed)
        fingerprint_shuffled = hash_events(events_shuffled)

        # Assert - All should produce the same fingerprint
        assert fingerprint_original == fingerprint_reversed
        assert fingerprint_original == fingerprint_shuffled
        assert fingerprint_reversed == fingerprint_shuffled

    def test_empty_events_produce_consistent_fingerprint(self) -> None:
        """Test fingerprint for empty events list."""
        # Arrange
        empty_events: list[TransactionEvent] = []
        fingerprint1 = hash_events(empty_events)
        fingerprint2 = hash_events(empty_events)

        # Assert
        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 64


class TestAlgorithmServiceCache:
    """Tests for algorithm service cache behavior."""

    def test_cache_hit_same_request_id_and_fingerprint(
        self,
        layering_client: TestClient,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test algorithm service cache: same request_id + fingerprint = cache hit."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        request_id = str(uuid4())
        fingerprint = hash_events(sample_events)
        event_dtos = [transaction_event_to_dto(event) for event in sample_events]

        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        # Act - First call (cache miss)
        response1 = layering_client.post("/detect", json=request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"

        # Act - Second call with same request_id and fingerprint (cache hit)
        response2 = layering_client.post("/detect", json=request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()

        # Assert - Should return cached result
        assert data2["status"] == "success"
        assert data2["request_id"] == request_id
        # Results should be identical
        assert data1["results"] == data2["results"]

    def test_cache_miss_different_request_id(
        self,
        layering_client: TestClient,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test cache miss: different request_id."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        fingerprint = hash_events(sample_events)
        event_dtos = [transaction_event_to_dto(event) for event in sample_events]

        request1 = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        request2 = AlgorithmRequest(
            request_id=str(uuid4()),  # Different request_id
            event_fingerprint=fingerprint,  # Same fingerprint
            events=event_dtos,
        )

        # Act - First call
        response1 = layering_client.post("/detect", json=request1.model_dump())
        assert response1.status_code == 200

        # Act - Second call with different request_id (cache miss)
        response2 = layering_client.post("/detect", json=request2.model_dump())
        assert response2.status_code == 200

        # Assert - Both should process (cache miss for second)
        assert response1.json()["status"] == "success"
        assert response2.json()["status"] == "success"
        # Results should be the same (same events), but processed separately
        assert response1.json()["results"] == response2.json()["results"]

    def test_cache_miss_different_fingerprint(
        self,
        layering_client: TestClient,
        sample_events: list[TransactionEvent],
        sample_events_different: list[TransactionEvent],
    ) -> None:
        """Test cache miss: different fingerprint."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        request_id = str(uuid4())
        fingerprint1 = hash_events(sample_events)
        fingerprint2 = hash_events(sample_events_different)

        request1 = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint1,
            events=[transaction_event_to_dto(event) for event in sample_events],
        )

        request2 = AlgorithmRequest(
            request_id=request_id,  # Same request_id
            event_fingerprint=fingerprint2,  # Different fingerprint
            events=[transaction_event_to_dto(event) for event in sample_events_different],
        )

        # Act - First call
        response1 = layering_client.post("/detect", json=request1.model_dump())
        assert response1.status_code == 200

        # Act - Second call with different fingerprint (cache miss)
        response2 = layering_client.post("/detect", json=request2.model_dump())
        assert response2.status_code == 200

        # Assert - Both should process (cache miss for second)
        assert response1.json()["status"] == "success"
        assert response2.json()["status"] == "success"

    def test_cache_prevents_duplicate_processing_on_retries(
        self,
        layering_client: TestClient,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test cache prevents duplicate processing on retries."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        request_id = str(uuid4())
        fingerprint = hash_events(sample_events)
        event_dtos = [transaction_event_to_dto(event) for event in sample_events]

        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        # Act - First call (cache miss, processes)
        response1 = layering_client.post("/detect", json=request.model_dump())
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["status"] == "success"

        # Act - Simulate retry: same request_id + fingerprint (cache hit, no processing)
        response2 = layering_client.post("/detect", json=request.model_dump())
        assert response2.status_code == 200
        data2 = response2.json()

        # Act - Another retry (cache hit)
        response3 = layering_client.post("/detect", json=request.model_dump())
        assert response3.status_code == 200
        data3 = response3.json()

        # Assert - All should return same cached result
        assert data1["results"] == data2["results"]
        assert data1["results"] == data3["results"]
        assert data2["results"] == data3["results"]
        # All should have same request_id
        assert data1["request_id"] == request_id
        assert data2["request_id"] == request_id
        assert data3["request_id"] == request_id

    def test_cache_works_for_wash_trading_service(
        self,
        wash_trading_client: TestClient,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test cache works for wash trading service."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        request_id = str(uuid4())
        fingerprint = hash_events(sample_events)
        event_dtos = [transaction_event_to_dto(event) for event in sample_events]

        request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        # Act - First call (cache miss)
        response1 = wash_trading_client.post("/detect", json=request.model_dump())
        assert response1.status_code == 200

        # Act - Second call (cache hit)
        response2 = wash_trading_client.post("/detect", json=request.model_dump())
        assert response2.status_code == 200

        # Assert - Should return cached result
        assert response1.json()["results"] == response2.json()["results"]

    def test_cache_isolation_between_services(
        self,
        layering_client: TestClient,
        wash_trading_client: TestClient,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test cache isolation between services."""
        # Arrange
        from services.shared.converters import transaction_event_to_dto

        request_id = str(uuid4())
        fingerprint = hash_events(sample_events)
        event_dtos = [transaction_event_to_dto(event) for event in sample_events]

        layering_request = AlgorithmRequest(
            request_id=request_id,
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        wash_trading_request = AlgorithmRequest(
            request_id=request_id,  # Same request_id
            event_fingerprint=fingerprint,  # Same fingerprint
            events=event_dtos,
        )

        # Act - Call both services
        layering_response1 = layering_client.post("/detect", json=layering_request.model_dump())
        wash_trading_response1 = wash_trading_client.post("/detect", json=wash_trading_request.model_dump())

        # Act - Call again (should hit cache in each service)
        layering_response2 = layering_client.post("/detect", json=layering_request.model_dump())
        wash_trading_response2 = wash_trading_client.post("/detect", json=wash_trading_request.model_dump())

        # Assert - Each service has its own cache
        assert layering_response1.json()["results"] == layering_response2.json()["results"]
        assert wash_trading_response1.json()["results"] == wash_trading_response2.json()["results"]
        # Results may differ between services (different algorithms)
        # But each service's cache should work independently

    def test_fingerprint_with_real_transaction_events(
        self,
        layering_client: TestClient,
    ) -> None:
        """Test fingerprint with real TransactionEvent data."""
        # Arrange - Create realistic events
        base_time = datetime(2025, 1, 15, 10, 0, 0)
        events = [
            TransactionEvent(
                timestamp=base_time + timedelta(minutes=i),
                account_id=f"ACC{i % 3 + 1:03d}",
                product_id="IBM",
                side="BUY" if i % 2 == 0 else "SELL",
                price=Decimal(f"{100.00 + i * 0.10:.2f}"),
                quantity=1000 + i * 100,
                event_type="ORDER_PLACED" if i % 3 != 2 else "ORDER_CANCELLED",
            )
            for i in range(10)
        ]

        from services.shared.converters import transaction_event_to_dto

        fingerprint = hash_events(events)
        event_dtos = [transaction_event_to_dto(event) for event in events]

        request = AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint=fingerprint,
            events=event_dtos,
        )

        # Act
        response = layering_client.post("/detect", json=request.model_dump())

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(fingerprint) == 64  # SHA256 hexdigest

