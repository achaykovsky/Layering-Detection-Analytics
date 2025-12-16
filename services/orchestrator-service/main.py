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

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

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

# Import orchestrator modules
reader_path = Path(__file__).parent / "reader.py"
spec = importlib.util.spec_from_file_location("orchestrator_reader", reader_path)
orchestrator_reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_reader)
read_input_csv = orchestrator_reader.read_input_csv

utils_path = Path(__file__).parent / "utils.py"
spec = importlib.util.spec_from_file_location("orchestrator_utils", utils_path)
orchestrator_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_utils)
generate_request_id = orchestrator_utils.generate_request_id
hash_events = orchestrator_utils.hash_events

orchestrator_path = Path(__file__).parent / "orchestrator.py"
spec = importlib.util.spec_from_file_location("orchestrator", orchestrator_path)
orchestrator_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_module)
call_all_algorithm_services = orchestrator_module.call_all_algorithm_services
EXPECTED_SERVICES = orchestrator_module.EXPECTED_SERVICES

validation_path = Path(__file__).parent / "validation.py"
spec = importlib.util.spec_from_file_location("orchestrator_validation", validation_path)
orchestrator_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_validation)
validate_all_completed = orchestrator_validation.validate_all_completed

client_path = Path(__file__).parent / "client.py"
spec = importlib.util.spec_from_file_location("orchestrator_client", client_path)
orchestrator_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orchestrator_client)
call_aggregator_service = orchestrator_client.call_aggregator_service

from services.shared.api_models import AggregateRequest, AggregateResponse, AlgorithmResponse

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

