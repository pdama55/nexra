import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import factory

from models.agent import Agent
from models.agent_budget import AgentBudget
from models.audit_log import AuditLog
from models.delegation import Delegation
from models.organization import Organization
from models.policy import Policy
from models.trust_score_event import TrustScoreEvent

from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret


# Encryption key used in all test fixtures
TEST_ENCRYPTION_KEY = "a" * 64  # 64 hex chars (32 bytes)


class OrganizationFactory(factory.Factory):
    class Meta:
        model = Organization

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Test Org {n}")
    api_key_hash = factory.LazyFunction(lambda: generate_api_key()[1])
    api_key_prefix = factory.LazyFunction(lambda: generate_api_key()[2])
    stripe_id = None
    stripe_connect_account_id = None
    plan = "growth"
    owner_email = "admin@example.com"
    max_delegation_depth = 5
    approval_url = None
    jwt_secret_enc = factory.LazyFunction(
        lambda: encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENCRYPTION_KEY)
    )
    delegation_count = 0
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class AgentFactory(factory.Factory):
    class Meta:
        model = Agent

    id = factory.LazyFunction(uuid.uuid4)
    org_id = factory.LazyFunction(uuid.uuid4)
    agent_id = factory.Sequence(lambda n: f"agent-{n}")
    name = factory.Sequence(lambda n: f"Test Agent {n}")
    description = "A test agent for unit testing"
    capability_type = "research"
    input_schema = factory.LazyFunction(
        lambda: {"type": "object", "properties": {"query": {"type": "string"}}}
    )
    output_schema = factory.LazyFunction(
        lambda: {"type": "object", "properties": {"result": {"type": "string"}}}
    )
    webhook_url = "https://example.com/webhook"
    webhook_secret = "test_webhook_secret"
    pricing = factory.LazyFunction(lambda: {"per_call_usd": 0.10})
    sla = factory.LazyFunction(lambda: {"p99_latency_ms": 5000, "availability": 0.99})
    is_public = False
    embedding = None
    trust_score = Decimal("1.000")
    status = "active"
    delegation_count = 0
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class PolicyFactory(factory.Factory):
    class Meta:
        model = Policy

    id = factory.LazyFunction(uuid.uuid4)
    org_id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"policy-{n}")
    description = "Test policy"
    priority = 10
    rule_yaml = factory.LazyFunction(lambda: (
        "allow:\n"
        "  caller_type: research\n"
        "  callee_type: analysis\n"
        "conditions:\n"
        "  - field: time_of_day\n"
        "    operator: between\n"
        "    value: [\"00:00\", \"23:59\"]\n"
        "on_violation: block_and_alert\n"
    ))
    version = 1
    enabled = True
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class DelegationFactory(factory.Factory):
    class Meta:
        model = Delegation

    id = factory.LazyFunction(uuid.uuid4)
    caller_org_id = factory.LazyFunction(uuid.uuid4)
    caller_agent_id = "caller-agent"
    callee_org_id = None
    callee_agent_id = "callee-agent"
    task = factory.LazyFunction(lambda: {"type": "research", "input": {"query": "test"}})
    task_hash = "abc123"
    context_scope = factory.LazyFunction(lambda: ["scope_a"])
    policy_id = None
    policy_version = None
    policy_decision = "allow"
    status = "completed"
    result = None
    budget_cap_usd = Decimal("1.00")
    estimated_cost_usd = Decimal("0.10")
    actual_cost_usd = Decimal("0.10")
    latency_ms = 500
    llm_tokens = 100
    callback_url = None
    delegation_depth = 0
    parent_delegation_id = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    completed_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
