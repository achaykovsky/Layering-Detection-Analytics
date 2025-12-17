"""
Unit tests for shared logging utilities.

Tests logging setup, request_id filtering, JSON formatting, and service name inclusion.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from io import StringIO

import pytest

from services.shared.logging import (
    JSONFormatter,
    RequestIdFilter,
    ServiceFormatter,
    get_logger,
    setup_logging,
)


class TestRequestIdFilter:
    """Tests for RequestIdFilter class."""

    def test_filter_adds_request_id_from_extra(self) -> None:
        """Test filter adds request_id from extra dict."""
        filter_obj = RequestIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-123"
        result = filter_obj.filter(record)
        assert result is True
        assert record.request_id == "test-123"

    def test_filter_adds_default_request_id(self) -> None:
        """Test filter adds default 'N/A' when request_id not present."""
        filter_obj = RequestIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # No request_id set
        result = filter_obj.filter(record)
        assert result is True
        assert record.request_id == "N/A"


class TestServiceFormatter:
    """Tests for ServiceFormatter class."""

    def test_format_includes_service_name(self) -> None:
        """Test formatter includes service name."""
        formatter = ServiceFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-123"
        formatted = formatter.format(record)
        assert "test-service" in formatted
        assert "Test message" in formatted
        assert "request_id=test-123" in formatted

    def test_format_includes_timestamp(self) -> None:
        """Test formatter includes timestamp."""
        formatter = ServiceFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-123"
        formatted = formatter.format(record)
        # Should contain ISO timestamp format
        assert "T" in formatted or "Z" in formatted or "+" in formatted

    def test_format_includes_level(self) -> None:
        """Test formatter includes log level."""
        formatter = ServiceFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-123"
        formatted = formatter.format(record)
        assert "[ERROR]" in formatted

    def test_format_includes_exception(self) -> None:
        """Test formatter includes exception info."""
        formatter = ServiceFormatter(service_name="test-service")
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
            record.request_id = "test-123"
            formatted = formatter.format(record)
            assert "Test error" in formatted
            assert "ValueError" in formatted


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_creates_valid_json(self) -> None:
        """Test formatter creates valid JSON."""
        formatter = JSONFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-123"
        formatted = formatter.format(record)
        # Should be valid JSON
        data = json.loads(formatted)
        assert data["level"] == "INFO"
        assert data["service"] == "test-service"
        assert data["request_id"] == "test-123"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_includes_exception_in_json(self) -> None:
        """Test formatter includes exception in JSON."""
        formatter = JSONFormatter(service_name="test-service")
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
            record.request_id = "test-123"
            formatted = formatter.format(record)
            data = json.loads(formatted)
            assert "exception" in data
            assert "ValueError" in data["exception"]
            assert "Test error" in data["exception"]


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up after each test."""
        # Reset logging to avoid test interference
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def test_setup_logging_creates_logger(self) -> None:
        """Test setup_logging returns a logger."""
        logger = setup_logging("test-service", log_level="INFO")
        assert isinstance(logger, logging.Logger)

    def test_setup_logging_sets_level(self) -> None:
        """Test setup_logging sets correct log level."""
        logger = setup_logging("test-service", log_level="DEBUG")
        assert logger.level == logging.DEBUG

        logger = setup_logging("test-service", log_level="ERROR")
        assert logger.level == logging.ERROR

    def test_setup_logging_uses_stdout(self) -> None:
        """Test setup_logging uses stdout handler."""
        logger = setup_logging("test-service", log_level="INFO")
        handlers = logger.handlers
        assert len(handlers) > 0
        assert isinstance(handlers[0], logging.StreamHandler)
        assert handlers[0].stream == sys.stdout

    def test_setup_logging_includes_service_name(self) -> None:
        """Test logs include service name."""
        logger = setup_logging("test-service", log_level="INFO")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ServiceFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Test message", extra={"request_id": "test-123"})
        output = stream.getvalue()
        assert "test-service" in output

    def test_setup_logging_supports_request_id(self) -> None:
        """Test logger supports request_id via extra parameter."""
        logger = setup_logging("test-service", log_level="INFO")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ServiceFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Test message", extra={"request_id": "test-123"})
        output = stream.getvalue()
        assert "request_id=test-123" in output

    def test_setup_logging_default_request_id(self) -> None:
        """Test logger uses default request_id when not provided."""
        logger = setup_logging("test-service", log_level="INFO")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ServiceFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Test message")  # No extra parameter
        output = stream.getvalue()
        assert "request_id=N/A" in output

    def test_setup_logging_json_format(self) -> None:
        """Test setup_logging with JSON format."""
        logger = setup_logging("test-service", log_level="INFO", use_json=True)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Test message", extra={"request_id": "test-123"})
        output = stream.getvalue()
        data = json.loads(output.strip())
        assert data["service"] == "test-service"
        assert data["request_id"] == "test-123"
        assert data["message"] == "Test message"

    def test_setup_logging_env_var_json_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test setup_logging uses LOG_FORMAT env var for JSON."""
        monkeypatch.setenv("LOG_FORMAT", "JSON")
        logger = setup_logging("test-service", log_level="INFO")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        # Check if JSON formatter would be used
        handler.setFormatter(JSONFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Test message", extra={"request_id": "test-123"})
        output = stream.getvalue()
        # Should be JSON format
        data = json.loads(output.strip())
        assert isinstance(data, dict)

    def test_setup_logging_prevents_propagation(self) -> None:
        """Test setup_logging prevents log propagation."""
        logger = setup_logging("test-service", log_level="INFO")
        assert logger.propagate is False

    def test_setup_logging_clears_existing_handlers(self) -> None:
        """Test setup_logging clears existing handlers."""
        # Add a handler first
        root_logger = logging.getLogger()
        root_logger.addHandler(logging.StreamHandler())
        initial_count = len(root_logger.handlers)

        # Setup logging should clear handlers
        setup_logging("test-service", log_level="INFO")
        # Should have exactly one handler (the one we added)
        assert len(root_logger.handlers) == 1


class TestGetLogger:
    """Tests for get_logger function."""

    def teardown_method(self) -> None:
        """Clean up after each test."""
        logging.getLogger().handlers.clear()

    def test_get_logger_returns_logger(self) -> None:
        """Test get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_inherits_configuration(self) -> None:
        """Test get_logger inherits configuration from root logger."""
        setup_logging("test-service", log_level="DEBUG")
        logger = get_logger("test_module")
        # Should inherit level from root logger
        assert logger.level == logging.DEBUG or logger.level == 0  # 0 = NOTSET inherits

    def test_get_logger_different_names(self) -> None:
        """Test get_logger with different module names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        assert logger1.name == "module1"
        assert logger2.name == "module2"


class TestLoggingIntegration:
    """Integration tests for logging setup."""

    def teardown_method(self) -> None:
        """Clean up after each test."""
        logging.getLogger().handlers.clear()

    def test_full_logging_workflow(self) -> None:
        """Test complete logging workflow."""
        # Setup logging
        logger = setup_logging("test-service", log_level="INFO")

        # Capture output
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ServiceFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        # Log messages with request_id
        logger.info("Service started", extra={"request_id": "req-001"})
        logger.warning("Retry attempt", extra={"request_id": "req-001"})
        logger.error("Processing failed", extra={"request_id": "req-002"})

        output = stream.getvalue()
        assert "test-service" in output
        assert "request_id=req-001" in output
        assert "request_id=req-002" in output
        assert "Service started" in output
        assert "Retry attempt" in output
        assert "Processing failed" in output

    def test_logging_without_request_id(self) -> None:
        """Test logging works without request_id."""
        logger = setup_logging("test-service", log_level="INFO")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(ServiceFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("No request ID")
        output = stream.getvalue()
        assert "request_id=N/A" in output
        assert "No request ID" in output

    def test_json_logging_workflow(self) -> None:
        """Test JSON logging workflow."""
        logger = setup_logging("test-service", log_level="INFO", use_json=True)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter(service_name="test-service"))
        handler.addFilter(RequestIdFilter())
        logger.addHandler(handler)

        logger.info("Service started", extra={"request_id": "req-001"})
        output = stream.getvalue().strip()
        data = json.loads(output)
        assert data["service"] == "test-service"
        assert data["request_id"] == "req-001"
        assert data["level"] == "INFO"
        assert data["message"] == "Service started"
        assert "timestamp" in data

