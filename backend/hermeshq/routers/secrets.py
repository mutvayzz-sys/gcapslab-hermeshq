import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import require_admin
from hermeshq.database import get_db_session
from hermeshq.models.secret import Secret
from hermeshq.models.user import User
from hermeshq.schemas.secret import SecretCreate, SecretRead, SecretUpdate
from hermeshq.services.audit import extract_ip, record_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/secrets", tags=["secrets"])


@router.get("", response_model=list[SecretRead])
async def list_secrets(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[SecretRead]:
    result = await db.execute(select(Secret).order_by(Secret.created_at.asc()))
    return [SecretRead.model_validate(secret) for secret in result.scalars().all()]


@router.post("", response_model=SecretRead, status_code=status.HTTP_201_CREATED)
async def create_secret(
    payload: SecretCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> SecretRead:
    vault = request.app.state.secret_vault
    secret = Secret(
        name=payload.name,
        provider=payload.provider,
        value_enc=vault.encrypt(payload.value),
    )
    db.add(secret)
    await db.flush()
    await record_audit(
        db,
        action="secret.create",
        target_type="secret",
        target_id=secret.id,
        target_name=secret.name,
        actor_id=current_user.id,
        actor_username=current_user.username,
        actor_role=current_user.role,
        ip_address=extract_ip(request),
    )
    await db.commit()
    await db.refresh(secret)
    return SecretRead.model_validate(secret)


@router.put("/{secret_id}", response_model=SecretRead)
async def update_secret(
    secret_id: str,
    payload: SecretUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> SecretRead:
    secret = await db.get(Secret, secret_id)
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    if payload.provider is not None:
        secret.provider = payload.provider
    if payload.value is not None:
        secret.value_enc = request.app.state.secret_vault.encrypt(payload.value)
    await record_audit(
        db,
        action="secret.update",
        target_type="secret",
        target_id=secret.id,
        target_name=secret.name,
        actor_id=current_user.id,
        actor_username=current_user.username,
        actor_role=current_user.role,
        ip_address=extract_ip(request),
        details={"fields_changed": [k for k, v in payload.model_dump(exclude_unset=True).items() if k != "value"]},
    )
    await db.commit()
    await db.refresh(secret)
    return SecretRead.model_validate(secret)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    secret_id: str,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    secret = await db.get(Secret, secret_id)
    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")
    await record_audit(
        db,
        action="secret.delete",
        target_type="secret",
        target_id=secret.id,
        target_name=secret.name,
        actor_id=current_user.id,
        actor_username=current_user.username,
        actor_role=current_user.role,
        ip_address=extract_ip(request),
    )
    await db.delete(secret)
    await db.commit()
