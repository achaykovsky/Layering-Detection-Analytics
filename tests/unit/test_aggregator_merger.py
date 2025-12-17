"""
Unit tests for Aggregator Service result merging logic.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from services.shared.api_models import AlgorithmResponse, SuspiciousSequenceDTO

# Import merger module (handles hyphenated directory name)
project_root = Path(__file__).parent.parent.parent
merger_path = project_root / "services" / "aggregator-service" / "merger.py"
spec = importlib.util.spec_from_file_location("aggregator_merger", merger_path)
aggregator_merger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aggregator_merger)
merge_results = aggregator_merger.merge_results


class TestMergeResults:
    """Tests for merge_results function."""

    def test_merge_multiple_services(self) -> None:
        """Test merging sequences from multiple successful services."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
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
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC002",
                        product_id="GOOG",
                        start_timestamp="2025-01-15T12:00:00",
                        end_timestamp="2025-01-15T13:00:00",
                        total_buy_qty=3000,
                        total_sell_qty=3000,
                        detection_type="WASH_TRADING",
                        alternation_percentage=75.5,
                        price_change_percentage=2.5,
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        assert len(merged) == 2
        assert merged[0].account_id == "ACC001"
        assert merged[1].account_id == "ACC002"

    def test_merge_deduplicates_overlapping_sequences(self) -> None:
        """Test deduplication of sequences with same account_id and overlapping time windows."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",  # Same account
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:30:00",  # Overlapping time window
                        end_timestamp="2025-01-15T11:30:00",
                        total_buy_qty=3000,
                        total_sell_qty=3000,
                        detection_type="WASH_TRADING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should deduplicate - only one sequence kept
        assert len(merged) == 1
        assert merged[0].account_id == "ACC001"

    def test_merge_preserves_non_overlapping_sequences(self) -> None:
        """Test that sequences with same account_id but non-overlapping time windows are preserved."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",  # Same account
                        product_id="IBM",
                        start_timestamp="2025-01-15T12:00:00",  # Non-overlapping time window
                        end_timestamp="2025-01-15T13:00:00",
                        total_buy_qty=3000,
                        total_sell_qty=3000,
                        detection_type="WASH_TRADING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should preserve both sequences (different time windows)
        assert len(merged) == 2

    def test_merge_preserves_different_accounts(self) -> None:
        """Test that sequences with different account_ids are preserved."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC002",  # Different account
                        product_id="GOOG",
                        start_timestamp="2025-01-15T10:00:00",  # Same time window
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=3000,
                        total_sell_qty=3000,
                        detection_type="WASH_TRADING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should preserve both sequences (different accounts)
        assert len(merged) == 2

    def test_merge_skips_failed_services(self) -> None:
        """Test that sequences from failed services are not included."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="failure",  # Failed service
                results=None,
                error="Service error",
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should only include sequences from successful service
        assert len(merged) == 1
        assert merged[0].account_id == "ACC001"

    def test_merge_empty_results(self) -> None:
        """Test merging when no sequences are found."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[],  # Empty results
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[],  # Empty results
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        assert len(merged) == 0

    def test_merge_all_failed_services(self) -> None:
        """Test merging when all services failed."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="failure",
                results=None,
                error="Service error",
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="failure",
                results=None,
                error="Service error",
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        assert len(merged) == 0

    def test_merge_deduplicates_multiple_overlaps(self) -> None:
        """Test deduplication when multiple sequences overlap."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                    SuspiciousSequenceDTO(
                        account_id="ACC001",  # Same account
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:15:00",  # Overlapping
                        end_timestamp="2025-01-15T11:15:00",
                        total_buy_qty=3000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should deduplicate overlapping sequences
        assert len(merged) == 1
        assert merged[0].account_id == "ACC001"

    def test_merge_preserves_first_occurrence(self) -> None:
        """Test that first occurrence is preserved during deduplication."""
        results = [
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                        side="BUY",
                    ),
                ],
                error=None,
                final_status=True,
            ),
            AlgorithmResponse(
                request_id=str(uuid4()),
                service_name="wash_trading",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",  # Same account
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:30:00",  # Overlapping
                        end_timestamp="2025-01-15T11:30:00",
                        total_buy_qty=3000,
                        total_sell_qty=3000,
                        detection_type="WASH_TRADING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results)

        # Should preserve first occurrence (from layering service)
        assert len(merged) == 1
        assert merged[0].detection_type == "LAYERING"  # First occurrence preserved
        assert merged[0].side == "BUY"

    def test_merge_with_request_id_logging(self) -> None:
        """Test that merge_results accepts request_id for logging."""
        request_id = str(uuid4())
        results = [
            AlgorithmResponse(
                request_id=request_id,
                service_name="layering",
                status="success",
                results=[
                    SuspiciousSequenceDTO(
                        account_id="ACC001",
                        product_id="IBM",
                        start_timestamp="2025-01-15T10:00:00",
                        end_timestamp="2025-01-15T11:00:00",
                        total_buy_qty=5000,
                        total_sell_qty=0,
                        detection_type="LAYERING",
                    ),
                ],
                error=None,
                final_status=True,
            ),
        ]

        merged = merge_results(results, request_id=request_id)

        assert len(merged) == 1

