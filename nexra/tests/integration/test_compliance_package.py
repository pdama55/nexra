"""Integration tests for SOC2 compliance evidence package."""

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.crypto import encrypt_aes_gcm, generate_api_key, generate_org_jwt_secret
from models.agent import Agent
from models.delegation import Delegation
from models.organization import Organization
from services.audit_service import AuditService
from services.compliance_service import ComplianceService

TEST_ENC_KEY = "a" * 64


async def _create_org(db_session: AsyncSession) -> Organization:
    _, hashed, prefix = generate_api_key()
    org = Organization(
        id=uuid.uuid4(),
        name="Compliance Org",
        api_key_hash=hashed,
        api_key_prefix=prefix,
        plan="growth",
        jwt_secret_enc=encrypt_aes_gcm(generate_org_jwt_secret(), TEST_ENC_KEY),
        delegation_count=0,
    )
    db_session.add(org)
    await db_session.flush()
    return org


@pytest.mark.asyncio
async def test_soc2_core_package_contains_required_files_and_manifest(db_session: AsyncSession) -> None:
    org = await _create_org(db_session)

    db_session.add(
        Agent(
            org_id=org.id,
            agent_id="agent-a",
            name="Agent A",
            description="Agent A for compliance package",
            capability_type="analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            webhook_url="https://example.com/a",
            webhook_secret="a" * 32,
            pricing={"per_call_usd": 0.1},
            sla={"p99_latency_ms": 1000, "availability": 0.99},
            is_public=False,
            trust_score=Decimal("0.900"),
            status="active",
            team="platform",
        )
    )

    delegation = Delegation(
        caller_org_id=org.id,
        caller_agent_id="agent-a",
        callee_org_id=org.id,
        callee_agent_id="agent-a",
        task={"input": {"q": "x"}},
        task_hash="hash-1",
        context_scope=["finance"],
        policy_decision="allow",
        status="completed",
        workflow="reconciliation",
        actual_cost_usd=Decimal("1.2500"),
        created_at=datetime.now(UTC) - timedelta(hours=1),
        completed_at=datetime.now(UTC) - timedelta(minutes=50),
    )
    db_session.add(delegation)
    await db_session.commit()

    audit = AuditService(db_session)
    await audit.append(
        org_id=str(org.id),
        event_type="policy_evaluated",
        actor_agent_id="agent-a",
        target_agent_id="agent-a",
        details={"policy_id": "policy-1", "decision": "allow", "policy_decision": "allow"},
        delegation_id=str(delegation.id),
        cost_usd=1.25,
    )
    await audit.append(
        org_id=str(org.id),
        event_type="hil_triggered",
        actor_agent_id="agent-a",
        target_agent_id="agent-a",
        details={"approval_deadline": datetime.now(UTC).isoformat(), "reason": "threshold"},
        delegation_id=str(delegation.id),
    )
    await audit.append(
        org_id=str(org.id),
        event_type="hil_approved",
        actor_agent_id="admin@example.com",
        target_agent_id="agent-a",
        details={"approver_email": "admin@example.com", "approver_role": "admin"},
        delegation_id=str(delegation.id),
    )

    service = ComplianceService(db_session)
    archive_bytes = await service.generate_soc2_core_package(str(org.id))

    zf = zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r")
    names = set(zf.namelist())
    required = {
        "audit_log.csv",
        "policy_coverage.csv",
        "spend_governance.csv",
        "agent_status_history.csv",
        "hitl_decision_log.csv",
        "manifest.json",
    }
    assert required.issubset(names)

    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    assert manifest["schema_version"] == "2026-03-17.soc2_core.v1"
    assert manifest["set"] == "soc2_core"

    audit_csv = zf.read("audit_log.csv").decode("utf-8")
    spend_csv = zf.read("spend_governance.csv").decode("utf-8")
    hitl_csv = zf.read("hitl_decision_log.csv").decode("utf-8")

    assert "policy_evaluated" in audit_csv
    assert "reconciliation" in spend_csv
    assert "approved" in hitl_csv
