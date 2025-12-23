#!/usr/bin/env python3
"""
CLI entry point for layering detection analytics.

Runs the layering detection pipeline on transaction CSV files and produces
suspicious accounts and detection logs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from layering_detection.orchestrator import run_pipeline


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Detect layering manipulation patterns in transaction data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py input/transactions.csv output logs
  python main.py custom/input.csv custom/output custom/logs
        """,
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="input/transactions.csv",
        help="Path to input transactions CSV file (default: input/transactions.csv)",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="output",
        help="Directory for output CSV file (default: output)",
    )
    parser.add_argument(
        "logs_dir",
        nargs="?",
        default="logs",
        help="Directory for detection logs CSV (default: logs)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    logs_dir = Path(args.logs_dir)

    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        print(f"Please ensure the file exists and try again.", file=sys.stderr)
        return 1

    if not input_path.is_file():
        print(f"Error: Input path is not a file: {input_path}", file=sys.stderr)
        return 1

    try:
        print(f"Reading transactions from: {input_path}")
        print(f"Running layering detection...")
        
        run_pipeline(input_path, output_dir, logs_dir)
        
        suspicious_path = output_dir / "suspicious_accounts.csv"
        logs_path = logs_dir / "detections.csv"
        
        print(f"\n✓ Detection complete!")
        print(f"  Output: {suspicious_path}")
        print(f"  Logs:   {logs_path}")
        
        return 0
        
    except Exception as e:
        print(f"\nError running pipeline: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

