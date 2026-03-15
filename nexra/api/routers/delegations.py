import time

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org, get_authenticated_org_and_agent, get_redis
from api.schemas.common import DataResponse, MetaResponse
from api.schemas.delegations import (
    DelegateRequest,
    DelegationCompleteRequest,
    DelegationStatusResponse,
    PolicyResultResponse,
    UsageResponse,
)
from core.errors import DELEGATION_NOT_FOUND, NexraError
from db.session import get_db
from models.agent import Agent
from models.delegation import Delegation
from models.organization import Organization
from services.audit_service import AuditService
from services.budget_service import BudgetService
from services.delegation_service import DelegationService
from services.policy_engine import PolicyEngine
from services.trust_service import TrustService
from services.webhook_service import WebhookService

router = APIRouter(tags=["delegations"])


def _build_delegation_service(
    db: AsyncSession, redis_client: aioredis.Redis
) -> DelegationService:
    policy_engine = PolicyEngine(redis_client, db)
    webhook_service = WebhookService()
    budget_service = BudgetService(db)
    audit_service = AuditService(db)
    trust_service = TrustService(db)
    return DelegationService(
        db, redis_client, policy_engine, webhook_service,
        budget_service, audit_service, trust_service,
    )


@router.post("/delegate")
async def delegate(
    request: Request,
    body: DelegateRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Initiate a delegation (full 13-step flow).

    Requires X-Agent-ID header.
    """
    org, caller_agent = org_and_agent
    start = time.perf_counter()

    service = _build_delegation_service(db, redis_client)
    result = await service.initiate(org, caller_agent, body)

    latency = round((time.perf_counter() - start) * 1000, 2)

    status_code = 200 if result.status == "completed" else 202
    response_body = DataResponse(
        data=result,
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=response_body.model_dump(mode="json"),
    )


@router.get("/delegations/{delegation_id}")
async def get_delegation_status(
    request: Request,
    delegation_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Get delegation status and result."""
    start = time.perf_counter()

    service = _build_delegation_service(db, redis_client)
    delegation = await service.get_status(str(org.id), delegation_id)

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=DelegationStatusResponse(
            delegation_id=str(delegation.id),
            status=delegation.status,
            policy_result=PolicyResultResponse(
                policy_id=str(delegation.policy_id) if delegation.policy_id else None,
                policy_version=delegation.policy_version,
                decision=delegation.policy_decision or "",
            )
            if delegation.policy_id
            else None,
            result=delegation.result,
            usage=UsageResponse(
                cost_usd=float(delegation.actual_cost_usd or 0),
                latency_ms=delegation.latency_ms or 0,
                llm_tokens=delegation.llm_tokens,
            )
            if delegation.actual_cost_usd
            else None,
            created_at=delegation.created_at,
            completed_at=delegation.completed_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.post("/delegations/{delegation_id}/complete")
async def complete_delegation(
    request: Request,
    delegation_id: str,
    body: DelegationCompleteRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Callee posts result back to Nexra. Auth: Delegation JWT (not org API key)."""
    if not authorization.startswith("Bearer "):
        raise NexraError(401, "UNAUTHORIZED", "Missing Bearer token")

    token = authorization[7:]

    deleg_result = await db.execute(
        select(Delegation).where(Delegation.id == delegation_id)
    )
    delegation = deleg_result.scalar_one_or_none()
    if not delegation:
        raise NexraError(404, DELEGATION_NOT_FOUND, "Delegation not found")

    org_result = await db.execute(
        select(Organization).where(Organization.id == delegation.caller_org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise NexraError(500, "INTERNAL_ERROR", "Caller organization not found")

    service = _build_delegation_service(db, redis_client)
    resp = await service.complete(delegation_id, token, body.result, body.usage, org)

    return DataResponse(
        data=resp,
        meta=MetaResponse(request_id=getattr(request.state, "request_id", None)),
    )


@router.post("/delegations/{delegation_id}/approve")
async def approve_delegation(
    request: Request,
    delegation_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Approve a paused delegation (HiTL)."""
    from services.hitl_service import HiTLService

    service = HiTLService(db)
    delegation = await service.approve(delegation_id, str(org.id), "admin")
    return {"data": {"delegation_id": str(delegation.id), "status": delegation.status}}


@router.post("/delegations/{delegation_id}/reject")
async def reject_delegation(
    request: Request,
    delegation_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Reject a paused delegation (HiTL)."""
    from services.hitl_service import HiTLService

    service = HiTLService(db)
    delegation = await service.reject(delegation_id, str(org.id), "admin")
    return {"data": {"delegation_id": str(delegation.id), "status": delegation.status}}
