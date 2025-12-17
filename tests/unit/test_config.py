"""
Unit tests for shared configuration utilities.

Tests environment variable loading, defaults, and validation.
"""

from __future__ import annotations

import os

import pytest

from services.shared.config import (
    get_logs_dir,
    get_max_retries,
    get_output_dir,
    get_port,
    get_service_url,
    get_timeout_seconds,
)


class TestGetPort:
    """Tests for get_port function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        os.environ.pop("PORT", None)

    def test_get_port_from_env_var(self) -> None:
        """Test get_port reads from PORT environment variable."""
        os.environ["PORT"] = "8001"
        assert get_port() == 8001

    def test_get_port_with_default(self) -> None:
        """Test get_port uses default when PORT not set."""
        assert get_port(default=8000) == 8000

    def test_get_port_no_default_raises_error(self) -> None:
        """Test get_port raises ValueError when PORT not set and no default."""
        with pytest.raises(ValueError, match="PORT environment variable not set"):
            get_port()

    def test_get_port_invalid_value_raises_error(self) -> None:
        """Test get_port raises ValueError for invalid port value."""
        os.environ["PORT"] = "not-a-number"
        with pytest.raises(ValueError, match="Invalid PORT environment variable"):
            get_port()

    def test_get_port_out_of_range_raises_error(self) -> None:
        """Test get_port raises ValueError for out-of-range port."""
        os.environ["PORT"] = "70000"  # > 65535
        with pytest.raises(ValueError, match="Invalid port number"):
            get_port()

    def test_get_port_zero_raises_error(self) -> None:
        """Test get_port raises ValueError for port 0."""
        os.environ["PORT"] = "0"
        with pytest.raises(ValueError, match="Invalid port number"):
            get_port()


class TestGetServiceUrl:
    """Tests for get_service_url function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        env_vars = [
            "LAYERING_SERVICE_URL",
            "WASH_TRADING_SERVICE_URL",
            "ORCHESTRATOR_SERVICE_URL",
            "AGGREGATOR_SERVICE_URL",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

    def test_get_service_url_layering_default(self) -> None:
        """Test get_service_url for layering service with default."""
        url = get_service_url("layering")
        assert url == "http://layering-service:8001"

    def test_get_service_url_wash_trading_default(self) -> None:
        """Test get_service_url for wash_trading service with default."""
        url = get_service_url("wash_trading")
        assert url == "http://wash-trading-service:8002"

    def test_get_service_url_orchestrator_default(self) -> None:
        """Test get_service_url for orchestrator service with default."""
        url = get_service_url("orchestrator")
        assert url == "http://orchestrator-service:8000"

    def test_get_service_url_aggregator_default(self) -> None:
        """Test get_service_url for aggregator service with default."""
        url = get_service_url("aggregator")
        assert url == "http://aggregator-service:8003"

    def test_get_service_url_with_custom_port(self) -> None:
        """Test get_service_url with custom port."""
        url = get_service_url("layering", port=9001)
        assert url == "http://layering-service:9001"

    def test_get_service_url_from_env_var(self) -> None:
        """Test get_service_url reads from service-specific env var."""
        os.environ["LAYERING_SERVICE_URL"] = "http://custom-host:9000"
        url = get_service_url("layering")
        assert url == "http://custom-host:9000"

    def test_get_service_url_env_var_overrides_port(self) -> None:
        """Test env var URL overrides port parameter."""
        os.environ["WASH_TRADING_SERVICE_URL"] = "http://custom-host:9000"
        url = get_service_url("wash_trading", port=8002)
        assert url == "http://custom-host:9000"  # Env var takes precedence

    def test_get_service_url_invalid_service_raises_error(self) -> None:
        """Test get_service_url raises ValueError for invalid service name."""
        with pytest.raises(ValueError, match="Invalid service_name"):
            get_service_url("invalid_service")  # type: ignore[arg-type]


class TestGetMaxRetries:
    """Tests for get_max_retries function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        os.environ.pop("MAX_RETRIES", None)

    def test_get_max_retries_from_env_var(self) -> None:
        """Test get_max_retries reads from MAX_RETRIES environment variable."""
        os.environ["MAX_RETRIES"] = "5"
        assert get_max_retries() == 5

    def test_get_max_retries_default(self) -> None:
        """Test get_max_retries uses default when MAX_RETRIES not set."""
        assert get_max_retries() == 3

    def test_get_max_retries_custom_default(self) -> None:
        """Test get_max_retries uses custom default."""
        assert get_max_retries(default=5) == 5

    def test_get_max_retries_zero_allowed(self) -> None:
        """Test get_max_retries allows zero retries."""
        os.environ["MAX_RETRIES"] = "0"
        assert get_max_retries() == 0

    def test_get_max_retries_invalid_value_raises_error(self) -> None:
        """Test get_max_retries raises ValueError for invalid value."""
        os.environ["MAX_RETRIES"] = "not-a-number"
        with pytest.raises(ValueError, match="Invalid MAX_RETRIES environment variable"):
            get_max_retries()

    def test_get_max_retries_negative_raises_error(self) -> None:
        """Test get_max_retries raises ValueError for negative value."""
        os.environ["MAX_RETRIES"] = "-1"
        with pytest.raises(ValueError, match="Invalid MAX_RETRIES"):
            get_max_retries()


class TestGetTimeoutSeconds:
    """Tests for get_timeout_seconds function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        os.environ.pop("ALGORITHM_TIMEOUT_SECONDS", None)

    def test_get_timeout_seconds_from_env_var(self) -> None:
        """Test get_timeout_seconds reads from ALGORITHM_TIMEOUT_SECONDS."""
        os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "60"
        assert get_timeout_seconds() == 60

    def test_get_timeout_seconds_default(self) -> None:
        """Test get_timeout_seconds uses default when not set."""
        assert get_timeout_seconds() == 30

    def test_get_timeout_seconds_custom_default(self) -> None:
        """Test get_timeout_seconds uses custom default."""
        assert get_timeout_seconds(default=60) == 60

    def test_get_timeout_seconds_invalid_value_raises_error(self) -> None:
        """Test get_timeout_seconds raises ValueError for invalid value."""
        os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "not-a-number"
        with pytest.raises(ValueError, match="Invalid ALGORITHM_TIMEOUT_SECONDS"):
            get_timeout_seconds()

    def test_get_timeout_seconds_zero_raises_error(self) -> None:
        """Test get_timeout_seconds raises ValueError for zero."""
        os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "0"
        with pytest.raises(ValueError, match="Invalid ALGORITHM_TIMEOUT_SECONDS"):
            get_timeout_seconds()

    def test_get_timeout_seconds_negative_raises_error(self) -> None:
        """Test get_timeout_seconds raises ValueError for negative value."""
        os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "-1"
        with pytest.raises(ValueError, match="Invalid ALGORITHM_TIMEOUT_SECONDS"):
            get_timeout_seconds()


class TestGetOutputDir:
    """Tests for get_output_dir function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        os.environ.pop("OUTPUT_DIR", None)

    def test_get_output_dir_from_env_var(self) -> None:
        """Test get_output_dir reads from OUTPUT_DIR environment variable."""
        os.environ["OUTPUT_DIR"] = "/custom/output"
        assert get_output_dir() == "/custom/output"

    def test_get_output_dir_default(self) -> None:
        """Test get_output_dir uses default when OUTPUT_DIR not set."""
        assert get_output_dir() == "/app/output"

    def test_get_output_dir_custom_default(self) -> None:
        """Test get_output_dir uses custom default."""
        assert get_output_dir(default="/tmp/output") == "/tmp/output"


class TestGetLogsDir:
    """Tests for get_logs_dir function."""

    def teardown_method(self) -> None:
        """Clean up environment variables after each test."""
        os.environ.pop("LOGS_DIR", None)

    def test_get_logs_dir_from_env_var(self) -> None:
        """Test get_logs_dir reads from LOGS_DIR environment variable."""
        os.environ["LOGS_DIR"] = "/custom/logs"
        assert get_logs_dir() == "/custom/logs"

    def test_get_logs_dir_default(self) -> None:
        """Test get_logs_dir uses default when LOGS_DIR not set."""
        assert get_logs_dir() == "/app/logs"

    def test_get_logs_dir_custom_default(self) -> None:
        """Test get_logs_dir uses custom default."""
        assert get_logs_dir(default="/tmp/logs") == "/tmp/logs"


class TestConfigurationIntegration:
    """Integration tests for configuration utilities."""

    def teardown_method(self) -> None:
        """Clean up all environment variables after each test."""
        env_vars = [
            "PORT",
            "MAX_RETRIES",
            "ALGORITHM_TIMEOUT_SECONDS",
            "OUTPUT_DIR",
            "LOGS_DIR",
            "LAYERING_SERVICE_URL",
            "WASH_TRADING_SERVICE_URL",
            "ORCHESTRATOR_SERVICE_URL",
            "AGGREGATOR_SERVICE_URL",
        ]
        for var in env_vars:
            os.environ.pop(var, None)

    def test_all_config_functions_with_defaults(self) -> None:
        """Test all config functions work with defaults."""
        port = get_port(default=8000)
        assert port == 8000

        url = get_service_url("layering")
        assert url == "http://layering-service:8001"

        retries = get_max_retries()
        assert retries == 3

        timeout = get_timeout_seconds()
        assert timeout == 30

        output_dir = get_output_dir()
        assert output_dir == "/app/output"

        logs_dir = get_logs_dir()
        assert logs_dir == "/app/logs"

    def test_all_config_functions_with_env_vars(self) -> None:
        """Test all config functions read from environment variables."""
        os.environ["PORT"] = "9000"
        os.environ["MAX_RETRIES"] = "5"
        os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "60"
        os.environ["OUTPUT_DIR"] = "/custom/output"
        os.environ["LOGS_DIR"] = "/custom/logs"
        os.environ["LAYERING_SERVICE_URL"] = "http://custom-layering:9001"

        assert get_port() == 9000
        assert get_max_retries() == 5
        assert get_timeout_seconds() == 60
        assert get_output_dir() == "/custom/output"
        assert get_logs_dir() == "/custom/logs"
        assert get_service_url("layering") == "http://custom-layering:9001"

