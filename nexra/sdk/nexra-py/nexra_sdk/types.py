from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisterResult:
    agent_id: str
    status: str
    embedding_id: str | None = None
    registered_at: str = ""


@dataclass
class AgentMatch:
    agent_id: str
    name: str
    match_score: float
    trust_score: float
    status: str
    pricing: dict = field(default_factory=dict)
    sla: dict = field(default_factory=dict)
    is_cross_org: bool = False
    capability_type: str = ""


@dataclass
class PolicyResult:
    policy_id: str | None = None
    policy_version: int | None = None
    decision: str = ""


@dataclass
class Usage:
    cost_usd: float = 0.0
    latency_ms: int = 0
    llm_tokens: int | None = None


@dataclass
class DelegationResult:
    delegation_id: str
    status: str
    policy_result: PolicyResult | None = None
    result: Any = None
    usage: Usage | None = None
    poll_url: str | None = None
    approval_deadline: str | None = None
