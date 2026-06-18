"""Agent avatar endpoints – get, upload, delete."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy import select as sql_select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from hermeshq.core.security import ensure_agent_access, get_current_user
from hermeshq.database import get_db_session
from hermeshq.models.agent import Agent
from hermeshq.models.task import Task
from hermeshq.models.user import User
from hermeshq.routers.agents_shared import (
    _agent_avatar_base,
    _build_avatar_path,
    _serialize_agent,
)
from hermeshq.schemas.agent import AgentRead, AvatarGenerationRead
from hermeshq.services.avatar import (
    build_avatar_dir,
    delete_avatar_files as _delete_avatar_files_shared,
    resolve_media_type,
    validate_and_save_avatar,
)
from hermeshq.services.avatar_generator import generate_avatar
from hermeshq.services.task_board import next_board_order, runtime_status_to_board_column

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/{agent_id}/avatar", include_in_schema=False)
async def get_agent_avatar(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    agent = await db.get(Agent, agent_id)
    if not agent or not agent.avatar_filename:
        raise HTTPException(status_code=404, detail="Avatar not found")
    avatar_path = _build_avatar_path(agent)
    if not avatar_path or not avatar_path.exists():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(avatar_path, media_type=resolve_media_type(avatar_path))


@router.post("/{agent_id}/avatar/generate-ai", response_model=AvatarGenerationRead)
async def generate_ai_avatar(
    agent_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Request the HQ Operator to generate an AI avatar for the agent."""
    agent = await ensure_agent_access(db, current_user, agent_id)

    # Find HQ Operator agent
    operator_result = await db.execute(
        sql_select(Agent).where(Agent.slug == "hq-operator").limit(1)
    )
    operator = operator_result.scalar_one_or_none()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail="HQ Operator agent not found. Create an agent with slug 'hq-operator' first.",
        )

    agent_name = agent.friendly_name or agent.name or "Agent"
    agent_desc = agent.description or ""

    prompt = (
        f"Generate a unique avatar image for the agent named '{agent_name}'."
        f"{' Description: ' + agent_desc + '.' if agent_desc else ''}"
        f" The image should be a simple, clean, modern icon-style avatar"
        f" suitable for a chatbot or AI assistant."
        f" Use warm, professional colors."
        f" Save the image as a PNG file in your work/ directory"
        f" using the filename 'avatar.png'."
        f" It will be automatically applied to the agent."
    )

    task = Task(
        agent_id=operator.id,
        title=f"Generate AI avatar for {agent_name}",
        prompt=prompt,
        priority=3,
        metadata_json={
            "avatar_generation": True,
            "target_agent_id": agent_id,
        },
    )
    task.board_column = runtime_status_to_board_column(task.status)
    task.board_order = next_board_order()
    task.board_manual = False
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Submit task if operator is running
    if operator.status == "running":
        try:
            await request.app.state.supervisor.submit_task(task.id)
        except Exception:  # noqa: BLE001  # supervisor task submit best-effort
            logger.debug("Failed to submit avatar-update task; will be picked up on next start", exc_info=True)

    return {
        "status": "submitted",
        "task_id": task.id,
        "operator_id": operator.id,
        "operator_status": operator.status,
    }


@router.post("/{agent_id}/avatar/generate", response_model=AgentRead)
async def generate_agent_avatar(
    agent_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AgentRead:
    """Generate a deterministic avatar from the agent's name (gradient + initials)."""
    agent = await ensure_agent_access(db, current_user, agent_id)
    avatar_base = _agent_avatar_base()
    content, filename = generate_avatar(agent.friendly_name or agent.name or "Agent")

    from hermeshq.services.avatar import build_avatar_dir
    avatar_dir = build_avatar_dir(avatar_base, agent_id)
    avatar_dir.mkdir(parents=True, exist_ok=True)

    # Remove existing avatar files
    for existing in avatar_dir.iterdir():
        if existing.is_file() or existing.is_symlink():
            existing.unlink()

    (avatar_dir / filename).write_bytes(content)
    agent.avatar_filename = filename
    await db.commit()
    await db.refresh(agent)
    result = await db.execute(select(Agent).options(selectinload(Agent.node)).where(Agent.id == agent_id))
    return _serialize_agent(request, result.scalar_one())


@router.post("/{agent_id}/avatar", response_model=AgentRead)
async def upload_agent_avatar(
    agent_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AgentRead:
    agent = await ensure_agent_access(db, current_user, agent_id)
    avatar_filename = await validate_and_save_avatar(_agent_avatar_base(), agent_id, file)
    agent.avatar_filename = avatar_filename
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        avatar_file = build_avatar_dir(_agent_avatar_base(), agent_id) / avatar_filename
        avatar_file.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to save avatar")
    await db.refresh(agent)
    result = await db.execute(select(Agent).options(selectinload(Agent.node)).where(Agent.id == agent_id))
    return _serialize_agent(request, result.scalar_one())


@router.delete("/{agent_id}/avatar", response_model=AgentRead)
async def delete_agent_avatar(
    agent_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AgentRead:
    agent = await ensure_agent_access(db, current_user, agent_id)
    _delete_avatar_files_shared(_agent_avatar_base(), agent_id)
    agent.avatar_filename = None
    await db.commit()
    await db.refresh(agent)
    result = await db.execute(select(Agent).options(selectinload(Agent.node)).where(Agent.id == agent_id))
    return _serialize_agent(request, result.scalar_one())
