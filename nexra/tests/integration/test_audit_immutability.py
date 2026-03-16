"""Integration tests for audit log — append-only immutability."""

import uuid

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.audit_log import AuditLog
from models.organization import Organization
from services.audit_service import AuditService


TEST_ENC_KEY = "a" * 64


async def _create_org(db: AsyncSession) -> Organization:
    raw_key, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Audit Test Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db.add(org)
    await db.flush()
    return org


class TestAuditLogAppend:
    @pytest.mark.asyncio
    async def test_append_creates_audit_entry(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        service = AuditService(db_session)

        entry = await service.append(
            org_id=str(org.id),
            event_type="delegation_initiated",
            actor_agent_id="caller-agent",
            target_agent_id="callee-agent",
            details={"task_hash": "abc123", "budget_cap_usd": 1.0},
        )

        assert entry.id is not None
        assert entry.event_type == "delegation_initiated"
        assert entry.actor_agent_id == "caller-agent"

    @pytest.mark.asyncio
    async def test_query_returns_own_org_entries(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        service = AuditService(db_session)

        await service.append(
            org_id=str(org.id), event_type="policy_evaluated",
            actor_agent_id="a1", target_agent_id="a2", details={"decision": "allow"},
        )
        await service.append(
            org_id=str(org.id), event_type="delegation_completed",
            actor_agent_id="a1", target_agent_id="a2", details={"result_keys": ["answer"]},
        )

        entries, cursor = await service.query(str(org.id))
        assert len(entries) >= 2
        event_types = {e.event_type for e in entries}
        assert "policy_evaluated" in event_types
        assert "delegation_completed" in event_types

    @pytest.mark.asyncio
    async def test_query_filter_by_event_type(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        service = AuditService(db_session)

        await service.append(
            org_id=str(org.id), event_type="policy_evaluated",
            actor_agent_id="a1", target_agent_id="a2", details={},
        )
        await service.append(
            org_id=str(org.id), event_type="delegation_blocked",
            actor_agent_id="a1", target_agent_id="a3", details={},
        )

        entries, _ = await service.query(str(org.id), event_type="delegation_blocked")
        for e in entries:
            assert e.event_type == "delegation_blocked"

    @pytest.mark.asyncio
    async def test_query_filter_by_agent_id(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        service = AuditService(db_session)

        await service.append(
            org_id=str(org.id), event_type="delegation_initiated",
            actor_agent_id="agent-x", target_agent_id="agent-y", details={},
        )
        await service.append(
            org_id=str(org.id), event_type="delegation_initiated",
            actor_agent_id="agent-z", target_agent_id="agent-w", details={},
        )

        entries, _ = await service.query(str(org.id), agent_id="agent-x")
        for e in entries:
            assert e.actor_agent_id == "agent-x" or e.target_agent_id == "agent-x"

    @pytest.mark.asyncio
    async def test_csv_export(self, db_session: AsyncSession) -> None:
        org = await _create_org(db_session)
        service = AuditService(db_session)

        await service.append(
            org_id=str(org.id), event_type="delegation_completed",
            actor_agent_id="a1", target_agent_id="a2",
            details={"key": "value"}, cost_usd=0.25,
        )

        csv_data = await service.export_csv(str(org.id))
        assert "delegation_completed" in csv_data
        assert "a1" in csv_data
        assert csv_data.startswith("id,")


class TestAuditLogImmutability:
    """Test that the DB trigger prevents UPDATE and DELETE on audit_log.

    NOTE: These tests require the immutability trigger from migration 001.
    If the trigger was not applied, these tests will FAIL — which is the point.
    """

    @pytest.mark.asyncio
    async def test_update_is_rejected_by_trigger(self, db_session: AsyncSession) -> None:
        """Attempting to UPDATE an audit log entry should raise an error."""
        org = await _create_org(db_session)
        service = AuditService(db_session)

        entry = await service.append(
            org_id=str(org.id), event_type="delegation_initiated",
            actor_agent_id="a1", target_agent_id="a2", details={"original": True},
        )

        with pytest.raises(Exception) as exc:
            await db_session.execute(
                update(AuditLog)
                .where(AuditLog.id == entry.id)
                .values(event_type="tampered")
            )
            await db_session.flush()

        # The trigger should raise a PostgreSQL error
        error_msg = str(exc.value).lower()
        assert "immutable" in error_msg or "cannot" in error_msg or "trigger" in error_msg

    @pytest.mark.asyncio
    async def test_delete_is_rejected_by_trigger(self, db_session: AsyncSession) -> None:
        """Attempting to DELETE an audit log entry should raise an error."""
        org = await _create_org(db_session)
        service = AuditService(db_session)

        entry = await service.append(
            org_id=str(org.id), event_type="delegation_initiated",
            actor_agent_id="a1", target_agent_id="a2", details={},
        )

        with pytest.raises(Exception):
            await db_session.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": str(entry.id)},
            )
            await db_session.flush()
