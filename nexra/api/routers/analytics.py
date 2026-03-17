import time
import csv
import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import RequestActor, get_authenticated_org, require_roles
from api.schemas.common import DataResponse, MetaResponse
from core.errors import INVALID_REQUEST, NexraError
from db.session import get_db
from models.agent import Agent
from models.agent_budget import AgentBudget
from models.delegation import Delegation
from models.organization import Organization
from services.budget_service import BudgetService

router = APIRouter(tags=["analytics"])


def _window_start(window: str) -> datetime:
    now = datetime.now(UTC)
    if window == "last_hour":
        return now - timedelta(hours=1)
    if window == "last_24h":
        return now - timedelta(hours=24)
    if window == "last_7d":
        return now - timedelta(days=7)
    if window == "last_30d":
        return now - timedelta(days=30)
    raise NexraError(400, INVALID_REQUEST, "window must be one of: last_hour,last_24h,last_7d,last_30d")


@router.get("/analytics/usage", response_model=DataResponse[Any])
async def usage_stats(
    request: Request,
    window: str = Query("last_24h"),
    bucket: str | None = Query(None, description="hour|day for timeseries buckets"),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard usage endpoint.

    - No bucket: returns aggregate usage stats for the requested window.
    - bucket=hour|day: returns timeseries buckets (completed/blocked/failed/total).
    """
    start = time.perf_counter()
    window_start = _window_start(window)
    org_id = str(org.id)

    if bucket is not None:
        if bucket not in ("hour", "day"):
            raise NexraError(400, INVALID_REQUEST, "bucket must be 'hour' or 'day'")
        trunc = "hour" if bucket == "hour" else "day"
        result = await db.execute(
            text(f"""
                SELECT
                    date_trunc('{trunc}', created_at) AS ts,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
                    SUM(CASE WHEN status IN ('failed', 'timeout') THEN 1 ELSE 0 END) AS failed,
                    COUNT(*) AS total
                FROM delegations
                WHERE caller_org_id = CAST(:org_id AS uuid)
                  AND created_at >= :window_start
                GROUP BY ts
                ORDER BY ts ASC
            """),
            {"org_id": org_id, "window_start": window_start},
        )
        rows = result.fetchall()
        latency = round((time.perf_counter() - start) * 1000, 2)
        return {
            "data": [
                {
                    "timestamp": row.ts.isoformat(),
                    "completed": int(row.completed or 0),
                    "blocked": int(row.blocked or 0),
                    "failed": int(row.failed or 0),
                    "total": int(row.total or 0),
                }
                for row in rows
            ],
            "meta": MetaResponse(
                request_id=getattr(request.state, "request_id", None),
                latency_ms=latency,
            ).model_dump(),
        }

    result = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total_delegations,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status IN ('failed', 'timeout') THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
                SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) AS timed_out,
                SUM(CASE WHEN status = 'completed' THEN COALESCE(actual_cost_usd, 0) ELSE 0 END) AS total_cost_usd,
                AVG(CASE WHEN status = 'completed' THEN latency_ms END) AS avg_latency_ms
            FROM delegations
            WHERE caller_org_id = CAST(:org_id AS uuid)
              AND created_at >= :window_start
        """),
        {"org_id": org_id, "window_start": window_start},
    )
    row = result.one()
    total = int(row.total_delegations or 0)
    completed = int(row.completed or 0)
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "total_delegations": total,
            "completed": completed,
            "failed": int(row.failed or 0),
            "blocked": int(row.blocked or 0),
            "timed_out": int(row.timed_out or 0),
            "success_rate": round((completed / total), 4) if total > 0 else 0.0,
            "total_cost_usd": float(row.total_cost_usd or 0),
            "avg_latency_ms": int(round(float(row.avg_latency_ms or 0))),
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/spend/summary", response_model=DataResponse[dict[str, Any]])
async def spend_summary(
    request: Request,
    agent_id: str | None = Query(None),
    window: str = Query("last_24h"),
    breakdown: str = Query(
        "all",
        description="all|summary|agent|team|workflow|timeseries|totals",
    ),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """CFO-facing spend summary by agent and period."""
    start = time.perf_counter()
    if breakdown not in {"all", "summary", "agent", "team", "workflow", "timeseries", "totals"}:
        raise NexraError(
            400,
            INVALID_REQUEST,
            "breakdown must be one of: all,summary,agent,team,workflow,timeseries,totals",
        )

    service = BudgetService(db)
    org_id = str(org.id)
    summary_rows = await service.get_summary(org_id, agent_id)

    window_start = _window_start(window)
    bucket = "day" if window in ("last_7d", "last_30d") else "hour"

    totals_stmt = select(
        func.coalesce(func.sum(Delegation.actual_cost_usd), 0),
        func.count(Delegation.id),
        func.coalesce(func.avg(Delegation.actual_cost_usd), 0),
    ).where(
        Delegation.caller_org_id == org.id,
        Delegation.created_at >= window_start,
        Delegation.status == "completed",
    )
    if agent_id:
        totals_stmt = totals_stmt.where(Delegation.caller_agent_id == agent_id)

    totals_result = await db.execute(totals_stmt)
    total_spend_raw, delegation_count_raw, avg_cost_raw = totals_result.one()

    series_sql = text(f"""
        SELECT
            date_trunc('{bucket}', created_at) AS ts,
            COALESCE(SUM(actual_cost_usd), 0) AS spend_usd,
            COUNT(*) AS delegation_count
        FROM delegations
        WHERE caller_org_id = CAST(:org_id AS uuid)
          AND created_at >= :window_start
          AND status = 'completed'
          { "AND caller_agent_id = :agent_id" if agent_id else "" }
        GROUP BY ts
        ORDER BY ts ASC
    """)
    series_result = await db.execute(
        series_sql,
        {
            "org_id": org_id,
            "window_start": window_start,
            **({"agent_id": agent_id} if agent_id else {}),
        },
    )
    timeseries = [
        {
            "timestamp": row.ts.isoformat(),
            "spend_usd": float(row.spend_usd or 0),
            "delegation_count": int(row.delegation_count or 0),
        }
        for row in series_result.fetchall()
    ]

    agent_stmt = select(
        Delegation.caller_agent_id,
        func.count(Delegation.id).label("delegation_count"),
        func.coalesce(func.sum(Delegation.actual_cost_usd), 0).label("total_spend_usd"),
        func.coalesce(func.avg(Delegation.actual_cost_usd), 0).label("avg_cost_usd"),
    ).where(
        Delegation.caller_org_id == org.id,
        Delegation.created_at >= window_start,
        Delegation.status == "completed",
    ).group_by(Delegation.caller_agent_id).order_by(text("total_spend_usd DESC"))
    if agent_id:
        agent_stmt = agent_stmt.where(Delegation.caller_agent_id == agent_id)
    agent_result = await db.execute(agent_stmt)
    agent_breakdown = [
        {
            "agent_id": row.caller_agent_id,
            "delegation_count": int(row.delegation_count or 0),
            "total_spend_usd": float(row.total_spend_usd or 0),
            "avg_cost_usd": float(row.avg_cost_usd or 0),
        }
        for row in agent_result.fetchall()
    ]

    team_sql = text("""
        SELECT
            COALESCE(a.team, 'unassigned') AS team,
            COUNT(d.id) AS delegation_count,
            COALESCE(SUM(d.actual_cost_usd), 0) AS total_spend_usd,
            COALESCE(AVG(d.actual_cost_usd), 0) AS avg_cost_usd
        FROM delegations d
        LEFT JOIN agents a
          ON a.org_id = d.caller_org_id
         AND a.agent_id = d.caller_agent_id
        WHERE d.caller_org_id = CAST(:org_id AS uuid)
          AND d.created_at >= :window_start
          AND d.status = 'completed'
          {agent_filter}
        GROUP BY team
        ORDER BY total_spend_usd DESC
    """.replace("{agent_filter}", "AND d.caller_agent_id = :agent_id" if agent_id else ""))
    team_result = await db.execute(
        team_sql,
        {
            "org_id": org_id,
            "window_start": window_start,
            **({"agent_id": agent_id} if agent_id else {}),
        },
    )
    team_breakdown = [
        {
            "team": str(row.team or "unassigned"),
            "delegation_count": int(row.delegation_count or 0),
            "total_spend_usd": float(row.total_spend_usd or 0),
            "avg_cost_usd": float(row.avg_cost_usd or 0),
        }
        for row in team_result.fetchall()
    ]

    workflow_stmt = select(
        Delegation.workflow,
        func.count(Delegation.id).label("delegation_count"),
        func.coalesce(func.sum(Delegation.actual_cost_usd), 0).label("total_spend_usd"),
        func.coalesce(func.avg(Delegation.actual_cost_usd), 0).label("avg_cost_usd"),
    ).where(
        Delegation.caller_org_id == org.id,
        Delegation.created_at >= window_start,
        Delegation.status == "completed",
    ).group_by(Delegation.workflow).order_by(text("total_spend_usd DESC"))
    if agent_id:
        workflow_stmt = workflow_stmt.where(Delegation.caller_agent_id == agent_id)
    workflow_result = await db.execute(workflow_stmt)
    workflow_breakdown = [
        {
            "workflow": row.workflow or "unclassified",
            "delegation_count": int(row.delegation_count or 0),
            "total_spend_usd": float(row.total_spend_usd or 0),
            "avg_cost_usd": float(row.avg_cost_usd or 0),
        }
        for row in workflow_result.fetchall()
    ]

    total_cap = sum(float(item.get("cap_usd", 0)) for item in summary_rows)
    total_budget_spent = sum(float(item.get("spent_usd", 0)) for item in summary_rows)
    highest = agent_breakdown[0] if agent_breakdown else None

    totals = {
        "total_spend_usd": float(total_spend_raw or 0),
        "delegation_count": int(delegation_count_raw or 0),
        "avg_cost_per_delegation": float(avg_cost_raw or 0),
        "highest_spend_agent": (
            {"agent_id": highest["agent_id"], "spend_usd": highest["total_spend_usd"]}
            if highest
            else None
        ),
        "budget_utilization": (total_budget_spent / total_cap) if total_cap > 0 else 0.0,
    }

    data: dict[str, Any] = {
        "summary": summary_rows,
        "totals": totals,
        "agent_breakdown": agent_breakdown,
        "team_breakdown": team_breakdown,
        "workflow_breakdown": workflow_breakdown,
        "timeseries": timeseries,
    }
    if breakdown == "summary":
        data = {"summary": summary_rows}
    elif breakdown == "agent":
        data = {"agent_breakdown": agent_breakdown}
    elif breakdown == "team":
        data = {"team_breakdown": team_breakdown}
    elif breakdown == "workflow":
        data = {"workflow_breakdown": workflow_breakdown}
    elif breakdown == "timeseries":
        data = {"timeseries": timeseries}
    elif breakdown == "totals":
        data = {"totals": totals}

    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": data,
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/spend/summary/export")
async def export_spend_summary_csv(
    request: Request,
    agent_id: str | None = Query(None),
    window: str = Query("last_24h"),
    breakdown: str = Query("all", description="all|agent|team|workflow|timeseries|totals"),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    if breakdown not in {"all", "agent", "team", "workflow", "timeseries", "totals"}:
        raise NexraError(
            400,
            INVALID_REQUEST,
            "breakdown must be one of: all,agent,team,workflow,timeseries,totals",
        )

    payload = await spend_summary(
        request=request,
        agent_id=agent_id,
        window=window,
        breakdown="all" if breakdown == "all" else breakdown,
        org=org,
        db=db,
    )
    data = payload["data"]

    out = io.StringIO()
    writer = csv.writer(out)

    def write_agent_rows() -> None:
        writer.writerow(["section", "agent_id", "delegation_count", "total_spend_usd", "avg_cost_usd"])
        for row in data.get("agent_breakdown", []):
            writer.writerow(
                ["agent", row.get("agent_id"), row.get("delegation_count"), row.get("total_spend_usd"), row.get("avg_cost_usd")]
            )

    def write_team_rows() -> None:
        writer.writerow(["section", "team", "delegation_count", "total_spend_usd", "avg_cost_usd"])
        for row in data.get("team_breakdown", []):
            writer.writerow(
                ["team", row.get("team"), row.get("delegation_count"), row.get("total_spend_usd"), row.get("avg_cost_usd")]
            )

    def write_workflow_rows() -> None:
        writer.writerow(["section", "workflow", "delegation_count", "total_spend_usd", "avg_cost_usd"])
        for row in data.get("workflow_breakdown", []):
            writer.writerow(
                [
                    "workflow",
                    row.get("workflow"),
                    row.get("delegation_count"),
                    row.get("total_spend_usd"),
                    row.get("avg_cost_usd"),
                ]
            )

    def write_timeseries_rows() -> None:
        writer.writerow(["section", "timestamp", "spend_usd", "delegation_count"])
        for row in data.get("timeseries", []):
            writer.writerow(["timeseries", row.get("timestamp"), row.get("spend_usd"), row.get("delegation_count")])

    def write_totals_rows() -> None:
        totals = data.get("totals", {}) if isinstance(data.get("totals"), dict) else {}
        writer.writerow(["section", "metric", "value"])
        for metric, value in totals.items():
            if isinstance(value, dict):
                writer.writerow(["totals", metric, str(value)])
            else:
                writer.writerow(["totals", metric, value])

    if breakdown in {"all", "agent"}:
        write_agent_rows()
    if breakdown in {"all", "team"}:
        write_team_rows()
    if breakdown in {"all", "workflow"}:
        write_workflow_rows()
    if breakdown in {"all", "timeseries"}:
        write_timeseries_rows()
    if breakdown in {"all", "totals"}:
        write_totals_rows()

    body = out.getvalue()
    filename = f"spend-summary-{window}-{breakdown}.csv"
    return StreamingResponse(
        iter([body]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class SetBudgetCapRequest(BaseModel):
    agent_id: str = Field(..., description="Agent to set cap for")
    period_type: str = Field(..., description="'daily' or 'monthly'")
    cap_usd: float = Field(..., gt=0, description="Budget cap in USD")


@router.post("/spend/budget-cap", response_model=DataResponse[dict[str, Any]])
async def set_budget_cap(
    request: Request,
    body: SetBudgetCapRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin", "engineer")),
    db: AsyncSession = Depends(get_db),
):
    """Set a daily or monthly budget cap for an agent."""
    start = time.perf_counter()
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
    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": {
            "agent_id": body.agent_id,
            "period_type": body.period_type,
            "cap_usd": body.cap_usd,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/volume", response_model=DataResponse[list[dict[str, Any]]])
async def delegation_volume(
    request: Request,
    days: int = Query(7, ge=1, le=90),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Delegation volume over time."""
    start = time.perf_counter()
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
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": [{"day": row.day.isoformat(), "count": row.count} for row in rows],
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/cost-breakdown", response_model=DataResponse[list[dict[str, Any]]])
async def cost_breakdown(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Cost breakdown by agent."""
    start = time.perf_counter()
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
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": [{"agent_id": r.callee_agent_id, "total_cost": float(r.total_cost or 0), "count": r.count} for r in rows],
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/failure-rates", response_model=DataResponse[list[dict[str, Any]]])
async def failure_rates(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Failure rates by agent."""
    start = time.perf_counter()
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
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": [{"agent_id": r.callee_agent_id, "total": r.total, "failures": r.failures, "failure_rate": round(float(r.failures or 0) / r.total, 3) if r.total > 0 else 0} for r in rows],
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/trust-leaderboard", response_model=DataResponse[list[dict[str, Any]]])
async def trust_leaderboard(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agent trust score leaderboard."""
    start = time.perf_counter()
    result = await db.execute(
        select(Agent)
        .where(Agent.org_id == org.id)
        .order_by(Agent.trust_score.desc())
        .limit(limit)
    )
    agents = result.scalars().all()
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": [{"agent_id": a.agent_id, "trust_score": float(a.trust_score), "status": a.status, "delegation_count": a.delegation_count} for a in agents],
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/budget-alerts", response_model=DataResponse[list[dict[str, Any]]])
async def budget_alerts(
    request: Request,
    threshold: float = Query(0.8, ge=0, le=1.0, description="Alert when spent/cap exceeds this ratio"),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agents approaching budget caps."""
    start = time.perf_counter()
    result = await db.execute(
        select(AgentBudget).where(AgentBudget.org_id == org.id)
    )
    budgets = result.scalars().all()
    alerts = []
    for b in budgets:
        ratio = float(b.spent_usd) / float(b.cap_usd) if float(b.cap_usd) > 0 else 0
        if ratio >= threshold:
            alerts.append({"agent_id": b.agent_id, "period": str(b.period), "period_type": b.period_type, "spent_usd": float(b.spent_usd), "cap_usd": float(b.cap_usd), "ratio": round(ratio, 3)})
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": alerts,
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/dashboard/network-graph", response_model=DataResponse[dict[str, Any]])
async def network_graph(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Agent delegation network graph (edges = delegation relationships)."""
    start = time.perf_counter()
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
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {"edges": [{"source": r.caller_agent_id, "target": r.callee_agent_id, "weight": r.weight} for r in rows]},
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
