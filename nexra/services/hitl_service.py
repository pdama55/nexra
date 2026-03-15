import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.errors import DELEGATION_NOT_FOUND, NexraError
from models.delegation import Delegation
from services.audit_service import AuditService

logger = logging.getLogger("nexra.services.hitl")


class HiTLService:
    """Human-in-the-Loop approval service for paused delegations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def trigger_approval_request(
        self, delegation_id: str, org_id: str, reason: str
    ) -> dict:
        settings = get_settings()
        ttl_hours = settings.hil_approval_ttl_hours
        deadline = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        return {
            "delegation_id": delegation_id,
            "status": "pending_approval",
            "approval_deadline": deadline.isoformat(),
            "reason": reason,
        }

    async def approve(self, delegation_id: str, org_id: str, approver: str) -> Delegation:
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        delegation = result.scalar_one_or_none()
        if not delegation:
            raise NexraError(404, DELEGATION_NOT_FOUND, "Delegation not found")
        if delegation.status != "pending_approval":
            raise NexraError(409, "INVALID_STATE", f"Delegation status is '{delegation.status}', expected 'pending_approval'")

        delegation.status = "pending"
        await self.db.commit()

        audit = AuditService(self.db)
        await audit.append(
            org_id=org_id, event_type="delegation_approved",
            actor_agent_id=approver, target_agent_id=delegation.callee_agent_id,
            details={"approver": approver},
            delegation_id=delegation_id,
        )
        return delegation

    async def reject(self, delegation_id: str, org_id: str, rejector: str, reason: str = "") -> Delegation:
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.id == delegation_id,
                Delegation.caller_org_id == org_id,
            )
        )
        delegation = result.scalar_one_or_none()
        if not delegation:
            raise NexraError(404, DELEGATION_NOT_FOUND, "Delegation not found")
        if delegation.status != "pending_approval":
            raise NexraError(409, "INVALID_STATE", f"Delegation status is '{delegation.status}', expected 'pending_approval'")

        delegation.status = "blocked"
        delegation.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        audit = AuditService(self.db)
        await audit.append(
            org_id=org_id, event_type="delegation_rejected",
            actor_agent_id=rejector, target_agent_id=delegation.callee_agent_id,
            details={"rejector": rejector, "reason": reason},
            delegation_id=delegation_id,
        )
        return delegation

    async def expire_stale(self) -> int:
        settings = get_settings()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.hil_approval_ttl_hours)
        result = await self.db.execute(
            select(Delegation).where(
                Delegation.status == "pending_approval",
                Delegation.created_at < cutoff,
            )
        )
        stale = list(result.scalars().all())
        for d in stale:
            d.status = "blocked"
            d.completed_at = datetime.now(timezone.utc)
        if stale:
            await self.db.commit()
            logger.info(f"Expired {len(stale)} stale approval requests")
        return len(stale)
