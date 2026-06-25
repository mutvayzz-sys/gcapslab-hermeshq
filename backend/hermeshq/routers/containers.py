from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user, is_admin, require_admin
from hermeshq.database import get_db_session
from hermeshq.models.container import Container
from hermeshq.models.user import User
from hermeshq.schemas.container import (
    ContainerCreate,
    ContainerResponse,
    ContainerStartStopResponse,
)
from hermeshq.services.container_supervisor import ContainerSupervisor

router = APIRouter(prefix="/containers", tags=["containers"])


async def _get_supervisor(request) -> ContainerSupervisor:
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
    return container


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
    return None
