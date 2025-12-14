"""
Abstract base class for detection algorithms.

Defines the interface that all detection algorithms must implement,
enabling plugin-based architecture for extensible algorithm addition.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List

from ..models import SuspiciousSequence, TransactionEvent
from ..utils.transaction_io import read_transactions, write_suspicious_accounts


class DetectionAlgorithm(ABC):
    """
    Abstract base class for all detection algorithms.
    
    All detection algorithms must inherit from this class and implement
    the required abstract methods. This enables a plugin-based architecture
    where new algorithms can be added without modifying core code.
    
    Example:
        >>> class MyAlgorithm(DetectionAlgorithm):
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_algorithm"
        ...     
        ...     @property
        ...     def description(self) -> str:
        ...         return "My custom detection algorithm"
        ...     
        ...     def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        ...         # Implementation here
        ...         return []
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this algorithm.
        
        Returns:
            Algorithm name (e.g., "layering", "wash_trading").
            Must be unique across all registered algorithms.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what this algorithm detects.
        
        Returns:
            Description string explaining the algorithm's purpose
            and what patterns it identifies.
        """
        pass

    @abstractmethod
    def detect(self, events: Iterable[TransactionEvent]) -> List[SuspiciousSequence]:
        """
        Detect suspicious sequences in the given events.
        
        This is the core detection method that all algorithms must implement.
        It receives an iterable of transaction events and returns a list of
        detected suspicious sequences.
        
        Args:
            events: Iterable of transaction events to analyze.
                Events may be filtered by `filter_events()` before calling this method.
        
        Returns:
            List of detected suspicious sequences. Empty list if no sequences detected.
        
        Raises:
            ValueError: If events are invalid or algorithm-specific validation fails.
        """
        pass

    def filter_events(self, events: Iterable[TransactionEvent]) -> List[TransactionEvent]:
        """
        Filter events before detection (optional preprocessing step).
        
        Default implementation returns all events. Subclasses can override
        to filter events by type, side, or other criteria before detection.
        
        Args:
            events: Iterable of transaction events to filter.
        
        Returns:
            Filtered list of events. Default implementation returns all events.
        
        Example:
            >>> class TradeOnlyAlgorithm(DetectionAlgorithm):
            ...     def filter_events(self, events):
            ...         return [e for e in events if e.event_type == "TRADE_EXECUTED"]
        """
        return list(events)

    def run_from_volume(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
    ) -> None:
        """
        Run algorithm from Docker volume (for containerized execution).
        
        Reads transaction events from input directory, runs detection,
        and writes results to output directory. Designed for Docker Compose
        and containerized deployments.
        
        Args:
            input_dir: Path to directory containing input CSV files.
                Expected file: `transactions.csv`
            output_dir: Path to directory where results will be written.
                Creates `suspicious_accounts.csv` with detection results.
        
        Raises:
            FileNotFoundError: If input directory or file does not exist.
            ValueError: If input data is invalid.
            IOError: If output directory cannot be created or written to.
        
        Example:
            >>> algorithm = MyAlgorithm()
            >>> algorithm.run_from_volume("/app/data/events", "/app/data/results")
        """
        input_path = Path(input_dir) / "transactions.csv"
        output_path = Path(output_dir) / "suspicious_accounts.csv"

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Ensure output directory exists
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise IOError(f"Cannot create output directory: {output_path.parent}") from e

        # Read events (may raise ValueError for invalid CSV format)
        try:
            events = read_transactions(input_path)
        except ValueError as e:
            raise ValueError(f"Invalid transaction data in {input_path}: {e}") from e

        # Filter events (algorithm-specific preprocessing)
        filtered_events = self.filter_events(events)

        # Run detection
        sequences = self.detect(filtered_events)

        # Write results (may raise IOError for write failures)
        try:
            write_suspicious_accounts(output_path, sequences)
        except OSError as e:
            raise IOError(f"Cannot write results to {output_path}: {e}") from e

