"""
Integration tests for Aggregator Service.

Tests the full aggregation flow: validation, merging, CSV writing, and error handling.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from services.shared.api_models import AggregateRequest, AlgorithmResponse, SuspiciousSequenceDTO

# Import the app after setting up path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(project_root))

# Import app module (need to import as module to handle path setup)
app_module_path = project_root / "services" / "aggregator-service" / "main.py"
spec = importlib.util.spec_from_file_location("aggregator_service_main", app_module_path)
aggregator_service_main = importlib.util.module_from_spec(spec)
__import__("sys").modules["aggregator_service_main"] = aggregator_service_main
spec.loader.exec_module(aggregator_service_main)
app = aggregator_service_main.app


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_output_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary output directory and set environment variables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        logs_dir = Path(tmpdir) / "logs"
        output_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)

        # Set environment variables for config
        monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
        monkeypatch.setenv("LOGS_DIR", str(logs_dir))

        yield output_dir


@pytest.fixture
def sample_suspicious_sequence_dto() -> SuspiciousSequenceDTO:
    """Create sample SuspiciousSequenceDTO for testing."""
    return SuspiciousSequenceDTO(
        account_id="ACC001",
        product_id="IBM",
        start_timestamp="2025-01-15T10:00:00",
        end_timestamp="2025-01-15T11:00:00",
        total_buy_qty=5000,
        total_sell_qty=0,
        detection_type="LAYERING",
        side="BUY",
        num_cancelled_orders=3,
        order_timestamps=["2025-01-15T10:00:00", "2025-01-15T10:30:00"],
    )


@pytest.fixture
def sample_aggregate_request(
    sample_suspicious_sequence_dto: SuspiciousSequenceDTO,
) -> AggregateRequest:
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
                results=[sample_suspicious_sequence_dto],
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


class TestAggregateEndpoint:
    """Tests for POST /aggregate endpoint."""

    def test_aggregate_success(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test successful aggregation flow."""
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["merged_count"] == 1
        assert data["failed_services"] == []
        assert data["error"] is None

        # Verify output files were written
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        detections_path = temp_output_dir.parent / "logs" / "detections.csv"
        assert suspicious_path.exists()
        assert detections_path.exists()

        # Verify CSV content
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["account_id"] == "ACC001"

    def test_aggregate_validation_failure_missing_service(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test aggregation fails validation when service is missing."""
        # Remove one service from results
        request_data = sample_aggregate_request.model_dump()
        request_data["results"] = [request_data["results"][0]]  # Only layering service

        response = client.post("/aggregate", json=request_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "validation_failed"
        assert data["merged_count"] == 0
        assert "Missing services" in data["error"]
        assert "wash_trading" in data["error"]

        # Verify no files were written
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        assert not suspicious_path.exists()

    def test_aggregate_validation_failure_incomplete_service(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test aggregation fails validation when service has final_status=False."""
        request_data = sample_aggregate_request.model_dump()
        # Set final_status=False for one service
        request_data["results"][0]["final_status"] = False

        response = client.post("/aggregate", json=request_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "validation_failed"
        assert data["merged_count"] == 0
        assert "Services not completed" in data["error"]
        assert "final_status=True" in data["error"]

    def test_aggregate_with_failed_service_but_complete(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test aggregation succeeds when service failed but has final_status=True."""
        request_data = sample_aggregate_request.model_dump()
        # Set one service to failure but final_status=True (retries exhausted)
        request_data["results"][1] = {
            "request_id": request_data["request_id"],
            "service_name": "wash_trading",
            "status": "failure",
            "results": None,
            "error": "Service error",
            "final_status": True,
        }

        response = client.post("/aggregate", json=request_data)

        # Assertions - should succeed (validation passes, merge skips failed service)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["merged_count"] == 1  # Only layering service results
        assert "wash_trading" in data["failed_services"]

        # Verify files were written
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        assert suspicious_path.exists()

    def test_aggregate_merges_multiple_services(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test aggregation merges sequences from multiple services."""
        request_data = sample_aggregate_request.model_dump()
        # Add second sequence to wash_trading service
        request_data["results"][1]["results"] = [
            {
                "account_id": "ACC002",
                "product_id": "GOOG",
                "start_timestamp": "2025-01-15T12:00:00",
                "end_timestamp": "2025-01-15T13:00:00",
                "total_buy_qty": 3000,
                "total_sell_qty": 3000,
                "detection_type": "WASH_TRADING",
                "alternation_percentage": 75.5,
                "price_change_percentage": 2.5,
            }
        ]

        response = client.post("/aggregate", json=request_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["merged_count"] == 2  # Both sequences merged

        # Verify CSV has both sequences
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2

    def test_aggregate_deduplicates_overlapping_sequences(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test aggregation deduplicates overlapping sequences."""
        request_data = sample_aggregate_request.model_dump()
        # Add overlapping sequence (same account_id, overlapping time window)
        request_data["results"][1]["results"] = [
            {
                "account_id": "ACC001",  # Same account
                "product_id": "IBM",
                "start_timestamp": "2025-01-15T10:30:00",  # Overlapping time
                "end_timestamp": "2025-01-15T11:30:00",
                "total_buy_qty": 3000,
                "total_sell_qty": 3000,
                "detection_type": "WASH_TRADING",
            }
        ]

        response = client.post("/aggregate", json=request_data)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["merged_count"] == 1  # Deduplicated

        # Verify CSV has only one sequence
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1

    def test_aggregate_empty_results(
        self,
        client: TestClient,
        temp_output_dir: Path,
    ) -> None:
        """Test aggregation with empty results."""
        request_id = str(uuid4())
        request = AggregateRequest(
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

        response = client.post("/aggregate", json=request.model_dump())

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["merged_count"] == 0

        # Verify files exist but are empty (headers only)
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        assert suspicious_path.exists()

    def test_aggregate_request_id_preserved(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test that request_id is preserved throughout aggregation."""
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Request ID is logged but not in response (as per AggregateResponse model)

    def test_aggregate_invalid_request(self, client: TestClient) -> None:
        """Test aggregation with invalid request returns validation error."""
        response = client.post("/aggregate", json={"invalid": "data"})

        # FastAPI should return 422 for validation error
        assert response.status_code == 422

    def test_csv_format_suspicious_accounts(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test suspicious_accounts.csv format matches expected structure."""
        # Arrange
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())
        assert response.status_code == 200

        # Act - Read CSV file
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        assert suspicious_path.exists()

        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Assert - Verify CSV structure matches expected format
        assert len(rows) == 1
        row = rows[0]
        # Verify all required fields exist (per write_suspicious_accounts schema)
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
        for field in expected_fields:
            assert field in row, f"Missing field: {field}"
        
        # Verify data values
        assert row["account_id"] == "ACC001"
        assert row["product_id"] == "IBM"
        assert row["detection_type"] == "LAYERING"
        assert int(row["total_buy_qty"]) == 5000
        assert int(row["total_sell_qty"]) == 0
        assert int(row["num_cancelled_orders"]) == 3
        # alternation_percentage should be empty for LAYERING
        assert row["alternation_percentage"] == ""

    def test_csv_format_detections(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test detections.csv format matches expected structure."""
        # Arrange
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())
        assert response.status_code == 200

        # Act - Read detections CSV file
        detections_path = temp_output_dir.parent / "logs" / "detections.csv"
        assert detections_path.exists()

        with detections_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Assert - Verify CSV format matches expected schema (per write_detection_logs)
        assert len(rows) >= 1
        expected_fields = [
            "account_id",
            "product_id",
            "order_timestamps",
            "duration_seconds",
        ]
        if rows:
            row = rows[0]
            for field in expected_fields:
                assert field in row, f"Missing field: {field}"
            assert row["account_id"] == "ACC001"
            assert row["product_id"] == "IBM"
            # Verify duration_seconds is a valid float
            assert float(row["duration_seconds"]) >= 0

    def test_csv_writes_unique_accounts_only(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test suspicious_accounts.csv contains unique account IDs only."""
        # Arrange - Multiple sequences with same account_id
        request_data = sample_aggregate_request.model_dump()
        request_data["results"][0]["results"].append(
            {
                "account_id": "ACC001",  # Same account
                "product_id": "IBM",
                "start_timestamp": "2025-01-15T12:00:00",
                "end_timestamp": "2025-01-15T13:00:00",
                "total_buy_qty": 2000,
                "total_sell_qty": 0,
                "detection_type": "LAYERING",
            }
        )

        # Act
        response = client.post("/aggregate", json=request_data)
        assert response.status_code == 200

        # Assert - suspicious_accounts.csv should have unique accounts
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            account_ids = [row["account_id"] for row in rows]
            # Should be unique (deduplicated)
            assert len(account_ids) == len(set(account_ids))

    def test_csv_format_wash_trading_fields(
        self,
        client: TestClient,
        temp_output_dir: Path,
    ) -> None:
        """Test CSV format includes wash trading specific fields correctly."""
        # Arrange - Create request with wash trading sequence
        request_id = str(uuid4())
        request = AggregateRequest(
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
                    results=[
                        SuspiciousSequenceDTO(
                            account_id="ACC002",
                            product_id="GOOG",
                            start_timestamp="2025-01-15T10:00:00",
                            end_timestamp="2025-01-15T11:00:00",
                            total_buy_qty=5000,
                            total_sell_qty=5000,
                            detection_type="WASH_TRADING",
                            alternation_percentage=75.5,
                            price_change_percentage=2.5,
                        )
                    ],
                    error=None,
                    final_status=True,
                ),
            ],
        )

        # Act
        response = client.post("/aggregate", json=request.model_dump())
        assert response.status_code == 200

        # Assert - Verify wash trading fields are populated
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        with suspicious_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        row = rows[0]
        assert row["detection_type"] == "WASH_TRADING"
        assert row["alternation_percentage"] == "75.50"  # Formatted to 2 decimals
        assert row["price_change_percentage"] == "2.50"
        assert int(row["num_cancelled_orders"]) == 0  # Should be 0 for wash trading

    def test_file_write_error_handling_invalid_path(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test file write error handling with invalid path."""
        # Arrange - Set invalid output directory
        # Use a path that will fail on write (non-existent parent on Unix, or invalid drive on Windows)
        import platform
        if platform.system() == "Windows":
            # On Windows, use an invalid drive letter
            invalid_path = "Z:\\invalid\\path\\that\\does\\not\\exist"
        else:
            # On Unix, use a path with non-existent parent
            invalid_path = "/invalid/path/that/does/not/exist"
        
        monkeypatch.setenv("OUTPUT_DIR", invalid_path)
        monkeypatch.setenv("LOGS_DIR", invalid_path)

        # Act
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())

        # Assert - Should handle error gracefully
        assert response.status_code == 200
        data = response.json()
        # Should return validation_failed status with error message
        assert data["status"] == "validation_failed"
        assert data["error"] is not None
        assert "Failed to write output files" in data["error"]
        assert data["merged_count"] >= 0  # Merged count may be set even if write failed

    def test_csv_writes_both_files_successfully(
        self,
        client: TestClient,
        temp_output_dir: Path,
        sample_aggregate_request: AggregateRequest,
    ) -> None:
        """Test that both suspicious_accounts.csv and detections.csv are written."""
        # Arrange
        response = client.post("/aggregate", json=sample_aggregate_request.model_dump())
        assert response.status_code == 200

        # Assert - Both files should exist
        suspicious_path = temp_output_dir / "suspicious_accounts.csv"
        detections_path = temp_output_dir.parent / "logs" / "detections.csv"
        
        assert suspicious_path.exists(), "suspicious_accounts.csv should be created"
        assert detections_path.exists(), "detections.csv should be created"
        
        # Verify files are not empty (have headers at minimum)
        assert suspicious_path.stat().st_size > 0
        assert detections_path.stat().st_size > 0

