from pydantic import BaseModel


class SkillCatalogRead(BaseModel):
    skills: list[dict]
    count: int
    query: str


class AgentSkillsRead(BaseModel):
    agent_id: str
    assigned: list[str]
    installed: list
    count: int
