import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import RequestActor, get_authenticated_org, require_roles
from api.schemas.common import DataResponse, MetaResponse
from db.session import get_db
from models.organization import Organization
from services.marketplace_service import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/connect-onboard", response_model=DataResponse[dict])
async def connect_onboard(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Initiate Stripe Connect Express onboarding for the organization."""
    start = time.perf_counter()
    service = MarketplaceService(db)
    onboarding_url = await service.initiate_connect_onboarding(org)
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {"onboarding_url": onboarding_url},
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/connect-status", response_model=DataResponse[dict])
async def connect_status(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
):
    """Check Stripe Connect onboarding status."""
    start = time.perf_counter()
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "org_id": str(org.id),
            "stripe_connect_account_id": org.stripe_connect_account_id,
            "onboarded": org.stripe_connect_account_id is not None,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
