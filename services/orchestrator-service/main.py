"""
Orchestrator Service.

FastAPI microservice for coordinating the detection pipeline: reading input CSV,
calling algorithm services in parallel, handling retries, and forwarding results to aggregator.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path to import shared utilities
# In Docker, this will be /app, in local dev it's the project root
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI

from services.shared.config import get_port
from services.shared.logging import setup_logging

# Import service-specific config
# Note: orchestrator-service directory name has hyphen, so we import via path manipulation
import importlib.util
config_path = Path(__file__).parent / "config.py"
spec = importlib.util.spec_from_file_location("orchestrator_config", config_path)
orchestrator_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_config)
get_layering_service_url = orchestrator_config.get_layering_service_url
get_wash_trading_service_url = orchestrator_config.get_wash_trading_service_url
get_aggregator_service_url = orchestrator_config.get_aggregator_service_url
get_max_retries = orchestrator_config.get_max_retries
get_timeout_seconds = orchestrator_config.get_timeout_seconds
get_input_dir = orchestrator_config.get_input_dir

# Setup logging
logger = setup_logging("orchestrator-service", log_level="INFO")

# Create FastAPI app
app = FastAPI(
    title="Orchestrator Service",
    description="Microservice for coordinating the detection pipeline",
    version="1.0.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with status and service name
    """
    logger.info("Health check requested")
    return {"status": "healthy", "service": "orchestrator-service"}


@app.get("/")
async def root() -> dict[str, str]:
    """
    Root endpoint.

    Returns:
        Service information
    """
    return {
        "service": "orchestrator-service",
        "version": "1.0.0",
        "status": "running",
        "input_dir": get_input_dir(),
        "layering_service_url": get_layering_service_url(),
        "wash_trading_service_url": get_wash_trading_service_url(),
        "aggregator_service_url": get_aggregator_service_url(),
        "max_retries": get_max_retries(),
        "timeout_seconds": get_timeout_seconds(),
    }


if __name__ == "__main__":
    import uvicorn

    port = get_port(default=8000)
    logger.info(f"Starting Orchestrator Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

