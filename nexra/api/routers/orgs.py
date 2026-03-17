import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    RequestActor,
    get_authenticated_org,
    get_request_actor,
    require_roles,
)
from api.schemas.common import DataResponse, MetaResponse
from core.config import get_settings
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from db.session import get_db
from models.org_api_key import OrgApiKey
from models.org_member import OrgMember
from models.organization import Organization

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field("starter", description="starter | growth | enterprise")
    owner_email: str = Field("admin@nexra.local")


class OrgCreateResponse(BaseModel):
    org_id: str
    name: str
    plan: str
    api_key: str


class OrgSettingsResponse(BaseModel):
    org_id: str
    name: str
    plan: str
    max_delegation_depth: int | None
    owner_email: str | None
    approval_url: str | None
    notification_url: str | None
    stripe_connect_account_id: str | None
    created_at: str


class OrgSettingsUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    max_delegation_depth: int | None = Field(None, ge=1, le=20)
    approval_url: str | None = None
    notification_url: str | None = None


class OrgSessionResponse(BaseModel):
    org_id: str
    org_name: str
    plan: str
    role: str
    email: str


class OrgApiKeyCreateRequest(BaseModel):
    name: str = Field("dashboard", min_length=1, max_length=120)


class OrgMemberCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: str = Field("viewer")


class OrgMemberUpdateRequest(BaseModel):
    role: str = Field(..., description="admin|engineer|compliance|viewer")


class OrgWebhookSettingsRequest(BaseModel):
    approval_url: str | None = None
    notification_url: str | None = None


class OrgWebhookTestRequest(BaseModel):
    target: str = Field(..., description="approval|notification")


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
        owner_email=body.owner_email.lower().strip(),
        jwt_secret_enc=jwt_secret_enc,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    db.add(
        OrgApiKey(
            org_id=org.id,
            name="primary",
            key_hash=hashed_key,
            key_prefix=prefix,
        )
    )
    db.add(
        OrgMember(
            org_id=org.id,
            email=body.owner_email.lower().strip(),
            role="admin",
        )
    )
    await db.commit()

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
            max_delegation_depth=org.max_delegation_depth,
            owner_email=org.owner_email,
            approval_url=org.approval_url,
            notification_url=org.notification_url,
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
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:
        org.name = body.name
    if body.max_delegation_depth is not None:
        org.max_delegation_depth = body.max_delegation_depth
    if body.approval_url is not None:
        org.approval_url = body.approval_url
    if body.notification_url is not None:
        org.notification_url = body.notification_url

    await db.commit()
    await db.refresh(org)
    return {
        "data": {
            "org_id": str(org.id),
            "name": org.name,
            "max_delegation_depth": org.max_delegation_depth,
            "owner_email": org.owner_email,
            "approval_url": org.approval_url,
            "notification_url": org.notification_url,
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }


@router.get("/session", response_model=DataResponse[dict])
async def get_org_session(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    actor: RequestActor = Depends(get_request_actor),
):
    return {
        "data": OrgSessionResponse(
            org_id=str(org.id),
            org_name=org.name,
            plan=org.plan,
            role=actor.role,
            email=actor.email,
        ).model_dump(),
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }


@router.get("/api-keys", response_model=DataResponse[dict])
async def list_api_keys(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgApiKey).where(OrgApiKey.org_id == org.id).order_by(OrgApiKey.created_at.desc())
    )
    keys = list(result.scalars().all())
    return {
        "data": {
            "items": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "key_prefix": item.key_prefix,
                    "created_at": item.created_at.isoformat(),
                    "last_used_at": item.last_used_at.isoformat() if item.last_used_at else None,
                    "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
                }
                for item in keys
            ]
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }


@router.post("/api-keys", response_model=DataResponse[dict])
async def create_api_key(
    request: Request,
    body: OrgApiKeyCreateRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    raw_key, hashed_key, prefix = generate_api_key()
    row = OrgApiKey(
        org_id=org.id,
        name=body.name,
        key_hash=hashed_key,
        key_prefix=prefix,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "data": {
            "id": str(row.id),
            "name": row.name,
            "key_prefix": row.key_prefix,
            "api_key": raw_key,
            "created_at": row.created_at.isoformat(),
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    }


@router.delete("/api-keys/{key_id}", response_model=DataResponse[dict])
async def revoke_api_key(
    request: Request,
    key_id: str,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgApiKey).where(OrgApiKey.id == key_id, OrgApiKey.org_id == org.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {
            "data": {"id": key_id, "revoked": False},
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }
    row.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "data": {"id": str(row.id), "revoked": True},
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.get("/members", response_model=DataResponse[dict])
async def list_members(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id).order_by(OrgMember.created_at.asc())
    )
    members = list(result.scalars().all())
    return {
        "data": {
            "items": [
                {
                    "id": str(item.id),
                    "email": item.email,
                    "role": item.role,
                    "created_at": item.created_at.isoformat(),
                    "last_active_at": item.last_active_at.isoformat() if item.last_active_at else None,
                }
                for item in members
            ]
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.post("/members", response_model=DataResponse[dict])
async def create_member(
    request: Request,
    body: OrgMemberCreateRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    role = body.role.lower().strip()
    if role not in {"admin", "engineer", "compliance", "viewer"}:
        role = "viewer"
    member = OrgMember(
        org_id=org.id,
        email=body.email.lower().strip(),
        role=role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return {
        "data": {
            "id": str(member.id),
            "email": member.email,
            "role": member.role,
            "created_at": member.created_at.isoformat(),
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.patch("/members/{member_id}", response_model=DataResponse[dict])
async def update_member(
    request: Request,
    member_id: str,
    body: OrgMemberUpdateRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgMember).where(OrgMember.id == member_id, OrgMember.org_id == org.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        return {
            "data": {"id": member_id, "updated": False},
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }
    role = body.role.lower().strip()
    if role not in {"admin", "engineer", "compliance", "viewer"}:
        role = "viewer"
    member.role = role
    await db.commit()
    return {
        "data": {"id": str(member.id), "role": member.role, "updated": True},
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.delete("/members/{member_id}", response_model=DataResponse[dict])
async def delete_member(
    request: Request,
    member_id: str,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgMember).where(OrgMember.id == member_id, OrgMember.org_id == org.id)
    )
    member = result.scalar_one_or_none()
    if not member:
        return {
            "data": {"id": member_id, "deleted": False},
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }
    await db.delete(member)
    await db.commit()
    return {
        "data": {"id": member_id, "deleted": True},
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.get("/webhooks", response_model=DataResponse[dict])
async def get_webhook_settings(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
):
    return {
        "data": {
            "approval_url": org.approval_url,
            "notification_url": org.notification_url,
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.patch("/webhooks", response_model=DataResponse[dict])
async def update_webhook_settings(
    request: Request,
    body: OrgWebhookSettingsRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.approval_url is not None:
        org.approval_url = body.approval_url
    if body.notification_url is not None:
        org.notification_url = body.notification_url
    await db.commit()
    return {
        "data": {
            "approval_url": org.approval_url,
            "notification_url": org.notification_url,
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
    }


@router.post("/webhooks/test", response_model=DataResponse[dict])
async def test_webhook_settings(
    request: Request,
    body: OrgWebhookTestRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
):
    target = body.target.strip().lower()
    if target not in {"approval", "notification"}:
        target = "approval"
    url = org.approval_url if target == "approval" else org.notification_url
    if not url:
        return {
            "data": {"target": target, "ok": False, "status_code": None, "error": "URL_NOT_CONFIGURED"},
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }

    payload = {
        "event": "webhook_test_ping",
        "target": target,
        "org_id": str(org.id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
        return {
            "data": {
                "target": target,
                "ok": bool(resp.is_success),
                "status_code": resp.status_code,
                "error": None if resp.is_success else "NON_2XX_RESPONSE",
            },
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }
    except Exception as exc:
        return {
            "data": {"target": target, "ok": False, "status_code": None, "error": str(exc)},
            "meta": MetaResponse(request_id=getattr(request.state, "request_id", None)).model_dump(),
        }
