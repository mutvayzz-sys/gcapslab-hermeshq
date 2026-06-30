from datetime import datetime

from pydantic import BaseModel

from hermeshq.schemas.common import ORMModel


class RuntimeContainerRead(ORMModel):
    id: str
    user_id: str
    organization_id: str | None = None
    agent_id: str | None = None
    container_name: str
    image: str
    status: str
    endpoint_path: str
    health_status: str | None = None
    last_health_at: datetime | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class RuntimeContainerProvisionRequest(BaseModel):
    user_id: str | None = None
    agent_id: str | None = None
    force_recreate: bool = False


class RuntimeContainerProvisionResponse(BaseModel):
    container: RuntimeContainerRead
    endpoint_url: str
    api_server_key: str
    forward_auth_token: str | None = None
    forward_auth_expires_at: str | None = None


class RuntimeContainerHealthRead(BaseModel):
    container_id: str
    status: str
    endpoint_url: str
    runtime_url: str
    ok: bool
    detail: str | None = None


class UserContainerResponse(BaseModel):
    """Active container credentials for the authenticated user.
    Consumed by the console web chat and any client that needs to hit the
    Runs API without going through the full desktop provision flow."""
    endpoint_url: str
    api_server_key: str
    forward_auth_token: str | None = None
    forward_auth_expires_at: str | None = None
    container_name: str
    status: str
