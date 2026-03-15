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
    """Trust score computation and automatic status transitions.

    Formula: 0.4*success_rate + 0.3*latency_score + 0.2*budget_adherence + 0.1*recency
    """

    WEIGHT_SUCCESS = 0.4
    WEIGHT_LATENCY = 0.3
    WEIGHT_BUDGET = 0.2
    WEIGHT_RECENCY = 0.1

    ACTIVATION_SCORE = 0.70
    ACTIVATION_MIN_COUNT = 10
    QUARANTINE_SCORE = 0.20

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_after_delegation(
        self,
        agent_id: str,
        org_id: str,
        delegation: Delegation,
    ) -> float:
        """Recompute trust score after a delegation completes or fails."""
        agent_result = await self.db.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.agent_id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return 1.0

        score_before = float(agent.trust_score)

        deleg_result = await self.db.execute(
            select(Delegation)
            .where(
                Delegation.callee_agent_id == agent_id,
                Delegation.callee_org_id == org_id,
                Delegation.status.in_(["completed", "failed", "timeout"]),
            )
            .order_by(Delegation.created_at.desc())
            .limit(100)
        )
        delegations = list(deleg_result.scalars().all())

        if not delegations:
            return score_before

        completed = sum(1 for d in delegations if d.status == "completed")
        success_rate = completed / len(delegations)

        sla_ms = int(agent.sla.get("p99_latency_ms", 8000)) if agent.sla else 8000
        latency_scores = []
        for d in delegations:
            if d.latency_ms and d.status == "completed":
                ratio = d.latency_ms / sla_ms
                if ratio <= 1.0:
                    latency_scores.append(1.0)
                elif ratio <= 2.0:
                    latency_scores.append(2.0 - ratio)
                else:
                    latency_scores.append(0.0)
        latency_score = (
            sum(latency_scores) / len(latency_scores) if latency_scores else 0.5
        )

        budget_scores = []
        for d in delegations:
            if d.actual_cost_usd and d.estimated_cost_usd and d.status == "completed":
                ratio = float(d.actual_cost_usd) / float(d.estimated_cost_usd)
                if ratio <= 1.0:
                    budget_scores.append(1.0)
                elif ratio <= 1.5:
                    budget_scores.append(1.5 - ratio)
                else:
                    budget_scores.append(0.0)
        budget_adherence = (
            sum(budget_scores) / len(budget_scores) if budget_scores else 0.5
        )

        most_recent = delegations[0].created_at
        hours_since = (datetime.now(timezone.utc) - most_recent).total_seconds() / 3600
        recency = max(0.0, 1.0 - (hours_since / 168))

        new_score = round(
            self.WEIGHT_SUCCESS * success_rate
            + self.WEIGHT_LATENCY * latency_score
            + self.WEIGHT_BUDGET * budget_adherence
            + self.WEIGHT_RECENCY * recency,
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
                "latency_score": round(latency_score, 3),
                "budget_adherence": round(budget_adherence, 3),
                "recency": round(recency, 3),
                "delegation_count": len(delegations),
            },
        )
        self.db.add(event)

        agent.trust_score = Decimal(str(new_score))
        agent.delegation_count = len(delegations)

        old_status = agent.status
        if new_score < self.QUARANTINE_SCORE:
            agent.status = "quarantined"
        elif (
            agent.status == "probationary"
            and new_score >= self.ACTIVATION_SCORE
            and len(delegations) >= self.ACTIVATION_MIN_COUNT
        ):
            agent.status = "active"

        if agent.status != old_status:
            logger.info(
                f"Agent {agent_id} status transition: {old_status} -> {agent.status} "
                f"(score: {new_score})"
            )

        await self.db.commit()
        return new_score

    async def get_score(self, org_id: str, agent_id: str) -> float:
        result = await self.db.execute(
            select(Agent.trust_score).where(
                Agent.org_id == org_id, Agent.agent_id == agent_id
            )
        )
        score = result.scalar_one_or_none()
        return float(score) if score is not None else 1.0


class CircuitBreakerService:
    """Redis-based circuit breaker for agent failure tracking.

    Uses sorted sets with timestamps as scores. Window is 10 minutes.
    Trips when >50% of recent delegations (min 5) have failed.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def record_outcome(
        self, agent_id: str, org_id: str, success: bool
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
            for e in entries
            if (e if isinstance(e, str) else e.decode("utf-8")).startswith("fail:")
        )
        failure_rate = failures / len(entries)
        return failure_rate > CIRCUIT_BREAKER_THRESHOLD
