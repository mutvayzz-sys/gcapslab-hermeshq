"""Admin audit log — tracks who changed what, when, and from where."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from hermeshq.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Who performed the action
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    actor_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # What action was performed
    action: Mapped[str] = mapped_column(String(64), index=True)

    # What entity was affected
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    target_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Where the action came from
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Change details
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Additional context
    details: Mapped[dict] = mapped_column(JSON, default=dict)
