"""
Wash Trading Service Configuration.

Service-specific configuration utilities for the Wash Trading Service.
"""

from __future__ import annotations

import os


def get_api_key() -> str | None:
    """
    Get API key from environment variable.

    API key used for authenticating requests to the wash trading service.
    If not set, authentication is disabled (for development only).

    Returns:
        API key as string, or None if not set

    Examples:
        >>> import os
        >>> os.environ["API_KEY"] = "test-key-123"
        >>> get_api_key()
        'test-key-123'
        >>> del os.environ["API_KEY"]
        >>> get_api_key() is None
        True
    """
    return os.getenv("API_KEY")

