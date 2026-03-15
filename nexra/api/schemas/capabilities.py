from pydantic import BaseModel, Field


class DiscoverRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language capability query")
    capability_type: str | None = Field(None, description="Hard filter: exact capability_type match")
    budget_cap_usd: float | None = Field(None, gt=0, description="Exclude agents above this price")
    max_latency_ms: int | None = Field(None, gt=0, description="Exclude agents above this SLA")
    exclude_agents: list[str] = Field(default_factory=list, description="Agent IDs to exclude")
    include_cross_org: bool = Field(False, description="Include public agents from other orgs")
    limit: int = Field(5, ge=1, le=20, description="Max results to return")


class DiscoverMatchItem(BaseModel):
    agent_id: str
    name: str
    match_score: float
    trust_score: float
    status: str
    pricing: dict
    sla: dict
    is_cross_org: bool
    capability_type: str


class DiscoverResponse(BaseModel):
    matches: list[DiscoverMatchItem]
    total_candidates: int
    filtered_count: int
    latency_ms: float
