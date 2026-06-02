"""Request logging middleware for FastAPI.

Logs method, path, status code, and duration for every HTTP request.
Excludes health checks and WebSocket upgrades to reduce noise.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("hermeshq.request")

# Paths that are excluded from request logging (too noisy).
_EXCLUDED_PREFIXES = (
    "/health",
    "/favicon.ico",
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs each HTTP request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip non-HTTP requests (e.g. WebSocket)
        if request.url.path in _EXCLUDED_PREFIXES:
            return await call_next(request)

        # Skip WebSocket upgrade requests
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Determine log level based on status code
        status_code = response.status_code
        if status_code >= 500:
            log_fn = logger.error
        elif status_code >= 400:
            log_fn = logger.warning
        else:
            log_fn = logger.info

        log_fn(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )

        return response
