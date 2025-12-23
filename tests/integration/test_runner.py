"""
Integration tests for the detection pipeline runner.

Tests the end-to-end pipeline that runs both layering and wash trading
detection algorithms and produces merged output.
"""

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from layering_detection.orchestrator import run_pipeline
from layering_detection.models import TransactionEvent
from tests.fixtures import create_transaction_event


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class TestRunnerPipeline:
    """Test suite for the basic pipeline execution."""

    def test_run_pipeline_creates_outputs_and_logs(self, tmp_path: Path) -> None:
        """Test that pipeline creates output and log files."""
        input_path = BASE_DIR / "input" / "transactions.csv"
        assert input_path.exists(), "Expected sample transactions.csv for pipeline test"

        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"

        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)

        suspicious_path = output_dir / "suspicious_accounts.csv"
        logs_path = logs_dir / "detections.csv"

        assert suspicious_path.exists()
        assert logs_path.exists()

        # Sanity check contents of suspicious_accounts.csv
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # From the detector tests we expect two sequences for the sample data.
        assert len(rows) == 2
        keys = {(r["account_id"], r["product_id"]) for r in rows}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}

        # Verify detection_type field is present
        for row in rows:
            assert "detection_type" in row
            assert row["detection_type"] == "LAYERING"

        # Sanity check contents of detections.csv
        with logs_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            log_rows = list(reader)
            log_fieldnames = reader.fieldnames

        assert log_fieldnames == [
            "account_id",
            "product_id",
            "order_timestamps",
            "duration_seconds",
        ]
        assert len(log_rows) == 2


class TestRunnerPipelineIntegration:
    """Integration tests for merged pipeline with both algorithms."""

    def test_pipeline_runs_both_algorithms(self, tmp_path: Path) -> None:
        """Test that pipeline runs both layering and wash trading algorithms."""
        # Create test data with both layering and wash trading patterns
        base_time = datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        
        # Layering pattern: ACC001, IBM
        layering_events = [
            create_transaction_event(
                timestamp=base_time,
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=5000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=2),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=5000,
                event_type="ORDER_PLACED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=3),
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=Decimal("100.0"),
                quantity=5000,
                event_type="ORDER_CANCELLED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(seconds=4),
                account_id="ACC001",
                product_id="IBM",
                side="SELL",
                price=Decimal("100.5"),
                quantity=5000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        
        # Wash trading pattern: ACC002, AAPL
        wash_trading_events = [
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=1),
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("150.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=6),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("150.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=11),
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("151.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=16),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("151.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=21),
                account_id="ACC002",
                product_id="AAPL",
                side="BUY",
                price=Decimal("152.0"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
            create_transaction_event(
                timestamp=base_time + timedelta(minutes=26),
                account_id="ACC002",
                product_id="AAPL",
                side="SELL",
                price=Decimal("152.5"),
                quantity=2000,
                event_type="TRADE_EXECUTED",
            ),
        ]
        
        # Write test CSV
        input_path = tmp_path / "transactions.csv"
        all_events = layering_events + wash_trading_events
        
        with input_path.open("w", newline="", encoding="utf-8") as f:
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
            for event in all_events:
                writer.writerow(
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "account_id": event.account_id,
                        "product_id": event.product_id,
                        "side": event.side,
                        "price": str(event.price),
                        "quantity": str(event.quantity),
                        "event_type": event.event_type,
                    }
                )
        
        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"
        
        # Run pipeline
        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)
        
        # Verify output
        suspicious_path = output_dir / "suspicious_accounts.csv"
        assert suspicious_path.exists()
        
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Should have at least one layering and one wash trading detection
        detection_types = {row["detection_type"] for row in rows}
        assert "LAYERING" in detection_types or "WASH_TRADING" in detection_types
        
        # Verify detection_type field is present in all rows
        for row in rows:
            assert "detection_type" in row
            assert row["detection_type"] in ("LAYERING", "WASH_TRADING")

    def test_pipeline_output_includes_detection_type(self, tmp_path: Path) -> None:
        """Test that output CSV includes detection_type field to distinguish algorithms."""
        input_path = BASE_DIR / "input" / "transactions.csv"
        assert input_path.exists(), "Expected sample transactions.csv for pipeline test"

        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"

        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)

        suspicious_path = output_dir / "suspicious_accounts.csv"
        
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Verify detection_type is in fieldnames
        assert fieldnames is not None
        assert "detection_type" in fieldnames
        assert "alternation_percentage" in fieldnames
        assert "price_change_percentage" in fieldnames
        
        # Verify all rows have detection_type
        for row in rows:
            assert "detection_type" in row
            assert row["detection_type"] in ("LAYERING", "WASH_TRADING")

    def test_pipeline_merges_results_from_both_algorithms(self, tmp_path: Path) -> None:
        """Test that pipeline merges results from both algorithms into single list."""
        input_path = BASE_DIR / "input" / "transactions.csv"
        assert input_path.exists(), "Expected sample transactions.csv for pipeline test"

        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"

        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)

        suspicious_path = output_dir / "suspicious_accounts.csv"
        logs_path = logs_dir / "detections.csv"
        
        # Verify both files exist
        assert suspicious_path.exists()
        assert logs_path.exists()
        
        # Verify suspicious_accounts.csv contains merged results
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Should have at least the layering detections from sample data
        assert len(rows) >= 2
        
        # Verify logs.csv contains merged results
        with logs_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            log_rows = list(reader)
        
        # Should have at least the layering detections from sample data
        assert len(log_rows) >= 2

    def test_pipeline_backward_compatibility(self, tmp_path: Path) -> None:
        """Test that existing code still works (backward compatibility)."""
        input_path = BASE_DIR / "input" / "transactions.csv"
        assert input_path.exists(), "Expected sample transactions.csv for pipeline test"

        output_dir = tmp_path / "output"
        logs_dir = tmp_path / "logs"

        # Run pipeline (should work without errors)
        run_pipeline(input_path=input_path, output_dir=output_dir, logs_dir=logs_dir)

        suspicious_path = output_dir / "suspicious_accounts.csv"
        logs_path = logs_dir / "detections.csv"
        
        # Verify files are created
        assert suspicious_path.exists()
        assert logs_path.exists()
        
        # Verify output structure matches expected format
        with suspicious_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Should have expected layering detections
        assert len(rows) == 2
        keys = {(r["account_id"], r["product_id"]) for r in rows}
        assert keys == {("ACC001", "IBM"), ("ACC017", "AAPL")}
        
        # All should be LAYERING type (from sample data)
        for row in rows:
            assert row["detection_type"] == "LAYERING"


