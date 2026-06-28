from pydantic import BaseModel, Field


class ContainerCreate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    organization_id: str | None = Field(default=None, max_length=36)
    image: str | None = Field(default="hermes:latest", max_length=255)


class ContainerProvisionRequest(BaseModel):
    user_id: str = Field(..., max_length=36)
    name: str | None = Field(default=None, max_length=128)


class ContainerResponse(BaseModel):
    id: str
    user_id: str
    organization_id: str | None
    name: str
    status: str
    docker_container_id: str | None
    image: str
    ports: str | None
    volume_mounts: str | None
    env_vars: str | None
    health_check_url: str | None
    last_healthy_at: str | None
    error_message: str | None
    is_active: bool

    class Config:
        from_attributes = True


class ContainerStartStopResponse(BaseModel):
    container_id: str
    status: str
    health_check_url: str | None
