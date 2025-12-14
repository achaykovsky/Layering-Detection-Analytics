"""
Algorithm registry pattern for extensible detection algorithms.

Provides base class and registry for plugin-based algorithm addition.

The layering and wash trading algorithms are automatically registered when this module is imported.
"""

from .base import DetectionAlgorithm
from .layering import LayeringDetectionAlgorithm  # noqa: F401 - Import triggers registration
from .registry import AlgorithmRegistry
from .wash_trading import WashTradingDetectionAlgorithm  # noqa: F401 - Import triggers registration

__all__ = [
    "DetectionAlgorithm",
    "AlgorithmRegistry",
    "LayeringDetectionAlgorithm",
    "WashTradingDetectionAlgorithm",
]

