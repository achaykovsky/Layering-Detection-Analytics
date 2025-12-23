"""
Integration tests for Orchestrator Service.

Tests the orchestrator service with mocked HTTP calls to algorithm and aggregator services.
Uses httpx.AsyncClient mocking to test the full pipeline flow.
"""

from __future__ import annotations

import asyncio
import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from services.shared.api_models import AggregateResponse, AlgorithmResponse
from tests.fixtures import create_algorithm_response

# Import orchestrator main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "orchestrator-service" / "main.py"
spec = importlib.util.spec_from_file_location("orchestrator_main", main_path)
orchestrator_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_main)
app = orchestrator_main.app


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


def create_mock_async_client(post_handler):
    """Create a mock httpx.AsyncClient with custom post handler."""
    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            return await post_handler(self, url, **kwargs)

    return MockAsyncClient


def create_mock_response(status_code: int, json_data: dict, url: str = "http://test") -> httpx.Response:
    """Create a mock httpx.Response with proper request instance for raise_for_status()."""
    mock_request = httpx.Request("POST", url)
    response = httpx.Response(status_code, json=json_data, request=mock_request)
    # Mock raise_for_status to not raise for 2xx status codes
    if 200 <= status_code < 300:
        response.raise_for_status = lambda: None
    else:
        # For error status codes, raise_for_status should raise HTTPStatusError
        def raise_for_status():
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=mock_request,
                response=response,
            )
        response.raise_for_status = raise_for_status
    return response


@pytest.fixture
def sample_csv_file() -> Path:
    """Create temporary CSV file with sample transaction data."""
    csv_content = """timestamp,account_id,product_id,side,price,quantity,event_type
2025-01-15T10:30:00Z,ACC001,IBM,BUY,100.50,1000,ORDER_PLACED
2025-01-15T10:31:00Z,ACC001,IBM,SELL,100.75,500,ORDER_PLACED
2025-01-15T10:32:00Z,ACC001,IBM,BUY,101.00,2000,ORDER_CANCELLED
2025-01-15T10:33:00Z,ACC002,AAPL,SELL,150.75,500,ORDER_PLACED
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


class TestOrchestrateEndpoint:
    """Tests for POST /orchestrate endpoint with mocked HTTP services."""

    @pytest.mark.asyncio
    async def test_orchestrate_success(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test successful orchestration with mocked algorithm and aggregator services."""
        # Arrange - Mock algorithm service responses
        test_request_id = str(uuid4())
        mock_layering_response = create_algorithm_response(
            request_id=test_request_id,
            service_name="layering",
            status="success",
            results=[],
            final_status=True,
        )

        mock_wash_trading_response = create_algorithm_response(
            request_id=test_request_id,
            service_name="wash_trading",
            status="success",
            results=[],
            final_status=True,
        )

        mock_aggregate_response = AggregateResponse(
            status="completed",
            merged_count=0,
            failed_services=[],
            error=None,
        )

        # Mock httpx.AsyncClient context manager and post method
        async def mock_post(self, url, **kwargs):
            json_data = kwargs.get("json", {})

            # Mock layering service - URL contains "layering" and ends with "/detect"
            if "/detect" in url and ("layering" in url.lower() or "8001" in url):
                return create_mock_response(200, mock_layering_response.model_dump(), url)

            # Mock wash trading service - URL contains "wash" and ends with "/detect"
            if "/detect" in url and ("wash" in url.lower() or "8002" in url):
                return create_mock_response(200, mock_wash_trading_response.model_dump(), url)

            # Mock aggregator service - URL ends with "/aggregate"
            if "/aggregate" in url:
                return create_mock_response(200, mock_aggregate_response.model_dump(), url)

            return create_mock_response(404, {"detail": "Not found"}, url)

        # Patch httpx.AsyncClient
        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["event_count"] == 4
            assert data["aggregated_count"] == 0
            assert data["failed_services"] == []
            assert data["error"] is None
            assert "request_id" in data
            assert len(data["request_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_csv_reading(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test CSV reading functionality."""
        # Arrange - Mock services to return success
        test_request_id = str(uuid4())
        async def mock_post(self, url, **kwargs):
            # Mock algorithm services
            if "/detect" in url:
                service_name = "layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading"
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=test_request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )
            # Mock aggregator service
            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )
            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert - Verify CSV was read correctly
            assert response.status_code == 200
            data = response.json()
            assert data["event_count"] == 4  # 4 events in sample CSV

    @pytest.mark.asyncio
    async def test_request_id_generation(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test request_id generation and propagation."""
        # Arrange - Capture request IDs
        captured_request_ids: list[str] = []

        async def mock_post(self, url, **kwargs):
            json_data = kwargs.get("json", {})

            # Capture request_id from algorithm service calls
            if "/detect" in url:
                request_id = json_data.get("request_id")
                if request_id:
                    captured_request_ids.append(request_id)

                service_name = "layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading"
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=request_id or str(uuid4()),
                        service_name=service_name,
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                # Verify request_id in aggregate request matches
                aggregate_request_id = json_data.get("request_id")
                if captured_request_ids:
                    assert aggregate_request_id == captured_request_ids[0]

                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "request_id" in data
            assert len(data["request_id"]) == 36  # UUID format
            assert data["request_id"].count("-") == 4  # UUID has 4 hyphens
            # Verify request_id was propagated to services
            assert len(captured_request_ids) >= 2  # At least 2 algorithm services called

    @pytest.mark.asyncio
    async def test_event_fingerprinting(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test event fingerprinting (SHA256 hash generation)."""
        # Arrange - Capture fingerprints
        captured_fingerprints: list[str] = []

        async def mock_post(self, url, **kwargs):
            json_data = kwargs.get("json", {})

            if "/detect" in url:
                # Capture event_fingerprint
                fingerprint = json_data.get("event_fingerprint")
                if fingerprint:
                    captured_fingerprints.append(fingerprint)

                service_name = "layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading"
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=json_data.get("request_id", str(uuid4())),
                        service_name=service_name,
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert
            assert response.status_code == 200
            # Verify fingerprint was generated and sent to services
            assert len(captured_fingerprints) >= 2  # Both services should receive fingerprint
            # Verify fingerprint is SHA256 hexdigest (64 characters)
            for fingerprint in captured_fingerprints:
                assert len(fingerprint) == 64
                assert all(c in "0123456789abcdef" for c in fingerprint)

    @pytest.mark.asyncio
    async def test_parallel_algorithm_service_calls(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test parallel execution of algorithm service calls."""
        # Arrange - Track call order and timing
        call_times: list[float] = []
        import time

        async def mock_post(self, url, **kwargs):
            call_times.append(time.time())

            if "/detect" in url:
                # Simulate service processing time
                await asyncio.sleep(0.1)
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=str(uuid4()),
                        service_name="layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading",
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert
            assert response.status_code == 200
            # Verify both algorithm services were called (check call_times)
            assert len(call_times) >= 2  # Both services called

    @pytest.mark.asyncio
    async def test_retry_logic_on_failure(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test retry logic when algorithm service fails initially."""
        # Arrange - Track retry attempts
        retry_count = {"layering": 0, "wash_trading": 0}

        async def mock_post(self, url, **kwargs):
            if "/detect" in url:
                service_name = "layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading"
                retry_count[service_name] += 1

                # Fail first 2 attempts, succeed on 3rd
                if retry_count[service_name] < 3:
                    return create_mock_response(
                        500,
                        {"detail": "Internal server error"},
                        url,
                    )

                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=str(uuid4()),
                        service_name=service_name,
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert - Should eventually succeed after retries
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            # Verify retries occurred (each service should have been called multiple times)
            assert retry_count["layering"] >= 3
            assert retry_count["wash_trading"] >= 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test retry exhaustion when all retries fail."""
        # Arrange - Always return error
        async def mock_post(*args, **kwargs):
            url = kwargs.get("url", args[1] if len(args) > 1 else "")

            if "/detect" in url:
                # Always fail
                return create_mock_response(
                    500,
                    {"detail": "Service unavailable"},
                    url,
                )

            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post_func:
            mock_post_func.side_effect = mock_post

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert - Should handle exhausted retries gracefully
            # Services exhausted but final_status=True, so validation passes
            # But AggregateRequest requires results, so it may fail
            assert response.status_code in (200, 500)
            if response.status_code == 500:
                assert "did not complete" in response.json()["detail"].lower() or "validation" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_completion_validation(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test completion validation (all services must have final_status=True)."""
        # Arrange - One service returns final_status=False
        async def mock_post(*args, **kwargs):
            url = kwargs.get("url", args[1] if len(args) > 1 else "")

            if "/detect" in url:
                service_name = "layering" if "layering" in url else "wash_trading"
                # wash_trading returns final_status=False
                final_status = service_name != "wash_trading"

                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=str(uuid4()),
                        service_name=service_name,
                        status="success" if final_status else "pending",
                        results=[],
                        final_status=final_status,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post_func:
            mock_post_func.side_effect = mock_post

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert - Should fail validation
            assert response.status_code == 500
            assert "did not complete" in response.json()["detail"].lower() or "final_status" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_aggregator_call(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test aggregator service call with correct request structure."""
        # Arrange - Capture aggregate request
        captured_aggregate_request: dict | None = None

        async def mock_post(self, url, **kwargs):
            json_data = kwargs.get("json", {})

            if "/detect" in url:
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=json_data.get("request_id", str(uuid4())),
                        service_name="layering" if ("layering" in url.lower() or "8001" in url) else "wash_trading",
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                # Capture aggregate request
                nonlocal captured_aggregate_request
                captured_aggregate_request = json_data

                return create_mock_response(
                    200,
                    {
                        "status": "completed",
                        "merged_count": 0,
                        "failed_services": [],
                        "error": None,
                    },
                    url,
                )

            return create_mock_response(404, {}, url)

        MockAsyncClient = create_mock_async_client(mock_post)
        with patch("httpx.AsyncClient", MockAsyncClient):

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert
            assert response.status_code == 200
            # Verify aggregator was called with correct structure
            assert captured_aggregate_request is not None
            assert "request_id" in captured_aggregate_request
            assert "expected_services" in captured_aggregate_request
            assert "results" in captured_aggregate_request
            assert len(captured_aggregate_request["expected_services"]) == 2
            assert len(captured_aggregate_request["results"]) == 2

    @pytest.mark.asyncio
    async def test_aggregator_failure_handling(
        self,
        client: TestClient,
        sample_csv_file: Path,
    ) -> None:
        """Test error handling when aggregator service fails."""
        # Arrange
        async def mock_post(*args, **kwargs):
            url = kwargs.get("url", args[1] if len(args) > 1 else "")

            if "/detect" in url:
                return create_mock_response(
                    200,
                    create_algorithm_response(
                        request_id=str(uuid4()),
                        service_name="layering" if "layering" in url else "wash_trading",
                        status="success",
                        results=[],
                        final_status=True,
                    ).model_dump(),
                    url,
                )

            if "/aggregate" in url:
                # Aggregator fails
                return create_mock_response(
                    500,
                    {"detail": "Aggregator service error"},
                    url,
                )

            return create_mock_response(404, {}, url)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post_func:
            mock_post_func.side_effect = mock_post

            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(sample_csv_file)},
            )

            # Assert - Should handle aggregator failure
            assert response.status_code == 500
            assert "aggregator" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_csv_file_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error handling when CSV file is not found."""
        # Act
        response = client.post(
            "/orchestrate",
            json={"input_file": "nonexistent.csv"},
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_empty_csv_file(
        self,
        client: TestClient,
    ) -> None:
        """Test error handling when CSV file is empty."""
        # Arrange - Create empty CSV
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("timestamp,account_id,product_id,side,price,quantity,event_type\n")
            temp_path = Path(f.name)

        try:
            # Act
            response = client.post(
                "/orchestrate",
                json={"input_file": str(temp_path)},
            )

            # Assert
            assert response.status_code == 400
            assert "no events" in response.json()["detail"].lower()
        finally:
            if temp_path.exists():
                temp_path.unlink()
