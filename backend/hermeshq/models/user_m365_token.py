from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermeshq.models.base import Base, TimestampMixin


class UserM365Token(TimestampMixin, Base):
    __tablename__ = "user_m365_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    account_email: Mapped[str] = mapped_column(String(255))
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_cache_enc: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="m365_token")
