# Phase 06 — Policy Engine & Policy CRUD

**Phase:** 06 / 12 | **TDD Sections:** §7 (Policy Engine), §6 (Policy endpoints) | **48h Block:** Block 6 (17-22h)

> ⚠️ **Prerequisite:** Phase 05 acceptance criteria all GREEN before starting.

---

## Objective

Implement the YAML-based `PolicyEngine` (pure Python, zero external calls), the `DelegationContext` and `PolicyDecision` dataclasses, all 10 condition operators, Redis caching, and the Policy CRUD endpoints. Policy engine unit tests T-001 through T-005 must pass.

---

## Claude Code Prompt

```
You are implementing the Policy Engine for Nexra (pure Python, YAML policies, Redis caching).

TASK: Implement PolicyEngine per TDD §7, and policy CRUD endpoints.

Requirements:

1. **api/schemas/policies.py**:
   ```python
   class PolicyCreateRequest(BaseModel):
       name: str = Field(..., max_length=200)
       rule_yaml: str  # YAML string — validated by service layer
       priority: int = 100
       enabled: bool = True
   
   class PolicyResponse(BaseModel):
       id: str
       name: str
       rule_yaml: str
       priority: int
       enabled: bool
       version: int
       created_at: datetime
       updated_at: datetime
   ```

2. **services/policy_engine.py** — EXACTLY as TDD §7.2-7.4:
   ```python
   from dataclasses import dataclass
   from datetime import datetime
   
   @dataclass
   class DelegationContext:
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
       time_of_day: str  # 'HH:MM' UTC
       delegation_depth: int
       timestamp: datetime
   
   @dataclass
   class PolicyDecision:
       decision: str  # 'allow' | 'block' | 'pause'
       policy_id: str | None
       policy_version: int | None
       policy_name: str | None
       reason: str
       on_violation: str
   
   class PolicyEngine:
       def __init__(self, redis_client, db: AsyncSession): ...
   
       async def evaluate(self, ctx: DelegationContext, org_id: str) -> PolicyDecision:
           # 1. Load policies from Redis cache (key: f"policies:{org_id}") with 60s TTL
           #    If cache miss: load from DB sorted by priority ASC, serialize to JSON, cache
           # 2. If no policies: return PolicyDecision(decision='block', reason='No policies defined for org (default deny)')
           # 3. For each policy (priority ASC):
           #    a. yaml.safe_load(policy.rule_yaml)
           #    b. Check allow block (_matches_allow)
           #    c. Check all conditions (_evaluate_condition)
           #    d. If conditions fail: apply on_violation behavior
           #    e. Check hil_threshold_usd → return pause
           #    f. All pass → return allow
           # 4. No match → default block
   ```

3. **Condition operators** — implement ALL 10 from TDD §7.5:
   ```python
   def _evaluate_condition(self, cond: dict, ctx: DelegationContext) -> bool:
       field = cond['field']
       operator = cond['operator']
       value = cond['value']
       
       # Resolve field value from ctx: 'caller.budget_remaining_usd', 'time_of_day', etc.
       # Operators: '>', '<', '>=', '<=', '==', '!=', 'in', 'not_in', 'between', 'subset_of'
       # 'between': only for time_of_day (HH:MM range, UTC)
       # 'subset_of': list field must be subset of value list
   ```

4. **Policy CRUD** — services/policy_service.py:
   ```python
   class PolicyService:
       async def create(self, org_id: str, data: PolicyCreateRequest) -> Policy:
           # Validate rule_yaml: yaml.safe_load(data.rule_yaml) must not raise
           # Validate YAML has required keys: name, priority, enabled, (allow or deny)
           # Create Policy record with version=1
           # Invalidate Redis cache: await redis.delete(f"policies:{org_id}")
   
       async def update(self, org_id: str, policy_id: str, data: PolicyUpdateRequest) -> Policy:
           # Bump version += 1
           # Invalidate Redis cache
   
       async def delete(self, org_id: str, policy_id: str) -> None:
           # Soft delete: enabled=False (never hard delete)
           # Invalidate Redis cache
   ```

5. **api/routers/policies.py**:
   - POST /policies → 201
   - GET /policies → 200 list (can filter by enabled=true/false)
   - GET /policies/{id} → 200
   - PUT /policies/{id} → 200 (bumps version)
   - DELETE /policies/{id} → 204 (soft delete, enabled=false)

CRITICAL: PolicyEngine has NO FastAPI imports. It is a pure Python class.
All evaluation logic (yaml parsing, operator evaluation, default-deny) runs synchronously within evaluate().
```

---

## Guardrails

- ✅ **Default-deny** — if `policies` list is empty for org, ALL delegations are blocked (T-001)
- ✅ **No-match default-deny** — if no policy matches, delegation is blocked (not allowed)
- ✅ **Redis cache TTL = 60 seconds** per org — key: `f"policies:{org_id}"`
- ✅ **Cache invalidated on any policy mutation** (create/update/delete)
- ✅ **Soft delete only** — `enabled=False`, never `DELETE` the policy row (audit history preserved)
- ✅ **`version` bumped on every PUT** — immutable history via version field
- ✅ **`yaml.safe_load()`** not `yaml.load()` — `safe_load` only, never `yaml.load` (injection risk)
- ✅ **`subset_of` operator** — verify `context_scope` is a subset of the allowed list (T-005)
- ❌ **No FastAPI imports in `PolicyEngine`** — it's a pure service class
- ✅ **`hil_threshold_usd`** → `decision='pause'` (not block) when cost exceeds threshold (T-004)

---

## Acceptance Criteria

```bash
# 1. Create a policy
curl -X POST http://localhost:8000/policies \
  -H "Authorization: Bearer nx_live_<key>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sales-to-research",
    "priority": 10,
    "rule_yaml": "name: sales-to-research\npriority: 10\nenabled: true\nallow:\n  caller_type: sales_agent\n  callee_type: research\nconditions: []\non_violation: block_and_alert"
  }'
# → 201 with policy id

# 2. List policies
curl -H "Authorization: Bearer nx_live_<key>" http://localhost:8000/policies
# → list with the created policy

# 3. Policy engine unit tests
poetry run pytest tests/unit/test_policy_engine.py -v -x
# All 5 test cases (T-001 to T-005) must PASS
```

---

## Test Cases (TDD §20.2 — T-001 through T-005)

```bash
poetry run pytest tests/unit/test_policy_engine.py -v
```

**Write `tests/unit/test_policy_engine.py` with:**
- **T-001**: No policies defined → `PolicyDecision(decision='block', reason='No policies...')`
- **T-002**: Allow policy matches, all conditions pass → `decision='allow'`, `policy_id` is set
- **T-003**: Allow policy matches, condition fails → `decision='block'`, `on_violation='block_and_alert'`
- **T-004**: `estimated_cost_usd > hil_threshold_usd` → `decision='pause'`
- **T-005**: `context_scope` NOT subset of allowed list → `decision='block'`

```bash
# Integration: policy CRUD
poetry run pytest tests/integration/test_policy_crud.py -v
# - Create policy → verify in DB
# - Update policy → version bumped
# - Delete policy → enabled=False (not deleted from DB)
# - Redis cache invalidated after mutation
```
