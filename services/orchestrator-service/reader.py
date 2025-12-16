"""
CSV Reading Logic.

Reads input CSV files and parses TransactionEvent objects using existing CSV utilities.
"""

from __future__ import annotations

from pathlib import Path

from layering_detection.models import TransactionEvent
from layering_detection.utils.transaction_io import read_transactions

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
        error_msg = f"Input CSV file not found: {csv_path}"
        if request_id:
            logger.error(error_msg, extra={"request_id": request_id})
        else:
            logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # Validate file is readable
    if not csv_path.is_file():
        error_msg = f"Path is not a file: {csv_path}"
        if request_id:
            logger.error(error_msg, extra={"request_id": request_id})
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

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
        error_msg = f"Failed to read CSV file {csv_path}: {str(e)}"
        if request_id:
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
        else:
            logger.error(error_msg, exc_info=True)
        raise IOError(error_msg) from e
    except ValueError as e:
        # CSV format or data validation errors
        error_msg = f"Invalid CSV format or data in {csv_path}: {str(e)}"
        if request_id:
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
        else:
            logger.error(error_msg, exc_info=True)
        raise ValueError(error_msg) from e
    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error reading CSV file {csv_path}: {str(e)}"
        if request_id:
            logger.error(error_msg, extra={"request_id": request_id}, exc_info=True)
        else:
            logger.error(error_msg, exc_info=True)
        raise

