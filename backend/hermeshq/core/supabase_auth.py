"""Supabase JWT verification — asymmetric key (RS256) via public JWKS.

Separate from the local HS256 admin auth in core/security.py.
Supabase is the single identity source of truth for end users; HermesHQ verifies
their JWTs against the project's public JWKS endpoint (no shared secret).
"""

import logging
import time
from typing import Any

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.config import get_settings
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


async def verify_supabase_token(token: str, db: AsyncSession) -> User | None:
    """Verify a Supabase-issued JWT against the public JWKS and return the matching User.

    Returns None if:
    - SUPABASE_JWKS_URL is not configured
    - the JWKS fetch fails
    - the token is invalid, expired, or doesn't match any JWKS key
    - the user doesn't exist in HermesHQ or is inactive
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

    # Try each key until one validates. Supabase JWTs are RS256.
    for key in keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience="authenticated",  # Supabase access tokens use "authenticated"
            )
            email = payload.get("email")
            if not email:
                continue
            result = await db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
            return None
        except JWTError:
            continue

    logger.warning("Could not validate Supabase token with any JWKS key")
    return None