"""Audit log schemas."""

from datetime import datetime

from pydantic import BaseModel

from hermeshq.schemas.common import ORMModel


class AuditLogEntry(ORMModel):
    id: str
    actor_id: str | None = None
    actor_username: str | None = None
    actor_role: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    target_name: str | None = None
    ip_address: str | None = None
    old_value: dict | None = None
    new_value: dict | None = None
    details: dict = {}
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int
    has_more: bool
