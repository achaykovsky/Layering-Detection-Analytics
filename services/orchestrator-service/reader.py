"""
CSV Reading Logic.

Reads input CSV files and parses TransactionEvent objects using existing CSV utilities.
"""

from __future__ import annotations

from pathlib import Path

from layering_detection.models import TransactionEvent
from layering_detection.utils.transaction_io import read_transactions

from services.shared.error_sanitization import log_error_with_context, sanitize_error_message
from services.shared.logging import get_logger

logger = get_logger(__name__)


def read_input_csv(
    path: str | Path,
    request_id: str | None = None,
) -> list[TransactionEvent]:
    """
    Read input CSV file and parse TransactionEvent objects.

    Reuses existing CSV reading utilities from layering_detection.utils.transaction_io
    to ensure compatibility with existing CSV format.

    Args:
        path: Path to input CSV file (can be string or Path object)
        request_id: Optional request ID for logging context

    Returns:
        List of TransactionEvent domain models parsed from CSV

    Raises:
        FileNotFoundError: If CSV file does not exist
        IOError: If file cannot be read
        ValueError: If CSV format is invalid or data validation fails

    Examples:
        >>> events = read_input_csv("/app/input/transactions.csv")
        >>> len(events)
        100
        >>> isinstance(events[0], TransactionEvent)
        True
    """
    csv_path = Path(path)

    # Log file reading start
    if request_id:
        logger.info(
            f"Reading input CSV: request_id={request_id}, path={csv_path}",
            extra={"request_id": request_id},
        )
    else:
        logger.info(f"Reading input CSV: path={csv_path}")

    # Validate file exists
    if not csv_path.exists():
        error = FileNotFoundError(f"Input CSV file not found: {csv_path}")
        log_error_with_context(
            logger,
            "Input CSV file not found",
            error,
            request_id=request_id,
            path=str(csv_path),
        )
        # Raise with sanitized message
        raise FileNotFoundError(sanitize_error_message(error, "Input file not found"))

    # Validate file is readable
    if not csv_path.is_file():
        error = ValueError(f"Path is not a file: {csv_path}")
        log_error_with_context(
            logger,
            "Path is not a file",
            error,
            request_id=request_id,
            path=str(csv_path),
        )
        # Raise with sanitized message
        raise ValueError(sanitize_error_message(error, "Invalid file path"))

    try:
        # Use existing CSV reading utility
        events = read_transactions(csv_path)

        # Log file reading completion
        if request_id:
            logger.info(
                f"CSV reading completed: request_id={request_id}, "
                f"path={csv_path}, events_count={len(events)}",
                extra={"request_id": request_id},
            )
        else:
            logger.info(
                f"CSV reading completed: path={csv_path}, events_count={len(events)}"
            )

        return events

    except FileNotFoundError:
        # Re-raise FileNotFoundError as-is
        raise
    except (IOError, OSError) as e:
        # File read errors
        log_error_with_context(
            logger,
            "Failed to read CSV file",
            e,
            request_id=request_id,
            path=str(csv_path),
        )
        # Raise with sanitized message
        raise IOError(sanitize_error_message(e, "Failed to read input file")) from e
    except ValueError as e:
        # CSV format or data validation errors
        log_error_with_context(
            logger,
            "Invalid CSV format or data",
            e,
            request_id=request_id,
            path=str(csv_path),
        )
        # Raise with sanitized message
        raise ValueError(sanitize_error_message(e, "Invalid CSV format or data")) from e
    except Exception as e:
        # Unexpected errors
        log_error_with_context(
            logger,
            "Unexpected error reading CSV file",
            e,
            request_id=request_id,
            path=str(csv_path),
        )
        # Re-raise original exception (will be caught and sanitized at API level)
        raise

