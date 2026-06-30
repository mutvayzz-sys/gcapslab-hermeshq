from datetime import datetime

from pydantic import BaseModel, Field

from hermeshq.schemas.common import ORMModel


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64)
    kind: str = Field(default="company", pattern="^(school|company|personal)$")
    default_mode: str | None = Field(default=None, max_length=16)
    default_capabilities: str | None = Field(default=None, max_length=255)
    system_prompt_override: str | None = None
    honcho_base_url: str | None = Field(default=None, max_length=255)
    honcho_jwt_secret: str | None = None
    nous_api_key: str | None = Field(default=None, max_length=255)
    nous_base_url: str | None = Field(default=None, max_length=512)


class OrganizationRead(ORMModel):
    id: str
    name: str
    slug: str
    kind: str
    default_mode: str | None = None
    default_capabilities: str | None = None
    system_prompt_override: str | None = None
    honcho_base_url: str | None = None
    has_honcho_jwt_secret: bool = False
    has_nous_api_key: bool = False
    nous_base_url: str | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    kind: str | None = Field(default=None, pattern="^(school|company|personal)$")
    default_mode: str | None = Field(default=None, max_length=16)
    default_capabilities: str | None = Field(default=None, max_length=255)
    system_prompt_override: str | None = None
    honcho_base_url: str | None = Field(default=None, max_length=255)
    honcho_jwt_secret: str | None = None
    nous_api_key: str | None = Field(default=None, max_length=255)
    nous_base_url: str | None = Field(default=None, max_length=512)
