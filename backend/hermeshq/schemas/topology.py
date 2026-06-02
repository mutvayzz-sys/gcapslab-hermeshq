from pydantic import BaseModel


class TopologyNode(BaseModel):
    id: str
    label: str
    slug: str
    status: str


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class CommsTopologyRead(BaseModel):
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]
