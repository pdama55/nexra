"""Integration tests for policy version lineage behavior."""

import os
import uuid

import pytest
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import RequestActor
from api.routers.policies import create_policy, get_policy_versions, update_policy
from api.schemas.policies import PolicyCreateRequest, PolicyUpdateRequest
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.organization import Organization
from models.policy import Policy

TEST_ENC_KEY = "a" * 64
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")


def _req() -> object:
    return type("Req", (), {"state": type("State", (), {"request_id": "req-policy-lineage"})()})()


async def _create_org(db_session: AsyncSession, name: str = "Policy Lineage Org") -> Organization:
    _, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_policy_versions_preserve_root_lineage(db_session: AsyncSession) -> None:
    org = await _create_org(db_session)
    actor = RequestActor(email="admin@nexra.local", role="admin")

    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        created = await create_policy(
            _req(),
            PolicyCreateRequest(
                name="delegation-allow",
                description="v1",
                priority=100,
                allow={},
                conditions=[],
                on_violation="block_and_alert",
            ),
            org=org,
            _actor=actor,
            db=db_session,
            redis_client=redis_client,
        )
        root = created.data
        assert root.version == 1
        assert root.parent_policy_id == root.id

        second = await update_policy(
            _req(),
            root.id,
            PolicyUpdateRequest(description="v2"),
            org=org,
            _actor=actor,
            db=db_session,
            redis_client=redis_client,
        )
        v2 = second.data
        assert v2.version == 2
        assert v2.parent_policy_id == root.id
        assert v2.id != root.id

        third = await update_policy(
            _req(),
            v2.id,
            PolicyUpdateRequest(description="v3", priority=50),
            org=org,
            _actor=actor,
            db=db_session,
            redis_client=redis_client,
        )
        v3 = third.data
        assert v3.version == 3
        assert v3.parent_policy_id == root.id

        versions_response = await get_policy_versions(
            _req(),
            policy_id=v3.id,
            org=org,
            db=db_session,
        )
        assert versions_response.data.policy_id == root.id
        versions = versions_response.data.versions
        assert [item.version for item in versions] == [3, 2, 1]
        assert {item.parent_policy_id for item in versions} == {root.id}

        db_rows = await db_session.execute(
            select(Policy).where(Policy.org_id == org.id).order_by(Policy.version.asc())
        )
        persisted = list(db_rows.scalars().all())
        assert len(persisted) == 3
        assert [row.version for row in persisted] == [1, 2, 3]
        assert [row.enabled for row in persisted] == [False, False, True]
        assert {str(row.parent_policy_id) for row in persisted} == {root.id}
    finally:
        await redis_client.aclose()
