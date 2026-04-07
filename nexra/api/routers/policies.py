import time
from typing import Any

import redis.asyncio as aioredis
import yaml
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import RequestActor, get_authenticated_org, get_redis, require_roles
from api.schemas.common import DataResponse, MetaResponse
from api.schemas.policies import (
    PolicyCreateRequest,
    PolicyListResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    PolicyVersionsResponse,
)
from core.errors import POLICY_NOT_FOUND, NexraError
from db.session import get_db
from models.organization import Organization
from models.policy import Policy
from services.policy_engine import PolicyEngine

router = APIRouter(prefix="/policies", tags=["policies"])


def _parse_policy_yaml(rule_yaml: str) -> dict:
    return yaml.safe_load(rule_yaml) or {}


def _policy_to_response(p: Policy) -> PolicyResponse:
    parsed = _parse_policy_yaml(p.rule_yaml)
    return PolicyResponse(
        id=str(p.id),
        parent_policy_id=str(p.parent_policy_id) if p.parent_policy_id else None,
        name=p.name,
        description=p.description,
        priority=p.priority,
        version=p.version,
        enabled=p.enabled,
        allow=parsed.get("allow", {}),
        conditions=parsed.get("conditions", []),
        hil_threshold_usd=parsed.get("hil_threshold_usd"),
        on_violation=parsed.get("on_violation", "block_and_alert"),
        created_at=p.created_at,
    )


@router.post("")
async def create_policy(
    request: Request,
    body: PolicyCreateRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin", "engineer")),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Create a new delegation policy."""
    start = time.perf_counter()

    policy = Policy(
        org_id=org.id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        rule_yaml=body.to_yaml(),
        version=1,
        enabled=True,
    )
    db.add(policy)
    await db.flush()
    policy.parent_policy_id = policy.id
    await db.commit()
    await db.refresh(policy)

    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    latency = round((time.perf_counter() - start) * 1000, 2)
    return DataResponse(
        data=_policy_to_response(policy),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.get("", response_model=DataResponse[dict[str, Any]])
async def list_policies(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """List all policies for the authenticated org."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.org_id == org.id).order_by(Policy.priority.asc())
    )
    policies = list(result.scalars().all())

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": PolicyListResponse(
            policies=[_policy_to_response(p) for p in policies],
            total_count=len(policies),
        ).model_dump(),
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/{policy_id}", response_model=DataResponse[dict[str, Any]])
async def get_policy(
    request: Request,
    policy_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get a policy by ID with version history."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    family_root_id = policy.parent_policy_id or policy.id
    versions_result = await db.execute(
        select(Policy)
        .where(
            Policy.org_id == org.id,
            or_(
                Policy.id == family_root_id,
                Policy.parent_policy_id == family_root_id,
            ),
        )
        .order_by(Policy.version.desc())
    )
    versions = [_policy_to_response(p) for p in versions_result.scalars().all()]

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "current": _policy_to_response(policy).model_dump(),
            "versions": [v.model_dump() for v in versions],
        },
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }


@router.get("/{policy_id}/versions", response_model=DataResponse[PolicyVersionsResponse])
async def get_policy_versions(
    request: Request,
    policy_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get immutable version history for a policy family."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    family_root_id = policy.parent_policy_id or policy.id
    versions_result = await db.execute(
        select(Policy)
        .where(
            Policy.org_id == org.id,
            or_(
                Policy.id == family_root_id,
                Policy.parent_policy_id == family_root_id,
            ),
        )
        .order_by(Policy.version.desc())
    )
    versions = [_policy_to_response(p) for p in versions_result.scalars().all()]

    latency = round((time.perf_counter() - start) * 1000, 2)
    return DataResponse(
        data=PolicyVersionsResponse(
            policy_id=str(family_root_id),
            versions=versions,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.put("/{policy_id}")
async def update_policy(
    request: Request,
    policy_id: str,
    body: PolicyUpdateRequest,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin", "engineer")),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Update a policy. Creates a new version; old version is preserved."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    current = yaml.safe_load(existing.rule_yaml) or {}

    if body.allow is not None:
        current["allow"] = body.allow
    if body.conditions is not None:
        current["conditions"] = body.conditions
    if body.hil_threshold_usd is not None:
        current["hil_threshold_usd"] = body.hil_threshold_usd
    if body.on_violation is not None:
        current["on_violation"] = body.on_violation

    family_root_id = existing.parent_policy_id or existing.id
    max_version_result = await db.execute(
        select(func.max(Policy.version)).where(
            Policy.org_id == org.id,
            or_(
                Policy.id == family_root_id,
                Policy.parent_policy_id == family_root_id,
            ),
        )
    )
    next_version = int(max_version_result.scalar() or existing.version) + 1

    existing.enabled = False
    await db.flush()

    new_policy = Policy(
        org_id=org.id,
        parent_policy_id=family_root_id,
        name=existing.name,
        description=body.description if body.description is not None else existing.description,
        priority=body.priority if body.priority is not None else existing.priority,
        rule_yaml=yaml.dump(current, default_flow_style=False),
        version=next_version,
        enabled=True,
    )
    db.add(new_policy)
    await db.commit()
    await db.refresh(new_policy)

    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    latency = round((time.perf_counter() - start) * 1000, 2)
    return DataResponse(
        data=_policy_to_response(new_policy),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.delete("/{policy_id}")
async def disable_policy(
    request: Request,
    policy_id: str,
    org: Organization = Depends(get_authenticated_org),
    _actor: RequestActor = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Disable a policy (soft delete). Preserves history."""
    start = time.perf_counter()
    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    policy.enabled = False
    await db.commit()

    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {"id": str(policy.id), "enabled": False},
        "meta": MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ).model_dump(),
    }
