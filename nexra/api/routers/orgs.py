from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("/register", status_code=201)
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
