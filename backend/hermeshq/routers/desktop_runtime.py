import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user
from hermeshq.database import get_db_session
from hermeshq.models.agent import Agent
from hermeshq.models.agent_assignment import AgentAssignment
from hermeshq.models.audit_log import AuditLog
from hermeshq.models.provider import ProviderDefinition
from hermeshq.models.user import User
from hermeshq.schemas.desktop_runtime import (
    DesktopCloudContainerConfig,
    DesktopProvisionAppSettings,
    DesktopProvisionProvider,
    DesktopProvisionRequest,
    DesktopProvisionResponse,
    DesktopRuntimeInfo,
    DesktopRuntimeValidateRequest,
    DesktopRuntimeValidateResponse,
)
from hermeshq.core.combined_auth import get_authenticated_user
from hermeshq.services.container_supervisor import ContainerSupervisorError
from hermeshq.services.desktop_runtime import (
    DESKTOP_RUNTIME_TTL_SECONDS,
    capabilities_for_role,
    desktop_user_payload,
    is_capability_allowed,
    normalize_desktop_role,
    resolve_desktop_mode,
)

router = APIRouter(prefix="/desktop", tags=["desktop"])


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


async def _audit_log(
    db: AsyncSession,
    actor: User,
    action: str,
    target_type: str,
    target_id: str | None,
    old_value: dict | None,
    new_value: dict | None,
    details: dict | None,
) -> None:
    """Write an audit log entry."""
    db.add(
        AuditLog(
            actor_id=actor.id,
            actor_username=actor.username,
            actor_role=actor.role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            details=details or {},
        )
    )
    await db.commit()


async def _build_provision_response(
    user: User, request: Request, db: AsyncSession
) -> DesktopProvisionResponse:
    server_url = _base_url(request)
    capabilities = capabilities_for_role(user.role)
    mode = resolve_desktop_mode(user)

    # Phase 6.3: Resolve system prompt override from organization
    system_prompt_override: str | None = None
    org = None
    if user.organization_id:
        from hermeshq.models.organization import Organization

        org = await db.get(Organization, user.organization_id)
        if org:
            system_prompt_override = org.system_prompt_override

    # Phase 8: Cross-device session namespace
    from hermeshq.services.cross_device_session import derive_session_namespace
    session_namespace = derive_session_namespace(user)

    # Phase 5: Honcho memory continuity
    honcho_base_url: str | None = None
    honcho_api_key: str | None = None
    nous_api_key: str | None = None
    if org:
        honcho_base_url = org.honcho_base_url
        if org.honcho_jwt_secret:
            from jose import jwt
            honcho_api_key = jwt.encode(
                {"sub": str(user.id), "peer": session_namespace},
                org.honcho_jwt_secret,
                algorithm="HS256",
            )
        nous_api_key = None  # legacy — replaced by kimi-code runtime_env injection

    # Provider catalog + default model: ship the enabled ProviderDefinition
    # rows so the desktop can populate its model selector from HermesHQ
    # instead of relying solely on the local runtime's /api/model/options.
    provider_rows = (
        await db.execute(
            select(ProviderDefinition)
            .where(ProviderDefinition.enabled.is_(True))
            .order_by(ProviderDefinition.sort_order, ProviderDefinition.name)
        )
    ).scalars().all()
    providers = [
        DesktopProvisionProvider(
            slug=p.slug,
            name=p.name,
            runtime_provider=p.runtime_provider,
            auth_type=p.auth_type,
            base_url=p.base_url,
            default_model=p.default_model,
            available_models=p.available_models or [],
            enabled=p.enabled,
        )
        for p in provider_rows
    ]

    # Default model: resolve from the user's assigned agent (first active
    # assignment). Falls back to the first provider's default_model.
    default_model: str | None = None
    default_provider: str | None = None
    default_base_url: str | None = None
    assignment = (
        await db.execute(
            select(Agent)
            .join(AgentAssignment, AgentAssignment.agent_id == Agent.id)
            .where(AgentAssignment.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if assignment:
        default_model = assignment.model
        default_provider = assignment.provider
        default_base_url = assignment.base_url
    if not default_model and providers:
        default_model = providers[0].default_model
        default_provider = providers[0].slug
        default_base_url = providers[0].base_url

    # Resolve provider API key and ship it to the desktop so the local Hermes
    # runtime can authenticate with the configured provider.
    # Resolution order: env var → Secret vault (where admin stored the key via UI).
    runtime_env: dict[str, str] = {}
    if assignment and assignment.api_key_ref:
        key_value = os.environ.get(assignment.api_key_ref)
        if not key_value:
            from hermeshq.models.secret import Secret
            from sqlalchemy import select as _select
            secret_row = (
                await db.execute(_select(Secret).where(Secret.name == assignment.api_key_ref))
            ).scalar_one_or_none()
            if secret_row:
                try:
                    key_value = request.app.state.secret_vault.decrypt(secret_row.value_enc)
                except Exception:
                    key_value = None
        if key_value:
            runtime_env[assignment.api_key_ref] = key_value
    # Inject kimi-code model credential (replaces legacy nous_api_key).
    # These env vars tell the per-user container's Hermes profile to use
    # kimi-k2.7-code via the kimi-coding provider.
    from hermeshq.config import get_settings as _get_settings
    _s = _get_settings()
    if _s.kimi_api_key:
        runtime_env["KIMI_API_KEY"] = _s.kimi_api_key
        runtime_env["HERMES_DEFAULT_PROVIDER"] = _s.kimi_provider
        runtime_env["HERMES_DEFAULT_MODEL"] = _s.kimi_model
        runtime_env["HERMES_DEFAULT_BASE_URL"] = _s.kimi_base_url
        runtime_env["HERMES_DEFAULT_API_MODE"] = _s.kimi_api_mode

    # App settings (branding/theme) from AppSettings table
    from hermeshq.models.app_settings import AppSettings
    from hermeshq.routers.settings import _settings_to_public_read
    app_settings_row = await db.get(AppSettings, "default")
    app_settings = None
    if app_settings_row:
        public_read = _settings_to_public_read(app_settings_row)
        app_settings = DesktopProvisionAppSettings(
            app_name=public_read.app_name,
            app_short_name=public_read.app_short_name,
            theme_mode=public_read.theme_mode,
            default_locale=public_read.default_locale,
            logo_url=public_read.logo_url,
            favicon_url=public_read.favicon_url,
            has_logo=public_read.has_logo,
            has_favicon=public_read.has_favicon,
        )

    cloud_container_config: DesktopCloudContainerConfig | None = None
    runtime_base_url: str | None = None
    runtime_health_url: str | None = None
    runtime_version_url: str | None = None
    if mode == "headmaster_remote":
        if not hasattr(request.app.state, "container_supervisor"):
            raise HTTPException(status_code=503, detail="Cloud runtime supervisor is not available")
        try:
            container = await request.app.state.container_supervisor.ensure_user_runtime(
                db,
                user,
                agent=assignment,
                runtime_env=runtime_env,
            )
            await db.commit()
            runtime_base_url = request.app.state.container_supervisor.public_endpoint_url(container)
            runtime_health_url = request.app.state.container_supervisor.runtime_health_url(container)
            runtime_version_url = request.app.state.container_supervisor.runtime_version_url(container)
            cloud_container_config = DesktopCloudContainerConfig(
                endpoint_url=runtime_base_url,
                container_id=container.id,
                api_server_key=container.api_server_key,
                forward_auth_token=request.app.state.container_supervisor.forward_auth_token(container),
                forward_auth_expires_at=request.app.state.container_supervisor.forward_auth_expires_at().isoformat(),
            )
        except ContainerSupervisorError as exc:
            await db.rollback()
            raise HTTPException(status_code=502, detail=f"Cloud runtime provision failed: {exc}") from exc

    return DesktopProvisionResponse(
        mode=mode,
        hermeshq_url=server_url,
        user=desktop_user_payload(user),
        capabilities=capabilities,
        runtime=DesktopRuntimeInfo(
            base_url=runtime_base_url,
            api_base_path="/v1",
            health_url=runtime_health_url,
            validate_url=f"{server_url}/api/desktop/runtime/validate",
            version_url=runtime_version_url,
            ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
        ),
        cloud_container_config=cloud_container_config,
        system_prompt_override=system_prompt_override,
        session_namespace=session_namespace,
        honcho_base_url=honcho_base_url,
        honcho_api_key=honcho_api_key,
        nous_api_key=nous_api_key,
        providers=providers,
        default_model=default_model,
        default_provider=default_provider,
        default_base_url=default_base_url,
        app_settings=app_settings,
        runtime_env=runtime_env,
    )


@router.post("/provision", response_model=DesktopProvisionResponse)
async def provision_desktop_runtime(
    payload: DesktopProvisionRequest,
    request: Request,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> DesktopProvisionResponse:
    response = await _build_provision_response(current_user, request, db)
    await _audit_log(
        db,
        current_user,
        "desktop.provision",
        "desktop_runtime",
        current_user.id,
        None,
        {"mode": response.mode, "capabilities": response.capabilities},
        {"client": payload.client, "version": payload.version, "platform": payload.platform},
    )
    return response


@router.get("/provision/current", response_model=DesktopProvisionResponse)
async def get_current_desktop_provision(
    request: Request,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> DesktopProvisionResponse:
    return await _build_provision_response(current_user, request, db)


@router.post("/runtime/validate", response_model=DesktopRuntimeValidateResponse)
async def validate_desktop_runtime(
    payload: DesktopRuntimeValidateRequest,
    current_user: User = Depends(get_authenticated_user),
    db: AsyncSession = Depends(get_db_session),
) -> DesktopRuntimeValidateResponse:
    # Verify the user is active — inactive users get no provision
    if not current_user.is_active:
        await _audit_log(
            db,
            current_user,
            "desktop.runtime_validate_denied",
            "desktop_runtime",
            current_user.id,
            None,
            {"reason": "user_inactive", "role": current_user.role},
            {"runtime_id": payload.runtime_id},
        )
        return DesktopRuntimeValidateResponse(
            allowed=False,
            capabilities=[],
            role=normalize_desktop_role(current_user.role),
            ttl_seconds=0,
        )

    role = normalize_desktop_role(current_user.role)
    capabilities = capabilities_for_role(role)
    if not is_capability_allowed(capabilities, payload.requested_capability):
        await _audit_log(
            db,
            current_user,
            "desktop.runtime_validate_denied",
            "desktop_runtime",
            current_user.id,
            None,
            {"requested_capability": payload.requested_capability, "role": role},
            {"runtime_id": payload.runtime_id},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Capability not allowed",
        )
    await _audit_log(
        db,
        current_user,
        "desktop.runtime_validate",
        "desktop_runtime",
        current_user.id,
        None,
        {"allowed": True, "capabilities": capabilities, "role": role},
        {"runtime_id": payload.runtime_id, "requested_capability": payload.requested_capability},
    )
    return DesktopRuntimeValidateResponse(
        allowed=True,
        capabilities=capabilities,
        role=role,
        ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
    )
