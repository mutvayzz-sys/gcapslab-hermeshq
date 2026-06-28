from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user, is_admin, require_admin
from hermeshq.database import get_db_session
from hermeshq.models.audit_log import AuditLog
from hermeshq.models.container import Container
from hermeshq.models.user import User
from hermeshq.schemas.container import (
    ContainerCreate,
    ContainerProvisionRequest,
    ContainerResponse,
    ContainerStartStopResponse,
)
from hermeshq.services.container_supervisor import ContainerSupervisor

router = APIRouter(prefix="/containers", tags=["containers"])


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


async def _get_supervisor(request: Request) -> ContainerSupervisor:
    supervisor = getattr(request.app.state, "container_supervisor", None)
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Container supervisor not available",
        )
    return supervisor


@router.get("", response_model=list[ContainerResponse])
async def list_containers(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[ContainerResponse]:
    if is_admin(current_user):
        result = await db.execute(select(Container).where(Container.is_active.is_(True)))
    else:
        result = await db.execute(
            select(Container).where(
                Container.user_id == current_user.id,
                Container.is_active.is_(True),
            )
        )
    return result.scalars().all()


@router.post("", response_model=ContainerResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    request: Request,
    payload: ContainerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    supervisor = await _get_supervisor(request)
    container = await supervisor.create_container(
        user=current_user,
        org_id=payload.organization_id,
    )
    await _audit_log(
        db,
        current_user,
        "container.create",
        "container",
        container.id,
        None,
        {"status": container.status, "image": container.image},
        {"name": container.name, "org_id": payload.organization_id},
    )
    return container


@router.post("/provision", response_model=ContainerResponse, status_code=status.HTTP_201_CREATED)
async def provision_user_container(
    request: Request,
    payload: ContainerProvisionRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    """Create and start a Hermes container for a given user. Admin only."""
    target_user = await db.get(User, payload.user_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = (
        await db.execute(
            select(Container).where(
                Container.user_id == target_user.id,
                Container.is_active.is_(True),
                Container.status != "destroyed",
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has an active container",
        )

    supervisor = await _get_supervisor(request)
    container = await supervisor.create_container(user=target_user, org_id=target_user.organization_id)

    if payload.name:
        c = await db.get(Container, container.id)
        if c:
            c.name = payload.name
            await db.commit()
            await db.refresh(c)
            container = c

    updated = await supervisor.start_container(container.id)

    await _audit_log(
        db,
        current_user,
        "container.provision",
        "container",
        updated.id,
        None,
        {"status": updated.status, "user_id": target_user.id},
        {"target_user": target_user.username, "image": updated.image},
    )
    return updated


@router.get("/{container_id}", response_model=ContainerResponse)
async def get_container(
    container_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    container = await db.get(Container, container_id)
    if not container or not container.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    if not is_admin(current_user) and container.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return container


@router.post("/{container_id}/start", response_model=ContainerStartStopResponse)
async def start_container(
    container_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerStartStopResponse:
    container = await db.get(Container, container_id)
    if not container or not container.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    if not is_admin(current_user) and container.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    supervisor = await _get_supervisor(request)
    updated = await supervisor.start_container(container_id)
    await _audit_log(
        db,
        current_user,
        "container.start",
        "container",
        container_id,
        {"status": container.status},
        {"status": updated.status, "health_check_url": updated.health_check_url},
        None,
    )
    return ContainerStartStopResponse(
        container_id=updated.id,
        status=updated.status,
        health_check_url=updated.health_check_url,
    )


@router.post("/{container_id}/stop", response_model=ContainerStartStopResponse)
async def stop_container(
    container_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerStartStopResponse:
    container = await db.get(Container, container_id)
    if not container or not container.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    if not is_admin(current_user) and container.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    supervisor = await _get_supervisor(request)
    updated = await supervisor.stop_container(container_id)
    await _audit_log(
        db,
        current_user,
        "container.stop",
        "container",
        container_id,
        {"status": container.status},
        {"status": updated.status},
        None,
    )
    return ContainerStartStopResponse(
        container_id=updated.id,
        status=updated.status,
        health_check_url=updated.health_check_url,
    )


@router.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_container(
    container_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    container = await db.get(Container, container_id)
    if not container or not container.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    if not is_admin(current_user) and container.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    supervisor = await _get_supervisor(request)
    await supervisor.destroy_container(container_id)
    await _audit_log(
        db,
        current_user,
        "container.destroy",
        "container",
        container_id,
        {"status": container.status, "is_active": container.is_active},
        {"status": "destroyed", "is_active": False},
        None,
    )
    return None
