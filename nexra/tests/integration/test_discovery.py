"""Integration tests for discovery — semantic search + composite scoring."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from api.schemas.capabilities import DiscoverRequest
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.organization import Organization
from services.agent_service import AgentService
from services.discovery_service import DiscoveryService


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
        name="Discovery Test Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db.add(org)
    await db.flush()
    return org


async def _register_agent(
    db: AsyncSession,
    org_id: str,
    agent_id: str,
    capability_type: str = "research",
    is_public: bool = False,
) -> None:
    service = AgentService(db, _mock_openai())
    await service.register(
        org_id,
        AgentRegisterRequest(
            agent_id=agent_id,
            name=f"Agent {agent_id}",
            description="A discoverable agent for integration testing purposes",
            capability_type=capability_type,
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/webhook",
            webhook_secret="a" * 32,
            is_public=is_public,
        ),
    )


class TestDiscovery:
    @pytest.mark.asyncio
    async def test_discover_returns_registered_agents(self, db_session: AsyncSession) -> None:
        """Discovery should find agents from the same org."""
        org = await _create_test_org(db_session)
        await _register_agent(db_session, str(org.id), "discoverable-1")
        await _register_agent(db_session, str(org.id), "discoverable-2")

        openai = _mock_openai()
        service = DiscoveryService(db_session, openai)
        matches, total, filtered = await service.discover(
            str(org.id),
            DiscoverRequest(query="find a research agent"),
        )

        assert total >= 2
        agent_ids = {m.agent_id for m in matches}
        assert "discoverable-1" in agent_ids
        assert "discoverable-2" in agent_ids

    @pytest.mark.asyncio
    async def test_discover_excludes_quarantined(self, db_session: AsyncSession) -> None:
        """Quarantined agents should not appear in discovery results."""
        org = await _create_test_org(db_session)
        await _register_agent(db_session, str(org.id), "healthy-agent")
        await _register_agent(db_session, str(org.id), "bad-agent")

        # Quarantine the bad agent
        agent_service = AgentService(db_session, _mock_openai())
        await agent_service.update_status(str(org.id), "bad-agent", "quarantined")

        openai = _mock_openai()
        service = DiscoveryService(db_session, openai)
        matches, _, _ = await service.discover(
            str(org.id),
            DiscoverRequest(query="find an agent"),
        )

        agent_ids = {m.agent_id for m in matches}
        assert "healthy-agent" in agent_ids
        assert "bad-agent" not in agent_ids

    @pytest.mark.asyncio
    async def test_discover_filters_by_capability_type(self, db_session: AsyncSession) -> None:
        org = await _create_test_org(db_session)
        await _register_agent(db_session, str(org.id), "research-one", "research")
        await _register_agent(db_session, str(org.id), "analysis-one", "analysis")

        openai = _mock_openai()
        service = DiscoveryService(db_session, openai)
        matches, _, _ = await service.discover(
            str(org.id),
            DiscoverRequest(query="research", capability_type="research"),
        )

        for m in matches:
            assert m.capability_type == "research"

    @pytest.mark.asyncio
    async def test_discover_exclude_agents(self, db_session: AsyncSession) -> None:
        org = await _create_test_org(db_session)
        await _register_agent(db_session, str(org.id), "include-me")
        await _register_agent(db_session, str(org.id), "exclude-me")

        openai = _mock_openai()
        service = DiscoveryService(db_session, openai)
        matches, _, _ = await service.discover(
            str(org.id),
            DiscoverRequest(query="find agent", exclude_agents=["exclude-me"]),
        )

        agent_ids = {m.agent_id for m in matches}
        assert "exclude-me" not in agent_ids

    @pytest.mark.asyncio
    async def test_discover_composite_score_structure(self, db_session: AsyncSession) -> None:
        """Every match should have a composite score between 0 and ~2."""
        org = await _create_test_org(db_session)
        await _register_agent(db_session, str(org.id), "scored-agent")

        openai = _mock_openai()
        service = DiscoveryService(db_session, openai)
        matches, _, _ = await service.discover(
            str(org.id),
            DiscoverRequest(query="agent"),
        )

        for m in matches:
            assert m.match_score >= 0.0
            assert isinstance(m.trust_score, float)
