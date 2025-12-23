"""
Unit tests for Wash Trading Service detection endpoint.

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
    create_suspicious_sequence_wash_trading,
    create_transaction_event_dto,
    patch_algorithm_class,
)
from tests.unit.test_service_base import BaseServiceTest

# Import the app after setting up path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import app module (need to import as module to handle path setup)
app_module_path = project_root / "services" / "wash-trading-service" / "main.py"
spec = importlib.util.spec_from_file_location("wash_trading_service_main", app_module_path)
wash_trading_service_main = importlib.util.module_from_spec(spec)
sys.modules["wash_trading_service_main"] = wash_trading_service_main
spec.loader.exec_module(wash_trading_service_main)
app = wash_trading_service_main.app


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_transaction_event_dto() -> TransactionEventDTO:
    """
    Create sample TransactionEventDTO for wash trading service tests.
    
    Overrides the common fixture to use TRADE_EXECUTED event type,
    which is specific to wash trading detection.
    """
    return create_transaction_event_dto(
        timestamp="2025-01-15T10:30:00",
        event_type="TRADE_EXECUTED",
    )


@pytest.fixture
def sample_suspicious_sequence() -> SuspiciousSequence:
    """Create sample SuspiciousSequence for testing."""
    return create_suspicious_sequence_wash_trading(
        start_timestamp=datetime(2025, 1, 15, 10, 30, 0),
        end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
        total_buy_qty=5000,
        total_sell_qty=5000,
        alternation_percentage=75.5,
        price_change_percentage=2.5,
    )


class TestDetectEndpoint(BaseServiceTest):
    """Tests for POST /detect endpoint."""

    @property
    def service_name(self) -> str:
        """Service name used in AlgorithmResponse."""
        return "wash_trading"

    @property
    def algorithm_class_path(self) -> str:
        """Full module path to algorithm class for mocking."""
        return "wash_trading_service_main.WashTradingDetectionAlgorithm"

    @property
    def detection_type(self) -> str:
        """Detection type string."""
        return "WASH_TRADING"

    @property
    def health_service_name(self) -> str:
        """Service name used in health check response."""
        return "wash-trading-service"

    @property
    def create_suspicious_sequence(self):
        """Factory function for creating SuspiciousSequence objects."""
        return create_suspicious_sequence_wash_trading

    def setup_method(self) -> None:
        """Clear cache before each test."""
        # Access the cache from the imported module
        if hasattr(wash_trading_service_main, "_result_cache"):
            wash_trading_service_main._result_cache.clear()

    def test_detect_wash_trading_sequence_fields(
        self,
        client: TestClient,
        sample_algorithm_request: AlgorithmRequest,
        sample_suspicious_sequence: SuspiciousSequence,
    ) -> None:
        """Test that wash trading specific fields are included in response."""
        with patch_algorithm_class(
            "wash_trading_service_main.WashTradingDetectionAlgorithm",
            detect_return_value=[sample_suspicious_sequence],
        ) as (mock_algorithm_class, mock_algorithm_instance):
            # Make request
            response = client.post("/detect", json=sample_algorithm_request.model_dump())

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            result = data["results"][0]
            assert result["detection_type"] == "WASH_TRADING"
            assert result["alternation_percentage"] == 75.5
            assert result["price_change_percentage"] == 2.5
            assert result["side"] is None  # Wash trading doesn't have side
            assert result["num_cancelled_orders"] is None  # Wash trading doesn't have cancelled orders


class TestHealthEndpoint(BaseServiceTest):
    """Tests for GET /health endpoint."""

    @property
    def service_name(self) -> str:
        """Service name used in AlgorithmResponse."""
        return "wash_trading"

    @property
    def algorithm_class_path(self) -> str:
        """Full module path to algorithm class for mocking."""
        return "wash_trading_service_main.WashTradingDetectionAlgorithm"

    @property
    def detection_type(self) -> str:
        """Detection type string."""
        return "WASH_TRADING"

    @property
    def health_service_name(self) -> str:
        """Service name used in health check response."""
        return "wash-trading-service"

    @property
    def create_suspicious_sequence(self):
        """Factory function for creating SuspiciousSequence objects."""
        return create_suspicious_sequence_wash_trading
