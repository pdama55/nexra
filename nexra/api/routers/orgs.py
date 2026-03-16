import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org
from api.schemas.common import DataResponse, MetaResponse
from core.config import get_settings
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from db.session import get_db
from models.organization import Organization

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field("starter", description="starter | growth | enterprise")


class OrgCreateResponse(BaseModel):
    org_id: str
    name: str
    plan: str
    api_key: str


class OrgSettingsResponse(BaseModel):
    org_id: str
    name: str
    plan: str
    approval_url: str | None
    stripe_connect_account_id: str | None
    created_at: str


class OrgSettingsUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    approval_url: str | None = None


@router.post("/register", status_code=201, response_model=DataResponse[dict])
async def create_organization(
    request: Request,
    body: OrgCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization and return its API key.

    The API key is returned exactly once in this response.
    It is bcrypt-hashed before storage and cannot be retrieved again.
    """
    settings = get_settings()

    raw_key, hashed_key, prefix = generate_api_key()
    jwt_secret = generate_org_jwt_secret()
    jwt_secret_enc = encrypt_aes_gcm(jwt_secret, settings.secret_key_encryption_key)

    org = Organization(
        name=body.name,
        plan=body.plan,
        api_key_hash=hashed_key,
        api_key_prefix=prefix,
        jwt_secret_enc=jwt_secret_enc,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return {
        "data": OrgCreateResponse(
            org_id=str(org.id),
            name=org.name,
            plan=org.plan,
            api_key=raw_key,
        ).model_dump(),
        "meta": {
            "request_id": getattr(request.state, "request_id", None),
        },
    }


@router.get("/me", response_model=DataResponse[dict])
async def get_org_settings(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
):
    start = time.perf_counter()
    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": OrgSettingsResponse(
            org_id=str(org.id),
            name=org.name,
            plan=org.plan,
            approval_url=org.approval_url,
            stripe_connect_account_id=org.stripe_connect_account_id,
            created_at=org.created_at.isoformat(),
        ).model_dump(),
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.patch("/me", response_model=DataResponse[dict])
async def update_org_settings(
    request: Request,
    body: OrgSettingsUpdateRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        org.name = body.name
    if body.approval_url is not None:
        org.approval_url = body.approval_url

    await db.commit()
    await db.refresh(org)
    return {
        "data": {
            "org_id": str(org.id),
            "name": org.name,
            "approval_url": org.approval_url,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }
