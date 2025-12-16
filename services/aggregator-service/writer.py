"""
CSV Writing Logic.

Writes suspicious_accounts.csv and detections.csv files using existing CSV utilities.
"""

from __future__ import annotations

from pathlib import Path

from typing import TYPE_CHECKING

from layering_detection.models import SuspiciousSequence
from layering_detection.utils.logging_utils import write_detection_logs
from layering_detection.utils.transaction_io import write_suspicious_accounts

from services.shared.converters import dto_to_suspicious_sequence
from services.shared.logging import get_logger

if TYPE_CHECKING:
    from services.shared.api_models import SuspiciousSequenceDTO

logger = get_logger(__name__)


def write_output_files(
    sequences: list[SuspiciousSequence],
    output_dir: str | Path,
    logs_dir: str | Path | None = None,
    request_id: str | None = None,
) -> None:
    """
    Write output CSV files: suspicious_accounts.csv and detections.csv.

    Writes two CSV files:
    1. suspicious_accounts.csv: All suspicious sequences with detection details
    2. detections.csv: Per-sequence detection logs with timing information

    Uses existing CSV writing utilities from layering_detection.utils to ensure
    backward compatibility with monolithic output format.

    Args:
        sequences: List of SuspiciousSequence domain models to write
        output_dir: Directory where suspicious_accounts.csv will be written
        logs_dir: Directory where detections.csv will be written (defaults to output_dir)
        request_id: Optional request ID for logging context

    Raises:
        IOError: If file write fails (permission denied, disk full, etc.)
        OSError: If directory creation fails

    Examples:
        >>> from datetime import datetime
        >>> from layering_detection.models import SuspiciousSequence
        >>> sequences = [
        ...     SuspiciousSequence(
        ...         account_id="ACC001",
        ...         product_id="IBM",
        ...         start_timestamp=datetime(2025, 1, 15, 10, 0),
        ...         end_timestamp=datetime(2025, 1, 15, 11, 0),
        ...         total_buy_qty=5000,
        ...         total_sell_qty=0,
        ...         detection_type="LAYERING",
        ...     ),
        ... ]
        >>> write_output_files(sequences, "/app/output", "/app/logs")
    """
    output_dir_path = Path(output_dir)
    logs_dir_path = Path(logs_dir) if logs_dir else output_dir_path

    # Ensure directories exist
    output_dir_path.mkdir(parents=True, exist_ok=True)
    logs_dir_path.mkdir(parents=True, exist_ok=True)

    # File paths
    suspicious_accounts_path = output_dir_path / "suspicious_accounts.csv"
    detections_path = logs_dir_path / "detections.csv"

    # Log file write start
    if request_id:
        logger.info(
            f"Writing output files: request_id={request_id}, "
            f"sequences_count={len(sequences)}, "
            f"output_dir={output_dir_path}, "
            f"logs_dir={logs_dir_path}",
            extra={"request_id": request_id},
        )
    else:
        logger.info(
            f"Writing output files: sequences_count={len(sequences)}, "
            f"output_dir={output_dir_path}, "
            f"logs_dir={logs_dir_path}"
        )

    try:
        # Write suspicious_accounts.csv
        write_suspicious_accounts(suspicious_accounts_path, sequences)
        if request_id:
            logger.info(
                f"Wrote suspicious_accounts.csv: request_id={request_id}, "
                f"path={suspicious_accounts_path}, "
                f"sequences_count={len(sequences)}",
                extra={"request_id": request_id},
            )
        else:
            logger.info(
                f"Wrote suspicious_accounts.csv: path={suspicious_accounts_path}, "
                f"sequences_count={len(sequences)}"
            )

        # Write detections.csv
        write_detection_logs(detections_path, sequences)
        if request_id:
            logger.info(
                f"Wrote detections.csv: request_id={request_id}, "
                f"path={detections_path}, "
                f"sequences_count={len(sequences)}",
                extra={"request_id": request_id},
            )
        else:
            logger.info(
                f"Wrote detections.csv: path={detections_path}, "
                f"sequences_count={len(sequences)}"
            )

    except (IOError, OSError) as e:
        # Log error with context
        error_msg = f"Failed to write output files: {str(e)}"
        if request_id:
            logger.error(
                error_msg,
                extra={"request_id": request_id},
                exc_info=True,
            )
        else:
            logger.error(error_msg, exc_info=True)
        raise


def write_output_files_from_dtos(
    sequences: list["SuspiciousSequenceDTO"],
    output_dir: str | Path,
    logs_dir: str | Path | None = None,
    request_id: str | None = None,
) -> None:
    """
    Write output CSV files from SuspiciousSequenceDTO objects.

    Converts DTOs to domain models before writing to ensure compatibility with
    existing CSV writing utilities.

    Args:
        sequences: List of SuspiciousSequenceDTO objects to write
        output_dir: Directory where suspicious_accounts.csv will be written
        logs_dir: Directory where detections.csv will be written (defaults to output_dir)
        request_id: Optional request ID for logging context

    Raises:
        IOError: If file write fails
        OSError: If directory creation fails
        ValueError: If DTO conversion fails

    Examples:
        >>> from services.shared.api_models import SuspiciousSequenceDTO
        >>> dtos = [
        ...     SuspiciousSequenceDTO(
        ...         account_id="ACC001",
        ...         product_id="IBM",
        ...         start_timestamp="2025-01-15T10:00:00",
        ...         end_timestamp="2025-01-15T11:00:00",
        ...         total_buy_qty=5000,
        ...         total_sell_qty=0,
        ...         detection_type="LAYERING",
        ...     ),
        ... ]
        >>> write_output_files_from_dtos(dtos, "/app/output", "/app/logs")
    """
    # Convert DTOs to domain models
    domain_sequences: list[SuspiciousSequence] = []
    for dto in sequences:
        try:
            domain_seq = dto_to_suspicious_sequence(dto)
            domain_sequences.append(domain_seq)
        except Exception as e:
            error_msg = f"Failed to convert DTO to domain model: {str(e)}"
            if request_id:
                logger.error(
                    error_msg,
                    extra={"request_id": request_id},
                    exc_info=True,
                )
            else:
                logger.error(error_msg, exc_info=True)
            raise ValueError(error_msg) from e

    # Write files using domain models
    write_output_files(domain_sequences, output_dir, logs_dir, request_id)

