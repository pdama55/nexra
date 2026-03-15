import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import get_settings
from services.audit_service import AuditService
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.siem")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def export_audit_events(self, org_id: str, target: str, endpoint: str, api_key: str | None = None):
    """Export recent audit events to SIEM (Splunk/Datadog/Elastic/generic)."""
    asyncio.run(_export(org_id, target, endpoint, api_key))


async def _export(org_id: str, target: str, endpoint: str, api_key: str | None):
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        service = AuditService(session)
        entries, _ = await service.query(org_id, limit=100)

        events = [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "actor_agent_id": e.actor_agent_id,
                "target_agent_id": e.target_agent_id,
                "details": e.details,
                "cost_usd": float(e.cost_usd) if e.cost_usd else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]

        headers = {"Content-Type": "application/json"}
        if api_key:
            if target == "splunk":
                headers["Authorization"] = f"Splunk {api_key}"
            elif target == "datadog":
                headers["DD-API-KEY"] = api_key
            else:
                headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json={"events": events}, headers=headers)
            resp.raise_for_status()
            logger.info(f"Exported {len(events)} events to {target} for org {org_id}")

    await engine.dispose()
