import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ─── Request Models ───────────────────────────────────────────


class PricingSchema(BaseModel):
    per_call_usd: float = Field(..., gt=0, description="Cost per delegation call in USD")


class SLASchema(BaseModel):
    p99_latency_ms: int = Field(..., gt=0, description="P99 latency target in milliseconds")
    availability: float = Field(..., ge=0.0, le=1.0, description="Availability target (0.0-1.0)")


class AgentRegisterRequest(BaseModel):
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Lowercase alphanumeric + hyphens only.",
    )
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=20)
    capability_type: str
    input_schema: dict = Field(..., description="JSON Schema Draft 7 for task input")
    output_schema: dict = Field(..., description="JSON Schema Draft 7 for result")
    pricing: PricingSchema
    sla: SLASchema
    webhook_url: str
    webhook_secret: str = Field(..., min_length=32)
    is_public: bool = Field(False)

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("agent_id must contain only lowercase letters, numbers, and hyphens")
        return v

    @field_validator("capability_type")
    @classmethod
    def validate_capability_type(cls, v: str) -> str:
        allowed = {"research", "analysis", "generation", "enrichment", "validation", "execution", "other"}
        if v not in allowed:
            raise ValueError(f"capability_type must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("webhook_url must use HTTPS")
        return v

    @field_validator("input_schema", "output_schema")
    @classmethod
    def validate_json_schema(cls, v: dict) -> dict:
        import jsonschema

        try:
            jsonschema.Draft7Validator.check_schema(v)
        except jsonschema.SchemaError as e:
            raise ValueError(f"Invalid JSON Schema: {e.message}")
        return v


# ─── Response Models ──────────────────────────────────────────


class AgentRegisterResponse(BaseModel):
    agent_id: str
    status: str
    embedding_id: str | None = None
    registered_at: datetime


class AgentDetailResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    description: str
    capability_type: str
    input_schema: dict
    output_schema: dict
    pricing: dict
    sla: dict
    webhook_url: str
    is_public: bool
    trust_score: float
    status: str
    delegation_count: int
    created_at: datetime
    updated_at: datetime


class AgentListItem(BaseModel):
    agent_id: str
    name: str
    capability_type: str
    trust_score: float
    status: str
    is_public: bool
    delegation_count: int
    pricing: dict
    sla: dict
    created_at: datetime


class AgentListResponse(BaseModel):
    agents: list[AgentListItem]
    next_cursor: str | None = None
    total_count: int
