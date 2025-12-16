"""
Result Merging Logic.

Merges suspicious sequences from all successful algorithm services and deduplicates them.
"""

from __future__ import annotations

from datetime import datetime

from services.shared.api_models import AlgorithmResponse, SuspiciousSequenceDTO
from services.shared.logging import get_logger

logger = get_logger(__name__)


def _time_windows_overlap(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
) -> bool:
    """
    Check if two time windows overlap.

    Two time windows overlap if:
    - start1 <= end2 AND start2 <= end1

    Args:
        start1: Start time of first window
        end1: End time of first window
        start2: Start time of second window
        end2: End time of second window

    Returns:
        True if windows overlap, False otherwise

    Examples:
        >>> from datetime import datetime
        >>> _time_windows_overlap(
        ...     datetime(2025, 1, 15, 10, 0),
        ...     datetime(2025, 1, 15, 11, 0),
        ...     datetime(2025, 1, 15, 10, 30),
        ...     datetime(2025, 1, 15, 11, 30),
        ... )
        True
        >>> _time_windows_overlap(
        ...     datetime(2025, 1, 15, 10, 0),
        ...     datetime(2025, 1, 15, 11, 0),
        ...     datetime(2025, 1, 15, 12, 0),
        ...     datetime(2025, 1, 15, 13, 0),
        ... )
        False
    """
    return start1 <= end2 and start2 <= end1


def _sequences_duplicate(seq1: SuspiciousSequenceDTO, seq2: SuspiciousSequenceDTO) -> bool:
    """
    Check if two sequences are duplicates based on account_id and overlapping time window.

    Sequences are considered duplicates if:
    - Same account_id
    - Time windows overlap

    Args:
        seq1: First suspicious sequence
        seq2: Second suspicious sequence

    Returns:
        True if sequences are duplicates, False otherwise
    """
    # Must have same account_id
    if seq1.account_id != seq2.account_id:
        return False

    # Parse timestamps
    start1 = datetime.fromisoformat(seq1.start_timestamp.replace("Z", "+00:00"))
    end1 = datetime.fromisoformat(seq1.end_timestamp.replace("Z", "+00:00"))
    start2 = datetime.fromisoformat(seq2.start_timestamp.replace("Z", "+00:00"))
    end2 = datetime.fromisoformat(seq2.end_timestamp.replace("Z", "+00:00"))

    # Check if time windows overlap
    return _time_windows_overlap(start1, end1, start2, end2)


def merge_results(
    results: list[AlgorithmResponse],
    request_id: str | None = None,
) -> list[SuspiciousSequenceDTO]:
    """
    Merge suspicious sequences from all successful algorithm services, deduplicating sequences.

    Extracts sequences from all services with status="success", then deduplicates based on
    account_id and overlapping time windows. Preserves sequences from successful services only.

    Args:
        results: List of AlgorithmResponse objects from algorithm services
        request_id: Optional request ID for logging context

    Returns:
        Merged and deduplicated list of SuspiciousSequenceDTO objects

    Examples:
        >>> from services.shared.api_models import AlgorithmResponse, AlgorithmStatus
        >>> results = [
        ...     AlgorithmResponse(
        ...         request_id="abc",
        ...         service_name="layering",
        ...         status="success",
        ...         results=[...],
        ...         final_status=True,
        ...     ),
        ... ]
        >>> merged = merge_results(results)
        >>> len(merged)  # Deduplicated count
    """
    # Extract sequences from successful services only
    all_sequences: list[SuspiciousSequenceDTO] = []
    successful_services: list[str] = []
    failed_services: list[str] = []

    for result in results:
        if result.status == "success" and result.results is not None:
            all_sequences.extend(result.results)
            successful_services.append(result.service_name)
        else:
            failed_services.append(result.service_name)

    total_count = len(all_sequences)

    # Log merge counts
    if request_id:
        logger.info(
            f"Merging results: request_id={request_id}, "
            f"successful_services={successful_services}, "
            f"failed_services={failed_services}, "
            f"total_sequences={total_count}",
            extra={"request_id": request_id},
        )
    else:
        logger.info(
            f"Merging results: successful_services={successful_services}, "
            f"failed_services={failed_services}, "
            f"total_sequences={total_count}"
        )

    # Deduplicate sequences
    # Keep first occurrence of each duplicate group
    deduplicated: list[SuspiciousSequenceDTO] = []
    seen_indices: set[int] = set()

    for i, seq in enumerate(all_sequences):
        if i in seen_indices:
            continue

        # Check if this sequence is a duplicate of any already added sequence
        is_duplicate = False
        for existing_seq in deduplicated:
            if _sequences_duplicate(seq, existing_seq):
                is_duplicate = True
                break

        if not is_duplicate:
            deduplicated.append(seq)
        else:
            seen_indices.add(i)

    deduplicated_count = len(deduplicated)
    removed_count = total_count - deduplicated_count

    # Log deduplication results
    if request_id:
        logger.info(
            f"Deduplication complete: request_id={request_id}, "
            f"total_sequences={total_count}, "
            f"deduplicated_count={deduplicated_count}, "
            f"removed_count={removed_count}",
            extra={"request_id": request_id},
        )
    else:
        logger.info(
            f"Deduplication complete: total_sequences={total_count}, "
            f"deduplicated_count={deduplicated_count}, "
            f"removed_count={removed_count}"
        )

    return deduplicated

