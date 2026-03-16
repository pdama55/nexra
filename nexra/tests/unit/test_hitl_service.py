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
        await service.approve("deleg-1", "org-1", "admin")
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
    result = await service.reject("deleg-2", "org-1", "admin", "denied")

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
    assert stale.status == "blocked"
    release_called.assert_awaited_once()
    append_called.assert_awaited_once()
