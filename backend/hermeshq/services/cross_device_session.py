"""Cross-device session management for shared desktop + iOS experience.

Phase 8.1: Shared session namespace across desktop and iOS.
Phase 8.2: Honcho memory continuity across devices.

This module provides a unified session key that both desktop and iOS clients
can use to access the same conversation history and memory state.
"""

from __future__ import annotations

from hermeshq.models.user import User

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



