from typing import Any

from pydantic import BaseModel


class InternalRosterSelf(BaseModel):
    id: str
    display_name: str
    slug: str


class InternalDirectRead(BaseModel):
    success: bool
    message_id: str
    task_id: str | None
    from_agent: str
    to_agent: str
    message_type: str


class InternalDelegateRead(BaseModel):
    success: bool
    message_id: str
    task_id: str | None
    from_agent: str
    to_agent: str
    message_type: str
    delegate_allowed: bool
    delegate_route: str
    delegate_reason: str


class InternalRosterRead(BaseModel):
    self: InternalRosterSelf
    agents: list[dict[str, Any]]
