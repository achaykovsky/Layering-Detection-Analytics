"""
Unit tests for Orchestrator Service CSV reading logic.
"""

from __future__ import annotations

import csv
import importlib.util
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from layering_detection.models import TransactionEvent

# Import reader module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
reader_path = project_root / "services" / "orchestrator-service" / "reader.py"
spec = importlib.util.spec_from_file_location("orchestrator_reader", reader_path)
orchestrator_reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_reader)
read_input_csv = orchestrator_reader.read_input_csv


class TestReadInputCsv:
    """Tests for read_input_csv function."""

    def test_read_valid_csv(self) -> None:
        """Test reading valid CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": "1000",
                    "event_type": "ORDER_PLACED",
                }
            )
            csv_path = Path(f.name)

        try:
            events = read_input_csv(csv_path)

            assert len(events) == 1
            assert isinstance(events[0], TransactionEvent)
            assert events[0].account_id == "ACC001"
            assert events[0].product_id == "IBM"
            assert events[0].side == "BUY"
            assert events[0].price == Decimal("100.50")
            assert events[0].quantity == 1000
            assert events[0].event_type == "ORDER_PLACED"
        finally:
            csv_path.unlink()

    def test_read_multiple_rows(self) -> None:
        """Test reading CSV file with multiple rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": "1000",
                    "event_type": "ORDER_PLACED",
                }
            )
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:31:00Z",
                    "account_id": "ACC002",
                    "product_id": "GOOG",
                    "side": "SELL",
                    "price": "200.75",
                    "quantity": "500",
                    "event_type": "TRADE_EXECUTED",
                }
            )
            csv_path = Path(f.name)

        try:
            events = read_input_csv(csv_path)

            assert len(events) == 2
            assert events[0].account_id == "ACC001"
            assert events[1].account_id == "ACC002"
        finally:
            csv_path.unlink()

    def test_read_missing_file(self) -> None:
        """Test reading non-existent CSV file raises FileNotFoundError."""
        csv_path = Path("/nonexistent/file.csv")

        with pytest.raises(FileNotFoundError) as exc_info:
            read_input_csv(csv_path)

        assert "not found" in str(exc_info.value).lower()

    def test_read_invalid_csv_missing_columns(self) -> None:
        """Test reading CSV with missing required columns raises ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "account_id"])  # Missing columns
            writer.writeheader()
            writer.writerow({"timestamp": "2025-01-15T10:30:00Z", "account_id": "ACC001"})
            csv_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                read_input_csv(csv_path)

            assert "Missing required CSV columns" in str(exc_info.value)
        finally:
            csv_path.unlink()

    def test_read_invalid_csv_invalid_data(self) -> None:
        """Test reading CSV with invalid data skips invalid rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": "1000",
                    "event_type": "ORDER_PLACED",
                }
            )
            writer.writerow(
                {
                    "timestamp": "invalid-timestamp",  # Invalid timestamp
                    "account_id": "ACC002",
                    "product_id": "GOOG",
                    "side": "SELL",
                    "price": "200.75",
                    "quantity": "500",
                    "event_type": "TRADE_EXECUTED",
                }
            )
            csv_path = Path(f.name)

        try:
            # Invalid rows are skipped, valid rows are returned
            events = read_input_csv(csv_path)

            assert len(events) == 1  # Only valid row
            assert events[0].account_id == "ACC001"
        finally:
            csv_path.unlink()

    def test_read_empty_csv(self) -> None:
        """Test reading empty CSV file (headers only)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            # No data rows
            csv_path = Path(f.name)

        try:
            events = read_input_csv(csv_path)

            assert len(events) == 0
        finally:
            csv_path.unlink()

    def test_read_with_request_id_logging(self) -> None:
        """Test reading CSV with request_id for logging."""
        request_id = str(uuid4())
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": "1000",
                    "event_type": "ORDER_PLACED",
                }
            )
            csv_path = Path(f.name)

        try:
            events = read_input_csv(csv_path, request_id=request_id)

            assert len(events) == 1
        finally:
            csv_path.unlink()

    def test_read_path_object(self) -> None:
        """Test reading CSV using Path object instead of string."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "account_id",
                    "product_id",
                    "side",
                    "price",
                    "quantity",
                    "event_type",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": "1000",
                    "event_type": "ORDER_PLACED",
                }
            )
            csv_path = Path(f.name)

        try:
            # Pass Path object instead of string
            events = read_input_csv(csv_path)

            assert len(events) == 1
        finally:
            csv_path.unlink()

    def test_read_invalid_path_not_file(self) -> None:
        """Test reading path that is not a file raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)

            with pytest.raises(ValueError) as exc_info:
                read_input_csv(dir_path)

            assert "not a file" in str(exc_info.value).lower()

