"""Unit tests for services.policy_engine — YAML policy evaluation."""

import uuid
from datetime import datetime, timezone

import pytest

from services.policy_engine import DelegationContext, PolicyDecision, PolicyEngine


def _make_context(**overrides: object) -> DelegationContext:
    """Build a DelegationContext with sensible defaults, overridable per-test."""
    defaults = {
        "caller_agent_id": "sales-agent",
        "caller_agent_type": "research",
        "caller_org_id": str(uuid.uuid4()),
        "caller_budget_remaining_usd": 10.0,
        "callee_agent_id": "research-agent",
        "callee_agent_type": "analysis",
        "callee_trust_score": 0.90,
        "callee_org_id": str(uuid.uuid4()),
        "capability_type": "analysis",
        "context_scope": ["deal_metadata"],
        "estimated_cost_usd": 0.15,
        "budget_cap_usd": 1.0,
        "time_of_day": "14:00",
        "delegation_depth": 0,
        "timestamp": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return DelegationContext(**defaults)


class _FakePolicy:
    """Minimal object that looks like a Policy ORM model."""

    def __init__(
        self,
        rule_yaml: str,
        name: str = "test-policy",
        priority: int = 10,
        policy_id: str | None = None,
        version: int = 1,
    ) -> None:
        self.id = policy_id or str(uuid.uuid4())
        self.name = name
        self.priority = priority
        self.rule_yaml = rule_yaml
        self.version = version
        self.enabled = True


class _FakeRedis:
    """Minimal async Redis mock for policy engine tests.

    Always returns None from get() to force DB loading,
    avoiding SQLAlchemy ORM deserialization issues with _dict_to_policy.
    """

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ex: int = 0) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass


class _FakeDB:
    """Minimal async DB mock — returns canned policies."""

    def __init__(self, policies: list[_FakePolicy] | None = None) -> None:
        self._policies = policies or []

    async def execute(self, stmt: object) -> "_FakeResult":
        return _FakeResult(self._policies)


class _FakeResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._items)


class _FakeScalars:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


class TestPolicyEngineEvaluation:
    """Tests for PolicyEngine.evaluate() — pure logic, no DB needed."""

    @pytest.mark.asyncio
    async def test_no_policies_blocks_by_default(self) -> None:
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([]))
        ctx = _make_context()
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "block"
        assert "No policies" in decision.reason

    @pytest.mark.asyncio
    async def test_matching_allow_policy_allows(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "  callee_type: analysis\n"
                "conditions: []\n"
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))
        ctx = _make_context()
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "allow"
        assert decision.policy_id == str(policy.id)

    @pytest.mark.asyncio
    async def test_non_matching_allow_blocks(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: execution\n"
                "  callee_type: analysis\n"
                "conditions: []\n"
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))
        ctx = _make_context(caller_agent_type="research")
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "block"

    @pytest.mark.asyncio
    async def test_time_condition_between(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions:\n"
                "  - field: time_of_day\n"
                "    operator: between\n"
                '    value: ["06:00", "18:00"]\n'
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        # Within hours → allow
        ctx = _make_context(time_of_day="14:00")
        assert (await engine.evaluate(ctx, "org-1")).decision == "allow"

        # Outside hours → block
        ctx = _make_context(time_of_day="22:00")
        assert (await engine.evaluate(ctx, "org-1")).decision == "block"

    @pytest.mark.asyncio
    async def test_budget_condition(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions:\n"
                "  - field: caller.budget_remaining_usd\n"
                "    operator: \">\"\n"
                "    value: 5.0\n"
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        ctx = _make_context(caller_budget_remaining_usd=10.0)
        assert (await engine.evaluate(ctx, "org-1")).decision == "allow"

        ctx = _make_context(caller_budget_remaining_usd=2.0)
        assert (await engine.evaluate(ctx, "org-1")).decision == "block"

    @pytest.mark.asyncio
    async def test_hil_threshold_triggers_pause(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions: []\n"
                "hil_threshold_usd: 0.10\n"
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        ctx = _make_context(estimated_cost_usd=0.50)
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "pause"

    @pytest.mark.asyncio
    async def test_hil_threshold_below_allows(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions: []\n"
                "hil_threshold_usd: 1.00\n"
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        ctx = _make_context(estimated_cost_usd=0.05)
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "allow"

    @pytest.mark.asyncio
    async def test_context_scope_subset_of(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions:\n"
                "  - field: context_scope\n"
                "    operator: subset_of\n"
                '    value: ["deal_metadata", "account_tier"]\n'
                "on_violation: block_and_alert\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        ctx = _make_context(context_scope=["deal_metadata"])
        assert (await engine.evaluate(ctx, "org-1")).decision == "allow"

        ctx = _make_context(context_scope=["deal_metadata", "secret_data"])
        assert (await engine.evaluate(ctx, "org-1")).decision == "block"

    @pytest.mark.asyncio
    async def test_audit_only_violation_allows(self) -> None:
        policy = _FakePolicy(
            rule_yaml=(
                "allow:\n"
                "  caller_type: research\n"
                "conditions:\n"
                "  - field: caller.budget_remaining_usd\n"
                "    operator: \">\"\n"
                "    value: 100.0\n"
                "on_violation: audit_only\n"
            )
        )
        engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([policy]))

        ctx = _make_context(caller_budget_remaining_usd=5.0)
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "allow"

    @pytest.mark.asyncio
    async def test_priority_ordering_first_match_wins(self) -> None:
        block_policy = _FakePolicy(
            rule_yaml="allow:\n  caller_type: research\nconditions:\n  - field: caller.budget_remaining_usd\n    operator: \">\"\n    value: 100\non_violation: block_and_alert\n",
            priority=10,
        )
        allow_policy = _FakePolicy(
            rule_yaml="allow:\n  caller_type: research\nconditions: []\non_violation: block_and_alert\n",
            priority=20,
        )
        engine = PolicyEngine(
            redis_client=_FakeRedis(),
            db=_FakeDB([block_policy, allow_policy]),
        )

        ctx = _make_context(caller_budget_remaining_usd=5.0)
        decision = await engine.evaluate(ctx, "org-1")
        assert decision.decision == "block"
        assert decision.policy_id == str(block_policy.id)


class TestPolicyEngineConditionOperators:
    """Tests for individual condition operators."""

    def _engine(self) -> PolicyEngine:
        return PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB([]))

    def test_resolve_field(self) -> None:
        ctx = _make_context(delegation_depth=3)
        engine = self._engine()
        assert engine._resolve_field("delegation_depth", ctx) == 3
        assert engine._resolve_field("nonexistent_field", ctx) is None

    def test_operator_equals(self) -> None:
        engine = self._engine()
        ctx = _make_context(capability_type="research")
        assert engine._evaluate_condition(
            {"field": "capability_type", "operator": "==", "value": "research"}, ctx
        )
        assert not engine._evaluate_condition(
            {"field": "capability_type", "operator": "==", "value": "analysis"}, ctx
        )

    def test_operator_in(self) -> None:
        engine = self._engine()
        ctx = _make_context(capability_type="research")
        assert engine._evaluate_condition(
            {"field": "capability_type", "operator": "in", "value": ["research", "analysis"]}, ctx
        )
        assert not engine._evaluate_condition(
            {"field": "capability_type", "operator": "in", "value": ["generation"]}, ctx
        )

    def test_operator_not_in(self) -> None:
        engine = self._engine()
        ctx = _make_context(capability_type="research")
        assert engine._evaluate_condition(
            {"field": "capability_type", "operator": "not_in", "value": ["generation"]}, ctx
        )

    def test_on_violation_mapping(self) -> None:
        engine = self._engine()
        assert engine._on_violation_to_decision("block_and_alert") == "block"
        assert engine._on_violation_to_decision("block_silent") == "block"
        assert engine._on_violation_to_decision("pause_for_approval") == "pause"
        assert engine._on_violation_to_decision("audit_only") == "allow"
        assert engine._on_violation_to_decision("unknown") == "block"
