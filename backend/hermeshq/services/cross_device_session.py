"""Cross-device session management for shared desktop + iOS experience.

Phase 8.1: Shared session namespace across desktop and iOS.
Phase 8.2: Honcho memory continuity across devices.

This module provides a unified session key that both desktop and iOS clients
can use to access the same conversation history and memory state.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.models.user import User

logger = logging.getLogger(__name__)

SESSION_NAMESPACE_PREFIX = "headmaster"


def derive_session_namespace(user: User) -> str:
    """Derive a stable session namespace from the user's identity.

    Both desktop and iOS clients use this namespace so that:
    - Conversation history is shared across devices
    - Honcho memory is continuous regardless of which device is used
    - Session context (active agents, current task) follows the user

    Format: headmaster:{user_id}
    """
    return f"{SESSION_NAMESPACE_PREFIX}:{user.id}"


async def get_or_create_user_session(
    db: AsyncSession,
    user: User,
) -> dict:
    """Get or initialize the user's cross-device session state.

    Returns a dict with:
    - namespace: the shared session namespace
    - active_devices: list of currently connected devices
    - last_active_at: timestamp of last activity
    - preferred_mode: the user's preferred runtime mode
    """
    namespace = derive_session_namespace(user)

    # TODO: Persist session state in a dedicated table or Redis
    # For now, return a derived state from the user record
    return {
        "namespace": namespace,
        "active_devices": [],
        "last_active_at": user.updated_at.isoformat() if user.updated_at else None,
        "preferred_mode": user.organization.default_mode if user.organization else "headmaster_local",
    }


async def register_device_session(
    db: AsyncSession,
    user: User,
    device_type: str,  # "desktop" | "ios"
    device_id: str,
) -> dict:
    """Register a device as active in the user's session.

    This allows the user to see which devices are currently connected
    and enables real-time sync notifications.
    """
    namespace = derive_session_namespace(user)
    logger.info(f"Registering {device_type} device {device_id} for user {user.id} in namespace {namespace}")

    # TODO: Store in Redis or a session table
    return {
        "namespace": namespace,
        "device_type": device_type,
        "device_id": device_id,
        "registered_at": __import__("datetime").datetime.utcnow().isoformat(),
    }


async def invalidate_device_session(
    db: AsyncSession,
    user: User,
    device_id: str,
) -> None:
    """Remove a device from the user's active session.

    Called when a device logs out or its session expires.
    """
    namespace = derive_session_namespace(user)
    logger.info(f"Invalidating device {device_id} for user {user.id} in namespace {namespace}")

    # TODO: Remove from Redis or session table
