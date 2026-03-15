import time

from fastapi import APIRouter, Depends, Request
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org_and_agent
from api.schemas.capabilities import DiscoverRequest, DiscoverResponse
from api.schemas.common import DataResponse, MetaResponse
from core.config import get_settings
from db.session import get_db
from models.agent import Agent
from models.organization import Organization
from services.discovery_service import DiscoveryService

router = APIRouter(prefix="/capabilities", tags=["capabilities"])

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


@router.post("/discover")
async def discover_capabilities(
    request: Request,
    body: DiscoverRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
):
    """Discover agent capabilities via semantic search.

    Requires X-Agent-ID header. Returns ranked matches with composite score.
    """
    org, _caller_agent = org_and_agent
    start = time.perf_counter()

    service = DiscoveryService(db, _get_openai_client())
    matches, total_candidates, filtered_count = await service.discover(
        str(org.id), body
    )

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=DiscoverResponse(
            matches=matches,
            total_candidates=total_candidates,
            filtered_count=filtered_count,
            latency_ms=latency,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
