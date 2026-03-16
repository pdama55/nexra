import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.common import DataResponse, MetaResponse
from db.session import get_db
from models.organization import Organization
from services.siem_service import SIEMService

router = APIRouter(prefix="/siem", tags=["siem"])


class SIEMConfigRequest(BaseModel):
    target: str = Field(..., description="splunk | datadog | elastic | generic")
    endpoint: str = Field(..., description="SIEM ingestion endpoint URL")
    api_key: str | None = Field(None, description="API key for authentication")
    enabled: bool = Field(True)
    event_types: list[str] = Field(
        default_factory=list,
        description="Optional allow-list of audit event types; empty means all",
    )


@router.post("/config", response_model=DataResponse[dict])
async def set_siem_config(
    request: Request,
    body: SIEMConfigRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Configure SIEM export for the organization."""
    start = time.perf_counter()
    org_id = str(org.id)
    service = SIEMService(db)
    await service.set_config(
        org_id=org_id,
        target=body.target,
        endpoint=body.endpoint,
        api_key=body.api_key,
        enabled=body.enabled,
        event_types=body.event_types,
    )
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "org_id": org_id,
            "target": body.target,
            "enabled": body.enabled,
            "event_types": body.event_types,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/config", response_model=DataResponse[dict])
async def get_siem_config(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get current SIEM configuration."""
    start = time.perf_counter()
    org_id = str(org.id)
    service = SIEMService(db)
    config = await service.get_config(org_id)
    if not config:
        safe_config: dict[str, object] = {}
    else:
        safe_config = {
            "target": config.target,
            "endpoint": config.endpoint,
            "enabled": config.enabled,
            "event_types": config.event_types,
            "cursor": config.cursor.isoformat() if config.cursor else None,
            "updated_at": config.updated_at.isoformat(),
        }
    if config and config.api_key:
        safe_config["api_key_set"] = True
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": safe_config,
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
