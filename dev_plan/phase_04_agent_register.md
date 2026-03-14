# Phase 04 — Agent Registration & Registry

**Phase:** 04 / 12 | **TDD Sections:** §5.2 (AgentService), §6.3 (POST /agents/register), §9.2 (embedding) | **48h Block:** Block 4 (9-13h)

> ⚠️ **Prerequisite:** Phase 03 acceptance criteria all GREEN before starting.

---

## Objective

Implement `AgentService` with full `register()` (idempotent upsert + OpenAI embedding), and the API endpoints: `POST /agents/register`, `GET /agents/registry`, `GET /agents/{id}`, `POST /agents/{id}/quarantine`, `POST /agents/{id}/activate`. All request/response schemas follow TDD §6.3 exactly.

---

## Claude Code Prompt

```
You are implementing the Agent Registration layer for Nexra (FastAPI, Python 3.12, OpenAI embeddings).

TASK: Implement AgentService and the /agents/* endpoints per TDD §5.2 and §6.3.

Requirements:

1. **api/schemas/agents.py** — Pydantic v2 request/response models:
   ```python
   class SlaSchema(BaseModel):
       p99_latency_ms: int = Field(..., gt=0)
       availability: float = Field(..., ge=0.0, le=1.0)
   
   class PricingSchema(BaseModel):
       per_call_usd: float = Field(..., gt=0)
   
   class AgentRegisterRequest(BaseModel):
       agent_id: str = Field(..., pattern=r'^[a-z0-9-]{1,64}$')  # regex enforced
       name: str = Field(..., max_length=200)
       description: str = Field(..., min_length=20)
       capability_type: Literal['research','analysis','generation','enrichment','validation','execution','other']
       input_schema: dict  # validated as JSON Schema Draft 7 by service layer
       output_schema: dict  # validated as JSON Schema Draft 7 by service layer
       pricing: PricingSchema
       sla: SlaSchema
       webhook_url: str  # must start with https:// — validated by service layer
       webhook_secret: str = Field(..., min_length=32)
       is_public: bool = False
   
   class AgentRegisterResponse(BaseModel):
       agent_id: str
       status: str
       embedding_id: str  # UUID of the agent record
       registered_at: datetime
   
   class AgentListResponse(BaseModel):
       agents: list[AgentDetail]
       next_cursor: str | None
       total_count: int
   
   class ResponseEnvelope(BaseModel):
       data: Any
       meta: dict  # {"request_id": str, "latency_ms": int}
   ```

2. **services/agent_service.py** — exactly as TDD §5.2:
   ```python
   class AgentService:
       def __init__(self, db: AsyncSession, openai_client: AsyncOpenAI): ...
   
       async def register(self, org_id: str, data: AgentRegisterRequest) -> Agent:
           # Step 1: Check if agent_id already exists for this org (idempotent re-register)
           existing = await self._get_by_agent_id(org_id, data.agent_id)
           # Step 2: Validate webhook_url starts with https://
           if not data.webhook_url.startswith('https://'):
               raise NexraError(400, 'INVALID_WEBHOOK_URL', 'webhook_url must use HTTPS')
           # Step 3: Validate input_schema and output_schema are valid JSON Schema Draft 7
           #   Use: jsonschema.Draft7Validator.check_schema(data.input_schema)
           self._validate_json_schema(data.input_schema)
           self._validate_json_schema(data.output_schema)
           # Step 4: Generate embedding from name + description
           embed_text = f'{data.name}. {data.description}'
           embedding = await self._embed(embed_text)
           # Step 5: Upsert agent record
           if existing:
               # Update all fields, preserve trust_score and delegation_count
               ...
           else:
               agent = Agent(org_id=org_id, status='probationary', embedding=embedding, **data.model_dump())
           await self.db.commit()
           return agent
   
       async def _embed(self, text: str) -> list[float]:
           # Retry up to 3 times on openai.RateLimitError with exponential backoff
           # Returns list[float] of 1536 dimensions
           # Raises NexraError(503, 'EMBEDDING_SERVICE_UNAVAILABLE') after 3 failures
   
       def _validate_json_schema(self, schema: dict) -> None:
           # Uses jsonschema.Draft7Validator.check_schema(schema)
           # Raises NexraError(400, 'INVALID_SCHEMA', ...) on failure
   
       async def get_by_id(self, org_id: str, agent_uuid_or_slug: str) -> Agent | None:
           # Try UUID first, then fall back to agent_id slug search
   
       async def list_for_org(self, org_id: str, cursor: str | None, limit: int = 20) -> tuple[list[Agent], str | None]:
           # Cursor-based pagination on created_at DESC
   
       async def quarantine(self, org_id: str, agent_id: str) -> Agent:
           # Set status = 'quarantined', write audit log entry 'agent_quarantined'
   
       async def activate(self, org_id: str, agent_id: str) -> Agent:
           # q→probationary; probationary→active. Write audit log 'agent_activated'
   ```

3. **api/routers/agents.py**:
   - POST /agents/register → 201 AgentRegisterResponse (use ResponseEnvelope)
   - GET /agents/registry → 200 AgentListResponse (cursor-paginated, filterable by status, capability_type)
   - GET /agents/{id} → 200 AgentDetail  
   - GET /agents/{id}/trust → 200 trust score breakdown (pull from trust_score_events)
   - POST /agents/{id}/quarantine → 200 (admin action)
   - POST /agents/{id}/activate → 200 (admin action)
   
   All routes use: `org_and_agent = Depends(get_org_and_agent)`
   Agent-initiated calls (register, discover, delegate) also require X-Agent-ID header.

4. **api/dependencies.py** — add get_openai_client():
   ```python
   def get_openai_client() -> AsyncOpenAI:
       return AsyncOpenAI(api_key=get_settings().openai_api_key)
   ```

Error cases (from TDD §6.3):
- 400 INVALID_SCHEMA — invalid JSON Schema
- 400 INVALID_WEBHOOK_URL — not https://
- 400 INVALID_AGENT_ID — regex mismatch (caught by Pydantic)
- 401 UNAUTHORIZED — bad API key
- 429 RATE_LIMIT_EXCEEDED

All responses wrapped in: {"data": {...}, "meta": {"request_id": "...", "latency_ms": 340}}
```

---

## Guardrails

- ✅ **idempotent re-register** — same `agent_id` for same org = update, not 409 error
- ✅ **Preserve `trust_score` and `delegation_count`** on re-register (TDD §5.2)
- ✅ **New agent status = `'probationary'`** — never `'active'` on first registration
- ✅ **OpenAI retry with exponential backoff** (3 attempts, 2^attempt seconds)
- ✅ **JSON Schema Draft 7 validation** via `jsonschema.Draft7Validator.check_schema()`
- ✅ **ResponseEnvelope** wraps ALL responses — `{"data": ..., "meta": {"request_id": ..., "latency_ms": ...}}`
- ✅ **`webhook_secret` minimum 32 chars** — enforced at Pydantic level
- ❌ **Do NOT store `webhook_secret` hashed** — store plaintext (used for HMAC signing later)
- ❌ **Do NOT skip embedding on re-register** — always re-embed (description may have changed)
- ✅ **Cursor pagination on `GET /agents/registry`** — cursor = last seen `created_at`

---

## Acceptance Criteria

```bash
# 1. Register an agent
curl -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer nx_live_<key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-agent-v1",
    "name": "Competitive Research Agent",
    "description": "Researches competitors and provides detailed analysis reports for B2B sales teams",
    "capability_type": "research",
    "input_schema": {"type": "object", "required": ["company_name"], "properties": {"company_name": {"type": "string"}}},
    "output_schema": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    "pricing": {"per_call_usd": 0.15},
    "sla": {"p99_latency_ms": 8000, "availability": 0.99},
    "webhook_url": "https://agent.example.com/nexra",
    "webhook_secret": "s3cr3t_webhook_12345678901234567890123456"
  }'
# → 201 {"data": {"agent_id": "research-agent-v1", "status": "probationary", ...}}

# 2. Re-register same agent_id (idempotent)
# (run same curl again) → 201 (no error, updates fields)

# 3. Verify embedding stored in DB
docker exec nexra-postgres-1 psql -U nexra -d nexra -c \
  "SELECT array_length(embedding::float[], 1) FROM agents WHERE agent_id='research-agent-v1';"
# → 1536

# 4. List registry
curl -H "Authorization: Bearer nx_live_<key>" http://localhost:8000/agents/registry
# → {"data": {"agents": [...], "next_cursor": null}}

# 5. Invalid webhook_url (http://)
# → 400 INVALID_WEBHOOK_URL

# 6. Invalid JSON Schema
# → 400 INVALID_SCHEMA
```

---

## Test Cases

```bash
# Unit: AgentService (mock OpenAI, mock DB)
poetry run pytest tests/unit/test_agent_service.py -v
# - register() returns Agent with status='probationary'
# - re-register same agent_id returns updated Agent (no duplicate)
# - http:// webhook_url raises NexraError 400 INVALID_WEBHOOK_URL
# - invalid JSON schema raises NexraError 400 INVALID_SCHEMA
# - _embed() retries on RateLimitError, raises after 3 failures

# Integration: POST /agents/register with real DB + mocked OpenAI
poetry run pytest tests/integration/test_agent_register.py -v
# - Full DB round-trip: register → verify in DB
# - Re-register preserves trust_score
# - Embedding stored as 1536-dim vector

# Contract: response schema shape
poetry run pytest tests/contracts/test_agent_schemas.py -v
# - 201 response matches AgentRegisterResponse shape
# - ResponseEnvelope always contains "data" and "meta" with "request_id"
```
