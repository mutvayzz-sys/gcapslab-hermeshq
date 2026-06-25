from fastapi import APIRouter, Depends, HTTPException, Request, status

from hermeshq.core.security import get_current_user
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
    resolve_desktop_mode,
)

router = APIRouter(prefix="/desktop", tags=["desktop"])


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _build_provision_response(user: User, request: Request) -> DesktopProvisionResponse:
    server_url = _base_url(request)
    capabilities = capabilities_for_role(user.role)
    mode = resolve_desktop_mode(user, request.app.state.settings)
    return DesktopProvisionResponse(
        mode=mode,
        hermeshq_url=server_url,
        user=desktop_user_payload(user),
        capabilities=capabilities,
        runtime=DesktopRuntimeInfo(
            validate_url=f"{server_url}/api/desktop/runtime/validate",
            ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
        ),
    )


@router.post("/provision", response_model=DesktopProvisionResponse)
async def provision_desktop_runtime(
    payload: DesktopProvisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DesktopProvisionResponse:
    return _build_provision_response(current_user, request)


@router.get("/provision/current", response_model=DesktopProvisionResponse)
async def get_current_desktop_provision(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DesktopProvisionResponse:
    return _build_provision_response(current_user, request)


@router.post("/runtime/validate", response_model=DesktopRuntimeValidateResponse)
async def validate_desktop_runtime(
    payload: DesktopRuntimeValidateRequest,
    current_user: User = Depends(get_current_user),
) -> DesktopRuntimeValidateResponse:
    role = normalize_desktop_role(current_user.role)
    capabilities = capabilities_for_role(role)
    if not is_capability_allowed(capabilities, payload.requested_capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Capability not allowed",
        )
    return DesktopRuntimeValidateResponse(
        allowed=True,
        capabilities=capabilities,
        role=role,
        ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
    )
