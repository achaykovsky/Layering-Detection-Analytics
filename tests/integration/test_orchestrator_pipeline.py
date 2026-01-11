"""
Integration tests for Orchestrator Service pipeline endpoint.

Tests the full pipeline flow: read CSV, call algorithms, validate, aggregate.
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from services.shared.api_models import AggregateRequest, AggregateResponse, AlgorithmResponse

# Import orchestrator main module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "orchestrator-service" / "main.py"
spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
orchestrator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_main)
app = orchestrator_main.app


class TestOrchestratePipeline:
    """Tests for POST /orchestrate endpoint."""

    @pytest.fixture
    def input_dir(self, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create temporary input directory and set INPUT_DIR environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_dir_path = Path(tmpdir) / "input"
            input_dir_path.mkdir(parents=True)
            
            # Set INPUT_DIR environment variable
            monkeypatch.setenv("INPUT_DIR", str(input_dir_path))
            
            yield input_dir_path

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_csv_file(self, input_dir: Path) -> Path:
        """Create temporary CSV file with sample transaction data within INPUT_DIR."""
        csv_content = """timestamp,account_id,product_id,side,price,quantity,event_type
2025-01-15T10:30:00Z,ACC001,IBM,BUY,100.50,1000,ORDER_PLACED
2025-01-15T10:31:00Z,ACC002,AAPL,SELL,150.75,500,ORDER_PLACED
"""
        test_file = input_dir / "transactions.csv"
        test_file.write_text(csv_content)
        return test_file

    @pytest.mark.asyncio
    async def test_pipeline_success(self, client: TestClient, sample_csv_file: Path) -> None:
        """Test successful pipeline execution."""
        request_id = str(uuid4())

        # Mock algorithm service responses
        mock_layering_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        mock_wash_trading_response = AlgorithmResponse(
            request_id=request_id,
            service_name="wash_trading",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        # Mock aggregator response
        mock_aggregate_response = AggregateResponse(
            status="completed",
            merged_count=5,
            failed_services=[],
            error=None,
        )

        # Mock call_all_algorithm_services
        async def mock_call_all_services(
            request_id: str,
            event_fingerprint: str,
            events: list,
            **kwargs,
        ) -> dict:
            return {
                "layering": {
                    "status": "success",
                    "final_status": True,
                    "result": mock_layering_response,
                    "error": None,
                    "retry_count": 0,
                },
                "wash_trading": {
                    "status": "success",
                    "final_status": True,
                    "result": mock_wash_trading_response,
                    "error": None,
                    "retry_count": 0,
                },
            }

        # Mock call_aggregator_service
        async def mock_call_aggregator(request: AggregateRequest, **kwargs) -> AggregateResponse:
            return mock_aggregate_response

        with patch.object(
            orchestrator_main, "call_all_algorithm_services", new_callable=AsyncMock
        ) as mock_call_all, patch.object(
            orchestrator_main, "call_aggregator_service", new_callable=AsyncMock
        ) as mock_call_agg:
            mock_call_all.side_effect = mock_call_all_services
            mock_call_agg.side_effect = mock_call_aggregator

            # Call endpoint
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["event_count"] == 2
            assert data["aggregated_count"] == 5
            assert data["failed_services"] == []
            assert data["error"] is None
            assert "request_id" in data

            # Verify services were called
            assert mock_call_all.call_count == 1
            assert mock_call_agg.call_count == 1

    @pytest.mark.asyncio
    async def test_pipeline_file_not_found(self, client: TestClient) -> None:
        """Test pipeline with non-existent input file."""
        response = client.post(
            "/orchestrate",
            json={"input_file": "nonexistent.csv"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_empty_csv(self, client: TestClient, input_dir: Path) -> None:
        """Test pipeline with empty CSV file."""
        # Create empty CSV file within INPUT_DIR
        empty_file = input_dir / "empty.csv"
        empty_file.write_text("timestamp,account_id,product_id,side,price,quantity,event_type\n")

        response = client.post(
            "/orchestrate",
            json={"input_file": "empty.csv"},
        )

        assert response.status_code == 400
        assert "no events" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_algorithm_service_failure(self, client: TestClient, sample_csv_file: Path, input_dir: Path) -> None:
        """Test pipeline when algorithm service fails."""
        request_id = str(uuid4())

        # Mock algorithm service failure
        async def mock_call_all_services(
            request_id: str,
            event_fingerprint: str,
            events: list,
            **kwargs,
        ) -> dict:
            return {
                "layering": {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": "All retries exhausted",
                    "retry_count": 3,
                },
                "wash_trading": {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": "All retries exhausted",
                    "retry_count": 3,
                },
            }

        with patch.object(
            orchestrator_main, "call_all_algorithm_services", new_callable=AsyncMock
        ) as mock_call_all:
            mock_call_all.side_effect = mock_call_all_services

            # Call endpoint with relative path
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
            )

            # Should fail validation (services exhausted but final_status=True, so validation passes)
            # But AggregateRequest requires at least 1 result, so it will fail when creating request
            assert response.status_code == 500
            detail = response.json()["detail"].lower()
            assert "did not complete" in detail or "validation error" in detail or "aggregator" in detail

    @pytest.mark.asyncio
    async def test_pipeline_aggregator_failure(self, client: TestClient, sample_csv_file: Path, input_dir: Path) -> None:
        """Test pipeline when aggregator service fails."""
        request_id = str(uuid4())

        # Mock successful algorithm services
        mock_layering_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_call_all_services(
            request_id: str,
            event_fingerprint: str,
            events: list,
            **kwargs,
        ) -> dict:
            return {
                "layering": {
                    "status": "success",
                    "final_status": True,
                    "result": mock_layering_response,
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

        # Mock aggregator failure
        async def mock_call_aggregator(request: AggregateRequest, **kwargs) -> AggregateResponse:
            raise ConnectionError("Failed to connect to aggregator")

        with patch.object(
            orchestrator_main, "call_all_algorithm_services", new_callable=AsyncMock
        ) as mock_call_all, patch.object(
            orchestrator_main, "call_aggregator_service", new_callable=AsyncMock
        ) as mock_call_agg:
            mock_call_all.side_effect = mock_call_all_services
            mock_call_agg.side_effect = mock_call_aggregator

            # Call endpoint
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
            )

            assert response.status_code == 500
            assert "aggregator" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_validation_failed(self, client: TestClient, sample_csv_file: Path) -> None:
        """Test pipeline when aggregator validation fails."""
        request_id = str(uuid4())

        # Mock successful algorithm services
        mock_layering_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_call_all_services(
            request_id: str,
            event_fingerprint: str,
            events: list,
            **kwargs,
        ) -> dict:
            return {
                "layering": {
                    "status": "success",
                    "final_status": True,
                    "result": mock_layering_response,
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

        # Mock aggregator validation failure
        mock_aggregate_response = AggregateResponse(
            status="validation_failed",
            merged_count=0,
            failed_services=[],
            error="Missing services: ['wash_trading']",
        )

        async def mock_call_aggregator(request: AggregateRequest, **kwargs) -> AggregateResponse:
            return mock_aggregate_response

        with patch.object(
            orchestrator_main, "call_all_algorithm_services", new_callable=AsyncMock
        ) as mock_call_all, patch.object(
            orchestrator_main, "call_aggregator_service", new_callable=AsyncMock
        ) as mock_call_agg:
            mock_call_all.side_effect = mock_call_all_services
            mock_call_agg.side_effect = mock_call_aggregator

            # Call endpoint
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
            )

            assert response.status_code == 500
            assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_request_id_preserved(self, client: TestClient, sample_csv_file: Path) -> None:
        """Test that request_id is preserved throughout pipeline."""
        # Capture request_id from service calls
        captured_request_ids: list[str] = []

        async def mock_call_all_services(
            request_id: str,
            event_fingerprint: str,
            events: list,
            **kwargs,
        ) -> dict:
            # Capture request_id from call
            captured_request_ids.append(request_id)
            return {
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

        mock_aggregate_response = AggregateResponse(
            status="completed",
            merged_count=0,
            failed_services=[],
            error=None,
        )

        async def mock_call_aggregator(request: AggregateRequest, **kwargs) -> AggregateResponse:
            # Verify request_id in aggregate request matches captured request_id
            if captured_request_ids:
                assert request.request_id == captured_request_ids[0]
            return mock_aggregate_response

        with patch.object(
            orchestrator_main, "call_all_algorithm_services", new_callable=AsyncMock
        ) as mock_call_all, patch.object(
            orchestrator_main, "call_aggregator_service", new_callable=AsyncMock
        ) as mock_call_agg:
            mock_call_all.side_effect = mock_call_all_services
            mock_call_agg.side_effect = mock_call_aggregator

            # Call endpoint
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "request_id" in data
            # Verify request_id matches captured request_id from service calls
            assert len(captured_request_ids) > 0
            assert data["request_id"] == captured_request_ids[0]

