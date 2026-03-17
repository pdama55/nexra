"""Unit tests for HiTL lifecycle transitions and terminal semantics."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.errors import NexraError
from services.hitl_service import HiTLService


def _db_with_delegation(delegation: object) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = delegation
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_approve_requires_pending_approval() -> None:
    delegation = SimpleNamespace(
        id="deleg-1",
        caller_org_id="org-1",
        caller_agent_id="caller-a",
        callee_agent_id="callee-a",
        status="blocked",
    )
    db = _db_with_delegation(delegation)
    service = HiTLService(db)

    with pytest.raises(NexraError) as exc:
        await service.approve(
            "deleg-1",
            "org-1",
            approver_email="admin@example.com",
            approver_role="admin",
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reject_releases_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    delegation = SimpleNamespace(
        id="deleg-2",
        caller_org_id="org-1",
        caller_agent_id="caller-a",
        callee_agent_id="callee-a",
        status="pending_approval",
        completed_at=None,
    )
    db = _db_with_delegation(delegation)

    release_called = AsyncMock()
    append_called = AsyncMock()

    class FakeBudgetService:
        def __init__(self, _db: object) -> None:
            pass

        release = release_called

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        append = append_called

    monkeypatch.setattr("services.hitl_service.BudgetService", FakeBudgetService)
    monkeypatch.setattr("services.hitl_service.AuditService", FakeAuditService)

    service = HiTLService(db)
    result = await service.reject(
        "deleg-2",
        "org-1",
        rejector_email="admin@example.com",
        rejector_role="admin",
        reason="denied",
    )

    assert result.status == "blocked"
    assert result.completed_at is not None
    release_called.assert_awaited_once_with("org-1", "caller-a", "deleg-2")
    append_called.assert_awaited_once()


@pytest.mark.asyncio
async def test_expire_stale_marks_blocked_and_emits_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = SimpleNamespace(
        id="deleg-3",
        caller_org_id="org-1",
        caller_agent_id="caller-a",
        callee_agent_id="callee-a",
        status="pending_approval",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        completed_at=None,
    )

    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [stale]
    db.execute = AsyncMock(return_value=result)

    release_called = AsyncMock()
    append_called = AsyncMock()

    class FakeBudgetService:
        def __init__(self, _db: object) -> None:
            pass

        release = release_called

    class FakeAuditService:
        def __init__(self, _db: object) -> None:
            pass

        append = append_called

    monkeypatch.setattr("services.hitl_service.BudgetService", FakeBudgetService)
    monkeypatch.setattr("services.hitl_service.AuditService", FakeAuditService)

    service = HiTLService(db)
    count = await service.expire_stale()

    assert count == 1
    assert stale.status == "failed"
    release_called.assert_awaited_once()
    append_called.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_approval_request_emits_webhook_and_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = SimpleNamespace(
        id="org-1",
        approval_url="https://example.com/approval",
        owner_email="owner@example.com",
    )
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = org
    db.execute = AsyncMock(return_value=result)

    webhook_post = AsyncMock(return_value=SimpleNamespace(status_code=200, is_success=True))

    class FakeAsyncClient:
        def __init__(self, timeout: float = 10.0) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, *args, **kwargs):
            return await webhook_post(*args, **kwargs)

    recipients_called = AsyncMock(return_value=["admin@example.com"])
    notify_called = AsyncMock(return_value=None)

    class FakeNotificationService:
        def __init__(self, _db: object) -> None:
            pass

        resolve_org_admin_owner_emails = recipients_called
        notify_hitl_approval_required = notify_called

    monkeypatch.setattr("services.hitl_service.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("services.hitl_service.NotificationService", FakeNotificationService)

    service = HiTLService(db)
    payload = await service.trigger_approval_request(
        delegation_id="deleg-4",
        org_id="org-1",
        reason="threshold_exceeded",
        caller_agent_id="caller-a",
        callee_agent_id="callee-a",
        estimated_cost_usd=1.2,
        context_scope=["deal_metadata"],
    )

    assert payload["event"] == "hil_approval_required"
    webhook_post.assert_awaited_once()
    recipients_called.assert_awaited_once_with(
        org_id="org-1",
        owner_email="owner@example.com",
    )
    notify_called.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_approval_request_ignores_email_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = SimpleNamespace(
        id="org-1",
        approval_url=None,
        owner_email="owner@example.com",
    )
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = org
    db.execute = AsyncMock(return_value=result)

    recipients_called = AsyncMock(return_value=["admin@example.com"])
    notify_called = AsyncMock(side_effect=RuntimeError("provider down"))

    class FakeNotificationService:
        def __init__(self, _db: object) -> None:
            pass

        resolve_org_admin_owner_emails = recipients_called
        notify_hitl_approval_required = notify_called

    monkeypatch.setattr("services.hitl_service.NotificationService", FakeNotificationService)

    service = HiTLService(db)
    payload = await service.trigger_approval_request(
        delegation_id="deleg-5",
        org_id="org-1",
        reason="threshold_exceeded",
    )

    assert payload["status"] == "pending_approval"
    recipients_called.assert_awaited_once()
    notify_called.assert_awaited_once()
