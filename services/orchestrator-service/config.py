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


def get_api_key() -> str | None:
    """
    Get API key from environment variable.

    API key used for authenticating requests to the orchestrator service.
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


def get_layering_api_key() -> str | None:
    """
    Get API key for layering service from environment variable.

    API key used for authenticating requests to the layering service.
    Falls back to LAYERING_API_KEY, then API_KEY if not set.

    Returns:
        API key as string, or None if not set

    Examples:
        >>> import os
        >>> os.environ["LAYERING_API_KEY"] = "layering-key-123"
        >>> get_layering_api_key()
        'layering-key-123'
    """
    return os.getenv("LAYERING_API_KEY") or os.getenv("API_KEY")


def get_wash_trading_api_key() -> str | None:
    """
    Get API key for wash trading service from environment variable.

    API key used for authenticating requests to the wash trading service.
    Falls back to WASH_TRADING_API_KEY, then API_KEY if not set.

    Returns:
        API key as string, or None if not set

    Examples:
        >>> import os
        >>> os.environ["WASH_TRADING_API_KEY"] = "wash-key-123"
        >>> get_wash_trading_api_key()
        'wash-key-123'
    """
    return os.getenv("WASH_TRADING_API_KEY") or os.getenv("API_KEY")


def get_aggregator_api_key() -> str | None:
    """
    Get API key for aggregator service from environment variable.

    API key used for authenticating requests to the aggregator service.
    Falls back to AGGREGATOR_API_KEY, then API_KEY if not set.

    Returns:
        API key as string, or None if not set

    Examples:
        >>> import os
        >>> os.environ["AGGREGATOR_API_KEY"] = "aggregator-key-123"
        >>> get_aggregator_api_key()
        'aggregator-key-123'
    """
    return os.getenv("AGGREGATOR_API_KEY") or os.getenv("API_KEY")