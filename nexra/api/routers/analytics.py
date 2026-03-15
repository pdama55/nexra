import time
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.common import MetaResponse
from core.errors import INVALID_REQUEST, NexraError
from db.session import get_db
from models.agent import Agent
from models.agent_budget import AgentBudget
from models.organization import Organization
from services.budget_service import BudgetService

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
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


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
    """Set a daily or monthly budget cap for an agent."""
    if body.period_type not in ("daily", "monthly"):
        raise NexraError(400, INVALID_REQUEST, "period_type must be 'daily' or 'monthly'")

    period = date.today() if body.period_type == "daily" else date.today().replace(day=1)

    stmt = (
        pg_insert(AgentBudget)
        .values(
            agent_id=body.agent_id,
            org_id=str(org.id),
            period=period,
            period_type=body.period_type,
            cap_usd=Decimal(str(body.cap_usd)),
            spent_usd=Decimal("0"),
        )
        .on_conflict_do_update(
            index_elements=["agent_id", "org_id", "period", "period_type"],
            set_={"cap_usd": Decimal(str(body.cap_usd))},
        )
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


@router.get("/dashboard/volume")
async def delegation_volume(
    request: Request,
    days: int = Query(7, ge=1, le=90),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Delegation volume over time."""
    result = await db.execute(
        text("""
            SELECT date_trunc('day', created_at) AS day, COUNT(*) AS count
            FROM delegations
            WHERE caller_org_id = CAST(:org_id AS uuid)
              AND created_at >= NOW() - make_interval(days => :days)
            GROUP BY day ORDER BY day
        """),
        {"org_id": str(org.id), "days": days},
    )
    rows = result.fetchall()
    return {"data": [{"day": row.day.isoformat(), "count": row.count} for row in rows]}


@router.get("/dashboard/cost-breakdown")
async def cost_breakdown(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Cost breakdown by agent."""
    result = await db.execute(
        text("""
            SELECT callee_agent_id, SUM(actual_cost_usd) AS total_cost, COUNT(*) AS count
            FROM delegations
            WHERE caller_org_id = CAST(:org_id AS uuid) AND status = 'completed'
            GROUP BY callee_agent_id ORDER BY total_cost DESC
        """),
        {"org_id": str(org.id)},
    )
    rows = result.fetchall()
    return {"data": [{"agent_id": r.callee_agent_id, "total_cost": float(r.total_cost or 0), "count": r.count} for r in rows]}


@router.get("/dashboard/failure-rates")
async def failure_rates(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Failure rates by agent."""
    result = await db.execute(
        text("""
            SELECT callee_agent_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status IN ('failed', 'timeout') THEN 1 ELSE 0 END) AS failures
            FROM delegations
            WHERE caller_org_id = CAST(:org_id AS uuid)
            GROUP BY callee_agent_id
        """),
        {"org_id": str(org.id)},
    )
    rows = result.fetchall()
    return {"data": [{"agent_id": r.callee_agent_id, "total": r.total, "failures": r.failures, "failure_rate": round(float(r.failures or 0) / r.total, 3) if r.total > 0 else 0} for r in rows]}


@router.get("/dashboard/trust-leaderboard")
async def trust_leaderboard(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agent trust score leaderboard."""
    result = await db.execute(
        select(Agent)
        .where(Agent.org_id == org.id)
        .order_by(Agent.trust_score.desc())
        .limit(limit)
    )
    agents = result.scalars().all()
    return {"data": [{"agent_id": a.agent_id, "trust_score": float(a.trust_score), "status": a.status, "delegation_count": a.delegation_count} for a in agents]}


@router.get("/dashboard/budget-alerts")
async def budget_alerts(
    request: Request,
    threshold: float = Query(0.8, ge=0, le=1.0, description="Alert when spent/cap exceeds this ratio"),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agents approaching budget caps."""
    result = await db.execute(
        select(AgentBudget).where(AgentBudget.org_id == org.id)
    )
    budgets = result.scalars().all()
    alerts = []
    for b in budgets:
        ratio = float(b.spent_usd) / float(b.cap_usd) if float(b.cap_usd) > 0 else 0
        if ratio >= threshold:
            alerts.append({"agent_id": b.agent_id, "period": str(b.period), "period_type": b.period_type, "spent_usd": float(b.spent_usd), "cap_usd": float(b.cap_usd), "ratio": round(ratio, 3)})
    return {"data": alerts}


@router.get("/dashboard/network-graph")
async def network_graph(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agent delegation network graph (edges = delegation relationships)."""
    result = await db.execute(
        text("""
            SELECT caller_agent_id, callee_agent_id, COUNT(*) AS weight
            FROM delegations
            WHERE caller_org_id = CAST(:org_id AS uuid) AND status = 'completed'
            GROUP BY caller_agent_id, callee_agent_id
        """),
        {"org_id": str(org.id)},
    )
    rows = result.fetchall()
    return {"data": {"edges": [{"source": r.caller_agent_id, "target": r.callee_agent_id, "weight": r.weight} for r in rows]}}
