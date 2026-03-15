import logging
import uuid

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NexraError, POLICY_NOT_FOUND
from models.policy import Policy

logger = logging.getLogger("nexra.services.policy_version")


class PolicyVersionService:
    """Policy versioning service. Updates create new versions; old versions are preserved."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_version_history(self, org_id: str, policy_name: str) -> list[dict]:
        org_uuid = uuid.UUID(org_id)
        result = await self.db.execute(
            select(Policy)
            .where(Policy.org_id == org_uuid, Policy.name == policy_name)
            .order_by(Policy.version.desc())
        )
        policies = result.scalars().all()
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "version": p.version,
                "enabled": p.enabled,
                "priority": p.priority,
                "rule_yaml": p.rule_yaml,
                "created_at": p.created_at.isoformat(),
            }
            for p in policies
        ]

    async def rollback_to_version(
        self, org_id: str, policy_name: str, target_version: int
    ) -> Policy:
        """Rollback to a specific version by creating a new version with the old config."""
        org_uuid = uuid.UUID(org_id)
        target_result = await self.db.execute(
            select(Policy).where(
                Policy.org_id == org_uuid,
                Policy.name == policy_name,
                Policy.version == target_version,
            )
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise NexraError(404, POLICY_NOT_FOUND, f"Policy version {target_version} not found")

        current_result = await self.db.execute(
            select(Policy)
            .where(Policy.org_id == org_uuid, Policy.name == policy_name, Policy.enabled == True)
            .order_by(Policy.version.desc())
            .limit(1)
        )
        current = current_result.scalar_one_or_none()
        next_version = (current.version + 1) if current else (target_version + 1)

        if current:
            current.enabled = False

        new_policy = Policy(
            org_id=org_uuid,
            name=target.name,
            description=f"Rollback to v{target_version}",
            priority=target.priority,
            rule_yaml=target.rule_yaml,
            version=next_version,
            enabled=True,
        )
        self.db.add(new_policy)
        await self.db.commit()
        await self.db.refresh(new_policy)
        return new_policy
