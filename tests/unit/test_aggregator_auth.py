"""
Unit tests for aggregator service API key authentication.

Tests authentication logic for the aggregator service endpoints.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Import aggregator main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "aggregator-service" / "main.py"
spec = importlib.util.spec_from_file_location("aggregator_main", main_path)
aggregator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_main)
app = aggregator_main.app
verify_api_key = aggregator_main.verify_api_key
get_api_key = aggregator_main.get_api_key


class TestVerifyApiKey:
    """Tests for verify_api_key authentication dependency."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        """Test that valid API key is accepted."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=expected_key):
            # Act
            result = await verify_api_key(api_key=expected_key)

            # Assert
            assert result == expected_key

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_401(self) -> None:
        """Test that missing API key raises HTTP 401."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=expected_key):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key=None)

            assert exc_info.value.status_code == 401
            assert "Missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_401(self) -> None:
        """Test that invalid API key raises HTTP 401."""
        # Arrange
        expected_key = "test-api-key-123"
        invalid_key = "wrong-key"
        with patch.object(aggregator_main, "get_api_key", return_value=expected_key):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key=invalid_key)

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_access(self) -> None:
        """Test that when API_KEY is not configured, authentication is skipped (dev mode)."""
        # Arrange - No API key configured
        with patch.object(aggregator_main, "get_api_key", return_value=None):
            # Act
            result = await verify_api_key(api_key=None)

            # Assert - Should allow access when no API key configured
            assert result == ""


class TestAggregateEndpointAuth:
    """Tests for /aggregate endpoint authentication."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_aggregate_with_valid_api_key(
        self,
        client: TestClient,
    ) -> None:
        """Test that /aggregate accepts requests with valid API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=api_key):
            # Mock the aggregation logic to avoid full processing
            with patch.object(
                aggregator_main,
                "validate_completeness",
            ) as mock_validate:
                mock_validate.side_effect = ValueError("Mocked validation failure")

                # Act
                response = client.post(
                    "/aggregate",
                    json={
                        "request_id": "test-123",
                        "expected_services": ["layering", "wash_trading"],
                        "results": [],
                    },
                    headers={"X-API-Key": api_key},
                )

                # Assert - Should pass authentication (may fail on validation, but not 401)
                assert response.status_code != 401
                # Should be 200 (validation_failed status in body) or 422 (validation error)
                assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_aggregate_without_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /aggregate rejects requests without API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/aggregate",
                json={
                    "request_id": "test-123",
                    "expected_services": ["layering", "wash_trading"],
                    "results": [],
                },
                # No X-API-Key header
            )

            # Assert
            assert response.status_code == 401
            assert "Missing API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_aggregate_with_invalid_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /aggregate rejects requests with invalid API key."""
        # Arrange
        api_key = "test-api-key-123"
        invalid_key = "wrong-key"
        with patch.object(aggregator_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/aggregate",
                json={
                    "request_id": "test-123",
                    "expected_services": ["layering", "wash_trading"],
                    "results": [],
                },
                headers={"X-API-Key": invalid_key},
            )

            # Assert
            assert response.status_code == 401
            assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_aggregate_without_api_key_config_allows_access(
        self,
        client: TestClient,
    ) -> None:
        """Test that /aggregate allows access when API_KEY is not configured (dev mode)."""
        # Arrange - No API key configured
        with patch.object(aggregator_main, "get_api_key", return_value=None):
            # Mock the aggregation logic
            with patch.object(
                aggregator_main,
                "validate_completeness",
            ) as mock_validate:
                mock_validate.side_effect = ValueError("Mocked validation failure")

                # Act
                response = client.post(
                    "/aggregate",
                    json={
                        "request_id": "test-123",
                        "expected_services": ["layering", "wash_trading"],
                        "results": [],
                    },
                    # No X-API-Key header
                )

                # Assert - Should not return 401 (auth skipped)
                assert response.status_code != 401
                # Should be 200 (validation_failed status in body) or 422 (validation error)
                assert response.status_code in (200, 422)


class TestHealthEndpointAuth:
    """Tests for /health endpoint (should remain public)."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    def test_health_check_public_no_auth_required(
        self,
        client: TestClient,
    ) -> None:
        """Test that /health endpoint is public and doesn't require authentication."""
        # Arrange - API key configured but not required for health
        api_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=api_key):
            # Act - No API key header
            response = client.get("/health")

            # Assert - Should succeed without authentication
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    def test_health_check_with_api_key_also_works(
        self,
        client: TestClient,
    ) -> None:
        """Test that /health endpoint works with or without API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(aggregator_main, "get_api_key", return_value=api_key):
            # Act - With API key header
            response = client.get(
                "/health",
                headers={"X-API-Key": api_key},
            )

            # Assert - Should succeed
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

