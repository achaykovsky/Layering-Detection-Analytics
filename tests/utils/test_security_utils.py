"""
Unit tests for security_utils module.

Tests security and sanitization helper functions.
"""

import hashlib
import os
from unittest.mock import patch

import pytest

from layering_detection.utils.security_utils import (
    get_pseudonymization_salt,
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

    def test_prefixes_equals_in_middle(self) -> None:
        """Test that = anywhere in string is prefixed (enhanced protection)."""
        # Arrange
        value = "value=123"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'value=123"
        assert result.startswith("'")

    def test_prefixes_plus_in_middle(self) -> None:
        """Test that + anywhere in string is prefixed (enhanced protection)."""
        # Arrange
        value = "value+123"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'value+123"
        assert result.startswith("'")

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

    def test_prefixes_minus_in_middle(self) -> None:
        """Test that - anywhere in string is prefixed (enhanced protection)."""
        # Arrange
        value = "value-123"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'value-123"
        assert result.startswith("'")

    def test_prefixes_at_in_middle(self) -> None:
        """Test that @ anywhere in string is prefixed (enhanced protection)."""
        # Arrange
        value = "user@domain"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'user@domain"
        assert result.startswith("'")

    def test_prefixes_tab_character(self) -> None:
        """Test that tab character anywhere triggers sanitization."""
        # Arrange
        value = "text\twith\ttabs"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'text\twith\ttabs"
        assert result.startswith("'")

    def test_prefixes_carriage_return_character(self) -> None:
        """Test that carriage return character anywhere triggers sanitization."""
        # Arrange
        value = "text\rwith\rcarriage"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'text\rwith\rcarriage"
        assert result.startswith("'")

    def test_prefixes_multiple_dangerous_characters(self) -> None:
        """Test that multiple dangerous characters trigger sanitization."""
        # Arrange
        value = "value=123+456@test"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'value=123+456@test"
        assert result.startswith("'")

    def test_handles_tab_at_start(self) -> None:
        """Test that tab character at start triggers sanitization."""
        # Arrange
        value = "\tindented"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'\tindented"
        assert result.startswith("'")

    def test_handles_carriage_return_at_start(self) -> None:
        """Test that carriage return at start triggers sanitization."""
        # Arrange
        value = "\rline"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'\rline"
        assert result.startswith("'")

    def test_handles_newline_character(self) -> None:
        """Test that newline character is handled (not dangerous for CSV injection)."""
        # Arrange
        value = "line1\nline2"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        # Newline is not a formula injection vector, so should not be prefixed
        assert result == "line1\nline2"
        assert not result.startswith("'")

    def test_handles_formula_with_equals_in_middle(self) -> None:
        """Test that formula with = in middle is sanitized."""
        # Arrange
        value = "IF(A1=10, \"yes\", \"no\")"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'IF(A1=10, \"yes\", \"no\")"
        assert result.startswith("'")

    def test_handles_complex_formula(self) -> None:
        """Test that complex formula with multiple operators is sanitized."""
        # Arrange
        value = "SUM(A1:A10)+AVG(B1:B10)-COUNT(C1:C10)"

        # Act
        result = sanitize_for_csv(value)

        # Assert
        assert result == "'SUM(A1:A10)+AVG(B1:B10)-COUNT(C1:C10)"
        assert result.startswith("'")


class TestGetPseudonymizationSalt:
    """Test suite for get_pseudonymization_salt() function."""

    def test_returns_salt_from_environment(self) -> None:
        """Test that salt is read from environment variable."""
        # Arrange
        with patch.dict(os.environ, {"PSEUDONYMIZATION_SALT": "test-salt-123"}):
            # Act
            result = get_pseudonymization_salt()

            # Assert
            assert result == "test-salt-123"

    def test_raises_error_when_salt_not_set(self) -> None:
        """Test that ValueError is raised when salt is not set."""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            # Act & Assert
            with pytest.raises(ValueError, match="PSEUDONYMIZATION_SALT environment variable is required"):
                get_pseudonymization_salt()

    def test_raises_error_when_salt_is_empty(self) -> None:
        """Test that ValueError is raised when salt is empty."""
        # Arrange
        with patch.dict(os.environ, {"PSEUDONYMIZATION_SALT": ""}):
            # Act & Assert
            with pytest.raises(ValueError, match="PSEUDONYMIZATION_SALT environment variable cannot be empty"):
                get_pseudonymization_salt()

    def test_raises_error_when_salt_is_whitespace_only(self) -> None:
        """Test that ValueError is raised when salt is whitespace only."""
        # Arrange
        with patch.dict(os.environ, {"PSEUDONYMIZATION_SALT": "   "}):
            # Act & Assert
            with pytest.raises(ValueError, match="PSEUDONYMIZATION_SALT environment variable cannot be empty"):
                get_pseudonymization_salt()


class TestPseudonymizeAccountId:
    """Test suite for pseudonymize_account_id() function."""

    def test_returns_hex_digest_for_account_id(self) -> None:
        """Test that account_id is hashed to hex digest."""
        # Arrange
        account_id = "ACC001"
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest length
        assert all(c in "0123456789abcdef" for c in result)

    def test_returns_deterministic_hash(self) -> None:
        """Test that same account_id and salt produce same hash."""
        # Arrange
        account_id = "ACC001"
        salt = "test-salt"

        # Act
        result1 = pseudonymize_account_id(account_id, salt)
        result2 = pseudonymize_account_id(account_id, salt)

        # Assert
        assert result1 == result2

    def test_different_account_ids_produce_different_hashes(self) -> None:
        """Test that different account_ids produce different hashes."""
        # Arrange
        account_id1 = "ACC001"
        account_id2 = "ACC002"
        salt = "test-salt"

        # Act
        result1 = pseudonymize_account_id(account_id1, salt)
        result2 = pseudonymize_account_id(account_id2, salt)

        # Assert
        assert result1 != result2

    def test_uses_salt_when_provided(self) -> None:
        """Test that salt is used when provided."""
        # Arrange
        account_id = "ACC001"
        salt1 = "salt1"
        salt2 = "salt2"

        # Act
        result1 = pseudonymize_account_id(account_id, salt1)
        result2 = pseudonymize_account_id(account_id, salt2)

        # Assert
        assert isinstance(result1, str)
        assert len(result1) == 64
        assert isinstance(result2, str)
        assert len(result2) == 64
        # Different salts should produce different results
        assert result1 != result2

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
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        # Should hash salt:empty_account_id
        expected = hashlib.sha256(f"{salt}:{account_id}".encode("utf-8")).hexdigest()
        assert result == expected

    def test_raises_error_when_salt_is_empty(self) -> None:
        """Test that ValueError is raised when salt is empty."""
        # Arrange
        account_id = "ACC001"
        salt = ""

        # Act & Assert
        with pytest.raises(ValueError, match="Salt is required for pseudonymization and cannot be empty"):
            pseudonymize_account_id(account_id, salt)

    def test_raises_error_when_salt_is_whitespace_only(self) -> None:
        """Test that ValueError is raised when salt is whitespace only."""
        # Arrange
        account_id = "ACC001"
        salt = "   "

        # Act & Assert
        with pytest.raises(ValueError, match="Salt is required for pseudonymization and cannot be empty"):
            pseudonymize_account_id(account_id, salt)

    def test_handles_unicode_account_id(self) -> None:
        """Test that unicode account_id is handled correctly."""
        # Arrange
        account_id = "账户001"
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_handles_special_characters_in_account_id(self) -> None:
        """Test that special characters in account_id are handled correctly."""
        # Arrange
        account_id = "ACC@001#test"
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64

    def test_handles_long_account_id(self) -> None:
        """Test that long account_id is handled correctly."""
        # Arrange
        account_id = "A" * 1000
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

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
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        # Verify it's a valid SHA-256 hex digest
        expected = hashlib.sha256(f"{salt}:{account_id}".encode("utf-8")).hexdigest()
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
        # Arrange
        salt = "test-salt"

        # Act
        result = pseudonymize_account_id(account_id, salt)

        # Assert
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)
