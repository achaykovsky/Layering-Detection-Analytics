"""
Shared configuration utilities for microservices.

Provides environment variable management following 12-factor app principles.
All configuration comes from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from typing import Literal

# Service name type
ServiceName = Literal["layering", "wash_trading", "orchestrator", "aggregator"]

# Default port mappings for services
DEFAULT_PORTS: dict[ServiceName, int] = {
    "orchestrator": 8000,
    "layering": 8001,
    "wash_trading": 8002,
    "aggregator": 8003,
}

# Default service hostnames (Docker service names)
DEFAULT_SERVICE_HOSTS: dict[ServiceName, str] = {
    "orchestrator": "orchestrator-service",
    "layering": "layering-service",
    "wash_trading": "wash-trading-service",
    "aggregator": "aggregator-service",
}


def get_port(default: int | None = None) -> int:
    """
    Get port number from PORT environment variable.

    Args:
        default: Default port if PORT env var not set. If None, raises ValueError.

    Returns:
        Port number as integer

    Raises:
        ValueError: If PORT env var is not set and no default provided, or if value is invalid

    Example:
        >>> import os
        >>> os.environ["PORT"] = "8001"
        >>> get_port()
        8001

        >>> get_port(default=8000)
        8000  # If PORT not set
    """
    port_str = os.getenv("PORT")
    if port_str is None:
        if default is None:
            raise ValueError("PORT environment variable not set and no default provided")
        return default

    try:
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError(f"Invalid port number: {port} (must be 1-65535)")
        return port
    except ValueError as e:
        if "invalid literal" in str(e).lower():
            raise ValueError(f"Invalid PORT environment variable: {port_str} (must be integer)") from e
        raise


def get_service_url(service_name: ServiceName, port: int | None = None) -> str:
    """
    Get service URL from environment variable or construct from defaults.

    Checks for service-specific env var first (e.g., LAYERING_SERVICE_URL),
    then falls back to constructing URL from service name and port.

    Args:
        service_name: Service name ("layering", "wash_trading", "orchestrator", "aggregator")
        port: Port number (optional, uses default if not provided)

    Returns:
        Service URL as string (e.g., "http://layering-service:8001")

    Raises:
        ValueError: If service_name is invalid

    Example:
        >>> get_service_url("layering")
        'http://layering-service:8001'

        >>> get_service_url("layering", port=9001)
        'http://layering-service:9001'

        >>> import os
        >>> os.environ["LAYERING_SERVICE_URL"] = "http://custom-host:9000"
        >>> get_service_url("layering")
        'http://custom-host:9000'
    """
    # Map service name to env var name
    env_var_map: dict[ServiceName, str] = {
        "layering": "LAYERING_SERVICE_URL",
        "wash_trading": "WASH_TRADING_SERVICE_URL",
        "orchestrator": "ORCHESTRATOR_SERVICE_URL",
        "aggregator": "AGGREGATOR_SERVICE_URL",
    }

    # Check for service-specific URL env var first
    env_var = env_var_map.get(service_name)
    if env_var:
        url = os.getenv(env_var)
        if url:
            return url

    # Fall back to constructing URL from service name and port
    if service_name not in DEFAULT_SERVICE_HOSTS:
        raise ValueError(
            f"Invalid service_name: {service_name}. "
            f"Must be one of: {list(DEFAULT_SERVICE_HOSTS.keys())}"
        )

    host = DEFAULT_SERVICE_HOSTS[service_name]
    if port is None:
        port = DEFAULT_PORTS.get(service_name, 8000)

    return f"http://{host}:{port}"


def get_max_retries(default: int = 3) -> int:
    """
    Get maximum retry count from MAX_RETRIES environment variable.

    Args:
        default: Default retry count if MAX_RETRIES not set (default: 3)

    Returns:
        Maximum retry count as integer

    Raises:
        ValueError: If MAX_RETRIES value is invalid (not a positive integer)

    Example:
        >>> import os
        >>> os.environ["MAX_RETRIES"] = "5"
        >>> get_max_retries()
        5

        >>> get_max_retries()
        3  # Default if MAX_RETRIES not set
    """
    retries_str = os.getenv("MAX_RETRIES")
    if retries_str is None:
        return default

    try:
        retries = int(retries_str)
        if retries < 0:
            raise ValueError(f"Invalid MAX_RETRIES: {retries} (must be non-negative)")
        return retries
    except ValueError as e:
        if "invalid literal" in str(e).lower():
            raise ValueError(f"Invalid MAX_RETRIES environment variable: {retries_str} (must be integer)") from e
        raise


def get_timeout_seconds(default: int = 30) -> int:
    """
    Get timeout in seconds from ALGORITHM_TIMEOUT_SECONDS environment variable.

    Args:
        default: Default timeout if ALGORITHM_TIMEOUT_SECONDS not set (default: 30)

    Returns:
        Timeout in seconds as integer

    Raises:
        ValueError: If ALGORITHM_TIMEOUT_SECONDS value is invalid (not a positive integer)

    Example:
        >>> import os
        >>> os.environ["ALGORITHM_TIMEOUT_SECONDS"] = "60"
        >>> get_timeout_seconds()
        60

        >>> get_timeout_seconds()
        30  # Default if ALGORITHM_TIMEOUT_SECONDS not set
    """
    timeout_str = os.getenv("ALGORITHM_TIMEOUT_SECONDS")
    if timeout_str is None:
        return default

    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            raise ValueError(f"Invalid ALGORITHM_TIMEOUT_SECONDS: {timeout} (must be positive)")
        return timeout
    except ValueError as e:
        if "invalid literal" in str(e).lower():
            raise ValueError(
                f"Invalid ALGORITHM_TIMEOUT_SECONDS environment variable: {timeout_str} (must be integer)"
            ) from e
        raise


def get_output_dir(default: str = "/app/output") -> str:
    """
    Get output directory path from OUTPUT_DIR environment variable.

    Args:
        default: Default output directory if OUTPUT_DIR not set (default: /app/output)

    Returns:
        Output directory path as string

    Example:
        >>> import os
        >>> os.environ["OUTPUT_DIR"] = "/custom/output"
        >>> get_output_dir()
        '/custom/output'

        >>> get_output_dir()
        '/app/output'  # Default if OUTPUT_DIR not set
    """
    return os.getenv("OUTPUT_DIR", default)


def get_logs_dir(default: str = "/app/logs") -> str:
    """
    Get logs directory path from LOGS_DIR environment variable.

    Args:
        default: Default logs directory if LOGS_DIR not set (default: /app/logs)

    Returns:
        Logs directory path as string

    Example:
        >>> import os
        >>> os.environ["LOGS_DIR"] = "/custom/logs"
        >>> get_logs_dir()
        '/custom/logs'

        >>> get_logs_dir()
        '/app/logs'  # Default if LOGS_DIR not set
    """
    return os.getenv("LOGS_DIR", default)

