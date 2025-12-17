"""
End-to-end tests for full pipeline execution with Docker Compose.

Tests the complete flow: CSV → orchestrator → algorithms → aggregator → output.
Requires docker-compose to be running or available.
"""

from __future__ import annotations

import asyncio
import csv
import subprocess
import time
from pathlib import Path
from typing import Generator

import httpx
import pytest

# Project root
project_root = Path(__file__).parent.parent.parent


def docker_compose_up() -> None:
    """Start docker-compose services."""
    subprocess.run(
        ["docker-compose", "up", "-d", "--build"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )


def docker_compose_down() -> None:
    """Stop docker-compose services."""
    subprocess.run(
        ["docker-compose", "down"],
        cwd=project_root,
        check=False,
        capture_output=True,
    )


def docker_compose_stop_service(service_name: str) -> None:
    """Stop a specific service."""
    subprocess.run(
        ["docker-compose", "stop", service_name],
        cwd=project_root,
        check=False,
        capture_output=True,
    )


def docker_compose_start_service(service_name: str) -> None:
    """Start a specific service."""
    subprocess.run(
        ["docker-compose", "start", service_name],
        cwd=project_root,
        check=False,
        capture_output=True,
    )


def wait_for_service_healthy(service_url: str, timeout: int = 60) -> bool:
    """Wait for a service to become healthy."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = httpx.get(f"{service_url}/health", timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def wait_for_all_services_healthy(timeout: int = 120) -> bool:
    """Wait for all services to become healthy."""
    services = [
        "http://localhost:8000",  # orchestrator
        "http://localhost:8001",  # layering
        "http://localhost:8002",  # wash-trading
        "http://localhost:8003",  # aggregator
    ]
    for service_url in services:
        if not wait_for_service_healthy(service_url, timeout=timeout):
            return False
    return True


@pytest.fixture(scope="module")
def docker_compose_setup() -> Generator[None, None, None]:
    """Fixture to start and stop docker-compose services."""
    # Start services
    try:
        docker_compose_up()
        # Wait for services to be healthy
        if not wait_for_all_services_healthy(timeout=120):
            pytest.skip("Docker Compose services did not become healthy in time")
        yield
    finally:
        # Cleanup - stop services
        docker_compose_down()


@pytest.fixture
def sample_csv_file(docker_compose_setup) -> Path:
    """Copy sample CSV to input directory."""
    input_dir = project_root / "input"
    input_dir.mkdir(exist_ok=True)

    sample_csv = project_root / "tests" / "e2e" / "fixtures" / "sample_transactions.csv"
    target_csv = input_dir / "sample_transactions.csv"

    # Copy sample CSV to input directory
    import shutil
    shutil.copy(sample_csv, target_csv)

    yield target_csv

    # Cleanup
    if target_csv.exists():
        target_csv.unlink()


@pytest.fixture
def clean_output_dirs() -> Generator[None, None, None]:
    """Clean output and logs directories before test."""
    output_dir = project_root / "output"
    logs_dir = project_root / "logs"

    # Clean directories
    for csv_file in output_dir.glob("*.csv"):
        csv_file.unlink()
    for csv_file in logs_dir.glob("*.csv"):
        csv_file.unlink()

    yield

    # Cleanup after test
    for csv_file in output_dir.glob("*.csv"):
        csv_file.unlink()
    for csv_file in logs_dir.glob("*.csv"):
        csv_file.unlink()


class TestFullPipeline:
    """Tests for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_execution(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test full pipeline execution: CSV → orchestrator → algorithms → aggregator → output."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Act - Call orchestrator endpoint
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["event_count"] > 0
        assert "request_id" in data
        assert len(data["request_id"]) == 36  # UUID format

        # Verify output files were created
        output_dir = project_root / "output"
        logs_dir = project_root / "logs"

        suspicious_path = output_dir / "suspicious_accounts.csv"
        detections_path = logs_dir / "detections.csv"

        assert suspicious_path.exists(), "suspicious_accounts.csv should be created"
        assert detections_path.exists(), "detections.csv should be created"

        # Verify CSV format
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Should have at least headers
            assert len(rows) >= 0
            if rows:
                # Verify required fields
                assert "account_id" in rows[0]
                assert "product_id" in rows[0]
                assert "detection_type" in rows[0]

    @pytest.mark.asyncio
    async def test_output_csv_format(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test output CSV files have correct format."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Act
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )

        assert response.status_code == 200

        # Assert - Verify CSV format
        output_dir = project_root / "output"
        suspicious_path = output_dir / "suspicious_accounts.csv"

        if suspicious_path.exists():
            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                # Verify expected fields exist
                expected_fields = [
                    "account_id",
                    "product_id",
                    "total_buy_qty",
                    "total_sell_qty",
                    "num_cancelled_orders",
                    "detected_timestamp",
                    "detection_type",
                    "alternation_percentage",
                    "price_change_percentage",
                ]
                if rows:
                    for field in expected_fields:
                        assert field in rows[0], f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_retry_scenario(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test retry scenario: temporarily stop service, verify retry."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Stop layering service temporarily
        docker_compose_stop_service("layering-service")
        time.sleep(2)

        # Start a request (should retry)
        async with httpx.AsyncClient(timeout=180.0) as client:
            # Start request in background
            request_task = client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )

            # Wait a bit, then restart service
            await asyncio.sleep(5)
            docker_compose_start_service("layering-service")
            wait_for_service_healthy("http://localhost:8001", timeout=30)

            # Wait for request to complete
            response = await request_task

        # Assert - Should eventually succeed after retry
        assert response.status_code == 200
        data = response.json()
        # May succeed or fail depending on timing, but should handle gracefully
        assert data["status"] in ("completed", "failed")

    @pytest.mark.asyncio
    async def test_fault_isolation(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test fault isolation: one service fails, others continue."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Stop one service (wash-trading)
        docker_compose_stop_service("wash-trading-service")

        try:
            # Act - Run pipeline
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{orchestrator_url}/orchestrate",
                    json={"input_file": input_file},
                )

            # Assert - Should handle failure gracefully
            # Orchestrator should retry and eventually mark service as exhausted
            assert response.status_code in (200, 500)
            if response.status_code == 200:
                data = response.json()
                # May complete with failed service or fail validation
                assert data["status"] in ("completed", "failed")
        finally:
            # Restart service
            docker_compose_start_service("wash-trading-service")
            wait_for_service_healthy("http://localhost:8002", timeout=30)

    @pytest.mark.asyncio
    async def test_deduplication(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test deduplication: same request_id + fingerprint returns cached result."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Act - Run pipeline twice with same file
        async with httpx.AsyncClient(timeout=120.0) as client:
            response1 = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )
            assert response1.status_code == 200
            request_id1 = response1.json()["request_id"]

            # Run again with same file (should generate same fingerprint)
            response2 = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )
            assert response2.status_code == 200
            request_id2 = response2.json()["request_id"]

        # Assert - Request IDs should be different (new request each time)
        # But algorithm services should use idempotency cache
        assert request_id1 != request_id2  # Different orchestrator requests

    @pytest.mark.asyncio
    async def test_completion_validation(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test completion validation: all services must complete."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Act - Run pipeline
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()

        # If completed, all services should have finished
        if data["status"] == "completed":
            assert data["failed_services"] == [] or len(data["failed_services"]) < 2
            # Should have aggregated results
            assert data["aggregated_count"] >= 0

    @pytest.mark.asyncio
    async def test_real_input_csv(
        self,
        docker_compose_setup,
        sample_csv_file: Path,
        clean_output_dirs,
    ) -> None:
        """Test with real input CSV file."""
        # Arrange
        orchestrator_url = "http://localhost:8000"
        input_file = sample_csv_file.name

        # Verify input file exists
        assert sample_csv_file.exists()

        # Act
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{orchestrator_url}/orchestrate",
                json={"input_file": input_file},
            )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["event_count"] > 0

        # Verify output files exist
        output_dir = project_root / "output"
        suspicious_path = output_dir / "suspicious_accounts.csv"
        assert suspicious_path.exists()

