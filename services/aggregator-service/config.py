"""
Aggregator Service Configuration.

Service-specific configuration utilities for the Aggregator Service.
"""

from __future__ import annotations

import os


def get_output_dir(default: str = "/app/output") -> str:
    """
    Get output directory path from environment variable.

    Directory where output CSV files (suspicious_accounts.csv, detections.csv) are written.

    Args:
        default: Default directory path if OUTPUT_DIR env var is not set

    Returns:
        Output directory path as string

    Examples:
        >>> get_output_dir()
        '/app/output'
        >>> get_output_dir(default="/tmp/output")
        '/tmp/output'
    """
    return os.getenv("OUTPUT_DIR", default)


def get_logs_dir(default: str = "/app/logs") -> str:
    """
    Get logs directory path from environment variable.

    Directory where log files are written.

    Args:
        default: Default directory path if LOGS_DIR env var is not set

    Returns:
        Logs directory path as string

    Examples:
        >>> get_logs_dir()
        '/app/logs'
        >>> get_logs_dir(default="/tmp/logs")
        '/tmp/logs'
    """
    return os.getenv("LOGS_DIR", default)


def get_validation_strict(default: bool = True) -> bool:
    """
    Get validation strict mode from environment variable.

    If True, validation failures raise exceptions. If False, warnings are logged but processing continues.

    Args:
        default: Default value if VALIDATION_STRICT env var is not set

    Returns:
        True if validation should be strict (fail fast), False otherwise

    Examples:
        >>> get_validation_strict()
        True
        >>> get_validation_strict(default=False)
        False
    """
    value = os.getenv("VALIDATION_STRICT", str(default)).lower()
    return value in ("true", "1", "yes")


def get_allow_partial_results(default: bool = False) -> bool:
    """
    Get allow partial results flag from environment variable.

    If True, allows merging results even if some services failed. If False, requires all services to complete.

    Args:
        default: Default value if ALLOW_PARTIAL_RESULTS env var is not set

    Returns:
        True if partial results are allowed, False otherwise

    Examples:
        >>> get_allow_partial_results()
        False
        >>> get_allow_partial_results(default=True)
        True
    """
    value = os.getenv("ALLOW_PARTIAL_RESULTS", str(default)).lower()
    return value in ("true", "1", "yes")

