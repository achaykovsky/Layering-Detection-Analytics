"""
Unit tests for Aggregator Service completion validation logic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

from services.shared.api_models import AlgorithmResponse
from tests.fixtures import create_algorithm_response

# Import validation module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
validation_path = project_root / "services" / "aggregator-service" / "validation.py"
spec = importlib.util.spec_from_file_location("aggregator_validation", validation_path)
aggregator_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_validation)
validate_completeness = aggregator_validation.validate_completeness


class TestValidateCompleteness:
    """Tests for validate_completeness function."""

    def test_validation_success_all_services_complete(self) -> None:
        """Test validation passes when all expected services are present and complete."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=True,
            ),
            create_algorithm_response(
                service_name="wash_trading",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        # Should not raise exception
        validate_completeness(["layering", "wash_trading"], results)

    def test_validation_fails_missing_service(self) -> None:
        """Test validation fails when expected service is missing."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], results)

        error_message = str(exc_info.value)
        assert "Missing services" in error_message
        assert "wash_trading" in error_message
        assert "Expected" in error_message
        assert "Got" in error_message

    def test_validation_fails_multiple_missing_services(self) -> None:
        """Test validation fails when multiple expected services are missing."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading", "another_service"], results)

        error_message = str(exc_info.value)
        assert "Missing services" in error_message
        assert "wash_trading" in error_message
        assert "another_service" in error_message

    def test_validation_fails_incomplete_service(self) -> None:
        """Test validation fails when service has final_status=False."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=False,  # Still retrying
            ),
            create_algorithm_response(
                service_name="wash_trading",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], results)

        error_message = str(exc_info.value)
        assert "Services not completed" in error_message
        assert "layering" in error_message
        assert "final_status=True" in error_message

    def test_validation_fails_multiple_incomplete_services(self) -> None:
        """Test validation fails when multiple services have final_status=False."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=False,
            ),
            create_algorithm_response(
                service_name="wash_trading",
                status="success",
                results=[],
                final_status=False,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], results)

        error_message = str(exc_info.value)
        assert "Services not completed" in error_message
        assert "layering" in error_message
        assert "wash_trading" in error_message

    def test_validation_fails_both_missing_and_incomplete(self) -> None:
        """Test validation fails when both missing and incomplete services exist."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=False,  # Incomplete
            ),
            # wash_trading is missing
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], results)

        # Should report missing service first (checked before incomplete)
        error_message = str(exc_info.value)
        assert "Missing services" in error_message
        assert "wash_trading" in error_message

    def test_validation_success_with_failed_service_but_final_status_true(self) -> None:
        """Test validation passes when service failed but has final_status=True (retries exhausted)."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="failure",
                results=None,
                error="Service error",
                final_status=True,  # Retries exhausted, considered complete
            ),
            create_algorithm_response(
                service_name="wash_trading",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        # Should not raise exception - final_status=True means service completed (even if failed)
        validate_completeness(["layering", "wash_trading"], results)

    def test_validation_empty_results(self) -> None:
        """Test validation fails when results list is empty."""
        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], [])

        error_message = str(exc_info.value)
        assert "Missing services" in error_message
        assert "layering" in error_message
        assert "wash_trading" in error_message

    def test_validation_extra_services_ignored(self) -> None:
        """Test validation passes when all expected services are present (even if duplicates exist)."""
        # Note: AlgorithmResponse validates service_name, so we can't test with invalid service names
        # Instead, we test that validation passes when all expected services are present
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=True,
            ),
            create_algorithm_response(
                service_name="wash_trading",
                status="success",
                results=[],
                final_status=True,
            ),
        ]

        # Should not raise exception - all expected services are present
        validate_completeness(["layering", "wash_trading"], results)

    def test_validation_error_message_format(self) -> None:
        """Test error message format includes all necessary information."""
        results = [
            create_algorithm_response(
                service_name="layering",
                status="success",
                results=[],
                final_status=False,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_completeness(["layering", "wash_trading"], results)

        error_message = str(exc_info.value)
        # Check error message contains key information
        assert "Missing services" in error_message
        assert "wash_trading" in error_message
        # Should also check incomplete after missing is resolved
        # But since missing is checked first, we get missing error

