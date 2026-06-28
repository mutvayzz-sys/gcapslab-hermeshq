from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.config import get_settings
from hermeshq.models.container import Container
from hermeshq.models.user import User

DESKTOP_RUNTIME_TTL_SECONDS = 300
DESKTOP_MODE = "headmaster_local"

CAP_CHAT = "chat"
CAP_TERMINAL = "terminal"
CAP_LOCAL_FILES = "local_files"
CAP_COWORK = "cowork"
CAP_MODEL_SELECTION = "model_selection"
CAP_RUNTIME_SETTINGS = "runtime_settings"
CAP_ADMIN_AUDIT = "admin_audit"

ALL_DESKTOP_CAPABILITIES = (
    CAP_CHAT,
    CAP_TERMINAL,
    CAP_LOCAL_FILES,
    CAP_COWORK,
    CAP_MODEL_SELECTION,
    CAP_RUNTIME_SETTINGS,
    CAP_ADMIN_AUDIT,
)

ROLE_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "admin": ALL_DESKTOP_CAPABILITIES,
    "user": ALL_DESKTOP_CAPABILITIES,
    "staff": ALL_DESKTOP_CAPABILITIES,
    "beta_user": ALL_DESKTOP_CAPABILITIES,
    "school_admin": ALL_DESKTOP_CAPABILITIES,
    "student": (CAP_CHAT, CAP_COWORK, CAP_MODEL_SELECTION),
}


def normalize_desktop_role(role: str | None) -> str:
    normalized = (role or "user").strip().lower()
    return normalized if normalized in ROLE_CAPABILITIES else "user"


def capabilities_for_role(role: str | None) -> list[str]:
    return list(ROLE_CAPABILITIES[normalize_desktop_role(role)])


def desktop_user_payload(user: User) -> dict[str, str]:
    role = normalize_desktop_role(user.role)
    return {
        "id": str(user.id),
        "username": str(user.username),
        "role": role,
    }


def is_capability_allowed(capabilities: Iterable[str], requested_capability: str | None) -> bool:
    requested = (requested_capability or "").strip()
    if not requested:
        return True
    return requested in set(capabilities)


def resolve_desktop_mode(user: User) -> str:
    role = normalize_desktop_role(user.role)
    if user.organization and user.organization.default_mode:
        return user.organization.default_mode
    if role == "student":
        return "headmaster_plus_thin"
    return "headmaster_local"


async def resolve_container_config(user: User, db: AsyncSession) -> dict | None:
    """Return cloud container config if the user has an active running container."""
    result = await db.execute(
        select(Container).where(
            Container.user_id == user.id,
            Container.is_active.is_(True),
            Container.status == "running",
        )
    )
    container = result.scalar_one_or_none()
    if not container:
        return None

    # Build the public endpoint URL for the desktop app.
    # Traffic routes through nginx at /runtime/{container-name}/ on the hermes_runtime network —
    # no host ports are exposed. CONTAINER_HOST_URL (or public_base_url) is the domain.
    settings = get_settings()
    host = (settings.container_host_url or settings.public_base_url or "").rstrip("/")
    endpoint_url = f"{host}/runtime/{container.name}" if host else None

    return {
        "endpoint_url": endpoint_url,
        "container_id": container.id,
        "api_server_key": container.api_server_key,
    }
