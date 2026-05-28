from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user, require_admin
from hermeshq.database import get_db_session
from hermeshq.models.app_settings import AppSettings
from hermeshq.models.user import User
from hermeshq.models.user_m365_token import UserM365Token
from hermeshq.services.m365_oauth import (
    AVAILABLE_SCOPES,
    M365ConfigError,
    M365TokenError,
    complete_device_flow,
    get_instance_m365_config,
    get_valid_token,
    initiate_device_flow,
    revoke_user_token,
)

router = APIRouter(prefix="/m365", tags=["m365"])

# Almacenamiento en memoria para flows pendientes (user_id → flow_state)
# En producción con múltiples workers se debería usar Redis/cache compartido,
# pero para una instancia single-server es suficiente.
_pending_flows: dict[str, dict] = {}


# ─── Schemas ────────────────────────────────────────────────────────────────

class M365AppConfigRead(BaseModel):
    client_id: str | None
    tenant_id: str | None
    enabled_scopes: list[str]
    available_scopes: dict[str, str]
    configured: bool


class M365AppConfigUpdate(BaseModel):
    client_id: str | None = None
    tenant_id: str | None = None
    enabled_scopes: list[str] | None = None


class M365UserTokenRead(BaseModel):
    connected: bool
    account_email: str | None = None
    account_name: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None
    revoked: bool = False


class M365ConnectFlowRead(BaseModel):
    verification_uri: str
    user_code: str
    expires_in: int


class M365ConnectStatusRead(BaseModel):
    status: str
    account_email: str | None = None
    account_name: str | None = None


# ─── Admin: configuración de la instancia ───────────────────────────────────

@router.get("/config", response_model=M365AppConfigRead)
async def get_m365_config(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> M365AppConfigRead:
    config = await get_instance_m365_config(db)
    if config:
        return M365AppConfigRead(
            client_id=config["client_id"],
            tenant_id=config["tenant_id"],
            enabled_scopes=config["enabled_scopes"],
            available_scopes=AVAILABLE_SCOPES,
            configured=True,
        )
    settings = await db.get(AppSettings, "default")
    return M365AppConfigRead(
        client_id=settings.m365_client_id if settings else None,
        tenant_id=settings.m365_tenant_id if settings else None,
        enabled_scopes=[],
        available_scopes=AVAILABLE_SCOPES,
        configured=False,
    )


@router.put("/config", response_model=M365AppConfigRead)
async def update_m365_config(
    payload: M365AppConfigUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> M365AppConfigRead:
    settings = await db.get(AppSettings, "default")
    if not settings:
        settings = AppSettings(id="default")
        db.add(settings)

    if payload.client_id is not None:
        settings.m365_client_id = payload.client_id.strip() or None
    if payload.tenant_id is not None:
        settings.m365_tenant_id = payload.tenant_id.strip() or None
    if payload.enabled_scopes is not None:
        valid = [s for s in payload.enabled_scopes if s in AVAILABLE_SCOPES]
        settings.m365_enabled_scopes = valid

    await db.commit()
    await db.refresh(settings)

    configured = bool(
        (settings.m365_client_id or "").strip()
        and (settings.m365_tenant_id or "").strip()
    )
    return M365AppConfigRead(
        client_id=settings.m365_client_id,
        tenant_id=settings.m365_tenant_id,
        enabled_scopes=list(settings.m365_enabled_scopes or []),
        available_scopes=AVAILABLE_SCOPES,
        configured=configured,
    )


# ─── Admin: ver tokens de usuarios ──────────────────────────────────────────

@router.get("/admin/tokens", response_model=list[dict])
async def list_user_tokens(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    result = await db.execute(select(UserM365Token))
    tokens = result.scalars().all()
    return [
        {
            "id": t.id,
            "user_id": t.user_id,
            "account_email": t.account_email,
            "account_name": t.account_name,
            "scopes": t.scopes.split() if t.scopes else [],
            "expires_at": t.expires_at,
            "revoked": t.revoked_at is not None,
            "created_at": t.created_at,
        }
        for t in tokens
    ]


@router.delete("/admin/tokens/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_revoke_user_token(
    user_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await revoke_user_token(user_id, db)


# ─── Usuario: su propia cuenta M365 ─────────────────────────────────────────

@router.get("/me", response_model=M365UserTokenRead)
async def get_my_m365_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> M365UserTokenRead:
    result = await db.execute(
        select(UserM365Token).where(UserM365Token.user_id == current_user.id)
    )
    token_record = result.scalar_one_or_none()
    if not token_record:
        return M365UserTokenRead(connected=False)
    return M365UserTokenRead(
        connected=token_record.revoked_at is None,
        account_email=token_record.account_email,
        account_name=token_record.account_name,
        scopes=token_record.scopes.split() if token_record.scopes else [],
        expires_at=token_record.expires_at,
        revoked=token_record.revoked_at is not None,
    )


@router.post("/me/connect", response_model=M365ConnectFlowRead)
async def start_connect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> M365ConnectFlowRead:
    try:
        flow_state = await initiate_device_flow(db)
    except M365ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    _pending_flows[current_user.id] = flow_state
    return M365ConnectFlowRead(
        verification_uri=flow_state["verification_uri"],
        user_code=flow_state["user_code"],
        expires_in=flow_state["expires_in"],
    )


@router.get("/me/connect/status", response_model=M365ConnectStatusRead)
async def poll_connect_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> M365ConnectStatusRead:
    flow_state = _pending_flows.get(current_user.id)
    if not flow_state:
        raise HTTPException(status_code=404, detail="No hay un flujo de autenticación pendiente.")

    vault = request.app.state.secret_vault

    try:
        token_record = await complete_device_flow(
            flow_state=flow_state,
            vault=vault,
            db=db,
            user_id=current_user.id,
        )
        _pending_flows.pop(current_user.id, None)
        return M365ConnectStatusRead(
            status="connected",
            account_email=token_record.account_email,
            account_name=token_record.account_name,
        )
    except M365TokenError as exc:
        error_msg = str(exc)
        if "authorization_pending" in error_msg or "authorization_declined" in error_msg.lower():
            return M365ConnectStatusRead(status="pending")
        _pending_flows.pop(current_user.id, None)
        raise HTTPException(status_code=400, detail=error_msg) from exc
    except Exception as exc:
        _pending_flows.pop(current_user.id, None)
        raise HTTPException(status_code=500, detail="Error inesperado durante la autenticación.") from exc


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_my_m365(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    _pending_flows.pop(current_user.id, None)
    await revoke_user_token(current_user.id, db)
