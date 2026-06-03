"""Shared types for gateway management."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class GatewayProcessHandle:
    agent_id: str
    process: object  # subprocess.Popen
    log_path: str
    log_handle: object
    platforms: set[str] = field(default_factory=set)
    monitor_task: asyncio.Task | None = None
    activity_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    known_activity_keys: dict[str, set[str]] = field(default_factory=dict)
    session_file_state: dict[str, dict[str, tuple[int, int, int]]] = field(default_factory=dict)
