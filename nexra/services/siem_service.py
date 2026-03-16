import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.audit_log import AuditLog
from models.siem_config import SIEMConfig
from services.audit_service import AuditService

logger = logging.getLogger("nexra.services.siem")


class SIEMService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def set_config(
        self,
        org_id: str,
        target: str,
        endpoint: str,
        api_key: str | None,
        enabled: bool,
        event_types: list[str],
    ) -> None:
        stmt = (
            pg_insert(SIEMConfig)
            .values(
                org_id=org_id,
                target=target,
                endpoint=endpoint,
                api_key=api_key,
                enabled=enabled,
                event_types=event_types,
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=["org_id"],
                set_={
                    "target": target,
                    "endpoint": endpoint,
                    "api_key": api_key,
                    "enabled": enabled,
                    "event_types": event_types,
                    "updated_at": datetime.now(timezone.utc),
                },
            )
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_config(self, org_id: str) -> SIEMConfig | None:
        result = await self.db.execute(
            select(SIEMConfig).where(SIEMConfig.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_enabled_configs(self) -> list[SIEMConfig]:
        result = await self.db.execute(
            select(SIEMConfig).where(SIEMConfig.enabled == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def export_next_batch(self, config: SIEMConfig, batch_limit: int = 500) -> int:
        since = config.cursor or datetime.fromtimestamp(0, tz=timezone.utc)
        audit = AuditService(self.db)
        entries = await audit.query_since(
            org_id=str(config.org_id),
            date_from=since,
            event_types=list(config.event_types) if config.event_types else None,
            limit=batch_limit,
        )
        if not entries:
            return 0

        payload = {
            "events": [
                self._format_event_for_target(config.target, e)
                for e in entries
            ]
        }

        headers = {"Content-Type": "application/json"}
        if config.api_key:
            if config.target == "splunk":
                headers["Authorization"] = f"Splunk {config.api_key}"
            elif config.target == "datadog":
                headers["DD-API-KEY"] = config.api_key
            else:
                headers["Authorization"] = f"Bearer {config.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(config.endpoint, json=payload, headers=headers)
            resp.raise_for_status()

        config.cursor = entries[-1].created_at
        config.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        logger.info(
            "Exported %s SIEM events for org %s to %s",
            len(entries),
            config.org_id,
            config.target,
        )
        return len(entries)

    def _format_event_for_target(self, target: str, entry: AuditLog) -> dict:
        base = {
            "id": str(entry.id),
            "event_type": entry.event_type,
            "org_id": str(entry.org_id),
            "delegation_id": str(entry.delegation_id) if entry.delegation_id else None,
            "actor_agent_id": entry.actor_agent_id,
            "target_agent_id": entry.target_agent_id,
            "details": entry.details,
            "cost_usd": float(entry.cost_usd) if entry.cost_usd else None,
            "created_at": entry.created_at.isoformat(),
        }
        if target == "splunk":
            base["sourcetype"] = "nexra:audit"
            base["source"] = "nexra-control-plane"
            base["host"] = "nexra-api"
        elif target == "datadog":
            base["ddsource"] = "nexra"
            base["ddtags"] = f"event_type:{entry.event_type},org_id:{entry.org_id}"
        elif target == "elastic":
            base["@timestamp"] = entry.created_at.isoformat()
            base["_index"] = "nexra-audit"
        return base
