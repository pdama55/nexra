# Phase 10 — Circuit Breakers & Trust Score System (P1)

> **TDD Sections**: §10 (Trust Score System), §14 (Circuit Breakers & Anomaly Detection)
>
> **Depends On**: Phase 9 (MVP complete).

---

## 1. Prerequisites

- [ ] MVP fully deployed and functional
- [ ] trust_score_events table exists
- [ ] Agent model has trust_score and status columns
- [ ] TrustService stub exists from Phase 7
- [ ] Celery app skeleton exists from Phase 8

---

## 2. Objective

- Full TrustService: compute trust score after every delegation, automatic status transitions
- Circuit breaker: trip on >50% failure rate in 10-minute sliding window
- Anomaly detection: hourly Celery beat job, 3σ spend deviation alerts
- Replace Phase 7 TrustService stub with full implementation

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trust formula | 0.4×success_rate + 0.3×latency_score + 0.2×budget_adherence + 0.1×recency | TDD §10.1. Weighted composite. |
| Status transitions | probationary→active (score≥0.70, count≥10), any→quarantined (score<0.20) | TDD §10.2. Automatic, no manual override needed. |
| Circuit breaker window | 10 minutes, Redis sorted set | TDD §14.1. Sliding window for real-time failure tracking. |
| Circuit breaker threshold | >50% failure rate in window | TDD §14.1. Trips when majority of recent delegations fail. |
| Anomaly detection | Mean + 3σ on hourly spend, Celery beat | TDD §14.2. Statistical anomaly detection. |

---

## 4. File-by-File Implementation Guide

### 4.1 `services/trust_service.py` (Full Implementation)

**Path**: `nexra/services/trust_service.py` — replaces the Phase 7 stub.

```python
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from models.agent import Agent
from models.delegation import Delegation
from models.trust_score_event import TrustScoreEvent

logger = logging.getLogger("nexra.services.trust")


class TrustService:
    """Trust score computation and automatic status transitions.

    Formula: 0.4 * success_rate + 0.3 * latency_score + 0.2 * budget_adherence + 0.1 * recency
    """

    WEIGHT_SUCCESS = 0.4
    WEIGHT_LATENCY = 0.3
    WEIGHT_BUDGET = 0.2
    WEIGHT_RECENCY = 0.1

    # Status transition thresholds
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
        """Recompute trust score after a delegation completes or fails.

        Steps:
        1. Fetch last 100 delegations for this agent (as callee)
        2. Compute 4 component scores
        3. Weighted average → new trust score
        4. Record TrustScoreEvent
        5. Update agent.trust_score
        6. Check status transitions
        """
        # Get current score
        agent_result = await self.db.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.agent_id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return 1.0

        score_before = float(agent.trust_score)

        # Fetch last 100 delegations as callee
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

        # Component 1: Success rate
        completed = sum(1 for d in delegations if d.status == "completed")
        success_rate = completed / len(delegations)

        # Component 2: Latency score (1.0 = all within SLA, 0.0 = all over 2x SLA)
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
        latency_score = sum(latency_scores) / len(latency_scores) if latency_scores else 0.5

        # Component 3: Budget adherence (actual <= estimated)
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
        budget_adherence = sum(budget_scores) / len(budget_scores) if budget_scores else 0.5

        # Component 4: Recency (more recent activity = higher score)
        most_recent = delegations[0].created_at
        hours_since = (datetime.now(timezone.utc) - most_recent).total_seconds() / 3600
        recency = max(0.0, 1.0 - (hours_since / 168))  # Decays over 1 week

        # Composite score
        new_score = round(
            self.WEIGHT_SUCCESS * success_rate
            + self.WEIGHT_LATENCY * latency_score
            + self.WEIGHT_BUDGET * budget_adherence
            + self.WEIGHT_RECENCY * recency,
            3,
        )
        new_score = max(0.0, min(1.0, new_score))

        # Record event
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

        # Update agent
        agent.trust_score = Decimal(str(new_score))
        agent.delegation_count = len(delegations)

        # Status transitions
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
                f"Agent {agent_id} status transition: {old_status} → {agent.status} "
                f"(score: {new_score})"
            )

        await self.db.commit()
        return new_score

    async def get_score(self, org_id: str, agent_id: str) -> float:
        """Get current trust score."""
        result = await self.db.execute(
            select(Agent.trust_score).where(
                Agent.org_id == org_id, Agent.agent_id == agent_id
            )
        )
        score = result.scalar_one_or_none()
        return float(score) if score is not None else 1.0
```

### 4.2 `services/anomaly_service.py`

**Path**: `nexra/services/anomaly_service.py`

```python
import logging
import math
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.delegation import Delegation
from models.agent import Agent
from services.audit_service import AuditService
from core.config import get_settings

logger = logging.getLogger("nexra.services.anomaly")


class AnomalyService:
    """Statistical anomaly detection for agent spend.

    Detects agents whose hourly spend deviates by more than 3σ from their
    historical mean. Runs as a Celery beat job (hourly).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def detect_spend_anomalies(self) -> list[dict]:
        """Scan all active agents for spend anomalies.

        For each agent:
        1. Compute mean and stddev of hourly spend over last 7 days
        2. Compute spend in the last hour
        3. If last_hour > mean + 3σ → flag as anomaly

        Returns list of anomaly dicts for logging/alerting.
        """
        settings = get_settings()
        sigma_threshold = settings.anomaly_sigma_threshold
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        seven_days_ago = now - timedelta(days=7)

        # Get all agents with recent activity
        agents_result = await self.db.execute(
            select(Agent.agent_id, Agent.org_id)
            .where(Agent.status != "quarantined")
            .distinct()
        )
        agents = agents_result.all()

        anomalies = []
        audit_service = AuditService(self.db)

        for agent_id, org_id in agents:
            # Historical hourly spend (last 7 days)
            hist_result = await self.db.execute(
                select(func.sum(Delegation.actual_cost_usd))
                .where(
                    Delegation.callee_agent_id == agent_id,
                    Delegation.callee_org_id == org_id,
                    Delegation.status == "completed",
                    Delegation.created_at >= seven_days_ago,
                    Delegation.created_at < one_hour_ago,
                )
                .group_by(func.date_trunc("hour", Delegation.created_at))
            )
            hourly_spends = [float(row[0] or 0) for row in hist_result.all()]

            if len(hourly_spends) < 24:
                continue  # Not enough data

            mean = sum(hourly_spends) / len(hourly_spends)
            variance = sum((x - mean) ** 2 for x in hourly_spends) / len(hourly_spends)
            stddev = math.sqrt(variance) if variance > 0 else 0

            # Current hour spend
            current_result = await self.db.execute(
                select(func.sum(Delegation.actual_cost_usd))
                .where(
                    Delegation.callee_agent_id == agent_id,
                    Delegation.callee_org_id == org_id,
                    Delegation.status == "completed",
                    Delegation.created_at >= one_hour_ago,
                )
            )
            current_spend = float(current_result.scalar() or 0)

            threshold = mean + (sigma_threshold * stddev)
            if stddev > 0 and current_spend > threshold:
                anomaly = {
                    "agent_id": agent_id,
                    "org_id": str(org_id),
                    "current_hour_spend": current_spend,
                    "mean_hourly_spend": round(mean, 4),
                    "stddev": round(stddev, 4),
                    "threshold": round(threshold, 4),
                    "sigma_deviation": round((current_spend - mean) / stddev, 2),
                }
                anomalies.append(anomaly)
                logger.warning(f"Spend anomaly detected: {anomaly}")

                await audit_service.append(
                    org_id=str(org_id),
                    event_type="anomaly_detected",
                    actor_agent_id=None,
                    target_agent_id=agent_id,
                    details=anomaly,
                )

        return anomalies
```

### 4.3 `workers/anomaly_worker.py`

**Path**: `nexra/workers/anomaly_worker.py`

```python
import asyncio
import logging
from workers.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from core.config import get_settings
from services.anomaly_service import AnomalyService

logger = logging.getLogger("nexra.workers.anomaly")


@celery_app.task(bind=True)
def run_anomaly_detection(self):
    """Hourly Celery beat task for spend anomaly detection."""
    asyncio.run(_detect())


async def _detect():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = AnomalyService(session)
        anomalies = await service.detect_spend_anomalies()
        logger.info(f"Anomaly detection complete: {len(anomalies)} anomalies found")

    await engine.dispose()
```

Update `workers/celery_app.py` beat schedule:
```python
celery_app.conf.beat_schedule = {
    "anomaly-detection-hourly": {
        "task": "workers.anomaly_worker.run_anomaly_detection",
        "schedule": 3600.0,  # Every hour
    },
}
```

### 4.4 Circuit Breaker (Redis-based)

Add to `services/trust_service.py`:

```python
import redis.asyncio as aioredis

CIRCUIT_BREAKER_WINDOW = 600  # 10 minutes
CIRCUIT_BREAKER_THRESHOLD = 0.50  # 50% failure rate


class CircuitBreakerService:
    """Redis-based circuit breaker for agent failure tracking.

    Uses a sorted set with timestamps as scores. Members are
    'success' or 'failure' entries. Window is 10 minutes.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self.redis = redis_client

    async def record_outcome(self, agent_id: str, org_id: str, success: bool) -> None:
        """Record a delegation outcome for circuit breaker tracking."""
        import time, uuid
        key = f"cb:{org_id}:{agent_id}"
        now = time.time()
        member = f"{'ok' if success else 'fail'}:{uuid.uuid4()}"
        await self.redis.zadd(key, {member: now})
        # Trim entries older than window
        await self.redis.zremrangebyscore(key, 0, now - CIRCUIT_BREAKER_WINDOW)
        await self.redis.expire(key, CIRCUIT_BREAKER_WINDOW + 60)

    async def is_tripped(self, agent_id: str, org_id: str) -> bool:
        """Check if circuit breaker is tripped (>50% failure rate in window)."""
        import time
        key = f"cb:{org_id}:{agent_id}"
        now = time.time()
        window_start = now - CIRCUIT_BREAKER_WINDOW

        # Get all entries in window
        entries = await self.redis.zrangebyscore(key, window_start, now)
        if len(entries) < 5:
            return False  # Not enough data

        # IMPORTANT: If Redis is configured with decode_responses=True (as in api/dependencies.py),
        # entries are strings. If decode_responses=False, entries are bytes.
        # Normalize to str for safe comparison.
        failures = sum(
            1 for e in entries
            if (e if isinstance(e, str) else e.decode("utf-8")).startswith("fail:")
        )
        failure_rate = failures / len(entries)
        return failure_rate > CIRCUIT_BREAKER_THRESHOLD
```

### 4.5 Agent Trust & Status Endpoints

**Path**: Add to `nexra/api/routers/agents.py` (extends Phase 3 router)

```python
from services.trust_service import TrustService
from services.anomaly_service import AnomalyService


@router.get("/{agent_ref}/trust")
async def get_agent_trust(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get trust score and recent score events for an agent."""
    service = AgentService(db, _get_openai_client())
    agent = await service.get_by_agent_id(str(org.id), agent_ref)
    if not agent:
        from core.errors import NexraError, AGENT_NOT_FOUND
        raise NexraError(404, AGENT_NOT_FOUND, f"Agent '{agent_ref}' not found")

    from models.trust_score_event import TrustScoreEvent
    from sqlalchemy import select
    events_result = await db.execute(
        select(TrustScoreEvent)
        .where(TrustScoreEvent.agent_id == agent_ref, TrustScoreEvent.org_id == org.id)
        .order_by(TrustScoreEvent.created_at.desc())
        .limit(10)
    )
    events = events_result.scalars().all()

    return {
        "data": {
            "agent_id": agent.agent_id,
            "trust_score": float(agent.trust_score),
            "status": agent.status,
            "delegation_count": agent.delegation_count,
            "recent_events": [
                {
                    "score_before": float(e.score_before),
                    "score_after": float(e.score_after),
                    "components": e.components,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
        },
    }


@router.post("/{agent_ref}/quarantine")
async def quarantine_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Manually quarantine an agent. Quarantined agents cannot participate in delegations."""
    service = AgentService(db, _get_openai_client())
    agent = await service.update_status(str(org.id), agent_ref, "quarantined")
    return {"data": {"agent_id": agent.agent_id, "status": agent.status}}


@router.post("/{agent_ref}/activate")
async def activate_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Manually activate an agent (override probationary/quarantined status)."""
    service = AgentService(db, _get_openai_client())
    agent = await service.update_status(str(org.id), agent_ref, "active")
    return {"data": {"agent_id": agent.agent_id, "status": agent.status}}
```

---

## 5. Integration Points

Wire into delegation flow (update `services/delegation_service.py`):

1. **Before Step 10** (after policy allow): Check circuit breaker for callee. If tripped, return 503 with `CIRCUIT_BREAKER_TRIPPED`.
2. **Step 13 (success)**: Call `trust_service.update_after_delegation()` and `circuit_breaker.record_outcome(success=True)`.
3. **Step 13 (failure)**: Call `trust_service.update_after_delegation()` and `circuit_breaker.record_outcome(success=False)`.

---

## 6. Guardrails

1. **DO NOT** allow manual trust score overrides. Scores are computed algorithmically.
2. **DO NOT** skip the minimum delegation count (10) for probationary→active transition.
3. **DO NOT** use the circuit breaker for rate limiting — it's for failure detection only.
4. **DO NOT** run anomaly detection more frequently than hourly — it's expensive.

---

## 7. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-008 | Trust | Score increases after successful delegation | new_score > old_score (given good metrics) |
| T-009 | Trust | Score decreases after failed delegation | new_score < old_score |
| T-010 | Trust | probationary→active when score≥0.70 and count≥10 | status=='active' |
| T-011 | Trust | Quarantine when score<0.20 | status=='quarantined' |
| T-TRUST-005 | Trust | Score clamped to [0, 1] | Never negative, never > 1 |
| T-CB-001 | Circuit | Breaker trips at >50% failure in 10min | is_tripped()==True |
| T-CB-002 | Circuit | Breaker not tripped with <5 entries | is_tripped()==False |
| T-CB-003 | Circuit | Old entries pruned from window | Entries older than 10min removed |
| T-ANOM-001 | Anomaly | 3σ deviation flagged | anomaly detected in results |
| T-ANOM-002 | Anomaly | Normal spend not flagged | no anomalies |
| T-ANOM-003 | Anomaly | <24 hours data → skip | agent skipped |
