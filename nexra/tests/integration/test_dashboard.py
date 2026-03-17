"""Integration tests for dashboard analytics endpoints."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.analytics import budget_alerts, trust_leaderboard, usage_stats
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.agent import Agent
from models.agent_budget import AgentBudget
from models.delegation import Delegation
from models.organization import Organization

TEST_ENC_KEY = "a" * 64


def _req() -> object:
    return type("Req", (), {"state": type("State", (), {"request_id": "req-dashboard"})()})()


@pytest.mark.asyncio
async def test_usage_stats_and_trust_leaderboard(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Dashboard Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()

    agent_a = Agent(
        org_id=org.id,
        agent_id="agent-a",
        name="Agent A",
        description="Agent A dashboard integration test",
        capability_type="analysis",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        webhook_url="https://example.com/a",
        webhook_secret="a" * 32,
        pricing={"per_call_usd": 0.1},
        sla={"p99_latency_ms": 1000, "availability": 0.99},
        is_public=False,
        trust_score=Decimal("0.950"),
        status="active",
    )
    agent_b = Agent(
        org_id=org.id,
        agent_id="agent-b",
        name="Agent B",
        description="Agent B dashboard integration test",
        capability_type="analysis",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        webhook_url="https://example.com/b",
        webhook_secret="b" * 32,
        pricing={"per_call_usd": 0.1},
        sla={"p99_latency_ms": 1000, "availability": 0.99},
        is_public=False,
        trust_score=Decimal("0.700"),
        status="probationary",
    )
    db_session.add_all([agent_a, agent_b])

    delegation = Delegation(
        caller_org_id=org.id,
        caller_agent_id="agent-a",
        callee_org_id=org.id,
        callee_agent_id="agent-b",
        task={"input": {"q": "x"}},
        task_hash="abc123",
        context_scope=["deal_metadata"],
        status="completed",
        budget_cap_usd=Decimal("1.0"),
        estimated_cost_usd=Decimal("0.1"),
        actual_cost_usd=Decimal("0.1"),
        latency_ms=100,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(delegation)

    budget = AgentBudget(
        org_id=org.id,
        agent_id="agent-a",
        period=datetime.now(timezone.utc).date(),
        period_type="daily",
        cap_usd=Decimal("1.0"),
        spent_usd=Decimal("0.9"),
    )
    db_session.add(budget)
    await db_session.commit()

    usage = await usage_stats(_req(), window="last_24h", bucket=None, org=org, db=db_session)
    leaderboard = await trust_leaderboard(_req(), limit=10, org=org, db=db_session)
    alerts = await budget_alerts(_req(), threshold=0.8, org=org, db=db_session)

    assert usage["data"]["total_delegations"] >= 1
    assert leaderboard["data"][0]["agent_id"] == "agent-a"
    assert any(a["agent_id"] == "agent-a" for a in alerts["data"])
