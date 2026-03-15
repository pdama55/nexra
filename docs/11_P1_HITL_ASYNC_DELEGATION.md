# Phase 11 — Human-in-the-Loop Gates & Async Delegation (P1)

> **TDD Sections**: §15 (Human-in-the-Loop Gate), §12.2 (Async Webhook Delivery — Celery Worker), §8 (Delegation Flow — async path)
>
> **Depends On**: Phase 10 (Circuit Breakers & Trust complete). MVP fully deployed.

---

## 1. Prerequisites

- [ ] MVP fully deployed and functional (Phases 1–9)
- [ ] Phase 10 complete (TrustService full impl, CircuitBreakerService, AnomalyService)
- [ ] Delegation model has `status` supporting `pending_approval` value
- [ ] Delegation model has `callback_url` column
- [ ] Organization model has `approval_url` column (for HiTL webhook notifications)
- [ ] Celery app skeleton exists from Phase 8 (`workers/celery_app.py`)
- [ ] AuditService supports `hil_triggered`, `hil_approved`, `hil_expired` event types (defined in TDD §13.1)
- [ ] PolicyEngine returns `decision='pause'` when `estimated_cost > hil_threshold_usd` (T-004 from Phase 5)
- [ ] Redis available for HiTL approval token storage

---

## 2. Objective

This phase delivers two interconnected features:

1. **Human-in-the-Loop (HiTL) Gates**: When a policy evaluation returns `decision='pause'` (because `estimated_cost > hil_threshold_usd`), the delegation is held in `pending_approval` status. An approval notification is sent to the org's `approval_url`. An admin must explicitly approve or reject. Unapproved delegations expire after a configurable TTL (default 24 hours).

2. **Async Delegation via Celery**: Replace the MVP's synchronous HTTPX webhook delivery with a Celery-based async worker that supports exponential backoff retries (3 attempts), dead letter queuing, and `callback_url` support for long-running tasks.

---

## 3. Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HiTL notification delivery | Webhook POST to org's `approval_url` | TDD §15.1. Email notification is out of scope for P1 — webhook-only. |
| Approval token | Redis key with TTL = `hil_approval_ttl_hours` | Prevents stale approvals. Auto-expires. |
| Approval auth | Org API key required on `/approve` and `/reject` endpoints | Only org admins can approve. Agent-level keys cannot approve. |
| Async webhook delivery | Celery task with Redis broker, 3 retries, exponential backoff | TDD §12.2. Replaces MVP's direct HTTPX call for production reliability. |
| Dead letter queue | Redis list `nexra:dlq:webhooks` | Failed webhooks after 3 retries are stored for manual inspection. |
| Callback delivery | Separate Celery task fires POST to `callback_url` after delegation completes | TDD §8 step 12. Enables long-running delegations. |
| HiTL expiry check | Celery beat task every 5 minutes | Scans for expired `pending_approval` delegations. |
| Sync vs async mode | `callback_url=null` → sync (existing), `callback_url` set → async (new) | Backward compatible. Sync mode unchanged from Phase 6. |

---

## 4. File-by-File Implementation Guide

### 4.1 `services/hitl_service.py` (New File)

**Path**: `nexra/services/hitl_service.py`

This service manages the full HiTL lifecycle: triggering approval requests, processing approvals/rejections, and expiring stale requests.

```python
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import redis.asyncio as aioredis

from models.delegation import Delegation
from models.organization import Organization
from models.agent import Agent
from services.audit_service import AuditService
from core.config import get_settings
from core.errors import NexraError

logger = logging.getLogger("nexra.services.hitl")


class HiTLService:
    """Human-in-the-Loop gate management.

    Lifecycle:
    1. Policy returns decision='pause' → trigger_approval_request()
    2. Admin calls POST /delegations/{id}/approve → approve()
    3. Admin calls POST /delegations/{id}/reject → reject()
    4. Celery beat checks for expired approvals → expire_stale()
    """

    APPROVAL_KEY_PREFIX = "hitl:approval:"

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.audit = AuditService(db)
        self.settings = get_settings()

    async def trigger_approval_request(
        self,
        delegation: Delegation,
        caller_agent: Agent,
        callee_agent: Agent,
        org: Organization,
        estimated_cost_usd: float,
        hil_threshold_usd: float,
    ) -> dict:
        """Create a pending approval and notify the org.

        Steps:
        1. Set delegation status to 'pending_approval'
        2. Generate approval token and store in Redis with TTL
        3. Compute approval deadline
        4. Send webhook notification to org.approval_url
        5. Write audit entry 'hil_triggered'
        6. Return approval metadata for 202 response

        Returns:
            dict with delegation_id, approval_deadline, status
        """
        settings = self.settings
        ttl_hours = settings.hil_approval_ttl_hours
        approval_deadline = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        # Step 1: Update delegation status
        delegation.status = "pending_approval"
        await self.db.flush()

        # Step 2: Store approval token in Redis
        approval_token = str(uuid.uuid4())
        redis_key = f"{self.APPROVAL_KEY_PREFIX}{delegation.id}"
        await self.redis.setex(
            redis_key,
            int(ttl_hours * 3600),
            approval_token,
        )

        # Step 3: Build notification payload (TDD §15.2)
        notification_payload = {
            "event": "hil_approval_required",
            "delegation_id": str(delegation.id),
            "caller_agent": {
                "agent_id": caller_agent.agent_id,
                "name": caller_agent.name,
            },
            "callee_agent": {
                "agent_id": callee_agent.agent_id,
                "name": callee_agent.name,
            },
            "estimated_cost_usd": estimated_cost_usd,
            "hil_threshold_usd": hil_threshold_usd,
            "task_summary": {
                "type": delegation.task.get("type", "unknown"),
                "input_keys": list(delegation.task.get("input", {}).keys())
                if isinstance(delegation.task.get("input"), dict)
                else [],
            },
            "context_scope": delegation.context_scope or [],
            "approve_url": (
                f"{settings.api_base_url}/delegations/{delegation.id}/approve"
            ),
            "reject_url": (
                f"{settings.api_base_url}/delegations/{delegation.id}/reject"
            ),
            "approval_deadline": approval_deadline.isoformat(),
        }

        # Step 4: Send webhook notification to org's approval_url
        if org.approval_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        org.approval_url,
                        json=notification_payload,
                    )
                    if not resp.is_success:
                        logger.warning(
                            f"HiTL notification to {org.approval_url} returned "
                            f"{resp.status_code} for delegation {delegation.id}"
                        )
            except httpx.RequestError as e:
                logger.error(
                    f"Failed to send HiTL notification for delegation "
                    f"{delegation.id}: {e}"
                )
        else:
            logger.warning(
                f"Org {org.id} has no approval_url configured. "
                f"HiTL delegation {delegation.id} requires manual polling."
            )

        # Step 5: Audit entry
        await self.audit.append(
            org_id=str(delegation.caller_org_id),
            event_type="hil_triggered",
            actor_agent_id=caller_agent.agent_id,
            target_agent_id=callee_agent.agent_id,
            delegation_id=str(delegation.id),
            details={
                "hil_threshold_usd": hil_threshold_usd,
                "estimated_cost_usd": estimated_cost_usd,
                "approval_deadline": approval_deadline.isoformat(),
            },
        )

        await self.db.commit()

        return {
            "delegation_id": str(delegation.id),
            "status": "pending_approval",
            "approval_deadline": approval_deadline.isoformat(),
        }

    async def approve(
        self,
        delegation_id: str,
        org_id: str,
        approved_by: str | None = None,
    ) -> Delegation:
        """Approve a HiTL-gated delegation.

        Steps:
        1. Verify delegation exists and belongs to org
        2. Verify delegation is in 'pending_approval' status
        3. Verify Redis approval token has not expired
        4. Update delegation status to 'pending' (ready for execution)
        5. Delete Redis approval token
        6. Write audit entry 'hil_approved'
        7. Return updated delegation

        Raises:
            NexraError(404) if delegation not found
            NexraError(409) if delegation not in pending_approval status
            NexraError(410) if approval window has expired
        """
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        delegation = result.scalar_one_or_none()

        if not delegation:
            raise NexraError(404, "DELEGATION_NOT_FOUND", "Delegation not found")

        if delegation.status != "pending_approval":
            raise NexraError(
                409,
                "INVALID_DELEGATION_STATUS",
                f"Delegation is '{delegation.status}', not 'pending_approval'",
            )

        # Check Redis for approval token (verifies not expired)
        redis_key = f"{self.APPROVAL_KEY_PREFIX}{delegation_id}"
        token = await self.redis.get(redis_key)
        if not token:
            # Token expired — mark delegation as failed
            delegation.status = "failed"
            await self.audit.append(
                org_id=org_id,
                event_type="hil_expired",
                actor_agent_id=None,
                target_agent_id=None,
                delegation_id=delegation_id,
                details={"reason": "Approval window expired before approval received"},
            )
            await self.db.commit()
            raise NexraError(
                410,
                "HIL_APPROVAL_EXPIRED",
                "Approval window has expired. Delegation cancelled.",
            )

        # Approve: set status to 'pending' so delegation flow can resume
        delegation.status = "pending"
        await self.redis.delete(redis_key)

        await self.audit.append(
            org_id=org_id,
            event_type="hil_approved",
            actor_agent_id=None,
            target_agent_id=delegation.callee_agent_id,
            delegation_id=delegation_id,
            details={
                "approved_by": approved_by or "org_admin",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "original_trigger": "hil_threshold_exceeded",
            },
        )

        await self.db.commit()
        return delegation

    async def reject(
        self,
        delegation_id: str,
        org_id: str,
        reason: str = "Rejected by admin",
    ) -> Delegation:
        """Reject a HiTL-gated delegation.

        Steps:
        1. Verify delegation exists and belongs to org
        2. Verify delegation is in 'pending_approval' status
        3. Update delegation status to 'blocked'
        4. Delete Redis approval token
        5. Write audit entry 'delegation_blocked'
        6. Return updated delegation

        Raises:
            NexraError(404) if delegation not found
            NexraError(409) if delegation not in pending_approval status
        """
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        delegation = result.scalar_one_or_none()

        if not delegation:
            raise NexraError(404, "DELEGATION_NOT_FOUND", "Delegation not found")

        if delegation.status != "pending_approval":
            raise NexraError(
                409,
                "INVALID_DELEGATION_STATUS",
                f"Delegation is '{delegation.status}', not 'pending_approval'",
            )

        delegation.status = "blocked"

        redis_key = f"{self.APPROVAL_KEY_PREFIX}{delegation_id}"
        await self.redis.delete(redis_key)

        await self.audit.append(
            org_id=org_id,
            event_type="delegation_blocked",
            actor_agent_id=None,
            target_agent_id=delegation.callee_agent_id,
            delegation_id=delegation_id,
            details={
                "reason": reason,
                "trigger": "hil_rejected",
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        await self.db.commit()
        return delegation

    async def expire_stale(self) -> int:
        """Expire all pending_approval delegations whose Redis tokens have expired.

        Called by Celery beat task every 5 minutes.

        Returns:
            Number of delegations expired.
        """
        result = await self.db.execute(
            select(Delegation).where(Delegation.status == "pending_approval")
        )
        pending = result.scalars().all()
        expired_count = 0

        for delegation in pending:
            redis_key = f"{self.APPROVAL_KEY_PREFIX}{delegation.id}"
            token = await self.redis.get(redis_key)

            if token is None:
                delegation.status = "failed"
                await self.audit.append(
                    org_id=str(delegation.caller_org_id),
                    event_type="hil_expired",
                    actor_agent_id=None,
                    target_agent_id=delegation.callee_agent_id,
                    delegation_id=str(delegation.id),
                    details={
                        "reason": "Approval window expired without response",
                    },
                )
                expired_count += 1

        if expired_count > 0:
            await self.db.commit()
            logger.info(f"Expired {expired_count} stale HiTL delegations")

        return expired_count
```

---

### 4.2 `workers/hitl_worker.py` (New File)

**Path**: `nexra/workers/hitl_worker.py`

Celery beat task that checks for expired HiTL approvals every 5 minutes.

```python
import asyncio
import logging

from workers.celery_app import celery_app
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from core.config import get_settings

logger = logging.getLogger("nexra.workers.hitl")


@celery_app.task(bind=True, name="workers.hitl_worker.expire_stale_approvals")
def expire_stale_approvals(self):
    """Celery beat task: expire pending_approval delegations past their TTL.

    Runs every 5 minutes. Scans for delegations in 'pending_approval' status
    whose Redis approval token has expired, marks them as 'failed', and writes
    'hil_expired' audit entries.
    """
    asyncio.run(_expire())


async def _expire():
    import redis.asyncio as aioredis
    from services.hitl_service import HiTLService

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis_client = aioredis.from_url(settings.redis_url)

    try:
        async with session_factory() as session:
            service = HiTLService(session, redis_client)
            expired = await service.expire_stale()
            logger.info(f"HiTL expiry check complete: {expired} delegations expired")
    finally:
        await redis_client.aclose()
        await engine.dispose()
```

---

### 4.3 `workers/webhook_worker.py` (New File — replaces MVP sync delivery for production)

**Path**: `nexra/workers/webhook_worker.py`

Celery task for async webhook delivery with exponential backoff and dead letter queue.

```python
import logging
import time
import json

import httpx
from workers.celery_app import celery_app
from core.config import get_settings

logger = logging.getLogger("nexra.workers.webhook")

DLQ_KEY = "nexra:dlq:webhooks"


@celery_app.task(
    bind=True,
    name="workers.webhook_worker.deliver_webhook",
    max_retries=3,
    default_retry_delay=2,
    acks_late=True,
    queue="webhooks",
)
def deliver_webhook(
    self,
    webhook_url: str,
    payload: dict,
    signature: str,
    delegation_id: str,
    timeout_ms: int,
):
    """Deliver a webhook to a callee agent with retry and dead letter queue.

    Retry policy (TDD §12.2):
        Attempt 1: immediate
        Attempt 2: 2s delay (2^1)
        Attempt 3: 4s delay (2^2)
        After 3 failures: mark delegation 'failed', write to dead letter queue

    Args:
        webhook_url: Callee's registered webhook endpoint (HTTPS)
        payload: Full delegation payload including task, delegation_token, context
        signature: HMAC-SHA256 signature for X-Nexra-Signature header
        delegation_id: UUID string for tracking
        timeout_ms: Webhook timeout in milliseconds
    """
    effective_timeout = min(timeout_ms / 1000, 29.9)

    headers = {
        "Content-Type": "application/json",
        "X-Nexra-Signature": signature,
        "X-Delegation-ID": delegation_id,
        "X-Nexra-Timestamp": str(int(time.time())),
    }

    try:
        with httpx.Client(timeout=effective_timeout) as client:
            resp = client.post(webhook_url, json=payload, headers=headers)

            if resp.status_code in (401, 403):
                # Callee rejected HMAC — do NOT retry (TDD §12.1)
                logger.error(
                    f"Webhook HMAC rejected by callee for delegation "
                    f"{delegation_id}: {resp.status_code}"
                )
                _mark_delegation_failed(
                    delegation_id,
                    f"Callee returned {resp.status_code} — HMAC mismatch, not retried",
                )
                return

            if resp.status_code >= 400:
                raise ValueError(
                    f"Webhook returned {resp.status_code}: {resp.text[:500]}"
                )

            # Webhook delivered — process callee response
            _process_webhook_response(delegation_id, resp.json())

    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.error(
                f"Webhook delivery failed after {self.max_retries + 1} attempts "
                f"for delegation {delegation_id}: {exc}"
            )
            _write_to_dlq(delegation_id, webhook_url, str(exc))
            _mark_delegation_failed(delegation_id, str(exc))
        else:
            countdown = 2 ** (self.request.retries + 1)
            logger.warning(
                f"Webhook delivery attempt {self.request.retries + 1} failed "
                f"for delegation {delegation_id}, retrying in {countdown}s: {exc}"
            )
            raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    bind=True,
    name="workers.webhook_worker.deliver_callback",
    max_retries=3,
    default_retry_delay=2,
    queue="webhooks",
)
def deliver_callback(
    self,
    callback_url: str,
    delegation_id: str,
    result_payload: dict,
):
    """Deliver delegation result to caller's callback_url for async delegations.

    Same retry policy as webhook delivery.

    Args:
        callback_url: Caller's registered callback endpoint
        delegation_id: UUID string for tracking
        result_payload: Full delegation result including status, result, usage
    """
    headers = {
        "Content-Type": "application/json",
        "X-Delegation-ID": delegation_id,
        "X-Nexra-Timestamp": str(int(time.time())),
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(callback_url, json=result_payload, headers=headers)
            if resp.status_code >= 400:
                raise ValueError(f"Callback returned {resp.status_code}")
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.error(
                f"Callback delivery failed after {self.max_retries + 1} attempts "
                f"for delegation {delegation_id}: {exc}"
            )
            _write_to_dlq(delegation_id, callback_url, str(exc))
        else:
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))


def _mark_delegation_failed(delegation_id: str, reason: str) -> None:
    """Fire a Celery task to update delegation status to 'failed'.

    Uses a separate task to avoid circular imports and ensure the DB
    update happens even if the current task context is lost.
    """
    mark_delegation_status.delay(delegation_id, "failed", reason)


@celery_app.task(name="workers.webhook_worker.mark_delegation_status", queue="webhooks")
def mark_delegation_status(delegation_id: str, status: str, reason: str) -> None:
    """Update delegation status in the database.

    Runs synchronously inside Celery worker using asyncio.run().
    """
    import asyncio
    asyncio.run(_update_delegation_status(delegation_id, status, reason))


async def _update_delegation_status(
    delegation_id: str, status: str, reason: str
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import update as sql_update
    from models.delegation import Delegation
    from services.audit_service import AuditService

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await session.execute(
            sql_update(Delegation)
            .where(Delegation.id == delegation_id)
            .values(status=status)
        )

        audit = AuditService(session)
        await audit.append(
            org_id=None,
            event_type="delegation_failed",
            actor_agent_id=None,
            target_agent_id=None,
            delegation_id=delegation_id,
            details={"reason": reason, "trigger": "webhook_delivery_exhausted"},
        )
        await session.commit()

    await engine.dispose()


def _process_webhook_response(delegation_id: str, response_body: dict) -> None:
    """Process a successful webhook response from callee.

    If the callee returns a result inline (sync mode), this triggers
    the settlement flow. If the callee will POST to /complete later,
    this is a no-op.
    """
    if response_body.get("result") is not None:
        complete_delegation_from_webhook.delay(delegation_id, response_body)


@celery_app.task(
    name="workers.webhook_worker.complete_delegation_from_webhook",
    queue="webhooks",
)
def complete_delegation_from_webhook(delegation_id: str, response_body: dict) -> None:
    """Process inline webhook response and complete the delegation."""
    import asyncio
    asyncio.run(_complete_from_webhook(delegation_id, response_body))


async def _complete_from_webhook(delegation_id: str, response_body: dict) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from services.delegation_service import DelegationService

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = DelegationService(session)
        await service.complete_delegation(delegation_id, response_body)

    await engine.dispose()


def _write_to_dlq(delegation_id: str, url: str, error: str) -> None:
    """Write failed webhook delivery to Redis dead letter queue."""
    import redis as sync_redis

    settings = get_settings()
    r = sync_redis.from_url(settings.redis_url)
    entry = json.dumps({
        "delegation_id": delegation_id,
        "url": url,
        "error": error,
        "timestamp": int(time.time()),
    })
    r.lpush(DLQ_KEY, entry)
    r.ltrim(DLQ_KEY, 0, 9999)  # Cap DLQ at 10,000 entries
    r.close()
```

---

### 4.4 Update `workers/celery_app.py` — Add Beat Schedule

**Path**: `nexra/workers/celery_app.py`

Add the HiTL expiry task to the existing beat schedule.

```python
# Add to existing beat_schedule dict:

celery_app.conf.beat_schedule.update({
    "hitl-expiry-check": {
        "task": "workers.hitl_worker.expire_stale_approvals",
        "schedule": 300.0,  # Every 5 minutes
    },
})

# Also register webhook and callback queues
celery_app.conf.task_routes = {
    "workers.webhook_worker.*": {"queue": "webhooks"},
    "workers.billing_worker.*": {"queue": "billing"},
    "workers.anomaly_worker.*": {"queue": "anomaly"},
    "workers.hitl_worker.*": {"queue": "default"},
}
```

---

### 4.5 `api/routers/delegations.py` — Add `/approve` and `/reject` Endpoints

**Path**: `nexra/api/routers/delegations.py`

Add these endpoints to the existing delegations router.

```python
from pydantic import BaseModel, Field


class ApproveRequest(BaseModel):
    approved_by: str | None = Field(
        None, description="Identifier of the admin approving (optional)"
    )


class RejectRequest(BaseModel):
    reason: str = Field(
        "Rejected by admin",
        description="Reason for rejection",
    )


class HiTLResponse(BaseModel):
    delegation_id: str
    status: str
    message: str


@router.post(
    "/delegations/{delegation_id}/approve",
    response_model=HiTLResponse,
    status_code=200,
    summary="Approve a HiTL-gated delegation",
    description=(
        "Approve a delegation that was paused for human review. "
        "Only callable by org admin (org-level API key). "
        "After approval, the delegation proceeds immediately: "
        "JWT is issued, webhook is delivered to callee."
    ),
)
async def approve_delegation(
    delegation_id: str,
    body: ApproveRequest,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Approve a pending_approval delegation.

    Flow after approval:
    1. HiTLService.approve() updates status to 'pending'
    2. Resume delegation flow: issue JWT, build webhook payload, deliver
    3. If async mode (callback_url set): queue webhook via Celery
    4. If sync mode: deliver webhook synchronously and return result
    """
    hitl_service = HiTLService(db, redis)
    delegation = await hitl_service.approve(
        delegation_id=delegation_id,
        org_id=str(org.id),
        approved_by=body.approved_by,
    )

    # Resume the delegation flow
    delegation_service = DelegationService(db, redis)
    result = await delegation_service.resume_after_approval(delegation)

    if delegation.callback_url:
        # Async mode: queue webhook delivery via Celery
        return HiTLResponse(
            delegation_id=str(delegation.id),
            status="in_flight",
            message="Delegation approved and queued for execution",
        )

    # Sync mode: return result directly
    return result


@router.post(
    "/delegations/{delegation_id}/reject",
    response_model=HiTLResponse,
    status_code=200,
    summary="Reject a HiTL-gated delegation",
    description=(
        "Reject a delegation that was paused for human review. "
        "Delegation status becomes 'blocked'. Audit entry written."
    ),
)
async def reject_delegation(
    delegation_id: str,
    body: RejectRequest,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    hitl_service = HiTLService(db, redis)
    delegation = await hitl_service.reject(
        delegation_id=delegation_id,
        org_id=str(org.id),
        reason=body.reason,
    )

    return HiTLResponse(
        delegation_id=str(delegation.id),
        status="blocked",
        message=f"Delegation rejected: {body.reason}",
    )
```

---

### 4.6 Update `services/delegation_service.py` — Add `resume_after_approval()` and Async Mode

**Path**: `nexra/services/delegation_service.py`

Add these methods to the existing DelegationService class.

```python
async def resume_after_approval(self, delegation: Delegation) -> dict | None:
    """Resume a delegation after HiTL approval.

    Picks up from step 10 of the 13-step flow:
    10. Issue delegation JWT
    11. Build and sign webhook payload
    12. Deliver webhook (sync or async based on callback_url)
    13. Return result to caller (or queue callback)

    Args:
        delegation: Delegation record with status='pending'

    Returns:
        Result dict if sync mode, None if async mode
    """
    from core.jwt import issue_delegation_token
    from core.crypto import sign_webhook_payload
    from services.webhook_service import WebhookService

    # Fetch callee agent for webhook details
    callee = await self._get_agent(
        delegation.callee_agent_id,
        delegation.callee_org_id or delegation.caller_org_id,
    )
    if not callee:
        raise NexraError(404, "AGENT_NOT_FOUND", "Callee agent no longer exists")

    # Fetch org for JWT secret
    org = await self._get_org(delegation.caller_org_id)

    # Step 10: Issue delegation JWT
    token = issue_delegation_token(
        org_jwt_secret=org.jwt_secret_enc,
        delegation_id=str(delegation.id),
        callee_agent_id=callee.agent_id,
        context_scope=delegation.context_scope or [],
    )

    # Step 11: Build webhook payload
    webhook_payload = {
        "delegation_id": str(delegation.id),
        "delegation_token": token,
        "task": delegation.task,
        "context_scope": delegation.context_scope or [],
        "timeout_ms": delegation.timeout_ms if hasattr(delegation, 'timeout_ms') else 30000,
    }
    signature = sign_webhook_payload(webhook_payload, callee.webhook_secret)

    # Update status to in_flight
    delegation.status = "in_flight"
    await self.db.flush()

    # Step 12: Deliver webhook
    if delegation.callback_url:
        # Async mode: queue via Celery
        from workers.webhook_worker import deliver_webhook
        deliver_webhook.delay(
            webhook_url=callee.webhook_url,
            payload=webhook_payload,
            signature=f"sha256={signature}",
            delegation_id=str(delegation.id),
            timeout_ms=webhook_payload["timeout_ms"],
        )
        await self.db.commit()
        return None
    else:
        # Sync mode: deliver directly
        webhook_service = WebhookService()
        result = await webhook_service.deliver_and_await(
            webhook_url=callee.webhook_url,
            payload=webhook_payload,
            signature=f"sha256={signature}",
            delegation_id=str(delegation.id),
            timeout_ms=webhook_payload["timeout_ms"],
        )
        # Settle
        await self._settle_delegation(delegation, result, callee)
        await self.db.commit()
        return self._build_response(delegation, result)


async def initiate_async_delegation(self, delegation: Delegation) -> dict:
    """Initiate an async delegation via Celery webhook worker.

    Called when callback_url is set on the delegation request.
    Instead of delivering the webhook synchronously, queues it
    via Celery and returns 202 Accepted immediately.

    The caller will receive the result via their callback_url
    when the callee completes the task.

    Returns:
        dict with delegation_id, status='in_flight'
    """
    from core.jwt import issue_delegation_token
    from core.crypto import sign_webhook_payload
    from workers.webhook_worker import deliver_webhook

    callee = await self._get_agent(
        delegation.callee_agent_id,
        delegation.callee_org_id or delegation.caller_org_id,
    )
    org = await self._get_org(delegation.caller_org_id)

    token = issue_delegation_token(
        org_jwt_secret=org.jwt_secret_enc,
        delegation_id=str(delegation.id),
        callee_agent_id=callee.agent_id,
        context_scope=delegation.context_scope or [],
    )

    webhook_payload = {
        "delegation_id": str(delegation.id),
        "delegation_token": token,
        "task": delegation.task,
        "context_scope": delegation.context_scope or [],
        "timeout_ms": 30000,
    }
    signature = sign_webhook_payload(webhook_payload, callee.webhook_secret)

    delegation.status = "in_flight"
    await self.db.commit()

    deliver_webhook.delay(
        webhook_url=callee.webhook_url,
        payload=webhook_payload,
        signature=f"sha256={signature}",
        delegation_id=str(delegation.id),
        timeout_ms=30000,
    )

    return {
        "delegation_id": str(delegation.id),
        "status": "in_flight",
        "message": "Delegation queued for async execution",
        "callback_url": delegation.callback_url,
    }
```

---

### 4.7 Update `core/config.py` — Add `api_base_url` Setting

**Path**: `nexra/core/config.py`

Add to the existing Settings class:

```python
api_base_url: str = "https://api.usenexra.com/v1"
```

---

## 5. Integration Points

### 5.1 Delegation Flow Integration (Update `POST /delegate` handler)

The existing delegation flow in Phase 6 must be updated at two points:

**Point A — After policy evaluation returns `decision='pause'`** (Step 9 in 13-step flow):

```python
# In delegation_service.py, inside initiate_delegation():
if policy_decision.decision == "pause":
    hitl_service = HiTLService(self.db, self.redis)
    return await hitl_service.trigger_approval_request(
        delegation=delegation,
        caller_agent=caller_agent,
        callee_agent=callee_agent,
        org=org,
        estimated_cost_usd=estimated_cost,
        hil_threshold_usd=policy_decision.hil_threshold_usd,
    )
```

**Point B — After all checks pass, if `callback_url` is set** (Step 12):

```python
# In delegation_service.py, inside initiate_delegation():
if delegation.callback_url:
    return await self.initiate_async_delegation(delegation)
# else: existing sync delivery code
```

### 5.2 Delegation Completion Callback

When a delegation completes (via `/delegations/{id}/complete`) and the delegation has a `callback_url`, fire the callback:

```python
# In delegation_service.py, inside complete_delegation():
if delegation.callback_url:
    from workers.webhook_worker import deliver_callback
    deliver_callback.delay(
        callback_url=delegation.callback_url,
        delegation_id=str(delegation.id),
        result_payload={
            "delegation_id": str(delegation.id),
            "status": "completed",
            "result": result,
            "usage": {
                "cost_usd": float(delegation.actual_cost_usd or 0),
                "latency_ms": delegation.latency_ms,
                "llm_tokens": delegation.llm_tokens,
            },
        },
    )
```

---

## 6. Guardrails

1. **DO NOT** allow agent-level API keys to approve or reject HiTL delegations. Only org-level admin keys (no `X-Agent-ID` header) can call `/approve` and `/reject`.
2. **DO NOT** retry webhook delivery on 401/403 responses. These indicate HMAC mismatch — retrying will not fix it. Mark delegation as failed immediately.
3. **DO NOT** allow approval of a delegation after the Redis TTL has expired. Even if the delegation record still says `pending_approval`, the expired Redis key means the approval window is closed.
4. **DO NOT** store the HiTL approval deadline in the database. The Redis TTL is the single source of truth for expiry. This prevents clock drift issues between DB and application.
5. **DO NOT** deliver webhooks synchronously in production when Celery workers are available. The sync path (`WebhookService.deliver_and_await`) is the MVP fallback only.
6. **DO NOT** allow the dead letter queue to grow unbounded. Cap at 10,000 entries with `LTRIM`.
7. **DO NOT** process callback delivery in the same Celery task as webhook delivery. Use a separate task (`deliver_callback`) to isolate failures.
8. **DO NOT** skip the HMAC signature on callback deliveries. Callers must be able to verify callbacks came from Nexra. (Note: callback HMAC signing is a v2 enhancement — for P1, callbacks are unsigned but delivered over HTTPS only.)

---

## 7. Verification Checklist

After implementing all files, verify each item:

- [ ] `HiTLService` instantiates without error with valid `AsyncSession` and `Redis`
- [ ] `trigger_approval_request()` sets delegation status to `pending_approval`
- [ ] `trigger_approval_request()` stores approval token in Redis with correct TTL
- [ ] `trigger_approval_request()` sends webhook to `org.approval_url` with TDD §15.2 payload shape
- [ ] `trigger_approval_request()` writes `hil_triggered` audit entry
- [ ] `approve()` changes delegation status from `pending_approval` to `pending`
- [ ] `approve()` deletes Redis approval token
- [ ] `approve()` writes `hil_approved` audit entry
- [ ] `approve()` raises `NexraError(404)` for nonexistent delegation
- [ ] `approve()` raises `NexraError(409)` for delegation not in `pending_approval`
- [ ] `approve()` raises `NexraError(410)` when Redis token has expired
- [ ] `reject()` changes delegation status to `blocked`
- [ ] `reject()` writes `delegation_blocked` audit entry with `trigger: hil_rejected`
- [ ] `expire_stale()` finds and expires delegations whose Redis tokens are gone
- [ ] `expire_stale()` writes `hil_expired` audit entries for each expired delegation
- [ ] Celery beat schedule includes `hitl-expiry-check` at 300s interval
- [ ] `deliver_webhook` task retries with exponential backoff (2s, 4s)
- [ ] `deliver_webhook` task does NOT retry on 401/403
- [ ] `deliver_webhook` task writes to DLQ after 3 failures
- [ ] `deliver_webhook` task marks delegation as failed after exhausting retries
- [ ] `deliver_callback` task delivers result to caller's `callback_url`
- [ ] `POST /delegations/{id}/approve` endpoint returns 200 with correct response shape
- [ ] `POST /delegations/{id}/reject` endpoint returns 200 with correct response shape
- [ ] `resume_after_approval()` picks up delegation flow at step 10 (JWT issuance)
- [ ] Async delegation with `callback_url` returns 202 immediately and delivers result via callback

---

## 8. Test Cases

| Test ID | Category | Description | Assertion |
|---------|----------|-------------|-----------|
| T-HITL-001 | HiTL | Policy returns `pause` → delegation status becomes `pending_approval` | `delegation.status == 'pending_approval'` |
| T-HITL-002 | HiTL | Approval notification sent to `org.approval_url` | Mock HTTPX captures POST to approval_url with §15.2 payload |
| T-HITL-003 | HiTL | `POST /approve` on valid pending delegation → status becomes `pending` | `delegation.status == 'pending'`, audit entry `hil_approved` exists |
| T-HITL-004 | HiTL | `POST /approve` resumes delegation flow → webhook delivered | Callee webhook receives payload, delegation completes |
| T-HITL-005 | HiTL | `POST /reject` → status becomes `blocked` | `delegation.status == 'blocked'`, audit entry `delegation_blocked` with `trigger: hil_rejected` |
| T-HITL-006 | HiTL | Approval after Redis TTL expires → 410 error | `NexraError(410, 'HIL_APPROVAL_EXPIRED')` raised |
| T-HITL-007 | HiTL | `POST /approve` on non-pending delegation → 409 | `NexraError(409, 'INVALID_DELEGATION_STATUS')` |
| T-HITL-008 | HiTL | `POST /approve` on nonexistent delegation → 404 | `NexraError(404, 'DELEGATION_NOT_FOUND')` |
| T-HITL-009 | HiTL | `expire_stale()` expires delegations with no Redis token | Delegation status → `failed`, `hil_expired` audit entry |
| T-HITL-010 | HiTL | `expire_stale()` does NOT expire delegations with valid Redis token | Delegation status remains `pending_approval` |
| T-HITL-011 | HiTL | Org without `approval_url` → delegation still paused, warning logged | `delegation.status == 'pending_approval'`, log contains warning |
| T-ASYNC-001 | Async | `callback_url` set → webhook queued via Celery, 202 returned | HTTP 202, Celery task enqueued |
| T-ASYNC-002 | Async | Webhook delivery succeeds → callback fired to `callback_url` | Mock captures POST to callback_url with result payload |
| T-ASYNC-003 | Async | Webhook delivery fails 3 times → DLQ entry written | Redis list `nexra:dlq:webhooks` contains entry |
| T-ASYNC-004 | Async | Webhook delivery fails 3 times → delegation status `failed` | `delegation.status == 'failed'` |
| T-ASYNC-005 | Async | Webhook 401/403 → no retry, immediate failure | Only 1 attempt made, delegation `failed` |
| T-ASYNC-006 | Async | Webhook 500 → retry with exponential backoff | 3 attempts with delays 2s, 4s |
| T-ASYNC-007 | Async | `callback_url=null` → sync mode unchanged from Phase 6 | Existing sync tests still pass |
| T-ASYNC-008 | Async | DLQ capped at 10,000 entries | After 10,001 writes, `LLEN` returns 10,000 |

---

## 9. Test Implementation Guide

### 9.1 Unit Tests — `tests/unit/test_hitl_service.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from services.hitl_service import HiTLService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=b"approval-token-123")
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def hitl_service(mock_db, mock_redis):
    return HiTLService(mock_db, mock_redis)


class TestTriggerApprovalRequest:
    """T-HITL-001, T-HITL-002, T-HITL-011"""

    async def test_sets_delegation_status_to_pending_approval(
        self, hitl_service, mock_delegation, mock_caller, mock_callee, mock_org
    ):
        # T-HITL-001
        result = await hitl_service.trigger_approval_request(
            delegation=mock_delegation,
            caller_agent=mock_caller,
            callee_agent=mock_callee,
            org=mock_org,
            estimated_cost_usd=1.50,
            hil_threshold_usd=1.00,
        )
        assert mock_delegation.status == "pending_approval"
        assert result["status"] == "pending_approval"

    async def test_stores_redis_token_with_ttl(
        self, hitl_service, mock_redis, mock_delegation, mock_caller, mock_callee, mock_org
    ):
        await hitl_service.trigger_approval_request(
            delegation=mock_delegation,
            caller_agent=mock_caller,
            callee_agent=mock_callee,
            org=mock_org,
            estimated_cost_usd=1.50,
            hil_threshold_usd=1.00,
        )
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][1] == 24 * 3600  # Default TTL


class TestApprove:
    """T-HITL-003, T-HITL-006, T-HITL-007, T-HITL-008"""

    async def test_approve_valid_delegation(self, hitl_service, mock_db, mock_redis):
        # T-HITL-003: Setup mock to return a pending_approval delegation
        pass  # Full implementation with mock setup

    async def test_approve_expired_token_returns_410(self, hitl_service, mock_redis):
        # T-HITL-006: Redis returns None for expired token
        mock_redis.get = AsyncMock(return_value=None)
        # Assert NexraError(410) raised

    async def test_approve_wrong_status_returns_409(self, hitl_service):
        # T-HITL-007: Delegation in 'completed' status
        pass

    async def test_approve_nonexistent_returns_404(self, hitl_service, mock_db):
        # T-HITL-008: No delegation found
        pass


class TestExpireStale:
    """T-HITL-009, T-HITL-010"""

    async def test_expires_delegations_without_redis_token(self, hitl_service):
        # T-HITL-009
        pass

    async def test_preserves_delegations_with_valid_token(self, hitl_service):
        # T-HITL-010
        pass
```

### 9.2 Unit Tests — `tests/unit/test_webhook_worker.py`

```python
import pytest
from unittest.mock import patch, MagicMock
from workers.webhook_worker import deliver_webhook, DLQ_KEY


class TestDeliverWebhook:
    """T-ASYNC-003 through T-ASYNC-006"""

    @patch("workers.webhook_worker.httpx.Client")
    def test_successful_delivery(self, mock_client_cls):
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.json.return_value = {"result": {"data": "test"}}
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        deliver_webhook(
            webhook_url="https://agent.example.com/webhook",
            payload={"task": {}},
            signature="sha256=abc123",
            delegation_id="del-123",
            timeout_ms=30000,
        )

    @patch("workers.webhook_worker.httpx.Client")
    def test_401_no_retry(self, mock_client_cls):
        # T-ASYNC-005: 401 should NOT trigger retry
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        # Should not raise self.retry()
        deliver_webhook(
            webhook_url="https://agent.example.com/webhook",
            payload={"task": {}},
            signature="sha256=abc123",
            delegation_id="del-123",
            timeout_ms=30000,
        )
```

---

## 10. Sequence Diagrams

### 10.1 HiTL Approval Flow

```
Caller                Nexra API           HiTLService          Redis           Org Admin
  │                      │                    │                   │                │
  │ POST /delegate       │                    │                   │                │
  │─────────────────────>│                    │                   │                │
  │                      │ policy='pause'     │                   │                │
  │                      │───────────────────>│                   │                │
  │                      │                    │ SETEX token (24h) │                │
  │                      │                    │──────────────────>│                │
  │                      │                    │ POST approval_url │                │
  │                      │                    │────────────────────────────────────>│
  │  202 pending_approval│                    │                   │                │
  │<─────────────────────│                    │                   │                │
  │                      │                    │                   │                │
  │                      │ POST /approve      │                   │                │
  │                      │<────────────────────────────────────────────────────────│
  │                      │───────────────────>│                   │                │
  │                      │                    │ GET token          │                │
  │                      │                    │──────────────────>│                │
  │                      │                    │ token exists ✓    │                │
  │                      │                    │<──────────────────│                │
  │                      │                    │ DEL token          │                │
  │                      │                    │──────────────────>│                │
  │                      │ resume delegation  │                   │                │
  │                      │ (steps 10-13)      │                   │                │
  │  200 result          │                    │                   │                │
  │<─────────────────────│                    │                   │                │
```

### 10.2 Async Delegation Flow

```
Caller              Nexra API         Celery Worker        Callee           Caller Callback
  │                    │                   │                  │                   │
  │ POST /delegate     │                   │                  │                   │
  │ (callback_url set) │                   │                  │                   │
  │───────────────────>│                   │                  │                   │
  │                    │ queue webhook     │                  │                   │
  │                    │──────────────────>│                  │                   │
  │ 202 in_flight      │                   │                  │                   │
  │<───────────────────│                   │                  │                   │
  │                    │                   │ POST webhook_url │                   │
  │                    │                   │─────────────────>│                   │
  │                    │                   │ 200 result       │                   │
  │                    │                   │<─────────────────│                   │
  │                    │                   │ settle delegation│                   │
  │                    │                   │ POST callback_url│                   │
  │                    │                   │──────────────────────────────────────>│
  │                    │                   │                  │                   │
```
