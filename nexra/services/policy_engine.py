import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import redis.asyncio as aioredis
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.policy import Policy

logger = logging.getLogger("nexra.services.policy_engine")

POLICY_CACHE_TTL = 60


@dataclass
class DelegationContext:
    """All fields populated before policy evaluation begins."""

    caller_agent_id: str
    caller_agent_type: str
    caller_org_id: str
    caller_budget_remaining_usd: float

    callee_agent_id: str
    callee_agent_type: str
    callee_trust_score: float
    callee_org_id: str

    capability_type: str
    context_scope: list[str]
    estimated_cost_usd: float
    budget_cap_usd: float

    time_of_day: str
    delegation_depth: int
    timestamp: datetime


@dataclass
class PolicyDecision:
    """Output of policy evaluation."""

    decision: str  # 'allow' | 'block' | 'pause'
    policy_id: str | None
    policy_version: int | None
    policy_name: str | None
    reason: str
    on_violation: str


@dataclass
class CachedPolicy:
    id: str
    name: str
    priority: int
    rule_yaml: str
    version: int


class PolicyEngine:
    """Evaluates delegation policies for an organization.

    Default-deny: no policies = block all delegations.
    Evaluation order: priority ASC (lower number = first).
    First matching policy wins.
    """

    def __init__(self, redis_client: aioredis.Redis, db: AsyncSession) -> None:
        self.redis = redis_client
        self.db = db

    async def evaluate(self, ctx: DelegationContext, org_id: str) -> PolicyDecision:
        """Evaluate all org policies against a delegation context."""
        policies = await self._load_policies(org_id)

        if not policies:
            return PolicyDecision(
                decision="block",
                policy_id=None,
                policy_version=None,
                policy_name=None,
                reason="No policies defined for org (default deny)",
                on_violation="block_silent",
            )

        for policy in policies:
            rule = yaml.safe_load(policy.rule_yaml)

            if not self._matches_allow(rule.get("allow", {}), ctx):
                continue

            conditions = rule.get("conditions", [])
            failed_condition = None
            for cond in conditions:
                if not self._evaluate_condition(cond, ctx):
                    failed_condition = cond
                    break

            if failed_condition:
                on_v = rule.get("on_violation", "block_and_alert")
                decision = self._on_violation_to_decision(on_v)
                return PolicyDecision(
                    decision=decision,
                    policy_id=str(policy.id),
                    policy_version=policy.version,
                    policy_name=policy.name,
                    reason=(
                        f"Condition failed: {failed_condition.get('field')} "
                        f"{failed_condition.get('operator')} {failed_condition.get('value')}"
                    ),
                    on_violation=on_v,
                )

            hil = rule.get("hil_threshold_usd")
            if hil is not None and ctx.estimated_cost_usd > float(hil):
                return PolicyDecision(
                    decision="pause",
                    policy_id=str(policy.id),
                    policy_version=policy.version,
                    policy_name=policy.name,
                    reason=f"Estimated cost ${ctx.estimated_cost_usd:.4f} exceeds HiTL threshold ${hil}",
                    on_violation="pause_for_approval",
                )

            return PolicyDecision(
                decision="allow",
                policy_id=str(policy.id),
                policy_version=policy.version,
                policy_name=policy.name,
                reason="Policy matched and all conditions passed",
                on_violation="",
            )

        return PolicyDecision(
            decision="block",
            policy_id=None,
            policy_version=None,
            policy_name=None,
            reason="No matching policy found (default deny)",
            on_violation="block_silent",
        )

    # ─── Allow Block Matching ─────────────────────────────────

    def _matches_allow(self, allow: dict, ctx: DelegationContext) -> bool:
        if "caller_type" in allow:
            if ctx.caller_agent_type != allow["caller_type"]:
                return False
        if "callee_type" in allow:
            if ctx.callee_agent_type != allow["callee_type"]:
                return False
        if "capability_types" in allow:
            if ctx.capability_type not in allow["capability_types"]:
                return False
        return True

    # ─── Condition Evaluation ─────────────────────────────────

    def _evaluate_condition(self, cond: dict, ctx: DelegationContext) -> bool:
        field = cond.get("field", "")
        operator = cond.get("operator", "")
        value = cond.get("value")

        actual = self._resolve_field(field, ctx)
        if actual is None:
            logger.warning(f"Unknown policy condition field: {field}")
            return False

        try:
            if operator == ">":
                return float(actual) > float(value)
            elif operator == "<":
                return float(actual) < float(value)
            elif operator == ">=":
                return float(actual) >= float(value)
            elif operator == "<=":
                return float(actual) <= float(value)
            elif operator == "==":
                return str(actual) == str(value)
            elif operator == "!=":
                return str(actual) != str(value)
            elif operator == "in":
                return str(actual) in [str(v) for v in value]
            elif operator == "not_in":
                return str(actual) not in [str(v) for v in value]
            elif operator == "between":
                low, high = str(value[0]), str(value[1])
                actual_str = str(actual)
                if low <= high:
                    return low <= actual_str <= high
                else:
                    return actual_str >= low or actual_str <= high
            elif operator == "subset_of":
                if isinstance(actual, list):
                    return all(item in value for item in actual)
                return False
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except (ValueError, TypeError, IndexError) as e:
            logger.warning(f"Condition evaluation error: {e}")
            return False

    def _resolve_field(self, field: str, ctx: DelegationContext) -> object:
        field_map = {
            "caller.budget_remaining_usd": ctx.caller_budget_remaining_usd,
            "caller_budget_remaining_usd": ctx.caller_budget_remaining_usd,
            "caller_agent_type": ctx.caller_agent_type,
            "caller_org_id": ctx.caller_org_id,
            "callee_trust_score": ctx.callee_trust_score,
            "callee_agent_type": ctx.callee_agent_type,
            "callee_agent_id": ctx.callee_agent_id,
            "callee_org_id": ctx.callee_org_id,
            "capability_type": ctx.capability_type,
            "context_scope": ctx.context_scope,
            "estimated_cost_usd": ctx.estimated_cost_usd,
            "budget_cap_usd": ctx.budget_cap_usd,
            "time_of_day": ctx.time_of_day,
            "delegation_depth": ctx.delegation_depth,
        }
        return field_map.get(field)

    def _on_violation_to_decision(self, on_violation: str) -> str:
        if on_violation in ("block_and_alert", "block_silent"):
            return "block"
        elif on_violation == "pause_for_approval":
            return "pause"
        elif on_violation == "audit_only":
            return "allow"
        return "block"

    # ─── Policy Loading with Cache ────────────────────────────

    async def _load_policies(self, org_id: str) -> list[Policy | CachedPolicy]:
        cache_key = f"policies:{org_id}"

        cached = await self.redis.get(cache_key)
        if cached:
            policy_dicts = json.loads(cached)
            return [self._dict_to_policy(d) for d in policy_dicts]

        result = await self.db.execute(
            select(Policy)
            .where(Policy.org_id == org_id, Policy.enabled == True)  # noqa: E712
            .order_by(Policy.priority.asc())
        )
        policies = list(result.scalars().all())

        if policies:
            cache_data = json.dumps(
                [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "priority": p.priority,
                        "rule_yaml": p.rule_yaml,
                        "version": p.version,
                    }
                    for p in policies
                ]
            )
            await self.redis.set(cache_key, cache_data, ex=POLICY_CACHE_TTL)

        return policies

    def _dict_to_policy(self, d: dict) -> CachedPolicy:
        return CachedPolicy(
            id=d["id"],
            name=d["name"],
            priority=d["priority"],
            rule_yaml=d["rule_yaml"],
            version=d["version"],
        )

    async def invalidate_cache(self, org_id: str) -> None:
        await self.redis.delete(f"policies:{org_id}")
