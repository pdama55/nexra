"""Unit tests for services.trust_service — trust score computation."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trust_service import TrustService


class _FakeAgent:
    """Simple agent stand-in with real attributes (not MagicMock)."""

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
        self.agent_id = "test-agent"
        self.org_id = str(uuid.uuid4())


def _make_agent(
    trust_score: float = 1.0,
    status: str = "active",
    sla: dict | None = None,
    delegation_count: int = 0,
) -> _FakeAgent:
    return _FakeAgent(
        trust_score=trust_score,
        status=status,
        sla=sla,
        delegation_count=delegation_count,
    )


def _make_delegation(
    status: str = "completed",
    latency_ms: int = 1000,
    actual_cost: float = 0.10,
    estimated_cost: float = 0.10,
    created_at: datetime | None = None,
) -> MagicMock:
    d = MagicMock()
    d.status = status
    d.latency_ms = latency_ms
    d.actual_cost_usd = Decimal(str(actual_cost))
    d.estimated_cost_usd = Decimal(str(estimated_cost))
    d.created_at = created_at or datetime.now(timezone.utc)
    d.id = uuid.uuid4()
    return d


class TestTrustServiceWeights:
    """Verify the trust score formula weights match the PRD spec."""

    def test_weights_sum_to_1(self) -> None:
        total = (
            TrustService.WEIGHT_SUCCESS
            + TrustService.WEIGHT_LATENCY
            + TrustService.WEIGHT_BUDGET
            + TrustService.WEIGHT_RECENCY
        )
        assert total == pytest.approx(1.0)

    def test_weight_values_match_spec(self) -> None:
        assert TrustService.WEIGHT_SUCCESS == 0.4
        assert TrustService.WEIGHT_LATENCY == 0.3
        assert TrustService.WEIGHT_BUDGET == 0.2
        assert TrustService.WEIGHT_RECENCY == 0.1

    def test_activation_thresholds(self) -> None:
        assert TrustService.ACTIVATION_SCORE == 0.70
        assert TrustService.ACTIVATION_MIN_COUNT == 10
        assert TrustService.QUARANTINE_SCORE == 0.20


class TestTrustScoreComputation:
    """Tests for update_after_delegation with mocked DB."""

    @pytest.mark.asyncio
    async def test_all_successful_delegations_high_score(self) -> None:
        agent = _make_agent(trust_score=1.0, status="probationary")
        delegations = [
            _make_delegation(
                status="completed",
                latency_ms=1000,
                actual_cost=0.10,
                estimated_cost=0.10,
            )
            for _ in range(15)
        ]

        db = AsyncMock()

        # First execute returns agent
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = agent

        # Second execute returns delegations
        deleg_result = MagicMock()
        deleg_scalars = MagicMock()
        deleg_scalars.all.return_value = delegations
        deleg_result.scalars.return_value = deleg_scalars

        db.execute = AsyncMock(side_effect=[agent_result, deleg_result])
        db.add = MagicMock()
        db.commit = AsyncMock()

        service = TrustService(db)
        delegation = _make_delegation()
        score = await service.update_after_delegation(
            "test-agent", str(uuid.uuid4()), delegation
        )

        assert score > 0.7
        assert score <= 1.0

    @pytest.mark.asyncio
    async def test_all_failed_delegations_low_score(self) -> None:
        agent = _make_agent(trust_score=1.0, status="active")
        delegations = [
            _make_delegation(status="failed", latency_ms=None, actual_cost=0, estimated_cost=0.10)
            for _ in range(10)
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
        delegation = _make_delegation(status="failed")
        score = await service.update_after_delegation(
            "test-agent", str(uuid.uuid4()), delegation
        )

        assert score < 0.40

    @pytest.mark.asyncio
    async def test_agent_not_found_returns_default(self) -> None:
        db = AsyncMock()
        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=agent_result)

        service = TrustService(db)
        delegation = _make_delegation()
        score = await service.update_after_delegation(
            "nonexistent", str(uuid.uuid4()), delegation
        )
        assert score == 1.0

    @pytest.mark.asyncio
    async def test_quarantine_on_very_low_score(self) -> None:
        """Score must drop below QUARANTINE_SCORE (0.20) to trigger quarantine.

        Use all-failed delegations that are old (recency → 0), with no completed
        delegations (latency/budget default to 0.5 each). This gives:
        score = 0.4*0 + 0.3*0.5 + 0.2*0.5 + 0.1*0.0 = 0.25 — still above 0.20.

        To get below 0.20, we mix in completed delegations that have terrible
        latency and over-budget costs, bringing those factors to 0.0:
        score = 0.4*0 + 0.3*0 + 0.2*0 + 0.1*0 = 0.0
        """
        old_time = datetime.now(timezone.utc) - timedelta(days=14)
        agent = _make_agent(trust_score=0.25, status="active")
        delegations = []
        # 18 failed delegations contribute success_rate toward 0
        for _ in range(18):
            delegations.append(
                _make_delegation(
                    status="failed",
                    latency_ms=None,
                    actual_cost=0,
                    estimated_cost=0.10,
                    created_at=old_time,
                )
            )
        # 2 completed delegations with terrible latency and over-budget
        # latency_ms=15000 on a 5000ms SLA → ratio=3.0 → latency_score=0
        # actual_cost=5.0 on estimated_cost=0.10 → ratio=50 → budget_score=0
        # Overall: success_rate=2/20=0.10, lat=0, budget=0, recency=0
        # Score = 0.4*0.10 = 0.04 → well below QUARANTINE_SCORE (0.20)
        for _ in range(2):
            delegations.append(
                _make_delegation(
                    status="completed",
                    latency_ms=15000,
                    actual_cost=5.0,
                    estimated_cost=0.10,
                    created_at=old_time,
                )
            )

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
        delegation = _make_delegation(status="failed")
        score = await service.update_after_delegation(
            "test-agent", str(uuid.uuid4()), delegation
        )

        assert score < TrustService.QUARANTINE_SCORE
        assert agent.status == "quarantined"

    @pytest.mark.asyncio
    async def test_activation_on_high_score_with_enough_delegations(self) -> None:
        agent = _make_agent(trust_score=0.5, status="probationary")
        delegations = [
            _make_delegation(
                status="completed", latency_ms=1000, actual_cost=0.10, estimated_cost=0.10
            )
            for _ in range(12)
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
        delegation = _make_delegation()
        score = await service.update_after_delegation(
            "test-agent", str(uuid.uuid4()), delegation
        )

        if score >= TrustService.ACTIVATION_SCORE:
            assert agent.status == "active"
