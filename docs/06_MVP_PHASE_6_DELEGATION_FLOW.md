# Phase 6 — Delegation Flow (13-Step)

> **TDD Sections**: §8 (Delegation Flow), §12.1 (Webhook Delivery — sync), §4.4 (Delegation JWT), §4.5 (HMAC Signing), §6.5 (POST /delegate), §6.6 (POST /delegations/{id}/complete)
>
> **48-Hour Block**: Hours 22–31
>
> **Depends On**: Phases 3 (Registry), 4 (Discovery), and 5 (Policy Engine) ALL complete.

---

## 1. Prerequisites

- [ ] AgentService — register, get_by_agent_id working
- [ ] DiscoveryService — discover working with composite scoring
- [ ] PolicyEngine — evaluate returning PolicyDecision
- [ ] core/jwt.py — issue_delegation_token, verify_delegation_token working
- [ ] core/crypto.py — sign_webhook_payload, verify_webhook_signature, sha256_json, encrypt/decrypt_aes_gcm working
- [ ] Redis available for JWT single-use enforcement

---

## 2. Objective

Deliver the complete 13-step delegation flow:

1. Resolve callee agent
2. Validate caller status
3. Schema-validate task payload against callee's input_schema
4. Estimate cost
5. Check budget (stub — full impl in Phase 7)
6. Compute delegation depth
7. Policy evaluation
8. Create delegation record
9. Handle non-allow decisions (block → 403, pause → 202)
10. Issue delegation JWT
11. Build and sign webhook payload
12. Deliver webhook (synchronous for MVP)
13. Return result to caller

Plus: POST /delegations/{id}/complete (callee posts result back), GET /delegations/{id} (status polling).

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sync delivery (MVP) | Direct HTTPX call, single retry on 5xx | TDD §12.1. Async Celery delivery is P1. |
| Timeout | min(caller timeout, 30s default) | TDD §12.1. Prevents unbounded waits. |
| Schema validation | jsonschema.validate() against callee's input_schema | TDD §6.5. Catches malformed payloads before webhook. |
| Task hash | SHA-256 of canonical JSON | TDD §8. Tamper detection in audit log. |
| Budget check | Stub returning allowed=True for MVP | Full BudgetService in Phase 7. |

---

## 4. File-by-File Implementation Guide

### 4.1 `api/schemas/delegations.py`

**Path**: `nexra/api/schemas/delegations.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime


class DelegateRequest(BaseModel):
    callee_agent_id: str = Field(..., description="Target agent's agent_id")
    task: dict = Field(..., description="Task payload — validated against callee's input_schema")
    context_scope: list[str] = Field(default_factory=list, description="Explicit data grant keys")
    budget_cap_usd: float = Field(..., gt=0, description="Max cost for this delegation")
    timeout_ms: int = Field(30000, ge=1000, le=120000, description="Webhook timeout in ms")
    callback_url: str | None = Field(None, description="Async callback URL (null=sync)")
    include_cross_org: bool = Field(False, description="Allow cross-org callee resolution")


class PolicyResultResponse(BaseModel):
    policy_id: str | None
    policy_version: int | None
    decision: str


class UsageResponse(BaseModel):
    cost_usd: float
    latency_ms: int
    llm_tokens: int | None = None


class DelegationResponse(BaseModel):
    delegation_id: str
    status: str
    policy_result: PolicyResultResponse | None = None
    result: dict | None = None
    usage: UsageResponse | None = None
    poll_url: str | None = None
    approval_deadline: str | None = None


class DelegationCompleteRequest(BaseModel):
    result: dict = Field(..., description="Task result — validated against output_schema")
    usage: dict | None = Field(None, description="Self-reported usage: llm_tokens, external_api_cost_usd")


class DelegationStatusResponse(BaseModel):
    delegation_id: str
    status: str
    policy_result: PolicyResultResponse | None = None
    result: dict | None = None
    usage: UsageResponse | None = None
    created_at: datetime
    completed_at: datetime | None = None
```

### 4.2 `services/webhook_service.py`

**Path**: `nexra/services/webhook_service.py`

Synchronous webhook delivery for MVP. Handles HMAC signing, timeout, single retry on 5xx.

```python
import time
import asyncio
import logging
import httpx

from core.crypto import sign_webhook_payload
from core.errors import NexraError, DELEGATION_TIMEOUT, CALLEE_WEBHOOK_FAILED, WEBHOOK_SIGNATURE_REJECTED

logger = logging.getLogger("nexra.services.webhook")


class WebhookService:
    """Delivers signed webhooks to callee agents.

    MVP: synchronous HTTPX delivery with single retry on 5xx.
    Production (P1): Celery async delivery with exponential backoff.
    """

    MAX_TIMEOUT_SECONDS = 30

    async def deliver_and_await(
        self,
        webhook_url: str,
        payload: dict,
        webhook_secret: str,
        delegation_id: str,
        timeout_ms: int,
    ) -> dict:
        """Deliver webhook and await response (synchronous mode).

        Steps:
        1. Sign payload with HMAC-SHA256
        2. POST to callee's webhook_url with signature header
        3. On 401/403: fail immediately (signature rejected, no retry)
        4. On 5xx: single retry after 1s
        5. On timeout: raise DELEGATION_TIMEOUT
        6. On success: return response body

        Returns:
            Callee's response body as dict.

        Raises:
            NexraError(408, DELEGATION_TIMEOUT)
            NexraError(503, CALLEE_WEBHOOK_FAILED)
            NexraError(503, WEBHOOK_SIGNATURE_REJECTED)
        """
        import json as _json
        signature = sign_webhook_payload(payload, webhook_secret)
        effective_timeout = min(timeout_ms / 1000, self.MAX_TIMEOUT_SECONDS - 0.1)

        # CRITICAL: Serialize payload with sorted keys and no whitespace.
        # This MUST match the serialization used by sign_webhook_payload().
        # Using httpx's json= parameter would use a different serialization
        # (unsorted keys, with spaces) which would cause HMAC mismatch on the callee side.
        body_bytes = _json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-Nexra-Signature": signature,
            "X-Delegation-ID": delegation_id,
            "X-Nexra-Timestamp": str(int(time.time())),
        }

        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            try:
                resp = await client.post(webhook_url, content=body_bytes, headers=headers)
            except httpx.TimeoutException:
                raise NexraError(408, DELEGATION_TIMEOUT, f"Callee did not respond within {timeout_ms}ms")
            except httpx.RequestError as e:
                raise NexraError(503, CALLEE_WEBHOOK_FAILED, f"Webhook delivery failed: {str(e)[:200]}")

            # Signature rejected — do NOT retry
            if resp.status_code in (401, 403):
                raise NexraError(
                    503, WEBHOOK_SIGNATURE_REJECTED,
                    "Callee returned 401/403 — likely HMAC mismatch. Not retried."
                )

            # Server error — single retry
            if resp.status_code >= 500:
                logger.warning(f"Webhook returned {resp.status_code}, retrying once...")
                await asyncio.sleep(1)
                try:
                    resp = await client.post(webhook_url, content=body_bytes, headers=headers)
                except (httpx.TimeoutException, httpx.RequestError) as e:
                    raise NexraError(503, CALLEE_WEBHOOK_FAILED, f"Webhook retry failed: {str(e)[:200]}")

            if not resp.is_success:
                raise NexraError(503, CALLEE_WEBHOOK_FAILED, f"Callee returned {resp.status_code}")

            return resp.json()
```

### 4.3 `services/delegation_service.py`

**Path**: `nexra/services/delegation_service.py`

The central orchestrator. Implements all 13 steps.

```python
import time
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis
import jsonschema

from models.organization import Organization
from models.agent import Agent
from models.delegation import Delegation
from api.schemas.delegations import DelegateRequest, DelegationResponse, PolicyResultResponse, UsageResponse
from services.policy_engine import PolicyEngine, DelegationContext
from services.webhook_service import WebhookService
from core.crypto import sha256_json, encrypt_aes_gcm, decrypt_aes_gcm
from core.jwt import issue_delegation_token, verify_delegation_token
from core.config import get_settings
from core.errors import (
    NexraError, AGENT_NOT_FOUND, AGENT_QUARANTINED,
    SCHEMA_VALIDATION_FAILED, BUDGET_EXCEEDED, MAX_DEPTH_EXCEEDED,
    POLICY_BLOCKED, DELEGATION_NOT_FOUND, DELEGATION_ALREADY_COMPLETE,
    OUTPUT_SCHEMA_FAILED,
)

logger = logging.getLogger("nexra.services.delegation")


class DelegationService:
    """Orchestrates the 13-step delegation flow.

    Constructor dependencies:
        db: AsyncSession
        redis_client: aioredis.Redis
        policy_engine: PolicyEngine
        webhook_service: WebhookService
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        policy_engine: PolicyEngine,
        webhook_service: WebhookService,
    ) -> None:
        self.db = db
        self.redis = redis_client
        self.policy_engine = policy_engine
        self.webhook_service = webhook_service

    async def initiate(
        self,
        org: Organization,
        caller_agent: Agent,
        request: DelegateRequest,
    ) -> DelegationResponse:
        """Execute the 13-step delegation flow.

        Steps 1-9 are pre-webhook. Steps 10-12 are webhook delivery.
        Step 13 is result handling.
        """
        start_time = time.perf_counter()
        settings = get_settings()

        # ── STEP 1: Resolve callee agent ──────────────────────
        callee = await self._resolve_callee(
            str(org.id), request.callee_agent_id, request.include_cross_org
        )
        if not callee:
            raise NexraError(404, AGENT_NOT_FOUND, f"Callee agent '{request.callee_agent_id}' not found")

        # ── STEP 2: Validate caller status ────────────────────
        if caller_agent.status == "quarantined":
            raise NexraError(403, AGENT_QUARANTINED, "Caller agent is quarantined")

        # ── STEP 3: Schema validate task payload ──────────────
        if callee.input_schema and callee.input_schema.get("type"):
            try:
                task_input = request.task.get("input", request.task)
                jsonschema.validate(task_input, callee.input_schema)
            except jsonschema.ValidationError as e:
                raise NexraError(422, SCHEMA_VALIDATION_FAILED, f"Task payload validation failed: {e.message}")

        # ── STEP 4: Estimate cost ─────────────────────────────
        estimated_cost = float(callee.pricing.get("per_call_usd", 0))

        # ── STEP 5: Check budget (stub for MVP — full in Phase 7)
        if estimated_cost > request.budget_cap_usd:
            raise NexraError(
                402, BUDGET_EXCEEDED,
                f"Estimated cost ${estimated_cost:.4f} exceeds budget cap ${request.budget_cap_usd:.4f}",
                {"remaining_budget_usd": request.budget_cap_usd},
            )

        # ── STEP 6: Compute delegation depth ──────────────────
        depth = 0  # Top-level for MVP. Nested delegations tracked in P1.
        max_depth = settings.max_delegation_depth_default
        if depth >= max_depth:
            raise NexraError(400, MAX_DEPTH_EXCEEDED, f"Delegation depth {depth} exceeds limit {max_depth}")

        # ── STEP 7: Policy evaluation ─────────────────────────
        ctx = DelegationContext(
            caller_agent_id=caller_agent.agent_id,
            caller_agent_type=caller_agent.capability_type,
            caller_org_id=str(org.id),
            caller_budget_remaining_usd=request.budget_cap_usd,  # Simplified for MVP
            callee_agent_id=callee.agent_id,
            callee_agent_type=callee.capability_type,
            callee_trust_score=float(callee.trust_score),
            callee_org_id=str(callee.org_id),
            capability_type=callee.capability_type,
            context_scope=request.context_scope,
            estimated_cost_usd=estimated_cost,
            budget_cap_usd=request.budget_cap_usd,
            time_of_day=datetime.now(timezone.utc).strftime("%H:%M"),
            delegation_depth=depth,
            timestamp=datetime.now(timezone.utc),
        )
        decision = await self.policy_engine.evaluate(ctx, str(org.id))

        # ── STEP 8: Create delegation record ──────────────────
        delegation = Delegation(
            caller_org_id=org.id,
            caller_agent_id=caller_agent.agent_id,
            callee_org_id=callee.org_id,
            callee_agent_id=callee.agent_id,
            task=request.task,
            task_hash=sha256_json(request.task),
            context_scope=request.context_scope,
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            policy_decision=decision.decision,
            budget_cap_usd=request.budget_cap_usd,
            estimated_cost_usd=estimated_cost,
            callback_url=request.callback_url,
            delegation_depth=depth,
            status="pending",
        )

        # ── STEP 9: Handle non-allow decisions ────────────────
        if decision.decision == "block":
            delegation.status = "blocked"
            self.db.add(delegation)
            await self.db.commit()
            raise NexraError(
                403, POLICY_BLOCKED, decision.reason,
                {"policy_id": decision.policy_id, "policy_name": decision.policy_name},
            )

        if decision.decision == "pause":
            delegation.status = "pending_approval"
            self.db.add(delegation)
            await self.db.commit()
            return DelegationResponse(
                delegation_id=str(delegation.id),
                status="pending_approval",
                policy_result=PolicyResultResponse(
                    policy_id=decision.policy_id,
                    policy_version=decision.policy_version,
                    decision="pause",
                ),
                poll_url=f"/v1/delegations/{delegation.id}",
            )

        # ── STEP 10: Issue delegation token ───────────────────
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)
        delegation_token = issue_delegation_token(
            org_secret, str(delegation.id), callee.agent_id, request.context_scope
        )

        # ── STEP 11: Build webhook payload ────────────────────
        webhook_payload = {
            "delegation_id": str(delegation.id),
            "task": request.task,
            "context_scope": request.context_scope,
            "budget_cap_usd": request.budget_cap_usd,
            "timeout_ms": request.timeout_ms,
            "delegation_token": delegation_token,
            "complete_url": f"{settings.api_base_url}/v1/delegations/{delegation.id}/complete",
        }

        # ── STEP 12: Deliver webhook ──────────────────────────
        delegation.status = "in_flight"
        self.db.add(delegation)
        await self.db.commit()

        try:
            callee_response = await self.webhook_service.deliver_and_await(
                callee.webhook_url,
                webhook_payload,
                callee.webhook_secret,
                str(delegation.id),
                request.timeout_ms,
            )
        except NexraError as e:
            # Update delegation status on failure
            delegation.status = "timeout" if e.code == "DELEGATION_TIMEOUT" else "failed"
            delegation.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            raise

        # ── STEP 13: Process result ───────────────────────────
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        actual_cost = estimated_cost  # Simplified for MVP

        delegation.status = "completed"
        delegation.result = callee_response
        delegation.actual_cost_usd = actual_cost
        delegation.latency_ms = latency_ms
        delegation.llm_tokens = callee_response.get("usage", {}).get("llm_tokens")
        delegation.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        return DelegationResponse(
            delegation_id=str(delegation.id),
            status="completed",
            policy_result=PolicyResultResponse(
                policy_id=decision.policy_id,
                policy_version=decision.policy_version,
                decision="allow",
            ),
            result=callee_response.get("result", callee_response),
            usage=UsageResponse(
                cost_usd=actual_cost,
                latency_ms=latency_ms,
                llm_tokens=delegation.llm_tokens,
            ),
        )

    async def complete(
        self,
        delegation_id: str,
        token: str,
        result: dict,
        usage: dict | None,
        org: Organization,
    ) -> DelegationResponse:
        """Called by callee to post result back via /delegations/{id}/complete.

        Steps:
        1. Verify delegation JWT (signature + single-use)
        2. Verify delegation_id matches JWT claim
        3. Validate result against callee's output_schema
        4. Update delegation status to 'completed'
        5. Return result
        """
        settings = get_settings()
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)

        # Step 1: Verify JWT
        payload = await verify_delegation_token(token, org_secret, self.redis)

        # Step 2: Verify delegation_id matches
        if payload["delegation_id"] != delegation_id:
            raise NexraError(401, "INVALID_DELEGATION_TOKEN", "Delegation ID mismatch in token")

        # Load delegation
        db_result = await self.db.execute(
            select(Delegation).where(Delegation.id == delegation_id)
        )
        delegation = db_result.scalar_one_or_none()
        if not delegation:
            raise NexraError(404, DELEGATION_NOT_FOUND, f"Delegation '{delegation_id}' not found")

        if delegation.status == "completed":
            raise NexraError(409, DELEGATION_ALREADY_COMPLETE, "Delegation already completed")

        # Step 3: Validate result against output_schema (if callee has one)
        callee_result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == payload["callee_agent_id"],
                Agent.org_id == delegation.callee_org_id,
            )
        )
        callee = callee_result.scalar_one_or_none()
        if callee and callee.output_schema and callee.output_schema.get("type"):
            try:
                jsonschema.validate(result, callee.output_schema)
            except jsonschema.ValidationError as e:
                raise NexraError(422, OUTPUT_SCHEMA_FAILED, f"Result validation failed: {e.message}")

        # Step 4: Update delegation
        delegation.status = "completed"
        delegation.result = result
        delegation.completed_at = datetime.now(timezone.utc)
        if usage:
            delegation.llm_tokens = usage.get("llm_tokens")
            external_cost = usage.get("external_api_cost_usd", 0)
            delegation.actual_cost_usd = float(delegation.estimated_cost_usd or 0) + float(external_cost)
        await self.db.commit()

        return DelegationResponse(
            delegation_id=str(delegation.id),
            status="completed",
            result=result,
        )

    async def get_status(self, org_id: str, delegation_id: str) -> Delegation:
        """Get delegation status for polling."""
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        delegation = result.scalar_one_or_none()
        if not delegation:
            raise NexraError(404, DELEGATION_NOT_FOUND, f"Delegation '{delegation_id}' not found")
        return delegation

    # ─── Private Methods ──────────────────────────────────────

    async def _resolve_callee(
        self, caller_org_id: str, callee_agent_id: str, include_cross_org: bool
    ) -> Agent | None:
        """Resolve callee agent by agent_id, respecting org boundaries."""
        # Same org first
        result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == callee_agent_id,
                Agent.org_id == caller_org_id,
            )
        )
        agent = result.scalar_one_or_none()
        if agent:
            return agent

        # Cross-org (public agents only)
        if include_cross_org:
            result = await self.db.execute(
                select(Agent).where(
                    Agent.agent_id == callee_agent_id,
                    Agent.is_public == True,
                    Agent.status != "quarantined",
                )
            )
            return result.scalar_one_or_none()

        return None
```

### 4.4 `api/routers/delegations.py`

**Path**: `nexra/api/routers/delegations.py`

```python
import time
from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from api.dependencies import get_authenticated_org_and_agent, get_authenticated_org, get_db, get_redis
from api.schemas.delegations import (
    DelegateRequest, DelegationResponse, DelegationCompleteRequest,
    DelegationStatusResponse, PolicyResultResponse, UsageResponse,
)
from api.schemas.common import DataResponse, MetaResponse
from services.delegation_service import DelegationService
from services.policy_engine import PolicyEngine
from services.webhook_service import WebhookService
from models.organization import Organization
from models.agent import Agent

router = APIRouter(tags=["delegations"])


def _build_delegation_service(db: AsyncSession, redis_client: aioredis.Redis) -> DelegationService:
    policy_engine = PolicyEngine(redis_client, db)
    webhook_service = WebhookService()
    return DelegationService(db, redis_client, policy_engine, webhook_service)


@router.post("/delegate")
async def delegate(
    request: Request,
    body: DelegateRequest,
    org_and_agent: tuple[Organization, Agent] = Depends(get_authenticated_org_and_agent),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Initiate a delegation (full 13-step flow).

    Requires X-Agent-ID header — delegations are agent-initiated.
    """
    org, caller_agent = org_and_agent
    start = time.perf_counter()

    service = _build_delegation_service(db, redis_client)
    result = await service.initiate(org, caller_agent, body)

    latency = round((time.perf_counter() - start) * 1000, 2)

    status_code = 200 if result.status == "completed" else 202
    from fastapi.responses import JSONResponse
    response_body = DataResponse(
        data=result,
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=response_body.model_dump(mode="json"),
    )


@router.get("/delegations/{delegation_id}")
async def get_delegation_status(
    request: Request,
    delegation_id: str,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Get delegation status and result. Polling endpoint for async delegations."""
    start = time.perf_counter()

    service = _build_delegation_service(db, redis_client)
    delegation = await service.get_status(str(org.id), delegation_id)

    latency = round((time.perf_counter() - start) * 1000, 2)

    return DataResponse(
        data=DelegationStatusResponse(
            delegation_id=str(delegation.id),
            status=delegation.status,
            policy_result=PolicyResultResponse(
                policy_id=str(delegation.policy_id) if delegation.policy_id else None,
                policy_version=delegation.policy_version,
                decision=delegation.policy_decision or "",
            ) if delegation.policy_id else None,
            result=delegation.result,
            usage=UsageResponse(
                cost_usd=float(delegation.actual_cost_usd or 0),
                latency_ms=delegation.latency_ms or 0,
                llm_tokens=delegation.llm_tokens,
            ) if delegation.actual_cost_usd else None,
            created_at=delegation.created_at,
            completed_at=delegation.completed_at,
        ),
        meta=MetaResponse(
            request_id=getattr(request.state, "request_id", None),
            latency_ms=latency,
        ),
    )


@router.post("/delegations/{delegation_id}/complete")
async def complete_delegation(
    request: Request,
    delegation_id: str,
    body: DelegationCompleteRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Callee posts result back to Nexra.

    Auth: Delegation JWT (not org API key).
    """
    # Extract JWT from Bearer token
    if not authorization.startswith("Bearer "):
        from core.errors import NexraError
        raise NexraError(401, "UNAUTHORIZED", "Missing Bearer token")

    token = authorization[7:]

    # We need the caller org to decrypt the JWT secret (JWT was signed with caller org's secret).
    from sqlalchemy import select
    from models.delegation import Delegation
    from models.organization import Organization as OrgModel
    from core.errors import NexraError, DELEGATION_NOT_FOUND

    deleg_result = await db.execute(
        select(Delegation).where(Delegation.id == delegation_id)
    )
    delegation = deleg_result.scalar_one_or_none()
    if not delegation:
        raise NexraError(404, DELEGATION_NOT_FOUND, "Delegation not found")

    # Load the CALLER org (the JWT was signed with the caller org's per-org secret)
    org_result = await db.execute(
        select(OrgModel).where(OrgModel.id == delegation.caller_org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise NexraError(500, "INTERNAL_ERROR", "Caller organization not found")

    service = _build_delegation_service(db, redis_client)
    resp = await service.complete(
        delegation_id, token, body.result, body.usage, org
    )

    return DataResponse(
        data=resp,
        meta=MetaResponse(request_id=getattr(request.state, "request_id", None)),
    )
```

**Register in `api/main.py`**:
```python
from api.routers.delegations import router as delegations_router
app.include_router(delegations_router, prefix="/v1")
```

---

## 5. Guardrails

1. **DO NOT** skip schema validation on task payloads. Always validate against callee's input_schema before webhook delivery.
2. **DO NOT** retry webhooks that return 401/403. Signature rejection is permanent.
3. **DO NOT** allow delegation tokens to be reused. Redis jti enforcement is mandatory.
4. **DO NOT** store the delegation token in the database. It is ephemeral.
5. **DO NOT** return the webhook_secret or delegation_token in any response to the caller.
6. **DO NOT** allow callee to post results after delegation is already completed (409 DELEGATION_ALREADY_COMPLETE).
7. **DO NOT** skip the task_hash (SHA-256) — it is required for tamper detection in the audit log.
8. **DO NOT** allow unbounded timeouts. Cap at 120s (120000ms).

---

## 6. Verification Checklist

```bash
# Full delegation round-trip test:
# 1. Register two agents (caller + callee)
# 2. Create a policy allowing the delegation
# 3. POST /delegate from caller to callee
# 4. Verify callee webhook receives the payload
# 5. Callee POSTs to /delegations/{id}/complete
# 6. Verify delegation status is 'completed'
# 7. Verify audit log entries exist

# Test policy block:
# Change policy to block → POST /delegate → expect 403

# Test schema validation:
# Send task with missing required field → expect 422

# Test budget cap:
# Set budget_cap_usd lower than callee price → expect 402
```

---

## 7. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-DEL-001 | Flow | Full 13-step sync delegation completes | status=='completed', result present, usage present |
| T-DEL-002 | Flow | Policy block returns 403 with policy_id | status_code==403, POLICY_BLOCKED, policy_id in details |
| T-DEL-003 | Flow | Policy pause returns 202 with pending_approval | status=='pending_approval', poll_url set |
| T-DEL-004 | Flow | Budget exceeded returns 402 | status_code==402, BUDGET_EXCEEDED, remaining_budget_usd |
| T-DEL-005 | Flow | Schema validation failure returns 422 | status_code==422, SCHEMA_VALIDATION_FAILED |
| T-DEL-006 | Flow | Callee not found returns 404 | status_code==404, AGENT_NOT_FOUND |
| T-DEL-007 | Flow | Quarantined caller returns 403 | status_code==403, AGENT_QUARANTINED |
| T-DEL-008 | Webhook | Callee timeout → 408 | delegation.status=='timeout' |
| T-DEL-009 | Webhook | Callee 401 → 503 not retried | WEBHOOK_SIGNATURE_REJECTED |
| T-DEL-010 | Webhook | Callee 500 → single retry → success | delegation.status=='completed' |
| T-DEL-011 | JWT | Single-use token enforced on /complete | Second POST → ValueError |
| T-DEL-012 | JWT | Expired token rejected | Expired JWT → 401 |
| T-DEL-013 | Complete | Result validated against output_schema | Invalid result → 422 |
| T-DEL-014 | Complete | Already completed → 409 | DELEGATION_ALREADY_COMPLETE |
| T-DEL-015 | Status | GET /delegations/{id} returns correct status | All fields match |
| T-DEL-016 | Hash | task_hash is SHA-256 of canonical JSON | Verify hash matches |
| T-023 | E2E | Full round-trip: register → discover → delegate → complete → settle | All audit entries present, status completed, budget updated |

---

## Appendix A: Cumulative `DelegationService` Constructor (Final State)

The `DelegationService` is built incrementally across phases. After Phase 7 (Budget/Audit) and Phase 10 (Trust/Circuit Breakers), the final constructor looks like this. Use this as a reference — build incrementally per phase.

```python
class DelegationService:
    """Orchestrates the 13-step delegation flow."""

    def __init__(
        self,
        db: AsyncSession,
        policy_service: PolicyService,
        webhook_service: WebhookService,
        budget_service: BudgetService,       # Added in Phase 7
        audit_service: AuditService,         # Added in Phase 7
        trust_service: TrustService,         # Added in Phase 10
    ):
        self._db = db
        self._policy = policy_service
        self._webhook = webhook_service
        self._budget = budget_service
        self._audit = audit_service
        self._trust = trust_service
```

**Phase-by-phase constructor evolution:**

| Phase | Constructor Parameters |
|-------|----------------------|
| Phase 6 (initial) | `db`, `policy_service`, `webhook_service` |
| Phase 7 (budget/audit) | + `budget_service`, `audit_service` |
| Phase 10 (trust) | + `trust_service` |

**Integration points within `DelegationService.initiate()`:**

| Step | Service Call | Phase |
|------|-------------|-------|
| Step 3 (policy check) | `self._policy.evaluate(context)` | 6 |
| Step 4 (budget check) | `self._budget.check_and_reserve(caller_agent_id, callee.price_per_call_usd)` | 7 |
| Step 8 (webhook delivery) | `self._webhook.deliver_and_await(callee, payload)` | 6 |
| Step 12 (record spend) | `self._budget.record_spend(caller_agent_id, callee.price_per_call_usd, delegation.id)` | 7 |
| Step 12 (audit log) | `self._audit.log(...)` | 7 |
| Step 12 (trust update) | `self._trust.update_after_delegation(callee, delegation)` | 10 |

**Factory / dependency injection in the router:**

```python
# api/routers/delegations.py — inside the route handler

async def initiate_delegation(
    request: Request,
    body: DelegateRequest,
    org: Organization = Depends(get_authenticated_org),
    db: AsyncSession = Depends(get_db),
):
    from services.policy_service import PolicyService
    from services.webhook_service import WebhookService
    from services.budget_service import BudgetService
    from services.audit_service import AuditService
    from services.trust_service import TrustService
    from api.dependencies import get_redis

    redis = await get_redis()
    service = DelegationService(
        db=db,
        policy_service=PolicyService(db),
        webhook_service=WebhookService(db),
        budget_service=BudgetService(db, redis),
        audit_service=AuditService(db),
        trust_service=TrustService(db, redis),
    )
    # ...
```
