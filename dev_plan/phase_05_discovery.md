# Phase 05 — Capability Discovery Engine

**Phase:** 05 / 12 | **TDD Sections:** §9 (Discovery), §6.4 (POST /capabilities/discover) | **48h Block:** Block 5 (13-17h)

> ⚠️ **Prerequisite:** Phase 04 acceptance criteria all GREEN. At least 3 agents registered in DB before testing.

---

## Objective

Implement `DiscoveryService` with the full pgvector composite-score SQL query (TDD §9.1), and the `POST /capabilities/discover` endpoint. Discovery must rank candidates by composite score (semantic 50%, trust 25%, cost 15%, latency 10%), apply all hard filters, and return results in < 200ms P99.

---

## Claude Code Prompt

```
You are implementing the Discovery Engine for Nexra (FastAPI, pgvector, PostgreSQL 16).

TASK: Implement DiscoveryService and POST /capabilities/discover per TDD §9 and §6.4.

Requirements:

1. **api/schemas/discovery.py** — Pydantic v2 schemas:
   ```python
   class DiscoverRequest(BaseModel):
       query: str = Field(..., min_length=3)
       capability_type: str | None = None
       budget_cap_usd: float | None = Field(None, gt=0)
       max_latency_ms: int | None = Field(None, gt=0)
       exclude_agents: list[str] = []
       include_cross_org: bool = False
       limit: int = Field(5, ge=1, le=20)
   
   class AgentMatch(BaseModel):
       agent_id: str
       name: str
       match_score: float  # composite: 0.0 - 1.0
       trust_score: float
       status: str
       pricing: dict
       sla: dict
       is_cross_org: bool
       capability_type: str
   
   class DiscoverResponse(BaseModel):
       matches: list[AgentMatch]
       total_candidates: int  # agents evaluated before filtering
       filtered_count: int    # agents remaining after hard filters
       latency_ms: int        # actual discovery latency
   ```

2. **services/discovery_service.py** — single-query composite scoring:
   ```python
   class DiscoveryService:
       def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI): ...
   
       async def discover(
           self,
           org_id: str,
           request: DiscoverRequest,
           restrict_probationary: bool = False
       ) -> DiscoverResponse:
           # 1. Generate embedding for request.query
           query_embedding = await self._embed(request.query)
           # 2. Run the composite SQL query (single round-trip — see SQL below)
           # 3. Build AgentMatch list from results
           # 4. Return DiscoverResponse with latency_ms measured
   
       async def _embed(self, text: str) -> list[float]:
           # Same retry logic as AgentService._embed()
   ```

   The SQL query (EXACTLY as in TDD §9.1 — do not deviate):
   ```sql
   WITH candidates AS (
     SELECT
       a.id, a.agent_id, a.name, a.capability_type,
       a.trust_score, a.pricing, a.sla, a.is_public, a.status,
       1 - (a.embedding <=> :query_embedding) AS semantic_score,
       a.pricing->>'per_call_usd' AS price_usd,
       a.sla->>'p99_latency_ms' AS latency_ms
     FROM agents a
     WHERE
       a.status != 'quarantined'
       AND NOT (a.status = 'probationary' AND :restrict_probationary)
       AND (:capability_type IS NULL OR a.capability_type = :capability_type)
       AND (:budget_cap IS NULL OR (a.pricing->>'per_call_usd')::float <= :budget_cap)
       AND (:max_latency IS NULL OR (a.sla->>'p99_latency_ms')::int <= :max_latency)
       AND (a.org_id = :caller_org_id OR a.is_public = TRUE)
       AND a.agent_id != ALL(:exclude_agents)
   ),
   price_stats AS (
     SELECT MAX((price_usd)::float) as max_price, MAX((latency_ms)::float) as max_latency
     FROM candidates
   )
   SELECT
     c.*,
     (
       (c.semantic_score * 0.50)
       + (c.trust_score * 0.25)
       + ((1 - (c.price_usd::float / NULLIF(ps.max_price, 0))) * 0.15)
       + ((1 - (c.latency_ms::float / NULLIF(ps.max_latency, 0))) * 0.10)
     ) AS composite_score
   FROM candidates c, price_stats ps
   ORDER BY composite_score DESC
   LIMIT :limit;
   ```
   
   Run via: `await self.db.execute(text(sql), params)`
   Pass `query_embedding` as a Python list → SQLAlchemy will convert for pgvector.

3. **api/routers/capabilities.py**:
   ```python
   @router.post("/capabilities/discover")
   async def discover_capabilities(
       request: DiscoverRequest,
       org_and_agent: tuple = Depends(get_org_and_agent),
       db: AsyncSession = Depends(get_db),
       openai_client = Depends(get_openai_client)
   ):
       org, caller_agent = org_and_agent
       # Require X-Agent-ID for /capabilities/discover
       if caller_agent is None:
           raise NexraError(401, 'UNAUTHORIZED', 'X-Agent-ID header required for discovery')
       service = DiscoveryService(db, openai_client)
       result = await service.discover(org.id, request)
       return ResponseEnvelope(data=result, meta={"request_id": request_id, "latency_ms": ...})
   ```

4. Mount router in api/main.py.

Performance requirement: The discover endpoint must complete in < 200ms P99 (excluding OpenAI embedding call). The SQL query runs in a single round-trip. If using IVFFlat index, set `SET ivfflat.probes = 10` at session level before the query.
```

---

## Guardrails

- ✅ **Single SQL query** — no N+1 queries. The composite score must be computed entirely in PostgreSQL.
- ✅ **Quarantined agents always excluded** — `a.status != 'quarantined'` is a hard filter (T-017)
- ✅ **Budget filter excludes expensive agents** — `per_call_usd <= budget_cap` hard filter (T-018)
- ✅ **`include_cross_org: false` by default** — only same-org agents + `is_public=true` agents visible
- ✅ **`ivfflat.probes = 10`** — set as session-level param before the discovery query
- ✅ **Composite score = semantic 50% + trust 25% + cost 15% + latency 10%** (TDD §6.4)
- ✅ **X-Agent-ID required** for `/capabilities/discover` (agent is the caller, not just the org)
- ❌ **Do NOT filter probationary agents by default** — `restrict_probationary` is false unless org configures it
- ✅ **`latency_ms` in response** = actual wall-clock time of the discovery query (measured in service)
- ✅ **max limit=20** — enforce via Pydantic `le=20`

---

## Acceptance Criteria

```bash
# Setup: ensure 3+ agents registered with different capability_types and trust scores

# 1. Basic discovery
curl -X POST http://localhost:8000/capabilities/discover \
  -H "Authorization: Bearer nx_live_<key>" \
  -H "X-Agent-ID: sales-agent-v1" \
  -H "Content-Type: application/json" \
  -d '{"query": "competitive research for B2B SaaS companies", "limit": 5}'
# → {"data": {"matches": [...], "total_candidates": N, "filtered_count": M, "latency_ms": <200}}

# 2. Quarantined agent excluded (T-017)
# Quarantine an agent via POST /agents/{id}/quarantine, then run discovery
# → quarantined agent does NOT appear in matches

# 3. Budget filter (T-018)
curl -X POST http://localhost:8000/capabilities/discover \
  -d '{"query": "research", "budget_cap_usd": 0.10}'
# → No agents with per_call_usd > 0.10 in results

# 4. capability_type hard filter
curl -X POST http://localhost:8000/capabilities/discover \
  -d '{"query": "any task", "capability_type": "analysis"}'
# → Only analysis agents in results

# 5. Performance check (P99 < 200ms)
time curl -X POST http://localhost:8000/capabilities/discover \
  -d '{"query": "research", "limit": 5}'
# → real time < 0.200s (excluding network)
```

---

## Test Cases

```bash
# Unit: DiscoveryService composite score (mock DB returning raw SQL rows)
poetry run pytest tests/unit/test_discovery_service.py -v
# - composite_score formula correct (50/25/15/10 weights)
# - Quarantined agent gets filtered at SQL level

# Integration: Real pgvector query with 5+ agents (T-017, T-018)
poetry run pytest tests/integration/test_discovery.py -v
# - T-017: Quarantined agent excluded from results
# - T-018: Budget filter excludes expensive agents
# - Results sorted by composite_score DESC
# - latency_ms reported in response

# Contract: response shape
poetry run pytest tests/contracts/test_discovery_schema.py -v
# - Response always has matches[], total_candidates, filtered_count, latency_ms
```
