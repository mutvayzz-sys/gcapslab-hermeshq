"""Supabase JWT verification — asymmetric key (RS256 or ES256) via public JWKS.

Separate from the local HS256 admin auth in core/security.py.
Supabase is the single identity source of truth for end users; HermesHQ verifies
their JWTs against the project's public JWKS endpoint (no shared secret).
"""

import logging
import secrets
import time
from typing import Any

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.config import get_settings
from hermeshq.core.security import hash_password
from hermeshq.models.user import User

logger = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_CACHE_TTL = 3600  # 1 hour


async def _fetch_supabase_jwks(jwks_url: str) -> list[dict]:
    """Fetch and cache the Supabase JWKS keys."""
    now = time.time()
    if _JWKS_CACHE["keys"] is not None and (now - _JWKS_CACHE["fetched_at"]) < _JWKS_CACHE_TTL:
        return _JWKS_CACHE["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        data = response.json()
    _JWKS_CACHE["keys"] = data.get("keys", [])
    _JWKS_CACHE["fetched_at"] = now
    return _JWKS_CACHE["keys"]


async def _auto_provision_supabase_user(db: AsyncSession, email: str, payload: dict[str, Any]) -> User | None:
    """Create a HermesHQ User for a Supabase-authenticated caller with no matching row yet.

    Supabase is the identity source of truth for end users (see module docstring) — a
    verified JWT is proof of a real account, so a first-time caller is mirrored here rather
    than requiring an admin to hand-create a matching row before they can be provisioned.
    Lands in the same "pending" role/approval queue as native open-signup registrations
    (routers/auth.py::register), so the existing admin-approval UI covers both paths.
    """
    metadata = payload.get("user_metadata") or {}
    display_name = payload.get("name") or metadata.get("full_name") or email.split("@")[0]
    user = User(
        username=email,
        email=email,
        display_name=display_name,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        auth_source="supabase",
        role="pending",
        is_active=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race with a concurrent request auto-provisioning the same email.
        await db.rollback()
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        return user if user and user.is_active else None
    await db.refresh(user)
    return user


async def verify_supabase_token(token: str, db: AsyncSession) -> User | None:
    """Verify a Supabase-issued JWT against the public JWKS and return the matching User.

    A caller with no matching User row is auto-provisioned (see
    `_auto_provision_supabase_user`) rather than rejected — see the module docstring.

    Returns None if:
    - SUPABASE_JWKS_URL is not configured
    - the JWKS fetch fails
    - the token is invalid, expired, or doesn't match any JWKS key
    - the user exists in HermesHQ but is inactive
    """
    settings = get_settings()
    jwks_url = settings.supabase_jwks_url
    if not jwks_url:
        logger.warning("SUPABASE_JWKS_URL not configured — cannot verify Supabase JWTs")
        return None

    try:
        keys = await _fetch_supabase_jwks(jwks_url)
    except Exception:
        logger.exception("Failed to fetch Supabase JWKS from %s", jwks_url)
        return None

    if not keys:
        logger.warning("Supabase JWKS returned no keys from %s", jwks_url)
        return None

    # Try each key until one validates. Supabase signing keys can be RS256 (RSA) or
    # ES256 (EC, the current default for new projects) — use each key's own declared
    # `alg` rather than assuming RS256, or verification silently fails for every key.
    for key in keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[key.get("alg", "RS256")],
                audience="authenticated",  # Supabase access tokens use "authenticated"
            )
            email = payload.get("email")
            if not email:
                continue
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if user:
                return user if user.is_active else None
            return await _auto_provision_supabase_user(db, email, payload)
        except JWTError:
            continue

    logger.warning("Could not validate Supabase token with any JWKS key")
    return None