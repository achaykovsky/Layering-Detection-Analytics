"""
Base test class for algorithm tests.

This module provides a base class that contains shared test methods for algorithm
tests, eliminating duplicate test code between wash trading and layering algorithm tests.

## When to Use BaseAlgorithmTest

**Use BaseAlgorithmTest when:**
- Writing tests for a new algorithm that follows the registry pattern
- You need shared test methods (registry, filtering, empty handling)
- You want to reduce duplicate test code between similar algorithms

**Don't use BaseAlgorithmTest when:**
- Your algorithm has a completely different interface
- Shared test methods don't apply to your algorithm
- You need to test algorithm-specific functionality not covered by base class

## Usage

Subclass BaseAlgorithmTest and implement the required abstract properties:

```python
class TestMyAlgorithm(BaseAlgorithmTest):
    @property
    def algorithm_name(self) -> str:
        return "my_algorithm"
    
    @property
    def expected_description_keywords(self) -> list[str]:
        return ["my", "algorithm"]
```

The base class provides 7 shared test methods that automatically work with
your algorithm configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pytest

from layering_detection.algorithms.registry import AlgorithmRegistry
from layering_detection.models import TransactionEvent


class BaseAlgorithmTest(ABC):
    """
    Abstract base class for algorithm tests.

    Subclasses must implement abstract properties to provide algorithm-specific
    configuration values.

    ## Inherited Test Methods

    The base class provides these shared test methods:
    - `test_registered_in_registry()` - Algorithm is registered
    - `test_name_property_returns_correct_name()` - Name property works
    - `test_description_property_returns_description()` - Description contains keywords
    - `test_filter_events_handles_empty_list()` - Empty list filtering
    - `test_detect_handles_empty_event_list()` - Empty list detection
    - `test_can_be_retrieved_via_registry_get()` - Registry retrieval
    - `test_can_be_called_via_registry()` - Registry calling

    ## Algorithm-Specific Tests

    Keep algorithm-specific tests in your subclass. For example:
    - Tests for algorithm-specific filtering logic
    - Tests for algorithm-specific detection behavior
    - Tests for algorithm-specific configuration

    Example:
        >>> class TestWashTradingAlgorithm(BaseAlgorithmTest):
        ...     @property
        ...     def algorithm_name(self) -> str:
        ...         return "wash_trading"
        ...     
        ...     def test_filter_returns_only_trade_executed(self):
        ...         # Algorithm-specific test
        ...         pass
    """

    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """
        Algorithm name used in registry (e.g., "wash_trading", "layering").

        Returns:
            Algorithm name string.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def expected_description_keywords(self) -> list[str]:
        """
        Expected keywords that should appear in algorithm description.

        Returns:
            List of keyword strings (case-insensitive matching).
        """
        raise NotImplementedError

    def test_registered_in_registry(self) -> None:
        """
        Test that algorithm is registered in AlgorithmRegistry.

        Verifies that the algorithm can be retrieved from the registry and
        appears in the list of all registered algorithms.
        """
        # Act
        algorithm = AlgorithmRegistry.get(self.algorithm_name)

        # Assert
        assert algorithm.name == self.algorithm_name
        assert self.algorithm_name in AlgorithmRegistry.list_all()

    def test_name_property_returns_correct_name(self) -> None:
        """
        Test that name property returns correct algorithm name.

        Verifies that the algorithm's name property matches the expected
        algorithm name.
        """
        # Arrange
        algorithm = AlgorithmRegistry.get(self.algorithm_name)

        # Act
        name = algorithm.name

        # Assert
        assert name == self.algorithm_name

    def test_description_property_returns_description(self) -> None:
        """
        Test that description property returns non-empty description with expected keywords.

        Verifies that the algorithm has a description and that it contains
        expected keywords related to the algorithm's purpose.
        """
        # Arrange
        algorithm = AlgorithmRegistry.get(self.algorithm_name)

        # Act
        description = algorithm.description

        # Assert
        assert isinstance(description, str)
        assert len(description) > 0
        description_lower = description.lower()
        # At least one expected keyword should be present
        assert any(
            keyword.lower() in description_lower for keyword in self.expected_description_keywords
        ), f"Description should contain at least one of: {self.expected_description_keywords}"

    def test_filter_events_handles_empty_list(self) -> None:
        """
        Test that filter_events() handles empty event list.

        Verifies that filtering an empty list returns an empty list without
        raising exceptions.
        """
        # Arrange
        algorithm = AlgorithmRegistry.get(self.algorithm_name)
        events: list[TransactionEvent] = []

        # Act
        filtered = algorithm.filter_events(events)

        # Assert
        assert filtered == []

    def test_detect_handles_empty_event_list(self) -> None:
        """
        Test that detect() handles empty event list.

        Verifies that detecting on an empty list returns an empty list without
        raising exceptions.
        """
        # Arrange
        algorithm = AlgorithmRegistry.get(self.algorithm_name)
        events: list[TransactionEvent] = []

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert sequences == []

    def test_can_be_retrieved_via_registry_get(self) -> None:
        """
        Test that algorithm can be retrieved via AlgorithmRegistry.get().

        Verifies that the algorithm can be retrieved from the registry and
        has the expected interface (detect and filter_events methods).
        """
        # Act
        algorithm = AlgorithmRegistry.get(self.algorithm_name)

        # Assert
        assert algorithm is not None
        assert algorithm.name == self.algorithm_name
        assert hasattr(algorithm, "detect")
        assert callable(algorithm.detect)
        assert hasattr(algorithm, "filter_events")
        assert callable(algorithm.filter_events)

    def test_can_be_called_via_registry(self) -> None:
        """
        Test that algorithm can be called via registry.

        Verifies that the algorithm retrieved from the registry can be called
        with events and returns a list of sequences.
        """
        # Arrange
        algorithm = AlgorithmRegistry.get(self.algorithm_name)
        from datetime import datetime, timezone

        from tests.fixtures import create_transaction_event

        events = [
            create_transaction_event(
                timestamp=datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc),
                event_type="TRADE_EXECUTED" if self.algorithm_name == "wash_trading" else "ORDER_PLACED",
            )
        ]

        # Act
        sequences = algorithm.detect(events)

        # Assert
        assert isinstance(sequences, list)

