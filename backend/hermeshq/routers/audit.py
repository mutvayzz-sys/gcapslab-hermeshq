"""Audit log read endpoints — admin-only."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import require_admin
from hermeshq.database import get_db_session
from hermeshq.models.audit_log import AuditLog
from hermeshq.models.user import User
from hermeshq.schemas.audit import AuditLogEntry, AuditLogPage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])

PAGE_SIZE = 50


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    action: str | None = Query(default=None, description="Filter by action type"),
    target_type: str | None = Query(default=None, description="Filter by target type"),
    actor_id: str | None = Query(default=None, description="Filter by actor user ID"),
    search: str | None = Query(default=None, description="Search in target_name and actor_username"),
    cursor: str | None = Query(default=None, description="Pagination cursor (audit log ID)"),
    limit: int = Query(default=PAGE_SIZE, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> AuditLogPage:
    """List audit log entries, newest first, with optional filters."""
    # Count query
    count_q = select(func.count(AuditLog.id))
    data_q = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    if action:
        count_q = count_q.where(AuditLog.action == action)
        data_q = data_q.where(AuditLog.action == action)
    if target_type:
        count_q = count_q.where(AuditLog.target_type == target_type)
        data_q = data_q.where(AuditLog.target_type == target_type)
    if actor_id:
        count_q = count_q.where(AuditLog.actor_id == actor_id)
        data_q = data_q.where(AuditLog.actor_id == actor_id)
    if search:
        pattern = f"%{search}%"
        count_q = count_q.where(
            (AuditLog.target_name.ilike(pattern)) | (AuditLog.actor_username.ilike(pattern))
        )
        data_q = data_q.where(
            (AuditLog.target_name.ilike(pattern)) | (AuditLog.actor_username.ilike(pattern))
        )
    if cursor:
        # Get the cursor entry to know its timestamp
        cursor_entry = await db.get(AuditLog, cursor)
        if cursor_entry:
            data_q = data_q.where(
                (AuditLog.created_at < cursor_entry.created_at)
                | ((AuditLog.created_at == cursor_entry.created_at) & (AuditLog.id < cursor))
            )

    total = (await db.execute(count_q)).scalar() or 0
    data_q = data_q.limit(limit + 1)
    rows = (await db.execute(data_q)).scalars().all()

    has_more = len(rows) > limit
    items = rows[:limit]

    return AuditLogPage(
        items=[AuditLogEntry.model_validate(entry) for entry in items],
        total=total,
        has_more=has_more,
    )
