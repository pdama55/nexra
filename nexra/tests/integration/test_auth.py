"""Integration tests for auth dependencies."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_authenticated_org, get_authenticated_org_and_agent
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.agent import Agent
from models.org_api_key import OrgApiKey
from models.organization import Organization

TEST_ENC_KEY = "a" * 64


class _FakeRedis:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        return None


@pytest.mark.asyncio
async def test_valid_api_key_and_agent_authenticates(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Auth Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    db_session.add(
        Agent(
            org_id=org.id,
            agent_id="auth-agent",
            name="Auth Agent",
            description="Auth integration test agent description",
            capability_type="research",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            webhook_url="https://example.com/hook",
            webhook_secret="a" * 32,
            pricing={"per_call_usd": 0.1},
            sla={"p99_latency_ms": 1000, "availability": 0.99},
            is_public=False,
            status="active",
        )
    )
    await db_session.commit()

    request = type("Req", (), {"state": type("State", (), {})()})()
    org_result, agent = await get_authenticated_org_and_agent(
        request=request,
        authorization=f"Bearer {raw_key}",
        x_agent_id="auth-agent",
        db=db_session,
        redis_client=_FakeRedis(),
    )

    assert str(org_result.id) == str(org.id)
    assert agent.agent_id == "auth-agent"


@pytest.mark.asyncio
async def test_wrong_agent_for_org_returns_401(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Auth Org 2",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.commit()

    request = type("Req", (), {"state": type("State", (), {})()})()
    with pytest.raises(HTTPException) as exc:
        await get_authenticated_org_and_agent(
            request=request,
            authorization=f"Bearer {raw_key}",
            x_agent_id="missing-agent",
            db=db_session,
            redis_client=_FakeRedis(),
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_quarantined_agent_returns_403(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Auth Org 3",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    db_session.add(
        Agent(
            org_id=org.id,
            agent_id="quarantined-agent",
            name="Quarantined Agent",
            description="Quarantined auth integration test agent",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            webhook_url="https://example.com/hook",
            webhook_secret="b" * 32,
            pricing={"per_call_usd": 0.1},
            sla={"p99_latency_ms": 1000, "availability": 0.99},
            is_public=False,
            status="quarantined",
        )
    )
    await db_session.commit()

    request = type("Req", (), {"state": type("State", (), {})()})()
    with pytest.raises(HTTPException) as exc:
        await get_authenticated_org_and_agent(
            request=request,
            authorization=f"Bearer {raw_key}",
            x_agent_id="quarantined-agent",
            db=db_session,
            redis_client=_FakeRedis(),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_invalid_primary_key_with_matching_prefix_is_rejected(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Auth Org 4",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.commit()

    tampered_char = "x" if raw_key[-1] != "x" else "y"
    invalid_raw_key = f"{raw_key[:-1]}{tampered_char}"

    request = type("Req", (), {"state": type("State", (), {})()})()
    with pytest.raises(HTTPException) as exc:
        await get_authenticated_org(
            request=request,
            authorization=f"Bearer {invalid_raw_key}",
            db=db_session,
            redis_client=_FakeRedis(),
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_secondary_org_api_key_authenticates_and_updates_last_used(db_session: AsyncSession) -> None:
    _, primary_hashed, primary_prefix = generate_api_key()
    secondary_raw_key, secondary_hashed, secondary_prefix = generate_api_key()

    org = Organization(
        id=uuid.uuid4(),
        name="Auth Org 5",
        api_key_hash=primary_hashed,
        api_key_prefix=primary_prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        OrgApiKey(
            org_id=org.id,
            name="dashboard",
            key_hash=secondary_hashed,
            key_prefix=secondary_prefix,
        )
    )
    await db_session.commit()

    request = type("Req", (), {"state": type("State", (), {})()})()
    org_result = await get_authenticated_org(
        request=request,
        authorization=f"Bearer {secondary_raw_key}",
        db=db_session,
        redis_client=_FakeRedis(),
    )
    await db_session.commit()

    assert str(org_result.id) == str(org.id)
    key_row_result = await db_session.execute(
        select(OrgApiKey).where(
            OrgApiKey.org_id == org.id,
            OrgApiKey.key_prefix == secondary_prefix,
        )
    )
    key_row = key_row_result.scalar_one()
    assert key_row.last_used_at is not None
