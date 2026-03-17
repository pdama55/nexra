import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.common import DataResponse, MetaResponse
from db.session import get_db
from models.organization import Organization
from services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/log", response_model=DataResponse[dict[str, Any]])
async def query_audit_log(
    request: Request,
    agent_id: str | None = Query(None),
    actor_agent_id: str | None = Query(None),
    target_agent_id: str | None = Query(None),
    event_type: str | None = Query(None),
    policy_id: str | None = Query(None),
    policy_decision: str | None = Query(None, description="allow|block|pause"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    cost_min: float | None = Query(None, ge=0),
    cost_max: float | None = Query(None, ge=0),
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
        org_id=str(org.id),
        agent_id=agent_id,
        actor_agent_id=actor_agent_id,
        target_agent_id=target_agent_id,
        event_type=event_type,
        policy_id=policy_id,
        policy_decision=policy_decision,
        date_from=date_from,
        date_to=date_to,
        cost_min=cost_min,
        cost_max=cost_max,
        delegation_id=delegation_id,
        cursor=cursor,
        limit=limit,
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
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
