"""
Integration tests for retry logic, exponential backoff, and fault tolerance.

Tests retry behavior with mocked HTTP clients to simulate various failure scenarios.
"""

from __future__ import annotations

import asyncio
import importlib.util
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from layering_detection.models import TransactionEvent

# Import retry module
project_root = Path(__file__).parent.parent.parent
retry_path = project_root / "services" / "orchestrator-service" / "retry.py"
spec = importlib.util.spec_from_file_location("orchestrator_retry", retry_path)
orchestrator_retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_retry)
process_with_retries = orchestrator_retry.process_with_retries


@pytest.fixture
def sample_events() -> list[TransactionEvent]:
    """Create sample TransactionEvent list for testing."""
    return [
        TransactionEvent(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            account_id="ACC001",
            product_id="IBM",
            side="BUY",
            price=Decimal("100.50"),
            quantity=1000,
            event_type="ORDER_PLACED",
        ),
    ]


@pytest.fixture
def service_status() -> dict[str, dict]:
    """Create empty service_status dict for testing."""
    return {}


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


# Store original asyncio.sleep before any patching
_original_asyncio_sleep = asyncio.sleep

def create_fast_sleep_mock():
    """
    Create a mock for asyncio.sleep that reduces delays for faster tests.
    
    Returns an async function that replaces asyncio.sleep in the retry module.
    The mock reduces all sleep delays to 0.01s while maintaining test logic.
    """
    async def fast_sleep(delay: float) -> None:
        """Mock sleep that reduces delays to 0.01s for test speed."""
        # Use original asyncio.sleep (captured at module level) to avoid recursion
        await _original_asyncio_sleep(0.01)  # Minimal delay for test speed
    
    return fast_sleep


class TestRetryOnTimeoutError:
    """Tests for retry logic on TimeoutError."""

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry on TimeoutError (mocked timeout)."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 2:
                # First call times out
                raise httpx.TimeoutException("Request timed out")
            # Second call succeeds
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 1  # Retried once
            assert call_count["count"] == 2  # Called twice

    @pytest.mark.asyncio
    async def test_timeout_exhaustion(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry exhaustion on TimeoutError."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        async def mock_post(self, url, **kwargs):
            # Always timeout
            raise httpx.TimeoutException("Request timed out")

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=2,  # 3 total attempts (0, 1, 2)
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "exhausted"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 3  # 3 attempts total
            assert service_status["layering"]["result"] is None
            assert service_status["layering"]["error"] is not None


class TestRetryOnConnectionError:
    """Tests for retry logic on ConnectionError."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry on ConnectionError (mocked connection failure)."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="wash_trading",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 2:
                # First call fails with connection error
                raise httpx.ConnectError("Connection refused")
            # Second call succeeds
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="wash_trading",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["wash_trading"]["status"] == "success"
            assert service_status["wash_trading"]["final_status"] is True
            assert service_status["wash_trading"]["retry_count"] == 1
            assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_connection_error_exhaustion(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry exhaustion on ConnectionError."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        async def mock_post(self, url, **kwargs):
            # Always fail with connection error
            raise httpx.ConnectError("Connection refused")

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="wash_trading",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=2,
                timeout=30,
            )

            # Assert
            assert service_status["wash_trading"]["status"] == "exhausted"
            assert service_status["wash_trading"]["final_status"] is True
            assert service_status["wash_trading"]["retry_count"] == 3


class TestRetryOnHttp5xxErrors:
    """Tests for retry logic on HTTP 5xx errors."""

    @pytest.mark.asyncio
    async def test_retry_on_http_500_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry on HTTP 500 error."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 2:
                # First call returns 500
                response = httpx.Response(500, json={"detail": "Internal server error"})
                raise httpx.HTTPStatusError("Server error", request=None, response=response)
            # Second call succeeds
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 1
            assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_retry_on_http_503_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry on HTTP 503 error."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="wash_trading",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            if call_count["count"] < 3:
                # First two calls return 503
                response = httpx.Response(503, json={"detail": "Service unavailable"})
                raise httpx.HTTPStatusError("Service unavailable", request=None, response=response)
            # Third call succeeds
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="wash_trading",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["wash_trading"]["status"] == "success"
            assert service_status["wash_trading"]["final_status"] is True
            assert service_status["wash_trading"]["retry_count"] == 2
            assert call_count["count"] == 3

    @pytest.mark.asyncio
    async def test_http_5xx_exhaustion(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry exhaustion on HTTP 5xx errors."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        async def mock_post(self, url, **kwargs):
            # Always return 500
            response = httpx.Response(500, json={"detail": "Internal server error"})
            raise httpx.HTTPStatusError("Server error", request=None, response=response)

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=2,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "exhausted"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 3
            assert "HTTP 500" in service_status["layering"]["error"]


class TestNoRetryOnHttp4xxErrors:
    """Tests for no retry on HTTP 4xx errors."""

    @pytest.mark.asyncio
    async def test_no_retry_on_http_400_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test no retry on HTTP 400 error (client error)."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            # Return 400 error (should not retry)
            response = httpx.Response(400, json={"detail": "Bad request"})
            raise httpx.HTTPStatusError("Bad request", request=None, response=response)

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "exhausted"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 1  # Only one attempt
            assert call_count["count"] == 1  # Called only once
            assert "HTTP 400" in service_status["layering"]["error"]

    @pytest.mark.asyncio
    async def test_no_retry_on_http_404_error(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test no retry on HTTP 404 error (client error)."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        call_count = {"count": 0}

        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            # Return 404 error (should not retry)
            response = httpx.Response(404, json={"detail": "Not found"})
            raise httpx.HTTPStatusError("Not found", request=None, response=response)

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient):
            # Act
            await process_with_retries(
                service_name="wash_trading",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["wash_trading"]["status"] == "exhausted"
            assert service_status["wash_trading"]["final_status"] is True
            assert service_status["wash_trading"]["retry_count"] == 1
            assert call_count["count"] == 1


class TestExponentialBackoff:
    """Tests for exponential backoff delays."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test exponential backoff delays (verify timing)."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        sleep_times: list[float] = []

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            # Fail first 2 attempts, succeed on 3rd
            if len(sleep_times) < 2:
                raise httpx.TimeoutException("Request timed out")
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        # Mock asyncio.sleep to capture sleep times
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            sleep_times.append(delay)
            await original_sleep(0.01)  # Minimal delay for test speed

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch("asyncio.sleep", mock_sleep):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "success"
            assert len(sleep_times) == 2  # Two backoff delays
            # Verify exponential backoff: 2^0 = 1s, 2^1 = 2s
            assert sleep_times[0] == 1.0
            assert sleep_times[1] == 2.0


class TestRetryCountTracking:
    """Tests for retry count tracking."""

    @pytest.mark.asyncio
    async def test_retry_count_tracking(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test retry count tracking."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        call_count = {"count": 0}
        async def mock_post(self, url, **kwargs):
            call_count["count"] += 1
            # Fail first attempt, succeed on second
            if call_count["count"] < 2:
                raise httpx.TimeoutException("Request timed out")
            mock_request = httpx.Request("POST", url)
            response = httpx.Response(200, json=mock_response.model_dump(), request=mock_request)
            response.raise_for_status = lambda: None
            return response

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["retry_count"] == 1  # One retry
            assert service_status["layering"]["final_status"] is True


class TestFinalStatusAfterExhaustion:
    """Tests for final_status=True after retries exhausted."""

    @pytest.mark.asyncio
    async def test_final_status_after_exhaustion(
        self,
        sample_events: list[TransactionEvent],
        service_status: dict[str, dict],
    ) -> None:
        """Test final_status=True after retries exhausted."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        async def mock_post(self, url, **kwargs):
            # Always fail
            raise httpx.TimeoutException("Request timed out")

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act
            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=2,
                timeout=30,
            )

            # Assert
            assert service_status["layering"]["status"] == "exhausted"
            assert service_status["layering"]["final_status"] is True  # Always True
            assert service_status["layering"]["retry_count"] == 3  # 3 attempts total


class TestFaultIsolation:
    """Tests for fault isolation (one service fails, others succeed)."""

    @pytest.mark.asyncio
    async def test_fault_isolation_one_service_fails(
        self,
        sample_events: list[TransactionEvent],
    ) -> None:
        """Test fault isolation: one service fails, others succeed."""
        # Arrange
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        service_status: dict[str, dict] = {}

        from services.shared.api_models import AlgorithmResponse

        layering_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        async def mock_post(self, url, **kwargs):
            # Layering service succeeds
            if "layering" in url.lower() or "8001" in url:
                mock_request = httpx.Request("POST", url)
                response = httpx.Response(200, json=layering_response.model_dump(), request=mock_request)
                response.raise_for_status = lambda: None
                return response
            # Wash trading service fails
            if "wash" in url.lower() or "8002" in url:
                raise httpx.TimeoutException("Request timed out")
            return httpx.Response(404)

        MockAsyncClient = create_mock_async_client(mock_post)

        with patch("httpx.AsyncClient", MockAsyncClient), patch.object(
            orchestrator_retry.asyncio, "sleep", create_fast_sleep_mock()
        ):
            # Act - Process both services
            import asyncio
            await asyncio.gather(
                process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=2,
                    timeout=30,
                ),
                process_with_retries(
                    service_name="wash_trading",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=2,
                    timeout=30,
                ),
            )

            # Assert
            # Layering should succeed
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["final_status"] is True
            # Wash trading should be exhausted
            assert service_status["wash_trading"]["status"] == "exhausted"
            assert service_status["wash_trading"]["final_status"] is True
            # Both should have final_status=True (fault isolation)

