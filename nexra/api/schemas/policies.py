from datetime import datetime

import yaml
from pydantic import BaseModel, Field, field_validator


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    priority: int = Field(100, ge=1, le=10000, description="Lower = evaluated first")
    allow: dict = Field(..., description="Allow block: caller_type, callee_type, capability_types")
    conditions: list[dict] = Field(default_factory=list)
    hil_threshold_usd: float | None = Field(None, gt=0)
    on_violation: str = Field("block_and_alert")

    @field_validator("on_violation")
    @classmethod
    def validate_on_violation(cls, v: str) -> str:
        allowed = {"block_and_alert", "block_silent", "audit_only", "pause_for_approval"}
        if v not in allowed:
            raise ValueError(f"on_violation must be one of: {', '.join(sorted(allowed))}")
        return v

    def to_yaml(self) -> str:
        policy_dict: dict = {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "enabled": True,
            "allow": self.allow,
            "conditions": self.conditions,
            "on_violation": self.on_violation,
        }
        if self.hil_threshold_usd is not None:
            policy_dict["hil_threshold_usd"] = self.hil_threshold_usd
        return yaml.dump(policy_dict, default_flow_style=False)


class PolicyUpdateRequest(BaseModel):
    description: str | None = None
    priority: int | None = Field(None, ge=1, le=10000)
    allow: dict | None = None
    conditions: list[dict] | None = None
    hil_threshold_usd: float | None = None
    on_violation: str | None = None

    @field_validator("on_violation")
    @classmethod
    def validate_on_violation(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"block_and_alert", "block_silent", "audit_only", "pause_for_approval"}
        if v not in allowed:
            raise ValueError(f"on_violation must be one of: {', '.join(sorted(allowed))}")
        return v


class PolicyResponse(BaseModel):
    id: str
    parent_policy_id: str | None
    name: str
    description: str | None
    priority: int
    version: int
    enabled: bool
    allow: dict
    conditions: list[dict]
    hil_threshold_usd: float | None
    on_violation: str
    created_at: datetime


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total_count: int


class PolicyVersionsResponse(BaseModel):
    policy_id: str
    versions: list[PolicyResponse]
