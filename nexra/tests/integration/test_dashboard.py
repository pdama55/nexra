"""Integration tests for dashboard analytics endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.agents import get_agent_trust
from api.routers.analytics import budget_alerts, spend_summary, trust_leaderboard, usage_stats
from api.routers.audit import query_audit_log
from api.routers.delegations import list_delegations
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.agent import Agent
from models.agent_budget import AgentBudget
from models.delegation import Delegation
from models.organization import Organization
from models.trust_score_event import TrustScoreEvent
from services.audit_service import AuditService

TEST_ENC_KEY = "a" * 64


def _req() -> object:
    return type("Req", (), {"state": type("State", (), {"request_id": "req-dashboard"})()})()


async def _create_org(db_session: AsyncSession, name: str) -> Organization:
    _, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_usage_stats_and_trust_leaderboard(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Dashboard Org")

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
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(delegation)

    budget = AgentBudget(
        org_id=org.id,
        agent_id="agent-a",
        period=datetime.now(UTC).date(),
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


@pytest.mark.asyncio
async def test_delegations_query_supports_dashboard_filters(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Delegation Filters Org")

    now = datetime.now(UTC)
    rows = [
        Delegation(
            caller_org_id=org.id,
            caller_agent_id="caller-a",
            callee_org_id=org.id,
            callee_agent_id="callee-a",
            task={"input": {"q": "one"}},
            task_hash="hash-1",
            context_scope=["meta"],
            policy_decision="allow",
            status="completed",
            estimated_cost_usd=Decimal("0.2000"),
            actual_cost_usd=Decimal("0.2300"),
            created_at=now - timedelta(minutes=10),
            completed_at=now - timedelta(minutes=9),
        ),
        Delegation(
            caller_org_id=org.id,
            caller_agent_id="caller-a",
            callee_org_id=org.id,
            callee_agent_id="callee-b",
            task={"input": {"q": "two"}},
            task_hash="hash-2",
            context_scope=["meta"],
            policy_decision="block",
            status="blocked",
            estimated_cost_usd=Decimal("0.1000"),
            actual_cost_usd=Decimal("0.0000"),
            created_at=now - timedelta(minutes=8),
        ),
        Delegation(
            caller_org_id=org.id,
            caller_agent_id="caller-b",
            callee_org_id=org.id,
            callee_agent_id="callee-a",
            task={"input": {"q": "three"}},
            task_hash="hash-3",
            context_scope=["meta"],
            policy_decision="pause",
            status="pending_approval",
            estimated_cost_usd=Decimal("0.5000"),
            actual_cost_usd=Decimal("0.5000"),
            created_at=now - timedelta(minutes=5),
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    response = await list_delegations(
        _req(),
        status="completed",
        caller_agent_id="caller-a",
        callee_agent_id="callee-a",
        policy_decision="allow",
        date_from=now - timedelta(hours=1),
        date_to=now,
        cost_min=0.2,
        cost_max=0.3,
        cursor=None,
        limit=25,
        sort="created_at:desc",
        org=org,
        db=db_session,
    )
    assert len(response["data"]["items"]) == 1
    assert response["data"]["items"][0]["task_hash"] == "hash-1"

    queue_response = await list_delegations(
        _req(),
        status="pending_approval",
        caller_agent_id=None,
        callee_agent_id=None,
        policy_decision=None,
        date_from=None,
        date_to=None,
        cost_min=None,
        cost_max=None,
        cursor=None,
        limit=25,
        sort="approval_deadline:asc",
        org=org,
        db=db_session,
    )
    assert len(queue_response["data"]["items"]) == 1
    assert queue_response["data"]["items"][0]["approval_deadline"] is not None


@pytest.mark.asyncio
async def test_audit_log_query_supports_new_filters(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Audit Filters Org")
    service = AuditService(db_session)

    await service.append(
        org_id=str(org.id),
        event_type="policy_evaluated",
        actor_agent_id="actor-a",
        target_agent_id="target-a",
        details={"policy_id": "policy-1"},
        cost_usd=0.55,
    )
    await service.append(
        org_id=str(org.id),
        event_type="policy_evaluated",
        actor_agent_id="actor-b",
        target_agent_id="target-b",
        details={"policy_id": "policy-2"},
        cost_usd=0.95,
    )

    response = await query_audit_log(
        _req(),
        agent_id=None,
        actor_agent_id="actor-a",
        target_agent_id="target-a",
        event_type="policy_evaluated",
        policy_id="policy-1",
        date_from=None,
        date_to=None,
        cost_min=0.5,
        cost_max=0.6,
        delegation_id=None,
        cursor=None,
        limit=50,
        format="json",
        org=org,
        db=db_session,
    )

    assert len(response["data"]["entries"]) == 1
    entry = response["data"]["entries"][0]
    assert entry["actor_agent_id"] == "actor-a"
    assert entry["target_agent_id"] == "target-a"
    assert entry["details"]["policy_id"] == "policy-1"


@pytest.mark.asyncio
async def test_spend_summary_uses_real_spend_timeseries(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Spend Summary Org")
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Delegation(
                caller_org_id=org.id,
                caller_agent_id="spender",
                callee_org_id=org.id,
                callee_agent_id="callee-1",
                task={"input": {"q": "a"}},
                task_hash="spend-1",
                context_scope=["finance"],
                policy_decision="allow",
                status="completed",
                actual_cost_usd=Decimal("1.2500"),
                created_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=2),
            ),
            Delegation(
                caller_org_id=org.id,
                caller_agent_id="spender",
                callee_org_id=org.id,
                callee_agent_id="callee-2",
                task={"input": {"q": "b"}},
                task_hash="spend-2",
                context_scope=["finance"],
                policy_decision="allow",
                status="completed",
                actual_cost_usd=Decimal("2.0000"),
                created_at=now - timedelta(days=3),
                completed_at=now - timedelta(days=3),
            ),
        ]
    )
    await db_session.commit()

    response = await spend_summary(
        _req(),
        agent_id=None,
        window="last_24h",
        breakdown="timeseries",
        org=org,
        db=db_session,
    )
    timeseries = response["data"]["timeseries"]
    assert len(timeseries) >= 1
    assert abs(sum(item["spend_usd"] for item in timeseries) - 1.25) < 1e-9

    totals_response = await spend_summary(
        _req(),
        agent_id=None,
        window="last_24h",
        breakdown="totals",
        org=org,
        db=db_session,
    )
    assert totals_response["data"]["totals"]["delegation_count"] == 1


@pytest.mark.asyncio
async def test_agent_trust_exposes_stable_breakdown_shape(db_session: AsyncSession) -> None:
    org = await _create_org(db_session, "Trust Shape Org")
    agent = Agent(
        org_id=org.id,
        agent_id="trust-agent",
        name="Trust Agent",
        description="Trust Agent integration test",
        capability_type="analysis",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        webhook_url="https://example.com/t",
        webhook_secret="t" * 32,
        pricing={"per_call_usd": 0.1},
        sla={"p99_latency_ms": 1000, "availability": 0.99},
        is_public=False,
        trust_score=Decimal("0.910"),
        status="active",
    )
    db_session.add(agent)
    await db_session.flush()

    db_session.add_all(
        [
            TrustScoreEvent(
                agent_id=agent.agent_id,
                org_id=org.id,
                score_before=Decimal("0.800"),
                score_after=Decimal("0.860"),
                components={
                    "success_rate": 0.8,
                    "sla_compliance": 0.82,
                    "cost_accuracy": 0.85,
                    "policy_violations_inverse": 0.95,
                    "policy_violations": 1,
                    "delegation_count": 10,
                },
            ),
            TrustScoreEvent(
                agent_id=agent.agent_id,
                org_id=org.id,
                score_before=Decimal("0.860"),
                score_after=Decimal("0.910"),
                components={
                    "success_rate": 0.9,
                    "sla_compliance": 0.91,
                    "cost_accuracy": 0.89,
                    "policy_violations_inverse": 0.98,
                    "policy_violations": 0,
                    "delegation_count": 20,
                },
            ),
        ]
    )
    await db_session.commit()

    response = await get_agent_trust(
        _req(),
        agent_ref=agent.agent_id,
        org=org,
        db=db_session,
    )
    breakdown = response["data"]["breakdown"]
    assert set(
        ["success_rate", "sla_compliance", "cost_accuracy", "policy_violations_inverse", "policy_violations"]
    ).issubset(breakdown.keys())
    assert breakdown["success_rate"] == 0.9
    assert len(response["data"]["timeseries"]) == 2
