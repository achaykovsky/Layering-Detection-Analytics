"""
Unit tests for orchestrator API key authentication.

Tests authentication logic for the orchestrator service endpoints.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Import orchestrator main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "orchestrator-service" / "main.py"
spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
orchestrator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_main)
app = orchestrator_main.app
verify_api_key = orchestrator_main.verify_api_key
get_api_key = orchestrator_main.get_api_key


class TestVerifyApiKey:
    """Tests for verify_api_key authentication dependency."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        """Test that valid API key is accepted."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(orchestrator_main, "get_api_key", return_value=expected_key):
            # Act
            result = await verify_api_key(api_key=expected_key)

            # Assert
            assert result == expected_key

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_401(self) -> None:
        """Test that missing API key raises HTTP 401."""
        # Arrange
        expected_key = "test-api-key-123"
        with patch.object(orchestrator_main, "get_api_key", return_value=expected_key):
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
        with patch.object(orchestrator_main, "get_api_key", return_value=expected_key):
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(api_key=invalid_key)

            assert exc_info.value.status_code == 401
            assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_no_api_key_configured_allows_access(self) -> None:
        """Test that when API_KEY is not configured, authentication is skipped (dev mode)."""
        # Arrange - No API key configured
        with patch.object(orchestrator_main, "get_api_key", return_value=None):
            # Act
            result = await verify_api_key(api_key=None)

            # Assert - Should allow access when no API key configured
            assert result == ""


class TestOrchestrateEndpointAuth:
    """Tests for /orchestrate endpoint authentication."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_orchestrate_with_valid_api_key(
        self,
        client: TestClient,
    ) -> None:
        """Test that /orchestrate accepts requests with valid API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
            # Mock the orchestration logic to avoid full pipeline execution
            with patch.object(
                orchestrator_main,
                "read_input_csv",
                side_effect=FileNotFoundError("Mocked for auth test"),
            ):
                # Act
                response = client.post(
                    "/orchestrate",
                    json={"input_file": "test.csv"},
                    headers={"X-API-Key": api_key},
                )

                # Assert - Should pass authentication (may fail on file not found, but not 401)
                assert response.status_code != 401
                # Should be 404 (file not found) or 400 (path validation), not 401
                assert response.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_orchestrate_without_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /orchestrate rejects requests without API key."""
        # Arrange
        api_key = "test-api-key-123"
        with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": "test.csv"},
                # No X-API-Key header
            )

            # Assert
            assert response.status_code == 401
            assert "Missing API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_orchestrate_with_invalid_api_key_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Test that /orchestrate rejects requests with invalid API key."""
        # Arrange
        api_key = "test-api-key-123"
        invalid_key = "wrong-key"
        with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": "test.csv"},
                headers={"X-API-Key": invalid_key},
            )

            # Assert
            assert response.status_code == 401
            assert "Invalid API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_orchestrate_without_api_key_config_allows_access(
        self,
        client: TestClient,
    ) -> None:
        """Test that /orchestrate allows access when API_KEY is not configured (dev mode)."""
        # Arrange - No API key configured
        with patch.object(orchestrator_main, "get_api_key", return_value=None):
            # Mock orchestration to avoid full pipeline
            with patch.object(
                orchestrator_main,
                "read_input_csv",
                side_effect=FileNotFoundError("Mocked for auth test"),
            ):
                # Act
                response = client.post(
                    "/orchestrate",
                    json={"input_file": "test.csv"},
                    # No X-API-Key header
                )

                # Assert - Should not return 401 (auth skipped)
                assert response.status_code != 401
                # Should be 404 (file not found) or 400 (path validation)
                assert response.status_code in (400, 404)


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
        with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
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
        with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
            # Act - With API key header
            response = client.get(
                "/health",
                headers={"X-API-Key": api_key},
            )

            # Assert - Should succeed
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

