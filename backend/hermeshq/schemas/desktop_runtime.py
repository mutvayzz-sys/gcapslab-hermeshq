from pydantic import BaseModel, Field


class DesktopProvisionRequest(BaseModel):
    client: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)
    platform: str = Field(min_length=1, max_length=32)
    mode: str | None = Field(default=None, max_length=32)


class DesktopRuntimeValidateRequest(BaseModel):
    runtime_id: str = Field(default="local-hermes", min_length=1, max_length=128)
    requested_capability: str | None = Field(default=None, max_length=64)


class DesktopProvisionUser(BaseModel):
    id: str
    username: str
    role: str


class DesktopRuntimeInfo(BaseModel):
    validate_url: str
    ttl_seconds: int


class DesktopProvisionProvider(BaseModel):
    slug: str
    name: str
    runtime_provider: str
    auth_type: str
    base_url: str | None = None
    default_model: str | None = None
    available_models: list[str] = []
    enabled: bool = True


class DesktopProvisionAppSettings(BaseModel):
    """Public app settings shipped in the provision response so the desktop can
    apply admin-configured branding/theme without making a separate round-trip."""
    app_name: str
    app_short_name: str
    theme_mode: str
    default_locale: str
    logo_url: str | None = None
    favicon_url: str | None = None
    has_logo: bool = False
    has_favicon: bool = False


class DesktopProvisionResponse(BaseModel):
    mode: str
    hermeshq_url: str
    user: DesktopProvisionUser
    capabilities: list[str]
    runtime: DesktopRuntimeInfo
    cloud_container_config: dict | None = None
    system_prompt_override: str | None = None
    session_namespace: str | None = None
    honcho_base_url: str | None = None
    honcho_api_key: str | None = None
    # Provider catalog + default model so the desktop can populate its model
    # selector from HermesHQ instead of relying solely on the local runtime's
    # /api/model/options (which only sees whatever API keys are in the local
    # .env). Populated from ProviderDefinition rows + the user's assigned
    # agent config.
    providers: list[DesktopProvisionProvider] = []
    default_model: str | None = None
    default_provider: str | None = None
    default_base_url: str | None = None
    # Admin-configured branding/theme settings (from AppSettings)
    app_settings: DesktopProvisionAppSettings | None = None


class DesktopRuntimeValidateResponse(BaseModel):
    allowed: bool
    capabilities: list[str]
    role: str
    ttl_seconds: int
