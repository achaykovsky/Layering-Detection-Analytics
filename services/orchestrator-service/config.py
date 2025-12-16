"""
Orchestrator Service Configuration.

Service-specific configuration utilities for the Orchestrator Service.
"""

from __future__ import annotations

import os

from services.shared.config import get_max_retries as get_shared_max_retries
from services.shared.config import get_service_url
from services.shared.config import get_timeout_seconds as get_shared_timeout_seconds


def get_input_dir(default: str = "/app/input") -> str:
    """
    Get input directory path from environment variable.

    Directory where input CSV files are read from.

    Args:
        default: Default directory path if INPUT_DIR env var is not set

    Returns:
        Input directory path as string

    Examples:
        >>> get_input_dir()
        '/app/input'
        >>> get_input_dir(default="/tmp/input")
        '/tmp/input'
    """
    return os.getenv("INPUT_DIR", default)


def get_layering_service_url() -> str:
    """
    Get Layering Service URL from environment variable or defaults.

    Returns:
        Layering Service URL (e.g., "http://layering-service:8001")

    Examples:
        >>> get_layering_service_url()
        'http://layering-service:8001'
    """
    return get_service_url("layering")


def get_wash_trading_service_url() -> str:
    """
    Get Wash Trading Service URL from environment variable or defaults.

    Returns:
        Wash Trading Service URL (e.g., "http://wash-trading-service:8002")

    Examples:
        >>> get_wash_trading_service_url()
        'http://wash-trading-service:8002'
    """
    return get_service_url("wash_trading")


def get_aggregator_service_url() -> str:
    """
    Get Aggregator Service URL from environment variable or defaults.

    Returns:
        Aggregator Service URL (e.g., "http://aggregator-service:8003")

    Examples:
        >>> get_aggregator_service_url()
        'http://aggregator-service:8003'
    """
    return get_service_url("aggregator")


def get_max_retries(default: int = 3) -> int:
    """
    Get maximum retry count from environment variable.

    Maximum number of retry attempts for algorithm service calls.

    Args:
        default: Default value if MAX_RETRIES env var is not set

    Returns:
        Maximum retry count as integer

    Examples:
        >>> get_max_retries()
        3
        >>> get_max_retries(default=5)
        5
    """
    return get_shared_max_retries(default=default)


def get_timeout_seconds(default: int = 30) -> int:
    """
    Get timeout in seconds from environment variable.

    Timeout per algorithm service call.

    Args:
        default: Default value if ALGORITHM_TIMEOUT_SECONDS env var is not set

    Returns:
        Timeout in seconds as integer

    Examples:
        >>> get_timeout_seconds()
        30
        >>> get_timeout_seconds(default=60)
        60
    """
    return get_shared_timeout_seconds(default=default)

