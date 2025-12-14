"""
Unit tests for DetectionAlgorithm base class.
"""

from abc import ABC
from pathlib import Path
from typing import Iterable

import pytest

from layering_detection.algorithms.base import DetectionAlgorithm
from layering_detection.models import SuspiciousSequence, TransactionEvent


class TestDetectionAlgorithm:
    """Test suite for DetectionAlgorithm base class."""

    def test_is_abstract_base_class(self) -> None:
        """Test that DetectionAlgorithm is an abstract base class."""
        # Assert
        assert issubclass(DetectionAlgorithm, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        """Test that DetectionAlgorithm cannot be instantiated directly."""
        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DetectionAlgorithm()  # type: ignore[abstract]

    def test_requires_name_property(self) -> None:
        """Test that subclasses must implement name property."""
        # Arrange
        class IncompleteAlgorithm(DetectionAlgorithm):
            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteAlgorithm()  # type: ignore[abstract]

    def test_requires_description_property(self) -> None:
        """Test that subclasses must implement description property."""
        # Arrange
        class IncompleteAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            def detect(self, events):
                return []

        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteAlgorithm()  # type: ignore[abstract]

    def test_requires_detect_method(self) -> None:
        """Test that subclasses must implement detect method."""
        # Arrange
        class IncompleteAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

        # Act & Assert
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteAlgorithm()  # type: ignore[abstract]

    def test_complete_implementation_can_be_instantiated(self) -> None:
        """Test that complete implementation can be instantiated."""
        # Arrange
        class CompleteAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test_algorithm"

            @property
            def description(self) -> str:
                return "Test algorithm for unit testing"

            def detect(
                self, events: Iterable[TransactionEvent]
            ) -> list[SuspiciousSequence]:
                return []

        # Act
        algorithm = CompleteAlgorithm()

        # Assert
        assert algorithm.name == "test_algorithm"
        assert algorithm.description == "Test algorithm for unit testing"
        assert isinstance(algorithm, DetectionAlgorithm)

    def test_filter_events_default_returns_all_events(self) -> None:
        """Test that filter_events() default implementation returns all events."""
        # Arrange
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        algorithm = TestAlgorithm()
        events = [
            TransactionEvent(
                timestamp=None,  # type: ignore[arg-type]
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=None,  # type: ignore[arg-type]
                quantity=100,
                event_type="ORDER_PLACED",
            )
        ]

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert filtered == events
        assert len(filtered) == 1

    def test_filter_events_can_be_overridden(self) -> None:
        """Test that filter_events() can be overridden in subclasses."""
        # Arrange
        class FilteringAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "filtering"

            @property
            def description(self) -> str:
                return "Filtering test"

            def detect(self, events):
                return []

            def filter_events(self, events):
                return [e for e in events if e.event_type == "TRADE_EXECUTED"]

        algorithm = FilteringAlgorithm()
        events = [
            TransactionEvent(
                timestamp=None,  # type: ignore[arg-type]
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=None,  # type: ignore[arg-type]
                quantity=100,
                event_type="ORDER_PLACED",
            ),
            TransactionEvent(
                timestamp=None,  # type: ignore[arg-type]
                account_id="ACC001",
                product_id="IBM",
                side="BUY",
                price=None,  # type: ignore[arg-type]
                quantity=100,
                event_type="TRADE_EXECUTED",
            ),
        ]

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert len(filtered) == 1
        assert filtered[0].event_type == "TRADE_EXECUTED"

    def test_detect_method_signature(self) -> None:
        """Test that detect() method has correct signature."""
        # Arrange
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(
                self, events: Iterable[TransactionEvent]
            ) -> list[SuspiciousSequence]:
                return []

        algorithm = TestAlgorithm()
        events: list[TransactionEvent] = []

        # Act
        result = algorithm.detect(events)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    def test_name_property_is_readonly(self) -> None:
        """Test that name property is read-only."""
        # Arrange
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        algorithm = TestAlgorithm()

        # Act & Assert
        assert algorithm.name == "test"
        # Cannot set property (read-only)
        with pytest.raises(AttributeError):
            algorithm.name = "new_name"  # type: ignore[misc]

    def test_description_property_is_readonly(self) -> None:
        """Test that description property is read-only."""
        # Arrange
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test description"

            def detect(self, events):
                return []

        algorithm = TestAlgorithm()

        # Act & Assert
        assert algorithm.description == "Test description"
        # Cannot set property (read-only)
        with pytest.raises(AttributeError):
            algorithm.description = "New description"  # type: ignore[misc]

    def test_run_from_volume_reads_and_writes_files(self, tmp_path: Path) -> None:
        """Test that run_from_volume() reads input and writes output correctly."""
        # Arrange
        from datetime import datetime, timezone
        from decimal import Decimal

        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(
                self, events: Iterable[TransactionEvent]
            ) -> list[SuspiciousSequence]:
                # Return empty list for simplicity
                return []

        algorithm = TestAlgorithm()
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create minimal valid CSV
        input_file = input_dir / "transactions.csv"
        input_file.write_text(
            "timestamp,account_id,product_id,side,price,quantity,event_type\n"
            "2025-01-01T09:00:00Z,ACC001,IBM,BUY,100.0,1000,ORDER_PLACED\n"
        )

        # Act
        algorithm.run_from_volume(str(input_dir), str(output_dir))

        # Assert
        output_file = output_dir / "suspicious_accounts.csv"
        assert output_file.exists()
        # Output file should exist (even if empty for no detections)

    def test_run_from_volume_raises_file_not_found_if_input_missing(
        self, tmp_path: Path
    ) -> None:
        """Test that run_from_volume() raises FileNotFoundError if input file missing."""
        # Arrange
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        algorithm = TestAlgorithm()
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Input file not found"):
            algorithm.run_from_volume(str(input_dir), str(output_dir))

    def test_run_from_volume_creates_output_directory(self, tmp_path: Path) -> None:
        """Test that run_from_volume() creates output directory if it doesn't exist."""
        # Arrange
        from datetime import datetime, timezone
        from decimal import Decimal

        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        algorithm = TestAlgorithm()
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output" / "nested"
        input_dir.mkdir()

        # Create minimal valid CSV
        input_file = input_dir / "transactions.csv"
        input_file.write_text(
            "timestamp,account_id,product_id,side,price,quantity,event_type\n"
            "2025-01-01T09:00:00Z,ACC001,IBM,BUY,100.0,1000,ORDER_PLACED\n"
        )

        # Act
        algorithm.run_from_volume(str(input_dir), str(output_dir))

        # Assert
        assert output_dir.exists()
        output_file = output_dir / "suspicious_accounts.csv"
        assert output_file.exists()

