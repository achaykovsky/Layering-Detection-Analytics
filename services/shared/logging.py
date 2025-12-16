"""
Shared logging utilities for microservices.

Provides structured logging with request_id support, service name inclusion,
and optional JSON formatting for Docker-friendly log aggregation.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


class RequestIdFilter(logging.Filter):
    """
    Logging filter that adds request_id to log records.

    Extracts request_id from the 'extra' dict and adds it as a record attribute.
    If request_id is not present, uses 'N/A' as default.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request_id to log record.

        Args:
            record: Log record to filter

        Returns:
            True (always allows the record through)
        """
        record.request_id = getattr(record, "request_id", "N/A")
        return True


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Formats log records as JSON strings suitable for log aggregation systems.
    Includes timestamp, level, service name, request_id, and message.
    """

    def __init__(self, service_name: str) -> None:
        """
        Initialize JSON formatter.

        Args:
            service_name: Name of the service (included in all log messages)
        """
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "request_id": getattr(record, "request_id", "N/A"),
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present (excluding request_id which is already added)
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "request_id",
                    "service",
                ):
                    # Only include JSON-serializable values
                    try:
                        json.dumps(value)
                        log_data[key] = value
                    except (TypeError, ValueError):
                        # Skip non-serializable values
                        pass

        return json.dumps(log_data, ensure_ascii=False)


class ServiceFormatter(logging.Formatter):
    """
    Standard formatter that includes service name and request_id.

    Formats logs in a human-readable format suitable for development and debugging.
    """

    def __init__(self, service_name: str) -> None:
        """
        Initialize service formatter.

        Args:
            service_name: Name of the service (included in all log messages)
        """
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with service name and request_id.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Ensure request_id is set (via filter)
        request_id = getattr(record, "request_id", "N/A")

        # Format: [timestamp] [level] [service] [request_id] message
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        level = record.levelname
        message = record.getMessage()

        formatted = f"[{timestamp}] [{level}] [{self.service_name}] [request_id={request_id}] {message}"

        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    use_json: bool | None = None,
) -> logging.Logger:
    """
    Set up logging for a microservice.

    Configures root logger with:
    - Service name in all messages
    - Request ID support via extra parameter
    - Output to stdout/stderr (Docker-friendly)
    - Optional JSON formatting

    Args:
        service_name: Name of the service (e.g., "layering-service")
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_json: If True, use JSON formatting. If None, check LOG_FORMAT env var.

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging("layering-service", log_level="INFO")
        >>> logger.info("Service started", extra={"request_id": "abc-123"})
        [2025-01-15T10:30:00+00:00] [INFO] [layering-service] [request_id=abc-123] Service started

        >>> logger = setup_logging("layering-service", use_json=True)
        >>> logger.info("Service started", extra={"request_id": "abc-123"})
        {"timestamp": "2025-01-15T10:30:00+00:00", "level": "INFO", "service": "layering-service", "request_id": "abc-123", "message": "Service started"}
    """
    # Determine JSON formatting preference
    if use_json is None:
        log_format_env = os.getenv("LOG_FORMAT", "").upper()
        use_json = log_format_env == "JSON"

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Create console handler (stdout for INFO and below, stderr for WARNING and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Add request_id filter
    request_id_filter = RequestIdFilter()
    console_handler.addFilter(request_id_filter)

    # Set formatter
    if use_json:
        formatter = JSONFormatter(service_name=service_name)
    else:
        formatter = ServiceFormatter(service_name=service_name)

    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    The logger inherits the configuration from the root logger set up by setup_logging().

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request", extra={"request_id": "abc-123"})
    """
    return logging.getLogger(name)

