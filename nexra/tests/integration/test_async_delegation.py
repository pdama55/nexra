"""Integration tests for async callback delegation mode."""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from api.schemas.delegations import DelegateRequest
from core.config import get_settings
from core.crypto import decrypt_aes_gcm, encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from core.errors import OUTPUT_SCHEMA_FAILED, NexraError
from core.jwt import issue_delegation_token
from models.audit_log import AuditLog
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
TEST_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")


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
    _raw_key, hashed, prefix = generate_api_key()
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

    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
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


@pytest.mark.asyncio
async def test_output_schema_validation_enabled_by_default(
    db_session: AsyncSession,
) -> None:
    _raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Async Output Schema Org",
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
            agent_id="output-schema-caller",
            name="Output Schema Caller",
            description="Caller for output schema test",
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
            agent_id="output-schema-callee",
            name="Output Schema Callee",
            description="Callee for output schema test",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
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
        parent_policy_id=None,
    )
    db_session.add(policy)
    await db_session.flush()

    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
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

        caller = await service.get_by_agent_id(str(org.id), "output-schema-caller")
        initiated = await delegation_service.initiate(
            org,
            caller,
            DelegateRequest(
                callee_agent_id="output-schema-callee",
                task={"input": {"query": "hello"}},
                budget_cap_usd=1.0,
                callback_url="https://example.com/callback",
            ),
        )
        assert initiated.status == "in_flight"

        settings = get_settings()
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)
        token = issue_delegation_token(
            org_secret,
            initiated.delegation_id,
            "output-schema-callee",
            [],
        )
        with pytest.raises(NexraError) as exc:
            await delegation_service.complete(
                initiated.delegation_id,
                token,
                {"bad": True},
                {"llm_tokens": 3},
                org,
            )
        assert exc.value.code == OUTPUT_SCHEMA_FAILED
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_output_schema_validation_disabled_bypasses_result_validation(
    db_session: AsyncSession,
) -> None:
    _raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Async Output Schema Disabled Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
        schema_validation_enabled=False,
    )
    db_session.add(org)
    await db_session.flush()

    service = AgentService(db_session, _mock_openai())
    await service.register(
        str(org.id),
        AgentRegisterRequest(
            agent_id="output-schema-off-caller",
            name="Output Schema Off Caller",
            description="Caller for output schema disabled test",
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
            agent_id="output-schema-off-callee",
            name="Output Schema Off Callee",
            description="Callee for output schema disabled test",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
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
        parent_policy_id=None,
    )
    db_session.add(policy)
    await db_session.flush()

    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
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

        caller = await service.get_by_agent_id(str(org.id), "output-schema-off-caller")
        initiated = await delegation_service.initiate(
            org,
            caller,
            DelegateRequest(
                callee_agent_id="output-schema-off-callee",
                task={"input": {"query": "hello"}},
                budget_cap_usd=1.0,
                callback_url="https://example.com/callback",
            ),
        )
        assert initiated.status == "in_flight"

        settings = get_settings()
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)
        token = issue_delegation_token(
            org_secret,
            initiated.delegation_id,
            "output-schema-off-callee",
            [],
        )
        completed = await delegation_service.complete(
            initiated.delegation_id,
            token,
            {"bad": True},
            {"llm_tokens": 3},
            org,
        )
        assert completed.status == "completed"
    finally:
        await redis_client.aclose()


@pytest.mark.asyncio
async def test_callback_completion_appends_callback_audit_events(
    db_session: AsyncSession,
) -> None:
    _raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Async Callback Audit Org",
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
            agent_id="callback-caller",
            name="Callback Caller",
            description="Caller for callback audit testing",
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
            agent_id="callback-callee",
            name="Callback Callee",
            description="Callee for callback audit testing",
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

    redis_client = aioredis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        policy_engine = PolicyEngine(redis_client, db_session)
        webhook_service = WebhookService()
        webhook_service.enqueue = AsyncMock()
        webhook_service.deliver_callback = AsyncMock()
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

        caller = await service.get_by_agent_id(str(org.id), "callback-caller")
        initiated = await delegation_service.initiate(
            org,
            caller,
            DelegateRequest(
                callee_agent_id="callback-callee",
                task={"input": {"query": "hello"}},
                budget_cap_usd=1.0,
                callback_url="https://example.com/callback",
            ),
        )
        assert initiated.status == "in_flight"

        settings = get_settings()
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)
        token = issue_delegation_token(
            org_secret,
            initiated.delegation_id,
            "callback-callee",
            [],
        )
        completed = await delegation_service.complete(
            initiated.delegation_id,
            token,
            {"answer": "ok"},
            {"llm_tokens": 3},
            org,
        )
        assert completed.status == "completed"

        audit_result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.delegation_id == uuid.UUID(initiated.delegation_id),
                AuditLog.event_type == "callback_delivered",
            )
        )
        callback_event = audit_result.scalar_one_or_none()
        assert callback_event is not None
    finally:
        await redis_client.aclose()
