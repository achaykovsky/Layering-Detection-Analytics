"""
Security and sanitization helpers for the layering detection analytics.
"""

from __future__ import annotations

import hashlib
import os


def sanitize_for_csv(value: str) -> str:
    """
    Make a string safer for use in CSV cells that may be opened in Excel/Sheets.

    Prevents formula injection by prefixing with a single quote if the value
    contains any formula-starting characters (=, +, -, @) or control characters
    (tab, carriage return) anywhere in the string.

    Args:
        value: String value to sanitize

    Returns:
        Sanitized string (prefixed with ' if contains dangerous characters)

    Examples:
        >>> sanitize_for_csv("=SUM(A1:A10)")
        "'=SUM(A1:A10)"
        >>> sanitize_for_csv("normal_value")
        "normal_value"
        >>> sanitize_for_csv("value=123")
        "'value=123"
        >>> sanitize_for_csv("text\\twith\\ttabs")
        "'text\\twith\\ttabs"
    """
    if not value:
        return value

    # Check for formula-starting characters anywhere in the string
    # Also check for tab and carriage return characters
    dangerous_chars = ("=", "+", "-", "@", "\t", "\r")

    # If value contains any dangerous character, prefix with quote
    if any(char in value for char in dangerous_chars):
        return "'" + value

    return value


def get_pseudonymization_salt() -> str:
    """
    Get pseudonymization salt from PSEUDONYMIZATION_SALT environment variable.

    Returns:
        Salt value as string

    Raises:
        ValueError: If PSEUDONYMIZATION_SALT environment variable is not set

    Example:
        >>> import os
        >>> os.environ["PSEUDONYMIZATION_SALT"] = "my-secret-salt"
        >>> get_pseudonymization_salt()
        'my-secret-salt'
    """
    salt = os.getenv("PSEUDONYMIZATION_SALT")
    if salt is None:
        raise ValueError(
            "PSEUDONYMIZATION_SALT environment variable is required for pseudonymization. "
            "Set it to a secure random string in production."
        )
    if not salt.strip():
        raise ValueError(
            "PSEUDONYMIZATION_SALT environment variable cannot be empty. "
            "Set it to a secure random string in production."
        )
    return salt


def pseudonymize_account_id(account_id: str, salt: str) -> str:
    """
    Return a pseudonymized representation of an account_id using SHA-256.

    Salt is required to prevent rainbow table attacks and ensure secure pseudonymization.
    Use get_pseudonymization_salt() to read salt from environment variable.

    Args:
        account_id: Account ID to pseudonymize
        salt: Salt value (required). Use get_pseudonymization_salt() to get from config.

    Returns:
        Hex-encoded SHA-256 digest (64 characters)

    Raises:
        ValueError: If salt is empty

    Example:
        >>> salt = get_pseudonymization_salt()
        >>> pseudonymize_account_id("ACC001", salt)
        'a1b2c3d4e5f6...'  # 64 hex characters
    """
    if not salt or not salt.strip():
        raise ValueError("Salt is required for pseudonymization and cannot be empty")
    material = f"{salt}:{account_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest
