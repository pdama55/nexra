from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Literal

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.crypto import verify_api_key
from core.errors import INSUFFICIENT_ROLE, NexraError
from db.session import get_db
from models.agent import Agent
from models.org_api_key import OrgApiKey
from models.org_member import OrgMember
from models.organization import Organization

# ─── Redis Dependency ─────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Returns a shared async Redis client."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool on app shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None


# ─── Rate Limit Check ────────────────────────────────────────


async def check_rate_limit(
    redis_client: aioredis.Redis,
    org_key_prefix: str,
    rpm_limit: int,
) -> None:
    """Sliding window rate limit check.

    Uses Redis INCR + EXPIRE for a 60-second window.
    """
    key = f"rate:{org_key_prefix}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, 60)
    if current > rpm_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded: {rpm_limit} requests per minute",
                }
            },
            headers={"Retry-After": "60"},
        )


# ─── Auth Dependency ──────────────────────────────────────────


async def get_authenticated_org(
    request: Request,
    authorization: str = Header(..., description="Bearer nx_live_..."),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> Organization:
    """Authenticate the request and return the Organization."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Missing Bearer token"}},
        )

    raw_key = authorization[7:]
    prefix = raw_key[:16]

    settings = get_settings()

    org_result = await db.execute(
        select(Organization).where(Organization.api_key_prefix == prefix)
    )
    org = org_result.scalar_one_or_none()
    authenticated_org: Organization | None = None

    if org and verify_api_key(raw_key, org.api_key_hash):
        authenticated_org = org

    if authenticated_org is None:
        key_result = await db.execute(
            select(OrgApiKey, Organization)
            .join(Organization, Organization.id == OrgApiKey.org_id)
            .where(
                OrgApiKey.key_prefix == prefix,
                OrgApiKey.revoked_at.is_(None),
            )
        )
        pair = key_result.first()
        if pair:
            org_key, matched_org = pair
            if verify_api_key(raw_key, org_key.key_hash):
                authenticated_org = matched_org
                org_key.last_used_at = datetime.now(UTC)
                await db.flush()

    if authenticated_org is None:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}},
        )

    rpm = (
        settings.rate_limit_growth_rpm
        if authenticated_org.plan in ("growth", "enterprise")
        else settings.rate_limit_starter_rpm
    )
    await check_rate_limit(redis_client, prefix, rpm)

    return authenticated_org


async def get_authenticated_org_and_agent(
    request: Request,
    authorization: str = Header(...),
    x_agent_id: str = Header(..., alias="X-Agent-ID"),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> tuple[Organization, Agent]:
    """Authenticate and return both Organization and Agent.

    Used for agent-initiated requests (discover, delegate).
    """
    org = await get_authenticated_org(request, authorization, db, redis_client)

    result = await db.execute(
        select(Agent).where(
            Agent.org_id == org.id,
            Agent.agent_id == x_agent_id,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": f"Agent '{x_agent_id}' not found under this organization",
                }
            },
        )

    if agent.status == "quarantined":
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "AGENT_QUARANTINED",
                    "message": f"Agent '{x_agent_id}' is quarantined",
                }
            },
        )

    return org, agent


AllowedRole = Literal["admin", "engineer", "compliance", "viewer"]


@dataclass(frozen=True)
class RequestActor:
    email: str
    role: AllowedRole


def _normalize_role(value: str | None) -> AllowedRole:
    role = (value or "").strip().lower()
    if role in {"admin", "engineer", "compliance", "viewer"}:
        return role
    return "viewer"


async def get_request_actor(
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    x_user_email: str | None = Header(None, alias="X-User-Email"),
) -> RequestActor:
    """Resolve request actor from verified email header and org membership."""
    raw_email = (x_user_email or "").strip().lower()
    if raw_email:
        member_result = await db.execute(
            select(OrgMember).where(
                OrgMember.org_id == org.id,
                OrgMember.email == raw_email,
            )
        )
        member = member_result.scalar_one_or_none()
        if member:
            member.last_active_at = datetime.now(UTC)
            await db.flush()
            return RequestActor(email=member.email, role=_normalize_role(member.role))
        return RequestActor(email=raw_email, role="viewer")

    # Local/dev compatibility: if no member records exist yet for this org,
    # treat the implicit local admin identity as admin.
    count_result = await db.execute(
        select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org.id)
    )
    has_members = int(count_result.scalar() or 0) > 0
    if not has_members:
        return RequestActor(email="admin@nexra.local", role="admin")
    return RequestActor(email="unknown@nexra.local", role="viewer")


def require_roles(*allowed_roles: AllowedRole):
    allowed = set(allowed_roles)

    async def _dependency(actor: RequestActor = Depends(get_request_actor)) -> RequestActor:
        if actor.role not in allowed:
            raise NexraError(
                403,
                INSUFFICIENT_ROLE,
                f"Role '{actor.role}' cannot perform this action",
                {"allowed_roles": sorted(allowed)},
            )
        return actor

    return _dependency
