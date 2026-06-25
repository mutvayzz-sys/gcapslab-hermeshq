from pydantic import BaseModel, Field


class DesktopProvisionRequest(BaseModel):
    client: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=32)
    platform: str = Field(min_length=1, max_length=32)


class DesktopRuntimeValidateRequest(BaseModel):
    runtime_id: str = Field(default="local-hermes", min_length=1, max_length=128)
    requested_capability: str | None = Field(default=None, max_length=64)


class DesktopProvisionUser(BaseModel):
    id: str
    username: str
    role: str


class DesktopRuntimeInfo(BaseModel):
    validate_url: str
    ttl_seconds: int


class DesktopProvisionResponse(BaseModel):
    mode: str
    hermeshq_url: str
    user: DesktopProvisionUser
    capabilities: list[str]
    runtime: DesktopRuntimeInfo


class DesktopRuntimeValidateResponse(BaseModel):
    allowed: bool
    capabilities: list[str]
    role: str
    ttl_seconds: int
