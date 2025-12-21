"""
Pytest configuration and fixtures for test suite.

Ensures algorithms are registered before tests run and provides common fixtures
for test data creation.
"""

import sys
from pathlib import Path

import pytest

# Add project root to sys.path for importing benchmarks module
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from layering_detection.algorithms import (  # noqa: F401
    AlgorithmRegistry,
    LayeringDetectionAlgorithm,
    WashTradingDetectionAlgorithm,
)
from services.shared.api_models import AlgorithmRequest, TransactionEventDTO
from tests.fixtures import create_algorithm_request, create_transaction_event_dto


@pytest.fixture(autouse=True, scope="function")
def ensure_algorithms_registered() -> None:
    """
    Auto-use fixture that ensures algorithms are registered before each test.
    
    This is needed because some tests (e.g., test_algorithms_registry.py) clear
    the registry, which can affect subsequent tests. This fixture re-registers
    the algorithms after any registry clears.
    """
    # Check if algorithms are registered, and manually register them if not
    registered = AlgorithmRegistry.list_all()
    
    if "layering" not in registered:
        # Manually register layering algorithm
        AlgorithmRegistry.register(LayeringDetectionAlgorithm)
    
    if "wash_trading" not in registered:
        # Manually register wash trading algorithm
        AlgorithmRegistry.register(WashTradingDetectionAlgorithm)


@pytest.fixture
def sample_transaction_event_dto() -> TransactionEventDTO:
    """
    Create sample TransactionEventDTO for testing.
    
    Uses factory function with default values. Service-specific tests can
    override this fixture or use the factory directly with custom parameters.
    """
    return create_transaction_event_dto(
        timestamp="2025-01-15T10:30:00",
        event_type="ORDER_PLACED",
    )


@pytest.fixture
def sample_algorithm_request(
    sample_transaction_event_dto: TransactionEventDTO,
) -> AlgorithmRequest:
    """
    Create sample AlgorithmRequest for testing.
    
    Uses factory function with default values. Service-specific tests can
    override this fixture or use the factory directly with custom parameters.
    """
    return create_algorithm_request(
        events=[sample_transaction_event_dto],
    )
