"""
Unit tests for security_utils module.

Tests security and sanitization helper functions.
"""

import hashlib

import pytest

from layering_detection.utils.security_utils import (
    pseudonymize_account_id,
    sanitize_for_csv,
)


class TestSanitizeForCsv:
    """Test suite for sanitize_for_csv() function."""

    def test_returns_unchanged_string_when_safe(self) -> None:
        """Test that safe strings are returned unchanged."""
        # Arrange
        value = "normal_string"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "normal_string"

    def test_prefixes_equals_sign_with_quote(self) -> None:
        """Test that strings starting with = are prefixed with quote."""
        # Arrange
        value = "=SUM(A1:A10)"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'=SUM(A1:A10)"
        assert result.startswith("'")

    def test_prefixes_plus_sign_with_quote(self) -> None:
        """Test that strings starting with + are prefixed with quote."""
        # Arrange
        value = "+1234567890"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'+1234567890"
        assert result.startswith("'")

    def test_prefixes_minus_sign_with_quote(self) -> None:
        """Test that strings starting with - are prefixed with quote."""
        # Arrange
        value = "-1234567890"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'-1234567890"
        assert result.startswith("'")

    def test_prefixes_at_sign_with_quote(self) -> None:
        """Test that strings starting with @ are prefixed with quote."""
        # Arrange
        value = "@username"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'@username"
        assert result.startswith("'")

    def test_handles_empty_string(self) -> None:
        """Test that empty string is returned unchanged."""
        # Arrange
        value = ""

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == ""

    def test_handles_single_character_equals(self) -> None:
        """Test that single character = is prefixed."""
        # Arrange
        value = "="

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'="

    def test_does_not_prefix_equals_in_middle(self) -> None:
        """Test that = in middle of string is not prefixed."""
        # Arrange
        value = "value=123"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "value=123"
        assert not result.startswith("'")

    def test_does_not_prefix_plus_in_middle(self) -> None:
        """Test that + in middle of string is not prefixed."""
        # Arrange
        value = "value+123"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "value+123"
        assert not result.startswith("'")

    def test_handles_unicode_characters(self) -> None:
        """Test that unicode characters are handled correctly."""
        # Arrange
        value = "正常字符串"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "正常字符串"

    def test_handles_unicode_starting_with_equals(self) -> None:
        """Test that unicode string starting with = is prefixed."""
        # Arrange
        value = "=正常字符串"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'=正常字符串"

    def test_handles_whitespace_only_string(self) -> None:
        """Test that whitespace-only string is returned unchanged."""
        # Arrange
        value = "   "

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "   "

    def test_handles_string_with_newlines(self) -> None:
        """Test that string with newlines is handled correctly."""
        # Arrange
        value = "line1\nline2"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "line1\nline2"

    @pytest.mark.parametrize(
        "value,expected_prefix",
        [
            ("=formula", "'"),
            ("+number", "'"),
            ("-number", "'"),
            ("@mention", "'"),
            ("normal", ""),
            ("123", ""),
            ("ABC", ""),
        ],
    )
    def test_sanitize_various_prefixes(self, value: str, expected_prefix: str) -> None:
        """Test sanitization with various string prefixes."""
        # Act
        result = sanitize_for_csv(value)

        # Assert
        if expected_prefix:
            assert result.startswith(expected_prefix)
            assert result == expected_prefix + value
        else:
            assert result == value


class TestPseudonymizeAccountId:
    """Test suite for pseudonymize_account_id() function."""

    def test_returns_hex_digest_for_account_id(self) -> None:
        """Test that account_id is hashed to hex digest."""
        # Arrange
        account_id = "ACC001"

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in result)

    def test_returns_deterministic_hash(self) -> None:
        """Test that same account_id produces same hash."""
        # Arrange
        account_id = "ACC001"

        # Act
        result1 = pseudonymize_account_id(account_id)
        result2 = pseudonymize_account_id(account_id)

        # Assert
        assert result1 == result2

    def test_different_account_ids_produce_different_hashes(self) -> None:
        """Test that different account_ids produce different hashes."""
        # Arrange
        account_id1 = "ACC001"
        account_id2 = "ACC002"

        # Act
        result1 = pseudonymize_account_id(account_id1)
        result2 = pseudonymize_account_id(account_id2)

        # Assert
        assert result1 != result2

    def test_uses_salt_when_provided(self) -> None:
        """Test that salt is used when provided."""
        # Arrange
        account_id = "ACC001"
        salt = "my_salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        # Result should be different from no-salt version
        result_no_salt = pseudonymize_account_id(account_id)
        assert result != result_no_salt

    def test_salt_produces_deterministic_hash(self) -> None:
        """Test that same salt and account_id produce same hash."""
        # Arrange
        account_id = "ACC001"
        salt = "my_salt"

        # Act
        result1 = pseudonymize_account_id(account_id, salt)
        result2 = pseudonymize_account_id(account_id, salt)

        # Assert
        assert result1 == result2

    def test_different_salts_produce_different_hashes(self) -> None:
        """Test that different salts produce different hashes for same account_id."""
        # Arrange
        account_id = "ACC001"
        salt1 = "salt1"
        salt2 = "salt2"

        # Act
        result1 = pseudonymize_account_id(account_id, salt1)
        result2 = pseudonymize_account_id(account_id, salt2)

        # Assert
        assert result1 != result2

    def test_handles_empty_account_id(self) -> None:
        """Test that empty account_id is handled correctly."""
        # Arrange
        account_id = ""

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        # Empty string should produce valid hash
        expected = hashlib.sha256("".encode("utf-8")).hexdigest()
        assert result == expected

    def test_handles_empty_salt(self) -> None:
        """Test that empty salt is handled correctly."""
        # Arrange
        account_id = "ACC001"
        salt = ""

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        # Empty salt should produce different result from None salt
        result_no_salt = pseudonymize_account_id(account_id)
        assert result != result_no_salt

    def test_handles_unicode_account_id(self) -> None:
        """Test that unicode account_id is handled correctly."""
        # Arrange
        account_id = "账户001"

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_handles_special_characters_in_account_id(self) -> None:
        """Test that special characters in account_id are handled correctly."""
        # Arrange
        account_id = "ACC@001#test"

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_handles_long_account_id(self) -> None:
        """Test that long account_id is handled correctly."""
        # Arrange
        account_id = "A" * 1000

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_handles_long_salt(self) -> None:
        """Test that long salt is handled correctly."""
        # Arrange
        account_id = "ACC001"
        salt = "S" * 1000

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_verifies_sha256_hash_format(self) -> None:
        """Test that result matches SHA-256 hash format."""
        # Arrange
        account_id = "ACC001"

        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        # Verify it's a valid SHA-256 hex digest
        expected = hashlib.sha256(account_id.encode("utf-8")).hexdigest()
        assert result == expected

    def test_verifies_salt_format(self) -> None:
        """Test that salt format is correct (salt:account_id)."""
        # Arrange
        account_id = "ACC001"
        salt = "my_salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        # Verify it matches expected format
        expected = hashlib.sha256(f"{salt}:{account_id}".encode("utf-8")).hexdigest()
        assert result == expected

    def test_handles_none_salt_explicitly(self) -> None:
        """Test that None salt is handled correctly (should be same as no salt)."""
        # Arrange
        account_id = "ACC001"

        # Act
        result_none = pseudonymize_account_id(account_id, None)
        result_no_salt = pseudonymize_account_id(account_id)

        # Assert
        assert result_none == result_no_salt

    @pytest.mark.parametrize(
        "account_id",
        [
            "ACC001",
            "ACC002",
            "test_account",
            "12345",
            "A",
            "very_long_account_id_123456789",
        ],
    )
    def test_various_account_ids(self, account_id: str) -> None:
        """Test pseudonymization with various account_id formats."""
        # Act
        result = pseudonymize_account_id(account_id)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)
