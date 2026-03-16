"""Unit tests for SIEM export formatting and cursor behavior."""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.siem_service import SIEMService


def _entry(event_type: str, created_at: datetime | None = None) -> SimpleNamespace:
    ts = created_at or datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_type=event_type,
        org_id=uuid.uuid4(),
        delegation_id=uuid.uuid4(),
        actor_agent_id="caller-a",
        target_agent_id="callee-a",
        details={"k": "v"},
        cost_usd=1.25,
        created_at=ts,
    )


@pytest.mark.asyncio
async def test_export_next_batch_updates_cursor_and_posts_target_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.commit = AsyncMock()

    now = datetime.now(timezone.utc)
    entries = [_entry("delegation_completed", now), _entry("delegation_failed", now + timedelta(seconds=10))]

    captured_query: dict[str, object] = {}

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        async def query_since(
            self,
            org_id: str,
            date_from: datetime,
            event_types: list[str] | None = None,
            limit: int = 500,
        ):
            captured_query["org_id"] = org_id
            captured_query["date_from"] = date_from
            captured_query["event_types"] = event_types
            captured_query["limit"] = limit
            return entries

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    captured_post: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        async def post(self, endpoint: str, json: dict, headers: dict):  # type: ignore[no-untyped-def]
            captured_post["endpoint"] = endpoint
            captured_post["json"] = json
            captured_post["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("services.siem_service.AuditService", FakeAuditService)
    monkeypatch.setattr("services.siem_service.httpx.AsyncClient", FakeAsyncClient)

    config = SimpleNamespace(
        org_id=uuid.uuid4(),
        target="splunk",
        endpoint="https://siem.example.com/ingest",
        api_key="siem-key",
        enabled=True,
        event_types=["delegation_completed", "delegation_failed"],
        cursor=None,
        updated_at=now,
    )

    service = SIEMService(db)
    exported = await service.export_next_batch(config, batch_limit=200)

    assert exported == 2
    assert captured_query["org_id"] == str(config.org_id)
    assert captured_query["event_types"] == config.event_types
    assert captured_query["limit"] == 200
    assert captured_post["endpoint"] == "https://siem.example.com/ingest"
    assert (captured_post["headers"] or {}).get("Authorization") == "Splunk siem-key"
    events = (captured_post["json"] or {}).get("events", [])
    assert len(events) == 2
    assert events[0]["sourcetype"] == "nexra:audit"
    assert config.cursor == entries[-1].created_at
    db.commit.assert_awaited_once()


def test_format_event_for_target_variants() -> None:
    db = AsyncMock()
    service = SIEMService(db)
    entry = _entry("policy_evaluated")

    splunk_payload = service._format_event_for_target("splunk", entry)
    datadog_payload = service._format_event_for_target("datadog", entry)
    elastic_payload = service._format_event_for_target("elastic", entry)

    assert splunk_payload["sourcetype"] == "nexra:audit"
    assert "ddsource" in datadog_payload
    assert "@timestamp" in elastic_payload
