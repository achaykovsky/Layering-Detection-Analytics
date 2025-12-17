"""
Unit tests for Orchestrator Service HTTP client.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from services.shared.api_models import (
    AggregateRequest,
    AggregateResponse,
    AlgorithmRequest,
    AlgorithmResponse,
    TransactionEventDTO,
)

# Import client module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
client_path = project_root / "services" / "orchestrator-service" / "client.py"
spec = importlib.util.spec_from_file_location("orchestrator_client", client_path)
orchestrator_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_client)
call_algorithm_service = orchestrator_client.call_algorithm_service
call_aggregator_service = orchestrator_client.call_aggregator_service


class TestCallAlgorithmService:
    """Tests for call_algorithm_service function."""

    @pytest.fixture
    def sample_request(self) -> AlgorithmRequest:
        """Create sample AlgorithmRequest for testing."""
        return AlgorithmRequest(
            request_id=str(uuid4()),
            event_fingerprint="a" * 64,  # 64-character hexdigest
            events=[
                TransactionEventDTO(
                    timestamp="2025-01-15T10:30:00Z",
                    account_id="ACC001",
                    product_id="IBM",
                    side="BUY",
                    price="100.50",
                    quantity=1000,
                    event_type="ORDER_PLACED",
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_call_algorithm_service_success(self, sample_request: AlgorithmRequest) -> None:
        """Test successful algorithm service call."""
        expected_response = AlgorithmResponse(
            request_id=sample_request.request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_algorithm_service("layering", sample_request, timeout=30)

            assert isinstance(response, AlgorithmResponse)
            assert response.request_id == sample_request.request_id
            assert response.service_name == "layering"
            assert response.status == "success"

    @pytest.mark.asyncio
    async def test_call_algorithm_service_timeout(self, sample_request: AlgorithmRequest) -> None:
        """Test algorithm service call timeout."""
        # Mock httpx.TimeoutException
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(TimeoutError) as exc_info:
                await call_algorithm_service("layering", sample_request, timeout=30)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_algorithm_service_connection_error(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test algorithm service connection error."""
        # Mock httpx.ConnectError
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError) as exc_info:
                await call_algorithm_service("layering", sample_request, timeout=30)

            assert "failed to connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_algorithm_service_5xx_error(self, sample_request: AlgorithmRequest) -> None:
        """Test algorithm service 5xx HTTP error."""
        # Mock httpx.HTTPStatusError for 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_error = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await call_algorithm_service("layering", sample_request, timeout=30)

    @pytest.mark.asyncio
    async def test_call_algorithm_service_4xx_error(self, sample_request: AlgorithmRequest) -> None:
        """Test algorithm service 4xx HTTP error."""
        # Mock httpx.HTTPStatusError for 400 error
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_error = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await call_algorithm_service("layering", sample_request, timeout=30)

    @pytest.mark.asyncio
    async def test_call_algorithm_service_invalid_service_name(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test algorithm service call with invalid service name."""
        with pytest.raises(ValueError) as exc_info:
            await call_algorithm_service("invalid_service", sample_request, timeout=30)

        error_msg = str(exc_info.value).lower()
        assert "invalid" in error_msg and "service" in error_msg

    @pytest.mark.asyncio
    async def test_call_algorithm_service_response_parsing_error(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test algorithm service response parsing error."""
        # Mock invalid response JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}  # Missing required fields
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await call_algorithm_service("layering", sample_request, timeout=30)

            assert "failed to parse" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_algorithm_service_wash_trading(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test calling wash trading service."""
        expected_response = AlgorithmResponse(
            request_id=sample_request.request_id,
            service_name="wash_trading",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_algorithm_service("wash_trading", sample_request, timeout=30)

            assert response.service_name == "wash_trading"

    @pytest.mark.asyncio
    async def test_call_algorithm_service_request_id_preserved(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test that request_id is preserved in response."""
        expected_response = AlgorithmResponse(
            request_id=sample_request.request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_algorithm_service("layering", sample_request, timeout=30)

            assert response.request_id == sample_request.request_id

    @pytest.mark.asyncio
    async def test_call_algorithm_service_url_construction(
        self, sample_request: AlgorithmRequest
    ) -> None:
        """Test that service URL is constructed correctly."""
        expected_response = AlgorithmResponse(
            request_id=sample_request.request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await call_algorithm_service("layering", sample_request, timeout=30)

            # Verify POST was called with correct URL
            call_args = mock_client.post.call_args
            assert call_args is not None
            url = call_args[0][0]  # First positional argument
            assert url.endswith("/detect")
            assert "layering" in url.lower() or "8001" in url


class TestCallAggregatorService:
    """Tests for call_aggregator_service function."""

    @pytest.fixture
    def sample_aggregate_request(self) -> AggregateRequest:
        """Create sample AggregateRequest for testing."""
        request_id = str(uuid4())
        return AggregateRequest(
            request_id=request_id,
            expected_services=["layering", "wash_trading"],
            results=[
                AlgorithmResponse(
                    request_id=request_id,
                    service_name="layering",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
                AlgorithmResponse(
                    request_id=request_id,
                    service_name="wash_trading",
                    status="success",
                    results=[],
                    error=None,
                    final_status=True,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_call_aggregator_service_success(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test successful aggregator service call."""
        expected_response = AggregateResponse(
            status="completed",
            merged_count=5,
            failed_services=[],
            error=None,
        )

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_aggregator_service(sample_aggregate_request, timeout=60)

            assert isinstance(response, AggregateResponse)
            assert response.status == "completed"
            assert response.merged_count == 5
            assert response.failed_services == []
            assert response.error is None

    @pytest.mark.asyncio
    async def test_call_aggregator_service_timeout(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service call timeout."""
        # Mock httpx.TimeoutException
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(TimeoutError) as exc_info:
                await call_aggregator_service(sample_aggregate_request, timeout=60)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_aggregator_service_connection_error(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service connection error."""
        # Mock httpx.ConnectError
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError) as exc_info:
                await call_aggregator_service(sample_aggregate_request, timeout=60)

            assert "failed to connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_aggregator_service_5xx_error(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service 5xx HTTP error."""
        # Mock httpx.HTTPStatusError for 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_error = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await call_aggregator_service(sample_aggregate_request, timeout=60)

    @pytest.mark.asyncio
    async def test_call_aggregator_service_4xx_error(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service 4xx HTTP error."""
        # Mock httpx.HTTPStatusError for 400 error
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_error = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await call_aggregator_service(sample_aggregate_request, timeout=60)

    @pytest.mark.asyncio
    async def test_call_aggregator_service_response_parsing_error(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service response parsing error."""
        # Mock invalid response JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"invalid": "response"}  # Missing required fields
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError) as exc_info:
                await call_aggregator_service(sample_aggregate_request, timeout=60)

            assert "failed to parse" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_aggregator_service_validation_failed(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test aggregator service validation failed response."""
        expected_response = AggregateResponse(
            status="validation_failed",
            merged_count=0,
            failed_services=[],
            error="Missing services: ['wash_trading']",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_aggregator_service(sample_aggregate_request, timeout=60)

            assert response.status == "validation_failed"
            assert response.error is not None
            assert "missing" in response.error.lower()

    @pytest.mark.asyncio
    async def test_call_aggregator_service_request_id_preserved(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test that request_id is preserved in logging and request."""
        expected_response = AggregateResponse(
            status="completed",
            merged_count=0,
            failed_services=[],
            error=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = await call_aggregator_service(sample_aggregate_request, timeout=60)

            # Verify request was sent with correct request_id
            call_args = mock_client.post.call_args
            assert call_args is not None
            json_data = call_args[1]["json"]  # Keyword argument
            assert json_data["request_id"] == sample_aggregate_request.request_id

    @pytest.mark.asyncio
    async def test_call_aggregator_service_url_construction(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test that aggregator URL is constructed correctly."""
        expected_response = AggregateResponse(
            status="completed",
            merged_count=0,
            failed_services=[],
            error=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await call_aggregator_service(sample_aggregate_request, timeout=60)

            # Verify POST was called with correct URL
            call_args = mock_client.post.call_args
            assert call_args is not None
            url = call_args[0][0]  # First positional argument
            assert url.endswith("/aggregate")
            assert "aggregator" in url.lower() or "8003" in url

    @pytest.mark.asyncio
    async def test_call_aggregator_service_default_timeout(
        self, sample_aggregate_request: AggregateRequest
    ) -> None:
        """Test that default timeout is used when not specified."""
        expected_response = AggregateResponse(
            status="completed",
            merged_count=0,
            failed_services=[],
            error=None,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response.model_dump()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client) as mock_httpx:
            await call_aggregator_service(sample_aggregate_request)

            # Verify timeout was set (default is 60s)
            httpx_call_args = mock_httpx.call_args
            assert httpx_call_args is not None
            assert httpx_call_args[1]["timeout"] == 60

