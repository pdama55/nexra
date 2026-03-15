# Phase 5 — Policy Engine

> **TDD Sections**: §7 (Policy Engine — Design & Implementation), §6.2 (Policy CRUD endpoints)
>
> **48-Hour Block**: Hours 17–22
>
> **Depends On**: Phase 2 (Auth + Security) complete. Can be developed in parallel with Phases 3-4.

---

## 1. Prerequisites

- [ ] Auth middleware working (get_authenticated_org)
- [ ] Redis available for policy caching
- [ ] Policy ORM model exists (from Phase 1)

---

## 2. Objective

Deliver the complete policy engine:

- PolicyEngine class with YAML parsing, DelegationContext evaluation, all 10 operators
- Default-deny behavior (no policies = block all delegations)
- Policy CRUD endpoints: POST /policies, GET /policies, GET /policies/{id}, PUT /policies/{id}, DELETE /policies/{id}
- Redis caching of parsed policies per org (TTL 60s)
- PolicyDecision output dataclass

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Policy format | YAML stored as TEXT | TDD §7.1. Human-readable, easy to version control. |
| Evaluation order | Priority ASC (lower number = first) | TDD §7.4. First matching policy wins. |
| Default behavior | Block all (secure by default) | TDD §7.4. No policies = no delegations allowed. |
| Caching | Redis with TTL 60s per org | TDD §1.2. Reduces DB reads on hot path. |
| Evaluation | Synchronous Python (no async in eval loop) | TDD §7.4. Policy eval must be < 20ms P99. |

---

## 4. File-by-File Implementation Guide

### 4.1 `services/policy_engine.py`

**Path**: `nexra/services/policy_engine.py`

This is the most critical pure-logic module. It has ZERO external dependencies in the evaluation hot path (no DB, no HTTP, no async). Policies are loaded from cache/DB before evaluation begins.

```python
import yaml
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from models.policy import Policy

logger = logging.getLogger("nexra.services.policy_engine")

POLICY_CACHE_TTL = 60  # seconds


@dataclass
class DelegationContext:
    """All fields populated before policy evaluation begins.

    Every field maps to a condition field in YAML policies.
    Field names in YAML conditions use dot notation for nested access:
    - 'caller.budget_remaining_usd' → self.caller_budget_remaining_usd
    - 'callee_trust_score' → self.callee_trust_score
    """
    # Caller
    caller_agent_id: str
    caller_agent_type: str       # capability_type of the caller
    caller_org_id: str
    caller_budget_remaining_usd: float

    # Callee
    callee_agent_id: str
    callee_agent_type: str       # capability_type of the callee
    callee_trust_score: float
    callee_org_id: str

    # Task
    capability_type: str          # callee's capability_type
    context_scope: list[str]      # requested data grants
    estimated_cost_usd: float
    budget_cap_usd: float

    # Environment
    time_of_day: str              # 'HH:MM' UTC
    delegation_depth: int         # nesting level (0 = top-level)
    timestamp: datetime


@dataclass
class PolicyDecision:
    """Output of policy evaluation."""
    decision: str          # 'allow' | 'block' | 'pause'
    policy_id: str | None  # UUID of the matching policy (None if default deny)
    policy_version: int | None
    policy_name: str | None
    reason: str            # human-readable explanation
    on_violation: str      # action taken: block_and_alert, block_silent, audit_only, pause_for_approval


class PolicyEngine:
    """Evaluates delegation policies for an organization.

    Constructor dependencies:
        redis_client: aioredis.Redis — for policy caching
        db: AsyncSession — for loading policies from DB
    """

    def __init__(self, redis_client: aioredis.Redis, db: AsyncSession) -> None:
        self.redis = redis_client
        self.db = db

    async def evaluate(self, ctx: DelegationContext, org_id: str) -> PolicyDecision:
        """Evaluate all org policies against a delegation context.

        Algorithm:
        1. Load policies from cache or DB, sorted by priority ASC
        2. If no policies exist → DEFAULT BLOCK (secure by default)
        3. For each policy in priority order:
           a. Check if 'allow' block matches (caller_type, callee_type, capability_types)
           b. If allow doesn't match → skip to next policy
           c. If allow matches → evaluate all conditions
           d. If any condition fails → return block/pause based on on_violation
           e. If all conditions pass → check HiTL threshold
           f. If HiTL triggered → return pause
           g. Otherwise → return allow
        4. No policy matched → DEFAULT BLOCK

        Returns:
            PolicyDecision with decision, policy reference, and reason.
        """
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

            # Check allow block
            if not self._matches_allow(rule.get("allow", {}), ctx):
                continue  # This policy doesn't apply to this delegation

            # Evaluate all conditions
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
                    reason=f"Condition failed: {failed_condition.get('field')} {failed_condition.get('operator')} {failed_condition.get('value')}",
                    on_violation=on_v,
                )

            # Check HiTL threshold
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

            # All checks passed — ALLOW
            return PolicyDecision(
                decision="allow",
                policy_id=str(policy.id),
                policy_version=policy.version,
                policy_name=policy.name,
                reason="Policy matched and all conditions passed",
                on_violation="",
            )

        # No policy matched → default block
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
        """Check if the allow block matches the delegation context.

        All specified fields must match. Unspecified fields are wildcards.
        """
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
        """Evaluate a single condition against the delegation context.

        Supported operators: >, <, >=, <=, ==, !=, in, not_in, between, subset_of
        """
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
                # For time_of_day: value = ["06:00", "22:00"]
                return str(value[0]) <= str(actual) <= str(value[1])
            elif operator == "subset_of":
                # actual is a list, value is the allowed superset
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
        """Resolve a dot-notation field name to a value from DelegationContext.

        Mapping:
        - 'caller.budget_remaining_usd' → ctx.caller_budget_remaining_usd
        - 'callee_trust_score' → ctx.callee_trust_score
        - 'time_of_day' → ctx.time_of_day
        - 'delegation_depth' → ctx.delegation_depth
        - 'context_scope' → ctx.context_scope
        - 'estimated_cost_usd' → ctx.estimated_cost_usd
        - 'capability_type' → ctx.capability_type
        - 'caller_org_id' → ctx.caller_org_id
        - 'callee_agent_id' → ctx.callee_agent_id
        - 'callee_agent_type' → ctx.callee_agent_type
        """
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
        """Map on_violation action to a policy decision."""
        if on_violation in ("block_and_alert", "block_silent"):
            return "block"
        elif on_violation == "pause_for_approval":
            return "pause"
        elif on_violation == "audit_only":
            return "allow"  # audit_only logs but allows
        return "block"

    # ─── Policy Loading with Cache ────────────────────────────

    async def _load_policies(self, org_id: str) -> list[Policy]:
        """Load enabled policies for org, sorted by priority ASC.

        Uses Redis cache with 60s TTL to avoid DB reads on hot path.
        """
        cache_key = f"policies:{org_id}"

        # Try cache first
        cached = await self.redis.get(cache_key)
        if cached:
            policy_dicts = json.loads(cached)
            return [self._dict_to_policy(d) for d in policy_dicts]

        # Load from DB
        result = await self.db.execute(
            select(Policy)
            .where(Policy.org_id == org_id, Policy.enabled == True)
            .order_by(Policy.priority.asc())
        )
        policies = list(result.scalars().all())

        # Cache for 60s
        if policies:
            cache_data = json.dumps([
                {
                    "id": str(p.id),
                    "name": p.name,
                    "priority": p.priority,
                    "rule_yaml": p.rule_yaml,
                    "version": p.version,
                }
                for p in policies
            ])
            await self.redis.set(cache_key, cache_data, ex=POLICY_CACHE_TTL)

        return policies

    def _dict_to_policy(self, d: dict) -> Policy:
        """Reconstruct a minimal Policy object from cached dict."""
        p = Policy.__new__(Policy)
        p.id = d["id"]
        p.name = d["name"]
        p.priority = d["priority"]
        p.rule_yaml = d["rule_yaml"]
        p.version = d["version"]
        return p

    async def invalidate_cache(self, org_id: str) -> None:
        """Invalidate policy cache for an org. Call after policy CRUD."""
        await self.redis.delete(f"policies:{org_id}")
```

### 4.2 `api/schemas/policies.py`

**Path**: `nexra/api/schemas/policies.py`

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import yaml


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    priority: int = Field(100, ge=1, le=10000, description="Lower = evaluated first")
    allow: dict = Field(..., description="Allow block: caller_type, callee_type, capability_types")
    conditions: list[dict] = Field(default_factory=list, description="List of condition objects")
    hil_threshold_usd: float | None = Field(None, gt=0, description="HiTL trigger threshold")
    on_violation: str = Field("block_and_alert", description="Action on violation")

    @field_validator("on_violation")
    @classmethod
    def validate_on_violation(cls, v: str) -> str:
        allowed = {"block_and_alert", "block_silent", "audit_only", "pause_for_approval"}
        if v not in allowed:
            raise ValueError(f"on_violation must be one of: {', '.join(sorted(allowed))}")
        return v

    def to_yaml(self) -> str:
        """Convert the policy to YAML for storage."""
        policy_dict = {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "enabled": True,
            "allow": self.allow,
            "conditions": self.conditions,
            "on_violation": self.on_violation,
        }
        if self.hil_threshold_usd is not None:
            policy_dict["hil_threshold_usd"] = self.hil_threshold_usd
        return yaml.dump(policy_dict, default_flow_style=False)


class PolicyUpdateRequest(BaseModel):
    description: str | None = None
    priority: int | None = Field(None, ge=1, le=10000)
    allow: dict | None = None
    conditions: list[dict] | None = None
    hil_threshold_usd: float | None = None
    on_violation: str | None = None

    @field_validator("on_violation")
    @classmethod
    def validate_on_violation(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"block_and_alert", "block_silent", "audit_only", "pause_for_approval"}
        if v not in allowed:
            raise ValueError(f"on_violation must be one of: {', '.join(sorted(allowed))}")
        return v


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str | None
    priority: int
    version: int
    enabled: bool
    allow: dict
    conditions: list[dict]
    hil_threshold_usd: float | None
    on_violation: str
    created_at: datetime


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total_count: int
```

### 4.3 `api/routers/policies.py`

**Path**: `nexra/api/routers/policies.py`

```python
import time
import yaml
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import redis.asyncio as aioredis

from api.dependencies import get_authenticated_org, get_db, get_redis
from api.schemas.policies import (
    PolicyCreateRequest, PolicyUpdateRequest,
    PolicyResponse, PolicyListResponse,
)
from api.schemas.common import DataResponse, MetaResponse
from models.policy import Policy
from models.organization import Organization
from core.errors import NexraError, POLICY_NOT_FOUND
from services.policy_engine import PolicyEngine

router = APIRouter(prefix="/policies", tags=["policies"])


def _parse_policy_yaml(rule_yaml: str) -> dict:
    """Parse stored YAML back to dict for response."""
    return yaml.safe_load(rule_yaml) or {}


def _policy_to_response(p: Policy) -> PolicyResponse:
    parsed = _parse_policy_yaml(p.rule_yaml)
    return PolicyResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        priority=p.priority,
        version=p.version,
        enabled=p.enabled,
        allow=parsed.get("allow", {}),
        conditions=parsed.get("conditions", []),
        hil_threshold_usd=parsed.get("hil_threshold_usd"),
        on_violation=parsed.get("on_violation", "block_and_alert"),
        created_at=p.created_at,
    )


@router.post("")
async def create_policy(
    request: Request,
    body: PolicyCreateRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Create a new delegation policy."""
    start = time.perf_counter()

    policy = Policy(
        org_id=org.id,
        name=body.name,
        description=body.description,
        priority=body.priority,
        rule_yaml=body.to_yaml(),
        version=1,
        enabled=True,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)

    # Invalidate policy cache
    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    latency = round((time.perf_counter() - start) * 1000, 2)
    return DataResponse(
        data=_policy_to_response(policy),
        meta=MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    )


@router.get("")
async def list_policies(
    request: Request,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """List all policies for the authenticated org."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.org_id == org.id).order_by(Policy.priority.asc())
    )
    policies = list(result.scalars().all())

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": PolicyListResponse(
            policies=[_policy_to_response(p) for p in policies],
            total_count=len(policies),
        ),
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    }


@router.get("/{policy_id}")
async def get_policy(
    request: Request,
    policy_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    """Get a policy by ID with version history."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    # Get all versions
    versions_result = await db.execute(
        select(Policy).where(Policy.org_id == org.id, Policy.name == policy.name)
        .order_by(Policy.version.desc())
    )
    versions = [_policy_to_response(p) for p in versions_result.scalars().all()]

    latency = round((time.perf_counter() - start) * 1000, 2)
    return {
        "data": {
            "current": _policy_to_response(policy),
            "versions": versions,
        },
        "meta": MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    }


@router.put("/{policy_id}")
async def update_policy(
    request: Request,
    policy_id: str,
    body: PolicyUpdateRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Update a policy. Creates a new version — old version preserved."""
    start = time.perf_counter()

    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    existing = result.scalar_one_or_none()
    if not existing:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    # Parse existing YAML
    current = yaml.safe_load(existing.rule_yaml) or {}

    # Apply updates
    if body.allow is not None:
        current["allow"] = body.allow
    if body.conditions is not None:
        current["conditions"] = body.conditions
    if body.hil_threshold_usd is not None:
        current["hil_threshold_usd"] = body.hil_threshold_usd
    if body.on_violation is not None:
        current["on_violation"] = body.on_violation
    if body.priority is not None:
        pass  # priority set on the new Policy row, not in YAML
    if body.description is not None:
        pass  # description set on the new Policy row

    # Disable old version
    existing.enabled = False
    await db.flush()

    # Create new version
    new_policy = Policy(
        org_id=org.id,
        name=existing.name,
        description=body.description if body.description is not None else existing.description,
        priority=body.priority if body.priority is not None else existing.priority,
        rule_yaml=yaml.dump(current, default_flow_style=False),
        version=existing.version + 1,
        enabled=True,
    )
    db.add(new_policy)
    await db.commit()
    await db.refresh(new_policy)

    # Invalidate cache
    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    latency = round((time.perf_counter() - start) * 1000, 2)
    return DataResponse(
        data=_policy_to_response(new_policy),
        meta=MetaResponse(request_id=getattr(request.state, "request_id", None), latency_ms=latency),
    )


@router.delete("/{policy_id}")
async def disable_policy(
    request: Request,
    policy_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Disable a policy (soft delete). Preserves history."""
    result = await db.execute(
        select(Policy).where(Policy.id == policy_id, Policy.org_id == org.id)
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise NexraError(404, POLICY_NOT_FOUND, f"Policy '{policy_id}' not found")

    policy.enabled = False
    await db.commit()

    engine = PolicyEngine(redis_client, db)
    await engine.invalidate_cache(str(org.id))

    return {"data": {"id": str(policy.id), "enabled": False}}
```

**Register in `api/main.py`**:
```python
from api.routers.policies import router as policies_router
app.include_router(policies_router, prefix="/v1")
```

---

## 5. Guardrails

1. **DO NOT** allow default-allow behavior. If no policies exist, ALL delegations are blocked.
2. **DO NOT** use `yaml.load()` — always use `yaml.safe_load()` to prevent code injection.
3. **DO NOT** evaluate policies asynchronously. The eval loop is pure Python, synchronous, and must complete in < 20ms.
4. **DO NOT** skip cache invalidation after policy CRUD operations.
5. **DO NOT** delete policy rows from the database. Disable them (soft delete). Audit log entries reference policy_id and version.
6. **DO NOT** allow policies from one org to affect another org's delegations.
7. **DO NOT** use `eval()` or `exec()` for condition evaluation. All operators are hardcoded in `_evaluate_condition`.

### Critical Implementation Notes

**`caller_type` / `callee_type` in YAML `allow` block**: These map to `DelegationContext.caller_agent_type` and `DelegationContext.callee_agent_type`, which are the `capability_type` field of the Agent model (e.g., `"research"`, `"execution"`). They are NOT arbitrary labels. When writing policies, the `caller_type` and `callee_type` values must match the `capability_type` enum values from the Agent model.

**`between` operator and midnight crossing**: The `between` operator uses string comparison (`str(value[0]) <= str(actual) <= str(value[1])`). This works for time ranges that don't cross midnight (e.g., `["06:00", "22:00"]`). For overnight ranges like `["22:00", "06:00"]`, the string comparison fails because `"22:00" <= "02:00"` is False. To support overnight ranges, the agent implementing this should add a special case:
```python
elif operator == "between":
    low, high = str(value[0]), str(value[1])
    actual_str = str(actual)
    if low <= high:
        return low <= actual_str <= high
    else:
        # Overnight range: e.g., ["22:00", "06:00"]
        return actual_str >= low or actual_str <= high
```

**Policy YAML schema reference**: Every policy stored in `rule_yaml` must conform to this structure:
```yaml
name: "policy-name"
description: "optional description"
priority: 10
enabled: true
allow:
  caller_type: "execution"       # optional — matches DelegationContext.caller_agent_type
  callee_type: "research"        # optional — matches DelegationContext.callee_agent_type
  capability_types:              # optional — list of allowed callee capability_types
    - "research"
    - "analysis"
conditions:                      # list of condition objects, ALL must pass
  - field: "callee_trust_score"
    operator: ">="
    value: 0.50
  - field: "time_of_day"
    operator: "between"
    value: ["06:00", "22:00"]
  - field: "context_scope"
    operator: "subset_of"
    value: ["deal_metadata", "company_info"]
hil_threshold_usd: 1.00         # optional — triggers HiTL if estimated_cost exceeds this
on_violation: "block_and_alert"  # block_and_alert | block_silent | audit_only | pause_for_approval
```

**DelegationContext construction guide**: Phase 6's `DelegationService.initiate()` constructs the `DelegationContext` from live data. Here is the exact mapping:

| DelegationContext field | Source |
|---|---|
| `caller_agent_id` | `caller_agent.agent_id` |
| `caller_agent_type` | `caller_agent.capability_type` |
| `caller_org_id` | `str(org.id)` |
| `caller_budget_remaining_usd` | `request.budget_cap_usd` (simplified for MVP; full impl reads from BudgetService) |
| `callee_agent_id` | `callee.agent_id` |
| `callee_agent_type` | `callee.capability_type` |
| `callee_trust_score` | `float(callee.trust_score)` |
| `callee_org_id` | `str(callee.org_id)` |
| `capability_type` | `callee.capability_type` |
| `context_scope` | `request.context_scope` |
| `estimated_cost_usd` | `float(callee.pricing.get("per_call_usd", 0))` |
| `budget_cap_usd` | `request.budget_cap_usd` |
| `time_of_day` | `datetime.now(timezone.utc).strftime("%H:%M")` |
| `delegation_depth` | Computed from parent chain (0 for top-level) |
| `timestamp` | `datetime.now(timezone.utc)` |

---

## 6. Verification Checklist

```bash
# 1. Create a policy
curl -X POST http://localhost:8000/v1/policies \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sales-to-research",
    "description": "Sales agents may hire research agents during business hours",
    "priority": 10,
    "allow": {"caller_type": "sales_agent", "callee_type": "research_agent", "capability_types": ["research", "analysis"]},
    "conditions": [
      {"field": "time_of_day", "operator": "between", "value": ["06:00", "22:00"]},
      {"field": "caller.budget_remaining_usd", "operator": ">", "value": 0.10}
    ],
    "hil_threshold_usd": 1.00,
    "on_violation": "block_and_alert"
  }'
# Expected: 200 with policy data, version=1

# 2. List policies
curl http://localhost:8000/v1/policies -H "Authorization: Bearer <api_key>"
# Expected: policies array with 1 item

# 3. Update policy (creates new version)
curl -X PUT http://localhost:8000/v1/policies/<policy_id> \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"priority": 5}'
# Expected: version=2, priority=5

# 4. Disable policy
curl -X DELETE http://localhost:8000/v1/policies/<policy_id> \
  -H "Authorization: Bearer <api_key>"
# Expected: { data: { enabled: false } }
```

---

## 7. Test Cases

| Test ID | Category | Description | Mock Setup | Assertion |
|---------|----------|-------------|------------|-----------|
| T-001 | Policy | No policies defined → delegation blocked | Empty policies table | decision=='block', reason contains 'default deny' |
| T-002 | Policy | Allow policy matches, all conditions pass → allow | Create matching policy | decision=='allow', policy_id is set |
| T-003 | Policy | Allow policy matches, condition fails → block | Policy with time condition, ctx outside hours | decision=='block', on_violation=='block_and_alert' |
| T-004 | Policy | estimated_cost > hil_threshold_usd → pause | Policy with hil=1.00, cost=1.50 | decision=='pause' |
| T-005 | Policy | Context scope NOT subset of allowed → block | Policy allows ['a','b'], ctx requests ['a','c'] | decision=='block' |
| T-POL-006 | Operator | `>` operator works | field=0.5, operator='>', value=0.1 | True |
| T-POL-007 | Operator | `<` operator works | field=3, operator='<', value=5 | True |
| T-POL-008 | Operator | `between` operator for time | time='14:00', between ['06:00','22:00'] | True |
| T-POL-009 | Operator | `between` fails outside range | time='23:00', between ['06:00','22:00'] | False |
| T-POL-010 | Operator | `subset_of` passes | scope=['a'], allowed=['a','b'] | True |
| T-POL-011 | Operator | `subset_of` fails | scope=['a','c'], allowed=['a','b'] | False |
| T-POL-012 | Operator | `in` operator | type='research', in=['research','analysis'] | True |
| T-POL-013 | Operator | `not_in` operator | id='agent-1', not_in=['agent-2'] | True |
| T-POL-014 | Operator | `==` operator | type='research', =='research' | True |
| T-POL-015 | Operator | `!=` operator | org='a', !='b' | True |
| T-POL-016 | Priority | Lower priority policy evaluated first | Policy A (priority=10), Policy B (priority=20) | Policy A's decision returned |
| T-POL-017 | Priority | First matching policy wins | Policy A allows, Policy B blocks | decision=='allow' from Policy A |
| T-POL-018 | Cache | Policies loaded from Redis cache on second call | Load once, check Redis, load again | Second load hits cache (no DB query) |
| T-POL-019 | Cache | Cache invalidated after policy create | Create policy, check cache deleted | Redis key deleted |
| T-POL-020 | CRUD | Create policy returns version=1 | POST /policies | version==1 |
| T-POL-021 | CRUD | Update creates new version | PUT /policies/{id} | version==2, old version disabled |
| T-POL-022 | CRUD | Delete soft-disables policy | DELETE /policies/{id} | enabled==False, row still exists |
| T-POL-023 | Security | Policy from org A not visible to org B | Create policy under org A | GET from org B returns 404 |
| T-POL-024 | audit_only | on_violation='audit_only' returns allow | Policy with audit_only | decision=='allow' |
