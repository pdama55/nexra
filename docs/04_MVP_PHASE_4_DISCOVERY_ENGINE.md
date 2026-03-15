# Phase 4 — Discovery Engine

> **TDD Sections**: §6.4 (POST /capabilities/discover), §9 (Discovery Engine — Semantic Search & Ranking)
>
> **48-Hour Block**: Hours 13–17
>
> **Depends On**: Phase 3 (Agent Registry) complete — agents registered with embeddings in pgvector.

---

## 1. Prerequisites

- [ ] POST /agents/register works — agents stored with VECTOR(1536) embeddings
- [ ] At least 3 test agents registered with different capability_types
- [ ] pgvector extension installed, IVFFlat index created

---

## 2. Objective

Deliver semantic capability discovery with composite scoring:

- POST /capabilities/discover — semantic search + hard filters + composite ranking
- Composite score: schema fit 50% + trust score 25% + cost 15% + latency 10%
- Hard filters applied BEFORE scoring (quarantined excluded, budget cap, latency SLA, cross-org visibility)
- P99 latency target: < 200ms
- All scoring computed in a single PostgreSQL query (no N+1)

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring location | Single SQL query with CTEs | TDD §9.1. Avoids N+1. All scoring in Postgres. |
| Similarity metric | Cosine similarity via pgvector `<=>` operator | TDD §9.1. `1 - (a <=> b)` gives similarity score 0-1. |
| Query embedding | Generated at request time via OpenAI | Same model as registration (text-embedding-3-small). |
| Normalization | Price and latency normalized against max in result set | TDD §10. Prevents absolute values from dominating. |
| Default limit | 5 results, max 20 | TDD §6.4. Reasonable for agent selection. |

---

## 4. File-by-File Implementation Guide

### 4.1 `api/schemas/capabilities.py`

**Path**: `nexra/api/schemas/capabilities.py`

```python
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
    match_score: float  # composite score
    trust_score: float
    status: str
    pricing: dict
    sla: dict
    is_cross_org: bool
    capability_type: str


class DiscoverResponse(BaseModel):
    matches: list[DiscoverMatchItem]
    total_candidates: int  # agents evaluated before filtering
    filtered_count: int  # agents remaining after hard filters
    latency_ms: float
```

### 4.2 `services/discovery_service.py`

**Path**: `nexra/services/discovery_service.py`

The composite score query runs entirely in PostgreSQL. The Python code generates the query embedding, executes the SQL, and returns results.

```python
import time
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from openai import AsyncOpenAI

from api.schemas.capabilities import DiscoverRequest, DiscoverMatchItem
from core.errors import NexraError, EMBEDDING_SERVICE_UNAVAILABLE

logger = logging.getLogger("nexra.services.discovery")


class DiscoveryService:
    """Semantic discovery with composite scoring.

    Constructor dependencies:
        db: AsyncSession
        openai_client: AsyncOpenAI
    """

    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI) -> None:
        self.db = db
        self.openai = openai_client

    async def discover(
        self,
        caller_org_id: str,
        request: DiscoverRequest,
    ) -> tuple[list[DiscoverMatchItem], int, int]:
        """Execute semantic discovery with composite scoring.

        Steps:
        1. Generate embedding for the query text
        2. Execute composite score SQL query with hard filters
        3. Return ranked matches

        Returns:
            Tuple of (matches, total_candidates, filtered_count)
        """
        # Step 1: Generate query embedding
        query_embedding = await self._embed(request.query)

        # Step 2: Execute discovery SQL
        # The SQL uses CTEs to:
        #   a) Apply hard filters and compute semantic score
        #   b) Compute price/latency stats for normalization
        #   c) Compute composite score and rank

        sql = text("""
            WITH candidates AS (
                SELECT
                    a.id,
                    a.agent_id,
                    a.name,
                    a.capability_type,
                    a.trust_score,
                    a.pricing,
                    a.sla,
                    a.is_public,
                    a.status,
                    a.org_id,
                    1 - (a.embedding <=> CAST(:query_embedding AS vector)) AS semantic_score,
                    (a.pricing->>'per_call_usd')::float AS price_usd,
                    (a.sla->>'p99_latency_ms')::float AS latency_ms
                FROM agents a
                WHERE
                    a.status != 'quarantined'
                    AND a.embedding IS NOT NULL
                    AND (:capability_type IS NULL OR a.capability_type = :capability_type)
                    AND (:budget_cap IS NULL OR (a.pricing->>'per_call_usd')::float <= :budget_cap)
                    AND (:max_latency IS NULL OR (a.sla->>'p99_latency_ms')::int <= :max_latency)
                    AND (a.org_id = CAST(:caller_org_id AS uuid) OR (a.is_public = TRUE AND :include_cross_org = TRUE))
                    AND a.agent_id != ALL(:exclude_agents)
            ),
            price_stats AS (
                SELECT
                    COALESCE(MAX(price_usd), 1) AS max_price,
                    COALESCE(MAX(latency_ms), 1) AS max_latency,
                    COUNT(*) AS filtered_count
                FROM candidates
            )
            SELECT
                c.agent_id,
                c.name,
                c.capability_type,
                c.trust_score::float,
                c.status,
                c.pricing,
                c.sla,
                c.is_public,
                c.org_id,
                c.semantic_score,
                (
                    (c.semantic_score * 0.50)
                    + (c.trust_score::float * 0.25)
                    + ((1 - (c.price_usd / NULLIF(ps.max_price, 0))) * 0.15)
                    + ((1 - (c.latency_ms / NULLIF(ps.max_latency, 0))) * 0.10)
                ) AS composite_score,
                ps.filtered_count
            FROM candidates c, price_stats ps
            ORDER BY composite_score DESC
            LIMIT :result_limit;
        """)

        # Format embedding as PostgreSQL vector literal
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "capability_type": request.capability_type,
                "budget_cap": request.budget_cap_usd,
                "max_latency": request.max_latency_ms,
                "caller_org_id": caller_org_id,
                "include_cross_org": request.include_cross_org,
                "exclude_agents": request.exclude_agents or [],
                "result_limit": request.limit,
            },
        )

        rows = result.fetchall()

        # Get total candidates (before filtering) for analytics
        total_q = text("SELECT COUNT(*) FROM agents WHERE embedding IS NOT NULL AND status != 'quarantined'")
        total_result = await self.db.execute(total_q)
        total_candidates = total_result.scalar() or 0

        filtered_count = rows[0].filtered_count if rows else 0

        matches = [
            DiscoverMatchItem(
                agent_id=row.agent_id,
                name=row.name,
                match_score=round(float(row.composite_score), 4),
                trust_score=round(float(row.trust_score), 3),
                status=row.status,
                pricing=row.pricing,
                sla=row.sla,
                is_cross_org=(str(row.org_id) != caller_org_id),
                capability_type=row.capability_type,
            )
            for row in rows
        ]

        return matches, total_candidates, int(filtered_count)

    async def _embed(self, text_input: str) -> list[float]:
        """Generate query embedding with retry."""
        for attempt in range(3):
            try:
                resp = await self.openai.embeddings.create(
                    input=text_input,
                    model=self.EMBEDDING_MODEL,
                )
                return resp.data[0].embedding
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Query embedding attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise NexraError(
                        503, EMBEDDING_SERVICE_UNAVAILABLE,
                        f"Failed to generate query embedding: {str(e)[:200]}"
                    )
```

### 4.3 `api/routers/capabilities.py`

**Path**: `nexra/api/routers/capabilities.py`

```python
import time
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from api.dependencies import get_authenticated_org_and_agent, get_db
from api.schemas.capabilities import DiscoverRequest, DiscoverResponse
from api.schemas.common import DataResponse, MetaResponse
from services.discovery_service import DiscoveryService
from core.config import get_settings
from models.organization import Organization
from models.agent import Agent

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.post("/discover")
async def discover_capabilities(
    request: Request,
    body: DiscoverRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
):
    """Discover agent capabilities via semantic search.

    Requires X-Agent-ID header — discovery is agent-initiated.
    Returns ranked matches with composite score.
    """
    org, caller_agent = org_and_agent
    start = time.perf_counter()

    settings = get_settings()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    service = DiscoveryService(db, openai_client)

    matches, total_candidates, filtered_count = await service.discover(
        str(org.id), body
    )

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=DiscoverResponse(
            matches=matches,
            total_candidates=total_candidates,
            filtered_count=filtered_count,
            latency_ms=latency,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
```

**Register in `api/main.py`**:
```python
from api.routers.capabilities import router as capabilities_router
app.include_router(capabilities_router, prefix="/v1")
```

---

## 5. Database Changes

No new migrations. The IVFFlat index on `agents.embedding` was created in Phase 1.

**Performance note**: For the IVFFlat index to be effective, set `ivfflat.probes` at session level:
```sql
SET ivfflat.probes = 10;  -- default, >95% recall for <1000 agents
```

This should be set in the SQLAlchemy session factory or as a connection init command.

---

## 6. Guardrails

1. **DO NOT** compute composite scores in Python. The entire scoring runs in PostgreSQL via the CTE query.
2. **DO NOT** return agents with `embedding IS NULL`. These agents haven't been embedded yet (edge case during registration failure).
3. **DO NOT** return quarantined agents in discovery results — they are excluded by the hard filter.
4. **DO NOT** return private agents (`is_public=false`) from other orgs even if `include_cross_org=true`.
5. **DO NOT** use `OFFSET` pagination for discovery — it's a one-shot ranked query, not paginated.
6. **DO NOT** cache discovery results — they must reflect real-time trust scores and agent status.
7. **DO NOT** allow `limit > 20` — cap at 20 to prevent expensive queries.

---

## 7. Verification Checklist

```bash
# 1. Register 3 agents with different capabilities
# (use the curl from Phase 3, varying agent_id, name, description, capability_type, pricing)

# 2. Discover by semantic query
curl -X POST http://localhost:8000/v1/capabilities/discover \
  -H "Authorization: Bearer <api_key>" \
  -H "X-Agent-ID: <any_registered_agent_id>" \
  -H "Content-Type: application/json" \
  -d '{"query": "competitive research for B2B SaaS companies", "limit": 5}'
# Expected: matches array with composite scores, sorted DESC

# 3. Verify hard filter: budget cap
curl -X POST http://localhost:8000/v1/capabilities/discover \
  -H "Authorization: Bearer <api_key>" \
  -H "X-Agent-ID: <agent_id>" \
  -H "Content-Type: application/json" \
  -d '{"query": "research", "budget_cap_usd": 0.01}'
# Expected: no matches (all agents cost more than $0.01)

# 4. Verify hard filter: capability_type
curl -X POST http://localhost:8000/v1/capabilities/discover \
  -H "Authorization: Bearer <api_key>" \
  -H "X-Agent-ID: <agent_id>" \
  -H "Content-Type: application/json" \
  -d '{"query": "research", "capability_type": "analysis"}'
# Expected: only agents with capability_type="analysis"

# 5. Verify quarantined agent excluded
# (quarantine an agent via DB, then discover — it should not appear)

# 6. Check latency
# Expected: latency_ms < 200 for P99
```

---

## 8. Test Cases

| Test ID | Category | Description | Mock Setup | Assertion |
|---------|----------|-------------|------------|-----------|
| T-DISC-001 | Ranking | Higher semantic match ranks first | 3 agents, mock embeddings with known cosine distances | First result has highest composite_score |
| T-DISC-002 | Ranking | Trust score affects ranking | 2 agents same embedding, different trust | Higher trust agent ranks first |
| T-DISC-003 | Ranking | Cheaper agent ranks higher (cost component) | 2 agents same embedding/trust, different price | Cheaper agent has higher composite_score |
| T-DISC-004 | Filter | Quarantined agent excluded | 1 quarantined + 1 active agent | Only active agent in results |
| T-DISC-005 | Filter | Budget cap excludes expensive agents | Agent costs $0.50, budget_cap=$0.25 | No matches |
| T-DISC-006 | Filter | Latency SLA excludes slow agents | Agent SLA 10000ms, max_latency=5000 | No matches |
| T-DISC-007 | Filter | Cross-org private agents hidden | Agent in org B with is_public=false | Not visible to org A |
| T-DISC-008 | Filter | Cross-org public agents visible when include_cross_org=true | Agent in org B with is_public=true | Visible to org A, is_cross_org=true |
| T-DISC-009 | Filter | exclude_agents removes specific agents | Exclude agent-1 | agent-1 not in results |
| T-DISC-010 | Filter | capability_type hard filter | 2 research + 1 analysis agent, filter="research" | Only 2 research agents returned |
| T-DISC-011 | Limit | limit=1 returns only 1 result | 3 agents | matches array length == 1 |
| T-DISC-012 | Edge | No agents match → empty results | No agents registered | matches=[], filtered_count=0 |
| T-DISC-013 | Edge | Agent with NULL embedding excluded | Agent registered but embedding failed | Not in results |
| T-DISC-014 | Performance | Discovery completes under 200ms | 100 agents with embeddings | latency_ms < 200 |
| T-DISC-015 | Error | OpenAI embedding failure → 503 | Mock OpenAI → raise 3 times | NexraError 503 |
