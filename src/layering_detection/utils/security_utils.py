"""
Security and sanitization helpers for the layering detection analytics.
"""

from __future__ import annotations

import hashlib


def sanitize_for_csv(value: str) -> str:
    """
    Make a string safer for use in CSV cells that may be opened in Excel/Sheets.

    If the first character is one of =,+,-,@, prefix with a single quote to
    prevent formula interpretation.
    """
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def pseudonymize_account_id(account_id: str, salt: str | None = None) -> str:
    """
    Return a pseudonymized representation of an account_id using SHA-256.

    - If a salt is provided, it is concatenated with the account_id before hashing.
    - The result is a hex-encoded string.
    """
    material = account_id if salt is None else f"{salt}:{account_id}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest
