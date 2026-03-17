import time
import uuid as uuid_mod
import re
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.agents import (
    AgentDetailResponse,
    AgentListItem,
    AgentListResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
)
from api.schemas.common import DataResponse, MetaResponse
from core.config import get_settings
from core.errors import AGENT_NOT_FOUND, NexraError
from db.session import get_db
from models.organization import Organization
from models.trust_score_event import TrustScoreEvent
from services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])

_openai_client: AsyncOpenAI | None = None


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug[:64] or "a2a-agent"


def _map_a2a_capabilities(capabilities: dict | list | str | None) -> str:
    capability_keywords = {
        "research": ["research", "search", "investigate", "find"],
        "analysis": ["analysis", "analyze", "evaluate", "assess"],
        "generation": ["generate", "create", "write", "produce"],
        "enrichment": ["enrich", "augment", "enhance", "supplement"],
        "validation": ["validate", "verify", "check", "confirm"],
        "execution": ["execute", "run", "perform", "do"],
    }
    cap_text = str(capabilities or "").lower()
    for cap_type, keywords in capability_keywords.items():
        if any(kw in cap_text for kw in keywords):
            return cap_type
    return "other"


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


@router.post("/register")
async def register_agent(
    request: Request,
    body: AgentRegisterRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Register or re-register an agent capability.

    Idempotent on agent_id. New agents start with status='probationary'.
    """
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.register(str(org.id), body)
    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=AgentRegisterResponse(
            agent_id=agent.agent_id,
            status=agent.status,
            embedding_id=str(agent.id),
            registered_at=agent.created_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.post("/register/a2a")
async def register_a2a_agent(
    request: Request,
    agent_card: dict[str, Any] = Body(...),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Register a Google A2A-style agent card as a Nexra agent."""
    if "name" not in agent_card:
        raise NexraError(400, "INVALID_A2A_CARD", "A2A Agent Card must include 'name'")
    if "url" not in agent_card:
        raise NexraError(400, "INVALID_A2A_CARD", "A2A Agent Card must include 'url'")

    name = str(agent_card["name"])
    description = str(agent_card.get("description") or name)
    if len(description) < 20:
        description = f"{description} (A2A registered agent)"

    provided_secret = str(agent_card.get("webhook_secret") or "")
    webhook_secret = provided_secret if len(provided_secret) >= 32 else ("a2a-" + _slugify(name)).ljust(32, "x")

    payload = AgentRegisterRequest(
        agent_id=_slugify(name),
        name=name,
        description=description,
        capability_type=_map_a2a_capabilities(agent_card.get("capabilities") or agent_card.get("skills")),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        pricing={"per_call_usd": max(float(agent_card.get("per_call_usd", 0.0) or 0.0), 0.0)},
        sla={
            "p99_latency_ms": int(agent_card.get("p99_latency_ms", 30000)),
            "availability": float(agent_card.get("availability", 0.99)),
        },
        webhook_url=str(agent_card["url"]),
        webhook_secret=webhook_secret,
        is_public=bool(agent_card.get("is_public", False)),
    )

    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.register(str(org.id), payload)
    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=AgentRegisterResponse(
            agent_id=agent.agent_id,
            status=agent.status,
            embedding_id=str(agent.id),
            registered_at=agent.created_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.get("/registry", response_model=DataResponse[dict[str, Any]])
async def list_agents(
    request: Request,
    capability_type: str | None = Query(None),
    status: str | None = Query(None),
    is_public: bool | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """List registered agents for the authenticated org."""
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agents, next_cursor, total = await service.list_for_org(
        str(org.id), capability_type, status, is_public, cursor, limit
    )
    latency = round((time.perf_counter() - start) * 1000, 2)

    return {
        "data": AgentListResponse(
            agents=[
                AgentListItem(
                    id=str(a.id),
                    org_id=str(a.org_id),
                    agent_id=a.agent_id,
                    name=a.name,
                    description=a.description,
                    capability_type=a.capability_type,
                    input_schema=a.input_schema,
                    output_schema=a.output_schema,
                    webhook_url=a.webhook_url,
                    trust_score=float(a.trust_score),
                    status=a.status,
                    is_public=a.is_public,
                    delegation_count=a.delegation_count,
                    pricing=a.pricing,
                    sla=a.sla,
                    created_at=a.created_at,
                    updated_at=a.updated_at,
                )
                for a in agents
            ],
            next_cursor=next_cursor,
            total_count=total,
        ).model_dump(),
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/{agent_ref}")
async def get_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get agent details by UUID or agent_id."""
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())

    agent = None
    try:
        uuid_mod.UUID(agent_ref)
        agent = await service.get_by_uuid(str(org.id), agent_ref)
    except ValueError:
        agent = await service.get_by_agent_id(str(org.id), agent_ref)

    if not agent:
        raise NexraError(404, AGENT_NOT_FOUND, f"Agent '{agent_ref}' not found")

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=AgentDetailResponse(
            id=str(agent.id),
            agent_id=agent.agent_id,
            name=agent.name,
            description=agent.description,
            capability_type=agent.capability_type,
            input_schema=agent.input_schema,
            output_schema=agent.output_schema,
            pricing=agent.pricing,
            sla=agent.sla,
            webhook_url=agent.webhook_url,
            is_public=agent.is_public,
            trust_score=float(agent.trust_score),
            status=agent.status,
            delegation_count=agent.delegation_count,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.get("/{agent_ref}/trust", response_model=DataResponse[dict[str, Any]])
async def get_agent_trust(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get trust score and recent score events for an agent."""
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.get_by_agent_id(str(org.id), agent_ref)
    if not agent:
        raise NexraError(404, AGENT_NOT_FOUND, f"Agent '{agent_ref}' not found")

    events_result = await db.execute(
        select(TrustScoreEvent)
        .where(
            TrustScoreEvent.agent_id == agent.agent_id,
            TrustScoreEvent.org_id == org.id,
        )
        .order_by(TrustScoreEvent.created_at.desc())
        .limit(100)
    )
    events = list(events_result.scalars().all())
    latest_components = events[0].components if events else {}

    breakdown = {
        "success_rate": float(latest_components.get("success_rate", 0)),
        "sla_compliance": float(latest_components.get("sla_compliance", 0)),
        "cost_accuracy": float(latest_components.get("cost_accuracy", 0)),
        "policy_violations_inverse": float(latest_components.get("policy_violations_inverse", 0)),
        "policy_violations": int(latest_components.get("policy_violations", 0)),
        "delegation_count": int(latest_components.get("delegation_count", agent.delegation_count)),
    }
    timeseries = [
        {
            "score_before": float(e.score_before),
            "score_after": float(e.score_after),
            "created_at": e.created_at.isoformat(),
        }
        for e in reversed(events)
    ]
    last_active = events[0].created_at.isoformat() if events else None

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "agent_id": agent.agent_id,
            "trust_score": float(agent.trust_score),
            "status": agent.status,
            "delegation_count": agent.delegation_count,
            "last_active": last_active,
            "breakdown": breakdown,
            "timeseries": timeseries,
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
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.post("/{agent_ref}/quarantine")
async def quarantine_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Manually quarantine an agent."""
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.update_status(str(org.id), agent_ref, "quarantined")
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {"agent_id": agent.agent_id, "status": agent.status},
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.post("/{agent_ref}/activate")
async def activate_agent(
    request: Request,
    agent_ref: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Manually activate an agent."""
    start = time.perf_counter()
    service = AgentService(db, _get_openai_client())
    agent = await service.update_status(str(org.id), agent_ref, "active")
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {"agent_id": agent.agent_id, "status": agent.status},
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
