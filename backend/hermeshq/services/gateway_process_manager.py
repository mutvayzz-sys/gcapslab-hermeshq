"""Gateway process lifecycle management — spawn, stop, monitor gateway subprocesses."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hermeshq.core.events import EventBroker
from hermeshq.models.activity import ActivityLog
from hermeshq.models.agent import Agent
from hermeshq.models.base import utcnow
from hermeshq.models.messaging_channel import MessagingChannel
from hermeshq.services.hermes_installation import HermesInstallationError, HermesInstallationManager

from hermeshq.services.gateway_types import GatewayProcessHandle

logger = logging.getLogger(__name__)

GATEWAY_STARTUP_STABILIZATION_SECONDS = 2


class GatewayProcessManager:
    """Manages gateway subprocess lifecycle: start, stop, monitor, terminate."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_broker: EventBroker,
        installation_manager: HermesInstallationManager,
        processes: dict[str, GatewayProcessHandle],
        enterprise_gateways: object | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.event_broker = event_broker
        self.installation_manager = installation_manager
        self.processes = processes
        self._enterprise_gateways = enterprise_gateways

    def set_enterprise_gateways(self, manager: object) -> None:
        self._enterprise_gateways = manager

    # ── DB helpers ──────────────────────────────────────────────────────────

    async def _get_channel(self, session: AsyncSession, agent_id: str, platform: str) -> MessagingChannel | None:
        result = await session.execute(
            select(MessagingChannel).where(
                MessagingChannel.agent_id == agent_id,
                MessagingChannel.platform == platform,
            )
        )
        return result.scalar_one_or_none()

    async def _get_channels(self, session: AsyncSession, agent_id: str) -> list[MessagingChannel]:
        result = await session.execute(
            select(MessagingChannel)
            .where(MessagingChannel.agent_id == agent_id)
            .order_by(MessagingChannel.platform.asc())
        )
        return list(result.scalars().all())

    async def _reload_agent(self, agent_id: str) -> Agent:
        async with self.session_factory() as session:
            agent = await session.get(Agent, agent_id)
            if not agent:
                raise ValueError("Agent not found")
            return agent

    # ── Channel helpers ─────────────────────────────────────────────────────

    def _channel_runtime_enabled(self, channel: MessagingChannel) -> bool:
        metadata = channel.metadata_json if isinstance(channel.metadata_json, dict) else {}
        return bool(channel.enabled) and not bool(metadata.get("runtime_disabled"))

    def _set_runtime_disabled(self, channel: MessagingChannel, disabled: bool) -> None:
        metadata = dict(channel.metadata_json or {})
        if disabled:
            metadata["runtime_disabled"] = True
        else:
            metadata.pop("runtime_disabled", None)
        channel.metadata_json = metadata

    # ── Log event helper ────────────────────────────────────────────────────

    async def _log_channel_event(
        self,
        session: AsyncSession,
        agent: Agent,
        channel: MessagingChannel,
        event_type: str,
        message: str,
        *,
        severity: str = "info",
        details: dict | None = None,
    ) -> None:
        session.add(
            ActivityLog(
                agent_id=agent.id,
                node_id=agent.node_id,
                event_type=event_type,
                message=message,
                severity=severity,
                details=details or {},
            )
        )

    # ── Start channel ───────────────────────────────────────────────────────

    async def start_channel_locked(
        self,
        agent_id: str,
        platform: str,
        log_mgr,  # GatewayLogManager — avoid circular import
    ) -> None:
        """Start a gateway channel (must be called with agent lock held)."""
        if platform in ("google_chat", "kapso_whatsapp"):
            await self._start_enterprise_channel(agent_id, platform)
            return

        async with self.session_factory() as session:
            agent_row = await session.get(Agent, agent_id)
            if not agent_row:
                raise ValueError("Agent not found")
            channels = await self._get_channels(session, agent_id)
            channel = next((item for item in channels if item.platform == platform), None)
            if not channel:
                raise ValueError("Messaging channel not found")

            self._set_runtime_disabled(channel, False)
            if not channel.enabled:
                channel.status = "stopped"
                channel.last_error = None
                await session.commit()
                return

            if platform == "telegram" and not channel.secret_ref:
                channel.status = "error"
                channel.last_error = "Telegram bot token secret is required"
                await self._log_channel_event(
                    session, agent_row, channel,
                    f"channel.{platform}.start_failed",
                    f"{agent_row.name} {platform} gateway failed to start",
                    severity="warning",
                    details={"reason": "missing_secret_ref", "error": channel.last_error},
                )
                await session.commit()
                raise ValueError(channel.last_error)

            if platform == "telegram":
                from hermeshq.models.secret import Secret
                secret_exists = await session.execute(select(Secret.id).where(Secret.name == channel.secret_ref))
                if secret_exists.scalar_one_or_none() is None:
                    channel.status = "error"
                    channel.last_error = f"Telegram bot token secret '{channel.secret_ref}' was not found"
                    await self._log_channel_event(
                        session, agent_row, channel,
                        f"channel.{platform}.start_failed",
                        f"{agent_row.name} {platform} gateway failed to start",
                        severity="warning",
                        details={"reason": "secret_not_found", "error": channel.last_error},
                    )
                    await session.commit()
                    raise ValueError(channel.last_error)

            try:
                await self.installation_manager.sync_agent_installation(agent_row)
            except HermesInstallationError as exc:
                channel.status = "error"
                channel.last_error = str(exc)
                await self._log_channel_event(
                    session, agent_row, channel,
                    f"channel.{platform}.start_failed",
                    f"{agent_row.name} {platform} gateway failed to start",
                    severity="warning",
                    details={"reason": "installation_sync_failed", "error": channel.last_error},
                )
                await session.commit()
                raise ValueError(channel.last_error) from exc

            channels = await self._get_channels(session, agent_id)
            active_channels = [item for item in channels if self._channel_runtime_enabled(item)]

        existing = self.processes.pop(agent_id, None)
        if existing:
            await self._terminate_handle(existing)

        if not active_channels:
            async with self.session_factory() as session:
                channels = await self._get_channels(session, agent_id)
                for item in channels:
                    item.status = "stopped"
                    item.last_error = None
                await session.commit()
            return

        agent_row = await self._reload_agent(agent_id)
        try:
            handle = await self._launch_gateway_process(agent_row, active_channels, log_mgr)
        except ValueError as exc:
            async with self.session_factory() as session:
                agent_row = await session.get(Agent, agent_id)
                channels = await self._get_channels(session, agent_id)
                active_platforms = {item.platform for item in active_channels}
                for item in channels:
                    if item.platform in active_platforms:
                        item.status = "error"
                        item.last_error = str(exc)
                failed_channel = next((item for item in channels if item.platform == platform), None)
                if agent_row and failed_channel:
                    await self._log_channel_event(
                        session, agent_row, failed_channel,
                        f"channel.{platform}.start_failed",
                        f"{agent_row.name} {platform} gateway failed to start",
                        severity="warning",
                        details={"reason": "gateway_start_failed", "error": str(exc)},
                    )
                await session.commit()
            raise
        self.processes[agent_id] = handle

        async with self.session_factory() as session:
            agent_row = await session.get(Agent, agent_id)
            channels = await self._get_channels(session, agent_id)
            active_platforms = set(handle.platforms)
            for item in channels:
                if item.platform in active_platforms:
                    item.status = "running"
                    item.last_error = None
                    item.updated_at = utcnow()
                    session.add(
                        ActivityLog(
                            agent_id=agent_row.id,
                            node_id=agent_row.node_id,
                            event_type=f"channel.{item.platform}.started",
                            message=f"{agent_row.name} {item.platform} gateway started",
                            details={
                                "platform": item.platform,
                                "pid": handle.process.pid,
                                "active_platforms": sorted(active_platforms),
                            },
                        )
                    )
                elif not self._channel_runtime_enabled(item):
                    item.status = "stopped"
                    item.last_error = None
            await session.commit()

        for item in active_channels:
            await self.event_broker.publish(
                {"type": "messaging.status_changed", "agent_id": agent_id, "status": "running", "message": item.platform}
            )

    # ── Stop channel ────────────────────────────────────────────────────────

    async def stop_channel_locked(
        self,
        agent_id: str,
        platform: str,
    ) -> None:
        """Stop a gateway channel (must be called with agent lock held)."""
        if platform in ("google_chat", "kapso_whatsapp"):
            await self._stop_enterprise_channel(agent_id, platform)
            return

        async with self.session_factory() as session:
            agent_row = await session.get(Agent, agent_id)
            if not agent_row:
                return
            channels = await self._get_channels(session, agent_id)
            channel = next((item for item in channels if item.platform == platform), None)
            if not channel:
                return

            self._set_runtime_disabled(channel, True)
            try:
                await self.installation_manager.sync_agent_installation(agent_row)
            except HermesInstallationError:
                logger.exception("Failed to resync agent installation while stopping %s for %s", platform, agent_id)
            remaining_channels = [item for item in channels if self._channel_runtime_enabled(item)]

        existing = self.processes.pop(agent_id, None)
        if existing:
            await self._terminate_handle(existing)

        restarted_handle: GatewayProcessHandle | None = None
        if remaining_channels:
            agent_row = await self._reload_agent(agent_id)
            restarted_handle = await self._launch_gateway_process(agent_row, remaining_channels, None)
            self.processes[agent_id] = restarted_handle

        async with self.session_factory() as session:
            agent_row = await session.get(Agent, agent_id)
            channels = await self._get_channels(session, agent_id)
            active_platforms = set(restarted_handle.platforms) if restarted_handle else set()
            for item in channels:
                if item.platform == platform:
                    item.status = "stopped"
                    item.last_error = None
                elif item.platform in active_platforms:
                    item.status = "running"
                    item.last_error = None
                    item.updated_at = utcnow()
                    session.add(
                        ActivityLog(
                            agent_id=agent_row.id,
                            node_id=agent_row.node_id,
                            event_type=f"channel.{item.platform}.started",
                            message=f"{agent_row.name} {item.platform} gateway started",
                            details={
                                "platform": item.platform,
                                "pid": restarted_handle.process.pid,
                                "active_platforms": sorted(active_platforms),
                            },
                        )
                    )
                else:
                    item.status = "stopped"
                    item.last_error = None

            session.add(
                ActivityLog(
                    agent_id=agent_row.id,
                    node_id=agent_row.node_id,
                    event_type=f"channel.{platform}.stopped",
                    message=f"{agent_row.name} {platform} gateway stopped",
                    details={"platform": platform},
                )
            )
            await session.commit()

        await self.event_broker.publish(
            {"type": "messaging.status_changed", "agent_id": agent_id, "status": "stopped", "message": platform}
        )
        if restarted_handle:
            for remaining_platform in restarted_handle.platforms:
                await self.event_broker.publish(
                    {
                        "type": "messaging.status_changed",
                        "agent_id": agent_id,
                        "status": "running",
                        "message": remaining_platform,
                    }
                )

    # ── Enterprise gateways ─────────────────────────────────────────────────

    async def get_enterprise_runtime_status(self, agent_id: str, platform: str) -> dict:
        if self._enterprise_gateways is None:
            return {"status": "missing", "pid": None, "log_path": None}
        status_info = self._enterprise_gateways.get_status(agent_id, platform)
        running = status_info.get("running", False)

        async with self.session_factory() as session:
            channel = await self._get_channel(session, agent_id, platform)
            channel_status = channel.status if channel else "stopped"
            bootstrap = dict((channel.metadata_json or {}).get("bootstrap") or {}) if channel else {}

        return {
            "status": "running" if running else channel_status,
            "pid": None,
            "log_path": None,
            "last_bootstrap_at": bootstrap.get("last_attempt_at"),
            "last_bootstrap_success_at": bootstrap.get("last_success_at"),
            "last_bootstrap_status": bootstrap.get("last_status"),
            "last_bootstrap_error": bootstrap.get("last_error"),
            "last_bootstrap_duration_ms": bootstrap.get("last_duration_ms"),
            "last_bootstrap_attempts": bootstrap.get("last_attempts"),
            "paired": None,
            "pairing_status": None,
            "session_path": None,
            "bridge_log_path": None,
            "pairing_qr_text": None,
        }

    async def _start_enterprise_channel(self, agent_id: str, platform: str) -> None:
        if self._enterprise_gateways is None:
            raise ValueError(f"Enterprise gateway manager not available for {platform}")
        try:
            await self._enterprise_gateways.start_gateway(agent_id, platform)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(str(exc)) from exc

        async with self.session_factory() as session:
            channel = await self._get_channel(session, agent_id, platform)
            if channel:
                channel.status = "running"
                channel.last_error = None
                channel.updated_at = utcnow()
                await session.commit()

        await self.event_broker.publish(
            {"type": "messaging.status_changed", "agent_id": agent_id, "status": "running", "message": platform}
        )

    async def _stop_enterprise_channel(self, agent_id: str, platform: str) -> None:
        if self._enterprise_gateways is None:
            return
        await self._enterprise_gateways.stop_gateway(agent_id, platform)

        async with self.session_factory() as session:
            channel = await self._get_channel(session, agent_id, platform)
            if channel:
                channel.status = "stopped"
                channel.last_error = None
                channel.updated_at = utcnow()
                await session.commit()

        await self.event_broker.publish(
            {"type": "messaging.status_changed", "agent_id": agent_id, "status": "stopped", "message": platform}
        )

    # ── Process lifecycle ───────────────────────────────────────────────────

    async def _launch_gateway_process(
        self,
        agent: Agent,
        active_channels: list[MessagingChannel],
        log_mgr,  # GatewayLogManager or None
    ) -> GatewayProcessHandle:
        env = await self.installation_manager.build_gateway_env(agent)
        runtime_selection = await self.installation_manager.resolve_hermes_runtime(agent)
        workspace_path = self.installation_manager.resolve_workspace_path(agent.workspace_path)

        if log_mgr:
            log_mgr.cleanup_stale_gateway_pid(agent.workspace_path)

        log_path = self.gateway_log_path(agent.workspace_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            [runtime_selection.hermes_bin, "gateway", "run", "--replace"],
            cwd=str(workspace_path),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        handle = GatewayProcessHandle(
            agent_id=agent.id,
            process=process,
            log_path=log_path.as_posix(),
            log_handle=log_handle,
            platforms={item.platform for item in active_channels},
        )

        if log_mgr:
            sessions_dir = log_mgr.sessions_dir(agent.workspace_path)
            for item in active_channels:
                known_activity_keys, session_file_state = await asyncio.to_thread(
                    log_mgr.snapshot_session_activity,
                    sessions_dir,
                    item.platform,
                )
                handle.known_activity_keys[item.platform] = known_activity_keys
                handle.session_file_state[item.platform] = session_file_state
                handle.activity_tasks[item.platform] = asyncio.create_task(
                    log_mgr.activity_sync_loop(
                        agent.id,
                        agent.node_id,
                        str(workspace_path),
                        item.platform,
                        known_activity_keys,
                        session_file_state,
                    )
                )

        handle.monitor_task = asyncio.create_task(
            self._monitor_process(
                agent.id,
                process,
                log_path.as_posix(),
                log_handle,
                set(handle.platforms),
            )
        )
        try:
            await self._wait_for_gateway_startup(handle)
        except Exception:
            await self._terminate_handle(handle)
            raise
        return handle

    async def _wait_for_gateway_startup(self, handle: GatewayProcessHandle) -> None:
        await asyncio.sleep(GATEWAY_STARTUP_STABILIZATION_SECONDS)
        return_code = handle.process.poll()
        if return_code is None:
            return

        log_tail = self.read_log_tail(Path(handle.log_path), lines=80).lower()
        if "pid file race lost to another gateway instance" in log_tail:
            raise ValueError("PID file race lost to another gateway instance")
        if "whatsapp bridge process exited unexpectedly" in log_tail:
            raise ValueError("WhatsApp bridge process exited unexpectedly during startup")

        last_line = ""
        for line in reversed(log_tail.splitlines()):
            stripped = line.strip()
            if stripped:
                last_line = stripped
                break
        if last_line:
            raise ValueError(f"Gateway exited during startup with code {return_code}: {last_line}")
        raise ValueError(f"Gateway exited during startup with code {return_code}")

    async def _terminate_handle(self, handle: GatewayProcessHandle) -> None:
        if handle.monitor_task:
            handle.monitor_task.cancel()
        for task in handle.activity_tasks.values():
            task.cancel()
        if handle.process.poll() is None:
            handle.process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(handle.process.wait), timeout=5)
            except asyncio.TimeoutError:
                handle.process.kill()
                await asyncio.to_thread(handle.process.wait)
        with contextlib.suppress(Exception):
            handle.log_handle.close()

    async def _monitor_process(
        self,
        agent_id: str,
        process: subprocess.Popen,
        log_path: str,
        log_handle,
        platforms: set[str],
    ) -> None:
        try:
            return_code = await asyncio.to_thread(process.wait)
        except asyncio.CancelledError:
            return
        finally:
            with contextlib.suppress(Exception):
                log_handle.flush()
                log_handle.close()

        handle = self.processes.get(agent_id)
        if handle and handle.process is process:
            self.processes.pop(agent_id, None)
            for task in handle.activity_tasks.values():
                task.cancel()

        async with self.session_factory() as session:
            agent = await session.get(Agent, agent_id)
            if not agent:
                return
            channels = await self._get_channels(session, agent_id)
            for channel in channels:
                if channel.platform not in platforms:
                    continue
                channel.status = "stopped" if return_code == 0 else "error"
                channel.last_error = None if return_code == 0 else f"{channel.platform} gateway exited with code {return_code}"
                session.add(
                    ActivityLog(
                        agent_id=agent.id,
                        node_id=agent.node_id,
                        event_type=f"channel.{channel.platform}.exited",
                        message=f"{agent.name} {channel.platform} gateway exited",
                        details={"platform": channel.platform, "return_code": return_code, "log_path": log_path},
                    )
                )
            await session.commit()

        for platform in platforms:
            await self.event_broker.publish(
                {
                    "type": "messaging.status_changed",
                    "agent_id": agent_id,
                    "status": "stopped" if return_code == 0 else "error",
                    "message": platform,
                }
            )

    # ── Path helpers ────────────────────────────────────────────────────────

    def gateway_log_path(self, workspace_path: str) -> Path:
        return self.installation_manager.build_hermes_home(workspace_path) / "logs" / "gateway.log"

    @staticmethod
    def _read_log_tail(path: Path, lines: int = 120) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(content[-lines:])
        except Exception:
            return ""
