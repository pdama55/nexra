"""Integration tests for agent registration — service layer against real DB."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.agent import Agent
from models.organization import Organization
from services.agent_service import AgentService


TEST_ENC_KEY = "a" * 64


def _mock_openai() -> AsyncMock:
    embedding_data = MagicMock()
    embedding_data.embedding = [0.01] * 1536
    response = MagicMock()
    response.data = [embedding_data]
    client = AsyncMock()
    client.embeddings.create = AsyncMock(return_value=response)
    return client


async def _create_test_org(db: AsyncSession) -> Organization:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db.add(org)
    await db.flush()
    return org


def _register_request(agent_id: str = "research-agent-1") -> AgentRegisterRequest:
    return AgentRegisterRequest(
        agent_id=agent_id,
        name=f"Agent {agent_id}",
        description="A test research agent for integration testing purposes",
        capability_type="research",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        pricing={"per_call_usd": 0.10},
        sla={"p99_latency_ms": 5000, "availability": 0.99},
        webhook_url="https://example.com/webhook",
        webhook_secret="a" * 32,
        is_public=False,
    )


class TestAgentRegistration:
    @pytest.mark.asyncio
    async def test_register_new_agent(self, db_session: AsyncSession) -> None:
        """A new agent should be created with status='probationary'."""
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        agent = await service.register(str(org.id), _register_request())

        assert agent.agent_id == "research-agent-1"
        assert agent.status == "probationary"
        assert agent.capability_type == "research"
        assert float(agent.trust_score) == 1.0

    @pytest.mark.asyncio
    async def test_register_idempotent_on_agent_id(self, db_session: AsyncSession) -> None:
        """Re-registration with same agent_id should update, not duplicate."""
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        agent1 = await service.register(str(org.id), _register_request())
        original_id = agent1.id

        req2 = _register_request()
        req2.name = "Updated Agent Name"
        agent2 = await service.register(str(org.id), req2)

        assert agent2.id == original_id
        assert agent2.name == "Updated Agent Name"

    @pytest.mark.asyncio
    async def test_list_agents_returns_registered(self, db_session: AsyncSession) -> None:
        """Listed agents should include newly registered ones."""
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        await service.register(str(org.id), _register_request("agent-a"))
        await service.register(str(org.id), _register_request("agent-b"))

        agents, cursor, total = await service.list_for_org(str(org.id))
        agent_ids = {a.agent_id for a in agents}
        assert "agent-a" in agent_ids
        assert "agent-b" in agent_ids
        assert total >= 2

    @pytest.mark.asyncio
    async def test_get_by_agent_id(self, db_session: AsyncSession) -> None:
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        await service.register(str(org.id), _register_request("lookup-agent"))
        found = await service.get_by_agent_id(str(org.id), "lookup-agent")
        assert found is not None
        assert found.agent_id == "lookup-agent"

    @pytest.mark.asyncio
    async def test_quarantine_agent(self, db_session: AsyncSession) -> None:
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        await service.register(str(org.id), _register_request("q-agent"))
        quarantined = await service.update_status(str(org.id), "q-agent", "quarantined")
        assert quarantined.status == "quarantined"

    @pytest.mark.asyncio
    async def test_activate_agent(self, db_session: AsyncSession) -> None:
        org = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        await service.register(str(org.id), _register_request("a-agent"))
        activated = await service.update_status(str(org.id), "a-agent", "active")
        assert activated.status == "active"

    @pytest.mark.asyncio
    async def test_different_orgs_can_have_same_agent_id(self, db_session: AsyncSession) -> None:
        org1 = await _create_test_org(db_session)
        org2 = await _create_test_org(db_session)
        service = AgentService(db_session, _mock_openai())

        await service.register(str(org1.id), _register_request("shared-id"))
        await service.register(str(org2.id), _register_request("shared-id"))

        a1 = await service.get_by_agent_id(str(org1.id), "shared-id")
        a2 = await service.get_by_agent_id(str(org2.id), "shared-id")
        assert a1 is not None
        assert a2 is not None
        assert a1.org_id != a2.org_id
