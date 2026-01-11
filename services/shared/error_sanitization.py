"""
Error message sanitization utilities.

Prevents information disclosure by sanitizing error messages before returning to clients.
Full error details are logged server-side only.
"""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_error_message(error: Exception | str, generic_message: str) -> str:
    """
    Sanitize error message to prevent information disclosure.

    Removes file paths, internal details, and sensitive information from error messages
    that are returned to clients. Full error details should be logged server-side.

    Args:
        error: Exception object or error message string
        generic_message: Generic message to return to client

    Returns:
        Sanitized error message safe to return to client

    Examples:
        >>> sanitize_error_message(FileNotFoundError("/app/input/secret.csv"), "Input file not found")
        'Input file not found'

        >>> sanitize_error_message("Failed to read /app/input/data.csv", "Failed to read input file")
        'Failed to read input file'

        >>> sanitize_error_message(ValueError("Invalid data in /app/input/file.csv"), "Invalid input data")
        'Invalid input data'
    """
    # If generic message is provided, use it (safest approach)
    return generic_message


def extract_file_paths(text: str) -> list[str]:
    """
    Extract file paths from error message text.

    Used for logging purposes to identify which files were involved in errors.

    Args:
        text: Error message text

    Returns:
        List of file paths found in the text

    Examples:
        >>> extract_file_paths("File not found: /app/input/data.csv")
        ['/app/input/data.csv']

        >>> extract_file_paths("Failed to read /app/input/file.csv and /app/output/result.csv")
        ['/app/input/file.csv', '/app/output/result.csv']
    """
    # Pattern to match absolute paths (Unix and Windows)
    # Matches paths starting with / or drive letter (C:, D:, etc.)
    path_pattern = r'(?:[A-Za-z]:)?(?:[/\\][^\s:<>"|?*]+)+'
    paths = re.findall(path_pattern, text)

    # Filter to only valid-looking paths (contain at least one directory separator)
    valid_paths = [p for p in paths if '/' in p or '\\' in p]

    return valid_paths


def sanitize_path_in_message(message: str) -> str:
    """
    Remove file paths from error message, replacing with generic placeholders.

    Used when we need to preserve some error context but remove sensitive paths.

    Args:
        message: Error message that may contain file paths

    Returns:
        Message with paths replaced by generic placeholders

    Examples:
        >>> sanitize_path_in_message("File not found: /app/input/data.csv")
        'File not found: [file path]'

        >>> sanitize_path_in_message("Failed to read /app/input/file.csv")
        'Failed to read [file path]'
    """
    # Pattern to match absolute paths
    path_pattern = r'(?:[A-Za-z]:)?(?:[/\\][^\s:<>"|?*]+)+'

    # Replace paths with generic placeholder
    sanitized = re.sub(path_pattern, '[file path]', message)

    return sanitized


def log_error_with_context(
    logger_instance,
    generic_message: str,
    error: Exception | str,
    request_id: str | None = None,
    **context: str | int | Path,
) -> None:
    """
    Log error with full context while returning sanitized message to client.

    Helper function to ensure consistent error logging pattern:
    - Log full error details server-side (including paths, stack traces)
    - Return generic message to client

    Args:
        logger_instance: Logger instance to use
        generic_message: Generic message for client
        error: Exception or error message string
        request_id: Optional request ID for correlation
        **context: Additional context to include in logs (e.g., path=..., file=...)

    Examples:
        >>> import logging
        >>> logger = logging.getLogger(__name__)
        >>> log_error_with_context(
        ...     logger,
        ...     "Input file not found",
        ...     FileNotFoundError("/app/input/secret.csv"),
        ...     request_id="req-123",
        ...     path="/app/input/secret.csv"
        ... )
    """
    # Build context string
    context_parts = [f"{k}={v}" for k, v in context.items()]
    context_str = ", ".join(context_parts) if context_parts else ""

    # Build log message
    error_str = str(error)
    if context_str:
        log_message = f"{generic_message}: {context_str}, error={error_str}"
    else:
        log_message = f"{generic_message}: error={error_str}"

    # Log with request ID if provided
    if request_id:
        logger_instance.error(
            log_message,
            extra={"request_id": request_id},
            exc_info=isinstance(error, Exception),
        )
    else:
        logger_instance.error(
            log_message,
            exc_info=isinstance(error, Exception),
        )

