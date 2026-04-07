# Phase 12 — Governance Dashboard API, SIEM Export & Framework Adapters (P1)

> **TDD Sections**: §17.2 (nexra-ts SDK), §18 (Framework Adapters — LangGraph, CrewAI, Bedrock, A2A), §25.1 (Dashboard/SIEM)
>
> **Depends On**: Phase 11 (HiTL + Async Delegation complete).

---

## 1. Prerequisites

- [ ] All P1 features from Phases 10–11 complete and tested
- [ ] `/analytics/usage` endpoint exists (stub from Phase 7)
- [ ] `/audit/log` endpoint exists with cursor-based pagination (Phase 7)
- [ ] AuditService supports all event types from TDD §13.1
- [ ] Celery workers operational with beat schedule
- [ ] nexra-py SDK complete from Phase 8 (`sdk/nexra-py/`)
- [ ] Organization model accessible with `siem_config` field (new — added in this phase)
- [ ] OpenAI, Stripe, Redis, Postgres all operational

---

## 2. Objective

This phase delivers three feature groups:

1. **Governance Dashboard API**: Backend endpoints that power an org-level real-time dashboard. Includes delegation volume time-series, cost breakdowns, failure rates, trust score leaderboards, and agents approaching budget limits. (The React SPA frontend is out of scope for P1 — these are API-only endpoints.)

2. **SIEM Export**: Real-time streaming export of audit_log events to external SIEM systems (Splunk, Datadog, Elastic, generic webhook). Implemented as a Celery worker that tails the audit_log and forwards new events to org-configured SIEM endpoints.

3. **Framework Adapters**: LangGraph adapter (`nexra_tool()`), CrewAI adapter (`NexraTool`), AWS Bedrock adapter (SigV4 bridge), A2A native registration endpoint. Plus the TypeScript SDK (`nexra-ts`).

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dashboard API | Read-only endpoints on existing data | TDD §25.1. No new tables needed. Aggregation queries on delegations + audit_log. |
| Time-series granularity | Hourly buckets via `date_trunc('hour', ...)` | Sufficient for dashboard charts. Minute-level is too noisy, daily too coarse. |
| SIEM delivery | Celery beat (every 60s) + cursor-based tailing | Avoids CDC complexity. Cursor stored in Redis. Acceptable latency for SIEM (< 2 min). |
| SIEM payload format | JSON with consistent field names across all event types | TDD §25.1. SIEM systems expect structured JSON. |
| SIEM config storage | `siem_config` JSONB column on organizations table | Per-org configuration. Includes webhook_url, auth headers, enabled flag. |
| LangGraph adapter | `@tool` decorator wrapping `client.hire()` | TDD §18.1. Zero changes to existing LangGraph graph definitions. |
| CrewAI adapter | `BaseTool` subclass with sync `_run()` | TDD §18.2. CrewAI tools are synchronous. Uses `asyncio.run()` bridge. |
| Bedrock adapter | SigV4 signing + InvokeAgent payload mapping | TDD §18.3. Auto-detects Bedrock endpoints from webhook_url pattern. |
| A2A registration | Separate `/agents/register/a2a` endpoint | TDD §18.4. Maps A2A Agent Card fields to Nexra registration format. |
| nexra-ts SDK | TypeScript, published to npm, mirrors nexra-py API | TDD §17.2. Thin wrapper around REST API. |

---

## 4. Database Migration

### 4.1 Add `siem_config` to Organizations

**Migration file**: `db/migrations/versions/XXX_add_siem_config.py`

```python
"""Add siem_config to organizations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "XXX"
down_revision = "<previous_revision>"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("siem_config", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "siem_config")
```

**siem_config JSONB schema**:

```json
{
  "enabled": true,
  "webhook_url": "https://splunk.example.com/services/collector",
  "auth_header": "Splunk <HEC_TOKEN>",
  "format": "splunk|datadog|elastic|generic",
  "event_types": ["delegation_completed", "delegation_failed", "policy_evaluated"],
  "batch_size": 50,
  "created_at": "2026-03-15T00:00:00Z"
}
```

### 4.2 Update Organization Model

**Path**: `nexra/models/organization.py`

Add to the existing Organization model:

```python
from sqlalchemy.dialects.postgresql import JSONB

siem_config = Column(JSONB, nullable=True)
```

---

## 5. File-by-File Implementation Guide

### 5.1 `api/routers/analytics.py` — Dashboard API Endpoints

**Path**: `nexra/api/routers/analytics.py`

Extend the existing analytics router with dashboard-specific endpoints.

```python
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, text
from pydantic import BaseModel, Field

from api.dependencies import get_db, get_current_org
from models.delegation import Delegation
from models.agent import Agent
from models.agent_budget import AgentBudget
from models.audit_log import AuditLog

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ─── Response Models ────────────────────────────────────────────

class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: float


class DelegationVolumeResponse(BaseModel):
    """Delegation volume over time, bucketed hourly."""
    total: int
    series: list[TimeSeriesPoint]
    period_start: str
    period_end: str


class CostBreakdownItem(BaseModel):
    agent_id: str
    agent_name: str
    total_cost_usd: float
    delegation_count: int
    avg_cost_per_delegation: float


class CostBreakdownResponse(BaseModel):
    total_cost_usd: float
    by_agent: list[CostBreakdownItem]
    period_start: str
    period_end: str


class FailureRateItem(BaseModel):
    agent_id: str
    agent_name: str
    total_delegations: int
    failed_delegations: int
    failure_rate: float
    avg_latency_ms: float | None


class FailureRateResponse(BaseModel):
    items: list[FailureRateItem]


class TrustLeaderboardItem(BaseModel):
    agent_id: str
    agent_name: str
    trust_score: float
    status: str
    delegation_count: int


class TrustLeaderboardResponse(BaseModel):
    items: list[TrustLeaderboardItem]


class BudgetAlertItem(BaseModel):
    agent_id: str
    period: str
    period_type: str
    cap_usd: float
    spent_usd: float
    remaining_usd: float
    utilization_pct: float


class BudgetAlertResponse(BaseModel):
    """Agents approaching or exceeding budget limits (>80% utilization)."""
    items: list[BudgetAlertItem]


class NetworkGraphNode(BaseModel):
    agent_id: str
    name: str
    status: str
    trust_score: float
    delegation_count: int


class NetworkGraphEdge(BaseModel):
    source_agent_id: str
    target_agent_id: str
    delegation_count: int
    total_cost_usd: float


class NetworkGraphResponse(BaseModel):
    nodes: list[NetworkGraphNode]
    edges: list[NetworkGraphEdge]


# ─── Endpoints ──────────────────────────────────────────────────

@router.get(
    "/usage/volume",
    response_model=DelegationVolumeResponse,
    summary="Delegation volume time-series",
    description=(
        "Returns hourly delegation counts for the specified period. "
        "Default: last 7 days. Used for dashboard volume chart."
    ),
)
async def get_delegation_volume(
    days: int = Query(7, ge=1, le=90, description="Lookback period in days"),
    agent_id: str | None = Query(None, description="Filter by specific agent"),
    capability_type: str | None = Query(None, description="Filter by capability type"),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    filters = [
        Delegation.caller_org_id == org.id,
        Delegation.created_at >= period_start,
        Delegation.created_at <= period_end,
    ]
    if agent_id:
        filters.append(
            (Delegation.caller_agent_id == agent_id)
            | (Delegation.callee_agent_id == agent_id)
        )

    # Hourly buckets
    hour_bucket = func.date_trunc("hour", Delegation.created_at)
    result = await db.execute(
        select(hour_bucket.label("bucket"), func.count().label("count"))
        .where(and_(*filters))
        .group_by("bucket")
        .order_by("bucket")
    )
    rows = result.all()

    total = sum(r.count for r in rows)
    series = [
        TimeSeriesPoint(timestamp=r.bucket.isoformat(), value=r.count)
        for r in rows
    ]

    return DelegationVolumeResponse(
        total=total,
        series=series,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )


@router.get(
    "/usage/cost-breakdown",
    response_model=CostBreakdownResponse,
    summary="Cost breakdown by agent",
    description=(
        "Returns total cost, delegation count, and average cost per agent "
        "for the specified period. Used for CFO-facing spend reports."
    ),
)
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)

    result = await db.execute(
        select(
            Delegation.caller_agent_id,
            func.count().label("count"),
            func.coalesce(func.sum(Delegation.actual_cost_usd), 0).label("total_cost"),
        )
        .where(
            Delegation.caller_org_id == org.id,
            Delegation.created_at >= period_start,
            Delegation.status == "completed",
        )
        .group_by(Delegation.caller_agent_id)
        .order_by(text("total_cost DESC"))
    )
    rows = result.all()

    # Fetch agent names
    agent_ids = [r.caller_agent_id for r in rows]
    agents_result = await db.execute(
        select(Agent.agent_id, Agent.name).where(
            Agent.org_id == org.id,
            Agent.agent_id.in_(agent_ids),
        )
    )
    agent_names = {a.agent_id: a.name for a in agents_result.all()}

    total_cost = sum(float(r.total_cost) for r in rows)
    items = [
        CostBreakdownItem(
            agent_id=r.caller_agent_id,
            agent_name=agent_names.get(r.caller_agent_id, r.caller_agent_id),
            total_cost_usd=round(float(r.total_cost), 4),
            delegation_count=r.count,
            avg_cost_per_delegation=round(float(r.total_cost) / r.count, 4)
            if r.count > 0
            else 0,
        )
        for r in rows
    ]

    return CostBreakdownResponse(
        total_cost_usd=round(total_cost, 4),
        by_agent=items,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
    )


@router.get(
    "/usage/failure-rates",
    response_model=FailureRateResponse,
    summary="Failure rates by agent",
    description=(
        "Returns failure rate and average latency per agent. "
        "Used for reliability monitoring in dashboard."
    ),
)
async def get_failure_rates(
    days: int = Query(7, ge=1, le=90),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            Delegation.callee_agent_id,
            func.count().label("total"),
            func.sum(
                case((Delegation.status.in_(["failed", "timeout"]), 1), else_=0)
            ).label("failed"),
            func.avg(Delegation.latency_ms).label("avg_latency"),
        )
        .where(
            Delegation.caller_org_id == org.id,
            Delegation.created_at >= period_start,
            Delegation.status.in_(["completed", "failed", "timeout"]),
        )
        .group_by(Delegation.callee_agent_id)
        .order_by(text("failed DESC"))
    )
    rows = result.all()

    agent_ids = [r.callee_agent_id for r in rows]
    agents_result = await db.execute(
        select(Agent.agent_id, Agent.name).where(
            Agent.org_id == org.id,
            Agent.agent_id.in_(agent_ids),
        )
    )
    agent_names = {a.agent_id: a.name for a in agents_result.all()}

    items = [
        FailureRateItem(
            agent_id=r.callee_agent_id,
            agent_name=agent_names.get(r.callee_agent_id, r.callee_agent_id),
            total_delegations=r.total,
            failed_delegations=r.failed,
            failure_rate=round(r.failed / r.total, 3) if r.total > 0 else 0,
            avg_latency_ms=round(float(r.avg_latency), 1) if r.avg_latency else None,
        )
        for r in rows
    ]

    return FailureRateResponse(items=items)


@router.get(
    "/usage/trust-leaderboard",
    response_model=TrustLeaderboardResponse,
    summary="Trust score leaderboard",
    description="Returns all agents ranked by trust score, descending.",
)
async def get_trust_leaderboard(
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent)
        .where(Agent.org_id == org.id)
        .order_by(Agent.trust_score.desc())
    )
    agents = result.scalars().all()

    items = [
        TrustLeaderboardItem(
            agent_id=a.agent_id,
            agent_name=a.name,
            trust_score=float(a.trust_score),
            status=a.status,
            delegation_count=a.delegation_count or 0,
        )
        for a in agents
    ]

    return TrustLeaderboardResponse(items=items)


@router.get(
    "/usage/budget-alerts",
    response_model=BudgetAlertResponse,
    summary="Agents approaching budget limits",
    description=(
        "Returns agents whose budget utilization exceeds 80% for the "
        "current period. Used for proactive budget monitoring."
    ),
)
async def get_budget_alerts(
    threshold_pct: float = Query(80.0, ge=0, le=100),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    first_of_month = today.replace(day=1)

    result = await db.execute(
        select(AgentBudget).where(
            AgentBudget.org_id == org.id,
            AgentBudget.period.in_([today, first_of_month]),
        )
    )
    budgets = result.scalars().all()

    items = []
    for b in budgets:
        if float(b.cap_usd) == 0:
            continue
        utilization = (float(b.spent_usd) / float(b.cap_usd)) * 100
        if utilization >= threshold_pct:
            items.append(
                BudgetAlertItem(
                    agent_id=b.agent_id,
                    period=str(b.period),
                    period_type=b.period_type,
                    cap_usd=float(b.cap_usd),
                    spent_usd=float(b.spent_usd),
                    remaining_usd=max(0, float(b.cap_usd) - float(b.spent_usd)),
                    utilization_pct=round(utilization, 1),
                )
            )

    items.sort(key=lambda x: x.utilization_pct, reverse=True)
    return BudgetAlertResponse(items=items)


@router.get(
    "/usage/network-graph",
    response_model=NetworkGraphResponse,
    summary="Agent network graph data",
    description=(
        "Returns nodes (agents) and edges (delegation relationships) "
        "for rendering the agent network graph in the dashboard."
    ),
)
async def get_network_graph(
    days: int = Query(30, ge=1, le=365),
    org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    period_start = datetime.now(timezone.utc) - timedelta(days=days)

    # Nodes: all agents in org
    agents_result = await db.execute(
        select(Agent).where(Agent.org_id == org.id)
    )
    agents = agents_result.scalars().all()
    nodes = [
        NetworkGraphNode(
            agent_id=a.agent_id,
            name=a.name,
            status=a.status,
            trust_score=float(a.trust_score),
            delegation_count=a.delegation_count or 0,
        )
        for a in agents
    ]

    # Edges: delegation relationships
    edges_result = await db.execute(
        select(
            Delegation.caller_agent_id,
            Delegation.callee_agent_id,
            func.count().label("count"),
            func.coalesce(func.sum(Delegation.actual_cost_usd), 0).label("cost"),
        )
        .where(
            Delegation.caller_org_id == org.id,
            Delegation.created_at >= period_start,
            Delegation.status == "completed",
        )
        .group_by(Delegation.caller_agent_id, Delegation.callee_agent_id)
    )
    edge_rows = edges_result.all()
    edges = [
        NetworkGraphEdge(
            source_agent_id=e.caller_agent_id,
            target_agent_id=e.callee_agent_id,
            delegation_count=e.count,
            total_cost_usd=round(float(e.cost), 4),
        )
        for e in edge_rows
    ]

    return NetworkGraphResponse(nodes=nodes, edges=edges)
```

---

### 5.2 `workers/siem_worker.py` — SIEM Export Worker

**Path**: `nexra/workers/siem_worker.py`

Celery beat task that tails the audit_log and forwards new events to configured SIEM endpoints.

```python
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from workers.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, and_
import redis.asyncio as aioredis

from core.config import get_settings
from models.audit_log import AuditLog
from models.organization import Organization

logger = logging.getLogger("nexra.workers.siem")

SIEM_CURSOR_PREFIX = "siem:cursor:"
SIEM_DELIVERY_TIMEOUT = 10


@celery_app.task(
    bind=True,
    name="workers.siem_worker.export_audit_events",
    queue="siem",
)
def export_audit_events(self):
    """Celery beat task: export new audit_log events to configured SIEM endpoints.

    Runs every 60 seconds. For each org with SIEM enabled:
    1. Read cursor from Redis (last exported audit_log.id)
    2. Fetch new audit_log entries since cursor
    3. Format events for target SIEM format
    4. POST batch to org's SIEM webhook_url
    5. Update cursor on success
    """
    asyncio.run(_export())


async def _export():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = aioredis.from_url(settings.redis_url)

    try:
        async with session_factory() as session:
            # Find all orgs with SIEM enabled
            result = await session.execute(
                select(Organization).where(
                    Organization.siem_config.isnot(None)
                )
            )
            orgs = result.scalars().all()

            for org in orgs:
                config = org.siem_config
                if not config or not config.get("enabled"):
                    continue

                try:
                    await _export_for_org(session, redis_client, org, config)
                except Exception as e:
                    logger.error(
                        f"SIEM export failed for org {org.id}: {e}",
                        exc_info=True,
                    )
    finally:
        await redis_client.aclose()
        await engine.dispose()


async def _export_for_org(
    session,
    redis_client: aioredis.Redis,
    org: Organization,
    config: dict,
) -> None:
    """Export audit events for a single org to their SIEM endpoint."""
    cursor_key = f"{SIEM_CURSOR_PREFIX}{org.id}"
    last_cursor = await redis_client.get(cursor_key)

    # Build query for new events
    filters = [AuditLog.org_id == org.id]
    if last_cursor:
        filters.append(AuditLog.id > last_cursor.decode())

    # Filter by configured event types (if specified)
    event_types = config.get("event_types")
    if event_types:
        filters.append(AuditLog.event_type.in_(event_types))

    batch_size = config.get("batch_size", 50)

    result = await session.execute(
        select(AuditLog)
        .where(and_(*filters))
        .order_by(AuditLog.created_at.asc())
        .limit(batch_size)
    )
    events = result.scalars().all()

    if not events:
        return

    # Format events for target SIEM
    siem_format = config.get("format", "generic")
    formatted = [_format_event(event, siem_format) for event in events]

    # Deliver to SIEM endpoint
    webhook_url = config["webhook_url"]
    auth_header = config.get("auth_header")
    headers = {"Content-Type": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(timeout=SIEM_DELIVERY_TIMEOUT) as client:
        if siem_format == "splunk":
            # Splunk HEC expects individual events wrapped in {"event": ...}
            for event in formatted:
                resp = await client.post(
                    webhook_url,
                    json={"event": event},
                    headers=headers,
                )
                if not resp.is_success:
                    logger.warning(
                        f"SIEM delivery to {webhook_url} returned {resp.status_code}"
                    )
                    return  # Stop batch on failure — retry next cycle
        else:
            # Datadog, Elastic, generic: send batch
            resp = await client.post(
                webhook_url,
                json={"events": formatted},
                headers=headers,
            )
            if not resp.is_success:
                logger.warning(
                    f"SIEM batch delivery to {webhook_url} returned {resp.status_code}"
                )
                return

    # Update cursor to last successfully exported event
    new_cursor = str(events[-1].id)
    await redis_client.set(cursor_key, new_cursor)
    logger.info(
        f"SIEM export for org {org.id}: {len(events)} events exported "
        f"(cursor: {new_cursor})"
    )


def _format_event(event: AuditLog, siem_format: str) -> dict:
    """Format an audit_log entry for the target SIEM system.

    All formats share a common base structure. SIEM-specific wrappers
    are applied on top.

    Args:
        event: AuditLog ORM instance
        siem_format: One of 'splunk', 'datadog', 'elastic', 'generic'

    Returns:
        dict formatted for the target SIEM
    """
    base = {
        "id": str(event.id),
        "timestamp": event.created_at.isoformat() if event.created_at else None,
        "org_id": str(event.org_id),
        "event_type": event.event_type,
        "delegation_id": str(event.delegation_id) if event.delegation_id else None,
        "actor_agent_id": event.actor_agent_id,
        "target_agent_id": event.target_agent_id,
        "cost_usd": float(event.cost_usd) if event.cost_usd else None,
        "details": event.details or {},
        "source": "nexra",
    }

    if siem_format == "splunk":
        return {
            "time": int(event.created_at.timestamp()) if event.created_at else None,
            "sourcetype": "nexra:audit",
            "source": "nexra-api",
            "host": "api.usenexra.com",
            **base,
        }
    elif siem_format == "datadog":
        return {
            "ddsource": "nexra",
            "ddtags": f"event_type:{event.event_type},org:{event.org_id}",
            "hostname": "api.usenexra.com",
            "service": "nexra",
            "message": json.dumps(base),
            **base,
        }
    elif siem_format == "elastic":
        return {
            "@timestamp": event.created_at.isoformat() if event.created_at else None,
            "_index": "nexra-audit",
            **base,
        }
    else:
        return base
```

---

### 5.3 `api/routers/siem.py` — SIEM Configuration Endpoint

**Path**: `nexra/api/routers/siem.py`

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_org
from models.organization import Organization

router = APIRouter(prefix="/siem", tags=["siem"])


class SIEMConfigRequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable SIEM export")
    webhook_url: str = Field(
        ..., description="SIEM endpoint URL (Splunk HEC, Datadog, etc.)"
    )
    auth_header: str | None = Field(
        None, description="Authorization header value (e.g., 'Splunk <token>')"
    )
    format: str = Field(
        "generic",
        description="SIEM format: splunk | datadog | elastic | generic",
        pattern="^(splunk|datadog|elastic|generic)$",
    )
    event_types: list[str] | None = Field(
        None,
        description=(
            "Filter which event types to export. "
            "Null = all types. Example: ['delegation_completed', 'policy_evaluated']"
        ),
    )
    batch_size: int = Field(50, ge=1, le=500, description="Events per batch")


class SIEMConfigResponse(BaseModel):
    enabled: bool
    webhook_url: str
    format: str
    event_types: list[str] | None
    batch_size: int
    message: str


@router.post(
    "/config",
    response_model=SIEMConfigResponse,
    summary="Configure SIEM export",
    description=(
        "Set up real-time audit log export to your SIEM system. "
        "Supported formats: Splunk (HEC), Datadog, Elastic, generic webhook. "
        "Events are batched and delivered every 60 seconds."
    ),
)
async def configure_siem(
    body: SIEMConfigRequest,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    org.siem_config = {
        "enabled": body.enabled,
        "webhook_url": body.webhook_url,
        "auth_header": body.auth_header,
        "format": body.format,
        "event_types": body.event_types,
        "batch_size": body.batch_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.commit()

    return SIEMConfigResponse(
        enabled=body.enabled,
        webhook_url=body.webhook_url,
        format=body.format,
        event_types=body.event_types,
        batch_size=body.batch_size,
        message="SIEM export configured successfully",
    )


@router.get(
    "/config",
    response_model=SIEMConfigResponse | None,
    summary="Get current SIEM configuration",
)
async def get_siem_config(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    if not org.siem_config:
        return None

    config = org.siem_config
    return SIEMConfigResponse(
        enabled=config.get("enabled", False),
        webhook_url=config.get("webhook_url", ""),
        format=config.get("format", "generic"),
        event_types=config.get("event_types"),
        batch_size=config.get("batch_size", 50),
        message="Current SIEM configuration",
    )
```

---

### 5.4 Update `workers/celery_app.py` — Add SIEM Beat Schedule

```python
celery_app.conf.beat_schedule.update({
    "siem-export": {
        "task": "workers.siem_worker.export_audit_events",
        "schedule": 60.0,  # Every 60 seconds
    },
})

celery_app.conf.task_routes.update({
    "workers.siem_worker.*": {"queue": "siem"},
})
```

---

### 5.5 `sdk/nexra-py/nexra/adapters/langgraph.py` — LangGraph Adapter

**Path**: `nexra/sdk/nexra-py/nexra/adapters/langgraph.py`

```python
"""LangGraph adapter for Nexra.

Exposes Nexra's hire() as a LangGraph-compatible tool node.
Zero changes required to existing LangGraph graph definitions.

Usage:
    from nexra import NexraClient
    from nexra.adapters.langgraph import nexra_tool

    client = NexraClient(api_key="nx_live_...", agent_id="my-agent")
    tools = [nexra_tool(client)]
    graph = StateGraph(State).add_node("agent", create_react_agent(llm, tools))

TDD Reference: §18.1
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nexra.client import NexraClient


def nexra_tool(client: NexraClient):
    """Create a LangGraph-compatible tool that delegates tasks via Nexra.

    Args:
        client: Initialized NexraClient instance with API key and agent_id.

    Returns:
        A LangChain @tool function usable as a LangGraph ToolNode.
    """
    from langchain_core.tools import tool

    @tool
    async def hire_agent(
        capability: str,
        task_input: dict,
        budget_cap: float = 1.0,
        context_scope: list[str] | None = None,
    ) -> dict:
        """Hire a Nexra-registered agent for a given capability.

        Nexra handles: discovery → policy check → delegation → settlement.

        Args:
            capability: Capability type to search for (e.g., 'research', 'analysis')
            task_input: Task payload dict matching the callee's input_schema
            budget_cap: Maximum cost in USD for this delegation
            context_scope: Optional list of data grant keys for scoped context

        Returns:
            dict containing the callee agent's result
        """
        result = await client.hire(
            capability=capability,
            task={"type": capability, "input": task_input},
            context_scope=context_scope or [],
            budget_cap=budget_cap,
        )
        return result.result if hasattr(result, "result") else result

    return hire_agent


def nexra_discover_tool(client: NexraClient):
    """Create a LangGraph tool for discovering available agents.

    Useful when an agent needs to inspect available capabilities
    before deciding which to delegate to.
    """
    from langchain_core.tools import tool

    @tool
    async def discover_agents(
        query: str,
        capability_type: str | None = None,
        budget_cap: float | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Discover available agents in the Nexra registry.

        Args:
            query: Natural language description of needed capability
            capability_type: Optional exact capability type filter
            budget_cap: Optional max cost filter
            limit: Max results to return

        Returns:
            List of matching agents with scores and metadata
        """
        matches = await client.discover(
            query=query,
            capability_type=capability_type,
            budget_cap=budget_cap,
            limit=limit,
        )
        return [
            {
                "agent_id": m.agent_id,
                "name": m.name,
                "match_score": m.match_score,
                "trust_score": m.trust_score,
                "pricing": m.pricing,
            }
            for m in matches
        ]

    return discover_agents
```

---

### 5.6 `sdk/nexra-py/nexra/adapters/crewai.py` — CrewAI Adapter

**Path**: `nexra/sdk/nexra-py/nexra/adapters/crewai.py`

```python
"""CrewAI adapter for Nexra.

Exposes Nexra's hire() as a CrewAI BaseTool.
CrewAI tools are synchronous — uses asyncio.run() bridge.

Usage:
    from nexra import NexraClient
    from nexra.adapters.crewai import NexraTool

    client = NexraClient(api_key="nx_live_...", agent_id="my-agent")
    tool = NexraTool(client=client)
    agent = Agent(tools=[tool], ...)

TDD Reference: §18.2
"""
from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from crewai_tools import BaseTool

if TYPE_CHECKING:
    from nexra.client import NexraClient


class NexraTool(BaseTool):
    """CrewAI tool that delegates tasks to Nexra-registered agents.

    Wraps NexraClient.hire() in a synchronous interface compatible
    with CrewAI's BaseTool contract.
    """

    name: str = "nexra_hire"
    description: str = (
        "Hire a specialized agent from the Nexra registry for a given capability. "
        "Nexra handles discovery, policy evaluation, delegation, and settlement. "
        "Input: capability (str), task_input (dict), budget_cap (float, optional). "
        "Returns the agent's result as a string."
    )
    client: Any  # NexraClient — typed as Any to avoid pydantic validation issues

    def _run(
        self,
        capability: str,
        task_input: dict,
        budget_cap: float = 1.0,
        context_scope: list[str] | None = None,
    ) -> str:
        """Execute the tool synchronously (CrewAI requirement).

        Uses asyncio.run() to bridge to the async NexraClient.
        If an event loop is already running (e.g., in Jupyter),
        falls back to nest_asyncio.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.client.hire(
            capability=capability,
            task={"type": capability, "input": task_input},
            context_scope=context_scope or [],
            budget_cap=budget_cap,
        )

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            result = loop.run_until_complete(coro)
        else:
            result = asyncio.run(coro)

        return str(result.result if hasattr(result, "result") else result)


class NexraDiscoverTool(BaseTool):
    """CrewAI tool for discovering available agents in Nexra."""

    name: str = "nexra_discover"
    description: str = (
        "Discover available agents in the Nexra registry by capability. "
        "Input: query (str), capability_type (str, optional), limit (int, optional). "
        "Returns a list of matching agents with scores."
    )
    client: Any

    def _run(
        self,
        query: str,
        capability_type: str | None = None,
        budget_cap: float | None = None,
        limit: int = 5,
    ) -> str:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = self.client.discover(
            query=query,
            capability_type=capability_type,
            budget_cap=budget_cap,
            limit=limit,
        )

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            matches = loop.run_until_complete(coro)
        else:
            matches = asyncio.run(coro)

        return str([
            {
                "agent_id": m.agent_id,
                "match_score": m.match_score,
                "trust_score": m.trust_score,
            }
            for m in matches
        ])
```

---

### 5.7 `sdk/nexra-py/nexra/adapters/bedrock.py` — AWS Bedrock Adapter

**Path**: `nexra/sdk/nexra-py/nexra/adapters/bedrock.py`

```python
"""AWS Bedrock adapter for Nexra.

Auto-detects Bedrock agent endpoints from webhook_url patterns.
Handles SigV4 auth and bidirectional payload mapping between
Nexra's delegation protocol and Bedrock's InvokeAgent API.

TDD Reference: §18.3
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("nexra.adapters.bedrock")

BEDROCK_ENDPOINT_PATTERNS = [
    r"bedrock-agent-runtime\.",
    r"runtime\.sagemaker\.amazonaws\.com",
]


def is_bedrock_endpoint(url: str) -> bool:
    """Check if a webhook URL points to an AWS Bedrock agent endpoint.

    Args:
        url: The webhook URL to check.

    Returns:
        True if the URL matches a known Bedrock endpoint pattern.
    """
    return any(re.search(pattern, url) for pattern in BEDROCK_ENDPOINT_PATTERNS)


def extract_agent_id_from_url(url: str) -> str | None:
    """Extract the Bedrock agent ID from a Bedrock runtime URL.

    Expected URL format:
    https://bedrock-agent-runtime.{region}.amazonaws.com/agents/{agent_id}/...

    Returns:
        Agent ID string, or None if not extractable.
    """
    match = re.search(r"/agents/([A-Z0-9]+)", url)
    return match.group(1) if match else None


async def deliver_to_bedrock(
    webhook_url: str,
    nexra_payload: dict,
    aws_credentials: dict,
) -> dict:
    """Deliver a Nexra delegation to a Bedrock agent.

    Translates Nexra delegation payload to Bedrock InvokeAgent format,
    handles SigV4 signing, and maps the Bedrock response back to
    Nexra's expected result format.

    Args:
        webhook_url: Bedrock agent runtime URL
        nexra_payload: Nexra delegation payload with task, delegation_id, etc.
        aws_credentials: Dict with 'access_key', 'secret_key', 'region'

    Returns:
        dict with 'result' key containing the Bedrock agent's response text

    Raises:
        NexraError: If Bedrock invocation fails
    """
    import boto3
    from core.errors import NexraError

    agent_id = extract_agent_id_from_url(webhook_url)
    if not agent_id:
        raise NexraError(
            400,
            "INVALID_BEDROCK_URL",
            f"Could not extract agent ID from Bedrock URL: {webhook_url}",
        )

    # Map Nexra payload to Bedrock InvokeAgent format
    task_input = nexra_payload.get("task", {}).get("input", {})
    input_text = task_input.get("prompt", str(task_input))

    bedrock_payload = {
        "agentId": agent_id,
        "agentAliasId": "TSTALIASID",
        "sessionId": nexra_payload.get("delegation_id", "default-session"),
        "inputText": input_text,
    }

    try:
        session = boto3.Session(
            aws_access_key_id=aws_credentials["access_key"],
            aws_secret_access_key=aws_credentials["secret_key"],
            region_name=aws_credentials["region"],
        )
        client = session.client("bedrock-agent-runtime")
        response = client.invoke_agent(**bedrock_payload)

        # Parse streaming response
        output_text = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                chunk_bytes = event["chunk"].get("bytes", b"")
                output_text += chunk_bytes.decode("utf-8")

        return {
            "result": output_text,
            "source": "bedrock",
            "agent_id": agent_id,
        }

    except Exception as e:
        logger.error(f"Bedrock invocation failed for agent {agent_id}: {e}")
        raise NexraError(
            503,
            "BEDROCK_INVOCATION_FAILED",
            f"Bedrock agent {agent_id} invocation failed: {str(e)}",
        )
```

---

### 5.8 `sdk/nexra-py/nexra/adapters/__init__.py`

**Path**: `nexra/sdk/nexra-py/nexra/adapters/__init__.py`

```python
from nexra.adapters.langgraph import nexra_tool, nexra_discover_tool
from nexra.adapters.crewai import NexraTool, NexraDiscoverTool
from nexra.adapters.bedrock import is_bedrock_endpoint, deliver_to_bedrock

__all__ = [
    "nexra_tool",
    "nexra_discover_tool",
    "NexraTool",
    "NexraDiscoverTool",
    "is_bedrock_endpoint",
    "deliver_to_bedrock",
]
```

---

### 5.9 `api/routers/agents.py` — A2A Agent Card Registration

**Path**: `nexra/api/routers/agents.py`

Add this endpoint to the existing agents router.

```python
import re


def _slugify(text: str) -> str:
    """Convert text to a URL-safe agent_id slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:64]


def _map_a2a_capabilities(capabilities: dict) -> str:
    """Map A2A Agent Card capabilities to Nexra capability_type enum.

    A2A capabilities are free-form. We map to the closest Nexra enum value.
    Falls back to 'other' if no match.
    """
    capability_keywords = {
        "research": ["research", "search", "investigate", "find"],
        "analysis": ["analysis", "analyze", "evaluate", "assess"],
        "generation": ["generate", "create", "write", "produce"],
        "enrichment": ["enrich", "augment", "enhance", "supplement"],
        "validation": ["validate", "verify", "check", "confirm"],
        "execution": ["execute", "run", "perform", "do"],
    }

    cap_text = str(capabilities).lower()
    for cap_type, keywords in capability_keywords.items():
        if any(kw in cap_text for kw in keywords):
            return cap_type
    return "other"


@router.post(
    "/agents/register/a2a",
    status_code=201,
    summary="Register an A2A-compliant agent",
    description=(
        "Accepts a Google A2A Agent Card and maps it to Nexra's registration "
        "format. A2A agents need no SDK changes — they register their Agent Card "
        "JSON and receive a Nexra agent_id back. "
        "Note: A2A Agent Cards use natural language descriptions, not typed "
        "JSON schemas. Nexra assigns passthrough schemas (type: object) for "
        "A2A agents. Schema validation is skipped for A2A-registered agents."
    ),
)
async def register_a2a_agent(
    agent_card: dict,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Register an A2A Agent Card as a Nexra agent.

    A2A Agent Card expected fields:
    - name (required): Agent display name
    - description (optional): Agent description
    - url (required): Agent's A2A endpoint URL
    - capabilities (optional): Dict of capability descriptions
    - skills (optional): List of skill descriptions

    Mapping:
    - agent_card.name → agent_id (slugified), name
    - agent_card.description → description
    - agent_card.url → webhook_url
    - agent_card.capabilities → capability_type (best-effort mapping)
    - input_schema/output_schema → passthrough (type: object)
    - pricing → 0.0 per call (A2A agents set their own pricing externally)
    - sla → default (30s p99, 0.99 availability)
    """
    from services.agent_service import AgentService
    from api.schemas.agents import AgentRegisterRequest

    if "name" not in agent_card:
        raise NexraError(400, "INVALID_A2A_CARD", "A2A Agent Card must include 'name'")
    if "url" not in agent_card:
        raise NexraError(400, "INVALID_A2A_CARD", "A2A Agent Card must include 'url'")

    nexra_payload = AgentRegisterRequest(
        agent_id=_slugify(agent_card["name"]),
        name=agent_card["name"],
        description=agent_card.get("description", agent_card["name"]),
        capability_type=_map_a2a_capabilities(
            agent_card.get("capabilities", {})
        ),
        webhook_url=agent_card["url"],
        webhook_secret=agent_card.get("webhook_secret", ""),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        pricing={"per_call_usd": 0.0},
        sla={"p99_latency_ms": 30000, "availability": 0.99},
        is_public=agent_card.get("is_public", False),
    )

    agent_service = AgentService(db)
    result = await agent_service.register(str(org.id), nexra_payload)
    return result
```

---

### 5.10 `sdk/nexra-ts/` — TypeScript SDK

**Path**: `nexra/sdk/nexra-ts/`

#### 5.10.1 `package.json`

```json
{
  "name": "nexra",
  "version": "0.1.0",
  "description": "Nexra TypeScript SDK — the control plane for AI agent networks",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist", "README.md", "LICENSE"],
  "scripts": {
    "build": "tsc",
    "prepublishOnly": "npm run build",
    "test": "jest"
  },
  "engines": {
    "node": ">=20"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.5",
    "@types/node": "^20"
  },
  "keywords": ["nexra", "ai-agents", "governance", "delegation", "a2a"],
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/nexra/nexra-ts"
  }
}
```

#### 5.10.2 `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "rootDir": "src",
    "declaration": true,
    "strict": true,
    "esModuleInterop": true,
    "sourceMap": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

#### 5.10.3 `src/types.ts`

```typescript
export interface NexraConfig {
  apiKey: string;
  agentId: string;
  baseUrl?: string;
  timeoutMs?: number;
}

export interface AgentMatch {
  agent_id: string;
  name: string;
  match_score: number;
  trust_score: number;
  status: string;
  pricing: { per_call_usd: number };
  sla: { p99_latency_ms: number; availability: number };
  is_cross_org: boolean;
}

export interface DiscoverRequest {
  query: string;
  capability_type?: string;
  budget_cap_usd?: number;
  max_latency_ms?: number;
  exclude_agents?: string[];
  include_cross_org?: boolean;
  limit?: number;
}

export interface DiscoverResponse {
  matches: AgentMatch[];
  latency_ms: number;
}

export interface DelegateRequest {
  callee_agent_id: string;
  task: Record<string, unknown>;
  context_scope?: string[];
  budget_cap_usd: number;
  timeout_ms?: number;
  callback_url?: string | null;
}

export interface PolicyResult {
  policy_id: string | null;
  policy_version: number | null;
  decision: string;
}

export interface UsageInfo {
  cost_usd: number;
  latency_ms: number;
  llm_tokens: number;
}

export interface DelegationResult {
  delegation_id: string;
  status: string;
  policy_result: PolicyResult;
  result: Record<string, unknown> | null;
  usage: UsageInfo | null;
}

export interface RegisterRequest {
  agent_id: string;
  name: string;
  description: string;
  capability_type: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  webhook_url: string;
  webhook_secret: string;
  pricing: { per_call_usd: number };
  sla: { p99_latency_ms: number; availability: number };
  is_public?: boolean;
}

export interface RegisterResult {
  agent_id: string;
  status: string;
  embedding_id: string;
  registered_at: string;
}

export interface NexraError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id?: string;
}
```

#### 5.10.4 `src/client.ts`

```typescript
import {
  NexraConfig,
  AgentMatch,
  DiscoverRequest,
  DiscoverResponse,
  DelegateRequest,
  DelegationResult,
  RegisterRequest,
  RegisterResult,
  NexraError as NexraErrorType,
} from "./types.js";

export class NexraApiError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly details: Record<string, unknown>;

  constructor(statusCode: number, error: NexraErrorType) {
    super(error.message);
    this.name = "NexraApiError";
    this.statusCode = statusCode;
    this.code = error.code;
    this.details = error.details;
  }
}

export class NexraClient {
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;

  constructor(config: NexraConfig) {
    this.baseUrl = config.baseUrl ?? "https://api.usenexra.com/v1";
    this.timeoutMs = config.timeoutMs ?? 60000;
    this.headers = {
      Authorization: `Bearer ${config.apiKey}`,
      "X-Agent-ID": config.agentId,
      "Content-Type": "application/json",
    };
  }

  private async request<T>(
    method: string,
    path: string,
    body?: Record<string, unknown>
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        method,
        headers: this.headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      const json = await response.json();

      if (!response.ok) {
        throw new NexraApiError(response.status, json.error);
      }

      return json.data as T;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  async register(params: RegisterRequest): Promise<RegisterResult> {
    return this.request<RegisterResult>("POST", "/agents/register", params);
  }

  async discover(params: DiscoverRequest): Promise<AgentMatch[]> {
    const response = await this.request<DiscoverResponse>(
      "POST",
      "/capabilities/discover",
      params
    );
    return response.matches;
  }

  async delegate(params: DelegateRequest): Promise<DelegationResult> {
    return this.request<DelegationResult>("POST", "/delegate", params);
  }

  async hire(
    capability: string,
    task: Record<string, unknown>,
    options?: {
      contextScope?: string[];
      budgetCap?: number;
      timeoutMs?: number;
    }
  ): Promise<DelegationResult> {
    const matches = await this.discover({
      query: capability,
      budget_cap_usd: options?.budgetCap,
      limit: 1,
    });

    if (matches.length === 0) {
      throw new Error(`No agents found for capability: ${capability}`);
    }

    return this.delegate({
      callee_agent_id: matches[0].agent_id,
      task,
      context_scope: options?.contextScope ?? [],
      budget_cap_usd: options?.budgetCap ?? 1.0,
      timeout_ms: options?.timeoutMs ?? 30000,
    });
  }

  async getDelegation(delegationId: string): Promise<DelegationResult> {
    return this.request<DelegationResult>(
      "GET",
      `/delegations/${delegationId}`
    );
  }
}
```

#### 5.10.5 `src/index.ts`

```typescript
export { NexraClient, NexraApiError } from "./client.js";
export type {
  NexraConfig,
  AgentMatch,
  DiscoverRequest,
  DiscoverResponse,
  DelegateRequest,
  DelegationResult,
  RegisterRequest,
  RegisterResult,
  PolicyResult,
  UsageInfo,
  NexraError,
} from "./types.js";
```

#### 5.10.6 `README.md`

```markdown
# nexra-ts — TypeScript SDK for Nexra

The control plane for AI agent networks.

## Installation

```bash
npm install nexra
```

## Quick Start

```typescript
import { NexraClient } from "nexra";

const client = new NexraClient({
  apiKey: "nx_live_...",
  agentId: "my-agent",
});

// Discover + delegate in one call
const result = await client.hire("research", {
  type: "research",
  input: { company_name: "Acme Corp" },
});

console.log(result.result);
```

## API

### `new NexraClient(config)`

| Param | Type | Required | Default |
|-------|------|----------|---------|
| `apiKey` | `string` | Yes | — |
| `agentId` | `string` | Yes | — |
| `baseUrl` | `string` | No | `https://api.usenexra.com/v1` |
| `timeoutMs` | `number` | No | `60000` |

### `client.register(params)` — Register an agent
### `client.discover(params)` — Discover agents by capability
### `client.delegate(params)` — Delegate a task to a specific agent
### `client.hire(capability, task, options?)` — Discover + delegate in one call
### `client.getDelegation(delegationId)` — Poll delegation status
```

---

## 6. Guardrails

1. **DO NOT** expose raw SQL in analytics endpoints. All queries use SQLAlchemy ORM/Core.
2. **DO NOT** allow SIEM export to include the `api_key_hash` or `jwt_secret_enc` fields. These are filtered out in `_format_event()`.
3. **DO NOT** allow SIEM webhook_url to be HTTP (non-TLS). Validate HTTPS at configuration time.
4. **DO NOT** store SIEM auth tokens in plaintext in the database. The `auth_header` field in `siem_config` should be encrypted at rest (AES-GCM) in a future iteration. For P1, it's stored in JSONB — acceptable for initial release.
5. **DO NOT** allow the SIEM worker to block on a single org's failed delivery. Catch exceptions per-org and continue to the next.
6. **DO NOT** use `asyncio.run()` in the LangGraph adapter — it's already async. Only the CrewAI adapter needs the sync bridge.
7. **DO NOT** generate webhook_secret for A2A agents. A2A agents must provide their own or leave empty (HMAC signing skipped for agents with empty webhook_secret).
8. **DO NOT** publish the nexra-ts SDK to npm until Phase 9 (deploy) is complete and the API is live.

---

## 7. Verification Checklist

Status source of truth: `CONVERGENCE_CHECKLIST.md` and `docs/baseline/evidence/*`.

### Dashboard API
- [x] `GET /v1/dashboard/volume` returns hourly time-series data
- [x] `GET /v1/dashboard/cost-breakdown` returns per-agent cost breakdown
- [x] `GET /v1/dashboard/failure-rates` returns failure rate per agent
- [x] `GET /v1/dashboard/trust-leaderboard` returns agents sorted by trust score
- [x] `GET /v1/dashboard/budget-alerts` returns agents with >80% budget utilization
- [x] `GET /v1/dashboard/network-graph` returns nodes and edges for graph rendering
- [x] All dashboard endpoints are org-scoped (no cross-org data leakage)
- [x] All dashboard endpoints handle empty data gracefully (no 500 errors)

### SIEM Export
- [x] `POST /v1/siem/config` saves SIEM configuration to org
- [x] `GET /v1/siem/config` returns current SIEM configuration
- [x] SIEM worker exports new audit events every 60 seconds
- [x] SIEM worker maintains cursor in Redis (no duplicate exports)
- [x] Splunk format includes `sourcetype`, `source`, `host` fields
- [x] Datadog format includes `ddsource`, `ddtags` fields
- [x] Elastic format includes `@timestamp`, `_index` fields
- [x] SIEM worker handles delivery failures gracefully (retries next cycle)
- [x] Event type filtering works (only configured types exported)

### Framework Adapters
- [x] LangGraph `nexra_tool()` returns a valid `@tool` function
- [x] LangGraph tool executes `client.hire()` and returns result dict
- [x] CrewAI `NexraTool._run()` executes synchronously via `asyncio.run()`
- [x] CrewAI tool returns string representation of result
- [x] Bedrock `is_bedrock_endpoint()` correctly identifies Bedrock URLs
- [x] Bedrock `deliver_to_bedrock()` maps Nexra payload to InvokeAgent format
- [x] A2A `/agents/register/a2a` accepts Agent Card and creates Nexra agent
- [x] A2A registration maps capabilities to closest Nexra capability_type

### nexra-ts SDK
- [x] `tsc` compiles without errors
- [x] `dist/` contains `.js` and `.d.ts` files
- [ ] `NexraClient.hire()` calls discover then delegate
- [ ] `NexraClient.register()` sends correct payload
- [ ] `NexraApiError` includes status code, error code, and details

---

## 8. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-DASH-001 | Dashboard | Volume endpoint returns hourly buckets | Series points have hourly timestamps |
| T-DASH-002 | Dashboard | Cost breakdown sums correctly | `total_cost_usd == sum(by_agent[].total_cost_usd)` |
| T-DASH-003 | Dashboard | Failure rates computed correctly | `failure_rate == failed / total` |
| T-DASH-004 | Dashboard | Trust leaderboard sorted descending | `items[0].trust_score >= items[1].trust_score` |
| T-DASH-005 | Dashboard | Budget alerts only include >80% utilization | All items have `utilization_pct >= 80` |
| T-DASH-006 | Dashboard | Network graph edges match delegation data | Edge count matches delegation count between agent pairs |
| T-DASH-007 | Dashboard | Org isolation — no cross-org data | Query with org_a key returns no org_b data |
| T-SIEM-001 | SIEM | Config saved and retrievable | `GET /siem/config` returns saved values |
| T-SIEM-002 | SIEM | Worker exports new events | Mock SIEM endpoint receives events |
| T-SIEM-003 | SIEM | Cursor advances after successful export | Redis cursor updated to last event ID |
| T-SIEM-004 | SIEM | Cursor does NOT advance on delivery failure | Redis cursor unchanged |
| T-SIEM-005 | SIEM | Event type filtering works | Only configured types in exported batch |
| T-SIEM-006 | SIEM | Splunk format correct | Event has `sourcetype`, `source`, `host` |
| T-SIEM-007 | SIEM | Disabled SIEM config → no export | Worker skips org with `enabled: false` |
| T-ADAPT-001 | LangGraph | `nexra_tool()` returns callable | `callable(nexra_tool(client))` is True |
| T-ADAPT-002 | LangGraph | Tool executes hire and returns dict | Mock client.hire called, result returned |
| T-ADAPT-003 | CrewAI | `NexraTool._run()` returns string | `isinstance(result, str)` |
| T-ADAPT-004 | CrewAI | Tool bridges async to sync | `asyncio.run()` called with correct coro |
| T-ADAPT-005 | Bedrock | `is_bedrock_endpoint()` detects patterns | Returns True for bedrock-agent-runtime URLs |
| T-ADAPT-006 | Bedrock | Payload mapping correct | `agentId` extracted from URL, `inputText` from task |
| T-ADAPT-007 | A2A | Agent Card registration creates agent | Agent exists in DB with mapped fields |
| T-ADAPT-008 | A2A | Missing name in Agent Card → 400 | `NexraError(400, 'INVALID_A2A_CARD')` |
| T-SDK-TS-001 | nexra-ts | `tsc` compiles without errors | Exit code 0 |
| T-SDK-TS-002 | nexra-ts | `hire()` calls discover then delegate | Two fetch calls made in sequence |
| T-SDK-TS-003 | nexra-ts | API error mapped to `NexraApiError` | Error has `statusCode`, `code`, `details` |
