from uuid import uuid4

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hermeshq.models.base import Base, TimestampMixin


class Container(TimestampMixin, Base):
    __tablename__ = "containers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    organization_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending, creating, running, stopped, error, destroyed
    docker_container_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    image: Mapped[str] = mapped_column(String(255), nullable=False, default="hermes:latest")
    ports: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string: {"8080": 8080, "8081": 8081}
    volume_mounts: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string: [{"host_path": "/data/user-123", "container_path": "/app/data"}]
    env_vars: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON string: {"HERMES_MODE": "headmaster_remote", "API_KEY": "..."}
    health_check_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_healthy_at: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
