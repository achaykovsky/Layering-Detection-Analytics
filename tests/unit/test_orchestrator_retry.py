"""
Unit tests for Orchestrator Service retry logic with exponential backoff.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from layering_detection.models import TransactionEvent

# Import retry module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
retry_path = project_root / "services" / "orchestrator-service" / "retry.py"
spec = importlib.util.spec_from_file_location("orchestrator_retry", retry_path)
orchestrator_retry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_retry)
process_with_retries = orchestrator_retry.process_with_retries


class TestProcessWithRetries:
    """Tests for process_with_retries function."""

    @pytest.fixture
    def sample_events(self) -> list[TransactionEvent]:
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
    def service_status(self) -> dict[str, dict]:
        """Create empty service_status dict for testing."""
        return {}

    @pytest.mark.asyncio
    async def test_process_with_retries_success_first_attempt(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test successful service call on first attempt."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        # Mock successful response
        from services.shared.api_models import AlgorithmResponse

        mock_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = mock_response

            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Verify service_status updated correctly
            assert "layering" in service_status
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["final_status"] is True
            assert service_status["layering"]["retry_count"] == 0
            assert service_status["layering"]["result"] == mock_response
            assert service_status["layering"]["error"] is None

            # Verify called once (no retries)
            assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_process_with_retries_success_after_retry(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test successful service call after retry."""
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

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            # First call fails with timeout, second succeeds
            mock_call.side_effect = [
                TimeoutError("Request timed out"),
                mock_response,
            ]

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=3,
                    timeout=30,
                )

                # Verify service_status updated correctly
                assert service_status["layering"]["status"] == "success"
                assert service_status["layering"]["final_status"] is True
                assert service_status["layering"]["retry_count"] == 1  # Retried once

                # Verify called twice (initial + retry)
                assert mock_call.call_count == 2

                # Verify exponential backoff: 2^0 = 1 second
                mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_process_with_retries_exhausted_retries(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test exhausted retries after all attempts fail."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            # All calls fail with timeout
            mock_call.side_effect = TimeoutError("Request timed out")

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=3,
                    timeout=30,
                )

                # Verify service_status updated correctly
                assert service_status["layering"]["status"] == "exhausted"
                assert service_status["layering"]["final_status"] is True
                assert service_status["layering"]["retry_count"] == 4  # 0, 1, 2, 3 = 4 attempts
                assert service_status["layering"]["result"] is None
                assert service_status["layering"]["error"] is not None

                # Verify called 4 times (max_retries + 1)
                assert mock_call.call_count == 4

                # Verify exponential backoff: 1s, 2s, 4s
                assert mock_sleep.call_count == 3
                mock_sleep.assert_any_call(1)  # 2^0
                mock_sleep.assert_any_call(2)  # 2^1
                mock_sleep.assert_any_call(4)  # 2^2

    @pytest.mark.asyncio
    async def test_process_with_retries_no_retry_on_4xx(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test that 4xx errors are not retried."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        # Mock 400 Bad Request error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_error = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.side_effect = mock_error

            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            # Verify service_status updated correctly
            assert service_status["layering"]["status"] == "exhausted"
            assert service_status["layering"]["final_status"] is True
            assert "400" in service_status["layering"]["error"]

            # Verify called only once (no retry)
            assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_process_with_retries_retry_on_5xx(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test that 5xx errors are retried."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        from services.shared.api_models import AlgorithmResponse

        # First call fails with 500, second succeeds
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_error_500 = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response_500
        )

        success_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.side_effect = [mock_error_500, success_response]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=3,
                    timeout=30,
                )

                # Verify service_status updated correctly
                assert service_status["layering"]["status"] == "success"
                assert service_status["layering"]["retry_count"] == 1

                # Verify called twice (initial + retry)
                assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_process_with_retries_connection_error_retry(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test that ConnectionError is retried."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        from services.shared.api_models import AlgorithmResponse

        success_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            # First call fails with connection error, second succeeds
            mock_call.side_effect = [ConnectionError("Connection failed"), success_response]

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=3,
                    timeout=30,
                )

                # Verify service_status updated correctly
                assert service_status["layering"]["status"] == "success"
                assert service_status["layering"]["retry_count"] == 1

                # Verify called twice
                assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_process_with_retries_exponential_backoff_timing(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test exponential backoff timing (1s, 2s, 4s)."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            # All calls fail with timeout
            mock_call.side_effect = TimeoutError("Request timed out")

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=3,
                    timeout=30,
                )

                # Verify exponential backoff delays
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls == [1, 2, 4]  # 2^0, 2^1, 2^2

    @pytest.mark.asyncio
    async def test_process_with_retries_final_status_always_true(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test that final_status is always True after function completes."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        from services.shared.api_models import AlgorithmResponse

        # Test success case
        success_response = AlgorithmResponse(
            request_id=request_id,
            service_name="layering",
            status="success",
            results=[],
            error=None,
            final_status=True,
        )

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = success_response

            await process_with_retries(
                service_name="layering",
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=sample_events,
                service_status=service_status,
                max_retries=3,
                timeout=30,
            )

            assert service_status["layering"]["final_status"] is True

        # Test exhausted case
        service_status.clear()
        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.side_effect = TimeoutError("Request timed out")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await process_with_retries(
                    service_name="wash_trading",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=2,
                    timeout=30,
                )

                assert service_status["wash_trading"]["final_status"] is True

    @pytest.mark.asyncio
    async def test_process_with_retries_custom_max_retries(
        self, sample_events: list[TransactionEvent], service_status: dict[str, dict]
    ) -> None:
        """Test custom max_retries parameter."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64

        with patch.object(
            orchestrator_retry,
            "call_algorithm_service",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.side_effect = TimeoutError("Request timed out")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await process_with_retries(
                    service_name="layering",
                    request_id=request_id,
                    event_fingerprint=event_fingerprint,
                    events=sample_events,
                    service_status=service_status,
                    max_retries=2,  # Custom max_retries
                    timeout=30,
                )

                # Verify called 3 times (max_retries + 1)
                assert mock_call.call_count == 3

                # Verify retry_count is 3
                assert service_status["layering"]["retry_count"] == 3

