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
    DESKTOP_MODE,
    DESKTOP_RUNTIME_TTL_SECONDS,
    capabilities_for_role,
    desktop_user_payload,
    is_capability_allowed,
    normalize_desktop_role,
)

router = APIRouter(prefix="/desktop", tags=["desktop"])


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.post("/provision", response_model=DesktopProvisionResponse)
async def provision_desktop_runtime(
    payload: DesktopProvisionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DesktopProvisionResponse:
    server_url = _base_url(request)
    capabilities = capabilities_for_role(current_user.role)
    return DesktopProvisionResponse(
        mode=DESKTOP_MODE,
        hermeshq_url=server_url,
        user=desktop_user_payload(current_user),
        capabilities=capabilities,
        runtime=DesktopRuntimeInfo(
            validate_url=f"{server_url}/api/desktop/runtime/validate",
            ttl_seconds=DESKTOP_RUNTIME_TTL_SECONDS,
        ),
    )


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
