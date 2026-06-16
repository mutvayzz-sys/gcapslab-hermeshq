"""
Enterprise Gateway Manager.

Manages Google Chat and Kapso WhatsApp gateway instances
alongside the existing Hermes Agent gateway supervisor.

These gateways run as async tasks (not subprocesses) and connect
directly to the respective platform APIs.

Note: Microsoft Teams is now handled natively by hermes-agent.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hermeshq.models.messaging_channel import MessagingChannel
from hermeshq.services.secret_vault import SecretVault

logger = logging.getLogger(__name__)

# Platforms managed by this manager (not by the subprocess GatewaySupervisor)
ENTERPRISE_PLATFORMS = {"google_chat", "kapso_whatsapp"}


class EnterpriseGatewayManager:
    """
    Manages lifecycle of Google Chat and Kapso WhatsApp gateways.

    Unlike the Hermes Agent gateway supervisor which launches
    subprocess processes, this manager runs gateway adapters
    as asyncio tasks within the backend process.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        supervisor: object,
        event_broker: object,
        secret_vault: SecretVault,
    ) -> None:
        self.session_factory = session_factory
        self.supervisor = supervisor
        self.event_broker = event_broker
        self.secret_vault = secret_vault

        # Enterprise gateways — keyed by agent_id
        self.google_chat_gateways: dict[str, object] = {}
        self.kapso_gateways: dict[str, object] = {}

    # ---- bootstrap ----

    async def bootstrap(self) -> None:
        """Start gateways for all agents with enabled enterprise channels."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(MessagingChannel).where(
                    MessagingChannel.platform.in_(ENTERPRISE_PLATFORMS),
                    MessagingChannel.enabled == True,  # noqa: E712
                )
            )
            channels = result.scalars().all()

        # Group by agent
        agent_channels: dict[str, set[str]] = {}
        for ch in channels:
            agent_channels.setdefault(ch.agent_id, set()).add(ch.platform)

        for agent_id, platforms in agent_channels.items():
            for platform in platforms:
                try:
                    await self.start_gateway(agent_id, platform)
                except Exception:  # noqa: BLE001  # gateway bootstrap per-agent
                    logger.exception(
                        "Failed to bootstrap %s gateway for agent %s",
                        platform, agent_id,
                    )

    # ---- lifecycle ----

    async def start_gateway(self, agent_id: str, platform: str) -> None:
        """Start a gateway for the given agent and platform."""
        if platform == "google_chat":
            await self._start_google_chat(agent_id)
        elif platform == "kapso_whatsapp":
            await self._start_kapso_whatsapp(agent_id)
        else:
            raise ValueError(f"Unsupported enterprise platform: {platform}")

    async def stop_gateway(self, agent_id: str, platform: str) -> None:
        """Stop a gateway for the given agent and platform."""
        if platform == "google_chat":
            await self._stop_google_chat(agent_id)
        elif platform == "kapso_whatsapp":
            await self._stop_kapso_whatsapp(agent_id)

    async def stop_all(self, agent_id: str) -> None:
        """Stop all enterprise gateways for an agent."""
        await self._stop_google_chat(agent_id)
        await self._stop_kapso_whatsapp(agent_id)

    async def shutdown(self) -> None:
        """Shut down all enterprise gateways."""
        for agent_id in list(self.google_chat_gateways.keys()):
            await self._stop_google_chat(agent_id)
        for agent_id in list(self.kapso_gateways.keys()):
            await self._stop_kapso_whatsapp(agent_id)

    # ---- Google Chat ----

    async def _start_google_chat(self, agent_id: str) -> None:
        if agent_id in self.google_chat_gateways:
            return
        from hermeshq.services.google_chat_gateway import GoogleChatGateway

        gw = GoogleChatGateway(
            agent_id=agent_id,
            session_factory=self.session_factory,
            supervisor=self.supervisor,
            event_broker=self.event_broker,
            secret_vault=self.secret_vault,
        )
        await gw.start()
        self.google_chat_gateways[agent_id] = gw
        logger.info("Started Google Chat gateway for agent %s", agent_id)

    async def _stop_google_chat(self, agent_id: str) -> None:
        gw = self.google_chat_gateways.pop(agent_id, None)
        if gw:
            await gw.stop()
            logger.info("Stopped Google Chat gateway for agent %s", agent_id)

    # ---- Kapso WhatsApp ----

    async def _start_kapso_whatsapp(self, agent_id: str) -> None:
        if agent_id in self.kapso_gateways:
            return
        from hermeshq.services.kapso_whatsapp_gateway import KapsoWhatsAppGateway

        gw = KapsoWhatsAppGateway(
            agent_id=agent_id,
            session_factory=self.session_factory,
            supervisor=self.supervisor,
            event_broker=self.event_broker,
            secret_vault=self.secret_vault,
        )
        await gw.start()
        self.kapso_gateways[agent_id] = gw
        logger.info("Started Kapso WhatsApp gateway for agent %s", agent_id)

    async def _stop_kapso_whatsapp(self, agent_id: str) -> None:
        gw = self.kapso_gateways.pop(agent_id, None)
        if gw:
            await gw.stop()
            logger.info("Stopped Kapso WhatsApp gateway for agent %s", agent_id)

    # ---- status ----

    def get_status(self, agent_id: str, platform: str) -> dict:
        """Get the status of a gateway."""
        if platform == "google_chat":
            running = agent_id in self.google_chat_gateways
        elif platform == "kapso_whatsapp":
            running = agent_id in self.kapso_gateways
        else:
            running = False
        return {
            "running": running,
            "platform": platform,
            "agent_id": agent_id,
        }
