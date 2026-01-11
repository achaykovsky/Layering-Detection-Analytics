"""
Unit tests for error message sanitization.

Tests that error messages don't expose file paths or sensitive information to clients.
Full error details should be logged server-side only.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.shared.error_sanitization import (
    extract_file_paths,
    log_error_with_context,
    sanitize_error_message,
    sanitize_path_in_message,
)


class TestSanitizeErrorMessage:
    """Test sanitize_error_message function."""

    def test_sanitize_error_with_generic_message(self) -> None:
        """Test that generic message is returned regardless of error content."""
        error = FileNotFoundError("/app/input/secret.csv")
        result = sanitize_error_message(error, "Input file not found")
        assert result == "Input file not found"

    def test_sanitize_error_with_path_in_exception(self) -> None:
        """Test that file paths in exceptions are not exposed."""
        error = FileNotFoundError("File not found: /app/input/../../../etc/passwd")
        result = sanitize_error_message(error, "Input file not found")
        assert result == "Input file not found"
        assert "/app/input" not in result
        assert "etc/passwd" not in result

    def test_sanitize_error_string_with_path(self) -> None:
        """Test that file paths in error strings are not exposed."""
        error = "Failed to read /app/input/data.csv"
        result = sanitize_error_message(error, "Failed to read input file")
        assert result == "Failed to read input file"
        assert "/app/input" not in result

    def test_sanitize_error_with_internal_details(self) -> None:
        """Test that internal error details are not exposed."""
        error = ValueError("Invalid data in /app/input/file.csv: column 'secret' not found")
        result = sanitize_error_message(error, "Invalid input data")
        assert result == "Invalid input data"
        assert "secret" not in result
        assert "/app/input" not in result

    def test_sanitize_error_preserves_generic_message(self) -> None:
        """Test that generic message is always used, even if error is already generic."""
        error = ValueError("Invalid input")
        result = sanitize_error_message(error, "Invalid input data")
        assert result == "Invalid input data"


class TestExtractFilePaths:
    """Test extract_file_paths function."""

    def test_extract_single_unix_path(self) -> None:
        """Test extraction of single Unix path."""
        text = "File not found: /app/input/data.csv"
        paths = extract_file_paths(text)
        assert paths == ["/app/input/data.csv"]

    def test_extract_multiple_paths(self) -> None:
        """Test extraction of multiple paths."""
        text = "Failed to read /app/input/file.csv and /app/output/result.csv"
        paths = extract_file_paths(text)
        assert "/app/input/file.csv" in paths
        assert "/app/output/result.csv" in paths

    def test_extract_windows_path(self) -> None:
        """Test extraction of Windows path."""
        text = "File not found: C:\\app\\input\\data.csv"
        paths = extract_file_paths(text)
        assert len(paths) > 0
        assert "C:" in paths[0] or "\\" in paths[0]

    def test_extract_no_paths(self) -> None:
        """Test that no paths are extracted from text without paths."""
        text = "Invalid input data"
        paths = extract_file_paths(text)
        assert paths == []

    def test_extract_paths_with_relative_paths(self) -> None:
        """Test that relative paths are not extracted (only absolute)."""
        text = "File not found: ./input/data.csv"
        paths = extract_file_paths(text)
        # Relative paths starting with ./ should not match
        assert "./input/data.csv" not in paths


class TestSanitizePathInMessage:
    """Test sanitize_path_in_message function."""

    def test_sanitize_single_path(self) -> None:
        """Test that single path is replaced with placeholder."""
        message = "File not found: /app/input/data.csv"
        result = sanitize_path_in_message(message)
        assert result == "File not found: [file path]"
        assert "/app/input/data.csv" not in result

    def test_sanitize_multiple_paths(self) -> None:
        """Test that multiple paths are replaced with placeholders."""
        message = "Failed to read /app/input/file.csv and /app/output/result.csv"
        result = sanitize_path_in_message(message)
        assert "/app/input/file.csv" not in result
        assert "/app/output/result.csv" not in result
        assert "[file path]" in result

    def test_sanitize_no_paths(self) -> None:
        """Test that message without paths is unchanged."""
        message = "Invalid input data"
        result = sanitize_path_in_message(message)
        assert result == message

    def test_sanitize_windows_path(self) -> None:
        """Test that Windows paths are sanitized."""
        message = "File not found: C:\\app\\input\\data.csv"
        result = sanitize_path_in_message(message)
        assert "C:\\app\\input\\data.csv" not in result
        assert "[file path]" in result


class TestLogErrorWithContext:
    """Test log_error_with_context function."""

    def test_log_error_with_request_id(self) -> None:
        """Test that error is logged with request ID."""
        logger = MagicMock()
        error = FileNotFoundError("/app/input/secret.csv")

        log_error_with_context(
            logger,
            "Input file not found",
            error,
            request_id="req-123",
            path="/app/input/secret.csv",
        )

        logger.error.assert_called_once()
        call_args = logger.error.call_args
        assert "req-123" in str(call_args)
        assert "Input file not found" in str(call_args)
        assert "/app/input/secret.csv" in str(call_args)

    def test_log_error_without_request_id(self) -> None:
        """Test that error is logged without request ID."""
        logger = MagicMock()
        error = ValueError("Invalid data")

        log_error_with_context(
            logger,
            "Invalid input data",
            error,
            path="/app/input/file.csv",
        )

        logger.error.assert_called_once()
        call_args = logger.error.call_args
        assert "Invalid input data" in str(call_args)
        assert "/app/input/file.csv" in str(call_args)

    def test_log_error_with_exc_info(self) -> None:
        """Test that exc_info is set for Exception objects."""
        logger = MagicMock()
        error = FileNotFoundError("/app/input/secret.csv")

        log_error_with_context(
            logger,
            "Input file not found",
            error,
        )

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args[1]
        assert call_kwargs.get("exc_info") is True

    def test_log_error_without_exc_info_for_strings(self) -> None:
        """Test that exc_info is not set for string errors."""
        logger = MagicMock()
        error = "Failed to read file"

        log_error_with_context(
            logger,
            "Failed to read input file",
            error,
        )

        logger.error.assert_called_once()
        call_kwargs = logger.error.call_args[1]
        assert call_kwargs.get("exc_info") is False or "exc_info" not in call_kwargs


class TestOrchestratorReaderErrorSanitization:
    """Test error sanitization in orchestrator-service/reader.py."""

    def test_file_not_found_error_sanitized(self) -> None:
        """Test that FileNotFoundError doesn't expose file path."""
        import importlib.util
        from pathlib import Path

        # Import reader module (handles hyphenated directory name)
        project_root = Path(__file__).parent.parent.parent
        reader_path = project_root / "services" / "orchestrator-service" / "reader.py"
        spec = importlib.util.spec_from_file_location("orchestrator_reader", reader_path)
        orchestrator_reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(orchestrator_reader)
        read_input_csv = orchestrator_reader.read_input_csv

        with pytest.raises(FileNotFoundError) as exc_info:
            read_input_csv("/app/input/nonexistent.csv", request_id="test-123")

        error_msg = str(exc_info.value)
        assert error_msg == "Input file not found"
        assert "/app/input/nonexistent.csv" not in error_msg

    def test_invalid_path_error_sanitized(self) -> None:
        """Test that invalid path error doesn't expose file path."""
        import importlib.util
        from pathlib import Path

        # Import reader module
        project_root = Path(__file__).parent.parent.parent
        reader_path = project_root / "services" / "orchestrator-service" / "reader.py"
        spec = importlib.util.spec_from_file_location("orchestrator_reader", reader_path)
        orchestrator_reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(orchestrator_reader)
        read_input_csv = orchestrator_reader.read_input_csv

        # Create a directory path (not a file)
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=False):
                with pytest.raises(ValueError) as exc_info:
                    read_input_csv("/app/input/dir", request_id="test-123")

                error_msg = str(exc_info.value)
                assert error_msg == "Invalid file path"
                assert "/app/input/dir" not in error_msg

    def test_io_error_sanitized(self) -> None:
        """Test that IOError doesn't expose file path."""
        # Test the sanitization function directly with IOError
        error = IOError("Permission denied: /app/input/secret.csv")
        sanitized = sanitize_error_message(error, "Failed to read input file")
        assert sanitized == "Failed to read input file"
        assert "/app/input/secret.csv" not in sanitized
        assert "Permission denied" not in sanitized


class TestOrchestratorMainErrorSanitization:
    """Test error sanitization in orchestrator-service/main.py."""

    def test_unexpected_error_sanitized(self) -> None:
        """Test that unexpected errors don't expose internal details."""
        import importlib.util
        from fastapi.testclient import TestClient
        from pathlib import Path

        # Import main module (handles hyphenated directory name)
        project_root = Path(__file__).parent.parent.parent
        main_path = project_root / "services" / "orchestrator-service" / "main.py"
        spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
        orchestrator_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(orchestrator_main)
        app = orchestrator_main.app

        client = TestClient(app)

        # Mock an error that would expose internal details
        # Patch the read_input_csv function in the imported module
        with patch.object(
            orchestrator_main,
            "read_input_csv",
            side_effect=Exception("Internal error: /app/input/secret.csv"),
        ):
            response = client.post(
                "/orchestrate",
                json={"input_file": "test.csv"},
                headers={"X-API-Key": "dev-key-change-in-production"},
            )

            assert response.status_code == 500
            error_detail = response.json()["detail"]
            assert error_detail == "An unexpected error occurred"
            assert "/app/input/secret.csv" not in error_detail
            assert "Internal error" not in error_detail


class TestAggregatorWriterErrorSanitization:
    """Test error sanitization in aggregator-service/writer.py."""

    def test_write_error_sanitized(self) -> None:
        """Test that write errors don't expose file paths."""
        import importlib.util
        from datetime import datetime
        from pathlib import Path

        from layering_detection.models import SuspiciousSequence

        # Import writer module (handles hyphenated directory name)
        project_root = Path(__file__).parent.parent.parent
        writer_path = project_root / "services" / "aggregator-service" / "writer.py"
        spec = importlib.util.spec_from_file_location("aggregator_writer", writer_path)
        aggregator_writer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aggregator_writer)
        write_output_files = aggregator_writer.write_output_files

        sequences = [
            SuspiciousSequence(
                account_id="ACC001",
                product_id="IBM",
                start_timestamp=datetime(2025, 1, 15, 10, 0),
                end_timestamp=datetime(2025, 1, 15, 11, 0),
                total_buy_qty=5000,
                total_sell_qty=0,
                detection_type="LAYERING",
            ),
        ]

        with patch("pathlib.Path.mkdir"):
            with patch(
                "layering_detection.utils.transaction_io.write_suspicious_accounts",
                side_effect=IOError("Permission denied: /app/output/secret.csv"),
            ):
                with pytest.raises(IOError) as exc_info:
                    write_output_files(
                        sequences,
                        "/app/output",
                        "/app/logs",
                        request_id="test-123",
                    )

                error_msg = str(exc_info.value)
                assert error_msg == "Failed to write output files"
                assert "/app/output/secret.csv" not in error_msg
                assert "Permission denied" not in error_msg


class TestAggregatorMainErrorSanitization:
    """Test error sanitization in aggregator-service/main.py."""

    def test_write_error_in_response_sanitized(self) -> None:
        """Test that write errors in responses don't expose file paths."""
        import importlib.util
        from pathlib import Path
        from uuid import uuid4

        from fastapi.testclient import TestClient

        from services.shared.api_models import AggregateRequest, AlgorithmResponse

        # Import main module (handles hyphenated directory name)
        project_root = Path(__file__).parent.parent.parent
        main_path = project_root / "services" / "aggregator-service" / "main.py"
        spec = importlib.util.spec_from_file_location("aggregator_main", main_path)
        aggregator_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aggregator_main)
        app = aggregator_main.app

        client = TestClient(app)

        # Create a request that will trigger a write error
        request_id = str(uuid4())
        request = AggregateRequest(
            request_id=request_id,
            expected_services=["layering", "wash_trading"],
            results=[
                AlgorithmResponse(
                    request_id=request_id,
                    service_name="layering",
                    status="success",
                    results=[],
                ),
                AlgorithmResponse(
                    request_id=request_id,
                    service_name="wash_trading",
                    status="success",
                    results=[],
                ),
            ],
        )

        # Patch the write_output_files_from_dtos function in the imported module
        with patch.object(
            aggregator_main,
            "write_output_files_from_dtos",
            side_effect=IOError("Permission denied: /app/output/secret.csv"),
        ):
            response = client.post(
                "/aggregate",
                json=request.model_dump(),
                headers={"X-API-Key": "dev-key-change-in-production"},
            )

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["status"] == "validation_failed"
            error_message = response_data.get("error", "")
            assert error_message == "Failed to write output files"
            assert "/app/output/secret.csv" not in error_message
            assert "Permission denied" not in error_message

