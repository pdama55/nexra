import time
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org, get_authenticated_org_and_agent, get_redis
from api.routers.delegations import _build_delegation_service
from api.schemas.capabilities import DiscoverRequest, DiscoverResponse
from api.schemas.common import DataResponse, MetaResponse
from api.schemas.delegations import DelegateRequest
from core.config import get_settings
from db.session import get_db
from models.agent import Agent
from models.audit_log import AuditLog
from models.delegation import Delegation
from models.organization import Organization
from services.discovery_service import DiscoveryService

router = APIRouter(prefix="/mcp", tags=["mcp"])

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


@router.get("/tools", response_model=DataResponse[dict[str, Any]])
async def list_mcp_tools(request: Request) -> dict[str, Any]:
    tools = [
        {
            "name": "discover_capabilities",
            "description": "Find best-fit agents by semantic query and hard constraints",
            "path": "/v1/mcp/tools/discover",
        },
        {
            "name": "delegate_task",
            "description": "Delegate task to an agent through policy/budget-governed flow",
            "path": "/v1/mcp/tools/delegate",
        },
        {
            "name": "read_governance_snapshot",
            "description": "Read governance status summary (delegations, pending approvals, anomalies)",
            "path": "/v1/mcp/tools/governance/read",
        },
    ]
    return {
        "data": {
            "protocol": "mcp",
            "tools": tools,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }


@router.post("/tools/discover")
async def mcp_discover(
    request: Request,
    body: DiscoverRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    org, _agent = org_and_agent
    started = time.perf_counter()
    service = DiscoveryService(db, _get_openai_client())
    matches, total_candidates, filtered_count = await service.discover(str(org.id), body)
    latency = round((time.perf_counter() - started) * 1000, 2)
    return {
        "data": {
            "tool": "discover_capabilities",
            "result": DiscoverResponse(
                matches=matches,
                total_candidates=total_candidates,
                filtered_count=filtered_count,
                latency_ms=latency,
            ).model_dump(mode="json"),
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.post("/tools/delegate")
async def mcp_delegate(
    request: Request,
    body: DelegateRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> JSONResponse:
    org, caller_agent = org_and_agent
    started = time.perf_counter()
    service = _build_delegation_service(db, redis_client)
    result = await service.initiate(org, caller_agent, body)
    latency = round((time.perf_counter() - started) * 1000, 2)

    response_body = DataResponse(
        data={
            "tool": "delegate_task",
            "result": result.model_dump(mode="json"),
        },
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
    status_code = 200 if result.status == "completed" else 202
    return JSONResponse(
        status_code=status_code,
        content=response_body.model_dump(mode="json"),
    )


@router.get("/tools/governance/read", response_model=DataResponse[dict[str, Any]])
async def mcp_governance_read(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    started = time.perf_counter()

    delegation_counts = await db.execute(
        select(
            func.count(Delegation.id).label("total"),
            func.count().filter(Delegation.status == "pending_approval").label("pending_approval"),
            func.count().filter(Delegation.status == "blocked").label("blocked"),
        ).where(Delegation.caller_org_id == org.id)
    )
    total, pending_approval, blocked = delegation_counts.one()

    anomaly_count = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.org_id == org.id,
            AuditLog.event_type == "anomaly_detected",
        )
    )

    latency = round((time.perf_counter() - started) * 1000, 2)
    return {
        "data": {
            "tool": "read_governance_snapshot",
            "org_id": str(org.id),
            "summary": {
                "delegation_total": int(total or 0),
                "pending_approval": int(pending_approval or 0),
                "blocked": int(blocked or 0),
                "anomaly_events": int(anomaly_count.scalar() or 0),
            },
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
