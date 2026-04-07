# 99 — Master Testing Playbook

> **Purpose**: This file is the single source of truth for all testing across Nexra. It maps every test case from every phase file, defines the test infrastructure, provides implementation guides for each test category, configures CI/CD, and sets coverage targets. A coding agent uses this file after Phase 9 (MVP complete) to fill test gaps, and references it during P1/P2 phases for incremental test additions.
>
> **TDD Section**: §20 (Testing Strategy — Unit, Integration, E2E)

---

## 1. Test Pyramid & Coverage Targets

| Layer | Location | Dependencies | Coverage Target | Run Frequency |
|-------|----------|-------------|----------------|---------------|
| **Unit** | `tests/unit/` | None. No DB, no Redis, no HTTP. All external deps mocked. | >90% line coverage on service layer | Every PR, every commit |
| **Integration** | `tests/integration/` | Real Postgres (test schema), real Redis (test DB index). Mock OpenAI + Stripe. | >80% line coverage on data layer | Every PR |
| **E2E** | `tests/e2e/` | Full app via `httpx.AsyncClient(app=app)`. Two agent fixtures with webhook handlers. | Critical paths covered (delegation round-trip, policy enforcement) | On merge to main |
| **Contract** | `tests/contracts/` | None. Validates Pydantic schemas match API spec. | 100% of API endpoints | Every PR |
| **Performance** | `tests/performance/` | Real Postgres + Redis. Benchmarks against P99 targets. | Discovery <200ms P99, Policy eval <20ms P99 | Weekly / on demand |

**Overall target**: 80%+ line coverage across the entire codebase. 90%+ on the service layer.

---

## 2. Test Infrastructure Setup

### 2.1 `tests/conftest.py` — Root Conftest

```python
import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
import redis.asyncio as aioredis

# Force test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test",
)
os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"
os.environ["STRIPE_DELEGATION_METER_ID"] = "mtr_test_fake"
os.environ["SECRET_KEY_ENCRYPTION_KEY"] = "a" * 64  # 32 bytes hex


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test database engine (session-scoped)."""
    from core.config import get_settings
    settings = get_settings()
    eng = create_async_engine(settings.database_url, echo=False)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def setup_database(engine):
    """Create all tables once per test session.

    CRITICAL: pgvector and pgcrypto extensions must be created BEFORE tables,
    because the agents table has a VECTOR(1536) column and UUIDs use gen_random_uuid().
    """
    from models.base import Base
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(engine, setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with SAVEPOINT isolation.

    Each test runs inside a nested transaction (savepoint). When the test calls
    session.commit(), it only commits to the savepoint. After the test, the outer
    transaction is rolled back — so no test data persists between tests.

    This is critical because many services call session.commit() internally.
    Without savepoints, those commits would persist data and cause test interference.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            nested = await session.begin_nested()
            yield session
            if nested.is_active:
                await nested.rollback()


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Per-test Redis client using test DB index."""
    from core.config import get_settings
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def app():
    """Create a test FastAPI app instance."""
    from api.main import create_app
    application = create_app()
    yield application


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

### 2.2 `tests/fixtures/factories.py` — Test Data Factories

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from models.organization import Organization
from models.agent import Agent
from models.delegation import Delegation
from models.policy import Policy
from models.audit_log import AuditLog
from models.agent_budget import AgentBudget


class OrganizationFactory:
    """Factory for creating test Organization records."""

    @staticmethod
    def create(
        name: str = "Test Org",
        api_key_hash: str = "$2b$12$test_hash_placeholder",
        api_key_prefix: str = "nx_live_test1234",
        plan: str = "growth",
        approval_url: str | None = None,
        stripe_id: str | None = "cus_test_123",
        jwt_secret_enc: str = "encrypted_test_secret",
        **overrides,
    ) -> Organization:
        return Organization(
            id=overrides.get("id", uuid.uuid4()),
            name=name,
            api_key_hash=api_key_hash,
            api_key_prefix=api_key_prefix,
            plan=plan,
            approval_url=approval_url,
            stripe_id=stripe_id,
            jwt_secret_enc=jwt_secret_enc,
            **{k: v for k, v in overrides.items() if k not in ("id",)},
        )


class AgentFactory:
    """Factory for creating test Agent records."""

    @staticmethod
    def create(
        org_id: uuid.UUID | None = None,
        agent_id: str = "test-agent",
        name: str = "Test Agent",
        description: str = "A test agent for unit tests",
        capability_type: str = "research",
        status: str = "active",
        trust_score: Decimal = Decimal("0.850"),
        webhook_url: str = "https://test-agent.example.com/webhook",
        webhook_secret: str = "test_webhook_secret",
        is_public: bool = False,
        **overrides,
    ) -> Agent:
        return Agent(
            id=overrides.get("id", uuid.uuid4()),
            org_id=org_id or uuid.uuid4(),
            agent_id=agent_id,
            name=name,
            description=description,
            capability_type=capability_type,
            input_schema=overrides.get("input_schema", {
                "type": "object",
                "required": ["query"],
                "properties": {"query": {"type": "string"}},
            }),
            output_schema=overrides.get("output_schema", {
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"type": "string"}},
            }),
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
            pricing=overrides.get("pricing", {"per_call_usd": 0.10}),
            sla=overrides.get("sla", {"p99_latency_ms": 8000, "availability": 0.99}),
            is_public=is_public,
            trust_score=trust_score,
            status=status,
            delegation_count=overrides.get("delegation_count", 0),
        )


class DelegationFactory:
    """Factory for creating test Delegation records."""

    @staticmethod
    def create(
        caller_org_id: uuid.UUID | None = None,
        caller_agent_id: str = "caller-agent",
        callee_agent_id: str = "callee-agent",
        status: str = "completed",
        task: dict | None = None,
        **overrides,
    ) -> Delegation:
        import hashlib, json
        task = task or {"type": "research", "input": {"query": "test"}}
        task_json = json.dumps(task, sort_keys=True)
        return Delegation(
            id=overrides.get("id", uuid.uuid4()),
            caller_org_id=caller_org_id or uuid.uuid4(),
            caller_agent_id=caller_agent_id,
            callee_agent_id=callee_agent_id,
            task=task,
            task_hash=hashlib.sha256(task_json.encode()).hexdigest(),
            context_scope=overrides.get("context_scope", ["test_data"]),
            status=status,
            budget_cap_usd=overrides.get("budget_cap_usd", Decimal("1.00")),
            estimated_cost_usd=overrides.get("estimated_cost_usd", Decimal("0.10")),
            actual_cost_usd=overrides.get("actual_cost_usd", Decimal("0.08")),
            latency_ms=overrides.get("latency_ms", 1500),
            created_at=overrides.get("created_at", datetime.now(timezone.utc)),
        )


class PolicyFactory:
    """Factory for creating test Policy records."""

    @staticmethod
    def create(
        org_id: uuid.UUID | None = None,
        name: str = "test-policy",
        priority: int = 10,
        rule_yaml: str | None = None,
        **overrides,
    ) -> Policy:
        default_yaml = """
allow:
  caller_type: "*"
  callee_type: "*"
conditions: []
on_violation: block_and_alert
"""
        return Policy(
            id=overrides.get("id", uuid.uuid4()),
            org_id=org_id or uuid.uuid4(),
            name=name,
            priority=priority,
            rule_yaml=rule_yaml or default_yaml,
            version=overrides.get("version", 1),
            enabled=overrides.get("enabled", True),
        )
```

### 2.3 `tests/fixtures/mocks.py` — External Service Mocks

```python
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager


class MockOpenAI:
    """Mock for OpenAI embeddings API."""

    @staticmethod
    def patch():
        """Returns a context manager that patches OpenAI embedding calls."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        return patch("services.agent_service.openai_client", mock_client)


class MockStripe:
    """Mock for Stripe API calls."""

    @staticmethod
    def patch_meter_event():
        return patch(
            "stripe.billing.MeterEvent.create",
            return_value=MagicMock(id="mevt_test_123"),
        )

    @staticmethod
    def patch_transfer():
        return patch(
            "stripe.Transfer.create",
            return_value=MagicMock(id="tr_test_123"),
        )

    @staticmethod
    def patch_all():
        """Patch all Stripe calls at once."""
        return [MockStripe.patch_meter_event(), MockStripe.patch_transfer()]


class MockWebhook:
    """Mock for outbound webhook delivery."""

    @staticmethod
    def success_response(result: dict | None = None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.json.return_value = result or {"result": {"data": "test"}}
        return mock_resp

    @staticmethod
    def timeout_response():
        import httpx
        raise httpx.TimeoutException("Callee timeout")

    @staticmethod
    def rejection_response(status_code: int = 401):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.is_success = False
        return mock_resp
```

---

## 3. Complete Test Inventory

Every test case from every phase file, organized by category. Test IDs are globally unique.

### 3.1 Policy Engine Tests (Phase 5)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-001 | `tests/unit/test_policy_engine.py` | No policies defined → delegation blocked (default deny) | 5 |
| T-002 | `tests/unit/test_policy_engine.py` | Allow policy matches, all conditions pass → allow | 5 |
| T-003 | `tests/unit/test_policy_engine.py` | Allow policy matches, condition fails → block | 5 |
| T-004 | `tests/unit/test_policy_engine.py` | estimated_cost > hil_threshold_usd → pause | 5 |
| T-005 | `tests/unit/test_policy_engine.py` | Context scope NOT subset of allowed → block | 5 |

### 3.2 Budget Tests (Phase 7)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-006 | `tests/unit/test_budget_service.py` | estimated_cost + spent > daily cap → 402 | 7 |
| T-007 | `tests/integration/test_budget_concurrency.py` | Concurrent delegations don't double-spend (SELECT FOR UPDATE) | 7 |

### 3.3 Auth Tests (Phase 2)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-008 | `tests/integration/test_auth.py` | Valid API key + valid X-Agent-ID → 200 | 2 |
| T-009 | `tests/integration/test_auth.py` | Valid API key + wrong org agent_id → 401 | 2 |
| T-010 | `tests/integration/test_auth.py` | Quarantined agent → 403 on any endpoint | 2 |

### 3.4 Delegation JWT Tests (Phase 6)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-011 | `tests/unit/test_jwt.py` | Single-use enforcement — second use → error | 6 |
| T-012 | `tests/unit/test_jwt.py` | Expired token → error | 6 |

### 3.5 Audit Log Tests (Phase 7)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-013 | `tests/integration/test_audit_immutability.py` | INSERT succeeds; UPDATE raises exception | 7 |
| T-014 | `tests/integration/test_audit_immutability.py` | DELETE raises exception | 7 |

### 3.6 Trust Score Tests (Phase 10)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-008 (trust) | `tests/unit/test_trust_service.py` | Score increases after successful delegation | 10 |
| T-009 (trust) | `tests/unit/test_trust_service.py` | Score decreases after failed delegation | 10 |
| T-010 (trust) | `tests/unit/test_trust_service.py` | probationary→active when score≥0.70 and count≥10 | 10 |
| T-011 (trust) | `tests/unit/test_trust_service.py` | Quarantine when score<0.20 | 10 |
| T-TRUST-005 | `tests/unit/test_trust_service.py` | Score clamped to [0, 1] | 10 |
| T-015 | `tests/integration/test_trust_transitions.py` | 10 successes under SLA → trust ~0.95+, status active | 10 |
| T-016 | `tests/integration/test_trust_transitions.py` | trust_score < 0.20 → quarantine | 10 |

### 3.7 Discovery Tests (Phase 4)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-017 | `tests/integration/test_discovery.py` | Quarantined agent excluded from results | 4 |
| T-018 | `tests/integration/test_discovery.py` | Budget filter excludes expensive agents | 4 |

### 3.8 Webhook Tests (Phase 6, 11)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-019 | `tests/integration/test_webhook.py` | HMAC signature mismatch → 401, delegation failed | 6 |
| T-020 | `tests/integration/test_webhook.py` | Callee timeout → 408 response | 6 |

### 3.9 Schema Validation Tests (Phase 6, 13)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-021 | `tests/integration/test_schema_validation.py` | Task payload missing required field → 422 | 6/13 |

### 3.10 Circuit Breaker Tests (Phase 10)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-022 | `tests/unit/test_circuit_breaker.py` | >50% failure rate in 10-min window → tripped | 10 |
| T-CB-001 | `tests/unit/test_circuit_breaker.py` | Breaker trips at >50% failure in 10min | 10 |
| T-CB-002 | `tests/unit/test_circuit_breaker.py` | Breaker not tripped with <5 entries | 10 |
| T-CB-003 | `tests/unit/test_circuit_breaker.py` | Old entries pruned from window | 10 |

### 3.11 Anomaly Detection Tests (Phase 10)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-ANOM-001 | `tests/unit/test_anomaly_service.py` | 3σ deviation flagged | 10 |
| T-ANOM-002 | `tests/unit/test_anomaly_service.py` | Normal spend not flagged | 10 |
| T-ANOM-003 | `tests/unit/test_anomaly_service.py` | <24 hours data → skip | 10 |

### 3.12 HiTL Tests (Phase 11)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-HITL-001 | `tests/unit/test_hitl_service.py` | Policy pause → pending_approval | 11 |
| T-HITL-002 | `tests/unit/test_hitl_service.py` | Notification sent to approval_url | 11 |
| T-HITL-003 | `tests/integration/test_hitl.py` | POST /approve → status pending, audit entry | 11 |
| T-HITL-004 | `tests/integration/test_hitl.py` | Approval resumes delegation flow | 11 |
| T-HITL-005 | `tests/integration/test_hitl.py` | POST /reject → status blocked | 11 |
| T-HITL-006 | `tests/unit/test_hitl_service.py` | Approval after TTL → 410 | 11 |
| T-HITL-007 | `tests/unit/test_hitl_service.py` | Approve non-pending → 409 | 11 |
| T-HITL-008 | `tests/unit/test_hitl_service.py` | Approve nonexistent → 404 | 11 |
| T-HITL-009 | `tests/unit/test_hitl_service.py` | expire_stale() expires token-less delegations | 11 |
| T-HITL-010 | `tests/unit/test_hitl_service.py` | expire_stale() preserves valid tokens | 11 |
| T-HITL-011 | `tests/unit/test_hitl_service.py` | No approval_url → warning logged | 11 |

### 3.13 Async Delegation Tests (Phase 11)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-ASYNC-001 | `tests/integration/test_async_delegation.py` | callback_url → Celery queued, 202 returned | 11 |
| T-ASYNC-002 | `tests/integration/test_async_delegation.py` | Webhook success → callback fired | 11 |
| T-ASYNC-003 | `tests/unit/test_webhook_worker.py` | 3 failures → DLQ entry | 11 |
| T-ASYNC-004 | `tests/unit/test_webhook_worker.py` | 3 failures → delegation failed | 11 |
| T-ASYNC-005 | `tests/unit/test_webhook_worker.py` | 401/403 → no retry | 11 |
| T-ASYNC-006 | `tests/unit/test_webhook_worker.py` | 500 → retry with backoff | 11 |
| T-ASYNC-007 | `tests/integration/test_async_delegation.py` | callback_url=null → sync mode unchanged | 11 |
| T-ASYNC-008 | `tests/unit/test_webhook_worker.py` | DLQ capped at 10,000 | 11 |

### 3.14 Dashboard API Tests (Phase 12)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-DASH-001 | `tests/integration/test_dashboard.py` | Volume endpoint returns hourly buckets | 12 |
| T-DASH-002 | `tests/integration/test_dashboard.py` | Cost breakdown sums correctly | 12 |
| T-DASH-003 | `tests/integration/test_dashboard.py` | Failure rates computed correctly | 12 |
| T-DASH-004 | `tests/integration/test_dashboard.py` | Trust leaderboard sorted descending | 12 |
| T-DASH-005 | `tests/integration/test_dashboard.py` | Budget alerts >80% utilization only | 12 |
| T-DASH-006 | `tests/integration/test_dashboard.py` | Network graph edges match delegation data | 12 |
| T-DASH-007 | `tests/integration/test_dashboard.py` | Org isolation — no cross-org data | 12 |

### 3.15 SIEM Export Tests (Phase 12)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-SIEM-001 | `tests/integration/test_siem.py` | Config saved and retrievable | 12 |
| T-SIEM-002 | `tests/integration/test_siem.py` | Worker exports new events | 12 |
| T-SIEM-003 | `tests/integration/test_siem.py` | Cursor advances after export | 12 |
| T-SIEM-004 | `tests/integration/test_siem.py` | Cursor unchanged on failure | 12 |
| T-SIEM-005 | `tests/integration/test_siem.py` | Event type filtering works | 12 |
| T-SIEM-006 | `tests/unit/test_siem_format.py` | Splunk format correct | 12 |
| T-SIEM-007 | `tests/integration/test_siem.py` | Disabled config → no export | 12 |

### 3.16 Framework Adapter Tests (Phase 12)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-ADAPT-001 | `tests/unit/test_langgraph_adapter.py` | nexra_tool() returns callable | 12 |
| T-ADAPT-002 | `tests/unit/test_langgraph_adapter.py` | Tool executes hire, returns dict | 12 |
| T-ADAPT-003 | `tests/unit/test_crewai_adapter.py` | NexraTool._run() returns string | 12 |
| T-ADAPT-004 | `tests/unit/test_crewai_adapter.py` | Async-to-sync bridge works | 12 |
| T-ADAPT-005 | `tests/unit/test_bedrock_adapter.py` | is_bedrock_endpoint() detects patterns | 12 |
| T-ADAPT-006 | `tests/unit/test_bedrock_adapter.py` | Payload mapping correct | 12 |
| T-ADAPT-007 | `tests/integration/test_a2a_registration.py` | A2A Agent Card → Nexra agent | 12 |
| T-ADAPT-008 | `tests/integration/test_a2a_registration.py` | Missing name → 400 | 12 |

### 3.17 nexra-ts SDK Tests (Phase 12)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-SDK-TS-001 | `sdk/nexra-ts/` (build check) | tsc compiles without errors | 12 |
| T-SDK-TS-002 | `sdk/nexra-ts/tests/` | hire() calls discover then delegate | 12 |
| T-SDK-TS-003 | `sdk/nexra-ts/tests/` | API error → NexraApiError | 12 |

### 3.18 Marketplace Tests (Phase 13)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-MKT-001 | `tests/integration/test_marketplace.py` | Public agent in cross-org discovery | 13 |
| T-MKT-002 | `tests/integration/test_marketplace.py` | Public agent NOT visible without flag | 13 |
| T-MKT-003 | `tests/integration/test_marketplace.py` | Cross-org settlement → 80% to callee | 13 |
| T-MKT-004 | `tests/integration/test_marketplace.py` | No Connect → pending payout | 13 |
| T-MKT-005 | `tests/integration/test_marketplace.py` | Process pending payouts | 13 |
| T-MKT-006 | `tests/integration/test_marketplace.py` | Stripe error → fallback to pending | 13 |

### 3.19 Compliance Report Tests (Phase 13)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-COMP-001 | `tests/unit/test_compliance_service.py` | SOC 2 report has all sections | 13 |
| T-COMP-002 | `tests/unit/test_compliance_service.py` | GDPR report shows context_scope | 13 |
| T-COMP-003 | `tests/unit/test_compliance_service.py` | HIPAA report identifies PHI scopes | 13 |
| T-COMP-004 | `tests/unit/test_compliance_service.py` | CSV export correct format | 13 |
| T-COMP-005 | `tests/integration/test_compliance.py` | Report org isolation | 13 |
| T-COMP-006 | `tests/unit/test_compliance_service.py` | Empty data → empty report | 13 |

### 3.20 Schema Validation Tests (Phase 13)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-SCHEMA-001 | `tests/unit/test_schema_validation.py` | Valid payload passes | 13 |
| T-SCHEMA-002 | `tests/unit/test_schema_validation.py` | Invalid payload → 422 | 13 |
| T-SCHEMA-003 | `tests/unit/test_schema_validation.py` | Passthrough schema skips | 13 |
| T-SCHEMA-004 | `tests/unit/test_schema_validation.py` | Per-org disable skips | 13 |
| T-SCHEMA-005 | `tests/unit/test_schema_validation.py` | Invalid output → 422 | 13 |

### 3.21 Policy Version Control Tests (Phase 13)

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-POLV-001 | `tests/unit/test_policy_version.py` | Update creates new version | 13 |
| T-POLV-002 | `tests/unit/test_policy_version.py` | Old version disabled | 13 |
| T-POLV-003 | `tests/integration/test_policy_version.py` | Version history returns all | 13 |
| T-POLV-004 | `tests/unit/test_policy_version.py` | Audit references correct version | 13 |
| T-POLV-005 | `tests/unit/test_policy_version.py` | Nonexistent policy → 404 | 13 |

### 3.22 E2E Tests

| Test ID | File | Description | Phase |
|---------|------|-------------|-------|
| T-023 | `tests/e2e/test_full_delegation_flow.py` | Full round-trip: register → discover → delegate → complete → settle | 9 |
| T-E2E-002 | `tests/e2e/test_full_delegation_flow.py` | Policy block returns 403 with policy_id | 9 |
| T-E2E-003 | `tests/e2e/test_full_delegation_flow.py` | Budget exceeded returns 402 | 9 |
| T-E2E-004 | `tests/e2e/test_full_delegation_flow.py` | Schema validation failure returns 422 | 9 |
| T-E2E-005 | `tests/e2e/test_hitl_flow.py` | HiTL: pause → approve → complete | 11 |
| T-E2E-006 | `tests/e2e/test_async_flow.py` | Async delegation with callback_url | 11 |
| T-E2E-007 | `tests/e2e/test_cross_org_flow.py` | Cross-org delegation with marketplace settlement | 13 |

---

## 4. E2E Test Implementation — Full Delegation Round-Trip

### 4.1 `tests/e2e/test_full_delegation_flow.py`

```python
"""E2E test: Full delegation round-trip.

This test exercises the complete Nexra flow:
1. Create org + API key
2. Register two agents (caller + callee)
3. Create an allow policy
4. Discover callee agent
5. Delegate task to callee
6. Callee posts result to /complete
7. Verify: delegation completed, audit entries, budget updated, trust score updated

Requires: Postgres (test DB), Redis, mock OpenAI, mock Stripe
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock

from tests.fixtures.mocks import MockOpenAI, MockStripe


@pytest.mark.e2e
class TestFullDelegationFlow:

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, client: AsyncClient, db, redis_client):
        self.client = client
        self.db = db
        self.redis = redis_client
        self.api_key = "nx_live_test_key_12345"
        self.org_id = None
        self.caller_agent_id = "sales-agent-v1"
        self.callee_agent_id = "research-agent-v2"

    async def test_full_round_trip(self):
        """T-023: register → discover → delegate → complete → settle"""

        # Step 1: Create org (direct DB insert for test setup)
        from tests.fixtures.factories import OrganizationFactory
        from core.crypto import hash_api_key
        org = OrganizationFactory.create(
            api_key_hash=hash_api_key(self.api_key),
        )
        self.db.add(org)
        await self.db.flush()
        self.org_id = str(org.id)

        # Step 2: Register caller agent
        with MockOpenAI.patch():
            resp = await self.client.post(
                "/v1/agents/register",
                json={
                    "agent_id": self.caller_agent_id,
                    "name": "Sales Agent",
                    "description": "Handles sales workflows",
                    "capability_type": "execution",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "webhook_url": "https://sales.example.com/webhook",
                    "webhook_secret": "sales_secret",
                    "pricing": {"per_call_usd": 0.10},
                    "sla": {"p99_latency_ms": 5000, "availability": 0.99},
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Agent-ID": self.caller_agent_id,
                },
            )
            assert resp.status_code == 201

        # Step 3: Register callee agent
        with MockOpenAI.patch():
            resp = await self.client.post(
                "/v1/agents/register",
                json={
                    "agent_id": self.callee_agent_id,
                    "name": "Research Agent",
                    "description": "Competitive research for B2B SaaS",
                    "capability_type": "research",
                    "input_schema": {
                        "type": "object",
                        "required": ["company_name"],
                        "properties": {
                            "company_name": {"type": "string"},
                        },
                    },
                    "output_schema": {
                        "type": "object",
                        "required": ["summary"],
                        "properties": {
                            "summary": {"type": "string"},
                        },
                    },
                    "webhook_url": "https://research.example.com/webhook",
                    "webhook_secret": "research_secret",
                    "pricing": {"per_call_usd": 0.15},
                    "sla": {"p99_latency_ms": 8000, "availability": 0.99},
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Agent-ID": self.callee_agent_id,
                },
            )
            assert resp.status_code == 201

        # Step 4: Create allow policy
        resp = await self.client.post(
            "/v1/policies",
            json={
                "name": "sales-to-research",
                "priority": 10,
                "rule_yaml": """
allow:
  caller_type: execution
  callee_type: research
conditions: []
on_violation: block_and_alert
""",
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        assert resp.status_code == 201

        # Step 5: Discover
        with MockOpenAI.patch():
            resp = await self.client.post(
                "/v1/capabilities/discover",
                json={
                    "query": "competitive research B2B SaaS",
                    "capability_type": "research",
                    "limit": 5,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Agent-ID": self.caller_agent_id,
                },
            )
            assert resp.status_code == 200
            matches = resp.json()["data"]["matches"]
            assert len(matches) >= 1
            assert matches[0]["agent_id"] == self.callee_agent_id

        # Step 6: Delegate (mock webhook delivery)
        mock_webhook_resp = MagicMock()
        mock_webhook_resp.status_code = 200
        mock_webhook_resp.is_success = True
        mock_webhook_resp.json.return_value = {
            "result": {
                "summary": "Acme Corp is a mid-market CRM...",
            },
        }

        with patch("services.webhook_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_webhook_resp
            )
            with MockStripe.patch_meter_event():
                resp = await self.client.post(
                    "/v1/delegate",
                    json={
                        "callee_agent_id": self.callee_agent_id,
                        "task": {
                            "type": "research",
                            "input": {"company_name": "Acme Corp"},
                        },
                        "context_scope": ["deal_metadata"],
                        "budget_cap_usd": 0.25,
                        "timeout_ms": 12000,
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Agent-ID": self.caller_agent_id,
                    },
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["status"] == "completed"
                assert data["result"]["summary"] is not None

        # Step 7: Verify audit log entries
        resp = await self.client.get(
            "/v1/audit/log",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        assert resp.status_code == 200
        entries = resp.json()["data"]["entries"]
        event_types = [e["event_type"] for e in entries]
        assert "policy_evaluated" in event_types
        assert "delegation_initiated" in event_types
        assert "delegation_completed" in event_types
```

---

## 5. Performance Benchmarks

### 5.1 `tests/performance/test_discovery_p99.py`

```python
"""Performance benchmark: Discovery P99 latency.

Target: <200ms P99 (TDD §24.1)
Setup: 100 agents with embeddings in pgvector
"""
import pytest
import time
import statistics


@pytest.mark.performance
class TestDiscoveryPerformance:

    async def test_discovery_p99_under_200ms(self, client, db):
        """Benchmark discovery latency with 100 agents."""
        # Setup: insert 100 agents with embeddings
        # (use factory + bulk insert)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            resp = await client.post(
                "/v1/capabilities/discover",
                json={"query": "competitive research", "limit": 5},
                headers={
                    "Authorization": "Bearer test_key",
                    "X-Agent-ID": "bench-agent",
                },
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            assert resp.status_code == 200

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        p50 = statistics.median(latencies)

        print(f"Discovery P50: {p50:.1f}ms, P99: {p99:.1f}ms")
        assert p99 < 200, f"Discovery P99 ({p99:.1f}ms) exceeds 200ms target"


@pytest.mark.performance
class TestPolicyEvalPerformance:

    async def test_policy_eval_p99_under_20ms(self):
        """Benchmark policy evaluation latency (pure Python, no DB)."""
        from services.policy_engine import PolicyEngine

        engine = PolicyEngine()
        # Load 10 policies
        policies = [...]  # Create test policies

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            engine.evaluate(policies, context={...})
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        assert p99 < 20, f"Policy eval P99 ({p99:.1f}ms) exceeds 20ms target"
```

---

## 6. CI/CD Pipeline Configuration

### 6.1 `.github/workflows/convergence-ci.yml` — PR Checks

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy nexra/ --ignore-missing-imports

  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install
      - run: poetry run pytest tests/unit/ -v --tb=short --cov=nexra/services --cov-report=term-missing
      - name: Check coverage
        run: |
          COVERAGE=$(poetry run pytest tests/unit/ --cov=nexra/services --cov-report=term | grep TOTAL | awk '{print $4}' | tr -d '%')
          if [ "$COVERAGE" -lt 90 ]; then
            echo "Service layer coverage ($COVERAGE%) is below 90% target"
            exit 1
          fi

  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install
      - run: poetry run pytest tests/contracts/ -v

  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: nexra_test
          POSTGRES_USER: nexra
          POSTGRES_PASSWORD: nexra
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test
      TEST_REDIS_URL: redis://localhost:6379/1
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install
      - run: poetry run pytest tests/integration/ -v --tb=short

  ts-sdk-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: sdk/nexra-ts
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm install
      - run: npm run build
```

### 6.2 `.github/workflows/release-smoke.yml` — Release Smoke

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: nexra_test
          POSTGRES_USER: nexra
          POSTGRES_PASSWORD: nexra
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test
      TEST_REDIS_URL: redis://localhost:6379/1
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry && poetry install

      - name: Run all tests
        run: |
          poetry run pytest tests/unit/ tests/integration/ tests/e2e/ \
            -v --tb=short \
            --cov=nexra --cov-report=term-missing \
            --cov-fail-under=80

      - name: Deploy to Railway
        if: success()
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: railway up --detach
```

### 6.3 Celery Task Testing Infrastructure

Celery tasks (billing_worker, webhook_worker, anomaly_worker) run in a separate process and use `asyncio.run()` internally. For testing, use Celery's `ALWAYS_EAGER` mode which executes tasks synchronously in the same process:

```python
# tests/conftest.py — add this fixture

@pytest.fixture
def celery_eager(monkeypatch):
    """Run Celery tasks eagerly (synchronously) for testing."""
    from workers.celery_app import celery_app
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield celery_app
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )
```

**Usage in tests**:
```python
class TestBillingWorker:
    async def test_stripe_usage_recorded(self, celery_eager):
        """Test that billing worker records Stripe usage."""
        from workers.billing_worker import record_stripe_usage
        with patch("stripe.billing.MeterEvent.create") as mock_stripe:
            record_stripe_usage("cus_test_123", "del-123", 1700000000)
            mock_stripe.assert_called_once()
```

**For webhook_worker tests** (which use async internally), test the underlying async function directly instead of the Celery task:
```python
class TestWebhookWorker:
    async def test_webhook_delivery_with_retry(self, db):
        """Test async webhook delivery logic directly."""
        from workers.webhook_worker import _deliver_webhook_async
        # Test the async function, not the Celery task wrapper
```

---

## 7. Test Execution Commands

```bash
# Run all unit tests
poetry run pytest tests/unit/ -v

# Run all integration tests (requires Postgres + Redis)
poetry run pytest tests/integration/ -v

# Run all E2E tests
poetry run pytest tests/e2e/ -v

# Run specific test by ID
poetry run pytest -k "T-001" -v

# Run with coverage report
poetry run pytest tests/ --cov=nexra --cov-report=html

# Run performance benchmarks
poetry run pytest tests/performance/ -v -s --benchmark

# Run only MVP tests (Phases 1-9)
poetry run pytest tests/ -m "not p1 and not p2" -v

# Run P1 tests
poetry run pytest tests/ -m "p1" -v

# Run P2 tests
poetry run pytest tests/ -m "p2" -v

# Type check
mypy nexra/ --ignore-missing-imports

# Lint
ruff check .
ruff format --check .
```

---

## 8. Test Markers (pytest.ini)

```ini
[pytest]
asyncio_mode = auto
markers =
    unit: Unit tests (no external deps)
    integration: Integration tests (requires DB + Redis)
    e2e: End-to-end tests (full app)
    contract: API contract tests
    performance: Performance benchmarks
    p1: P1 feature tests (Phases 10-12)
    p2: P2 feature tests (Phase 13)
```

---

## 9. Coverage Report Interpretation

After running `pytest --cov=nexra --cov-report=html`, open `htmlcov/index.html` and verify:

| Module | Target Coverage | Critical Paths |
|--------|----------------|----------------|
| `services/policy_engine.py` | >95% | Default deny, all operators, HiTL threshold |
| `services/delegation_service.py` | >90% | All 13 steps, error paths, async mode |
| `services/trust_service.py` | >90% | Score computation, status transitions, clamping |
| `services/budget_service.py` | >90% | check_and_reserve, settle, concurrent access |
| `services/audit_service.py` | >85% | Append-only writes, all event types |
| `services/discovery_service.py` | >85% | Composite scoring, hard filters, cross-org |
| `services/webhook_service.py` | >85% | HMAC signing, timeout handling, retry |
| `services/hitl_service.py` | >90% | Trigger, approve, reject, expire |
| `services/marketplace_service.py` | >85% | Settlement, pending payouts, Connect transfer |
| `services/compliance_service.py` | >80% | All report types, CSV export |
| `core/crypto.py` | >95% | bcrypt, HMAC, AES-GCM, SHA-256 |
| `core/jwt.py` | >95% | Issue, verify, single-use, expiry |
| `api/middleware/auth.py` | >90% | Key verify, agent ownership, quarantine check |
| `api/middleware/rate_limit.py` | >85% | Sliding window, plan-based limits |

---

## 10. Definition of Done — Testing Complete

All of the following must be true before testing is declared complete:

- [ ] All test IDs from sections 3.1–3.22 have corresponding test implementations
- [ ] `poetry run pytest tests/unit/` passes with 0 failures
- [ ] `poetry run pytest tests/integration/` passes with 0 failures
- [ ] `poetry run pytest tests/e2e/` passes with 0 failures
- [ ] `poetry run pytest tests/contracts/` passes with 0 failures
- [ ] Service layer coverage >90% (`--cov=nexra/services`)
- [ ] Overall coverage >80% (`--cov=nexra`)
- [ ] `mypy nexra/` passes with 0 errors
- [ ] `ruff check .` passes with 0 errors
- [x] CI pipeline (`.github/workflows/convergence-ci.yml`) runs green on a test PR
- [x] Release smoke pipeline (`.github/workflows/release-smoke.yml`) runs green on workflow dispatch
- [ ] Discovery P99 benchmark <200ms with 100 agents
- [ ] Policy eval P99 benchmark <20ms with 10 policies
- [ ] nexra-ts SDK compiles with `tsc` (exit code 0)
