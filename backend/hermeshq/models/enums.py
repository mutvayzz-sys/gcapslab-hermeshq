"""Centralized status and mode enumerations for HermesHQ models.

These enums replace magic strings throughout the codebase and are used
for Pydantic validation in schemas.
"""

from enum import Enum


class AgentStatus(str, Enum):
    """Allowed agent status values (matches ck_agents_status constraint)."""
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"
    STARTING = "starting"


class AgentRunMode(str, Enum):
    """Allowed agent run_mode values."""
    HEADLESS = "headless"
    INTERACTIVE = "interactive"
    HYBRID = "hybrid"


class TaskStatus(str, Enum):
    """Allowed task status values."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalMode(str, Enum):
    """Approval mode for agent tool execution."""
    AUTO = "auto"
    MANUAL = "manual"
    SUGGEST = "suggest"


class ToolProgressMode(str, Enum):
    """Tool progress display mode."""
    FULL = "full"
    MINIMAL = "minimal"
    HIDDEN = "hidden"


class GatewayNotificationsMode(str, Enum):
    """Gateway notification mode for agents."""
    ALL = "all"
    ERRORS = "errors"
    NONE = "none"
