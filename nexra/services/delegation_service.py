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
    MAX_DEPTH_EXCEEDED,
    OUTPUT_SCHEMA_FAILED,
    POLICY_BLOCKED,
    SCHEMA_VALIDATION_FAILED,
    INVALID_REQUEST,
    NexraError,
)
from core.jwt import issue_delegation_token, verify_delegation_token
from models.agent import Agent
from models.delegation import Delegation
from models.organization import Organization
from services.audit_service import AuditService
from services.budget_service import BudgetService
from services.marketplace_service import MarketplaceService
from services.policy_engine import DelegationContext, PolicyEngine
from services.trust_service import TrustService
from services.webhook_service import WebhookService

logger = logging.getLogger("nexra.services.delegation")


class DelegationService:
    """Orchestrates the 13-step delegation flow."""

    def __init__(
        self,
        db: AsyncSession,
        redis_client: aioredis.Redis,
        policy_engine: PolicyEngine,
        webhook_service: WebhookService,
        budget_service: BudgetService,
        audit_service: AuditService,
        trust_service: TrustService,
    ) -> None:
        self.db = db
        self.redis = redis_client
        self.policy_engine = policy_engine
        self.webhook_service = webhook_service
        self.budget_service = budget_service
        self.audit_service = audit_service
        self.trust_service = trust_service

    async def initiate(
        self,
        org: Organization,
        caller_agent: Agent,
        request: DelegateRequest,
    ) -> DelegationResponse:
        """Execute the delegation lifecycle with deterministic budget accounting."""
        start_time = time.perf_counter()
        settings = get_settings()

        # Step 1: Resolve callee
        callee = await self._resolve_callee(
            str(org.id), request.callee_agent_id, request.include_cross_org
        )
        if not callee:
            raise NexraError(404, AGENT_NOT_FOUND, f"Callee agent '{request.callee_agent_id}' not found")

        # Step 2: Validate caller status
        if caller_agent.status == "quarantined":
            raise NexraError(403, AGENT_QUARANTINED, "Caller agent is quarantined")

        # Step 3: Schema validate task payload
        if callee.input_schema and callee.input_schema.get("type"):
            try:
                task_input = request.task.get("input", request.task)
                jsonschema.validate(task_input, callee.input_schema)
            except jsonschema.ValidationError as e:
                raise NexraError(422, SCHEMA_VALIDATION_FAILED, f"Task payload validation failed: {e.message}")

        # Step 4: Estimate cost
        estimated_cost = float(callee.pricing.get("per_call_usd", 0))

        # Step 5: Compute delegation depth
        parent_id, depth = await self._derive_depth(str(org.id), request.parent_delegation_id)
        max_depth = settings.max_delegation_depth_default
        if depth > max_depth:
            raise NexraError(400, MAX_DEPTH_EXCEEDED, f"Delegation depth {depth} exceeds limit {max_depth}")

        # Step 6: Create delegation record (policy + budget outcomes are applied below)
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
            delegation_depth=depth,
            parent_delegation_id=parent_id,
            status="pending",
        )
        self.db.add(delegation)
        await self.db.flush()

        # Step 7: Reserve budget against caller principal
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

        # Step 8: Policy evaluation
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

        # Audit: policy evaluated
        await self.audit_service.append(
            org_id=str(org.id), event_type="policy_evaluated",
            actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
            details={
                "decision": decision.decision,
                "policy_id": decision.policy_id,
                "policy_version": decision.policy_version,
                "reason": decision.reason,
            },
            delegation_id=str(delegation.id),
        )

        # Step 9: Handle non-allow decisions
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
                org_id=str(org.id), event_type="delegation_blocked",
                actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
                details={
                    "reason": decision.reason,
                    "policy_id": decision.policy_id,
                    "policy_version": decision.policy_version,
                },
                delegation_id=str(delegation.id),
            )
            raise NexraError(
                403, POLICY_BLOCKED, decision.reason,
                {"policy_id": decision.policy_id, "policy_name": decision.policy_name},
            )

        if decision.decision == "pause":
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
            )

        # Step 10: Issue delegation token
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)
        delegation_token = issue_delegation_token(
            org_secret, str(delegation.id), callee.agent_id, request.context_scope
        )

        # Step 11: Build webhook payload
        webhook_payload = {
            "delegation_id": str(delegation.id),
            "task": request.task,
            "context_scope": request.context_scope,
            "budget_cap_usd": request.budget_cap_usd,
            "timeout_ms": request.timeout_ms,
            "delegation_token": delegation_token,
            "complete_url": f"{settings.api_base_url}/v1/delegations/{delegation.id}/complete",
        }

        # Step 12: Deliver webhook
        delegation.status = "in_flight"
        await self.db.commit()

        await self.audit_service.append(
            org_id=str(org.id), event_type="delegation_initiated",
            actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
            details={"task_hash": delegation.task_hash, "budget_cap_usd": float(request.budget_cap_usd)},
            delegation_id=str(delegation.id),
        )

        try:
            callee_response = await self.webhook_service.deliver_and_await(
                callee.webhook_url,
                webhook_payload,
                callee.webhook_secret,
                str(delegation.id),
                request.timeout_ms,
            )
        except NexraError as e:
            delegation.status = "timeout" if e.code == "DELEGATION_TIMEOUT" else "failed"
            delegation.completed_at = datetime.now(timezone.utc)
            delegation.actual_cost_usd = 0
            await self.db.commit()
            await self.budget_service.release(
                str(org.id),
                caller_agent.agent_id,
                str(delegation.id),
            )
            event_type = "delegation_timeout" if e.code == "DELEGATION_TIMEOUT" else "delegation_failed"
            await self.audit_service.append(
                org_id=str(org.id), event_type=event_type,
                actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
                details={
                    "error_code": e.code,
                    "error_message": e.message,
                    "policy_id": decision.policy_id,
                    "policy_version": decision.policy_version,
                },
                delegation_id=str(delegation.id),
            )
            raise

        # Step 13: Process result
        latency_ms = round((time.perf_counter() - start_time) * 1000)
        actual_cost = estimated_cost

        delegation.status = "completed"
        delegation.result = callee_response
        delegation.actual_cost_usd = actual_cost
        delegation.latency_ms = latency_ms
        delegation.llm_tokens = callee_response.get("usage", {}).get("llm_tokens")
        delegation.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        await self.budget_service.settle(
            str(org.id),
            caller_agent.agent_id,
            str(delegation.id),
            actual_cost,
        )
        await self.trust_service.update_after_delegation(callee.agent_id, str(callee.org_id), delegation)
        result_keys = list(callee_response.get("result", {}).keys()) if isinstance(callee_response.get("result"), dict) else []
        await self.audit_service.append(
            org_id=str(org.id), event_type="delegation_completed",
            actor_agent_id=caller_agent.agent_id, target_agent_id=callee.agent_id,
            details={
                "result_keys": result_keys,
                "policy_id": decision.policy_id,
                "policy_version": decision.policy_version,
            },
            delegation_id=str(delegation.id), cost_usd=actual_cost,
        )
        await self._maybe_settle_marketplace_payout(delegation, actual_cost)

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

    async def _derive_depth(self, org_id: str, parent_delegation_id: str | None) -> tuple[str | None, int]:
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
                f"parent_delegation_id '{parent_delegation_id}' not found in caller org",
            )
        return str(parent.id), int(parent.delegation_depth) + 1

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
        org_secret = decrypt_aes_gcm(org.jwt_secret_enc, settings.secret_key_encryption_key)

        payload = await verify_delegation_token(token, org_secret, self.redis)

        if payload["delegation_id"] != delegation_id:
            raise NexraError(401, "INVALID_DELEGATION_TOKEN", "Delegation ID mismatch in token")

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

        delegation.status = "completed"
        delegation.result = result
        delegation.completed_at = datetime.now(timezone.utc)

        external_cost = 0.0
        if usage:
            delegation.llm_tokens = usage.get("llm_tokens")
            external_cost = float(usage.get("external_api_cost_usd", 0) or 0)
        actual_cost = float(delegation.estimated_cost_usd or 0) + external_cost
        delegation.actual_cost_usd = actual_cost
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
        await self.audit_service.append(
            org_id=str(delegation.caller_org_id),
            event_type="delegation_completed",
            actor_agent_id=delegation.caller_agent_id,
            target_agent_id=delegation.callee_agent_id,
            details={
                "result_keys": list(result.keys()) if isinstance(result, dict) else [],
                "policy_id": str(delegation.policy_id) if delegation.policy_id else None,
                "policy_version": delegation.policy_version,
                "completion_mode": "callee_complete_endpoint",
            },
            delegation_id=str(delegation.id),
            cost_usd=actual_cost,
        )
        await self._maybe_settle_marketplace_payout(delegation, actual_cost)

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
                latency_ms=delegation.latency_ms or 0,
                llm_tokens=delegation.llm_tokens,
            ),
        )

    async def _maybe_settle_marketplace_payout(
        self, delegation: Delegation, actual_cost: float
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
        self, caller_org_id: str, callee_agent_id: str, include_cross_org: bool
    ) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == callee_agent_id,
                Agent.org_id == caller_org_id,
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
