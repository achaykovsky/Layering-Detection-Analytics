"""
End-to-end orchestration for the layering detection analytics.

This module exposes a small function `run_pipeline` that:
  - Reads the transactions CSV.
  - Runs both layering and wash trading detection engines via algorithm registry.
  - Merges results from both algorithms.
  - Writes suspicious accounts CSV.
  - Writes per-sequence detection logs.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .algorithms import AlgorithmRegistry
from .models import SuspiciousSequence
from .utils.logging_utils import write_detection_logs
from .utils.transaction_io import read_transactions, write_suspicious_accounts


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    logs_dir: Path,
) -> None:
    """
    Run the full detection pipeline with both layering and wash trading algorithms.

    Reads transaction events, runs both detection algorithms via the algorithm
    registry, merges results, and writes unified output files.

    Args:
        input_path: Path to `transactions.csv`-style input file.
        output_dir: Directory where `suspicious_accounts.csv` will be written.
        logs_dir: Directory where detection logs CSV will be written.

    Raises:
        FileNotFoundError: If input_path does not exist.
        KeyError: If required algorithms are not registered in the registry.
        ValueError: If input data is invalid.
        IOError: If output directories cannot be created or files cannot be written.

    Example:
        >>> from pathlib import Path
        >>> run_pipeline(
        ...     Path("input/transactions.csv"),
        ...     Path("output"),
        ...     Path("logs")
        ... )
    """
    # Read transaction events
    events = read_transactions(input_path)

    # Get both algorithms from registry
    layering_algorithm = AlgorithmRegistry.get("layering")
    wash_trading_algorithm = AlgorithmRegistry.get("wash_trading")

    # Run both algorithms
    layering_sequences = layering_algorithm.detect(events)
    wash_trading_sequences = wash_trading_algorithm.detect(events)

    # Merge results from both algorithms
    all_sequences: List[SuspiciousSequence] = []
    all_sequences.extend(layering_sequences)
    all_sequences.extend(wash_trading_sequences)

    # Ensure output directories exist
    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Write unified output files
    suspicious_path = output_dir / "suspicious_accounts.csv"
    write_suspicious_accounts(suspicious_path, all_sequences)

    logs_path = logs_dir / "detections.csv"
    write_detection_logs(logs_path, all_sequences)



