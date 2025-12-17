"""
Unit tests for Orchestrator Service completion validation logic.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest

from services.shared.api_models import AlgorithmResponse

# Import validation module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
validation_path = project_root / "services" / "orchestrator-service" / "validation.py"
spec = importlib.util.spec_from_file_location("orchestrator_validation", validation_path)
orchestrator_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_validation)
validate_all_completed = orchestrator_validation.validate_all_completed


class TestValidateAllCompleted:
    """Tests for validate_all_completed function."""

    def test_validation_success_all_services_complete(self) -> None:
        """Test validation passes when all expected services are complete."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
            "wash_trading": {
                "status": "exhausted",
                "final_status": True,
                "result": None,
                "error": "Service error",
                "retry_count": 3,
            },
        }

        # Should not raise exception
        validate_all_completed(service_status, ["layering", "wash_trading"])

    def test_validation_fails_missing_service(self) -> None:
        """Test validation fails when expected service is missing."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
            # wash_trading is missing
        }

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering", "wash_trading"])

        error_message = str(exc_info.value)
        assert "Services did not complete" in error_message
        assert "wash_trading" in error_message
        assert "final_status=True" in error_message

    def test_validation_fails_incomplete_service(self) -> None:
        """Test validation fails when service has final_status=False."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": False,  # Incomplete
                "result": None,
                "error": None,
                "retry_count": 0,
            },
            "wash_trading": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="wash_trading",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
        }

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering", "wash_trading"])

        error_message = str(exc_info.value)
        assert "Services did not complete" in error_message
        assert "layering" in error_message
        assert "final_status=True" in error_message

    def test_validation_fails_multiple_incomplete_services(self) -> None:
        """Test validation fails when multiple services are incomplete."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": False,  # Incomplete
                "result": None,
                "error": None,
                "retry_count": 0,
            },
            "wash_trading": {
                "status": "exhausted",
                "final_status": False,  # Incomplete
                "result": None,
                "error": "Service error",
                "retry_count": 3,
            },
        }

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering", "wash_trading"])

        error_message = str(exc_info.value)
        assert "Services did not complete" in error_message
        assert "layering" in error_message
        assert "wash_trading" in error_message

    def test_validation_fails_missing_final_status_key(self) -> None:
        """Test validation fails when final_status key is missing."""
        service_status = {
            "layering": {
                "status": "success",
                # final_status key missing
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "retry_count": 0,
            },
        }

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering"])

        error_message = str(exc_info.value)
        assert "Services did not complete" in error_message
        assert "layering" in error_message

    def test_validation_success_with_exhausted_service(self) -> None:
        """Test validation passes when service exhausted retries but has final_status=True."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
            "wash_trading": {
                "status": "exhausted",
                "final_status": True,  # Retries exhausted, but final_status=True
                "result": None,
                "error": "All retries exhausted",
                "retry_count": 3,
            },
        }

        # Should not raise exception - exhausted services with final_status=True are considered complete
        validate_all_completed(service_status, ["layering", "wash_trading"])

    def test_validation_empty_service_status(self) -> None:
        """Test validation fails when service_status is empty."""
        service_status = {}

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering", "wash_trading"])

        error_message = str(exc_info.value)
        assert "Services did not complete" in error_message
        assert "layering" in error_message
        assert "wash_trading" in error_message

    def test_validation_with_request_id_logging(self) -> None:
        """Test validation with request_id for logging."""
        request_id = str(uuid4())
        service_status = {
            "layering": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=request_id,
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
            "wash_trading": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=request_id,
                    service_name="wash_trading",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
        }

        # Should not raise exception
        validate_all_completed(service_status, ["layering", "wash_trading"], request_id=request_id)

    def test_validation_error_message_format(self) -> None:
        """Test error message format includes all necessary information."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": False,  # Incomplete
                "result": None,
                "error": None,
                "retry_count": 0,
            },
        }

        with pytest.raises(RuntimeError) as exc_info:
            validate_all_completed(service_status, ["layering", "wash_trading"])

        error_message = str(exc_info.value)
        # Check error message contains key information
        assert "Services did not complete" in error_message
        assert "layering" in error_message or "wash_trading" in error_message
        assert "final_status=True" in error_message

    def test_validation_single_service(self) -> None:
        """Test validation with single expected service."""
        service_status = {
            "layering": {
                "status": "success",
                "final_status": True,
                "result": AlgorithmResponse(
                    request_id=str(uuid4()),
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                "error": None,
                "retry_count": 0,
            },
        }

        # Should not raise exception
        validate_all_completed(service_status, ["layering"])

