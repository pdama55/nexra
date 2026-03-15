# Nexra — Master Development Order

> **Purpose**: This document defines the exact sequence in which Nexra is built, the dependency graph between phases, and the mapping from every TDD section to its implementation file. A coding agent reads this file first, then executes the numbered phase files in order.

---

## 1. Development Phases — Execution Sequence

Each phase produces a working, testable increment. No phase may begin until every item in its **Depends On** column is complete.

| Phase | File | Scope | TDD Sections | Depends On | 48h Block |
|-------|------|-------|-------------|------------|-----------|
| 1 | `01_MVP_PHASE_1_SCAFFOLD.md` | Project scaffold, Docker Compose, PostgreSQL + pgvector + Redis, Alembic migrations, all ORM models | §1, §2, §3 | None | 0-6 h |
| 2 | `02_MVP_PHASE_2_AUTH_SECURITY.md` | API key generation/verification, bcrypt, auth middleware, rate limiting, /health endpoint | §4, §19 (partial) | Phase 1 | 6-9 h |
| 3 | `03_MVP_PHASE_3_AGENT_REGISTRY.md` | POST /agents/register, GET /agents/registry, GET /agents/{id}, OpenAI embedding, idempotent upsert | §5.2, §6.3 | Phase 2 | 9-13 h |
| 4 | `04_MVP_PHASE_4_DISCOVERY_ENGINE.md` | POST /capabilities/discover, pgvector cosine similarity, composite scoring, hard filters | §6.4, §9 | Phase 3 | 13-17 h |
| 5 | `05_MVP_PHASE_5_POLICY_ENGINE.md` | PolicyEngine class, YAML parsing, DelegationContext, all operators, default-deny, POST/GET /policies | §7, §6 (policies endpoints) | Phase 2 | 17-22 h |
| 6 | `06_MVP_PHASE_6_DELEGATION_FLOW.md` | POST /delegate (13-step flow), delegation JWT, HMAC webhook signing, POST /delegations/{id}/complete, GET /delegations/{id} | §8, §12, §4.4, §4.5, §6.5, §6.6 | Phases 3, 4, 5 | 22-31 h |
| 7 | `07_MVP_PHASE_7_BUDGET_AUDIT.md` | BudgetService (check_and_reserve, settle), AuditService (append-only), trust score update stub, spend summary endpoint | §11, §13, §10 (stub), §6 (spend/summary) | Phase 6 | 31-35 h |
| 8 | `08_MVP_PHASE_8_BILLING_SDK.md` | Stripe Metering API integration, BillingService, nexra-py SDK (NexraClient), README quickstart | §16, §17.1 | Phase 7 | 35-39 h |
| 9 | `09_MVP_PHASE_9_DEPLOY_DEMO.md` | Railway deploy, Docker production build, demo agents (sales + research), 90s demo video script, landing page, launch checklist | §21, §22 | Phase 8 | 39-48 h |
| 10 | `10_P1_CIRCUIT_BREAKERS_TRUST.md` | Full trust score system, automatic status transitions, circuit breaker service, anomaly detection (Celery beat) | §10, §14 | Phase 9 (MVP complete) | Post-MVP |
| 11 | `11_P1_HITL_ASYNC_DELEGATION.md` | Human-in-the-loop gates, approval/reject endpoints, async delegation (Celery webhook worker), callback_url support | §15, §12.2, §8 (async path) | Phase 10 | Post-MVP |
| 12 | `12_P1_DASHBOARD_SIEM_ADAPTERS.md` | Governance dashboard API endpoints, SIEM export worker, LangGraph adapter, CrewAI adapter, Bedrock adapter, A2A registration | §17 (nexra-ts), §18, §25.1 (dashboard/SIEM) | Phase 11 | Post-MVP |
| 13 | `13_P2_MARKETPLACE_COMPLIANCE.md` | Cross-org marketplace, Stripe Connect payouts, compliance report exports (SOC 2/GDPR/HIPAA), schema validation enforcement, policy version control | §25.1, §25.2 | Phase 12 | Post-MVP |

---

## 2. Dependency Graph

```
Phase 1 (Scaffold)
    │
    ▼
Phase 2 (Auth + Security)
    │
    ├──────────────────┐
    ▼                  ▼
Phase 3 (Registry)   Phase 5 (Policy Engine)
    │                  │
    ▼                  │
Phase 4 (Discovery)   │
    │                  │
    └──────┬───────────┘
           ▼
    Phase 6 (Delegation Flow)
           │
           ▼
    Phase 7 (Budget + Audit)
           │
           ▼
    Phase 8 (Billing + SDK)
           │
           ▼
    Phase 9 (Deploy + Demo)
           │
           ▼
    ═══ MVP COMPLETE ═══
           │
           ▼
    Phase 10 (Circuit Breakers + Trust)
           │
           ▼
    Phase 11 (HiTL + Async Delegation)
           │
           ▼
    Phase 12 (Dashboard + SIEM + Adapters)
           │
           ▼
    Phase 13 (Marketplace + Compliance)
```

> **Note**: Phases 3 and 5 can be developed in parallel after Phase 2 is complete. Phase 6 requires both to be finished.

---

## 3. TDD Section → Implementation File Mapping

Every section of the TDD is covered by exactly one implementation file. No section is skipped.

| TDD Section | Title | Implementation File |
|-------------|-------|-------------------|
| §1 | Architecture Overview & Technology Stack | `01_MVP_PHASE_1_SCAFFOLD.md` |
| §2 | Repository Structure & Project Setup | `01_MVP_PHASE_1_SCAFFOLD.md` |
| §3 | Database Schema — PostgreSQL 16 + pgvector | `01_MVP_PHASE_1_SCAFFOLD.md` |
| §4 | Authentication & Security Model | `02_MVP_PHASE_2_AUTH_SECURITY.md` |
| §5 | Core Services — Internal Module Design | Split across Phases 3-8 (each service in its relevant phase) |
| §6 | API Layer — Endpoint Specifications | Split across Phases 3-8 (each endpoint in its relevant phase) |
| §7 | Policy Engine — Design & Implementation | `05_MVP_PHASE_5_POLICY_ENGINE.md` |
| §8 | Delegation Flow — 13-Step Technical Walkthrough | `06_MVP_PHASE_6_DELEGATION_FLOW.md` |
| §9 | Discovery Engine — Semantic Search & Ranking | `04_MVP_PHASE_4_DISCOVERY_ENGINE.md` |
| §10 | Trust Score System | `10_P1_CIRCUIT_BREAKERS_TRUST.md` (stub in Phase 7) |
| §11 | Spend Metering & Budget Enforcement | `07_MVP_PHASE_7_BUDGET_AUDIT.md` |
| §12 | Webhook Delivery & HMAC Signing | `06_MVP_PHASE_6_DELEGATION_FLOW.md` (sync), `11_P1_HITL_ASYNC_DELEGATION.md` (async/Celery) |
| §13 | Audit Log — Immutability & Structure | `07_MVP_PHASE_7_BUDGET_AUDIT.md` |
| §14 | Circuit Breakers & Anomaly Detection | `10_P1_CIRCUIT_BREAKERS_TRUST.md` |
| §15 | Human-in-the-Loop (HiTL) Gate | `11_P1_HITL_ASYNC_DELEGATION.md` |
| §16 | Stripe Billing Integration | `08_MVP_PHASE_8_BILLING_SDK.md` |
| §17 | SDK Design — nexra-py & nexra-ts | `08_MVP_PHASE_8_BILLING_SDK.md` (nexra-py), `12_P1_DASHBOARD_SIEM_ADAPTERS.md` (nexra-ts) |
| §18 | Framework Adapters — LangGraph, CrewAI, Bedrock, A2A | `12_P1_DASHBOARD_SIEM_ADAPTERS.md` |
| §19 | Environment Configuration & Secrets | `01_MVP_PHASE_1_SCAFFOLD.md` (config), `02_MVP_PHASE_2_AUTH_SECURITY.md` (secrets) |
| §20 | Testing Strategy — Unit, Integration, E2E | `99_MASTER_TESTING_PLAYBOOK.md` |
| §21 | Deployment — Railway MVP → AWS ECS Production | `09_MVP_PHASE_9_DEPLOY_DEMO.md` |
| §22 | 48-Hour MVP Build Execution Plan | This file (00) + Phases 1-9 |
| §23 | Error Handling & Status Codes | `06_MVP_PHASE_6_DELEGATION_FLOW.md` (NexraError class created in Phase 1) |
| §24 | Performance Targets & SLAs | `04_MVP_PHASE_4_DISCOVERY_ENGINE.md` (discovery P99), `99_MASTER_TESTING_PLAYBOOK.md` (benchmarks) |
| §25 | Future Architecture — v2 & v3 Considerations | `13_P2_MARKETPLACE_COMPLIANCE.md` |

---

## 4. PRD Section → Implementation File Mapping

| PRD Section | Title | Implementation File |
|-------------|-------|-------------------|
| §1 | What Nexra Is | All files (scope boundary reference) |
| §2 | The Problem | All files (motivation reference) |
| §3 | Solution Overview | All files (feature mapping) |
| §4 | Protocol Context (A2A/MCP) | `12_P1_DASHBOARD_SIEM_ADAPTERS.md` |
| §5 | How It Works (6-Step Flow) | `06_MVP_PHASE_6_DELEGATION_FLOW.md` |
| §6 | Full Feature Set | Split by priority: P0 → Phases 1-9, P1 → Phases 10-12, P2 → Phase 13 |
| §7 | API Specifications | Phases 3-8 (each endpoint in its relevant phase) |
| §8 | Data Model | `01_MVP_PHASE_1_SCAFFOLD.md` |
| §9 | Auth & Security | `02_MVP_PHASE_2_AUTH_SECURITY.md` |
| §10 | Technical Architecture | `01_MVP_PHASE_1_SCAFFOLD.md`, `09_MVP_PHASE_9_DEPLOY_DEMO.md` |
| §14 | Pricing | `08_MVP_PHASE_8_BILLING_SDK.md` |
| §16 | 48-Hour MVP | Phases 1-9 |

---

## 5. Files Created Per Phase — Complete Inventory

### Phase 1 — Scaffold
```
nexra/
├── pyproject.toml
├── poetry.lock
├── .env.example
├── .gitignore
├── railway.toml
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
├── api/
│   ├── __init__.py
│   └── main.py                    (app factory stub)
├── models/
│   ├── __init__.py
│   ├── base.py                    (DeclarativeBase, UUID mixin)
│   ├── organization.py
│   ├── agent.py
│   ├── delegation.py
│   ├── policy.py
│   ├── audit_log.py
│   ├── agent_budget.py
│   └── trust_score_event.py
├── db/
│   ├── __init__.py
│   ├── session.py                 (async engine + session factory)
│   └── migrations/
│       ├── env.py
│       └── versions/
│           └── 001_initial_schema.py
├── core/
│   ├── __init__.py
│   ├── config.py                  (Pydantic Settings)
│   └── errors.py                  (NexraError exception class)
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── fixtures/
        ├── __init__.py
        ├── db.py
        └── factories.py
```

### Phase 2 — Auth + Security
```
├── core/
│   ├── crypto.py                  (bcrypt, HMAC, AES-GCM)
│   └── jwt.py                     (delegation JWT issue/verify)
├── api/
│   ├── dependencies.py            (FastAPI Depends: auth, db, redis)
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                (API key verify + agent ownership)
│   │   ├── rate_limit.py          (Redis sliding window)
│   │   └── logging.py             (structured JSON logging)
│   └── routers/
│       ├── health.py              (/health endpoint)
│       └── orgs.py                (POST /v1/orgs/register — bootstrap org creation)
```

### Phase 3 — Agent Registry
```
├── services/
│   ├── __init__.py
│   └── agent_service.py           (register, update_status, list)
├── api/
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py              (pagination, error envelope)
│   │   └── agents.py              (register request/response)
│   └── routers/
│       └── agents.py              (/agents/* endpoints)
```

### Phase 4 — Discovery Engine
```
├── services/
│   └── discovery_service.py       (semantic search + composite scoring)
├── api/
│   ├── schemas/
│   │   └── capabilities.py        (discover request/response)
│   └── routers/
│       └── capabilities.py        (/capabilities/discover)
```

### Phase 5 — Policy Engine
```
├── services/
│   └── policy_engine.py           (YAML eval, operators, default-deny)
├── api/
│   ├── schemas/
│   │   └── policies.py            (policy CRUD request/response)
│   └── routers/
│       └── policies.py            (/policies CRUD)
├── tests/
│   └── unit/
│       └── test_policy_engine.py  (T-001 through T-005)
```

### Phase 6 — Delegation Flow
```
├── services/
│   ├── delegation_service.py      (13-step initiate + complete)
│   └── webhook_service.py         (HMAC signing + HTTPX delivery)
├── api/
│   ├── schemas/
│   │   └── delegations.py         (delegate request/response)
│   └── routers/
│       └── delegations.py         (/delegate, /delegations/*)
```

### Phase 7 — Budget + Audit
```
├── services/
│   ├── budget_service.py          (check_and_reserve, settle)
│   ├── audit_service.py           (append-only writes, query)
│   └── trust_service.py           (stub — full impl in Phase 10)
├── api/
│   └── routers/
│       ├── audit.py               (/audit/log)
│       └── analytics.py           (/spend/summary)
```

### Phase 8 — Billing + SDK
```
├── services/
│   └── billing_service.py         (Stripe metering + Connect)
├── workers/
│   ├── __init__.py
│   ├── celery_app.py              (Celery init, stub beat schedule)
│   └── billing_worker.py          (Stripe event batching)
├── sdk/
│   └── nexra-py/
│       ├── nexra_sdk/             (IMPORTANT: nexra_sdk, not nexra — avoids import collision)
│       │   ├── __init__.py
│       │   ├── client.py          (NexraClient)
│       │   └── types.py           (typed response dataclasses)
│       ├── pyproject.toml         (name = "nexra-sdk")
│       └── README.md
```

### Phase 9 — Deploy + Demo
```
├── demo/
│   ├── sales_agent.py
│   ├── research_agent.py
│   └── README.md
├── (Railway deployment config already in railway.toml)
```

### Phase 10 — Circuit Breakers + Trust (P1)
```
├── services/
│   ├── trust_service.py           (full implementation replacing stub)
│   └── anomaly_service.py         (statistical spend anomaly detection)
├── workers/
│   └── anomaly_worker.py          (hourly Celery beat job)
├── tests/
│   └── unit/
│       ├── test_trust_service.py
│       └── test_circuit_breaker.py
```

### Phase 11 — HiTL + Async Delegation (P1)
```
├── workers/
│   └── webhook_worker.py          (async webhook delivery with retry)
├── api/
│   └── routers/
│       └── delegations.py         (add /approve, /reject endpoints)
```

### Phase 12 — Dashboard + SIEM + Adapters (P1)
```
├── api/
│   └── routers/
│       └── analytics.py           (add /analytics/usage time-series)
├── workers/
│   └── siem_worker.py             (SIEM export streaming)
├── sdk/
│   ├── nexra-py/
│   │   └── nexra/
│   │       └── adapters/
│   │           ├── __init__.py
│   │           ├── langgraph.py
│   │           ├── crewai.py
│   │           └── bedrock.py
│   └── nexra-ts/                  (TypeScript SDK)
│       ├── src/
│       │   ├── index.ts
│       │   ├── client.ts
│       │   └── types.ts
│       ├── tsconfig.json
│       ├── package.json
│       └── README.md
```

### Phase 13 — Marketplace + Compliance (P2)
```
├── services/
│   └── compliance_service.py      (report generation)
├── api/
│   └── routers/
│       └── compliance.py          (/compliance/export)
```

---

## 6. Testing File — Cross-Reference

The `99_MASTER_TESTING_PLAYBOOK.md` file covers:

- Unit test inventory (mapped to test IDs T-001 through T-023 from TDD §20)
- Integration test setup (test DB, test Redis, mock OpenAI/Stripe)
- E2E test scenarios (full delegation round-trip)
- Contract tests (Pydantic schema conformance)
- Performance benchmarks (discovery P99, policy eval P99)
- CI/CD pipeline configuration (GitHub Actions)
- Coverage targets (80%+ line coverage, 90%+ on service layer)

---

## 7. Critical Path

The longest dependency chain determines the minimum build time:

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 ─┐
                   → Phase 5 ────────────┤
                                         ▼
                                   Phase 6 → Phase 7 → Phase 8 → Phase 9
```

**Critical path**: Phases 1 → 2 → 3 → 4 → 6 → 7 → 8 → 9 (8 sequential phases).

Phases 3+5 can run in parallel. If parallelized, the critical path is 7 sequential phases.

---

## 7.1 Cumulative `api/main.py` — Final State After All Phases

Each phase adds routers and middleware to `create_app()`. Here is the complete `api/main.py` after all 13 phases are implemented. This serves as a reference — the agent should build it incrementally per phase, not copy this wholesale.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from core.errors import NexraError
from core.config import get_settings
import uuid


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Nexra API",
        description="The control plane for AI agent networks",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )

    # ── Middleware (order matters: last added = first executed) ──
    from api.middleware.logging import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Exception Handlers ──
    @app.exception_handler(NexraError)
    async def nexra_error_handler(request: Request, exc: NexraError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    # ── Routers ──
    # Phase 2: Health (no prefix — /health at root)
    from api.routers.health import router as health_router
    app.include_router(health_router)

    # Phase 2: Org creation
    from api.routers.orgs import router as orgs_router
    app.include_router(orgs_router, prefix="/v1")

    # Phase 3: Agent registry
    from api.routers.agents import router as agents_router
    app.include_router(agents_router, prefix="/v1")

    # Phase 4: Discovery
    from api.routers.capabilities import router as capabilities_router
    app.include_router(capabilities_router, prefix="/v1")

    # Phase 5: Policies
    from api.routers.policies import router as policies_router
    app.include_router(policies_router, prefix="/v1")

    # Phase 6: Delegations
    from api.routers.delegations import router as delegations_router
    app.include_router(delegations_router, prefix="/v1")

    # Phase 7: Audit + Analytics
    from api.routers.audit import router as audit_router
    from api.routers.analytics import router as analytics_router
    app.include_router(audit_router, prefix="/v1")
    app.include_router(analytics_router, prefix="/v1")

    # Phase 12: Dashboard analytics + SIEM
    # from api.routers.analytics import router as dashboard_router  # extends existing
    # from api.routers.siem import router as siem_router
    # app.include_router(siem_router, prefix="/v1")

    # Phase 13: Compliance + Marketplace
    # from api.routers.compliance import router as compliance_router
    # app.include_router(compliance_router, prefix="/v1")

    # ── Lifecycle ──
    from api.dependencies import close_redis

    @app.on_event("shutdown")
    async def shutdown():
        await close_redis()

    # ── Sentry ──
    if settings.sentry_dsn:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
            environment=settings.environment,
        )

    return app


app = create_app()
```

**Note**: P1/P2 routers (Phases 10-13) are commented out above. Uncomment them as each phase is implemented. The agent should add each router at the end of the corresponding phase.

---

## 7.2 MCP Server Stub (Future — Not in MVP)

Nexra's architecture is designed to be protocol-agnostic. The current MVP exposes a REST API. A future iteration will add an **MCP (Model Context Protocol) server** that wraps the same service layer, allowing LLM tool-use clients to interact with Nexra natively.

**Stub location**: `nexra/mcp/` (create when implementing)

**Scope**: The MCP server is **NOT** part of the 48-hour MVP (Phases 1-9) or P1 (Phases 10-12). It is a P2+ item. However, the service layer is designed to be transport-agnostic, so adding an MCP transport later requires no refactoring of business logic — only a new thin adapter layer that calls the same `AgentService`, `DelegationService`, `DiscoveryService`, etc.

**When to implement**: After Phase 13, or when MCP adoption reaches critical mass in the agent ecosystem.

---

## 7.3 Priority & Scope Notes

### What "P0 / P1 / P2" means in this project

| Priority | Phases | Timeline | Meaning |
|----------|--------|----------|---------|
| **P0** | 1-9 | 48 hours | Core MVP — must ship for product to function |
| **P1** | 10-12 | Post-MVP, weeks 1-2 | Trust, safety, and ecosystem features — required for production readiness |
| **P2** | 13+ | Post-P1 | Marketplace, compliance, MCP — growth and enterprise features |

### Concurrent delegation limit

The delegation flow (Phase 6) processes delegations **sequentially per caller agent** — there is no built-in concurrency limit in the MVP. For production (P1+), the following constraint should be enforced:

- **Per-agent concurrent delegation cap**: Default 10 active (in-flight) delegations per agent.
- **Implementation**: Add a Redis counter (`INCR`/`DECR` with TTL) in `DelegationService.initiate()` before Step 1. If the counter exceeds the cap, return HTTP 429 with error code `CONCURRENT_DELEGATION_LIMIT`.
- **Configuration**: Add `max_concurrent_delegations_per_agent: int = 10` to `core/config.py`.

```python
# In DelegationService.initiate(), before Step 1:
concurrent_key = f"nexra:delegations:active:{caller_agent.agent_id}"
current = await self._redis.incr(concurrent_key)
if current == 1:
    await self._redis.expire(concurrent_key, 3600)  # 1h TTL safety net
if current > settings.max_concurrent_delegations_per_agent:
    await self._redis.decr(concurrent_key)
    raise NexraError(429, "CONCURRENT_DELEGATION_LIMIT",
                     f"Agent has {current - 1} active delegations (max {settings.max_concurrent_delegations_per_agent})")

# In DelegationService._finalize() (called on complete/fail/timeout):
await self._redis.decr(concurrent_key)
```

This is **not** implemented in Phase 6 (MVP). Add it in Phase 10 alongside circuit breakers.

---

## 8. Agent Instructions

When a coding agent receives one of the phase files (01-13):

1. Read the **Prerequisites** section. Verify every prerequisite is met before proceeding.
2. Read the **Guardrails** section. These are hard constraints — violating them is a build failure.
3. Execute the **File-by-File Implementation Guide** in the order listed.
4. After each file is written, run the **Verification Checklist** items that apply.
5. After all files are written, run every **Test Case** listed. All must pass.
6. Do NOT proceed to the next phase file until the current phase's verification checklist is 100% green.

When a coding agent receives the testing playbook (99):

1. This file is executed AFTER Phase 9 (MVP complete) to fill any test gaps.
2. It is also referenced during P1/P2 phases for incremental test additions.
3. CI/CD pipeline setup is done as part of this file.

---

## 9. Definition of Done — MVP (Phases 1-9)

All of the following must be true before MVP is declared complete:

- [ ] `docker compose up` starts API, Postgres (pgvector), and Redis — all healthy
- [ ] `alembic upgrade head` runs without error on a fresh database
- [ ] `/health` returns 200 with component status for DB and Redis
- [ ] POST /agents/register creates an agent with embedding stored in pgvector
- [ ] POST /capabilities/discover returns ranked results under 200ms P99
- [ ] POST /policies creates a YAML-based delegation policy
- [ ] POST /delegate executes the full 13-step flow: policy eval → budget check → webhook delivery → settlement
- [ ] Policy block returns 403 with policy_id
- [ ] Budget exceeded returns 402 with remaining_budget_usd
- [ ] Schema validation failure returns 422
- [ ] Audit log contains entries for every delegation attempt (allow, block, complete, fail)
- [ ] UPDATE/DELETE on audit_log raises database exception
- [ ] Stripe usage event fires after delegation settlement
- [ ] nexra-py SDK `client.hire()` completes a full discover → delegate round-trip
- [ ] Demo: sales_agent.py and research_agent.py coordinate through Nexra with zero hardcoded connections
- [ ] Demo: Policy change from allow to block takes effect immediately
- [ ] Railway deployment is green with /health returning 200
- [ ] All unit tests pass (T-001 through T-023 from TDD §20.2)
- [ ] 80%+ line coverage on service layer

---

## 10. Definition of Done — P1 (Phases 10-12)

- [ ] Trust score updates after every delegation completion
- [ ] Automatic status transitions: probationary → active (score >= 0.70, count >= 10)
- [ ] Automatic quarantine when trust_score < 0.20
- [ ] Circuit breaker trips at >50% failure rate in 10-min window
- [ ] Anomaly detection alerts on 3σ spend deviation (hourly Celery job)
- [ ] HiTL gate triggers on estimated_cost > hil_threshold_usd
- [ ] POST /delegations/{id}/approve resumes a paused delegation
- [ ] Async delegation via callback_url works end-to-end
- [ ] Celery webhook worker retries with exponential backoff (3 attempts)
- [ ] LangGraph adapter: `nexra_tool()` works as a LangGraph ToolNode
- [ ] CrewAI adapter: `NexraTool` works as a CrewAI BaseTool
- [ ] SIEM export streams audit events to a configured webhook

---

## 11. Definition of Done — P2 (Phase 13)

- [ ] Cross-org marketplace: is_public=true agents visible in discovery with include_cross_org=true
- [ ] Stripe Connect: callee org receives 80% of per_call_usd automatically
- [ ] Compliance exports: SOC 2, GDPR, HIPAA report generation from audit_log
- [ ] Schema validation enforced by default on all delegations
- [ ] Policy version control: updates create new versions, old versions preserved in audit entries
