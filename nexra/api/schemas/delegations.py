from datetime import datetime

from pydantic import BaseModel, Field


class DelegateRequest(BaseModel):
    callee_agent_id: str = Field(..., description="Target agent's agent_id")
    task: dict = Field(..., description="Task payload validated against callee's input_schema")
    context_scope: list[str] = Field(default_factory=list, description="Explicit data grant keys")
    budget_cap_usd: float = Field(..., gt=0, description="Max cost for this delegation")
    timeout_ms: int = Field(30000, ge=1000, le=120000, description="Webhook timeout in ms")
    callback_url: str | None = Field(None, description="Async callback URL (null=sync)")
    include_cross_org: bool = Field(False, description="Allow cross-org callee resolution")
    workflow: str | None = Field(
        None,
        min_length=1,
        max_length=120,
        description="Optional workflow grouping key; defaults to 'unclassified'",
    )
    parent_delegation_id: str | None = Field(
        None, description="Optional parent delegation ID for nested delegation chains"
    )


class PolicyResultResponse(BaseModel):
    policy_id: str | None
    policy_version: int | None
    decision: str


class UsageResponse(BaseModel):
    cost_usd: float
    latency_ms: int
    llm_tokens: int | None = None


class DelegationResponse(BaseModel):
    delegation_id: str
    status: str
    policy_result: PolicyResultResponse | None = None
    result: dict | None = None
    usage: UsageResponse | None = None
    poll_url: str | None = None
    approval_deadline: str | None = None


class DelegationCompleteRequest(BaseModel):
    result: dict = Field(..., description="Task result validated against output_schema")
    usage: dict | None = Field(None, description="Self-reported usage: llm_tokens, external_api_cost_usd")


class DelegationStatusResponse(BaseModel):
    delegation_id: str
    status: str
    policy_result: PolicyResultResponse | None = None
    result: dict | None = None
    usage: UsageResponse | None = None
    created_at: datetime
    completed_at: datetime | None = None
