"""Structured error response middleware for FastAPI.

Ensures all error responses (4xx/5xx) have a consistent JSON shape:
    {"detail": "...", "status_code": N, "path": "/api/..."}

This normalizes unhandled exceptions, validation errors, and HTTPException
into a single predictable format for frontend consumers.
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("hermeshq.errors")


def _error_body(detail: str, status_code: int, path: str, *, extra: dict | None = None) -> dict:
    body: dict = {
        "detail": detail,
        "status_code": status_code,
        "path": path,
    }
    if extra:
        body.update(extra)
    return body


class StructuredErrorMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns a consistent JSON error."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001  # Global error handler — must catch everything
            logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
            return JSONResponse(
                content=_error_body(
                    detail="Internal server error",
                    status_code=500,
                    path=request.url.path,
                ),
                status_code=500,
            )

        # Only transform non-JSON error responses (e.g. plain text from Starlette defaults)
        if response.status_code >= 400 and response.status_code != 422:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                # Read the body and wrap it in structured format
                body_bytes = b""
                async for chunk in response.body_iterator:
                    if isinstance(chunk, str):
                        body_bytes += chunk.encode()
                    elif isinstance(chunk, bytes):
                        body_bytes += chunk
                detail = body_bytes.decode("utf-8", errors="replace")[:500] or "Unknown error"
                return JSONResponse(
                    content=_error_body(
                        detail=detail,
                        status_code=response.status_code,
                        path=request.url.path,
                    ),
                    status_code=response.status_code,
                )

        return response
