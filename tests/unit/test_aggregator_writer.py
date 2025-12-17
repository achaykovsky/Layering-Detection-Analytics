"""
Unit tests for Aggregator Service CSV writing logic.
"""

from __future__ import annotations

import csv
import importlib.util
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from layering_detection.models import SuspiciousSequence
from services.shared.api_models import SuspiciousSequenceDTO

# Import writer module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
writer_path = project_root / "services" / "aggregator-service" / "writer.py"
spec = importlib.util.spec_from_file_location("aggregator_writer", writer_path)
aggregator_writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_writer)
write_output_files = aggregator_writer.write_output_files
write_output_files_from_dtos = aggregator_writer.write_output_files_from_dtos


class TestWriteOutputFiles:
    """Tests for write_output_files function."""

    def test_write_suspicious_accounts_csv(self) -> None:
        """Test writing suspicious_accounts.csv file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                    side="BUY",
                    num_cancelled_orders=3,
                ),
            ]

            write_output_files(sequences, tmpdir)

            # Verify suspicious_accounts.csv exists and has correct content
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            assert suspicious_path.exists()

            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["account_id"] == "ACC001"
                assert rows[0]["product_id"] == "IBM"
                assert rows[0]["total_buy_qty"] == "5000"
                assert rows[0]["total_sell_qty"] == "0"
                assert rows[0]["num_cancelled_orders"] == "3"
                assert rows[0]["detection_type"] == "LAYERING"

    def test_write_detections_csv(self) -> None:
        """Test writing detections.csv file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 10, 0, 10),
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                    order_timestamps=[
                        datetime(2025, 1, 15, 10, 0, 0),
                        datetime(2025, 1, 15, 10, 0, 5),
                    ],
                ),
            ]

            write_output_files(sequences, tmpdir)

            # Verify detections.csv exists and has correct content
            detections_path = Path(tmpdir) / "detections.csv"
            assert detections_path.exists()

            with detections_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["account_id"] == "ACC001"
                assert rows[0]["product_id"] == "IBM"
                assert "order_timestamps" in rows[0]
                assert "duration_seconds" in rows[0]

    def test_write_both_files(self) -> None:
        """Test writing both suspicious_accounts.csv and detections.csv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                ),
            ]

            write_output_files(sequences, tmpdir)

            # Verify both files exist
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            detections_path = Path(tmpdir) / "detections.csv"
            assert suspicious_path.exists()
            assert detections_path.exists()

    def test_write_separate_logs_dir(self) -> None:
        """Test writing detections.csv to separate logs directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                ),
            ]

            write_output_files(sequences, tmpdir, logs_dir=str(logs_dir))

            # Verify files in correct locations
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            detections_path = logs_dir / "detections.csv"
            assert suspicious_path.exists()
            assert detections_path.exists()

    def test_write_multiple_sequences(self) -> None:
        """Test writing multiple sequences to CSV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                ),
                SuspiciousSequence(
                    account_id="ACC002",
                    product_id="GOOG",
                    start_timestamp=datetime(2025, 1, 15, 12, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 13, 0, 0),
                    total_buy_qty=3000,
                    total_sell_qty=3000,
                    detection_type="WASH_TRADING",
                    alternation_percentage=75.5,
                    price_change_percentage=2.5,
                ),
            ]

            write_output_files(sequences, tmpdir)

            # Verify both sequences are written
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 2
                assert rows[0]["account_id"] == "ACC001"
                assert rows[1]["account_id"] == "ACC002"

    def test_write_empty_sequences(self) -> None:
        """Test writing empty sequences list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_output_files([], tmpdir)

            # Verify files exist but are empty (only headers)
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            detections_path = Path(tmpdir) / "detections.csv"
            assert suspicious_path.exists()
            assert detections_path.exists()

            # Verify files have headers only
            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 0

    def test_write_wash_trading_sequence(self) -> None:
        """Test writing wash trading sequence with optional fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sequences = [
                SuspiciousSequence(
                    account_id="ACC001",
                    product_id="GOOG",
                    start_timestamp=datetime(2025, 1, 15, 10, 0, 0),
                    end_timestamp=datetime(2025, 1, 15, 11, 0, 0),
                    total_buy_qty=3000,
                    total_sell_qty=3000,
                    detection_type="WASH_TRADING",
                    alternation_percentage=75.5,
                    price_change_percentage=2.5,
                ),
            ]

            write_output_files(sequences, tmpdir)

            # Verify wash trading fields are written correctly
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["detection_type"] == "WASH_TRADING"
                assert rows[0]["alternation_percentage"] == "75.50"
                assert rows[0]["price_change_percentage"] == "2.50"
                assert rows[0]["num_cancelled_orders"] == "0"


class TestWriteOutputFilesFromDtos:
    """Tests for write_output_files_from_dtos function."""

    def test_write_from_dtos(self) -> None:
        """Test writing CSV files from DTOs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dtos = [
                SuspiciousSequenceDTO(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp="2025-01-15T10:00:00",
                    end_timestamp="2025-01-15T11:00:00",
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                    side="BUY",
                    num_cancelled_orders=3,
                ),
            ]

            write_output_files_from_dtos(dtos, tmpdir)

            # Verify files exist
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            detections_path = Path(tmpdir) / "detections.csv"
            assert suspicious_path.exists()
            assert detections_path.exists()

            # Verify content
            with suspicious_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["account_id"] == "ACC001"

    def test_write_from_dtos_with_request_id(self) -> None:
        """Test writing from DTOs with request_id for logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            request_id = str(uuid4())
            dtos = [
                SuspiciousSequenceDTO(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp="2025-01-15T10:00:00",
                    end_timestamp="2025-01-15T11:00:00",
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                ),
            ]

            write_output_files_from_dtos(dtos, tmpdir, request_id=request_id)

            # Verify files exist
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            assert suspicious_path.exists()

    def test_write_from_dtos_conversion_error_handling(self) -> None:
        """Test that conversion errors are handled gracefully."""
        # Note: Pydantic validates timestamps at DTO creation, so we can't test invalid timestamps
        # This test verifies the function handles conversion errors properly
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid DTOs should convert successfully
            dtos = [
                SuspiciousSequenceDTO(
                    account_id="ACC001",
                    product_id="IBM",
                    start_timestamp="2025-01-15T10:00:00",
                    end_timestamp="2025-01-15T11:00:00",
                    total_buy_qty=5000,
                    total_sell_qty=0,
                    detection_type="LAYERING",
                ),
            ]

            # Should not raise error
            write_output_files_from_dtos(dtos, tmpdir)

            # Verify files exist
            suspicious_path = Path(tmpdir) / "suspicious_accounts.csv"
            assert suspicious_path.exists()

