from uuid import uuid4

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermeshq.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default="company")
    default_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    default_capabilities: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    honcho_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    honcho_jwt_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    nous_api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nous_base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    users = relationship("User", back_populates="organization")

    @property
    def has_honcho_jwt_secret(self) -> bool:
        return bool(self.honcho_jwt_secret)

    @property
    def has_nous_api_key(self) -> bool:
        return bool(self.nous_api_key)
