"""
Unit tests for layering service LRU cache implementation.

Tests cache size limits and LRU eviction behavior.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.shared.api_models import SuspiciousSequenceDTO

# Import layering service main module
project_root = Path(__file__).parent.parent.parent
main_path = project_root / "services" / "layering-service" / "main.py"
spec = importlib.util.spec_from_file_location("layering_main", main_path)
layering_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layering_main)


class TestLRUCacheSizeLimit:
    """Tests for LRU cache size limits."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create FastAPI test client."""
        app = layering_main.app
        return TestClient(app)

    def test_cache_size_limited(self) -> None:
        """Test that cache size is limited to configured maximum."""
        # Arrange - Get cache from module
        cache = layering_main._result_cache

        # Assert - Cache should have maxsize attribute
        assert hasattr(cache, "maxsize")
        assert cache.maxsize > 0
        assert cache.maxsize == 1000  # Default cache size

    def test_cache_eviction_when_full(self) -> None:
        """Test that cache evicts least recently used items when full."""
        # Arrange - Create a small cache for testing
        from cachetools import LRUCache

        test_cache = LRUCache(maxsize=3)

        # Act - Fill cache beyond capacity
        test_cache[("req1", "fp1")] = []
        test_cache[("req2", "fp2")] = []
        test_cache[("req3", "fp3")] = []
        assert len(test_cache) == 3

        # Add one more - should evict least recently used (req1)
        test_cache[("req4", "fp4")] = []

        # Assert - Cache should still be size 3, req1 should be evicted
        assert len(test_cache) == 3
        assert ("req1", "fp1") not in test_cache
        assert ("req2", "fp2") in test_cache
        assert ("req3", "fp3") in test_cache
        assert ("req4", "fp4") in test_cache

    def test_cache_lru_eviction_order(self) -> None:
        """Test that cache evicts items in LRU order."""
        # Arrange - Create a small cache
        from cachetools import LRUCache

        test_cache = LRUCache(maxsize=3)

        # Act - Fill cache and access items to change LRU order
        test_cache[("req1", "fp1")] = []
        test_cache[("req2", "fp2")] = []
        test_cache[("req3", "fp3")] = []

        # Access req1 to make it more recently used
        _ = test_cache[("req1", "fp1")]

        # Add new item - should evict req2 (least recently used, not req1)
        test_cache[("req4", "fp4")] = []

        # Assert - req2 should be evicted, not req1
        assert len(test_cache) == 3
        assert ("req1", "fp1") in test_cache
        assert ("req2", "fp2") not in test_cache
        assert ("req3", "fp3") in test_cache
        assert ("req4", "fp4") in test_cache

    def test_cache_hit_returns_cached_result(
        self, client: TestClient
    ) -> None:
        """Test that cache hits return cached results without processing."""
        # Arrange - Create request
        from uuid import uuid4

        request_id = str(uuid4())
        event_fingerprint = "a" * 64
        request_body = {
            "request_id": request_id,
            "event_fingerprint": event_fingerprint,
            "events": [
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": 1000,
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        # Act - First request (cache miss, will process)
        response1 = client.post(
            "/detect",
            json=request_body,
            headers={"X-API-Key": "test-key"},
        )

        # Second request with same fingerprint (cache hit)
        response2 = client.post(
            "/detect",
            json=request_body,
            headers={"X-API-Key": "test-key"},
        )

        # Assert - Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200

        # Both should return same results (from cache on second request)
        data1 = response1.json()
        data2 = response2.json()
        assert data1["results"] == data2["results"]

    def test_cache_miss_processes_request(
        self, client: TestClient
    ) -> None:
        """Test that cache misses trigger processing."""
        # Arrange - Create unique request
        from uuid import uuid4

        request_id = str(uuid4())
        event_fingerprint = "b" * 64  # Different fingerprint
        request_body = {
            "request_id": request_id,
            "event_fingerprint": event_fingerprint,
            "events": [
                {
                    "timestamp": "2025-01-15T10:30:00Z",
                    "account_id": "ACC001",
                    "product_id": "IBM",
                    "side": "BUY",
                    "price": "100.50",
                    "quantity": 1000,
                    "event_type": "ORDER_PLACED",
                }
            ],
        }

        # Act
        response = client.post(
            "/detect",
            json=request_body,
            headers={"X-API-Key": "test-key"},
        )

        # Assert - Should process and return results
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "results" in data

    def test_cache_size_configurable_via_env_var(self) -> None:
        """Test that cache size can be configured via CACHE_SIZE environment variable."""
        # Arrange - Test get_cache_size function directly
        from services.shared.config import get_cache_size
        import os

        original_cache_size = os.getenv("CACHE_SIZE")
        try:
            # Set custom cache size
            os.environ["CACHE_SIZE"] = "500"

            # Assert - get_cache_size should return configured value
            cache_size = get_cache_size(default=1000)
            assert cache_size == 500

            # Test with different value
            os.environ["CACHE_SIZE"] = "200"
            cache_size = get_cache_size(default=1000)
            assert cache_size == 200
        finally:
            # Restore original value
            if original_cache_size is None:
                os.environ.pop("CACHE_SIZE", None)
            else:
                os.environ["CACHE_SIZE"] = original_cache_size

    def test_cache_prevents_memory_exhaustion(self) -> None:
        """Test that cache prevents unbounded memory growth."""
        # Arrange - Create small cache
        from cachetools import LRUCache

        test_cache = LRUCache(maxsize=10)

        # Act - Add many items
        for i in range(100):
            test_cache[(f"req{i}", f"fp{i}")] = [{"test": "data"}]

        # Assert - Cache should never exceed maxsize
        assert len(test_cache) == 10
        assert test_cache.maxsize == 10

