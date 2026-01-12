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
    # Pattern: single letter drive (A-Z) followed by colon and optional path separator
    is_windows_absolute = (
        len(input_file) >= 2
        and input_file[1] == ":"
        and input_file[0].isalpha()
    )

    # If it's a Windows absolute path, handle it specially
    if is_windows_absolute:
        # On Windows: Path.is_absolute() returns True, resolve normally
        # On Unix: Path.is_absolute() returns False, treat as relative (security risk!)
        if input_file_path.is_absolute():
            # On Windows: resolve the absolute path
            input_file_resolved = input_file_path.resolve()
            # Check if it's within input_dir
            try:
                input_file_resolved.relative_to(input_dir_resolved)
                # Path is within input_dir - allow it (legitimate Windows path)
                return input_file_resolved
            except ValueError:
                # Path is outside input_dir - reject it
                raise ValueError(
                    f"Path must be within INPUT_DIR. "
                    f"Windows absolute paths outside the input directory are not allowed. "
                    f"Provided: {input_file}, Resolved: {input_file_resolved}, "
                    f"Allowed directory: {input_dir_resolved}"
                )
        else:
            # On Unix: Windows paths are not recognized as absolute
            # They would be treated as relative and resolved within input_dir
            # This is a security risk - reject Windows-style paths on Unix
            raise ValueError(
                f"Path must be within INPUT_DIR. "
                f"Windows absolute paths are not allowed on this platform. "
                f"Provided: {input_file}, Allowed directory: {input_dir_resolved}"
            )

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
        raise ValueError(
            f"Path must be within INPUT_DIR. "
            f"Provided: {input_file}, Resolved: {input_file_resolved}, "
            f"Allowed directory: {input_dir_resolved}"
        )

    return input_file_resolved

