"""
Request size limit middleware for FastAPI services.

Prevents DoS attacks via memory exhaustion from large payloads.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request body size.

    Rejects requests larger than the specified limit with HTTP 413 (Payload Too Large).
    """

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024) -> None:
        """
        Initialize request size limit middleware.

        Args:
            app: FastAPI application
            max_request_size: Maximum request body size in bytes (default: 10MB)
        """
        super().__init__(app)
        self.max_request_size = max_request_size

    async def dispatch(self, request: Request, call_next):
        """
        Check request body size before processing.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response from next handler, or HTTP 413 if request too large
        """
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "detail": f"Request body too large. Maximum size: {self.max_request_size / (1024 * 1024):.1f}MB",
                        },
                    )
            except (ValueError, TypeError):
                # Invalid content-length, let request proceed (will fail at parsing)
                pass

        # Process request
        response = await call_next(request)

        return response

