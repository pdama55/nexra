"""Unit tests for compliance report sections and org-scoped query behavior."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.compliance_service import ComplianceService


def _audit_entry(
    event_type: str,
    *,
    actor_agent_id: str | None = "agent-a",
    details: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_type=event_type,
        actor_agent_id=actor_agent_id,
        details=details or {},
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_soc2_report_has_required_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_org_ids: list[str] = []

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        async def query(self, org_id: str, **kwargs):  # type: ignore[no-untyped-def]
            captured_org_ids.append(org_id)
            return (
                [
                    _audit_entry("delegation_completed"),
                    _audit_entry("delegation_blocked"),
                    _audit_entry("policy_evaluated", details={"policy_version": 2}),
                    _audit_entry("delegation_timeout"),
                ],
                None,
            )

    monkeypatch.setattr("services.compliance_service.AuditService", FakeAuditService)
    service = ComplianceService(AsyncMock())
    report = await service.generate_report("org-soc2", "soc2")

    assert captured_org_ids == ["org-soc2"]
    assert "access_controls" in report
    assert "processing_integrity" in report
    assert "incident_response" in report
    assert "change_management" in report


@pytest.mark.asyncio
async def test_gdpr_report_tracks_agent_context_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        async def query(self, _org_id: str, **kwargs):  # type: ignore[no-untyped-def]
            return (
                [
                    _audit_entry(
                        "delegation_completed",
                        actor_agent_id="agent-1",
                        details={"context_scope": ["deal_metadata", "crm"]},
                    ),
                ],
                None,
            )

    monkeypatch.setattr("services.compliance_service.AuditService", FakeAuditService)
    service = ComplianceService(AsyncMock())
    report = await service.generate_report("org-gdpr", "gdpr")

    assert "data_access" in report
    assert report["data_access"][0]["agent_id"] == "agent-1"
    assert report["data_access"][0]["context_scope"] == ["crm", "deal_metadata"]
    assert "data_processing" in report


@pytest.mark.asyncio
async def test_hipaa_report_contains_phi_access(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        async def query(self, _org_id: str, **kwargs):  # type: ignore[no-untyped-def]
            return (
                [
                    _audit_entry(
                        "delegation_completed",
                        actor_agent_id="med-agent",
                        details={"context_scope": ["phi", "treatment"]},
                    ),
                    _audit_entry(
                        "delegation_completed",
                        actor_agent_id="other-agent",
                        details={"context_scope": ["deal_metadata"]},
                    ),
                ],
                None,
            )

    monkeypatch.setattr("services.compliance_service.AuditService", FakeAuditService)
    service = ComplianceService(AsyncMock())
    report = await service.generate_report("org-hipaa", "hipaa")

    assert "phi_access" in report
    assert len(report["phi_access"]) == 1
    assert report["phi_access"][0]["agent_id"] == "med-agent"
    assert "safeguards" in report
