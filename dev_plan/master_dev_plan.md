# Nexra MVP — Master Development Plan

> **Source of truth:** `Nexra_TDD.md` (3562 lines, 25 sections) + `Nexra_PRD.md` + `AGENTS.md`
> **Coding protocol:** Follow `AGENTS.md` — strict TypeScript/Python engineering protocol with verification, type safety, and mandatory checklist-driven development.
> **Target stack:** Python 3.12, FastAPI 0.115+, PostgreSQL 16 + pgvector, Redis 7, Celery 5, OpenAI `text-embedding-3-small`, Stripe Metering API, Railway (MVP), Docker Compose (local dev).

---

## How to Use This Plan

Each phase maps to a `phase_XX_<name>.md` file in this directory. Every phase file contains:
1. **Objective** — what this phase delivers
2. **Claude Code Prompt** — exact prompt to paste into Claude Code
3. **Guardrails** — constraints Claude Code must not violate
4. **Acceptance Criteria** — how you verify the phase is done before moving on
5. **Test Cases** — specific tests to run (commands included)

> ⚠️ **Never start a phase until all acceptance criteria from the previous phase are GREEN.**

---

## Phase Order & TDD Mapping

| # | Phase File | TDD Sections | 48h Block | Priority |
|---|-----------|--------------|-----------|----------|
| 01 | [phase_01_scaffold.md](./phase_01_scaffold.md) | §2, §19, §21.3 | Block 1 (0-3h) | P0 |
| 02 | [phase_02_data_models.md](./phase_02_data_models.md) | §3, §22 Block 2 | Block 2 (3-6h) | P0 |
| 03 | [phase_03_auth_middleware.md](./phase_03_auth_middleware.md) | §4.1-4.3, §6.1 | Block 3 (6-9h) | P0 |
| 04 | [phase_04_agent_register.md](./phase_04_agent_register.md) | §5.2, §6.3, §9.2 | Block 4 (9-13h) | P0 |
| 05 | [phase_05_discovery.md](./phase_05_discovery.md) | §9, §6.4 | Block 5 (13-17h) | P0 |
| 06 | [phase_06_policy_engine.md](./phase_06_policy_engine.md) | §7, §6 (policy CRUD) | Block 6 (17-22h) | P0 |
| 07 | [phase_07_delegation_initiate.md](./phase_07_delegation_initiate.md) | §8.1 steps 1-9, §6.5 | Block 7 (22-27h) | P0 |
| 08 | [phase_08_webhook_complete.md](./phase_08_webhook_complete.md) | §4.4-4.5, §12, §6.6 | Block 8 (27-31h) | P0 |
| 09 | [phase_09_settle_trust_audit.md](./phase_09_settle_trust_audit.md) | §10, §11, §13 | Block 9 (31-35h) | P0 |
| 10 | [phase_10_billing_sdk.md](./phase_10_billing_sdk.md) | §16, §17 | Block 10 (35-39h) | P0 |
| 11 | [phase_11_demo_scenario.md](./phase_11_demo_scenario.md) | §22 Block 11 | Block 11 (39-43h) | P1 |
| 12 | [phase_12_deploy.md](./phase_12_deploy.md) | §21.1-21.2 | Block 12 (43-48h) | P0 |

---

## Repository Structure (from TDD §2)

```
nexra/
├── api/
│   ├── main.py               # App factory, middleware, router mounting
│   ├── dependencies.py       # FastAPI Depends() — auth, db session, redis
│   ├── middleware/
│   │   ├── auth.py           # API key bcrypt verify
│   │   ├── rate_limit.py     # Redis sliding window
│   │   └── logging.py        # Structured JSON request logging
│   ├── routers/
│   │   ├── agents.py         # /agents/register, /agents/registry, /agents/{id}/*
│   │   ├── capabilities.py   # /capabilities/discover
│   │   ├── delegations.py    # /delegate, /delegations/{id}/*
│   │   ├── policies.py       # /policies CRUD
│   │   ├── audit.py          # /audit/log
│   │   ├── analytics.py      # /analytics/usage, /spend/summary
│   │   └── health.py         # /health
│   └── schemas/              # Pydantic v2 request/response models
├── services/
│   ├── agent_service.py
│   ├── discovery_service.py
│   ├── policy_engine.py
│   ├── delegation_service.py
│   ├── trust_service.py
│   ├── budget_service.py
│   ├── audit_service.py
│   ├── webhook_service.py
│   ├── billing_service.py
│   └── anomaly_service.py
├── models/                   # SQLAlchemy ORM models
│   ├── organization.py
│   ├── agent.py
│   ├── policy.py
│   ├── delegation.py
│   ├── audit_log.py
│   ├── agent_budget.py
│   └── trust_score_event.py
├── db/
│   ├── session.py            # AsyncSession factory
│   └── migrations/           # Alembic migrations
├── workers/
│   ├── celery_app.py
│   ├── webhook_worker.py
│   └── anomaly_worker.py
├── core/
│   ├── config.py             # Pydantic Settings (pydantic-settings)
│   ├── crypto.py             # bcrypt, AES-GCM, HMAC
│   ├── errors.py             # NexraError + FastAPI exception handler
│   └── jwt.py               # Delegation JWT issue/verify
├── sdk/
│   └── nexra/
│       ├── client.py         # NexraClient
│       └── adapters/
│           ├── langgraph.py
│           ├── crewai.py
│           ├── bedrock.py
│           └── a2a.py
├── tests/
│   ├── unit/                 # No DB/Redis/HTTP — pure service logic
│   ├── integration/          # Real Postgres + Redis, mock OpenAI/Stripe
│   ├── e2e/                  # Full app via httpx.AsyncClient
│   └── contracts/            # Pydantic schema contract tests
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
├── infra/
│   └── railway.toml
├── pyproject.toml
├── .env.example
└── alembic.ini
```

---

## Database Tables (from TDD §3)

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `organizations` | `id UUID PK`, `api_key_hash`, `api_key_prefix` (first 16 chars), `jwt_secret_enc` | One row per tenant |
| `agents` | `id UUID PK`, `org_id FK`, `agent_id` (human slug), `status`, `trust_score DECIMAL(5,3)`, `embedding VECTOR(1536)` | pgvector field |
| `policies` | `id UUID PK`, `org_id FK`, `rule_yaml TEXT`, `version INT`, `enabled BOOL` | YAML stored as text |
| `delegations` | `id UUID PK`, `caller_*`, `callee_*`, `status`, `policy_decision`, `task JSONB`, `task_hash` | Central workflow table |
| `audit_log` | `id UUID PK`, `org_id`, `event_type`, `details JSONB` | **Append-only** — DB trigger blocks UPDATE/DELETE |
| `agent_budgets` | `agent_id`, `org_id`, `period DATE`, `period_type`, `cap_usd`, `spent_usd` | Daily + monthly rows |
| `trust_score_events` | `id UUID PK`, `agent_id`, `delegation_id FK`, `score_before`, `score_after`, `components JSONB` | Audit trail for trust |
| `policy_versions` | Implicit via `version INT` on `policies` table | Bump on every PUT |

---

## Service Dependencies (from TDD §5.1)

```
DelegationService
  ├── PolicyEngine        (pure Python, no external calls)
  ├── BudgetService       (Postgres SELECT FOR UPDATE)
  ├── WebhookService      (HTTPX outbound + Celery async)
  ├── AuditService        (Postgres append-only)
  ├── TrustService        (Postgres rolling 30-day stats)
  └── BillingService      (Stripe Metering API)

AgentService
  └── OpenAI              (text-embedding-3-small)

DiscoveryService
  └── Postgres pgvector   (cosine similarity + composite score)
```

---

## Non-Negotiable Guardrails (applied to every phase)

1. **`AGENTS.md` protocol** — verification before execution, checklist-driven, type-annotated.
2. **All models use `UUID` PKs** via `gen_random_uuid()`. Never `SERIAL/BIGINT`.
3. **All timestamps are `TIMESTAMPTZ`** (`datetime.now(timezone.utc)` in Python).
4. **`audit_log` is append-only** — the DB trigger is created in Phase 02 and must never be removed.
5. **`SELECT FOR UPDATE`** on `agent_budgets` to prevent race conditions.
6. **bcrypt on API key verification only after rate-limit check** (rate limit first = protect CPU).
7. **Delegation JWT is single-use** — `jti` marked in Redis immediately on verify.
8. **Webhook secrets stored as plaintext per agent**; org JWT secrets are AES-GCM encrypted.
9. **No `UPDATE` or `DELETE` ever called on `audit_log`** — not even in tests.
10. **All service classes have zero FastAPI imports** — pure Python, tested independently.
11. **HTTPS-only webhook URLs** — `webhook_url` must start with `https://`.
12. **Default-deny policy** — if no policies exist for an org, all delegations are blocked.
13. **Policy caching** — Redis TTL 60s per org to reduce DB hits in policy hot path.
14. **All Pydantic models are v2** — use `model_dump()`, not `.dict()`.

---

## P0 Endpoints (MVP must-have)

| Method | Path | Phase |
|--------|------|-------|
| POST | `/agents/register` | 04 |
| GET | `/agents/registry` | 04 |
| GET | `/agents/{id}` | 04 |
| POST | `/capabilities/discover` | 05 |
| POST | `/delegate` | 07-08 |
| GET | `/delegations/{id}` | 07 |
| POST | `/delegations/{id}/complete` | 08 |
| POST | `/policies` | 06 |
| GET | `/policies` | 06 |
| GET | `/policies/{id}` | 06 |
| GET | `/audit/log` | 09 |
| GET | `/spend/summary` | 09 |
| GET | `/health` | 03 |

---

## Performance Targets (from TDD §24)

| Endpoint | P99 Target | Timeout |
|----------|-----------|---------|
| `POST /capabilities/discover` | < 200ms | 5s |
| `POST /delegate` (pre-webhook) | < 150ms | N/A |
| `POST /agents/register` | < 2000ms | 10s |
| Policy engine evaluation | < 20ms | 100ms |
| Auth middleware (bcrypt) | < 80ms | 1s |

---

## Key Error Codes to Implement (TDD §23.2)

| HTTP | Code | Phase |
|------|------|-------|
| 400 | `INVALID_SCHEMA` | 04 |
| 400 | `INVALID_WEBHOOK_URL` | 04 |
| 400 | `MAX_DEPTH_EXCEEDED` | 07 |
| 401 | `UNAUTHORIZED` | 03 |
| 401 | `INVALID_DELEGATION_TOKEN` | 08 |
| 402 | `BUDGET_EXCEEDED` | 07 |
| 403 | `POLICY_BLOCKED` | 07 |
| 403 | `AGENT_QUARANTINED` | 07 |
| 404 | `AGENT_NOT_FOUND` | 07 |
| 408 | `DELEGATION_TIMEOUT` | 08 |
| 422 | `SCHEMA_VALIDATION_FAILED` | 07 |
| 429 | `RATE_LIMIT_EXCEEDED` | 03 |

---

## Environment Variables Required (TDD §19.1)

```bash
DATABASE_URL=postgresql+asyncpg://nexra:nexra@localhost:5432/nexra
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_DELEGATION_METER_ID=mtr_...
SECRET_KEY_ENCRYPTION_KEY=<32 hex bytes>
SENTRY_DSN=https://...@sentry.io/...   # prod only
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Testing Pyramid (from TDD §20.1)

| Layer | Location | Dependencies | Coverage Target |
|-------|----------|-------------|-----------------|
| Unit | `tests/unit/` | No DB, no Redis, no HTTP | >90% service layer |
| Integration | `tests/integration/` | Real Postgres + Redis; mock OpenAI + Stripe | Full DB round-trips, FK constraints, audit trigger |
| E2E | `tests/e2e/` | Full app + 2 real agent fixtures | Complete delegation flow |
| Contract | `tests/contracts/` | Pydantic schema shapes | Every endpoint request/response |

Full test matrix is in `master_test_plan.md`.

---

## Completion Checklist (before shipping)

- [ ] All 23 TDD test cases (T-001 through T-023) passing
- [ ] `/health` returns `200 OK` with component status
- [ ] Full delegation round-trip (register → discover → delegate → complete → settle) works
- [ ] Policy switch from `allow` to `block` takes effect within 60 seconds (Redis TTL)
- [ ] Audit log UPDATE/DELETE trigger verified (T-013, T-014)
- [ ] Stripe Meter event fires after delegation (Stripe Dashboard test mode)
- [ ] Railway deploy green with `/health` check
- [ ] `nexra-py` SDK `hire()` works end-to-end
- [ ] Demo: two agents coordinate with no hardcoded connections
