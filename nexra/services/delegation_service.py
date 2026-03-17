import logging
import time
from datetime import datetime, timezone

import jsonschema
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.delegations import (
    DelegateRequest,
    DelegationResponse,
    PolicyResultResponse,
    UsageResponse,
)
from core.config import get_settings
from core.crypto import decrypt_aes_gcm, sha256_json
from core.errors import (
    AGENT_NOT_FOUND,
    AGENT_QUARANTINED,
    BUDGET_EXCEEDED,
    DELEGATION_ALREADY_COMPLETE,
    DELEGATION_NOT_FOUND,
    INVALID_DELEGATION_TOKEN,
    INVALID_REQUEST,
    MAX_DEPTH_EXCEEDED,
    OUTPUT_SCHEMA_FAILED,
    POLICY_BLOCKED,
    SCHEMA_VALIDATION_FAILED,
    NexraError,
)
from core.jwt import issue_delegation_token, verify_delegation_token
from models.agent import Agent
from models.delegation import Delegation
from models.organization import Organization
from services.audit_service import AuditService
from services.billing_service import BillingService
from services.budget_service import BudgetService
from services.hitl_service import HiTLService
from services.marketplace_service import MarketplaceService
from services.policy_engine import DelegationContext, PolicyEngine
from services.trust_service import CircuitBreakerService, TrustService
from services.webhook_service import WebhookService

logger = logging.getLogger("nexra.services.delegation")


class DelegationService:
    """Orchestrates delegation lifecycle and settlement consistency."""

    def __init__(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        policy_engine: PolicyEngine,
        webhook_service: WebhookService,
        budget_service: BudgetService,
        audit_service: AuditService,
        trust_service: TrustService,
        billing_service: BillingService | None = None,
        hitl_service: HiTLService | None = None,
        circuit_breaker: CircuitBreakerService | None = None,
    ) -> None:
        self.db = db
        self.redis = redis_client
        self.policy_engine = policy_engine
        self.webhook_service = webhook_service
        self.budget_service = budget_service
        self.audit_service = audit_service
        self.trust_service = trust_service
        self.billing_service = billing_service or BillingService()
        self.hitl_service = hitl_service or HiTLService(db)
        self.circuit_breaker = circuit_breaker or CircuitBreakerService(redis_client)

    async def initiate(
        self,
        org: Organization,
        caller_agent: Agent,
        request: DelegateRequest,
    ) -> DelegationResponse:
        """Execute delegation lifecycle with deterministic budget accounting."""
        start_time = time.perf_counter()
        settings = get_settings()

        callee = await self._resolve_callee(
            str(org.id), request.callee_agent_id, request.include_cross_org
        )
        if not callee:
            raise NexraError(
                404,
                AGENT_NOT_FOUND,
                f"Callee agent '{request.callee_agent_id}' not found",
            )

        if caller_agent.status == "quarantined":
            raise NexraError(403, AGENT_QUARANTINED, "Caller agent is quarantined")
        if callee.status == "quarantined":
            raise NexraError(403, AGENT_QUARANTINED, "Callee agent is quarantined")

        if callee.input_schema and callee.input_schema.get("type"):
            try:
                task_input = request.task.get("input", request.task)
                jsonschema.validate(task_input, callee.input_schema)
            except jsonschema.ValidationError as exc:
                raise NexraError(
                    422,
                    SCHEMA_VALIDATION_FAILED,
                    f"Task payload validation failed: {exc.message}",
                )

        estimated_cost = float(callee.pricing.get("per_call_usd", 0))

        parent_id, depth = await self._derive_depth(
            str(org.id), request.parent_delegation_id
        )
        if depth > settings.max_delegation_depth_default:
            raise NexraError(
                400,
                MAX_DEPTH_EXCEEDED,
                (
                    f"Delegation depth {depth} exceeds "
                    f"limit {settings.max_delegation_depth_default}"
                ),
            )

        delegation = Delegation(
            caller_org_id=org.id,
            caller_agent_id=caller_agent.agent_id,
            callee_org_id=callee.org_id,
            callee_agent_id=callee.agent_id,
            task=request.task,
            task_hash=sha256_json(request.task),
            context_scope=request.context_scope,
            policy_id=None,
            policy_version=None,
            policy_decision=None,
            budget_cap_usd=request.budget_cap_usd,
            estimated_cost_usd=estimated_cost,
            callback_url=request.callback_url,
            workflow=(request.workflow or "unclassified").strip() or "unclassified",
            delegation_depth=depth,
            parent_delegation_id=parent_id,
            status="pending",
        )
        self.db.add(delegation)
        await self.db.flush()

        budget_check = await self.budget_service.check_and_reserve(
            str(org.id),
            caller_agent.agent_id,
            estimated_cost,
            request.budget_cap_usd,
            str(delegation.id),
        )
        if not budget_check.allowed:
            delegation.status = "blocked"
            delegation.completed_at = datetime.now(timezone.utc)
            delegation.actual_cost_usd = 0
            await self.db.commit()
            await self.audit_service.append(
                org_id=str(org.id),
                event_type="budget_exceeded",
                actor_agent_id=caller_agent.agent_id,
                target_agent_id=request.callee_agent_id,
                details={
                    "reason": budget_check.reason,
                    "remaining_budget_usd": budget_check.remaining_usd,
                    "estimated_cost_usd": estimated_cost,
                    "requested_budget_cap_usd": request.budget_cap_usd,
                },
                delegation_id=str(delegation.id),
            )
            raise NexraError(
                402,
                BUDGET_EXCEEDED,
                f"Budget exceeded: {budget_check.reason}",
                {"remaining_budget_usd": budget_check.remaining_usd},
            )

        ctx = DelegationContext(
            caller_agent_id=caller_agent.agent_id,
            caller_agent_type=caller_agent.capability_type,
            caller_org_id=str(org.id),
            caller_budget_remaining_usd=budget_check.remaining_usd,
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

        delegation.policy_id = decision.policy_id
        delegation.policy_version = decision.policy_version
        delegation.policy_decision = decision.decision

        await self.audit_service.append(
            org_id=str(org.id),
            event_type="policy_evaluated",
            actor_agent_id=caller_agent.agent_id,
            target_agent_id=callee.agent_id,
            details={
                "decision": decision.decision,
                "policy_decision": decision.decision,
                "policy_id": decision.policy_id,
                "policy_version": decision.policy_version,
                "reason": decision.reason,
            },
            delegation_id=str(delegation.id),
        )

        if decision.decision == "block":
            delegation.status = "blocked"
            delegation.completed_at = datetime.now(timezone.utc)
            delegation.actual_cost_usd = 0
            await self.db.commit()
            await self.budget_service.release(
                str(org.id),
                caller_agent.agent_id,
                str(delegation.id),
            )
            await self.audit_service.append(
                org_id=str(org.id),
                event_type="delegation_blocked",
                actor_agent_id=caller_agent.agent_id,
                target_agent_id=callee.agent_id,
                details={
                    "reason": decision.reason,
                    "policy_id": decision.policy_id,
                    "policy_version": decision.policy_version,
                    "policy_decision": decision.decision,
                },
                delegation_id=str(delegation.id),
            )
            raise NexraError(
                403,
                POLICY_BLOCKED,
                decision.reason,
                {
                    "policy_id": decision.policy_id,
                    "policy_name": decision.policy_name,
                },
            )

        if decision.decision == "pause":
            approval = await self.hitl_service.trigger_approval_request(
                delegation_id=str(delegation.id),
                org_id=str(org.id),
                reason=decision.reason,
                caller_agent_id=caller_agent.agent_id,
                callee_agent_id=callee.agent_id,
                estimated_cost_usd=estimated_cost,
                context_scope=request.context_scope,
            )
            delegation.status = "pending_approval"
            await self.db.commit()
            await self.audit_service.append(
                org_id=str(org.id),
                event_type="hil_triggered",
                actor_agent_id=caller_agent.agent_id,
                target_agent_id=callee.agent_id,
                details={
                    "reason": decision.reason,
                    "policy_id": decision.policy_id,
                    "policy_version": decision.policy_version,
                    "estimated_cost_usd": estimated_cost,
                    "approval_deadline": approval["approval_deadline"],
                    "workflow": delegation.workflow,
                },
                delegation_id=str(delegation.id),
            )
            return DelegationResponse(
                delegation_id=str(delegation.id),
                status="pending_approval",
                policy_result=PolicyResultResponse(
                    policy_id=decision.policy_id,
                    policy_version=decision.policy_version,
                    decision="pause",
                ),
                poll_url=f"/v1/delegations/{delegation.id}",
                approval_deadline=approval["approval_deadline"],
            )

        return await self._dispatch_to_callee(
            org=org,
            caller_agent=caller_agent,
            callee=callee,
            delegation=delegation,
            timeout_ms=request.timeout_ms,
            async_mode=bool(request.callback_url),
            start_time=start_time,
        )

    async def approve_and_resume(
        self,
        org: Organization,
        delegation_id: str,
        approver_email: str,
        approver_role: str,
    ) -> DelegationResponse:
        """Approve a paused delegation and immediately resume execution."""
        settings = get_settings()
        delegation = await self.hitl_service.approve(
            delegation_id,
            str(org.id),
            approver_email=approver_email,
            approver_role=approver_role,
        )

        caller_result = await self.db.execute(
            select(Agent).where(
                Agent.org_id == org.id,
                Agent.agent_id == delegation.caller_agent_id,
            )
        )
        caller_agent = caller_result.scalar_one_or_none()
        if not caller_agent:
            raise NexraError(404, AGENT_NOT_FOUND, "Caller agent not found")

        callee_result = await self.db.execute(
            select(Agent).where(
                Agent.org_id == delegation.callee_org_id,
                Agent.agent_id == delegation.callee_agent_id,
            )
        )
        callee = callee_result.scalar_one_or_none()
        if not callee:
            raise NexraError(404, AGENT_NOT_FOUND, "Callee agent not found")

        return await self._dispatch_to_callee(
            org=org,
            caller_agent=caller_agent,
            callee=callee,
            delegation=delegation,
            timeout_ms=settings.webhook_timeout_default_ms,
            async_mode=bool(delegation.callback_url),
            start_time=time.perf_counter(),
        )

    async def _dispatch_to_callee(
        self,
        org: Organization,
        caller_agent: Agent,
        callee: Agent,
        delegation: Delegation,
        timeout_ms: int,
        async_mode: bool,
        start_time: float,
    ) -> DelegationResponse:
        settings = get_settings()

        if await self.circuit_breaker.is_tripped(callee.agent_id, str(callee.org_id)):
            delegation.status = "blocked"
            delegation.completed_at = datetime.now(timezone.utc)
            delegation.actual_cost_usd = 0
            callee.status = "quarantined"
            await self.db.commit()
            await self.budget_service.release(
                str(delegation.caller_org_id),
                delegation.caller_agent_id,
                str(delegation.id),
            )
            await self.audit_service.append(
                org_id=str(delegation.caller_org_id),
                event_type="circuit_breaker_tripped",
                actor_agent_id=delegation.caller_agent_id,
                target_agent_id=delegation.callee_agent_id,
                details={"threshold": 0.50, "window_seconds": 600},
                delegation_id=str(delegation.id),
            )
            await self.audit_service.append(
                org_id=str(delegation.caller_org_id),
                event_type="agent_quarantined",
                actor_agent_id=None,
                target_agent_id=delegation.callee_agent_id,
                details={"reason": "circuit_breaker", "trigger": "auto"},
                delegation_id=str(delegation.id),
            )
            raise NexraError(403, AGENT_QUARANTINED, "Callee agent circuit breaker tripped")

        org_secret = decrypt_aes_gcm(
            org.jwt_secret_enc,
            settings.secret_key_encryption_key,
        )
        delegation_token = issue_delegation_token(
            org_secret,
            str(delegation.id),
            callee.agent_id,
            delegation.context_scope,
        )

        webhook_payload = {
            "delegation_id": str(delegation.id),
            "task": delegation.task,
            "context_scope": delegation.context_scope,
            "budget_cap_usd": float(delegation.budget_cap_usd or 0),
            "timeout_ms": timeout_ms,
            "delegation_token": delegation_token,
            "complete_url": f"{settings.api_base_url}/v1/delegations/{delegation.id}/complete",
        }

        delegation.status = "in_flight"
        await self.db.commit()

        await self.audit_service.append(
            org_id=str(org.id),
            event_type="delegation_initiated",
            actor_agent_id=caller_agent.agent_id,
            target_agent_id=callee.agent_id,
            details={
                "task_hash": delegation.task_hash,
                "budget_cap_usd": float(delegation.budget_cap_usd or 0),
                "workflow": delegation.workflow,
            },
            delegation_id=str(delegation.id),
        )

        if async_mode:
            await self.webhook_service.enqueue(
                callee.webhook_url,
                webhook_payload,
                callee.webhook_secret,
                str(delegation.id),
            )
            return DelegationResponse(
                delegation_id=str(delegation.id),
                status="in_flight",
                policy_result=PolicyResultResponse(
                    policy_id=str(delegation.policy_id) if delegation.policy_id else None,
                    policy_version=delegation.policy_version,
                    decision=delegation.policy_decision or "allow",
                ),
                poll_url=f"/v1/delegations/{delegation.id}",
            )

        try:
            callee_response = await self.webhook_service.deliver_and_await(
                callee.webhook_url,
                webhook_payload,
                callee.webhook_secret,
                str(delegation.id),
                timeout_ms,
            )
        except NexraError as exc:
            await self._fail_delegation(delegation, callee, caller_agent.agent_id, exc)
            raise

        response_result = callee_response
        response_usage = None
        if isinstance(callee_response, dict):
            if "result" in callee_response:
                response_result = callee_response.get("result")
            response_usage = callee_response.get("usage")

        latency_ms = round((time.perf_counter() - start_time) * 1000)
        return await self._apply_completion(
            delegation=delegation,
            result=response_result if isinstance(response_result, dict) else {"result": response_result},
            usage=response_usage if isinstance(response_usage, dict) else None,
            latency_ms=latency_ms,
            completion_mode="sync_webhook",
        )

    async def _fail_delegation(
        self,
        delegation: Delegation,
        callee: Agent,
        caller_agent_id: str,
        error: NexraError,
    ) -> None:
        delegation.status = "timeout" if error.code == "DELEGATION_TIMEOUT" else "failed"
        delegation.completed_at = datetime.now(timezone.utc)
        delegation.actual_cost_usd = 0
        await self.db.commit()

        await self.budget_service.release(
            str(delegation.caller_org_id),
            caller_agent_id,
            str(delegation.id),
        )

        event_type = "delegation_timeout" if error.code == "DELEGATION_TIMEOUT" else "delegation_failed"
        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type=event_type,
            actor_agent_id=caller_agent_id,
            target_agent_id=delegation.callee_agent_id,
            details={
                "error_code": error.code,
                "error_message": error.message,
                "policy_id": str(delegation.policy_id) if delegation.policy_id else None,
                "policy_version": delegation.policy_version,
            },
            delegation_id=str(delegation.id),
        )

        await self._record_circuit_outcome(callee, delegation, success=False)

    async def _apply_completion(
        self,
        delegation: Delegation,
        result: dict,
        usage: dict | None,
        latency_ms: int,
        completion_mode: str,
    ) -> DelegationResponse:
        delegation.status = "completed"
        delegation.result = result
        delegation.completed_at = datetime.now(timezone.utc)

        external_cost = 0.0
        if usage:
            delegation.llm_tokens = usage.get("llm_tokens")
            external_cost = float(usage.get("external_api_cost_usd", 0) or 0)

        actual_cost = float(delegation.estimated_cost_usd or 0) + external_cost
        delegation.actual_cost_usd = actual_cost
        delegation.latency_ms = latency_ms
        await self.db.commit()

        await self.budget_service.settle(
            str(delegation.caller_org_id),
            delegation.caller_agent_id,
            str(delegation.id),
            actual_cost,
        )
        await self.trust_service.update_after_delegation(
            delegation.callee_agent_id,
            str(delegation.callee_org_id),
            delegation,
        )

        callee_result = await self.db.execute(
            select(Agent).where(
                Agent.org_id == delegation.callee_org_id,
                Agent.agent_id == delegation.callee_agent_id,
            )
        )
        callee = callee_result.scalar_one_or_none()
        if callee:
            await self._record_circuit_outcome(callee, delegation, success=True)

        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type="delegation_completed",
            actor_agent_id=delegation.caller_agent_id,
            target_agent_id=delegation.callee_agent_id,
            details={
                "result_keys": list(result.keys()) if isinstance(result, dict) else [],
                "policy_id": str(delegation.policy_id) if delegation.policy_id else None,
                "policy_version": delegation.policy_version,
                "completion_mode": completion_mode,
            },
            delegation_id=str(delegation.id),
            cost_usd=actual_cost,
        )

        await self._queue_billing_event(delegation, actual_cost)
        await self._maybe_settle_marketplace_payout(delegation, actual_cost)
        await self._notify_caller_callback(delegation, result, latency_ms)

        return DelegationResponse(
            delegation_id=str(delegation.id),
            status="completed",
            policy_result=PolicyResultResponse(
                policy_id=str(delegation.policy_id) if delegation.policy_id else None,
                policy_version=delegation.policy_version,
                decision=delegation.policy_decision or "allow",
            ),
            result=result,
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
        """Called by callee to post result back via /delegations/{id}/complete."""
        settings = get_settings()
        org_secret = decrypt_aes_gcm(
            org.jwt_secret_enc,
            settings.secret_key_encryption_key,
        )

        try:
            payload = await verify_delegation_token(token, org_secret, self.redis)
        except ValueError as exc:
            raise NexraError(401, INVALID_DELEGATION_TOKEN, str(exc))

        if payload.get("delegation_id") != delegation_id:
            raise NexraError(401, INVALID_DELEGATION_TOKEN, "Delegation ID mismatch in token")

        db_result = await self.db.execute(
            select(Delegation).where(Delegation.id == delegation_id)
        )
        delegation = db_result.scalar_one_or_none()
        if not delegation:
            raise NexraError(404, DELEGATION_NOT_FOUND, f"Delegation '{delegation_id}' not found")

        if delegation.status == "completed":
            raise NexraError(409, DELEGATION_ALREADY_COMPLETE, "Delegation already completed")

        callee_result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == payload.get("callee_agent_id"),
                Agent.org_id == delegation.callee_org_id,
            )
        )
        callee = callee_result.scalar_one_or_none()
        if not callee:
            raise NexraError(404, AGENT_NOT_FOUND, "Callee agent not found")

        await self._validate_callee_output(callee, result)

        computed_latency = delegation.latency_ms
        if not computed_latency:
            computed_latency = max(
                0,
                int((datetime.now(timezone.utc) - delegation.created_at).total_seconds() * 1000),
            )

        return await self._apply_completion(
            delegation=delegation,
            result=result,
            usage=usage,
            latency_ms=computed_latency,
            completion_mode="callee_complete_endpoint",
        )

    async def _validate_callee_output(self, callee: Agent, result: dict) -> None:
        if callee.output_schema and callee.output_schema.get("type"):
            try:
                jsonschema.validate(result, callee.output_schema)
            except jsonschema.ValidationError as exc:
                raise NexraError(
                    422,
                    OUTPUT_SCHEMA_FAILED,
                    f"Result validation failed: {exc.message}",
                )

    async def _notify_caller_callback(
        self,
        delegation: Delegation,
        result: dict,
        latency_ms: int,
    ) -> None:
        if not delegation.callback_url:
            return

        payload = {
            "delegation_id": str(delegation.id),
            "status": "completed",
            "result": result,
            "usage": {
                "cost_usd": float(delegation.actual_cost_usd or 0),
                "latency_ms": latency_ms,
                "llm_tokens": delegation.llm_tokens,
            },
            "completed_at": delegation.completed_at.isoformat() if delegation.completed_at else None,
        }
        try:
            await self.webhook_service.deliver_callback(
                callback_url=delegation.callback_url,
                payload=payload,
                delegation_id=str(delegation.id),
            )
            await self.audit_service.append(
                org_id=str(delegation.caller_org_id),
                event_type="callback_delivered",
                actor_agent_id=delegation.caller_agent_id,
                target_agent_id=delegation.callee_agent_id,
                details={"callback_url": delegation.callback_url},
                delegation_id=str(delegation.id),
            )
        except NexraError as exc:
            await self.audit_service.append(
                org_id=str(delegation.caller_org_id),
                event_type="callback_failed",
                actor_agent_id=delegation.caller_agent_id,
                target_agent_id=delegation.callee_agent_id,
                details={
                    "callback_url": delegation.callback_url,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
                delegation_id=str(delegation.id),
            )

    async def _queue_billing_event(self, delegation: Delegation, actual_cost: float) -> None:
        org_result = await self.db.execute(
            select(Organization).where(Organization.id == delegation.caller_org_id)
        )
        org = org_result.scalar_one_or_none()
        if not org or not org.stripe_id:
            return

        queued = False
        try:
            from workers.billing_worker import record_stripe_usage

            record_stripe_usage.delay(
                stripe_customer_id=org.stripe_id,
                delegation_id=str(delegation.id),
                timestamp=int(delegation.created_at.timestamp()),
            )
            queued = True
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Failed to queue billing event for delegation %s: %s",
                delegation.id,
                exc,
            )

        if not queued:
            await self.billing_service.record_delegation_usage(org, delegation, actual_cost)

    async def _record_circuit_outcome(
        self,
        callee: Agent,
        delegation: Delegation,
        success: bool,
    ) -> None:
        await self.circuit_breaker.record_outcome(
            callee.agent_id,
            str(callee.org_id),
            success,
        )
        if success:
            return

        tripped = await self.circuit_breaker.is_tripped(callee.agent_id, str(callee.org_id))
        if not tripped or callee.status == "quarantined":
            return

        callee.status = "quarantined"
        await self.db.commit()
        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type="circuit_breaker_tripped",
            actor_agent_id=delegation.caller_agent_id,
            target_agent_id=delegation.callee_agent_id,
            details={"threshold": 0.50, "window_seconds": 600},
            delegation_id=str(delegation.id),
        )
        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type="agent_quarantined",
            actor_agent_id=None,
            target_agent_id=delegation.callee_agent_id,
            details={
                "trigger": "auto",
                "reason": "circuit_breaker_failure_rate",
            },
            delegation_id=str(delegation.id),
        )

    async def _derive_depth(
        self,
        org_id: str,
        parent_delegation_id: str | None,
    ) -> tuple[str | None, int]:
        if not parent_delegation_id:
            return None, 0

        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == parent_delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        parent = result.scalar_one_or_none()
        if not parent:
            raise NexraError(
                400,
                INVALID_REQUEST,
                (
                    f"parent_delegation_id '{parent_delegation_id}' "
                    "not found in caller org"
                ),
            )
        return str(parent.id), int(parent.delegation_depth) + 1

    async def _maybe_settle_marketplace_payout(
        self,
        delegation: Delegation,
        actual_cost: float,
    ) -> None:
        if actual_cost <= 0:
            return
        if not delegation.callee_org_id:
            return
        if delegation.caller_org_id == delegation.callee_org_id:
            return

        marketplace = MarketplaceService(self.db)
        await marketplace.create_pending_payout(
            delegation=delegation,
            callee_org_id=str(delegation.callee_org_id),
            amount_usd=actual_cost,
        )
        settled = await marketplace.settle_pending_payouts()
        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type="marketplace_payout",
            actor_agent_id=delegation.caller_agent_id,
            target_agent_id=delegation.callee_agent_id,
            details={
                "delegation_id": str(delegation.id),
                "gross_amount_usd": actual_cost,
                "platform_fee_rate": 0.20,
                "settled_count": settled,
            },
            delegation_id=str(delegation.id),
            cost_usd=actual_cost,
        )

    async def get_status(self, org_id: str, delegation_id: str) -> Delegation:
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

    async def _resolve_callee(
        self,
        caller_org_id: str,
        callee_agent_id: str,
        include_cross_org: bool,
    ) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == callee_agent_id,
                Agent.org_id == caller_org_id,
                Agent.status != "quarantined",
            )
        )
        agent = result.scalar_one_or_none()
        if agent:
            return agent

        if include_cross_org:
            result = await self.db.execute(
                select(Agent).where(
                    Agent.agent_id == callee_agent_id,
                    Agent.is_public == True,  # noqa: E712
                    Agent.status != "quarantined",
                )
            )
            return result.scalar_one_or_none()

        return None
