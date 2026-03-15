import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.common import MetaResponse
from db.session import get_db
from models.organization import Organization

router = APIRouter(prefix="/siem", tags=["siem"])

_siem_configs: dict[str, dict] = {}


class SIEMConfigRequest(BaseModel):
    target: str = Field(..., description="splunk | datadog | elastic | generic")
    endpoint: str = Field(..., description="SIEM ingestion endpoint URL")
    api_key: str | None = Field(None, description="API key for authentication")
    enabled: bool = Field(True)


@router.post("/config")
async def set_siem_config(
    request: Request,
    body: SIEMConfigRequest,
    org: Organization = Depends(get_authenticated_org),
):
    """Configure SIEM export for the organization."""
    org_id = str(org.id)
    _siem_configs[org_id] = {
        "target": body.target,
        "endpoint": body.endpoint,
        "api_key": body.api_key,
        "enabled": body.enabled,
    }
    return {
        "data": {"org_id": org_id, "target": body.target, "enabled": body.enabled},
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.get("/config")
async def get_siem_config(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
):
    """Get current SIEM configuration."""
    org_id = str(org.id)
    config = _siem_configs.get(org_id, {})
    safe_config = {k: v for k, v in config.items() if k != "api_key"}
    if config.get("api_key"):
        safe_config["api_key_set"] = True
    return {
        "data": safe_config,
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }
