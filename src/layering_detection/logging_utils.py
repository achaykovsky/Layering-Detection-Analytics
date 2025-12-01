"""
Logging utilities for layering detection analytics.

This module provides a small helper to emit per-sequence detection logs
into a CSV file under the configured logs directory.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .models import SuspiciousSequence
from .security_utils import sanitize_for_csv, pseudonymize_account_id


def write_detection_logs(
    path: Path,
    sequences: Iterable[SuspiciousSequence],
    pseudonymize_accounts: bool = False,
    salt: str | None = None,
) -> None:
    """
    Write detection logs for each suspicious sequence to a CSV file.

    The log schema (one row per sequence) is, per the assignment logging section:
    - account_id
    - product_id
    - order_timestamps        (semicolon-separated ISO timestamps)
    - duration_seconds        (float seconds between start and end)
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "account_id",
        "product_id",
        "order_timestamps",
        "duration_seconds",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for seq in sequences:
            account_id = (
                pseudonymize_account_id(seq.account_id, salt=salt)
                if pseudonymize_accounts
                else sanitize_for_csv(seq.account_id)
            )
            product_id = sanitize_for_csv(seq.product_id)
            duration_seconds = (seq.end_timestamp - seq.start_timestamp).total_seconds()
            order_timestamps = ";".join(ts.isoformat() for ts in seq.order_timestamps)
            writer.writerow(
                {
                    "account_id": account_id,
                    "product_id": product_id,
                    "order_timestamps": order_timestamps,
                    "duration_seconds": f"{duration_seconds:.3f}",
                }
            )



