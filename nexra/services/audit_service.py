import csv
import io
import logging
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog

logger = logging.getLogger("nexra.services.audit")


class AuditService:
    """Append-only audit log service.

    Only performs INSERT operations. No UPDATE. No DELETE.
    The DB trigger enforces immutability as defense-in-depth.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def append(
        self,
        org_id: str,
        event_type: str,
        actor_agent_id: str | None,
        target_agent_id: str | None,
        details: dict,
        delegation_id: str | None = None,
        cost_usd: float | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            delegation_id=delegation_id,
            org_id=org_id,
            event_type=event_type,
            actor_agent_id=actor_agent_id,
            target_agent_id=target_agent_id,
            details=details,
            cost_usd=cost_usd,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def query(
        self,
        org_id: str,
        agent_id: str | None = None,
        event_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        delegation_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditLog], str | None]:
        q = select(AuditLog).where(AuditLog.org_id == org_id)

        if agent_id:
            q = q.where(
                or_(
                    AuditLog.actor_agent_id == agent_id,
                    AuditLog.target_agent_id == agent_id,
                )
            )
        if event_type:
            q = q.where(AuditLog.event_type == event_type)
        if date_from:
            q = q.where(AuditLog.created_at >= date_from)
        if date_to:
            q = q.where(AuditLog.created_at <= date_to)
        if delegation_id:
            q = q.where(AuditLog.delegation_id == delegation_id)
        if cursor:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(AuditLog.created_at < cursor_dt)

        q = q.order_by(AuditLog.created_at.desc()).limit(limit + 1)
        result = await self.db.execute(q)
        entries = list(result.scalars().all())

        next_cursor = None
        if len(entries) > limit:
            next_cursor = entries[limit - 1].created_at.isoformat()
            entries = entries[:limit]

        return entries, next_cursor

    async def export_csv(
        self,
        org_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> str:
        entries, _ = await self.query(
            org_id, date_from=date_from, date_to=date_to, limit=10000
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id", "delegation_id", "event_type", "actor_agent_id",
                "target_agent_id", "cost_usd", "created_at", "details",
            ]
        )
        for e in entries:
            writer.writerow(
                [
                    str(e.id), str(e.delegation_id), e.event_type,
                    e.actor_agent_id, e.target_agent_id,
                    str(e.cost_usd) if e.cost_usd else "",
                    e.created_at.isoformat(), str(e.details),
                ]
            )
        return output.getvalue()
