"""
Path validation utilities for orchestrator service.

Prevents path traversal attacks by ensuring file paths are within the allowed input directory.
"""

from __future__ import annotations

from pathlib import Path


def validate_input_path(input_file: str, input_dir: str) -> Path:
    """
    Validate that input file path is within the allowed input directory.

    Prevents path traversal attacks by:
    1. Resolving both paths to absolute paths
    2. Ensuring the input file path is a subpath of input_dir
    3. Rejecting paths that escape the input directory

    Args:
        input_file: File path provided by user (can be relative or absolute)
        input_dir: Allowed input directory path

    Returns:
        Resolved Path object for the validated input file

    Raises:
        ValueError: If path is outside input_dir or contains invalid characters

    Examples:
        >>> validate_input_path("transactions.csv", "/app/input")
        PosixPath('/app/input/transactions.csv')

        >>> validate_input_path("../etc/passwd", "/app/input")
        Traceback (most recent call last):
        ...
        ValueError: Path must be within INPUT_DIR

        >>> validate_input_path("/app/input/transactions.csv", "/app/input")
        PosixPath('/app/input/transactions.csv')
    """
    # Resolve both paths to absolute paths to handle symlinks and relative paths
    input_dir_resolved = Path(input_dir).resolve()
    input_file_path = Path(input_file)

    # Detect Windows absolute paths (e.g., "C:\Windows\...") even on Unix systems
    # This prevents path traversal attempts using Windows-style paths
    is_windows_absolute = len(input_file) >= 2 and input_file[1] == ":" and input_file[0].isalpha()

    # If input_file is absolute, resolve it directly
    # If relative, resolve it relative to input_dir
    if input_file_path.is_absolute():
        input_file_resolved = input_file_path.resolve()
    else:
        # Resolve relative path against input_dir
        input_file_resolved = (input_dir_resolved / input_file_path).resolve()

    # Ensure the resolved file path is within the input directory
    # Use resolve() to handle symlinks and normalize paths
    try:
        # Check if input_file_resolved is a subpath of input_dir_resolved
        # Using relative_to() which raises ValueError if not a subpath
        input_file_resolved.relative_to(input_dir_resolved)
    except ValueError:
        # Path is outside input_dir - this is a path traversal attempt
        # If it's a Windows absolute path, provide a more specific error message
        if is_windows_absolute:
            raise ValueError(
                f"Path must be within INPUT_DIR. "
                f"Windows absolute paths outside the input directory are not allowed. "
                f"Provided: {input_file}, Resolved: {input_file_resolved}, "
                f"Allowed directory: {input_dir_resolved}"
            )
        raise ValueError(
            f"Path must be within INPUT_DIR. "
            f"Provided: {input_file}, Resolved: {input_file_resolved}, "
            f"Allowed directory: {input_dir_resolved}"
        )

    return input_file_resolved

