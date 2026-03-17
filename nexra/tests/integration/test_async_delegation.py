"""Integration tests for async callback delegation mode."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from api.schemas.delegations import DelegateRequest
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.organization import Organization
from models.policy import Policy
from services.agent_service import AgentService
from services.audit_service import AuditService
from services.budget_service import BudgetService
from services.delegation_service import DelegationService
from services.policy_engine import PolicyEngine
from services.trust_service import CircuitBreakerService, TrustService
from services.webhook_service import WebhookService

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
async def test_callback_url_queues_async_delivery(db_session: AsyncSession) -> None:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Async Test Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()

    service = AgentService(db_session, _mock_openai())
    await service.register(
        str(org.id),
        AgentRegisterRequest(
            agent_id="async-caller",
            name="Async Caller",
            description="Async caller agent for integration testing",
            capability_type="research",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/caller",
            webhook_secret="a" * 32,
            is_public=False,
        ),
    )
    await service.register(
        str(org.id),
        AgentRegisterRequest(
            agent_id="async-callee",
            name="Async Callee",
            description="Async callee agent for integration testing",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/callee",
            webhook_secret="b" * 32,
            is_public=False,
        ),
    )

    policy = Policy(
        id=uuid.uuid4(),
        org_id=org.id,
        name="allow-all",
        priority=10,
        rule_yaml=yaml.dump({"allow": {}, "conditions": [], "on_violation": "block_and_alert"}),
        version=1,
        enabled=True,
    )
    db_session.add(policy)
    await db_session.flush()

    redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
    try:
        policy_engine = PolicyEngine(redis_client, db_session)
        webhook_service = WebhookService()
        webhook_service.enqueue = AsyncMock()
        budget_service = BudgetService(db_session)
        audit_service = AuditService(db_session)
        trust_service = TrustService(db_session)
        circuit_breaker = CircuitBreakerService(redis_client)

        delegation_service = DelegationService(
            db_session,
            redis_client,
            policy_engine,
            webhook_service,
            budget_service,
            audit_service,
            trust_service,
            circuit_breaker=circuit_breaker,
        )

        caller = await service.get_by_agent_id(str(org.id), "async-caller")
        result = await delegation_service.initiate(
            org,
            caller,
            DelegateRequest(
                callee_agent_id="async-callee",
                task={"input": {"query": "hello"}},
                budget_cap_usd=1.0,
                callback_url="https://example.com/callback",
            ),
        )

        assert result.status == "in_flight"
        assert result.poll_url is not None
        webhook_service.enqueue.assert_awaited_once()
    finally:
        await redis_client.aclose()
