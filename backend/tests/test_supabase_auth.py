"""Tests for Supabase JWT verification via public JWKS."""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from hermeshq.core.supabase_auth import verify_supabase_token


def _fake_settings():
    return SimpleNamespace(supabase_jwks_url="https://example.com/.well-known/jwks.json")


async def _fake_jwks(url):
    return [{"kty": "RSA", "kid": "test", "n": "fake", "e": "AQAB"}]


def _patch_jwt_success(monkeypatch, payload):
    monkeypatch.setattr("hermeshq.core.supabase_auth.get_settings", _fake_settings)
    monkeypatch.setattr("hermeshq.core.supabase_auth._fetch_supabase_jwks", _fake_jwks)
    monkeypatch.setattr("hermeshq.core.supabase_auth.jwt.decode", lambda token, key, **kwargs: payload)


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


@pytest.mark.asyncio
async def test_verify_supabase_token_existing_active_user_returns_user(monkeypatch):
    """A JWT whose email matches an existing active User returns that row as-is."""
    _patch_jwt_success(monkeypatch, {"email": "existing@gcaplabs.com"})
    existing_user = SimpleNamespace(email="existing@gcaplabs.com", is_active=True)

    db = AsyncMock()
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = existing_user
    db.execute = AsyncMock(return_value=execute_result)

    result = await verify_supabase_token("fake-token", db=db)
    assert result is existing_user
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_verify_supabase_token_existing_inactive_user_returns_none(monkeypatch):
    """A matching but deactivated User is blocked, not auto-reprovisioned."""
    _patch_jwt_success(monkeypatch, {"email": "disabled@gcaplabs.com"})
    disabled_user = SimpleNamespace(email="disabled@gcaplabs.com", is_active=False)

    db = AsyncMock()
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = disabled_user
    db.execute = AsyncMock(return_value=execute_result)

    result = await verify_supabase_token("fake-token", db=db)
    assert result is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_verify_supabase_token_no_match_auto_provisions_user(monkeypatch):
    """A verified JWT with no matching User auto-creates a pending, Supabase-sourced row."""
    _patch_jwt_success(monkeypatch, {"email": "new.person@gcaplabs.com", "name": "New Person"})

    db = AsyncMock()
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await verify_supabase_token("fake-token", db=db)

    db.add.assert_called_once()
    created_user = db.add.call_args[0][0]
    assert created_user.username == "new.person@gcaplabs.com"
    assert created_user.email == "new.person@gcaplabs.com"
    assert created_user.display_name == "New Person"
    assert created_user.auth_source == "supabase"
    assert created_user.role == "pending"
    assert created_user.is_active is True
    assert result is created_user


@pytest.mark.asyncio
async def test_verify_supabase_token_auto_provision_race_reuses_winner(monkeypatch):
    """A unique-constraint race on auto-provision re-queries and returns the other request's row."""
    _patch_jwt_success(monkeypatch, {"email": "racer@gcaplabs.com"})
    winner = SimpleNamespace(email="racer@gcaplabs.com", is_active=True)

    db = AsyncMock()
    db.add = MagicMock()
    no_match = MagicMock()
    no_match.scalar_one_or_none.return_value = None
    found_winner = MagicMock()
    found_winner.scalar_one_or_none.return_value = winner
    db.execute = AsyncMock(side_effect=[no_match, found_winner])
    db.commit = AsyncMock(side_effect=IntegrityError("insert", {}, Exception("unique violation")))
    db.rollback = AsyncMock()

    result = await verify_supabase_token("fake-token", db=db)
    assert result is winner
    db.rollback.assert_called_once()