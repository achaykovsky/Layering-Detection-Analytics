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
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from layering_detection.models import SuspiciousSequence, TransactionEvent
from services.shared.api_models import AlgorithmRequest, AlgorithmResponse, TransactionEventDTO
from tests.fixtures import (
    create_algorithm_request,
    create_suspicious_sequence_layering,
    create_transaction_event_dto,
    patch_algorithm_class,
)
from tests.unit.test_service_base import BaseServiceTest


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
def sample_suspicious_sequence() -> SuspiciousSequence:
    """Create sample SuspiciousSequence for testing."""
    return create_suspicious_sequence_layering(
        start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
        end_timestamp=datetime(2025, 1, 15, 10, 30, 10),
        total_buy_qty=5000,
        total_sell_qty=0,
        side="BUY",
        num_cancelled_orders=3,
        order_timestamps=[
            datetime(2025, 1, 15, 10, 30, 0),
            datetime(2025, 1, 15, 10, 30, 5),
        ],
    )


class TestDetectEndpoint(BaseServiceTest):
    """Tests for POST /detect endpoint."""

    @property
    def service_name(self) -> str:
        """Service name used in AlgorithmResponse."""
        return "layering"

    @property
    def algorithm_class_path(self) -> str:
        """Full module path to algorithm class for mocking."""
        return "layering_service_main.LayeringDetectionAlgorithm"

    @property
    def detection_type(self) -> str:
        """Detection type string."""
        return "LAYERING"

    @property
    def health_service_name(self) -> str:
        """Service name used in health check response."""
        return "layering-service"

    @property
    def create_suspicious_sequence(self):
        """Factory function for creating SuspiciousSequence objects."""
        return create_suspicious_sequence_layering

    def setup_method(self) -> None:
        """Clear cache before each test."""
        # Access the cache from the imported module
        if hasattr(layering_service_main, "_result_cache"):
            layering_service_main._result_cache.clear()

    def test_detect_empty_events(
        self,
        client: TestClient,
    ) -> None:
        """Test detection with empty events list (algorithm returns empty results)."""
        # Note: AlgorithmRequest requires at least 1 event, so we test with
        # a valid request but algorithm returns empty results
        request = create_algorithm_request(
            events=[
                create_transaction_event_dto(
                    timestamp="2025-01-15T10:30:00",
                    event_type="ORDER_PLACED",
                )
            ],
        )

        with patch_algorithm_class(
            "layering_service_main.LayeringDetectionAlgorithm",
            detect_return_value=[],
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=request.model_dump())

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["results"] == []


class TestHealthEndpoint(BaseServiceTest):
    """Tests for GET /health endpoint."""

    @property
    def service_name(self) -> str:
        """Service name used in AlgorithmResponse."""
        return "layering"

    @property
    def algorithm_class_path(self) -> str:
        """Full module path to algorithm class for mocking."""
        return "layering_service_main.LayeringDetectionAlgorithm"

    @property
    def detection_type(self) -> str:
        """Detection type string."""
        return "LAYERING"

    @property
    def health_service_name(self) -> str:
        """Service name used in health check response."""
        return "layering-service"

    @property
    def create_suspicious_sequence(self):
        """Factory function for creating SuspiciousSequence objects."""
        return create_suspicious_sequence_layering

