from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from hermeshq.schemas.common import ORMModel


class AppSettingsUpdate(BaseModel):
    app_name: str | None = None
    app_short_name: str | None = None
    theme_mode: Literal["dark", "light", "system", "enterprise", "sixmanager", "sixmanager-light"] | None = None
    default_locale: Literal["en", "es"] | None = None
    default_provider: str | None = None
    default_model: str | None = None
    default_api_key_ref: str | None = None
    default_base_url: str | None = None
    default_hermes_version: str | None = None
    default_tui_skin: str | None = None
    resend_api_key: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    public_base_url: str | None = None
    mfa_email_enabled: bool | None = None


class AppSettingsRead(ORMModel):
    id: str
    app_version: str
    app_name: str | None
    app_short_name: str | None
    theme_mode: Literal["dark", "light", "system", "enterprise", "sixmanager", "sixmanager-light"]
    default_locale: Literal["en", "es"]
    default_provider: str | None
    default_model: str | None
    default_api_key_ref: str | None
    default_base_url: str | None
    default_hermes_version: str | None
    default_tui_skin: str | None = None
    resend_api_key: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    public_base_url: str | None = None
    mfa_email_enabled: bool = False
    tui_skin_filename: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    has_tui_skin: bool = False
    has_logo: bool = False
    has_favicon: bool = False
    created_at: datetime
    updated_at: datetime


class PublicSettingsRead(BaseModel):
    """Safe subset of settings for unauthenticated access (login page, etc.)."""
    app_version: str
    app_name: str | None
    app_short_name: str | None
    theme_mode: Literal["dark", "light", "system", "enterprise", "sixmanager", "sixmanager-light"]
    default_locale: Literal["en", "es"]
    logo_url: str | None = None
    favicon_url: str | None = None
    has_logo: bool = False
    has_favicon: bool = False


class ResourceStatusResponse(BaseModel):
    """Full resource status for the Settings UI."""
    semaphore: dict
    container: dict
    system: dict
    estimate: dict | None = None


class SemaphoreUpdateRequest(BaseModel):
    """Request body for updating the concurrency semaphore."""
    semaphore: int


class SemaphoreUpdateResponse(BaseModel):
    """Response after updating the semaphore."""
    semaphore: int
    restart_required: bool = True


class GenerateOverrideRequest(BaseModel):
    """Request body for generating docker-compose.override.yml."""
    agents: int


class GenerateOverrideResponse(BaseModel):
    """Response with generated override file content."""
    content: str
    agents: int
    semaphore: int
    applied: bool = False
    restart_required: bool = True
