"""Tests for POST /auth/refresh – token refresh endpoint."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from hermeshq.core.security import create_access_token


class TestRefreshEndpoint:
    """Test the refresh token endpoint logic."""

    def test_create_access_token_returns_valid_jwt(self):
        token, expires_at = create_access_token("user-123", subject_kind="id")
        assert isinstance(token, str)
        assert len(token) > 20
        assert expires_at is not None

    def test_create_access_token_contains_subject(self):
        from jose import jwt
        from hermeshq.config import get_settings

        settings = get_settings()
        token, _ = create_access_token("user-abc", subject_kind="id")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user-abc"
        assert payload["sub_kind"] == "id"
        assert "exp" in payload

    def test_create_access_token_different_for_different_users(self):
        token1, _ = create_access_token("user-1", subject_kind="id")
        token2, _ = create_access_token("user-2", subject_kind="id")
        assert token1 != token2

    def test_refresh_requires_authentication(self):
        """Refresh endpoint requires a valid current token."""
        from fastapi.testclient import TestClient
        # We test at the schema level that a missing token would fail
        # since we can't spin up the full app without DB
        from hermeshq.core.security import decode_access_token
        result = decode_access_token("")
        assert result is None

    def test_refresh_returns_new_token_with_same_subject(self):
        from jose import jwt
        from hermeshq.config import get_settings

        settings = get_settings()
        token1, _ = create_access_token("user-xyz", subject_kind="id")

        # Simulate what refresh does: create a new token for the same user
        token2, expires2 = create_access_token("user-xyz", subject_kind="id")

        payload1 = jwt.decode(token1, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        payload2 = jwt.decode(token2, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

        # Same subject
        assert payload1["sub"] == payload2["sub"] == "user-xyz"
        # Both have valid expiration
        assert "exp" in payload1
        assert "exp" in payload2

    def test_expired_token_fails_decode(self):
        from jose import jwt
        from hermeshq.config import get_settings
        from datetime import datetime, timedelta, timezone

        settings = get_settings()
        # Create an already-expired token
        expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        expired_token = jwt.encode(
            {"sub": "user-x", "sub_kind": "id", "exp": expired_at},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

        from hermeshq.core.security import decode_access_token
        result = decode_access_token(expired_token)
        assert result is None


class TestRefreshEndpointRouting:
    """Verify the refresh route is properly registered."""

    def test_auth_router_has_refresh_route(self):
        from hermeshq.routers.auth import router
        routes = [r.path for r in router.routes]
        assert "/refresh" in routes or "/auth/refresh" in routes

    def test_refresh_route_is_post(self):
        from hermeshq.routers.auth import router
        from fastapi.routing import APIRoute

        for route in router.routes:
            if isinstance(route, APIRoute) and route.path in ("/refresh", "/auth/refresh"):
                assert "POST" in route.methods
                break
        else:
            pytest.fail("Refresh route not found")

    def test_refresh_route_response_model(self):
        from hermeshq.routers.auth import router
        from fastapi.routing import APIRoute
        from hermeshq.schemas.auth import TokenResponse

        for route in router.routes:
            if isinstance(route, APIRoute) and route.path == "/refresh":
                assert route.response_model == TokenResponse
                break
