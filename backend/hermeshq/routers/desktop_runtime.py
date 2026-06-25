from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user
from hermeshq.database import get_db_session
from hermeshq.models.audit_log import AuditLog
from hermeshq.models.user import User
from hermeshq.schemas.desktop_runtime import (
    DesktopProvisionRequest,
    DesktopProvisionResponse,
    DesktopRuntimeInfo,
    DesktopRuntimeValidateRequest,
    DesktopRuntimeValidateResponse,
)
from hermeshq.services.desktop_runtime import (
    DESKTOP_RUNTIME_TTL_SECONDS,
    capabilities_for_role,
    desktop_user_payload,
    is_capability_allowed,
    normalize_desktop_role,
    resolve_container_config,
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
    mode = resolve_desktop_mode(user, request.app.state.settings)
    cloud_container_config = await resolve_container_config(user, request.app.state.settings, db)
    
    # Phase 6.3: Resolve system prompt override from organization
    system_prompt_override: str | None = None
    if user.organization_id:
        from hermeshq.models.organization import Organization
        org = await db.get(Organization, user.organization_id)
        if org:
            system_prompt_override = org.system_prompt_override
    
    # Phase 8: Cross-device session namespace
    from hermeshq.services.cross_device_session import derive_session_namespace
    session_namespace = derive_session_namespace(user)

    return DesktopProvisionResponse(
        mode=mode,
        hermeshq_url=server_url,
        user=desktop_user_payload(user),
        capabilities=capabilities,
        runtime=DesktopRuntimeInfo(
            validate_url=f"{server_url}/api/desktop/runtime/validate",
            ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
        ),
        cloud_container_config=cloud_container_config,
        system_prompt_override=system_prompt_override,
        session_namespace=session_namespace,
    )


@router.post("/provision", response_model=DesktopProvisionResponse)
async def provision_desktop_runtime(
    payload: DesktopProvisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DesktopProvisionResponse:
    return await _build_provision_response(current_user, request, db)


@router.post("/runtime/validate", response_model=DesktopRuntimeValidateResponse)
async def validate_desktop_runtime(
    payload: DesktopRuntimeValidateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> DesktopRuntimeValidateResponse:
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
