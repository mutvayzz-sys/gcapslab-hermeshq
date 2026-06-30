"""Tests for Supabase JWT verification via public JWKS."""

import pytest
from types import SimpleNamespace
from unittest.mock import patch

from hermeshq.core.supabase_auth import verify_supabase_token


@pytest.mark.asyncio
async def test_verify_supabase_token_no_jwks_url_returns_none(monkeypatch):
    """Returns None when SUPABASE_JWKS_URL is not configured."""
    monkeypatch.setattr(
        "hermeshq.core.supabase_auth.get_settings",
        lambda: SimpleNamespace(supabase_jwks_url=None),
    )
    result = await verify_supabase_token("fake-token", db=None)
    assert result is None


@pytest.mark.asyncio
async def test_verify_supabase_token_fetch_failure_returns_none(monkeypatch):
    """Returns None when the JWKS fetch fails (network error, bad URL, etc.)."""
    async def _fail(url):
        raise Exception("network error")

    monkeypatch.setattr(
        "hermeshq.core.supabase_auth.get_settings",
        lambda: SimpleNamespace(supabase_jwks_url="https://example.com/.well-known/jwks.json"),
    )
    monkeypatch.setattr("hermeshq.core.supabase_auth._fetch_supabase_jwks", _fail)
    result = await verify_supabase_token("fake-token", db=None)
    assert result is None


@pytest.mark.asyncio
async def test_verify_supabase_token_empty_jwks_returns_none(monkeypatch):
    """Returns None when the JWKS endpoint returns no keys."""

    async def _empty_jwks(url):
        return []

    monkeypatch.setattr(
        "hermeshq.core.supabase_auth.get_settings",
        lambda: SimpleNamespace(supabase_jwks_url="https://example.com/.well-known/jwks.json"),
    )
    monkeypatch.setattr("hermeshq.core.supabase_auth._fetch_supabase_jwks", _empty_jwks)
    result = await verify_supabase_token("fake-token", db=None)
    assert result is None


@pytest.mark.asyncio
async def test_verify_supabase_token_invalid_jwt_returns_none(monkeypatch):
    """Returns None when the JWT doesn't validate against any JWKS key."""
    from jose.exceptions import JWTError

    async def _fake_jwks(url):
        return [{"kty": "RSA", "kid": "test", "n": "invalid", "e": "AQAB"}]

    def _raise_jwt_error(token, key, **kwargs):
        raise JWTError("invalid signature")

    monkeypatch.setattr(
        "hermeshq.core.supabase_auth.get_settings",
        lambda: SimpleNamespace(supabase_jwks_url="https://example.com/.well-known/jwks.json"),
    )
    monkeypatch.setattr("hermeshq.core.supabase_auth._fetch_supabase_jwks", _fake_jwks)
    monkeypatch.setattr("hermeshq.core.supabase_auth.jwt.decode", _raise_jwt_error)
    result = await verify_supabase_token("fake-token", db=None)
    assert result is None