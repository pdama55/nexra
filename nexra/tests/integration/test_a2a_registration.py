"""Integration tests for A2A agent card registration endpoint behavior."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.agents import register_a2a_agent
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from core.errors import NexraError
from models.agent import Agent
from models.organization import Organization

TEST_ENC_KEY = "a" * 64


def _mock_openai() -> AsyncMock:
    embedding_data = MagicMock()
    embedding_data.embedding = [0.01] * 1536
    response = MagicMock()
    response.data = [embedding_data]
    client = AsyncMock()
    client.embeddings.create = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_a2a_registration_creates_agent(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="A2A Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.commit()

    monkeypatch.setattr("api.routers.agents._get_openai_client", _mock_openai)
    request = type("Req", (), {"state": type("State", (), {"request_id": "req-1"})()})()

    response = await register_a2a_agent(
        request=request,
        agent_card={
            "name": "A2A Research Agent",
            "description": "Researches market data",
            "url": "https://example.com/a2a",
            "capabilities": {"research": True},
        },
        org=org,
        db=db_session,
    )

    assert response.data.agent_id == "a2a-research-agent"

    result = await db_session.execute(
        select(Agent).where(Agent.org_id == org.id, Agent.agent_id == "a2a-research-agent")
    )
    agent = result.scalar_one_or_none()
    assert agent is not None
    assert agent.capability_type == "research"


@pytest.mark.asyncio
async def test_a2a_registration_missing_name_raises(
    db_session: AsyncSession,
) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="A2A Org 2",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.commit()

    request = type("Req", (), {"state": type("State", (), {"request_id": "req-2"})()})()

    with pytest.raises(NexraError) as exc:
        await register_a2a_agent(
            request=request,
            agent_card={"url": "https://example.com/a2a"},
            org=org,
            db=db_session,
        )

    assert exc.value.status_code == 400
    assert exc.value.code == "INVALID_A2A_CARD"
