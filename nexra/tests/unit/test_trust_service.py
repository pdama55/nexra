"""Unit tests for services.trust_service formula and transitions."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trust_service import TrustService


class _FakeAgent:
    def __init__(
        self,
        trust_score: float = 1.0,
        status: str = "active",
        sla: dict | None = None,
        delegation_count: int = 0,
    ) -> None:
        self.trust_score = Decimal(str(trust_score))
        self.status = status
        self.sla = sla or {"p99_latency_ms": 5000, "availability": 0.99}
        self.delegation_count = delegation_count


def _make_agent(
    trust_score: float = 1.0,
    status: str = "active",
    delegation_count: int = 0,
) -> _FakeAgent:
    return _FakeAgent(
        trust_score=trust_score,
        status=status,
        delegation_count=delegation_count,
    )


def _make_delegation(
    status: str = "completed",
    latency_ms: int | None = 1000,
    actual_cost: float = 0.10,
    estimated_cost: float = 0.10,
    policy_decision: str | None = "allow",
    created_at: datetime | None = None,
) -> MagicMock:
    d = MagicMock()
    d.status = status
    d.latency_ms = latency_ms
    d.actual_cost_usd = Decimal(str(actual_cost))
    d.estimated_cost_usd = Decimal(str(estimated_cost))
    d.created_at = created_at or datetime.now(timezone.utc)
    d.id = uuid.uuid4()
    d.policy_decision = policy_decision
    return d


class TestTrustServiceFormula:
    def test_weights_sum_to_1(self) -> None:
        total = (
            TrustService.WEIGHT_SUCCESS_RATE
            + TrustService.WEIGHT_SLA_COMPLIANCE
            + TrustService.WEIGHT_COST_ACCURACY
            + TrustService.WEIGHT_POLICY_VIOLATIONS_INVERSE
        )
        assert total == pytest.approx(1.0)

    def test_weight_values_match_tdd(self) -> None:
        assert TrustService.WEIGHT_SUCCESS_RATE == 0.40
        assert TrustService.WEIGHT_SLA_COMPLIANCE == 0.30
        assert TrustService.WEIGHT_COST_ACCURACY == 0.20
        assert TrustService.WEIGHT_POLICY_VIOLATIONS_INVERSE == 0.10


class TestTrustServiceTransitions:
    @pytest.mark.asyncio
    async def test_probationary_promotes_to_active(self) -> None:
        agent = _make_agent(trust_score=0.72, status="probationary", delegation_count=10)
        delegations = [_make_delegation(status="completed") for _ in range(12)]

        db = AsyncMock()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent
        deleg_result = MagicMock()
        deleg_scalars = MagicMock()
        deleg_scalars.all.return_value = delegations
        deleg_result.scalars.return_value = deleg_scalars

        db.execute = AsyncMock(side_effect=[agent_result, deleg_result])
        db.add = MagicMock()
        db.commit = AsyncMock()

        service = TrustService(db)
        current = _make_delegation(status="completed")
        score = await service.update_after_delegation("agent-1", str(uuid.uuid4()), current)

        assert score >= 0.70
        assert agent.status == "active"

    @pytest.mark.asyncio
    async def test_active_demotes_to_probationary_below_point_40(self) -> None:
        agent = _make_agent(trust_score=0.55, status="active", delegation_count=25)
        old_time = datetime.now(timezone.utc) - timedelta(days=1)
        delegations = [
            _make_delegation(status="failed", latency_ms=None, policy_decision="block", created_at=old_time)
            for _ in range(8)
        ] + [
            _make_delegation(
                status="completed",
                latency_ms=12_000,
                actual_cost=4.0,
                estimated_cost=0.10,
                policy_decision="allow",
                created_at=old_time,
            )
            for _ in range(2)
        ]

        db = AsyncMock()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent
        deleg_result = MagicMock()
        deleg_scalars = MagicMock()
        deleg_scalars.all.return_value = delegations
        deleg_result.scalars.return_value = deleg_scalars
        db.execute = AsyncMock(side_effect=[agent_result, deleg_result])
        db.add = MagicMock()
        db.commit = AsyncMock()

        service = TrustService(db)
        current = _make_delegation(status="failed", policy_decision="block")
        score = await service.update_after_delegation("agent-1", str(uuid.uuid4()), current)

        assert score < 0.40
        assert agent.status == "probationary"

    @pytest.mark.asyncio
    async def test_quarantine_below_point_20(self) -> None:
        agent = _make_agent(trust_score=0.30, status="active", delegation_count=30)
        old_time = datetime.now(timezone.utc) - timedelta(days=1)
        delegations = [
            _make_delegation(status="blocked", latency_ms=None, policy_decision="block", created_at=old_time)
            for _ in range(20)
        ]

        db = AsyncMock()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent
        deleg_result = MagicMock()
        deleg_scalars = MagicMock()
        deleg_scalars.all.return_value = delegations
        deleg_result.scalars.return_value = deleg_scalars
        db.execute = AsyncMock(side_effect=[agent_result, deleg_result])
        db.add = MagicMock()
        db.commit = AsyncMock()

        service = TrustService(db)
        current = _make_delegation(
            status="failed",
            actual_cost=10.0,
            estimated_cost=0.1,
            policy_decision="block",
        )
        score = await service.update_after_delegation("agent-1", str(uuid.uuid4()), current)

        assert score < 0.20
        assert agent.status == "quarantined"

    @pytest.mark.asyncio
    async def test_agent_not_found_returns_default(self) -> None:
        db = AsyncMock()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=agent_result)

        service = TrustService(db)
        current = _make_delegation()
        score = await service.update_after_delegation("missing", str(uuid.uuid4()), current)

        assert score == 1.0
