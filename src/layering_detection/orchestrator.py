"""
End-to-end orchestration for the layering detection analytics.

This module exposes a small function `run_pipeline` that:
  - Reads the transactions CSV.
  - Runs the layering detection engine.
  - Writes suspicious accounts CSV.
  - Writes per-sequence detection logs.
"""

from __future__ import annotations

from pathlib import Path

from .detector import detect_suspicious_sequences
from .io import read_transactions, write_suspicious_accounts
from .logging_utils import write_detection_logs


def run_pipeline(
    input_path: Path,
    output_dir: Path,
    logs_dir: Path,
) -> None:
    """
    Run the full layering detection pipeline.

    - input_path: path to `transactions.csv`-style input.
    - output_dir: directory where `suspicious_accounts.csv` will be written.
    - logs_dir: directory where detection logs CSV will be written.
    """
    events = read_transactions(input_path)
    sequences = detect_suspicious_sequences(events)

    output_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    suspicious_path = output_dir / "suspicious_accounts.csv"
    write_suspicious_accounts(suspicious_path, sequences)

    logs_path = logs_dir / "detections.csv"
    write_detection_logs(logs_path, sequences)



