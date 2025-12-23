"""
Unit tests for Orchestrator Service parallel algorithm service calls.
"""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from layering_detection.models import TransactionEvent
from services.shared.api_models import AlgorithmResponse
from tests.fixtures import create_transaction_event

# Import orchestrator module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
orchestrator_path = project_root / "services" / "orchestrator-service" / "orchestrator.py"
spec = importlib.util.spec_from_file_location("orchestrator", orchestrator_path)
orchestrator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator)
call_all_algorithm_services = orchestrator.call_all_algorithm_services
EXPECTED_SERVICES = orchestrator.EXPECTED_SERVICES


class TestCallAllAlgorithmServices:
    """Tests for call_all_algorithm_services function."""

    @pytest.mark.asyncio
    async def test_all_services_succeed(self) -> None:
        """Test parallel calls when all services succeed."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        # Mock process_with_retries to succeed for all services
        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            # Configure mock to update service_status
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": 0,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify all services were called
            assert mock_process.call_count == len(EXPECTED_SERVICES)
            called_services = {
                call.kwargs["service_name"] for call in mock_process.call_args_list
            }
            assert called_services == set(EXPECTED_SERVICES)

            # Verify service_status contains all services with success
            assert len(service_status) == len(EXPECTED_SERVICES)
            for service_name in EXPECTED_SERVICES:
                assert service_name in service_status
                assert service_status[service_name]["status"] == "success"
                assert service_status[service_name]["final_status"] is True
                assert service_status[service_name]["result"] is not None
                assert service_status[service_name]["error"] is None
                assert service_status[service_name]["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_some_services_fail(self) -> None:
        """Test parallel calls when some services fail."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        # Mock process_with_retries: layering succeeds, wash_trading fails
        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                if service_name == "layering":
                    service_status[service_name] = {
                        "status": "success",
                        "final_status": True,
                        "result": AlgorithmResponse(
                            request_id=request_id,
                            service_name=service_name,
                            status="success",
                            results=[],
                            error=None,
                            final_status=True,
                        ),
                        "error": None,
                        "retry_count": 0,
                    }
                else:  # wash_trading
                    service_status[service_name] = {
                        "status": "exhausted",
                        "final_status": True,
                        "result": None,
                        "error": "All retries exhausted",
                        "retry_count": 3,
                    }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify all services were called
            assert mock_process.call_count == len(EXPECTED_SERVICES)

            # Verify layering succeeded
            assert service_status["layering"]["status"] == "success"
            assert service_status["layering"]["final_status"] is True

            # Verify wash_trading failed
            assert service_status["wash_trading"]["status"] == "exhausted"
            assert service_status["wash_trading"]["final_status"] is True
            assert service_status["wash_trading"]["result"] is None
            assert "exhausted" in service_status["wash_trading"]["error"].lower()

    @pytest.mark.asyncio
    async def test_all_services_fail(self) -> None:
        """Test parallel calls when all services fail."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        # Mock process_with_retries to fail for all services
        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                service_status[service_name] = {
                    "status": "exhausted",
                    "final_status": True,
                    "result": None,
                    "error": f"Service {service_name} failed",
                    "retry_count": 3,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify all services were called
            assert mock_process.call_count == len(EXPECTED_SERVICES)

            # Verify all services failed
            for service_name in EXPECTED_SERVICES:
                assert service_status[service_name]["status"] == "exhausted"
                assert service_status[service_name]["final_status"] is True
                assert service_status[service_name]["result"] is None
                assert service_status[service_name]["error"] is not None
                assert service_status[service_name]["retry_count"] == 3

    @pytest.mark.asyncio
    async def test_parallel_execution(self) -> None:
        """Test that services are called in parallel (not sequentially)."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        # Track call order and timing
        call_times: dict[str, float] = {}
        call_order: list[str] = []

        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                import time

                call_times[service_name] = time.time()
                call_order.append(service_name)
                # Simulate some work
                await asyncio.sleep(0.1)
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": 0,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            start_time = asyncio.get_event_loop().time()
            await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )
            end_time = asyncio.get_event_loop().time()

            # Verify all services were called
            assert mock_process.call_count == len(EXPECTED_SERVICES)

            # Verify calls started around the same time (parallel execution)
            # If sequential, total time would be ~0.2s (2 * 0.1s)
            # If parallel, total time should be ~0.1s (max of 0.1s)
            elapsed_time = end_time - start_time
            assert elapsed_time < 0.15, f"Expected parallel execution, but took {elapsed_time}s"

    @pytest.mark.asyncio
    async def test_service_status_tracking(self) -> None:
        """Test that service_status is properly tracked for all services."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                # Each service updates service_status with different retry counts
                retry_count = 0 if service_name == "layering" else 2
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": retry_count,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify service_status structure
            assert len(service_status) == len(EXPECTED_SERVICES)
            for service_name in EXPECTED_SERVICES:
                assert service_name in service_status
                status = service_status[service_name]
                assert "status" in status
                assert "final_status" in status
                assert "result" in status
                assert "error" in status
                assert "retry_count" in status
                assert status["final_status"] is True

            # Verify specific retry counts
            assert service_status["layering"]["retry_count"] == 0
            assert service_status["wash_trading"]["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_custom_max_retries_and_timeout(self) -> None:
        """Test that custom max_retries and timeout are passed to process_with_retries."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        custom_max_retries = 5
        custom_timeout = 60

        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                max_retries: int | None = None,
                timeout: int | None = None,
                **kwargs,
            ) -> None:
                # Verify custom values are passed
                assert max_retries == custom_max_retries
                assert timeout == custom_timeout
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": 0,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function with custom values
            await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
                max_retries=custom_max_retries,
                timeout=custom_timeout,
            )

            # Verify all services were called with custom values
            assert mock_process.call_count == len(EXPECTED_SERVICES)
            for call in mock_process.call_args_list:
                assert call.kwargs["max_retries"] == custom_max_retries
                assert call.kwargs["timeout"] == custom_timeout

    @pytest.mark.asyncio
    async def test_request_id_preserved(self) -> None:
        """Test that request_id is preserved and passed to all service calls."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events = [
            create_transaction_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                account_id="acc1",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.00"),
                quantity=1000,
                event_type="ORDER_PLACED",
            )
        ]

        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                # Verify request_id matches
                assert request_id == request_id
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": 0,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify request_id was passed to all calls
            assert mock_process.call_count == len(EXPECTED_SERVICES)
            for call in mock_process.call_args_list:
                assert call.kwargs["request_id"] == request_id

    @pytest.mark.asyncio
    async def test_empty_events(self) -> None:
        """Test parallel calls with empty events list."""
        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        events: list[TransactionEvent] = []

        with patch.object(
            orchestrator,
            "process_with_retries",
            new_callable=AsyncMock,
        ) as mock_process:
            async def mock_process_side_effect(
                service_name: str,
                request_id: str,
                event_fingerprint: str,
                events: list[TransactionEvent],
                service_status: dict[str, dict],
                **kwargs,
            ) -> None:
                # Verify empty events list is passed
                assert events == []
                service_status[service_name] = {
                    "status": "success",
                    "final_status": True,
                    "result": AlgorithmResponse(
                        request_id=request_id,
                        service_name=service_name,
                        status="success",
                        results=[],
                        error=None,
                        final_status=True,
                    ),
                    "error": None,
                    "retry_count": 0,
                }

            mock_process.side_effect = mock_process_side_effect

            # Call function
            service_status = await call_all_algorithm_services(
                request_id=request_id,
                event_fingerprint=event_fingerprint,
                events=events,
            )

            # Verify all services were called
            assert mock_process.call_count == len(EXPECTED_SERVICES)
            assert len(service_status) == len(EXPECTED_SERVICES)

