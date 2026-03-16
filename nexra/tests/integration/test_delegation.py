"""Integration tests for delegation — policy evaluation + record creation."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio as aioredis
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.agents import AgentRegisterRequest
from api.schemas.delegations import DelegateRequest
from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from core.errors import NexraError
from models.delegation import Delegation
from models.agent_budget import AgentBudget
from models.organization import Organization
from models.policy import Policy
from services.agent_service import AgentService
from services.audit_service import AuditService
from services.budget_service import BudgetService
from services.delegation_service import DelegationService
from services.policy_engine import PolicyEngine
from services.trust_service import TrustService
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


async def _create_org(db: AsyncSession) -> Organization:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Delegation Test Org",
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
    db: AsyncSession, org_id: str, agent_id: str, cap_type: str = "research"
) -> None:
    service = AgentService(db, _mock_openai())
    await service.register(
        org_id,
        AgentRegisterRequest(
            agent_id=agent_id,
            name=f"Agent {agent_id}",
            description="A test agent for delegation integration testing",
            capability_type=cap_type,
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            pricing={"per_call_usd": 0.10},
            sla={"p99_latency_ms": 5000, "availability": 0.99},
            webhook_url="https://example.com/webhook",
            webhook_secret="a" * 32,
            is_public=False,
        ),
    )


async def _add_policy(
    db: AsyncSession,
    org_id: uuid.UUID,
    rule: dict,
    name: str = "test-policy",
    priority: int = 10,
) -> Policy:
    policy = Policy(
        id=uuid.uuid4(),
        org_id=org_id,
        name=name,
        priority=priority,
        rule_yaml=yaml.dump(rule),
        version=1,
        enabled=True,
    )
    db.add(policy)
    await db.flush()
    return policy


class TestDelegationPolicyBlocking:
    """Test that delegations are blocked when no policies exist (default deny)."""

    @pytest.mark.asyncio
    async def test_no_policies_blocks_delegation(self, db_session: AsyncSession) -> None:
        """Without any policies, the policy engine should block (default deny)."""
        org = await _create_org(db_session)
        await _register_agent(db_session, str(org.id), "caller-agent")
        await _register_agent(db_session, str(org.id), "callee-agent", "analysis")

        redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        try:
            policy_engine = PolicyEngine(redis_client, db_session)
            webhook_service = WebhookService()
            budget_service = BudgetService(db_session)
            audit_service = AuditService(db_session)
            trust_service = TrustService(db_session)

            service = DelegationService(
                db_session, redis_client, policy_engine,
                webhook_service, budget_service, audit_service, trust_service,
            )

            caller = await AgentService(db_session, _mock_openai()).get_by_agent_id(
                str(org.id), "caller-agent"
            )
            request = DelegateRequest(
                callee_agent_id="callee-agent",
                task={"type": "research", "input": {"query": "test"}},
                budget_cap_usd=1.0,
            )

            with pytest.raises(NexraError) as exc:
                await service.initiate(org, caller, request)

            assert exc.value.code == "POLICY_BLOCKED"
        finally:
            await redis_client.aclose()


class TestDelegationWithPolicy:
    """Test that delegations succeed with a matching allow policy."""

    @pytest.mark.asyncio
    async def test_policy_allows_creates_delegation_record(
        self, db_session: AsyncSession
    ) -> None:
        """An allow policy should let the delegation through to webhook delivery."""
        org = await _create_org(db_session)
        await _register_agent(db_session, str(org.id), "caller-agent-2")
        await _register_agent(db_session, str(org.id), "callee-agent-2", "analysis")

        # Create an allow-all policy
        await _add_policy(db_session, org.id, {
            "allow": {},
            "conditions": [],
            "on_violation": "block_and_alert",
        })

        redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        try:
            policy_engine = PolicyEngine(redis_client, db_session)
            budget_service = BudgetService(db_session)
            audit_service = AuditService(db_session)
            trust_service = TrustService(db_session)

            # Mock webhook delivery to return a result
            webhook_service = WebhookService()
            webhook_service.deliver_and_await = AsyncMock(
                return_value={"result": {"answer": "42"}, "usage": {"llm_tokens": 50}}
            )

            service = DelegationService(
                db_session, redis_client, policy_engine,
                webhook_service, budget_service, audit_service, trust_service,
            )

            caller = await AgentService(db_session, _mock_openai()).get_by_agent_id(
                str(org.id), "caller-agent-2"
            )
            request = DelegateRequest(
                callee_agent_id="callee-agent-2",
                task={"type": "analysis", "input": {"query": "test"}},
                budget_cap_usd=1.0,
            )

            result = await service.initiate(org, caller, request)

            assert result.status == "completed"
            assert result.delegation_id is not None
            assert result.result is not None

            budget_result = await db_session.execute(
                select(AgentBudget).where(
                    AgentBudget.org_id == org.id,
                    AgentBudget.agent_id.in_(["caller-agent-2", "callee-agent-2"]),
                )
            )
            budget_rows = list(budget_result.scalars().all())
            caller_rows = [r for r in budget_rows if r.agent_id == "caller-agent-2"]
            callee_rows = [r for r in budget_rows if r.agent_id == "callee-agent-2"]
            assert caller_rows, "caller budget rows must exist after settlement"
            assert not callee_rows, "callee budget rows must not be charged for caller-initiated delegation"
        finally:
            await redis_client.aclose()


class TestDelegationHiTL:
    """Test that HiTL threshold triggers a pause decision."""

    @pytest.mark.asyncio
    async def test_hil_threshold_pauses_delegation(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        await _register_agent(db_session, str(org.id), "hil-caller")
        await _register_agent(db_session, str(org.id), "hil-callee", "analysis")

        # Policy with a very low HiTL threshold
        await _add_policy(db_session, org.id, {
            "allow": {},
            "conditions": [],
            "hil_threshold_usd": 0.01,
            "on_violation": "block_and_alert",
        })

        redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        try:
            policy_engine = PolicyEngine(redis_client, db_session)
            webhook_service = WebhookService()
            budget_service = BudgetService(db_session)
            audit_service = AuditService(db_session)
            trust_service = TrustService(db_session)

            service = DelegationService(
                db_session, redis_client, policy_engine,
                webhook_service, budget_service, audit_service, trust_service,
            )

            caller = await AgentService(db_session, _mock_openai()).get_by_agent_id(
                str(org.id), "hil-caller"
            )
            request = DelegateRequest(
                callee_agent_id="hil-callee",
                task={"input": {"query": "expensive task"}},
                budget_cap_usd=1.0,
            )

            result = await service.initiate(org, caller, request)

            assert result.status == "pending_approval"
            assert result.poll_url is not None
        finally:
            await redis_client.aclose()


class TestDelegationDepth:
    @pytest.mark.asyncio
    async def test_parent_delegation_increments_depth(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        await _register_agent(db_session, str(org.id), "depth-caller")
        await _register_agent(db_session, str(org.id), "depth-callee", "analysis")

        await _add_policy(db_session, org.id, {
            "allow": {},
            "conditions": [],
            "on_violation": "block_and_alert",
        })

        redis_client = aioredis.from_url("redis://localhost:6379/1", decode_responses=True)
        try:
            policy_engine = PolicyEngine(redis_client, db_session)
            budget_service = BudgetService(db_session)
            audit_service = AuditService(db_session)
            trust_service = TrustService(db_session)
            webhook_service = WebhookService()
            webhook_service.deliver_and_await = AsyncMock(
                return_value={"result": {"answer": "ok"}, "usage": {"llm_tokens": 1}}
            )
            service = DelegationService(
                db_session, redis_client, policy_engine,
                webhook_service, budget_service, audit_service, trust_service,
            )
            caller = await AgentService(db_session, _mock_openai()).get_by_agent_id(
                str(org.id), "depth-caller"
            )
            first = await service.initiate(
                org,
                caller,
                DelegateRequest(
                    callee_agent_id="depth-callee",
                    task={"input": {"query": "depth one"}},
                    budget_cap_usd=1.0,
                ),
            )
            second = await service.initiate(
                org,
                caller,
                DelegateRequest(
                    callee_agent_id="depth-callee",
                    task={"input": {"query": "depth two"}},
                    budget_cap_usd=1.0,
                    parent_delegation_id=first.delegation_id,
                ),
            )
            result = await db_session.execute(
                select(Delegation).where(Delegation.id == second.delegation_id)
            )
            nested = result.scalar_one_or_none()
            assert nested is not None
            assert nested.delegation_depth == 1
            assert str(nested.parent_delegation_id) == first.delegation_id
        finally:
            await redis_client.aclose()
