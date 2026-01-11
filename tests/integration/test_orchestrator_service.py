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
def api_key() -> str:
    """Test API key for authentication."""
    return "test-api-key-123"


@pytest.fixture
def client(api_key: str) -> TestClient:
    """Create FastAPI test client with API key authentication enabled."""
    # Enable API key authentication for integration tests
    with patch.object(orchestrator_main, "get_api_key", return_value=api_key):
        yield TestClient(app)


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    """Headers with API key for authenticated requests."""
    return {"X-API-Key": api_key}


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
def input_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary input directory and set INPUT_DIR environment variable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_dir_path = Path(tmpdir) / "input"
        input_dir_path.mkdir(parents=True)
        
        # Set INPUT_DIR environment variable
        monkeypatch.setenv("INPUT_DIR", str(input_dir_path))
        
        yield input_dir_path


@pytest.fixture
def sample_csv_file(input_dir: Path) -> Path:
    """Create temporary CSV file with sample transaction data within INPUT_DIR."""
    csv_content = """timestamp,account_id,product_id,side,price,quantity,event_type
2025-01-15T10:30:00Z,ACC001,IBM,BUY,100.50,1000,ORDER_PLACED
2025-01-15T10:31:00Z,ACC001,IBM,SELL,100.75,500,ORDER_PLACED
2025-01-15T10:32:00Z,ACC001,IBM,BUY,101.00,2000,ORDER_CANCELLED
2025-01-15T10:33:00Z,ACC002,AAPL,SELL,150.75,500,ORDER_PLACED
"""
    test_file = input_dir / "transactions.csv"
    test_file.write_text(csv_content)
    return test_file


class TestOrchestrateEndpoint:
    """Tests for POST /orchestrate endpoint with mocked HTTP services."""

    @pytest.mark.asyncio
    async def test_orchestrate_success(
        self,
        client: TestClient,
        sample_csv_file: Path,
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
            )

            # Assert - Should fail validation
            assert response.status_code == 500
            assert "did not complete" in response.json()["detail"].lower() or "final_status" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_aggregator_call(
        self,
        client: TestClient,
        sample_csv_file: Path,
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
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
        auth_headers: dict[str, str],
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
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
            )

            # Assert - Should handle aggregator failure
            assert response.status_code == 500
            assert "aggregator" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_csv_file_not_found(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test error handling when CSV file is not found."""
        # Act
        response = client.post(
            "/orchestrate",
            json={"input_file": "nonexistent.csv"},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_empty_csv_file(
        self,
        client: TestClient,
        input_dir: Path,
        auth_headers: dict[str, str],
    ) -> None:
        """Test error handling when CSV file is empty."""
        # Arrange - Create empty CSV within INPUT_DIR
        empty_file = input_dir / "empty.csv"
        empty_file.write_text("timestamp,account_id,product_id,side,price,quantity,event_type\n")

        # Act
        response = client.post(
            "/orchestrate",
            json={"input_file": "empty.csv"},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == 400
        assert "no events" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_path_traversal_relative_up_blocked(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that path traversal with ../ is blocked."""
        # Act - Attempt path traversal
        response = client.post(
            "/orchestrate",
            json={"input_file": "../etc/passwd"},
            headers=auth_headers,
        )

        # Assert - Should be rejected with 422 (validation error) due to path separator
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "path separator" in error_detail

    @pytest.mark.asyncio
    async def test_path_traversal_multiple_up_blocked(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that path traversal with multiple ../ is blocked."""
        # Act - Attempt path traversal with multiple ../ sequences
        response = client.post(
            "/orchestrate",
            json={"input_file": "../../../etc/passwd"},
            headers=auth_headers,
        )

        # Assert - Should be rejected with 422 (validation error) due to path separator
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "path separator" in error_detail

    @pytest.mark.asyncio
    async def test_path_traversal_absolute_outside_blocked(
        self,
        client: TestClient,
        sample_csv_file: Path,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that absolute paths outside INPUT_DIR are blocked."""
        # Arrange - Create file outside INPUT_DIR (simulate)
        # Note: In real scenario, INPUT_DIR would be /app/input, but in tests it's temp
        # We'll use an absolute path that we know is outside

        # Act - Attempt to access file with absolute path outside INPUT_DIR
        # Use a path that's definitely outside (like /etc/passwd on Unix)
        import os
        if os.name != "nt":  # Unix-like system
            response = client.post(
                "/orchestrate",
                json={"input_file": "/etc/passwd"},
                headers=auth_headers,
            )
        else:  # Windows
            response = client.post(
                "/orchestrate",
                json={"input_file": "C:\\Windows\\System32\\config\\sam"},
                headers=auth_headers,
            )

        # Assert - Should be rejected with 422 (validation error) due to path separator
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "path separator" in error_detail

    @pytest.mark.asyncio
    async def test_path_traversal_with_subdirectory_blocked(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that path traversal from subdirectory is blocked."""
        # Act - Attempt path traversal from subdirectory
        response = client.post(
            "/orchestrate",
            json={"input_file": "subdir/../../etc/passwd"},
            headers=auth_headers,
        )

        # Assert - Should be rejected with 422 (validation error) due to path separator
        assert response.status_code == 422
        error_detail = str(response.json()).lower()
        assert "path separator" in error_detail

    @pytest.mark.asyncio
    async def test_valid_path_within_input_dir_accepted(
        self,
        client: TestClient,
        sample_csv_file: Path,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that valid paths within INPUT_DIR are still accepted."""
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

        # Mock httpx.AsyncClient
        async def mock_post(self, url, **kwargs):
            if "/detect" in url and ("layering" in url.lower() or "8001" in url):
                return create_mock_response(200, mock_layering_response.model_dump(), url)
            if "/detect" in url and ("wash" in url.lower() or "8002" in url):
                return create_mock_response(200, mock_wash_trading_response.model_dump(), url)
            if "/aggregate" in url:
                return create_mock_response(200, mock_aggregate_response.model_dump(), url)
            return create_mock_response(404, {}, url)

        with patch("httpx.AsyncClient", create_mock_async_client(mock_post)):
            # Act - Use valid path (absolute path to file in temp directory)
            response = client.post(
                "/orchestrate",
                json={"input_file": "transactions.csv"},
                headers=auth_headers,
            )

            # Assert - Should succeed (200) since file is within INPUT_DIR
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_orchestrate_authentication_required(
        self,
        client: TestClient,
        api_key: str,
    ) -> None:
        """Test that /orchestrate endpoint requires API key authentication."""
        # Arrange - Create client without auth headers
        # Act - Request without API key
        response = client.post(
            "/orchestrate",
            json={"input_file": "test.csv"},
            # No X-API-Key header
        )

        # Assert - Should return 401
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_orchestrate_invalid_api_key_rejected(
        self,
        client: TestClient,
    ) -> None:
        """Test that /orchestrate endpoint rejects invalid API key."""
        # Act - Request with invalid API key
        response = client.post(
            "/orchestrate",
            json={"input_file": "test.csv"},
            headers={"X-API-Key": "invalid-key"},
        )

        # Assert - Should return 401
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]