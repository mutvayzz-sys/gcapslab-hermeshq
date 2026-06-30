import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user, require_admin
from hermeshq.database import get_db_session
from hermeshq.models import Organization, User
from hermeshq.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
async def list_organizations(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[OrganizationRead]:
    result = await db.execute(select(Organization).order_by(Organization.created_at.asc()))
    return list(result.scalars().all())


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationRead:
    existing = await db.execute(select(Organization).where(Organization.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization slug already exists")
    org = Organization(
        name=payload.name,
        slug=payload.slug,
        kind=payload.kind,
        default_mode=payload.default_mode,
        default_capabilities=payload.default_capabilities,
        system_prompt_override=payload.system_prompt_override,
        honcho_base_url=payload.honcho_base_url,
        honcho_jwt_secret=payload.honcho_jwt_secret,
        nous_api_key=payload.nous_api_key,
        nous_base_url=payload.nous_base_url,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationRead)
async def get_organization(
    org_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationRead:
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/{org_id}", response_model=OrganizationRead)
async def update_organization(
    org_id: str,
    payload: OrganizationUpdate,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> OrganizationRead:
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if payload.name is not None:
        org.name = payload.name
    if payload.slug is not None:
        org.slug = payload.slug
    if payload.kind is not None:
        org.kind = payload.kind
    if payload.default_mode is not None:
        org.default_mode = payload.default_mode
    if payload.default_capabilities is not None:
        org.default_capabilities = payload.default_capabilities
    if payload.system_prompt_override is not None:
        org.system_prompt_override = payload.system_prompt_override
    if payload.honcho_base_url is not None:
        org.honcho_base_url = payload.honcho_base_url
    if payload.honcho_jwt_secret is not None:
        org.honcho_jwt_secret = payload.honcho_jwt_secret
    if payload.nous_api_key is not None:
        org.nous_api_key = payload.nous_api_key
    if payload.nous_base_url is not None:
        org.nous_base_url = payload.nous_base_url
    await db.commit()
    await db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    await db.delete(org)
    await db.commit()
