"""Combined auth: try Supabase JWT first, fall back to local HS256.

Used by endpoints that serve both console (Supabase-authenticated) and
desktop (local JWT) callers.
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import decode_access_token_subject, get_user_by_subject
from hermeshq.core.supabase_auth import verify_supabase_token
from hermeshq.database import get_db_session
from hermeshq.models.user import User


async def get_authenticated_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Try Supabase JWT → fall back to local JWT → 401 if neither works."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

        # Try Supabase first (RS256, asymmetric JWKS)
        user = await verify_supabase_token(token, db)
        if user:
            return user

        # Fall back to local auth (HS256, shared secret)
        subject, subject_kind = decode_access_token_subject(token)
        if subject:
            user = await get_user_by_subject(db, subject, subject_kind)
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )