# Phase 07 — Delegation Initiation (Steps 1-9)

**Phase:** 07 / 12 | **TDD Sections:** §8.1 steps 1-9, §6.5 | **48h Block:** Block 7 (22-27h)

> ⚠️ **Prerequisite:** Phase 06 acceptance criteria all GREEN before starting.

---

## Objective

Implement `DelegationService.initiate()` steps 1-9 (everything up to but NOT including webhook delivery). This covers: callee resolution, caller validation, schema validation, cost estimation, budget check, depth check, policy evaluation, delegation record creation, and block/pause handling. Establish `GET /delegations/{id}` and the HiTL `POST /delegations/{id}/approve` and `/reject` endpoints.

---

## Claude Code Prompt

```
You are implementing the Delegation initiation flow for Nexra (steps 1-9 of 13-step flow per TDD §8.1).

TASK: Implement DelegationService.initiate() steps 1-9 and the /delegate + /delegations/* endpoints.

Requirements:

1. **api/schemas/delegations.py**:
   ```python
   class DelegateRequest(BaseModel):
       callee_agent_id: str
       task: dict  # {"type": str, "input": dict}
       context_scope: list[str] = []
       budget_cap_usd: float = Field(..., gt=0)
       timeout_ms: int = Field(30000, ge=1000, le=120000)
       callback_url: str | None = None
       parent_delegation_id: str | None = None  # for chained delegations
       include_cross_org: bool = False
   
   class DelegationStatusResponse(BaseModel):
       delegation_id: str
       status: str
       policy_result: dict | None
       result: dict | None
       usage: dict | None
       created_at: datetime
       completed_at: datetime | None
   ```

2. **services/delegation_service.py** — 13-step initiate(), steps 1-9 ONLY for this phase:
   ```python
   class DelegationService:
       def __init__(self, db, redis, policy_engine, budget_service, audit_service,
                    webhook_service, billing_service, trust_service, openai_client): ...
   
       async def initiate(self, org: Organization, caller_agent: Agent, request: DelegateRequest) -> DelegationResult:
   
           # ── STEP 1: Resolve callee ───────────────────────────────
           callee = await self._resolve_callee(org.id, request.callee_agent_id, request.include_cross_org)
           if not callee:
               raise NexraError(404, 'AGENT_NOT_FOUND', 'Callee agent not found')
   
           # ── STEP 2: Validate caller status ───────────────────────
           if caller_agent.status == 'quarantined':
               raise NexraError(403, 'AGENT_QUARANTINED', 'Caller agent is quarantined')
   
           # ── STEP 3: Schema validate task payload ─────────────────
           try:
               jsonschema.validate(request.task['input'], callee.input_schema)
           except jsonschema.ValidationError as e:
               raise NexraError(422, 'SCHEMA_VALIDATION_FAILED', str(e.message))
   
           # ── STEP 4: Estimate cost ─────────────────────────────────
           estimated_cost = callee.pricing['per_call_usd']
   
           # ── STEP 5: Check budget ──────────────────────────────────
           budget_ok = await self.budget_service.check_and_reserve(
               org.id, caller_agent.agent_id, estimated_cost, request.budget_cap_usd
           )
           if not budget_ok.allowed:
               raise NexraError(402, 'BUDGET_EXCEEDED', f'Remaining budget: ${budget_ok.remaining_usd:.4f}')
   
           # ── STEP 6: Compute delegation depth ─────────────────────
           depth = await self._compute_depth(request.parent_delegation_id)
           max_depth = org.max_delegation_depth or settings.max_delegation_depth_default
           if depth >= max_depth:
               raise NexraError(400, 'MAX_DEPTH_EXCEEDED', f'Delegation depth {depth} at limit')
   
           # ── STEP 7: Policy evaluation ─────────────────────────────
           ctx = DelegationContext(
               caller_agent_id=caller_agent.agent_id,
               caller_agent_type=caller_agent.capability_type,
               caller_org_id=str(org.id),
               caller_budget_remaining_usd=budget_ok.remaining_usd,
               callee_agent_id=callee.agent_id,
               callee_agent_type=callee.capability_type,
               callee_trust_score=float(callee.trust_score),
               callee_org_id=str(callee.org_id),
               capability_type=callee.capability_type,
               context_scope=request.context_scope,
               estimated_cost_usd=estimated_cost,
               budget_cap_usd=request.budget_cap_usd,
               time_of_day=datetime.now(timezone.utc).strftime('%H:%M'),
               delegation_depth=depth,
               timestamp=datetime.now(timezone.utc)
           )
           decision = await self.policy_engine.evaluate(ctx, str(org.id))
   
           # ── STEP 8: Create delegation record ──────────────────────
           delegation = Delegation(
               caller_org_id=org.id, caller_agent_id=caller_agent.agent_id,
               callee_org_id=callee.org_id, callee_agent_id=callee.agent_id,
               task=request.task,
               task_hash=sha256_json(request.task),  # SHA-256 hex of sorted JSON
               context_scope=request.context_scope,
               policy_id=decision.policy_id, policy_version=decision.policy_version,
               policy_decision=decision.decision,
               budget_cap_usd=request.budget_cap_usd, estimated_cost_usd=estimated_cost,
               callback_url=request.callback_url, delegation_depth=depth,
               parent_delegation_id=request.parent_delegation_id,
               timeout_ms=request.timeout_ms
           )
   
           # ── STEP 9: Handle non-allow decisions ────────────────────
           if decision.decision == 'block':
               delegation.status = 'blocked'
               self.db.add(delegation)
               await self.db.commit()
               await self.audit_service.append(org.id, 'delegation_blocked',
                   caller_agent.agent_id, callee.agent_id,
                   {'delegation_id': str(delegation.id), 'reason': decision.reason,
                    'policy_id': decision.policy_id})
               raise NexraError(403, 'POLICY_BLOCKED', decision.reason, {'policy_id': decision.policy_id})
   
           if decision.decision == 'pause':
               delegation.status = 'pending_approval'
               self.db.add(delegation)
               await self.db.commit()
               await self._trigger_hil_notification(org, delegation, decision)
               await self.audit_service.append(org.id, 'hil_triggered', ...)
               return DelegationResult(status='pending_approval', delegation_id=str(delegation.id),
                                       poll_url=f'/v1/delegations/{delegation.id}',
                                       approval_deadline=...)
           
           # Steps 10-13 (webhook, token, delivery) — left as TODO for Phase 08
           self.db.add(delegation)
           await self.db.commit()
           return DelegationResult(status='in_flight', delegation_id=str(delegation.id))
   ```

3. **core/crypto.py** — add `sha256_json(obj: dict) -> str`:
   ```python
   import hashlib, json
   def sha256_json(obj: dict) -> str:
       return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',',':')).encode()).hexdigest()
   ```

4. **services/budget_service.py** — check_and_reserve() (TDD §11.1):
   - SELECT FOR UPDATE on agent_budgets for daily + monthly rows
   - Check per-delegation cap (estimated_cost > request_cap → fail)
   - Check daily cap if row exists
   - Return BudgetCheckResult(allowed=bool, remaining_usd=float)

5. **api/routers/delegations.py**:
   - POST /delegate → 200 (sync) or 202 (async/HiTL)
   - GET /delegations/{id} → 200 DelegationStatusResponse
   - POST /delegations/{id}/approve → 200 (admin)
   - POST /delegations/{id}/reject → 200 (admin)

Error codes to return:
- 403 POLICY_BLOCKED — policy blocked
- 402 BUDGET_EXCEEDED — budget exceeded
- 422 SCHEMA_VALIDATION_FAILED — task payload wrong
- 404 AGENT_NOT_FOUND — callee not found
- 400 MAX_DEPTH_EXCEEDED — depth limit
- 403 AGENT_QUARANTINED — caller is quarantined
```

---

## Guardrails

- ✅ **Steps execute in exactly this order**: resolve callee → validate caller → schema check → cost estimate → budget check → depth check → policy eval → create record → handle decision
- ✅ **`audit_log` entry written for BOTH `block` AND `pause` decisions** in step 9
- ✅ **`SELECT FOR UPDATE`** on `agent_budgets` — prevents race conditions (T-007)
- ✅ **`task_hash`** = SHA-256 of sorted compact JSON of `task` — for deduplication/audit
- ✅ **`delegation_depth` computed** from parent chain — recursive lookup capped at `max_delegation_depth`
- ✅ **HiTL notification sent on `pause`** before returning 202 response
- ❌ **Do NOT call webhook in this phase** — webhook delivery is Phase 08
- ✅ **`POLICY_BLOCKED` error must include `policy_id`** in `details` field
- ✅ **`BUDGET_EXCEEDED` error must include `remaining_budget_usd`** in `details` (TDD §6.5)

---

## Acceptance Criteria

```bash
# 1. Policy block returns 403
curl -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer nx_live_<key>" \
  -H "X-Agent-ID: sales-agent-v1" \
  -d '{"callee_agent_id": "research-agent-v1", "task": {...}, "budget_cap_usd": 1.0}'
# Before policy exists → 403 POLICY_BLOCKED (default deny)

# 2. Budget exceeded returns 402
# Set budget cap < per_call_usd of callee
curl ... -d '{"budget_cap_usd": 0.01}'
# → 402 BUDGET_EXCEEDED with remaining_budget_usd in details

# 3. Schema validation failure returns 422
# Send task.input missing a required field
# → 422 SCHEMA_VALIDATION_FAILED

# 4. Delegation record created in DB
docker exec nexra-postgres-1 psql -U nexra -d nexra -c \
  "SELECT status, policy_decision FROM delegations ORDER BY created_at DESC LIMIT 1;"
```

---

## Test Cases (TDD §20.2)

```bash
poetry run pytest tests/integration/test_delegation_initiate.py -v
# - T-006: estimated_cost + spent > daily cap → 402
# - T-007: concurrent delegations don't double-spend (run 2 concurrent, check spent_usd)
# - 403 on POLICY_BLOCKED with policy_id in details
# - 422 on SCHEMA_VALIDATION_FAILED when required field missing
# - 400 MAX_DEPTH_EXCEEDED when depth >= org limit
# - Delegation record created with correct status in DB
```
