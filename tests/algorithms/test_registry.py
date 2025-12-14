"""
Unit tests for AlgorithmRegistry.
"""

from typing import List

import pytest

from layering_detection.algorithms.base import DetectionAlgorithm
from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import SuspiciousSequence, TransactionEvent


class TestAlgorithmRegistry:
    """Test suite for AlgorithmRegistry class."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        AlgorithmRegistry.clear()

    def teardown_method(self) -> None:
        """Clear registry after each test."""
        AlgorithmRegistry.clear()

    def test_register_decorator_registers_algorithm(self) -> None:
        """Test that @register decorator registers algorithm."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test algorithm"

            def detect(
                self, events: List[TransactionEvent]
            ) -> List[SuspiciousSequence]:
                return []

        # Act
        algorithm = AlgorithmRegistry.get("test")

        # Assert
        assert isinstance(algorithm, TestAlgorithm)
        assert algorithm.name == "test"
        assert algorithm.description == "Test algorithm"

    def test_get_retrieves_registered_algorithm(self) -> None:
        """Test that get() retrieves registered algorithm by name."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        # Act
        algorithm = AlgorithmRegistry.get("test")

        # Assert
        assert isinstance(algorithm, TestAlgorithm)
        assert algorithm.name == "test"

    def test_get_raises_keyerror_for_unregistered_algorithm(self) -> None:
        """Test that get() raises KeyError for unregistered algorithm."""
        # Act & Assert
        with pytest.raises(KeyError, match="Algorithm 'nonexistent' is not registered"):
            AlgorithmRegistry.get("nonexistent")

    def test_list_all_returns_all_registered_names(self) -> None:
        """Test that list_all() returns all registered algorithm names."""
        # Arrange
        @AlgorithmRegistry.register
        class AlgorithmA(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "algorithm_a"

            @property
            def description(self) -> str:
                return "A"

            def detect(self, events):
                return []

        @AlgorithmRegistry.register
        class AlgorithmB(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "algorithm_b"

            @property
            def description(self) -> str:
                return "B"

            def detect(self, events):
                return []

        # Act
        names = AlgorithmRegistry.list_all()

        # Assert
        assert len(names) == 2
        assert "algorithm_a" in names
        assert "algorithm_b" in names
        assert names == sorted(names)  # Should be sorted

    def test_list_all_returns_empty_list_when_no_algorithms_registered(self) -> None:
        """Test that list_all() returns empty list when no algorithms registered."""
        # Act
        names = AlgorithmRegistry.list_all()

        # Assert
        assert names == []

    def test_get_all_returns_all_algorithms_when_enabled_is_none(self) -> None:
        """Test that get_all() returns all algorithms when enabled is None."""
        # Arrange
        @AlgorithmRegistry.register
        class AlgorithmA(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "a"

            @property
            def description(self) -> str:
                return "A"

            def detect(self, events):
                return []

        @AlgorithmRegistry.register
        class AlgorithmB(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "b"

            @property
            def description(self) -> str:
                return "B"

            def detect(self, events):
                return []

        # Act
        algorithms = AlgorithmRegistry.get_all()

        # Assert
        assert len(algorithms) == 2
        names = [alg.name for alg in algorithms]
        assert "a" in names
        assert "b" in names
        assert names == sorted(names)  # Should be sorted

    def test_get_all_filters_by_enabled_list(self) -> None:
        """Test that get_all() filters by enabled list."""
        # Arrange
        @AlgorithmRegistry.register
        class AlgorithmA(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "a"

            @property
            def description(self) -> str:
                return "A"

            def detect(self, events):
                return []

        @AlgorithmRegistry.register
        class AlgorithmB(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "b"

            @property
            def description(self) -> str:
                return "B"

            def detect(self, events):
                return []

        # Act
        algorithms = AlgorithmRegistry.get_all(enabled=["a"])

        # Assert
        assert len(algorithms) == 1
        assert algorithms[0].name == "a"

    def test_get_all_returns_empty_list_when_enabled_is_empty(self) -> None:
        """Test that get_all() returns empty list when enabled is empty."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        # Act
        algorithms = AlgorithmRegistry.get_all(enabled=[])

        # Assert
        assert algorithms == []

    def test_get_all_raises_keyerror_for_unregistered_in_enabled_list(self) -> None:
        """Test that get_all() raises KeyError if enabled list contains unregistered algorithm."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        # Act & Assert
        with pytest.raises(
            KeyError, match="Enabled list contains unregistered algorithms"
        ):
            AlgorithmRegistry.get_all(enabled=["test", "nonexistent"])

    def test_register_raises_valueerror_for_duplicate_name(self) -> None:
        """Test that register() raises ValueError for duplicate algorithm name."""
        # Arrange
        @AlgorithmRegistry.register
        class AlgorithmA(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "duplicate"

            @property
            def description(self) -> str:
                return "A"

            def detect(self, events):
                return []

        # Act & Assert
        with pytest.raises(
            ValueError, match="Algorithm name 'duplicate' is already registered"
        ):

            @AlgorithmRegistry.register
            class AlgorithmB(DetectionAlgorithm):
                @property
                def name(self) -> str:
                    return "duplicate"

                @property
                def description(self) -> str:
                    return "B"

                def detect(self, events):
                    return []

    def test_register_raises_valueerror_for_non_detection_algorithm(self) -> None:
        """Test that register() raises ValueError for class not inheriting DetectionAlgorithm."""
        # Act & Assert
        with pytest.raises(
            ValueError, match="must inherit from DetectionAlgorithm"
        ):

            @AlgorithmRegistry.register
            class NotAnAlgorithm:
                pass

    def test_register_raises_valueerror_for_empty_name(self) -> None:
        """Test that register() raises ValueError for algorithm with empty name."""
        # Act & Assert
        with pytest.raises(
            ValueError, match="must have a non-empty string name property"
        ):

            @AlgorithmRegistry.register
            class EmptyNameAlgorithm(DetectionAlgorithm):
                @property
                def name(self) -> str:
                    return ""

                @property
                def description(self) -> str:
                    return "Test"

                def detect(self, events):
                    return []

    def test_get_returns_new_instance_each_time(self) -> None:
        """Test that get() returns a new instance each time (algorithms are stateless)."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        # Act
        instance1 = AlgorithmRegistry.get("test")
        instance2 = AlgorithmRegistry.get("test")

        # Assert
        assert instance1 is not instance2  # Different instances
        assert isinstance(instance1, TestAlgorithm)
        assert isinstance(instance2, TestAlgorithm)

    def test_get_all_sorts_results_by_name(self) -> None:
        """Test that get_all() returns algorithms sorted by name."""
        # Arrange
        @AlgorithmRegistry.register
        class AlgorithmZ(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "z"

            @property
            def description(self) -> str:
                return "Z"

            def detect(self, events):
                return []

        @AlgorithmRegistry.register
        class AlgorithmA(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "a"

            @property
            def description(self) -> str:
                return "A"

            def detect(self, events):
                return []

        @AlgorithmRegistry.register
        class AlgorithmM(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "m"

            @property
            def description(self) -> str:
                return "M"

            def detect(self, events):
                return []

        # Act
        algorithms = AlgorithmRegistry.get_all()

        # Assert
        names = [alg.name for alg in algorithms]
        assert names == ["a", "m", "z"]  # Sorted alphabetically

    def test_clear_removes_all_registered_algorithms(self) -> None:
        """Test that clear() removes all registered algorithms."""
        # Arrange
        @AlgorithmRegistry.register
        class TestAlgorithm(DetectionAlgorithm):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "Test"

            def detect(self, events):
                return []

        assert len(AlgorithmRegistry.list_all()) == 1

        # Act
        AlgorithmRegistry.clear()

        # Assert
        assert len(AlgorithmRegistry.list_all()) == 0
        with pytest.raises(KeyError):
            AlgorithmRegistry.get("test")

