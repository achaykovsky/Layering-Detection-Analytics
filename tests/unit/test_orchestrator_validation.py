"""
Unit tests for orchestrator service input validation.

Tests input_file validation to prevent path injection attacks.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Import orchestrator main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "orchestrator-service" / "main.py"
spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
orchestrator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_main)
OrchestrateRequest = orchestrator_main.OrchestrateRequest


class TestInputFileValidation:
    """Tests for OrchestrateRequest.input_file validation."""

    def test_valid_filename_accepted(self) -> None:
        """Test that valid filenames are accepted."""
        # Arrange & Act
        request = OrchestrateRequest(input_file="transactions.csv")

        # Assert
        assert request.input_file == "transactions.csv"

    def test_valid_filename_with_hyphens(self) -> None:
        """Test that filenames with hyphens are accepted."""
        # Arrange & Act
        request = OrchestrateRequest(input_file="transactions-2025-01-15.csv")

        # Assert
        assert request.input_file == "transactions-2025-01-15.csv"

    def test_valid_filename_with_underscores(self) -> None:
        """Test that filenames with underscores are accepted."""
        # Arrange & Act
        request = OrchestrateRequest(input_file="transactions_2025_01_15.csv")

        # Assert
        assert request.input_file == "transactions_2025_01_15.csv"

    def test_valid_filename_with_dots(self) -> None:
        """Test that filenames with dots (for extensions) are accepted."""
        # Arrange & Act
        request = OrchestrateRequest(input_file="data.file.csv")

        # Assert
        assert request.input_file == "data.file.csv"

    def test_valid_filename_alphanumeric_only(self) -> None:
        """Test that alphanumeric-only filenames are accepted."""
        # Arrange & Act
        request = OrchestrateRequest(input_file="data123")

        # Assert
        assert request.input_file == "data123"

    def test_path_separator_forward_slash_rejected(self) -> None:
        """Test that forward slash path separator is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="path/to/file.csv")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)

    def test_path_separator_backslash_rejected(self) -> None:
        """Test that backslash path separator is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="path\\to\\file.csv")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)

    def test_invalid_characters_rejected(self) -> None:
        """Test that invalid characters are rejected."""
        # Test various invalid characters
        invalid_filenames = [
            "file with spaces.csv",
            "file@name.csv",
            "file#name.csv",
            "file$name.csv",
            "file%name.csv",
            "file&name.csv",
            "file*name.csv",
            "file+name.csv",
            "file=name.csv",
            "file[name].csv",
            "file{name}.csv",
            "file|name.csv",
            "file:name.csv",
            "file;name.csv",
            "file'name.csv",
            'file"name.csv',
            "file<name>.csv",
            "file>name.csv",
            "file?name.csv",
            "file!name.csv",
            "file~name.csv",
            "file`name.csv",
        ]

        for invalid_filename in invalid_filenames:
            with pytest.raises(ValidationError) as exc_info:
                OrchestrateRequest(input_file=invalid_filename)

            errors = exc_info.value.errors()
            assert any(
                "alphanumeric" in str(error).lower() or "invalid" in str(error).lower()
                for error in errors
            ), f"Expected validation error for: {invalid_filename}"

    def test_max_length_enforced(self) -> None:
        """Test that maximum filename length (255 chars) is enforced."""
        # Arrange - Create filename exactly at max length
        max_filename = "a" * 255

        # Act
        request = OrchestrateRequest(input_file=max_filename)

        # Assert
        assert len(request.input_file) == 255

    def test_exceeds_max_length_rejected(self) -> None:
        """Test that filenames exceeding max length are rejected."""
        # Arrange - Create filename exceeding max length
        too_long_filename = "a" * 256

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file=too_long_filename)

        errors = exc_info.value.errors()
        # Pydantic will raise error for max_length violation
        assert any("max_length" in str(error).lower() for error in errors)

    def test_empty_filename_rejected(self) -> None:
        """Test that empty filename is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="")

        errors = exc_info.value.errors()
        # Check that validation error occurred (could be from validator or Pydantic required field)
        assert len(errors) > 0
        # Verify the error is related to the input_file field
        assert any("input_file" in str(error) for error in errors)

    def test_whitespace_only_filename_rejected(self) -> None:
        """Test that whitespace-only filename is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="   ")

        errors = exc_info.value.errors()
        # Check that validation error occurred
        assert len(errors) > 0
        # Verify the error is related to the input_file field
        # The validator should catch whitespace-only strings
        assert any("input_file" in str(error) for error in errors)

    def test_filename_starting_with_dot_rejected(self) -> None:
        """Test that filename starting with dot is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file=".hidden_file.csv")

        errors = exc_info.value.errors()
        assert any("start" in str(error).lower() and "dot" in str(error).lower() for error in errors)

    def test_filename_ending_with_dot_rejected(self) -> None:
        """Test that filename ending with dot is rejected."""
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="file.csv.")

        errors = exc_info.value.errors()
        assert any("end" in str(error).lower() and "dot" in str(error).lower() for error in errors)

    def test_absolute_path_rejected(self) -> None:
        """Test that absolute paths are rejected."""
        # Test Unix-style absolute path
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="/etc/passwd")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)

        # Test Windows-style absolute path
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="C:\\Windows\\System32\\file.csv")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)

    def test_relative_path_rejected(self) -> None:
        """Test that relative paths are rejected."""
        # Test Unix-style relative path
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="../etc/passwd")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)

        # Test Windows-style relative path
        with pytest.raises(ValidationError) as exc_info:
            OrchestrateRequest(input_file="..\\..\\etc\\passwd")

        errors = exc_info.value.errors()
        assert any("path separator" in str(error).lower() for error in errors)


class TestInputFileValidationAtAPILevel:
    """Tests for input_file validation at API endpoint level."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = orchestrator_main.app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self) -> dict[str, str]:
        """Create authentication headers."""
        return {"X-API-Key": "test-key"}

    def test_valid_filename_works_at_api_level(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that valid filenames work at API endpoint level."""
        # Arrange
        request_body = {"input_file": "transactions.csv"}

        # Act
        response = client.post("/orchestrate", json=request_body, headers=auth_headers)

        # Assert - Should not return 422 (validation error)
        # May return other status codes (e.g., 404 if file doesn't exist, 500 for other errors)
        assert response.status_code != 422

    def test_invalid_filename_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that invalid filenames return HTTP 422 at API level."""
        # Arrange - Test with path separator
        request_body = {"input_file": "path/to/file.csv"}

        # Act
        response = client.post("/orchestrate", json=request_body, headers=auth_headers)

        # Assert - Should return 422 (validation error)
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "path separator" in error_detail or "validation" in error_detail

    def test_invalid_characters_return_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """Test that filenames with invalid characters return HTTP 422."""
        # Arrange - Test with invalid characters
        request_body = {"input_file": "file with spaces.csv"}

        # Act
        response = client.post("/orchestrate", json=request_body, headers=auth_headers)

        # Assert - Should return 422 (validation error)
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "alphanumeric" in error_detail or "invalid" in error_detail
