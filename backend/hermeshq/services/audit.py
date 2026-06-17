"""Reusable audit log helper — call from any endpoint that mutates admin state."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def _trunc(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    if len(value) > max_len:
        logger.debug("audit field truncated to %d chars", max_len)
        return value[:max_len]
    return value


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    target_name: str | None = None,
    actor_id: str | None = None,
    actor_username: str | None = None,
    actor_role: str | None = None,
    ip_address: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Create an audit log entry. Call before or after db.commit()."""
    entry = AuditLog(
        actor_id=actor_id,
        actor_username=_trunc(actor_username, 128),
        actor_role=_trunc(actor_role, 20),
        action=_trunc(action, 64),
        target_type=_trunc(target_type, 64),
        target_id=target_id,
        target_name=_trunc(target_name, 255),
        ip_address=_trunc(ip_address, 64),
        old_value=old_value,
        new_value=new_value,
        details=details or {},
    )
    db.add(entry)
    return entry


def extract_ip(request: Any) -> str | None:
    """Extract client IP from a FastAPI Request object."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
