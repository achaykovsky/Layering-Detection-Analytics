"""
Rate limiting middleware for FastAPI services.

Prevents DoS attacks via request flooding by limiting requests per IP address.
Uses sliding window algorithm with in-memory storage.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import DefaultDict

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request rate per IP address.

    Uses sliding window algorithm to track requests per IP.
    Rejects requests exceeding the limit with HTTP 429 (Too Many Requests).
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 100,
        excluded_paths: set[str] | None = None,
    ) -> None:
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            requests_per_minute: Maximum requests per minute per IP (default: 100)
            excluded_paths: Set of paths to exclude from rate limiting (e.g., /health)
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.excluded_paths = excluded_paths or {"/health"}
        # Store request timestamps per IP: {ip: [timestamp1, timestamp2, ...]}
        self._request_timestamps: DefaultDict[str, list[float]] = defaultdict(list)
        # Lock for thread safety (in-memory, single process)
        self._cleanup_interval = 60.0  # Clean up old entries every 60 seconds
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.

        Checks X-Forwarded-For header (for proxies) and falls back to direct client.

        Args:
            request: FastAPI request

        Returns:
            Client IP address as string
        """
        # Check X-Forwarded-For header (first IP in chain)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
            # Take the first one (original client)
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        # Default fallback
        return "unknown"

    def _cleanup_old_entries(self, current_time: float) -> None:
        """
        Remove old request timestamps to prevent memory growth.

        Cleans up entries older than 1 minute to keep memory usage bounded.

        Args:
            current_time: Current timestamp
        """
        # Only cleanup every cleanup_interval seconds
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        cutoff_time = current_time - 60.0  # Remove entries older than 1 minute

        # Clean up old timestamps for each IP
        for ip in list(self._request_timestamps.keys()):
            timestamps = self._request_timestamps[ip]
            # Keep only timestamps within the last minute
            self._request_timestamps[ip] = [ts for ts in timestamps if ts > cutoff_time]

            # Remove IP if no timestamps left
            if not self._request_timestamps[ip]:
                del self._request_timestamps[ip]

        self._last_cleanup = current_time

    def _is_rate_limited(self, ip: str, current_time: float) -> tuple[bool, int, int]:
        """
        Check if IP address has exceeded rate limit.

        Uses sliding window: counts requests in the last 60 seconds.

        Args:
            ip: Client IP address
            current_time: Current timestamp

        Returns:
            Tuple of (is_limited, remaining_requests, reset_in_seconds)
        """
        cutoff_time = current_time - 60.0  # Last 60 seconds

        # Get timestamps for this IP and filter to last minute
        timestamps = self._request_timestamps[ip]
        recent_timestamps = [ts for ts in timestamps if ts > cutoff_time]
        self._request_timestamps[ip] = recent_timestamps

        # Count requests in last minute
        request_count = len(recent_timestamps)

        # Check if limit exceeded
        is_limited = request_count >= self.requests_per_minute

        # Calculate remaining requests
        remaining = max(0, self.requests_per_minute - request_count)

        # Calculate reset time (seconds until oldest request expires)
        reset_in_seconds = 60
        if recent_timestamps:
            oldest_timestamp = min(recent_timestamps)
            reset_in_seconds = max(1, int(60 - (current_time - oldest_timestamp)))

        return is_limited, remaining, reset_in_seconds

    async def dispatch(self, request: Request, call_next):
        """
        Check rate limit before processing request.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from next handler, or HTTP 429 if rate limit exceeded
        """
        # Skip rate limiting for excluded paths (e.g., health checks)
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Cleanup old entries periodically
        self._cleanup_old_entries(current_time)

        # Check rate limit
        is_limited, remaining, reset_in_seconds = self._is_rate_limited(client_ip, current_time)

        if is_limited:
            # Rate limit exceeded
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Maximum {self.requests_per_minute} requests per minute.",
                },
            )
            # Add rate limit headers
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(int(current_time) + reset_in_seconds)
            return response

        # Add current request timestamp
        self._request_timestamps[client_ip].append(current_time)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)  # -1 because we just added a request
        response.headers["X-RateLimit-Reset"] = str(int(current_time) + reset_in_seconds)

        return response

