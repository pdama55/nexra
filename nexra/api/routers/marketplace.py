from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from db.session import get_db
from models.organization import Organization
from services.marketplace_service import MarketplaceService

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/connect-onboard")
async def connect_onboard(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Initiate Stripe Connect Express onboarding for the organization."""
    service = MarketplaceService(db)
    onboarding_url = await service.initiate_connect_onboarding(org)
    return {"data": {"onboarding_url": onboarding_url}}


@router.get("/connect-status")
async def connect_status(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
):
    """Check Stripe Connect onboarding status."""
    return {
        "data": {
            "org_id": str(org.id),
            "stripe_connect_account_id": org.stripe_connect_account_id,
            "onboarded": org.stripe_connect_account_id is not None,
        }
    }
