# Phase 7 — Budget Enforcement & Audit Log

> **TDD Sections**: §11 (Spend Metering & Budget Enforcement), §13 (Audit Log — Immutability & Structure), §10 (Trust Score — stub)
>
> **48-Hour Block**: Hours 31–35
>
> **Depends On**: Phase 6 (Delegation Flow) complete.

---

## 1. Prerequisites

- [ ] DelegationService — full 13-step flow working
- [ ] Delegation records created in DB with status transitions
- [ ] agent_budgets and audit_log tables exist (from Phase 1 migration)
- [ ] audit_log immutability trigger confirmed working

---

## 2. Objective

- BudgetService: check_and_reserve (with SELECT FOR UPDATE), settle (upsert daily/monthly spend)
- AuditService: append-only writes, cursor-paginated query, CSV export
- TrustService: stub that returns current trust_score (full implementation in Phase 10)
- Wire budget checks and audit logging into the delegation flow
- GET /audit/log endpoint with filters
- GET /spend/summary endpoint

---

## 3. File-by-File Implementation Guide

### 3.1 `services/budget_service.py`

**Path**: `nexra/services/budget_service.py`

```python
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models.agent_budget import AgentBudget


@dataclass
class BudgetCheckResult:
    allowed: bool
    reason: str  # '' if allowed, 'daily_cap'|'monthly_cap'|'per_delegation_cap' if not
    remaining_usd: float


class BudgetService:
    """Spend tracking and budget cap enforcement.

    Uses SELECT FOR UPDATE to prevent race conditions on concurrent delegations.

    Constructor dependencies:
        db: AsyncSession
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_and_reserve(
        self,
        org_id: str,
        agent_id: str,
        estimated_cost: float,
        request_cap: float,
    ) -> BudgetCheckResult:
        """Check if delegation is within budget caps.

        Checks in order:
        1. Per-delegation cap (from request)
        2. Daily cap (from agent_budgets table)
        3. Monthly cap (from agent_budgets table)

        Uses SELECT FOR UPDATE to lock budget rows during check.
        """
        # Check per-delegation cap
        if estimated_cost > request_cap:
            return BudgetCheckResult(
                allowed=False,
                reason="per_delegation_cap",
                remaining_usd=request_cap,
            )

        today = date.today()
        first_of_month = today.replace(day=1)

        async with self.db.begin_nested():
            # Check daily cap
            daily_result = await self.db.execute(
                select(AgentBudget)
                .where(
                    AgentBudget.agent_id == agent_id,
                    AgentBudget.org_id == org_id,
                    AgentBudget.period == today,
                    AgentBudget.period_type == "daily",
                )
                .with_for_update()
            )
            daily_row = daily_result.scalar_one_or_none()

            if daily_row:
                remaining = float(daily_row.cap_usd) - float(daily_row.spent_usd)
                if estimated_cost > remaining:
                    return BudgetCheckResult(
                        allowed=False,
                        reason="daily_cap",
                        remaining_usd=remaining,
                    )

            # Check monthly cap
            monthly_result = await self.db.execute(
                select(AgentBudget)
                .where(
                    AgentBudget.agent_id == agent_id,
                    AgentBudget.org_id == org_id,
                    AgentBudget.period == first_of_month,
                    AgentBudget.period_type == "monthly",
                )
                .with_for_update()
            )
            monthly_row = monthly_result.scalar_one_or_none()

            if monthly_row:
                remaining = float(monthly_row.cap_usd) - float(monthly_row.spent_usd)
                if estimated_cost > remaining:
                    return BudgetCheckResult(
                        allowed=False,
                        reason="monthly_cap",
                        remaining_usd=remaining,
                    )

        return BudgetCheckResult(
            allowed=True,
            reason="",
            remaining_usd=request_cap - estimated_cost,
        )

    async def settle(
        self, org_id: str, agent_id: str, actual_cost: float
    ) -> None:
        """Update spent_usd after delegation completes.

        Upserts both daily and monthly budget rows.
        """
        today = date.today()
        first_of_month = today.replace(day=1)

        for period, period_type in [(today, "daily"), (first_of_month, "monthly")]:
            stmt = pg_insert(AgentBudget).values(
                agent_id=agent_id,
                org_id=org_id,
                period=period,
                period_type=period_type,
                cap_usd=Decimal("999999"),  # Default high cap — real cap set via API
                spent_usd=Decimal(str(actual_cost)),
            ).on_conflict_do_update(
                index_elements=["agent_id", "org_id", "period", "period_type"],
                set_={
                    "spent_usd": AgentBudget.spent_usd + Decimal(str(actual_cost)),
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            await self.db.execute(stmt)

        await self.db.commit()

    async def get_summary(
        self, org_id: str, agent_id: str | None = None
    ) -> list[dict]:
        """Get spend summary for CFO dashboard."""
        q = select(AgentBudget).where(AgentBudget.org_id == org_id)
        if agent_id:
            q = q.where(AgentBudget.agent_id == agent_id)
        q = q.order_by(AgentBudget.period.desc())

        result = await self.db.execute(q)
        rows = result.scalars().all()

        return [
            {
                "agent_id": r.agent_id,
                "period": str(r.period),
                "period_type": r.period_type,
                "cap_usd": float(r.cap_usd),
                "spent_usd": float(r.spent_usd),
                "remaining_usd": float(r.cap_usd) - float(r.spent_usd),
            }
            for r in rows
        ]
```

### 3.2 `services/audit_service.py`

**Path**: `nexra/services/audit_service.py`

```python
import csv
import io
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from models.audit_log import AuditLog

logger = logging.getLogger("nexra.services.audit")


class AuditService:
    """Append-only audit log service.

    CRITICAL: This service ONLY performs INSERT operations on audit_log.
    No UPDATE. No DELETE. The DB trigger enforces this as defense-in-depth.

    Constructor dependencies:
        db: AsyncSession
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def append(
        self,
        org_id: str,
        event_type: str,
        actor_agent_id: str | None,
        target_agent_id: str | None,
        details: dict,
        delegation_id: str | None = None,
        cost_usd: float | None = None,
    ) -> AuditLog:
        """Append an immutable audit log entry."""
        entry = AuditLog(
            delegation_id=delegation_id,
            org_id=org_id,
            event_type=event_type,
            actor_agent_id=actor_agent_id,
            target_agent_id=target_agent_id,
            details=details,
            cost_usd=cost_usd,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def query(
        self,
        org_id: str,
        agent_id: str | None = None,
        event_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        delegation_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditLog], str | None]:
        """Query audit log with filters and cursor pagination."""
        q = select(AuditLog).where(AuditLog.org_id == org_id)

        if agent_id:
            from sqlalchemy import or_
            q = q.where(
                or_(AuditLog.actor_agent_id == agent_id, AuditLog.target_agent_id == agent_id)
            )
        if event_type:
            q = q.where(AuditLog.event_type == event_type)
        if date_from:
            q = q.where(AuditLog.created_at >= date_from)
        if date_to:
            q = q.where(AuditLog.created_at <= date_to)
        if delegation_id:
            q = q.where(AuditLog.delegation_id == delegation_id)
        if cursor:
            from datetime import datetime as _dt
            cursor_dt = _dt.fromisoformat(cursor)
            q = q.where(AuditLog.created_at < cursor_dt)

        q = q.order_by(AuditLog.created_at.desc()).limit(limit + 1)
        result = await self.db.execute(q)
        entries = list(result.scalars().all())

        next_cursor = None
        if len(entries) > limit:
            next_cursor = entries[limit - 1].created_at.isoformat()
            entries = entries[:limit]

        return entries, next_cursor

    async def export_csv(
        self, org_id: str, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> str:
        """Export audit log as CSV string for compliance."""
        entries, _ = await self.query(org_id, date_from=date_from, date_to=date_to, limit=10000)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "delegation_id", "event_type", "actor_agent_id",
            "target_agent_id", "cost_usd", "created_at", "details"
        ])
        for e in entries:
            writer.writerow([
                str(e.id), str(e.delegation_id), e.event_type,
                e.actor_agent_id, e.target_agent_id,
                str(e.cost_usd) if e.cost_usd else "",
                e.created_at.isoformat(),
                str(e.details),
            ])
        return output.getvalue()
```

### 3.3 `services/trust_service.py` (Stub)

**Path**: `nexra/services/trust_service.py`

Stub for MVP. Full implementation in Phase 10.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.agent import Agent


class TrustService:
    """Trust score management. Stub for MVP — full implementation in Phase 10."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_score(self, org_id: str, agent_id: str) -> float:
        """Get current trust score for an agent."""
        result = await self.db.execute(
            select(Agent.trust_score).where(
                Agent.org_id == org_id, Agent.agent_id == agent_id
            )
        )
        score = result.scalar_one_or_none()
        return float(score) if score is not None else 1.0

    async def update_after_delegation(self, agent_id: str, org_id: str, delegation) -> float:
        """Stub: returns current score without updating. Full impl in Phase 10."""
        return await self.get_score(org_id, agent_id)
```

### 3.4 `api/routers/audit.py`

**Path**: `nexra/api/routers/audit.py`

```python
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org, get_db
from api.schemas.common import MetaResponse
from services.audit_service import AuditService
from models.organization import Organization

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/log")
async def query_audit_log(
    request: Request,
    agent_id: str | None = Query(None),
    event_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    delegation_id: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    format: str = Query("json", description="json or csv"),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Query the immutable audit log."""
    start = time.perf_counter()
    service = AuditService(db)

    if format == "csv":
        csv_data = await service.export_csv(str(org.id), date_from, date_to)
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    entries, next_cursor = await service.query(
        str(org.id), agent_id, event_type, date_from, date_to, delegation_id, cursor, limit
    )
    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": {
            "entries": [
                {
                    "id": str(e.id),
                    "delegation_id": str(e.delegation_id) if e.delegation_id else None,
                    "event_type": e.event_type,
                    "actor_agent_id": e.actor_agent_id,
                    "target_agent_id": e.target_agent_id,
                    "details": e.details,
                    "cost_usd": float(e.cost_usd) if e.cost_usd else None,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
            ],
            "next_cursor": next_cursor,
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    }
```

### 3.5 `api/routers/analytics.py`

**Path**: `nexra/api/routers/analytics.py`

```python
import time
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org, get_db
from api.schemas.common import MetaResponse
from services.budget_service import BudgetService
from models.organization import Organization

router = APIRouter(tags=["analytics"])


@router.get("/spend/summary")
async def spend_summary(
    request: Request,
    agent_id: str | None = Query(None),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """CFO-facing spend summary by agent and period."""
    start = time.perf_counter()
    service = BudgetService(db)
    summary = await service.get_summary(str(org.id), agent_id)
    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": {"summary": summary},
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    }
```

### 3.6 Budget Cap Setting Endpoint

Add to `api/routers/analytics.py`:

```python
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models.agent_budget import AgentBudget


class SetBudgetCapRequest(BaseModel):
    agent_id: str = Field(..., description="Agent to set cap for")
    period_type: str = Field(..., description="'daily' or 'monthly'")
    cap_usd: float = Field(..., gt=0, description="Budget cap in USD")


@router.post("/spend/budget-cap")
async def set_budget_cap(
    request: Request,
    body: SetBudgetCapRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Set a daily or monthly budget cap for an agent.

    Without this, agents have no budget cap (default is $999,999).
    """
    if body.period_type not in ("daily", "monthly"):
        from core.errors import NexraError, INVALID_REQUEST
        raise NexraError(400, INVALID_REQUEST, "period_type must be 'daily' or 'monthly'")

    period = date.today() if body.period_type == "daily" else date.today().replace(day=1)

    stmt = pg_insert(AgentBudget).values(
        agent_id=body.agent_id,
        org_id=str(org.id),
        period=period,
        period_type=body.period_type,
        cap_usd=Decimal(str(body.cap_usd)),
        spent_usd=Decimal("0"),
    ).on_conflict_do_update(
        index_elements=["agent_id", "org_id", "period", "period_type"],
        set_={"cap_usd": Decimal(str(body.cap_usd))},
    )
    await db.execute(stmt)
    await db.commit()

    return {
        "data": {
            "agent_id": body.agent_id,
            "period_type": body.period_type,
            "cap_usd": body.cap_usd,
        },
    }
```

**Register both in `api/main.py`**:
```python
from api.routers.audit import router as audit_router
from api.routers.analytics import router as analytics_router
app.include_router(audit_router, prefix="/v1")
app.include_router(analytics_router, prefix="/v1")
```

---

## 4. Integration with Delegation Flow

Update `services/delegation_service.py` to wire in BudgetService, AuditService, and TrustService.

**Updated constructor** (replaces the Phase 6 constructor):
```python
class DelegationService:
    def __init__(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        policy_engine: PolicyEngine,
        webhook_service: WebhookService,
        budget_service: BudgetService,
        audit_service: AuditService,
        trust_service: TrustService,
    ) -> None:
        self.db = db
        self.redis = redis_client
        self.policy_engine = policy_engine
        self.webhook_service = webhook_service
        self.budget_service = budget_service
        self.audit_service = audit_service
        self.trust_service = trust_service
```

**Updated `_build_delegation_service` in `api/routers/delegations.py`**:
```python
from services.budget_service import BudgetService
from services.audit_service import AuditService
from services.trust_service import TrustService

def _build_delegation_service(db: AsyncSession, redis_client: aioredis.Redis) -> DelegationService:
    policy_engine = PolicyEngine(redis_client, db)
    webhook_service = WebhookService()
    budget_service = BudgetService(db)
    audit_service = AuditService(db)
    trust_service = TrustService(db)
    return DelegationService(
        db, redis_client, policy_engine, webhook_service,
        budget_service, audit_service, trust_service,
    )
```

**Exact integration points in `initiate()`**:

- **Step 5**: Replace the stub with:
  ```python
  budget_check = await self.budget_service.check_and_reserve(
      str(org.id), caller_agent.agent_id, estimated_cost, request.budget_cap_usd
  )
  if not budget_check.allowed:
      raise NexraError(
          402, BUDGET_EXCEEDED,
          f"Budget exceeded: {budget_check.reason}",
          {"remaining_budget_usd": budget_check.remaining_usd},
      )
  ```

- **Step 8** (after `self.db.add(delegation)` and `await self.db.commit()`):
  ```python
  await self.audit_service.append(
      org_id=str(org.id), event_type="policy_evaluated",
      actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
      details={"decision": decision.decision, "policy_id": decision.policy_id, "reason": decision.reason},
      delegation_id=str(delegation.id),
  )
  ```

- **Step 9 (block)** (before `raise NexraError`):
  ```python
  await self.audit_service.append(
      org_id=str(org.id), event_type="delegation_blocked",
      actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
      details={"reason": decision.reason, "policy_id": decision.policy_id},
      delegation_id=str(delegation.id),
  )
  ```

- **Step 12** (after setting status to `in_flight`):
  ```python
  await self.audit_service.append(
      org_id=str(org.id), event_type="delegation_initiated",
      actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
      details={"task_hash": delegation.task_hash, "budget_cap_usd": float(request.budget_cap_usd)},
      delegation_id=str(delegation.id),
  )
  ```

- **Step 13 (success)** (after updating delegation to completed):
  ```python
  await self.budget_service.settle(str(org.id), callee.agent_id, actual_cost)
  await self.trust_service.update_after_delegation(callee.agent_id, str(callee.org_id), delegation)
  await self.audit_service.append(
      org_id=str(org.id), event_type="delegation_completed",
      actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
      details={"result_keys": list(callee_response.get("result", {}).keys()) if isinstance(callee_response.get("result"), dict) else []},
      delegation_id=str(delegation.id), cost_usd=actual_cost,
  )
  ```

- **Step 13 (failure)** (in the `except NexraError` block):
  ```python
  event_type = "delegation_timeout" if e.code == "DELEGATION_TIMEOUT" else "delegation_failed"
  await self.audit_service.append(
      org_id=str(org.id), event_type=event_type,
      actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
      details={"error_code": e.code, "error_message": e.message},
      delegation_id=str(delegation.id),
  )
  ```

---

## 5. Guardrails

1. **DO NOT** perform UPDATE or DELETE on audit_log at any abstraction layer.
2. **DO NOT** skip SELECT FOR UPDATE on budget checks — race conditions will cause overspend.
3. **DO NOT** settle budget before delegation completes — only settle on success.
4. **DO NOT** return raw Decimal objects in JSON responses — always convert to float.
5. **DO NOT** allow negative spent_usd values.

---

## 6. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-006 | Budget | estimated_cost + spent > daily cap → 402 | BudgetCheckResult.allowed==False, reason='daily_cap' |
| T-007 | Budget | Concurrent delegations don't double-spend | SELECT FOR UPDATE prevents race. Final spent_usd is atomic. |
| T-BUD-003 | Budget | settle() upserts daily and monthly rows | Both rows exist after settle, spent_usd incremented |
| T-BUD-004 | Budget | No budget row → allowed (no cap configured) | BudgetCheckResult.allowed==True |
| T-013 | Audit | INSERT succeeds | Entry created with all fields |
| T-014 | Audit | UPDATE raises exception | DB trigger fires |
| T-AUD-003 | Audit | DELETE raises exception | DB trigger fires |
| T-AUD-004 | Audit | Query with filters returns correct entries | Filter by event_type, agent_id, date range |
| T-AUD-005 | Audit | Cursor pagination works | First page + next_cursor → second page |
| T-AUD-006 | Audit | CSV export contains all entries | Parse CSV, verify row count |
| T-AUD-007 | Audit | Delegation creates 3+ audit entries | policy_evaluated + delegation_initiated + delegation_completed |
