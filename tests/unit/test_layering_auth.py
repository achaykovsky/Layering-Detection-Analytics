"""
Unit tests for layering service API key authentication.

Tests authentication logic for the layering service endpoints.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Import layering main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "layering-service" / "main.py"
spec = importlib.util.spec_from_file_location("layering_main", main_path)
layering_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layering_main)
app = layering_main.app
verify_api_key = layering_main.verify_api_key
get_api_key = layering_main.get_api_key


class TestVerifyApiKey:
    """Tests for verify_api_key authentication dependency."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        """Test that valid API key is accepted."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(layering_main, "get_api_key", return_value=expected_key):
            # Act
            result = await verify_api_key(api_key=expected_key)

            # Assert
            assert result == expected_key

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_401(self) -> None:
        """Test that missing API key raises HTTP 401."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(layering_main, "get_api_key", return_value=expected_key):
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
        with patch.object(layering_main, "get_api_key", return_value=expected_key):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key=invalid_key)

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_access(self) -> None:
        """Test that when API_KEY is not configured, authentication is skipped (dev mode)."""
        # Arrange - No API key configured
        with patch.object(layering_main, "get_api_key", return_value=None):
            # Act
            result = await verify_api_key(api_key=None)

            # Assert - Should allow access when no API key configured
            assert result == ""


class TestDetectEndpointAuth:
    """Tests for /detect endpoint authentication."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_detect_with_valid_api_key(
        self,
        client: TestClient,
    ) -> None:
        """Test that /detect accepts requests with valid API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(layering_main, "get_api_key", return_value=api_key):
            # Mock the detection logic to avoid full algorithm execution
            with patch.object(
                layering_main,
                "LayeringDetectionAlgorithm",
            ) as mock_algorithm:
                mock_instance = mock_algorithm.return_value
                mock_instance.detect.return_value = []

                # Act
                response = client.post(
                    "/detect",
                    json={
                        "request_id": "test-123",
                        "event_fingerprint": "a" * 64,
                        "events": [],
                    },
                    headers={"X-API-Key": api_key},
                )

                # Assert - Should pass authentication (may fail on processing, but not 401)
                assert response.status_code != 401
                # Should be 200 (success) or 422 (validation error)
                assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_detect_without_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /detect rejects requests without API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(layering_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/detect",
                json={
                    "request_id": "test-123",
                    "event_fingerprint": "a" * 64,
                    "events": [],
                },
                # No X-API-Key header
            )

            # Assert
            assert response.status_code == 401
            assert "Missing API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_detect_with_invalid_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /detect rejects requests with invalid API key."""
        # Arrange
        api_key = "test-api-key-123"
        invalid_key = "wrong-key"
        with patch.object(layering_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/detect",
                json={
                    "request_id": "test-123",
                    "event_fingerprint": "a" * 64,
                    "events": [],
                },
                headers={"X-API-Key": invalid_key},
            )

            # Assert
            assert response.status_code == 401
            assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_detect_without_api_key_config_allows_access(
        self,
        client: TestClient,
    ) -> None:
        """Test that /detect allows access when API_KEY is not configured (dev mode)."""
        # Arrange - No API key configured
        with patch.object(layering_main, "get_api_key", return_value=None):
            # Mock the detection logic
            with patch.object(
                layering_main,
                "LayeringDetectionAlgorithm",
            ) as mock_algorithm:
                mock_instance = mock_algorithm.return_value
                mock_instance.detect.return_value = []

                # Act
                response = client.post(
                    "/detect",
                    json={
                        "request_id": "test-123",
                        "event_fingerprint": "a" * 64,
                        "events": [],
                    },
                    # No X-API-Key header
                )

                # Assert - Should not return 401 (auth skipped)
                assert response.status_code != 401
                # Should be 200 (success) or 422 (validation error)
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
        with patch.object(layering_main, "get_api_key", return_value=api_key):
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
        with patch.object(layering_main, "get_api_key", return_value=api_key):
            # Act - With API key header
            response = client.get(
                "/health",
                headers={"X-API-Key": api_key},
            )

            # Assert - Should succeed
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

