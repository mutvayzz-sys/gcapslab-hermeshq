from datetime import datetime

from pydantic import BaseModel

from hermeshq.schemas.common import ORMModel


class NodeCreate(BaseModel):
    name: str
    hostname: str
    node_type: str = "local"
    ssh_user: str | None = None
    ssh_port: int = 22
    max_agents: int = 10


class NodeUpdate(BaseModel):
    name: str | None = None
    hostname: str | None = None
    node_type: str | None = None
    ssh_user: str | None = None
    ssh_port: int | None = None
    max_agents: int | None = None
    status: str | None = None


class NodeRead(ORMModel):
    id: str
    name: str
    hostname: str
    node_type: str
    status: str
    ssh_user: str | None
    ssh_port: int
    max_agents: int
    last_heartbeat: datetime | None
    system_info: dict
    created_at: datetime
    updated_at: datetime


class NodeTestRead(BaseModel):
    status: str
    node_id: str
    message: str
    hostname: str
    port: int | None = None


class NodeProvisionRead(BaseModel):
    status: str
    node_id: str
    message: str


class NodeMetricsRead(BaseModel):
    node_id: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    memory_total: int
    memory_available: int
    disk_total: int
    disk_free: int
    system_info: dict
