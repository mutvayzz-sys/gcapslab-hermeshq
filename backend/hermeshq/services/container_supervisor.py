from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.config import Settings, get_settings
from hermeshq.models.agent import Agent
from hermeshq.models.runtime_container import RuntimeContainer
from hermeshq.models.user import User

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("provisioning", "starting", "running")


class ContainerSupervisorError(RuntimeError):
    pass


class RuntimeContainerSupervisor:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def public_endpoint_url(self, container: RuntimeContainer) -> str:
        base = (
            self.settings.container_host_url
            or self.settings.public_base_url
            or "http://localhost:3420"
        ).rstrip("/")
        return f"{base}{container.endpoint_path}"

    def runtime_health_url(self, container: RuntimeContainer) -> str:
        return f"http://{container.container_name}:8080/health"

    async def ensure_user_runtime(
        self,
        db: AsyncSession,
        user: User,
        *,
        agent: Agent | None,
        runtime_env: dict[str, str],
        force_recreate: bool = False,
    ) -> RuntimeContainer:
        await self.cleanup_stale_user_runtimes(db, user.id)
        existing = await self._load_active_for_user(db, user.id)
        if existing and not force_recreate:
            if await self.refresh_health(db, existing):
                return existing
            await self.remove(db, existing)

        container = self._new_container(user, agent)
        db.add(container)
        await db.flush()
        await self._run_container(container, user, agent, runtime_env)
        container.status = "running"
        container.health_status = "unknown"
        container.started_at = datetime.now(UTC)
        container.error_message = None
        await db.flush()
        await self.refresh_health(db, container)
        return container

    async def cleanup_stale_user_runtimes(self, db: AsyncSession, user_id: str) -> None:
        result = await db.execute(
            select(RuntimeContainer)
            .where(RuntimeContainer.user_id == user_id, RuntimeContainer.status.in_(ACTIVE_STATUSES))
            .order_by(RuntimeContainer.created_at.desc())
        )
        containers = list(result.scalars().all())
        for stale in containers[1:]:
            await self.remove(db, stale)

    async def cleanup_removed_containers(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(RuntimeContainer).where(RuntimeContainer.status.in_(("stopped", "removed", "error")))
        )
        removed = 0
        for container in result.scalars().all():
            await self.remove(db, container)
            removed += 1
        return removed

    async def start(self, db: AsyncSession, container: RuntimeContainer) -> RuntimeContainer:
        await self._docker("start", container.container_name)
        container.status = "running"
        container.started_at = datetime.now(UTC)
        container.stopped_at = None
        container.error_message = None
        await db.flush()
        await self.refresh_health(db, container)
        return container

    async def stop(self, db: AsyncSession, container: RuntimeContainer) -> RuntimeContainer:
        await self._docker("stop", container.container_name)
        container.status = "stopped"
        container.stopped_at = datetime.now(UTC)
        await db.flush()
        return container

    async def restart(self, db: AsyncSession, container: RuntimeContainer) -> RuntimeContainer:
        await self._docker("restart", container.container_name)
        container.status = "running"
        container.started_at = datetime.now(UTC)
        container.stopped_at = None
        container.error_message = None
        await db.flush()
        await self.refresh_health(db, container)
        return container

    async def remove(self, db: AsyncSession, container: RuntimeContainer) -> RuntimeContainer:
        try:
            await self._docker("rm", "-f", container.container_name)
        except ContainerSupervisorError as exc:
            logger.warning("Docker remove failed for %s: %s", container.container_name, exc)
        container.status = "removed"
        container.stopped_at = datetime.now(UTC)
        await db.flush()
        return container

    async def refresh_health(self, db: AsyncSession, container: RuntimeContainer) -> bool:
        ok = False
        detail = None
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(self.runtime_health_url(container))
            ok = response.status_code < 500
            detail = response.text[:500] if not ok else None
        except Exception as exc:  # noqa: BLE001 - health is best-effort
            detail = str(exc)
        container.health_status = "healthy" if ok else "unhealthy"
        container.last_health_at = datetime.now(UTC)
        container.error_message = None if ok else detail
        if container.status in {"provisioning", "starting"} and ok:
            container.status = "running"
        await db.flush()
        return ok

    async def _load_active_for_user(self, db: AsyncSession, user_id: str) -> RuntimeContainer | None:
        result = await db.execute(
            select(RuntimeContainer)
            .where(RuntimeContainer.user_id == user_id, RuntimeContainer.status.in_(ACTIVE_STATUSES))
            .order_by(RuntimeContainer.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _new_container(self, user: User, agent: Agent | None) -> RuntimeContainer:
        suffix = secrets.token_hex(4)
        safe_user = user.id.replace("-", "")[:8]
        name = f"hermes-{safe_user}-{suffix}"
        return RuntimeContainer(
            user_id=user.id,
            organization_id=user.organization_id,
            agent_id=agent.id if agent else None,
            container_name=name,
            image=self.settings.runtime_container_image,
            status="provisioning",
            endpoint_path=f"/runtime/{name}",
            api_server_key=secrets.token_urlsafe(32),
        )

    async def _run_container(
        self,
        container: RuntimeContainer,
        user: User,
        agent: Agent | None,
        runtime_env: dict[str, str],
    ) -> None:
        env = {
            **runtime_env,
            "HERMES_MODE": "headmaster_remote",
            "HERMES_HQ_URL": (self.settings.container_host_url or self.settings.public_base_url or "").rstrip("/"),
            "USER_ID": user.id,
            "API_SERVER_ENABLED": "true",
            "API_SERVER_HOST": "0.0.0.0",
            "API_SERVER_PORT": "8080",
            "API_SERVER_KEY": container.api_server_key,
        }
        if agent:
            env["AGENT_ID"] = agent.id

        args = [
            "run",
            "-d",
            "--name",
            container.container_name,
            "--network",
            self.settings.runtime_container_network,
            "--label",
            f"hermeshq.runtime_container_id={container.id}",
            "--label",
            f"hermeshq.user_id={user.id}",
        ]
        for key, value in sorted(env.items()):
            if value is None:
                continue
            args.extend(["-e", f"{key}={value}"])
        args.append(container.image)
        await self._docker(*args)

    async def _docker(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            message = stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace")
            raise ContainerSupervisorError(message.strip() or f"docker {' '.join(args)} failed")
        return stdout.decode("utf-8", errors="replace").strip()
