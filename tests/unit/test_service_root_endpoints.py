"""
Unit tests for service root endpoints.

Tests that root endpoints return only minimal information (service name, version, status)
and do not expose sensitive configuration details.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Import all service main modules
project_root = Path(__file__).parent.parent.parent


def load_service_app(service_name: str):
    """Load service app module."""
    main_path = project_root / "services" / f"{service_name}-service" / "main.py"
    spec = importlib.util.spec_from_file_location(f"{service_name}_main", main_path)
    service_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(service_main)
    return service_main.app


class TestOrchestratorRootEndpoint:
    """Tests for orchestrator service root endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = load_service_app("orchestrator")
        return TestClient(app)

    def test_root_endpoint_returns_minimal_info(self, client: TestClient) -> None:
        """Test that root endpoint returns only service, version, and status."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify only expected fields are present
        assert set(data.keys()) == {"service", "version", "status"}
        assert data["service"] == "orchestrator-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"

    def test_root_endpoint_no_sensitive_info(self, client: TestClient) -> None:
        """Test that root endpoint does not expose sensitive configuration."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify sensitive fields are not present
        sensitive_fields = [
            "input_dir",
            "layering_service_url",
            "wash_trading_service_url",
            "aggregator_service_url",
            "max_retries",
            "timeout_seconds",
        ]
        for field in sensitive_fields:
            assert field not in data, f"Sensitive field '{field}' should not be exposed"


class TestLayeringRootEndpoint:
    """Tests for layering service root endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = load_service_app("layering")
        return TestClient(app)

    def test_root_endpoint_returns_minimal_info(self, client: TestClient) -> None:
        """Test that root endpoint returns only service, version, and status."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify only expected fields are present
        assert set(data.keys()) == {"service", "version", "status"}
        assert data["service"] == "layering-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestWashTradingRootEndpoint:
    """Tests for wash trading service root endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = load_service_app("wash-trading")
        return TestClient(app)

    def test_root_endpoint_returns_minimal_info(self, client: TestClient) -> None:
        """Test that root endpoint returns only service, version, and status."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify only expected fields are present
        assert set(data.keys()) == {"service", "version", "status"}
        assert data["service"] == "wash-trading-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"


class TestAggregatorRootEndpoint:
    """Tests for aggregator service root endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = load_service_app("aggregator")
        return TestClient(app)

    def test_root_endpoint_returns_minimal_info(self, client: TestClient) -> None:
        """Test that root endpoint returns only service, version, and status."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify only expected fields are present
        assert set(data.keys()) == {"service", "version", "status"}
        assert data["service"] == "aggregator-service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"

    def test_root_endpoint_no_sensitive_info(self, client: TestClient) -> None:
        """Test that root endpoint does not expose sensitive configuration."""
        # Act
        response = client.get("/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Verify sensitive fields are not present
        sensitive_fields = [
            "output_dir",
            "logs_dir",
            "validation_strict",
            "allow_partial_results",
        ]
        for field in sensitive_fields:
            assert field not in data, f"Sensitive field '{field}' should not be exposed"


class TestHealthEndpointsUnchanged:
    """Tests that health check endpoints remain unchanged."""

    @pytest.fixture
    def orchestrator_client(self) -> TestClient:
        """Create orchestrator FastAPI test client."""
        app = load_service_app("orchestrator")
        return TestClient(app)

    @pytest.fixture
    def layering_client(self) -> TestClient:
        """Create layering FastAPI test client."""
        app = load_service_app("layering")
        return TestClient(app)

    @pytest.fixture
    def wash_trading_client(self) -> TestClient:
        """Create wash trading FastAPI test client."""
        app = load_service_app("wash-trading")
        return TestClient(app)

    @pytest.fixture
    def aggregator_client(self) -> TestClient:
        """Create aggregator FastAPI test client."""
        app = load_service_app("aggregator")
        return TestClient(app)

    def test_orchestrator_health_endpoint_unchanged(
        self, orchestrator_client: TestClient
    ) -> None:
        """Test that orchestrator health endpoint remains unchanged."""
        response = orchestrator_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    def test_layering_health_endpoint_unchanged(
        self, layering_client: TestClient
    ) -> None:
        """Test that layering health endpoint remains unchanged."""
        response = layering_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    def test_wash_trading_health_endpoint_unchanged(
        self, wash_trading_client: TestClient
    ) -> None:
        """Test that wash trading health endpoint remains unchanged."""
        response = wash_trading_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

    def test_aggregator_health_endpoint_unchanged(
        self, aggregator_client: TestClient
    ) -> None:
        """Test that aggregator health endpoint remains unchanged."""
        response = aggregator_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data

