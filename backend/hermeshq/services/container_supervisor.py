from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hermeshq.config import Settings, get_settings
from hermeshq.models.container import Container
from hermeshq.models.user import User

logger = logging.getLogger(__name__)

# Optional docker SDK import; if not available we fall back to subprocess.
try:
    import docker as _docker_sdk
except ImportError:
    _docker_sdk = None  # type: ignore[assignment]


class ContainerSupervisor:
    """Manages per-user Docker containers on the Mac Mini."""

    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self._health_monitor_task: asyncio.Task | None = None
        self._docker: object | None = None
        if _docker_sdk is not None:
            try:
                self._docker = _docker_sdk.from_env()
                logger.info("ContainerSupervisor: docker SDK initialised")
            except Exception as exc:  # noqa: BLE001
                logger.warning("ContainerSupervisor: docker SDK unavailable (%s), will use subprocess fallback", exc)
        else:
            logger.warning("ContainerSupervisor: docker SDK not installed, will use subprocess fallback")

    @classmethod
    def from_app_state(cls, db: AsyncSession) -> "ContainerSupervisor":
        """Create a supervisor instance from FastAPI app state (requires db.bind)."""
        # This is a convenience factory for use inside routers where we have a db session
        # but not the full app state.  In practice the lifespan creates the canonical
        # instance and stores it on app.state.container_supervisor.
        from hermeshq.config import get_settings
        settings = get_settings()
        # Use the session's engine to build a factory
        engine = db.bind
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return cls(settings, factory)

    # -- public API ----------------------------------------------------------

    async def create_container(self, user: User, org_id: str | None = None) -> Container:
        """Create a new container record in the DB (status='pending')."""
        name = f"hermes-{user.id[:8]}-{uuid.uuid4().hex[:8]}"
        container = Container(
            user_id=user.id,
            organization_id=org_id,
            name=name,
            status="pending",
            image="hermes:latest",
        )
        async with self.session_factory() as session:
            session.add(container)
            await session.commit()
            await session.refresh(container)
        logger.info("Created container record %s for user %s", container.id, user.id)
        return container

    async def start_container(self, container_id: str) -> Container:
        """Start the Docker container and update the DB record."""
        async with self.session_factory() as session:
            container = await session.get(Container, container_id)
            if not container:
                raise ValueError(f"Container {container_id} not found")
            if container.status == "running":
                logger.warning("Container %s is already running", container_id)
                return container

            container.status = "creating"
            await session.commit()
            await session.refresh(container)

            # Prepare host data directory
            host_data_dir = os.path.join("/data", "containers", container.user_id)
            os.makedirs(host_data_dir, exist_ok=True)

            # Build environment variables
            hq_url = self.settings.public_base_url or "http://localhost:8000"
            env_vars = {
                "HERMES_MODE": "headmaster_remote",
                "HERMES_HQ_URL": hq_url,
                "USER_ID": container.user_id,
            }
            container.env_vars = json.dumps(env_vars)

            # Build volume mounts
            volume_mounts = [{"host_path": host_data_dir, "container_path": "/app/data"}]
            container.volume_mounts = json.dumps(volume_mounts)

            # Determine port mapping: expose container 8080 to an ephemeral host port
            mapped_port = await self._run_container(
                container.name,
                container.image,
                container_ports={"8080/tcp": None},  # docker assigns ephemeral port
                volumes={host_data_dir: {"bind": "/app/data", "mode": "rw"}},
                environment=env_vars,
            )

            container.status = "running"
            container.health_check_url = f"http://localhost:{mapped_port}/health"
            container.ports = json.dumps({"8080": mapped_port})
            await session.commit()
            await session.refresh(container)

        logger.info("Container %s started on port %s", container_id, mapped_port)
        return container

    async def stop_container(self, container_id: str) -> Container:
        """Stop a running Docker container."""
        async with self.session_factory() as session:
            container = await session.get(Container, container_id)
            if not container:
                raise ValueError(f"Container {container_id} not found")
            if container.status not in ("running", "creating", "error"):
                logger.warning("Container %s is not running (status=%s)", container_id, container.status)
                return container

            docker_id = container.docker_container_id
            if docker_id:
                await self._docker_stop(docker_id)
            else:
                logger.warning("Container %s has no docker_container_id to stop", container_id)

            container.status = "stopped"
            await session.commit()
            await session.refresh(container)

        logger.info("Container %s stopped", container_id)
        return container

    async def destroy_container(self, container_id: str) -> None:
        """Destroy a container (remove from Docker and mark inactive)."""
        async with self.session_factory() as session:
            container = await session.get(Container, container_id)
            if not container:
                raise ValueError(f"Container {container_id} not found")

            docker_id = container.docker_container_id
            if docker_id:
                await self._docker_rm(docker_id)
            else:
                logger.warning("Container %s has no docker_container_id to remove", container_id)

            container.status = "destroyed"
            container.is_active = False
            await session.commit()

        logger.info("Container %s destroyed", container_id)

    async def get_user_container(self, user_id: str) -> Container | None:
        """Return the active container for a user, or None."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Container).where(
                    Container.user_id == user_id,
                    Container.is_active.is_(True),
                    Container.status != "destroyed",
                )
            )
            return result.scalar_one_or_none()

    async def health_check(self, container_id: str) -> bool:
        """HTTP GET to the container's health endpoint."""
        async with self.session_factory() as session:
            container = await session.get(Container, container_id)
            if not container:
                logger.warning("Health check: container %s not found", container_id)
                return False
            if container.status != "running":
                return False
            url = container.health_check_url
            if not url:
                logger.warning("Health check: container %s has no health_check_url", container_id)
                return False

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    healthy = response.status_code == 200
            except Exception as exc:  # noqa: BLE001
                logger.warning("Health check failed for %s: %s", container_id, exc)
                healthy = False

            if healthy:
                container.last_healthy_at = datetime.now(timezone.utc).isoformat()
            else:
                container.status = "error"
                container.error_message = f"Health check failed at {datetime.now(timezone.utc).isoformat()}"
            await session.commit()
            return healthy

    async def start_health_monitor(self) -> None:
        """Start the background health-monitor loop."""
        if self._health_monitor_task is not None:
            logger.warning("Health monitor already running")
            return
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        logger.info("Health monitor started")

    async def stop_health_monitor(self) -> None:
        """Cancel the background health-monitor loop."""
        if self._health_monitor_task is not None:
            self._health_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_monitor_task
            self._health_monitor_task = None
            logger.info("Health monitor stopped")

    # -- Docker helpers ------------------------------------------------------

    async def _run_container(
        self,
        name: str,
        image: str,
        container_ports: dict,
        volumes: dict,
        environment: dict,
    ) -> int:
        """Run a Docker container and return the mapped host port."""
        if self._docker is not None:
            return await self._docker_run_sdk(name, image, container_ports, volumes, environment)
        return await self._docker_run_subprocess(name, image, container_ports, volumes, environment)

    async def _docker_run_sdk(
        self,
        name: str,
        image: str,
        container_ports: dict,
        volumes: dict,
        environment: dict,
    ) -> int:
        """Run container via docker-py SDK."""
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            None,
            lambda: self._docker.containers.run(  # type: ignore[union-attr]
                image,
                name=name,
                detach=True,
                ports=container_ports,
                volumes=volumes,
                environment=environment,
            ),
        )
        # Refresh to get NetworkSettings
        container.reload()
        docker_id = container.id
        mapped_port = container.ports.get("8080/tcp", [{}])[0].get("HostPort", "0")
        # Update the DB record with docker_container_id — we do this in the caller,
        # but we need the id here.  Return both via a simple trick: store temporarily.
        self._last_docker_id = docker_id  # type: ignore[attr-defined]
        return int(mapped_port)

    async def _docker_run_subprocess(
        self,
        name: str,
        image: str,
        container_ports: dict,
        volumes: dict,
        environment: dict,
    ) -> int:
        """Run container via subprocess fallback."""
        port_spec = "-P"  # publish all exposed ports to ephemeral host ports
        env_args = [f"-e {k}={v}" for k, v in environment.items()]
        vol_args = [f"-v {host}:{bind['bind']}:{bind['mode']}" for host, bind in volumes.items()]
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            port_spec,
            *env_args,
            *vol_args,
            image,
        ]
        logger.info("Docker subprocess cmd: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"docker run failed: {stderr.decode()}")
        docker_id = stdout.decode().strip()
        self._last_docker_id = docker_id  # type: ignore[attr-defined]

        # Inspect to get mapped port
        inspect_proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format",
            "{{(index (index .NetworkSettings.Ports \"8080/tcp\") 0).HostPort}}",
            docker_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        inspect_stdout, inspect_stderr = await inspect_proc.communicate()
        if inspect_proc.returncode != 0:
            raise RuntimeError(f"docker inspect failed: {inspect_stderr.decode()}")
        mapped_port = int(inspect_stdout.decode().strip())
        return mapped_port

    async def _docker_stop(self, docker_container_id: str) -> None:
        if self._docker is not None:
            loop = asyncio.get_event_loop()
            try:
                container = await loop.run_in_executor(None, lambda: self._docker.containers.get(docker_container_id))  # type: ignore[union-attr]
                await loop.run_in_executor(None, container.stop)
            except Exception as exc:  # noqa: BLE001
                logger.warning("docker stop SDK failed for %s: %s", docker_container_id, exc)
        else:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stop", docker_container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning("docker stop subprocess failed for %s: %s", docker_container_id, stderr.decode())

    async def _docker_rm(self, docker_container_id: str) -> None:
        if self._docker is not None:
            loop = asyncio.get_event_loop()
            try:
                container = await loop.run_in_executor(None, lambda: self._docker.containers.get(docker_container_id))  # type: ignore[union-attr]
                await loop.run_in_executor(None, container.remove, True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("docker rm SDK failed for %s: %s", docker_container_id, exc)
        else:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", docker_container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.warning("docker rm subprocess failed for %s: %s", docker_container_id, stderr.decode())

    # -- health monitor loop -------------------------------------------------

    async def _health_monitor_loop(self) -> None:
        """Background task: every 30s, check all running containers."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await self._check_all_running()
                except Exception:  # noqa: BLE001
                    logger.exception("Health monitor periodic check error")
        except asyncio.CancelledError:
            return

    async def _check_all_running(self) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Container).where(
                    Container.status == "running",
                    Container.is_active.is_(True),
                )
            )
            running = result.scalars().all()

        for container in running:
            try:
                await self.health_check(container.id)
            except Exception:  # noqa: BLE001
                logger.exception("Health check error for container %s", container.id)
