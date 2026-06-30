from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.core.security import get_current_user, require_admin
from hermeshq.database import get_db_session
from hermeshq.models.agent import Agent
from hermeshq.models.agent_assignment import AgentAssignment
from hermeshq.models.runtime_container import RuntimeContainer
from hermeshq.models.organization import Organization
from hermeshq.models.user import User
from hermeshq.schemas.container import (
    RuntimeContainerHealthRead,
    RuntimeContainerProvisionRequest,
    RuntimeContainerProvisionResponse,
    RuntimeContainerRead,
    UserContainerResponse,
)
from hermeshq.services.container_supervisor import ContainerSupervisorError

router = APIRouter(prefix="/containers", tags=["containers"])


async def _assigned_agent(db: AsyncSession, user: User, requested_agent_id: str | None = None) -> Agent | None:
    if requested_agent_id:
        return await db.get(Agent, requested_agent_id)
    result = await db.execute(
        select(Agent)
        .join(AgentAssignment, AgentAssignment.agent_id == Agent.id)
        .where(AgentAssignment.user_id == user.id, Agent.is_archived.is_(False))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _runtime_env(request: Request, agent: Agent | None) -> dict[str, str]:
    if not agent:
        return {}
    try:
        env = await request.app.state.installation_manager.build_process_env(agent, include_channels=False)
    except Exception:
        return {}
    allowed_prefixes = (
        "API_SERVER_",
        "NOUS_",
        "OPENAI_",
        "KIMI_",
        "GLM_",
        "ZAI_",
        "Z_AI_",
        "OPENROUTER_",
        "ANTHROPIC_",
        "GEMINI_",
        "GOOGLE_",
        "AUXILIARY_",
    )
    return {key: value for key, value in env.items() if key.startswith(allowed_prefixes)}


async def _get_container(db: AsyncSession, container_id: str) -> RuntimeContainer:
    container = await db.get(RuntimeContainer, container_id)
    if not container:
        raise HTTPException(status_code=404, detail="Runtime container not found")
    return container


@router.get("/mine", response_model=UserContainerResponse)
async def get_my_container(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserContainerResponse:
    """Return the active container credentials for the current user.
    Used by the console web chat and any other client that needs the
    Runs API endpoint + Bearer key without the full desktop provision flow."""
    if not hasattr(request.app.state, "container_supervisor"):
        raise HTTPException(status_code=503, detail="Container supervisor not available")

    result = await db.execute(
        select(RuntimeContainer)
        .where(RuntimeContainer.user_id == current_user.id)
        .order_by(RuntimeContainer.created_at.desc())
        .limit(1)
    )
    container = result.scalar_one_or_none()
    if not container:
        raise HTTPException(status_code=404, detail="No active container for this user")

    return UserContainerResponse(
        endpoint_url=request.app.state.container_supervisor.public_endpoint_url(container),
        api_server_key=container.api_server_key,
        container_name=container.container_name,
        status=container.status,
    )


@router.get("", response_model=list[RuntimeContainerRead])
async def list_containers(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> list[RuntimeContainer]:
    result = await db.execute(select(RuntimeContainer).order_by(RuntimeContainer.created_at.desc()))
    return list(result.scalars().all())


@router.post("/provision", response_model=RuntimeContainerProvisionResponse, status_code=status.HTTP_201_CREATED)
async def provision_container(
    payload: RuntimeContainerProvisionRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainerProvisionResponse:
    target_user = await db.get(User, payload.user_id or admin_user.id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    agent = await _assigned_agent(db, target_user, payload.agent_id)
    env = await _runtime_env(request, agent)
    if target_user.organization_id:
        org = await db.get(Organization, target_user.organization_id)
        if org and org.nous_api_key:
            env["NOUS_API_KEY"] = org.nous_api_key
    try:
        container = await request.app.state.container_supervisor.ensure_user_runtime(
            db,
            target_user,
            agent=agent,
            runtime_env=env,
            force_recreate=payload.force_recreate,
        )
    except ContainerSupervisorError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Runtime container provision failed: {exc}") from exc
    await db.commit()
    await db.refresh(container)
    return RuntimeContainerProvisionResponse(
        container=container,
        endpoint_url=request.app.state.container_supervisor.public_endpoint_url(container),
        api_server_key=container.api_server_key,
    )


@router.post("/cleanup")
async def cleanup_containers(
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, int]:
    removed = await request.app.state.container_supervisor.cleanup_removed_containers(db)
    await db.commit()
    return {"removed": removed}


@router.get("/{container_id}", response_model=RuntimeContainerRead)
async def get_container(
    container_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainer:
    return await _get_container(db, container_id)


@router.post("/{container_id}/start", response_model=RuntimeContainerRead)
async def start_container(
    container_id: str,
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainer:
    container = await _get_container(db, container_id)
    try:
        await request.app.state.container_supervisor.start(db, container)
    except ContainerSupervisorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(container)
    return container


@router.post("/{container_id}/stop", response_model=RuntimeContainerRead)
async def stop_container(
    container_id: str,
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainer:
    container = await _get_container(db, container_id)
    try:
        await request.app.state.container_supervisor.stop(db, container)
    except ContainerSupervisorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(container)
    return container


@router.post("/{container_id}/restart", response_model=RuntimeContainerRead)
async def restart_container(
    container_id: str,
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainer:
    container = await _get_container(db, container_id)
    try:
        await request.app.state.container_supervisor.restart(db, container)
    except ContainerSupervisorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(container)
    return container


@router.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container(
    container_id: str,
    request: Request,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    container = await _get_container(db, container_id)
    await request.app.state.container_supervisor.remove(db, container)
    await db.commit()


@router.get("/{container_id}/health", response_model=RuntimeContainerHealthRead)
async def container_health(
    container_id: str,
    request: Request,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeContainerHealthRead:
    container = await _get_container(db, container_id)
    ok = await request.app.state.container_supervisor.refresh_health(db, container)
    await db.commit()
    return RuntimeContainerHealthRead(
        container_id=container.id,
        status=container.health_status or "unknown",
        endpoint_url=request.app.state.container_supervisor.public_endpoint_url(container),
        runtime_url=request.app.state.container_supervisor.runtime_health_url(container),
        ok=ok,
        detail=container.error_message,
    )
