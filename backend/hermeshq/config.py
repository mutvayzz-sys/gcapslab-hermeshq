import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HermesHQ"
    api_prefix: str = "/api"
    debug: bool = False
    auth_mode: str = "local"

    database_url: str = "postgresql+asyncpg://hermeshq:hermeshq@localhost:5432/hermeshq"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 12
    fernet_key: str | None = None
    oidc_issuer_url: str | None = None
    oidc_discovery_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_scope: str = "openid profile email"
    oidc_provider_name: str = "OIDC Provider"
    oidc_provider_slug: str = "generic"
    oidc_post_logout_redirect_uri: str | None = None
    oidc_auto_provision_users: bool = False
    oidc_visible_providers: str = ""
    oidc_provider_login_url_google: str | None = None
    oidc_provider_login_url_microsoft: str | None = None

    resend_api_key: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    public_base_url: str | None = None
    password_reset_token_minutes: int = 15
    # Public-facing host used to build container endpoint URLs sent to the desktop app.
    # E.g. "http://165.x.x.x" or "https://vps.example.com". Falls back to public_base_url then localhost.
    container_host_url: str | None = None
    run_domain: str | None = None
    forward_auth_hmac_secret: str | None = None
    forward_auth_token_ttl_seconds: int = 24 * 60 * 60
    forward_auth_url: str = "http://127.0.0.1:18081/"
    runtime_container_cpu: str = "2"
    runtime_container_memory: str = "4g"
    runtime_container_pids_limit: int = 512
    runtime_container_shm_size: str = "1g"
    runtime_container_traefik_middleware: str = "headmaster-forward-auth@docker"
    runtime_traefik_dynamic_config_path: str | None = None
    runtime_container_image: str = "headmaster-hermes-runtime:latest"
    runtime_container_network: str = "hermes_runtime"
    runtime_container_idle_ttl_seconds: int = 3600
    open_signup: bool = False

    admin_username: str = "admin"
    admin_password: str = ""
    admin_display_name: str = "Hermes Operator"

    workspaces_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "workspaces")
    branding_root: Path | None = None
    hermes_skins_root: Path | None = None
    agent_assets_root: Path | None = None
    user_assets_root: Path | None = None
    integration_packages_root: Path | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3420"]
    cookie_secure: bool = False
    pty_shell: str = "/bin/sh"
    internal_api_base_url: str = "http://127.0.0.1:8000/api/internal"
    # Max concurrent hermes_task_runner subprocesses.
    # Each process uses ~50MB RAM. Default: 8 (safe for 1GB container).
    # For production sizing: available_RAM_MB / 60 (50MB per process + 20% headroom)
    concurrency_semaphore: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        if self.jwt_secret == "":
            import secrets as _secrets

            self.jwt_secret = _secrets.token_urlsafe(32)
            # Persist the generated secret so it survives container restarts.
            # Without this, the SecretVault (which uses jwt_secret as Fernet seed
            # when FERNET_KEY is unset) would be unable to decrypt stored secrets
            # after every restart.
            env_path = self.model_config.get("env_file", ".env")
            if not Path(env_path).is_absolute():
                env_path = Path(__file__).resolve().parents[1] / env_path
            env_path = Path(env_path)
            try:
                lines = env_path.read_text().splitlines() if env_path.exists() else []
                found = False
                new_lines: list[str] = []
                for line in lines:
                    if line.strip().startswith("JWT_SECRET="):
                        new_lines.append(f"JWT_SECRET={self.jwt_secret}")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"JWT_SECRET={self.jwt_secret}")
                env_path.write_text("\n".join(new_lines) + "\n")
                logger.warning(
                    "⚠️ JWT_SECRET was empty — auto-generated and saved to %s. "
                    "Set JWT_SECRET in your environment for production.",
                    env_path,
                )
            except OSError:
                logger.warning(
                    "⚠️ JWT_SECRET was empty — auto-generated but could NOT persist to %s. "
                    "Secrets will break on next restart!",
                    env_path,
                )
        elif self.jwt_secret == "change-me":
            logger.warning(
                "⚠️ JWT_SECRET is using default value 'change-me'. "
                "This is insecure for production. To rotate, set FERNET_KEY first "
                "and then use the rotate-secrets CLI command."
            )
        if self.admin_password in ("", "admin123"):
            logger.warning("⚠️ ADMIN_PASSWORD is not set or using default value. This is insecure for production!")
        self.workspaces_root = self.workspaces_root.resolve()
        if self.branding_root is None:
            self.branding_root = self.workspaces_root / "_branding"
        if self.hermes_skins_root is None:
            self.hermes_skins_root = self.workspaces_root / "_hermes_skins"
        if self.agent_assets_root is None:
            self.agent_assets_root = self.workspaces_root / "_agent_assets"
        if self.user_assets_root is None:
            self.user_assets_root = self.workspaces_root / "_user_assets"
        if self.integration_packages_root is None:
            self.integration_packages_root = self.workspaces_root / "_integration_packages"
        self.branding_root = self.branding_root.resolve()
        self.hermes_skins_root = self.hermes_skins_root.resolve()
        self.agent_assets_root = self.agent_assets_root.resolve()
        self.user_assets_root = self.user_assets_root.resolve()
        self.integration_packages_root = self.integration_packages_root.resolve()


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def update_runtime_setting(key: str, value: object) -> None:
    """Update a setting value at runtime without restart."""
    global _settings_instance
    s = get_settings()
    setattr(s, key, value)
