# Phase 3 — Agent Registry

> **TDD Sections**: §5.2 (AgentService), §6.3 (POST /agents/register), §6.2 (GET /agents/registry, GET /agents/{id})
>
> **48-Hour Block**: Hours 9–13
>
> **Depends On**: Phase 2 (Auth + Security) complete — auth middleware, crypto, /health working.

---

## 1. Prerequisites

- [ ] `core/crypto.py` — generate_api_key, verify_api_key, encrypt_aes_gcm, decrypt_aes_gcm all working
- [ ] `api/dependencies.py` — get_authenticated_org, get_authenticated_org_and_agent working
- [ ] `/health` returns 200 with healthy components
- [ ] Rate limiting functional via Redis

---

## 2. Objective

Deliver the agent registration and listing system:

- POST /agents/register — register or re-register an agent with typed schemas, embedding generation, HTTPS webhook validation
- GET /agents/registry — paginated list of agents with filters (capability_type, status, is_public)
- GET /agents/{id} — get agent details by UUID or agent_id
- AgentService with OpenAI embedding generation (text-embedding-3-small, 1536 dimensions)
- Pydantic v2 request/response schemas with full validation
- Common response envelope: `{ data: <payload>, meta: { request_id, latency_ms } }`

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embedding model | text-embedding-3-small (1536 dims) | TDD §1.2, §9.2. Cost-effective, sufficient for capability matching. |
| Embed text | `"{name}. {description}"` | TDD §5.2. Concatenation gives semantic context for both identity and capability. |
| Idempotent register | Upsert on (org_id, agent_id) | TDD §6.3. Re-registration updates fields, preserves trust_score. |
| Schema validation | jsonschema Draft 7 | TDD §6.3. input_schema and output_schema validated as valid JSON Schema. |
| Pagination | Cursor-based (created_at DESC) | TDD §6.1. Consistent performance regardless of offset. |

---

## 4. File-by-File Implementation Guide

### 4.1 `api/schemas/common.py`

**Path**: `nexra/api/schemas/common.py`

Shared response envelope and pagination models used by all endpoints.

```python
from pydantic import BaseModel, Field
from typing import Any, Generic, TypeVar
from datetime import datetime

T = TypeVar("T")


class MetaResponse(BaseModel):
    request_id: str | None = None
    latency_ms: float | None = None


class DataResponse(BaseModel, Generic[T]):
    """Standard response envelope: { data: T, meta: {...} }"""
    data: T
    meta: MetaResponse = MetaResponse()


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error envelope: { error: {...} }"""
    error: ErrorDetail


class PaginationParams(BaseModel):
    cursor: str | None = Field(None, description="Cursor from previous response for pagination")
    limit: int = Field(50, ge=1, le=100, description="Number of items per page")


class PaginatedMeta(MetaResponse):
    next_cursor: str | None = None
    total_count: int | None = None
```

### 4.2 `api/schemas/agents.py`

**Path**: `nexra/api/schemas/agents.py`

Complete Pydantic v2 models for agent registration and listing.

```python
import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal


# ─── Request Models ───────────────────────────────────────────

class PricingSchema(BaseModel):
    per_call_usd: float = Field(..., gt=0, description="Cost per delegation call in USD")


class SLASchema(BaseModel):
    p99_latency_ms: int = Field(..., gt=0, description="P99 latency target in milliseconds")
    availability: float = Field(..., ge=0.0, le=1.0, description="Availability target (0.0-1.0)")


class AgentRegisterRequest(BaseModel):
    agent_id: str = Field(
        ..., min_length=1, max_length=64,
        description="Human-readable agent identifier, unique per org. Lowercase alphanumeric + hyphens only."
    )
    name: str = Field(..., min_length=1, max_length=200, description="Display name")
    description: str = Field(..., min_length=20, description="Agent capability description (min 20 chars)")
    capability_type: str = Field(
        ...,
        description="One of: research, analysis, generation, enrichment, validation, execution, other"
    )
    input_schema: dict = Field(..., description="JSON Schema Draft 7 for task input validation")
    output_schema: dict = Field(..., description="JSON Schema Draft 7 for result validation")
    pricing: PricingSchema
    sla: SLASchema
    webhook_url: str = Field(..., description="HTTPS URL where Nexra sends delegation webhooks")
    webhook_secret: str = Field(..., min_length=32, description="Secret for HMAC-SHA256 webhook signing")
    is_public: bool = Field(False, description="If true, visible in cross-org marketplace")

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
        """Validate that the provided dict is a valid JSON Schema Draft 7."""
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
```

### 4.3 `services/agent_service.py`

**Path**: `nexra/services/agent_service.py`

Core agent registration logic. No FastAPI imports.

```python
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from openai import AsyncOpenAI
import jsonschema

from models.agent import Agent
from api.schemas.agents import AgentRegisterRequest
from core.errors import NexraError, INVALID_SCHEMA, INVALID_WEBHOOK_URL, EMBEDDING_SERVICE_UNAVAILABLE
import asyncio
import logging

logger = logging.getLogger("nexra.services.agent")


class AgentService:
    """Handles agent registration, embedding generation, and listing.

    Constructor dependencies:
        db: AsyncSession — SQLAlchemy async session
        openai_client: AsyncOpenAI — for text-embedding-3-small
    """

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    EMBEDDING_MAX_RETRIES = 3

    def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI) -> None:
        self.db = db
        self.openai = openai_client

    async def register(self, org_id: str, data: AgentRegisterRequest) -> Agent:
        """Register or re-register an agent capability.

        Idempotent on (org_id, agent_id). Re-registration updates all fields
        except trust_score and delegation_count.

        Steps:
        1. Check if agent_id already exists for this org
        2. Validate webhook_url is HTTPS (defense-in-depth — Pydantic also checks)
        3. Validate input_schema and output_schema are valid JSON Schema Draft 7
        4. Generate embedding from "{name}. {description}"
        5. Upsert agent record

        Returns:
            The created or updated Agent ORM object.

        Raises:
            NexraError(400, INVALID_WEBHOOK_URL): webhook_url not HTTPS
            NexraError(400, INVALID_SCHEMA): invalid JSON Schema
            NexraError(503, EMBEDDING_SERVICE_UNAVAILABLE): OpenAI API failure
        """
        # Step 1: Check existing
        existing = await self._get_by_agent_id(org_id, data.agent_id)

        # Step 2: HTTPS validation (defense-in-depth)
        if not data.webhook_url.startswith("https://"):
            raise NexraError(400, INVALID_WEBHOOK_URL, "webhook_url must use HTTPS")

        # Step 3: JSON Schema validation (defense-in-depth)
        self._validate_json_schema(data.input_schema, "input_schema")
        self._validate_json_schema(data.output_schema, "output_schema")

        # Step 4: Generate embedding
        embed_text = f"{data.name}. {data.description}"
        embedding = await self._embed(embed_text)

        # Step 5: Upsert
        if existing:
            existing.name = data.name
            existing.description = data.description
            existing.capability_type = data.capability_type
            existing.input_schema = data.input_schema
            existing.output_schema = data.output_schema
            existing.webhook_url = data.webhook_url
            existing.webhook_secret = data.webhook_secret
            existing.pricing = data.pricing.model_dump()
            existing.sla = data.sla.model_dump()
            existing.embedding = embedding
            existing.is_public = data.is_public
            existing.updated_at = datetime.now(timezone.utc)
            # trust_score and delegation_count preserved
            agent = existing
        else:
            agent = Agent(
                org_id=org_id,
                agent_id=data.agent_id,
                name=data.name,
                description=data.description,
                capability_type=data.capability_type,
                input_schema=data.input_schema,
                output_schema=data.output_schema,
                webhook_url=data.webhook_url,
                webhook_secret=data.webhook_secret,
                pricing=data.pricing.model_dump(),
                sla=data.sla.model_dump(),
                embedding=embedding,
                is_public=data.is_public,
                status="probationary",
            )
            self.db.add(agent)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_by_agent_id(self, org_id: str, agent_id: str) -> Agent | None:
        """Public method to fetch an agent by org_id + agent_id."""
        return await self._get_by_agent_id(org_id, agent_id)

    async def get_by_uuid(self, org_id: str, uuid_str: str) -> Agent | None:
        """Fetch an agent by its UUID primary key, scoped to org."""
        result = await self.db.execute(
            select(Agent).where(Agent.id == uuid_str, Agent.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: str,
        capability_type: str | None = None,
        status: str | None = None,
        is_public: bool | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Agent], str | None, int]:
        """List agents for an org with optional filters and cursor pagination.

        Returns:
            Tuple of (agents, next_cursor, total_count).
        """
        # Base query
        q = select(Agent).where(Agent.org_id == org_id)

        # Filters
        if capability_type:
            q = q.where(Agent.capability_type == capability_type)
        if status:
            q = q.where(Agent.status == status)
        if is_public is not None:
            q = q.where(Agent.is_public == is_public)

        # Count
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Cursor pagination
        if cursor:
            q = q.where(Agent.created_at < cursor)

        q = q.order_by(Agent.created_at.desc()).limit(limit + 1)
        result = await self.db.execute(q)
        agents = list(result.scalars().all())

        next_cursor = None
        if len(agents) > limit:
            next_cursor = str(agents[limit - 1].created_at.isoformat())
            agents = agents[:limit]

        return agents, next_cursor, total

    async def update_status(self, org_id: str, agent_id: str, new_status: str) -> Agent:
        """Update an agent's status (active, probationary, quarantined)."""
        agent = await self._get_by_agent_id(org_id, agent_id)
        if not agent:
            raise NexraError(404, "AGENT_NOT_FOUND", f"Agent '{agent_id}' not found")
        agent.status = new_status
        agent.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    # ─── Private Methods ──────────────────────────────────────

    async def _get_by_agent_id(self, org_id: str, agent_id: str) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    def _validate_json_schema(self, schema: dict, field_name: str) -> None:
        try:
            jsonschema.Draft7Validator.check_schema(schema)
        except jsonschema.SchemaError as e:
            raise NexraError(400, INVALID_SCHEMA, f"{field_name} is not a valid JSON Schema: {e.message}")

    async def _embed(self, text: str) -> list[float]:
        """Generate 1536-dim embedding with retry on transient errors.

        Retries up to 3 times with exponential backoff on rate limit errors.
        """
        for attempt in range(self.EMBEDDING_MAX_RETRIES):
            try:
                resp = await self.openai.embeddings.create(
                    input=text,
                    model=self.EMBEDDING_MODEL,
                )
                return resp.data[0].embedding
            except Exception as e:
                if attempt < self.EMBEDDING_MAX_RETRIES - 1:
                    logger.warning(f"Embedding attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise NexraError(
                        503,
                        EMBEDDING_SERVICE_UNAVAILABLE,
                        f"Failed to generate embedding after {self.EMBEDDING_MAX_RETRIES} attempts: {str(e)[:200]}",
                    )
```

### 4.4 `api/routers/agents.py`

**Path**: `nexra/api/routers/agents.py`

```python
import time
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from api.dependencies import get_authenticated_org, get_db
from api.schemas.agents import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentDetailResponse,
    AgentListItem,
    AgentListResponse,
)
from api.schemas.common import DataResponse, MetaResponse
from services.agent_service import AgentService
from core.config import get_settings
from models.organization import Organization

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(api_key=settings.openai_api_key)


@router.post("/register")
async def register_agent(
    request: Request,
    body: AgentRegisterRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Register or re-register an agent capability.

    Idempotent on agent_id — re-registration updates all fields except trust_score.
    New agents start with status='probationary' and trust_score=1.000.
    """
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.register(str(org.id), body)
    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=AgentRegisterResponse(
            agent_id=agent.agent_id,
            status=agent.status,
            embedding_id=str(agent.id),
            registered_at=agent.created_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.get("/registry")
async def list_agents(
    request: Request,
    capability_type: str | None = Query(None),
    status: str | None = Query(None),
    is_public: bool | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """List registered agents for the authenticated org.

    Supports filtering by capability_type, status, is_public.
    Cursor-based pagination.
    """
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agents, next_cursor, total = await service.list_for_org(
        str(org.id), capability_type, status, is_public, cursor, limit
    )
    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": AgentListResponse(
            agents=[
                AgentListItem(
                    agent_id=a.agent_id,
                    name=a.name,
                    capability_type=a.capability_type,
                    trust_score=float(a.trust_score),
                    status=a.status,
                    is_public=a.is_public,
                    delegation_count=a.delegation_count,
                    pricing=a.pricing,
                    sla=a.sla,
                    created_at=a.created_at,
                )
                for a in agents
            ],
            next_cursor=next_cursor,
            total_count=total,
        ),
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    }


@router.get("/{agent_ref}")
async def get_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get agent details by UUID or agent_id.

    agent_ref can be either the UUID primary key or the human-readable agent_id.
    """
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())

    # Try UUID first, then agent_id
    agent = None
    try:
        import uuid
        uuid.UUID(agent_ref)
        agent = await service.get_by_uuid(str(org.id), agent_ref)
    except ValueError:
        agent = await service.get_by_agent_id(str(org.id), agent_ref)

    if not agent:
        from core.errors import NexraError, AGENT_NOT_FOUND
        raise NexraError(404, AGENT_NOT_FOUND, f"Agent '{agent_ref}' not found")

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=AgentDetailResponse(
            id=str(agent.id),
            agent_id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            capability_type=agent.capability_type,
            input_schema=agent.input_schema,
            output_schema=agent.output_schema,
            pricing=agent.pricing,
            sla=agent.sla,
            webhook_url=agent.webhook_url,
            is_public=agent.is_public,
            trust_score=float(agent.trust_score),
            status=agent.status,
            delegation_count=agent.delegation_count,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
```

**Register in `api/main.py`**:
```python
from api.routers.agents import router as agents_router
app.include_router(agents_router, prefix="/v1")
```

---

## 5. Database Changes

No new migrations. All tables exist from Phase 1.

---

## 6. Environment Variables

- `OPENAI_API_KEY` — required for embedding generation. Must be set in `.env`.

---

## 7. Guardrails

1. **DO NOT** return `webhook_secret` in any response. It is write-only.
2. **DO NOT** return the `embedding` vector in any response. It is internal.
3. **DO NOT** skip JSON Schema validation on input_schema/output_schema. Both Pydantic and the service layer validate — defense in depth.
4. **DO NOT** allow agent_id with uppercase letters, spaces, or special characters. Regex: `^[a-z0-9-]+$`.
5. **DO NOT** overwrite trust_score or delegation_count on re-registration. These are preserved.
6. **DO NOT** create a new OpenAI client per request in production — use a shared instance. For MVP, per-request is acceptable.
7. **DO NOT** embed empty strings. The description field has a minimum length of 20 characters.

---

## 8. Verification Checklist

```bash
# 1. Register an agent
curl -X POST http://localhost:8000/v1/agents/register \
  -H "Authorization: Bearer <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-agent-v1",
    "name": "Research Agent",
    "description": "Performs competitive research and market analysis for B2B SaaS companies",
    "capability_type": "research",
    "input_schema": {"type": "object", "required": ["company_name"], "properties": {"company_name": {"type": "string"}}},
    "output_schema": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    "pricing": {"per_call_usd": 0.15},
    "sla": {"p99_latency_ms": 8000, "availability": 0.99},
    "webhook_url": "https://example.com/webhook",
    "webhook_secret": "whs_this_is_a_test_secret_that_is_long_enough"
  }'
# Expected: 200 with { data: { agent_id, status: "probationary", ... } }

# 2. Verify embedding stored
docker compose exec postgres psql -U nexra -d nexra -c "SELECT agent_id, embedding IS NOT NULL as has_embedding FROM agents;"
# Expected: research-agent-v1 | true

# 3. Re-register same agent (idempotent)
# Same curl as above — should return 200, not error

# 4. List agents
curl http://localhost:8000/v1/agents/registry \
  -H "Authorization: Bearer <your_api_key>"
# Expected: { data: { agents: [...], total_count: 1 } }

# 5. Get agent by agent_id
curl http://localhost:8000/v1/agents/research-agent-v1 \
  -H "Authorization: Bearer <your_api_key>"
# Expected: { data: { agent_id: "research-agent-v1", ... } }

# 6. Invalid agent_id format
curl -X POST http://localhost:8000/v1/agents/register \
  -H "Authorization: Bearer <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "INVALID ID!", ...}'
# Expected: 422 validation error

# 7. HTTP webhook_url rejected
curl -X POST http://localhost:8000/v1/agents/register \
  -H "Authorization: Bearer <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "http://example.com/webhook", ...}'
# Expected: 422 validation error
```

---

## 9. Test Cases

| Test ID | Category | Description | Mock Setup | Assertion |
|---------|----------|-------------|------------|-----------|
| T-REG-001 | Registration | New agent created with status=probationary | Mock OpenAI → return 1536-dim vector | Agent in DB, status=="probationary", trust_score==1.000 |
| T-REG-002 | Registration | Re-register updates fields, preserves trust_score | Mock OpenAI, pre-create agent with trust_score=0.85 | trust_score still 0.85 after re-register |
| T-REG-003 | Registration | Re-register triggers re-embedding | Mock OpenAI | OpenAI called with new description text |
| T-REG-004 | Validation | agent_id with uppercase rejected | None | 422 error |
| T-REG-005 | Validation | agent_id with spaces rejected | None | 422 error |
| T-REG-006 | Validation | agent_id > 64 chars rejected | None | 422 error |
| T-REG-007 | Validation | description < 20 chars rejected | None | 422 error |
| T-REG-008 | Validation | webhook_url without https:// rejected | None | 422 error |
| T-REG-009 | Validation | webhook_secret < 32 chars rejected | None | 422 error |
| T-REG-010 | Validation | Invalid JSON Schema for input_schema rejected | None | 422 error |
| T-REG-011 | Validation | Invalid capability_type rejected | None | 422 error |
| T-REG-012 | Embedding | OpenAI failure after 3 retries → 503 | Mock OpenAI → raise exception 3 times | NexraError 503 EMBEDDING_SERVICE_UNAVAILABLE |
| T-REG-013 | Listing | List returns all agents for org | Create 3 agents | agents list has 3 items |
| T-REG-014 | Listing | Filter by capability_type | Create agents with different types | Only matching type returned |
| T-REG-015 | Listing | Filter by status | Create active + probationary agents | Only matching status returned |
| T-REG-016 | Listing | Cursor pagination | Create 5 agents, limit=2 | First page has 2, next_cursor set, second page has 2, etc. |
| T-REG-017 | Get | Get by agent_id returns correct agent | Create agent | All fields match |
| T-REG-018 | Get | Get by UUID returns correct agent | Create agent | All fields match |
| T-REG-019 | Get | Get nonexistent agent returns 404 | None | NexraError 404 AGENT_NOT_FOUND |
| T-REG-020 | Security | Agent from different org not visible | Create agent under org A | Get from org B returns 404 |
| T-REG-021 | Response | webhook_secret NOT in response | Register agent | Response does not contain webhook_secret |
| T-REG-022 | Response | embedding NOT in response | Register agent | Response does not contain embedding |
