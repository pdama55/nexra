import logging
import time as _time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent import Agent
from models.delegation import Delegation
from models.trust_score_event import TrustScoreEvent

logger = logging.getLogger("nexra.services.trust")

CIRCUIT_BREAKER_WINDOW = 600  # 10 minutes
CIRCUIT_BREAKER_THRESHOLD = 0.50


class TrustService:
    """Trust score computation and automatic status transitions."""

    WINDOW_DAYS = 30

    WEIGHT_SUCCESS_RATE = 0.40
    WEIGHT_SLA_COMPLIANCE = 0.30
    WEIGHT_COST_ACCURACY = 0.20
    WEIGHT_POLICY_VIOLATIONS_INVERSE = 0.10

    ACTIVATION_SCORE = 0.70
    ACTIVATION_MIN_COUNT = 10
    PROBATIONARY_SCORE = 0.40
    QUARANTINE_SCORE = 0.20

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_after_delegation(
        self,
        agent_id: str,
        org_id: str,
        delegation: Delegation,
    ) -> float:
        """Recompute trust score in a rolling 30-day window."""
        agent_result = await self.db.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.agent_id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return 1.0

        score_before = float(agent.trust_score)
        window_start = datetime.now(timezone.utc) - timedelta(days=self.WINDOW_DAYS)

        deleg_result = await self.db.execute(
            select(Delegation)
            .where(
                Delegation.callee_agent_id == agent_id,
                Delegation.callee_org_id == org_id,
                Delegation.created_at >= window_start,
                Delegation.status.in_(["completed", "failed", "timeout", "blocked"]),
            )
            .order_by(Delegation.created_at.desc())
        )
        delegations = list(deleg_result.scalars().all())
        total = len(delegations)
        if total == 0:
            return score_before

        completed = [d for d in delegations if d.status == "completed"]
        success_rate = len(completed) / max(total, 1)

        sla_ms = int(agent.sla.get("p99_latency_ms", 8000)) if agent.sla else 8000
        sla_met = sum(1 for d in completed if d.latency_ms is not None and d.latency_ms <= sla_ms)
        sla_compliance = sla_met / max(len(completed), 1)

        estimated = float(delegation.estimated_cost_usd or 0)
        actual = float(delegation.actual_cost_usd or 0)
        cost_accuracy = max(0.0, 1.0 - abs(actual - estimated) / max(estimated, 0.001))
        cost_accuracy = min(cost_accuracy, 1.0)

        policy_violations = sum(
            1
            for d in delegations
            if d.status == "blocked" or d.policy_decision == "block"
        )
        policy_violations_inverse = max(0.0, 1.0 - policy_violations / max(total, 1))

        new_score = round(
            (success_rate * self.WEIGHT_SUCCESS_RATE)
            + (sla_compliance * self.WEIGHT_SLA_COMPLIANCE)
            + (cost_accuracy * self.WEIGHT_COST_ACCURACY)
            + (policy_violations_inverse * self.WEIGHT_POLICY_VIOLATIONS_INVERSE),
            3,
        )
        new_score = max(0.0, min(1.0, new_score))

        event = TrustScoreEvent(
            agent_id=agent_id,
            org_id=org_id,
            delegation_id=delegation.id,
            score_before=Decimal(str(score_before)),
            score_after=Decimal(str(new_score)),
            components={
                "success_rate": round(success_rate, 3),
                "sla_compliance": round(sla_compliance, 3),
                "cost_accuracy": round(cost_accuracy, 3),
                "policy_violations_inverse": round(policy_violations_inverse, 3),
                "policy_violations": int(policy_violations),
                "delegation_count": total,
            },
        )
        self.db.add(event)

        old_status = agent.status
        agent.trust_score = Decimal(str(new_score))
        agent.delegation_count = max(int(agent.delegation_count) + 1, total)

        if new_score < self.QUARANTINE_SCORE:
            agent.status = "quarantined"
        elif new_score < self.PROBATIONARY_SCORE and old_status == "active":
            agent.status = "probationary"
        elif (
            new_score >= self.ACTIVATION_SCORE
            and agent.delegation_count >= self.ACTIVATION_MIN_COUNT
            and old_status == "probationary"
        ):
            agent.status = "active"

        if agent.status != old_status:
            logger.info(
                "Agent %s status transition: %s -> %s (score: %.3f)",
                agent_id,
                old_status,
                agent.status,
                new_score,
            )

        await self.db.commit()
        return new_score

    async def get_score(self, org_id: str, agent_id: str) -> float:
        result = await self.db.execute(
            select(Agent.trust_score).where(
                Agent.org_id == org_id,
                Agent.agent_id == agent_id,
            )
        )
        score = result.scalar_one_or_none()
        return float(score) if score is not None else 1.0


class CircuitBreakerService:
    """Redis-based circuit breaker for agent failure tracking."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def record_outcome(
        self,
        agent_id: str,
        org_id: str,
        success: bool,
    ) -> None:
        key = f"cb:{org_id}:{agent_id}"
        now = _time.time()
        member = f"{'ok' if success else 'fail'}:{_uuid.uuid4()}"
        await self.redis.zadd(key, {member: now})
        await self.redis.zremrangebyscore(key, 0, now - CIRCUIT_BREAKER_WINDOW)
        await self.redis.expire(key, CIRCUIT_BREAKER_WINDOW + 60)

    async def is_tripped(self, agent_id: str, org_id: str) -> bool:
        key = f"cb:{org_id}:{agent_id}"
        now = _time.time()
        window_start = now - CIRCUIT_BREAKER_WINDOW

        entries = await self.redis.zrangebyscore(key, window_start, now)
        if len(entries) < 5:
            return False

        failures = sum(
            1
            for entry in entries
            if (
                entry if isinstance(entry, str) else entry.decode("utf-8")
            ).startswith("fail:")
        )
        failure_rate = failures / len(entries)
        return failure_rate > CIRCUIT_BREAKER_THRESHOLD
