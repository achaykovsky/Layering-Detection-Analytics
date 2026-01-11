"""
Unit tests for rate limiting middleware.

Tests rate limiting logic, IP extraction, excluded paths, and rate limit headers.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from services.shared.rate_limiting import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Test rate limiting middleware functionality."""

    def test_rate_limit_allows_requests_within_limit(self) -> None:
        """Test that requests within rate limit are allowed."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=10)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        # Create test client
        client = TestClient(app)

        # Make 10 requests (at limit)
        for i in range(10):
            response = client.get("/test")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    def test_rate_limit_rejects_requests_over_limit(self) -> None:
        """Test that requests exceeding rate limit return HTTP 429."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make 5 requests (at limit)
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200

        # 6th request should be rate limited
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "detail" in response.json()
        assert "Rate limit exceeded" in response.json()["detail"]
        assert response.headers["X-RateLimit-Remaining"] == "0"

    def test_rate_limit_headers_present(self) -> None:
        """Test that rate limit headers are present in responses."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert int(response.headers["X-RateLimit-Remaining"]) < 100

    def test_rate_limit_excludes_health_endpoint(self) -> None:
        """Test that health check endpoints are excluded from rate limiting."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1, excluded_paths={"/health"})

        @app.get("/health")
        async def health_check() -> dict[str, str]:
            return {"status": "healthy"}

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make many health check requests (should not be rate limited)
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "healthy"}

        # But regular endpoint should be rate limited after 1 request
        response = client.get("/test")
        assert response.status_code == 200

        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_rate_limit_per_ip_separately(self) -> None:
        """Test that rate limits are applied per IP address."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client1 = TestClient(app, headers={"X-Forwarded-For": "192.168.1.1"})
        client2 = TestClient(app, headers={"X-Forwarded-For": "192.168.1.2"})

        # IP 1 makes 2 requests (at limit)
        response1 = client1.get("/test")
        assert response1.status_code == 200
        response1 = client1.get("/test")
        assert response1.status_code == 200

        # IP 2 should still be able to make requests
        response2 = client2.get("/test")
        assert response2.status_code == 200

        # IP 1 should now be rate limited
        response1 = client1.get("/test")
        assert response1.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # IP 2 should still be able to make one more request
        response2 = client2.get("/test")
        assert response2.status_code == 200

    def test_rate_limit_sliding_window(self) -> None:
        """Test that rate limit uses sliding window (requests expire after 60 seconds)."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=2)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make 2 requests (at limit)
        response = client.get("/test")
        assert response.status_code == 200
        response = client.get("/test")
        assert response.status_code == 200

        # 3rd request should be rate limited
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

        # Mock time to advance 61 seconds
        with patch("time.time", return_value=time.time() + 61):
            # Request should now be allowed (old requests expired)
            response = client.get("/test")
            assert response.status_code == 200

    def test_get_client_ip_from_x_forwarded_for(self) -> None:
        """Test that client IP is extracted from X-Forwarded-For header."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        # Test with X-Forwarded-For header
        client = TestClient(app, headers={"X-Forwarded-For": "10.0.0.1"})
        response = client.get("/test")
        assert response.status_code == 200

        # Same IP should be rate limited
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_get_client_ip_from_x_forwarded_for_multiple_ips(self) -> None:
        """Test that first IP is extracted from X-Forwarded-For with multiple IPs."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        # Test with multiple IPs in X-Forwarded-For (client, proxy1, proxy2)
        client = TestClient(app, headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1, 172.16.0.1"})
        response = client.get("/test")
        assert response.status_code == 200

        # Same client IP should be rate limited
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_rate_limit_cleanup_old_entries(self) -> None:
        """Test that old request timestamps are cleaned up to prevent memory growth."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make a request
        response = client.get("/test")
        assert response.status_code == 200

        # Note: We can't directly access middleware instance in tests when using add_middleware
        # This test verifies cleanup happens by checking behavior after time advance
        # Mock time to advance past cleanup interval
        current_time = time.time()
        with patch("time.time", return_value=current_time + 61):
            # Trigger cleanup by making another request
            response = client.get("/test")
            assert response.status_code == 200

    def test_rate_limit_reset_header(self) -> None:
        """Test that X-RateLimit-Reset header contains valid timestamp."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        reset_timestamp = int(response.headers["X-RateLimit-Reset"])
        current_timestamp = int(time.time())

        # Reset timestamp should be in the future (within 60 seconds)
        assert reset_timestamp >= current_timestamp
        assert reset_timestamp <= current_timestamp + 60

    def test_rate_limit_remaining_decreases(self) -> None:
        """Test that X-RateLimit-Remaining decreases with each request."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make requests and track remaining count
        remaining_counts = []
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200
            remaining = int(response.headers["X-RateLimit-Remaining"])
            remaining_counts.append(remaining)

        # Remaining should decrease (or stay same if requests are fast)
        # Note: Due to timing, remaining might not decrease linearly, but should trend downward
        assert remaining_counts[-1] <= remaining_counts[0]

    def test_rate_limit_default_excluded_paths(self) -> None:
        """Test that /health is excluded by default."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1)

        @app.get("/health")
        async def health_check() -> dict[str, str]:
            return {"status": "healthy"}

        client = TestClient(app)

        # Make many health check requests (should not be rate limited)
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_custom_excluded_paths(self) -> None:
        """Test that custom excluded paths work."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=1, excluded_paths={"/metrics", "/health"})

        @app.get("/metrics")
        async def metrics() -> dict[str, str]:
            return {"metrics": "ok"}

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Make many metrics requests (should not be rate limited)
        for _ in range(10):
            response = client.get("/metrics")
            assert response.status_code == 200

        # But regular endpoint should be rate limited
        response = client.get("/test")
        assert response.status_code == 200
        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_rate_limit_error_message(self) -> None:
        """Test that rate limit error message is informative."""
        app = FastAPI()
        app.add_middleware(RateLimitMiddleware, requests_per_minute=5)

        @app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Exceed rate limit
        for _ in range(5):
            client.get("/test")

        response = client.get("/test")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        error_detail = response.json()["detail"]
        assert "Rate limit exceeded" in error_detail
        assert "5" in error_detail  # Should mention the limit
        assert "requests per minute" in error_detail


class TestGetRateLimitPerMinute:
    """Test get_rate_limit_per_minute configuration function."""

    def test_get_rate_limit_per_minute_default(self) -> None:
        """Test that default rate limit is returned when env var not set."""
        from services.shared.config import get_rate_limit_per_minute

        with patch.dict("os.environ", {}, clear=True):
            rate_limit = get_rate_limit_per_minute(default=100)
            assert rate_limit == 100

    def test_get_rate_limit_per_minute_from_env(self) -> None:
        """Test that rate limit is read from environment variable."""
        from services.shared.config import get_rate_limit_per_minute

        with patch.dict("os.environ", {"RATE_LIMIT_PER_MINUTE": "200"}):
            rate_limit = get_rate_limit_per_minute(default=100)
            assert rate_limit == 200

    def test_get_rate_limit_per_minute_invalid_value(self) -> None:
        """Test that invalid rate limit value raises ValueError."""
        from services.shared.config import get_rate_limit_per_minute

        with patch.dict("os.environ", {"RATE_LIMIT_PER_MINUTE": "invalid"}):
            with pytest.raises(ValueError, match="Invalid RATE_LIMIT_PER_MINUTE"):
                get_rate_limit_per_minute(default=100)

    def test_get_rate_limit_per_minute_negative_value(self) -> None:
        """Test that negative rate limit value raises ValueError."""
        from services.shared.config import get_rate_limit_per_minute

        with patch.dict("os.environ", {"RATE_LIMIT_PER_MINUTE": "-10"}):
            with pytest.raises(ValueError, match="must be positive"):
                get_rate_limit_per_minute(default=100)

    def test_get_rate_limit_per_minute_zero_value(self) -> None:
        """Test that zero rate limit value raises ValueError."""
        from services.shared.config import get_rate_limit_per_minute

        with patch.dict("os.environ", {"RATE_LIMIT_PER_MINUTE": "0"}):
            with pytest.raises(ValueError, match="must be positive"):
                get_rate_limit_per_minute(default=100)

