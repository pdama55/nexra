"""Performance sanity test for policy evaluation."""

import time
import uuid
from datetime import datetime, timezone

import pytest

from services.policy_engine import DelegationContext, PolicyEngine


class _FakePolicy:
    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.name = "allow-all"
        self.priority = 10
        self.rule_yaml = "allow:\n  caller_type: research\nconditions: []\non_violation: block_and_alert\n"
        self.version = 1


class _FakeRedis:
    async def get(self, key: str):
        return None

    async def set(self, key: str, value: str, ex: int = 0):
        return None


class _FakeResult:
    def __init__(self, policies):
        self._policies = policies

    def scalars(self):
        class _Scalars:
            def __init__(self, policies):
                self._policies = policies

            def all(self):
                return self._policies

        return _Scalars(self._policies)


class _FakeDB:
    def __init__(self) -> None:
        self.policies = [_FakePolicy()]

    async def execute(self, stmt):
        return _FakeResult(self.policies)


@pytest.mark.asyncio
async def test_policy_eval_p99_under_20ms() -> None:
    engine = PolicyEngine(redis_client=_FakeRedis(), db=_FakeDB())
    ctx = DelegationContext(
        caller_agent_id="caller",
        caller_agent_type="research",
        caller_org_id=str(uuid.uuid4()),
        caller_budget_remaining_usd=10.0,
        callee_agent_id="callee",
        callee_agent_type="analysis",
        callee_trust_score=0.9,
        callee_org_id=str(uuid.uuid4()),
        capability_type="analysis",
        context_scope=["deal_metadata"],
        estimated_cost_usd=0.1,
        budget_cap_usd=1.0,
        time_of_day="12:00",
        delegation_depth=0,
        timestamp=datetime.now(timezone.utc),
    )

    samples_ms = []
    for _ in range(200):
        start = time.perf_counter()
        await engine.evaluate(ctx, "org-1")
        samples_ms.append((time.perf_counter() - start) * 1000)

    p99 = sorted(samples_ms)[int(0.99 * len(samples_ms)) - 1]
    assert p99 < 20.0
