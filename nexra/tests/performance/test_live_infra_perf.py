"""Live-infrastructure performance validation (opt-in).

Run only when `NEXRA_RUN_LIVE_PERF=1` is set.

Benchmarks:
- Policy evaluation (`PolicyEngine.evaluate`) with real Postgres + Redis cache path
  Sample size: 200 evaluations, target p99 < 80ms.
- Discovery query orchestration (`DiscoveryService.discover`) with real Postgres
  vector query path and fake embedding API.
  Sample size: 50 discoveries, target p99 < 350ms.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api.schemas.capabilities import DiscoverRequest
from models import Base
from models.agent import Agent
from models.organization import Organization
from models.policy import Policy
from services.discovery_service import DiscoveryService
from services.policy_engine import DelegationContext, PolicyEngine


class _FakeOpenAI:
    class _Embeddings:
        async def create(self, input: str, model: str):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.01] * 1536)])

    def __init__(self) -> None:
        self.embeddings = self._Embeddings()


@pytest_asyncio.fixture
async def live_db_session() -> AsyncSession:
    if os.getenv("NEXRA_RUN_LIVE_PERF") != "1":
        pytest.skip("Set NEXRA_RUN_LIVE_PERF=1 to run live infra perf tests")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://nexra:nexra@localhost:5432/nexra_test",
    )
    engine = create_async_engine(database_url, echo=False, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_policy_eval_p99_under_80ms(live_db_session: AsyncSession) -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url, decode_responses=True)

    org_id = uuid.uuid4()
    live_db_session.add(
        Policy(
            id=uuid.uuid4(),
            org_id=org_id,
            name="allow-all",
            priority=1,
            rule_yaml="allow: {}\nconditions: []\non_violation: block_and_alert\n",
            version=1,
            enabled=True,
        )
    )
    await live_db_session.commit()

    try:
        await redis_client.delete(f"policies:{org_id}")
        engine = PolicyEngine(redis_client=redis_client, db=live_db_session)
        ctx = DelegationContext(
            caller_agent_id="caller",
            caller_agent_type="research",
            caller_org_id=str(org_id),
            caller_budget_remaining_usd=50.0,
            callee_agent_id="callee",
            callee_agent_type="analysis",
            callee_trust_score=0.9,
            callee_org_id=str(org_id),
            capability_type="analysis",
            context_scope=["deal_metadata"],
            estimated_cost_usd=0.1,
            budget_cap_usd=1.0,
            time_of_day="12:00",
            delegation_depth=0,
            timestamp=datetime.now(UTC),
        )

        samples_ms: list[float] = []
        for _ in range(200):
            started = time.perf_counter()
            decision = await engine.evaluate(ctx, str(org_id))
            samples_ms.append((time.perf_counter() - started) * 1000)
            assert decision.decision == "allow"

        p99 = sorted(samples_ms)[int(0.99 * len(samples_ms)) - 1]
        assert p99 < 80.0
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_live_discovery_p99_under_350ms(live_db_session: AsyncSession) -> None:
    org_id = uuid.uuid4()
    live_db_session.add(
        Organization(
            id=org_id,
            name="Perf Org",
            api_key_hash="hash",
            api_key_prefix="nx_live_perf0001",
            plan="growth",
            jwt_secret_enc="a" * 64,
            delegation_count=0,
        )
    )
    live_db_session.add(
        Agent(
            org_id=org_id,
            agent_id="perf-agent",
            name="Perf Agent",
            description="Performance discovery test agent",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            webhook_url="https://example.com/perf",
            webhook_secret="a" * 32,
            pricing={"per_call_usd": 0.1},
            sla={"p99_latency_ms": 1200, "availability": 0.99},
            is_public=False,
            trust_score=Decimal("0.950"),
            status="active",
            embedding=[0.01] * 1536,
        )
    )
    await live_db_session.commit()

    service = DiscoveryService(live_db_session, _FakeOpenAI())

    samples_ms: list[float] = []
    for _ in range(50):
        started = time.perf_counter()
        matches, total, filtered = await service.discover(
            caller_org_id=str(org_id),
            request=DiscoverRequest(query="analysis", limit=5),
        )
        samples_ms.append((time.perf_counter() - started) * 1000)
        assert matches
        assert total >= filtered

    p99 = sorted(samples_ms)[int(0.99 * len(samples_ms)) - 1]
    assert p99 < 350.0
