"""Tests for the request logging middleware."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Response
from starlette.testclient import TestClient

from hermeshq.core.request_logging import RequestLoggingMiddleware


def _build_app() -> tuple[FastAPI, TestClient]:
    """Create a minimal FastAPI app with the middleware."""
    app = FastAPI()

    @app.get("/api/agents")
    async def get_agents():
        return []

    @app.get("/api/missing")
    async def not_found():
        return Response(status_code=404)

    @app.post("/api/agents")
    async def create_agent():
        return Response(status_code=201)

    @app.get("/api/error")
    async def server_error():
        return Response(status_code=500)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(RequestLoggingMiddleware)

    return app, TestClient(app, raise_server_exceptions=False)


class TestRequestLoggingMiddleware(unittest.TestCase):
    """Test RequestLoggingMiddleware via TestClient."""

    def test_logs_successful_request(self) -> None:
        """200 response logs at INFO level."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            response = client.get("/api/agents")
            self.assertEqual(response.status_code, 200)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            self.assertIn("GET", call_args[1])
            self.assertIn("/api/agents", call_args[2])
            self.assertEqual(call_args[3], 200)

    def test_logs_201_as_info(self) -> None:
        """201 response logs at INFO level."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            response = client.post("/api/agents")
            self.assertEqual(response.status_code, 201)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0]
            self.assertIn("POST", call_args[1])
            self.assertEqual(call_args[3], 201)

    def test_logs_client_error_as_warning(self) -> None:
        """4xx response logs at WARNING level."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            response = client.get("/api/missing")
            self.assertEqual(response.status_code, 404)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0]
            self.assertEqual(call_args[3], 404)

    def test_logs_server_error_as_error(self) -> None:
        """5xx response logs at ERROR level."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            response = client.get("/api/error")
            self.assertEqual(response.status_code, 500)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0]
            self.assertEqual(call_args[3], 500)

    def test_skips_health_endpoint(self) -> None:
        """Health endpoint is not logged."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)

            mock_logger.info.assert_not_called()
            mock_logger.warning.assert_not_called()
            mock_logger.error.assert_not_called()

    def test_logs_duration(self) -> None:
        """Duration is included in the log message."""
        app, client = _build_app()

        with patch("hermeshq.core.request_logging.logger") as mock_logger:
            client.get("/api/agents")

            call_args = mock_logger.info.call_args[0]
            # Format: "%s %s → %d (%.1fms)", method, path, status, duration_ms
            self.assertIsInstance(call_args[4], float)
            self.assertGreaterEqual(call_args[4], 0)


if __name__ == "__main__":
    unittest.main()
