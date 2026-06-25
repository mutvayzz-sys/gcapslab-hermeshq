"""Manages persistent `hermes gateway` processes for agents with api_server_enabled=True.

Each enabled agent gets its own long-running `hermes gateway` subprocess that exposes
an OpenAI-compatible API at http://host:{api_port}/v1. The gateway reads its config
from the agent's HERMES_HOME/.env (written by HermesInstallationManager._sync_dotenv).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hermeshq.models.agent import Agent
from hermeshq.services.hermes_installation import HermesInstallationManager

logger = logging.getLogger(__name__)

_GATEWAY_BOOT_DELAY = 1.5  # seconds to wait after spawning before logging "started"


class AgentApiGatewaySupervisor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        installation_manager: HermesInstallationManager,
    ) -> None:
        self._session_factory = session_factory
        self._installation_manager = installation_manager
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._monitor_tasks: dict[str, asyncio.Task] = {}

    async def bootstrap(self) -> None:
        """Restart API gateways for all running agents that have api_server_enabled."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Agent).where(
                    Agent.api_server_enabled.is_(True),
                    Agent.status == "running",
                    Agent.is_archived.is_(False),
                    Agent.api_port.is_not(None),
                )
            )
            agents = list(result.scalars().all())

        for agent in agents:
            try:
                await self.start(agent)
            except Exception:
                logger.exception("Failed to bootstrap API gateway for agent %s", agent.id)

    async def start(self, agent: Agent) -> None:
        """Start the hermes gateway for an agent. No-op if already running."""
        if not agent.api_server_enabled or not agent.api_port:
            return
        if agent.id in self._processes:
            proc = self._processes[agent.id]
            if proc.returncode is None:
                return  # already running

        # Sync installation so .env has API_SERVER_* vars before we launch.
        try:
            await self._installation_manager.sync_agent_installation(agent)
        except Exception:
            logger.warning("sync_agent_installation failed for %s; gateway may use stale .env", agent.id)

        runtime = await self._installation_manager.resolve_hermes_runtime(agent)
        hermes_home = self._installation_manager.build_hermes_home(agent.workspace_path)
        env = await self._installation_manager.build_process_env(agent)
        env["HERMES_HOME"] = str(hermes_home)

        process = await asyncio.create_subprocess_exec(
            runtime.hermes_bin,
            "gateway",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._processes[agent.id] = process
        self._monitor_tasks[agent.id] = asyncio.create_task(
            self._monitor(agent.id, process),
            name=f"api-gw-monitor-{agent.id[:8]}",
        )
        logger.info(
            "API gateway started for agent %s on port %d (pid=%d)",
            agent.id,
            agent.api_port,
            process.pid,
        )

    async def stop(self, agent_id: str) -> None:
        """Terminate the hermes gateway for an agent."""
        proc = self._processes.pop(agent_id, None)
        task = self._monitor_tasks.pop(agent_id, None)
        if task:
            task.cancel()
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except (TimeoutError, ProcessLookupError):
                with __import__("contextlib").suppress(ProcessLookupError):
                    proc.kill()
            logger.info("API gateway stopped for agent %s", agent_id)

    async def restart(self, agent: Agent) -> None:
        await self.stop(agent.id)
        await self.start(agent)

    async def shutdown(self) -> None:
        """Terminate all running gateways (called on app shutdown)."""
        for agent_id in list(self._processes):
            await self.stop(agent_id)

    def is_running(self, agent_id: str) -> bool:
        proc = self._processes.get(agent_id)
        return proc is not None and proc.returncode is None

    async def _monitor(self, agent_id: str, proc: asyncio.subprocess.Process) -> None:
        """Log stderr from the gateway process and clean up when it exits."""
        try:
            assert proc.stderr is not None
            async for line in proc.stderr:
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    logger.debug("api-gw[%s]: %s", agent_id[:8], text)
            await proc.wait()
            if proc.returncode not in (0, -15):  # -15 = SIGTERM (normal stop)
                logger.warning(
                    "API gateway for agent %s exited unexpectedly (code=%s)",
                    agent_id,
                    proc.returncode,
                )
        except asyncio.CancelledError:
            pass
        finally:
            self._processes.pop(agent_id, None)
            self._monitor_tasks.pop(agent_id, None)
