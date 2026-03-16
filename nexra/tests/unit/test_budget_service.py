"""Unit tests for services.budget_service — reserve/settle/release invariants."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.budget_service import BudgetCheckResult, BudgetService


def _make_budget_row(cap: float = 100.0, spent: float = 0.0) -> MagicMock:
    row = MagicMock()
    row.cap_usd = Decimal(str(cap))
    row.spent_usd = Decimal(str(spent))
    return row


def _scalar_result(value: float) -> MagicMock:
    result = MagicMock()
    result.scalar.return_value = Decimal(str(value))
    return result


class TestBudgetCheckResult:
    def test_allowed_result(self) -> None:
        r = BudgetCheckResult(allowed=True, reason="", remaining_usd=9.85)
        assert r.allowed is True
        assert r.remaining_usd == pytest.approx(9.85)

    def test_blocked_result(self) -> None:
        r = BudgetCheckResult(allowed=False, reason="daily_cap", remaining_usd=0.50)
        assert r.allowed is False
        assert r.reason == "daily_cap"


class TestBudgetServiceCheck:
    @pytest.mark.asyncio
    async def test_per_delegation_cap_blocks(self) -> None:
        db = AsyncMock()
        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=5.0,
            request_cap=1.0,
        )
        assert result.allowed is False
        assert result.reason == "per_delegation_cap"

    @pytest.mark.asyncio
    async def test_no_budget_rows_allows(self) -> None:
        db = AsyncMock()
        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = None
        monthly_result = MagicMock()
        monthly_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(
            side_effect=[
                _scalar_result(0),  # outstanding reserved
                daily_result,
                monthly_result,
            ]
        )

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.15,
            request_cap=1.0,
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_daily_cap_exceeded_considers_outstanding_reserves(self) -> None:
        db = AsyncMock()
        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = _make_budget_row(cap=10.0, spent=9.0)

        db.execute = AsyncMock(
            side_effect=[
                _scalar_result(0.9),  # outstanding reserved
                daily_result,
            ]
        )

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.2,
            request_cap=1.0,
        )
        assert result.allowed is False
        assert result.reason == "daily_cap"
        assert result.remaining_usd == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_within_budget_allows(self) -> None:
        db = AsyncMock()
        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = _make_budget_row(cap=100, spent=10)
        monthly_result = MagicMock()
        monthly_result.scalar_one_or_none.return_value = _make_budget_row(cap=1000, spent=50)

        db.execute = AsyncMock(
            side_effect=[
                _scalar_result(0),
                daily_result,
                monthly_result,
            ]
        )

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.15,
            request_cap=1.0,
        )
        assert result.allowed is True


class TestBudgetServiceSettlement:
    @pytest.mark.asyncio
    async def test_settle_releases_unused_amount(self) -> None:
        db = AsyncMock()
        service = BudgetService(db)

        reservation = MagicMock()
        reservation.reserved_usd = Decimal("1.0000")
        reservation.settled_usd = Decimal("0.0000")
        reservation.released_usd = Decimal("0.0000")
        reservation.state = "reserved"

        service._get_reservation_for_update = AsyncMock(return_value=reservation)  # type: ignore[attr-defined]
        service._apply_spend = AsyncMock()  # type: ignore[attr-defined]
        service._assert_invariant = AsyncMock()  # type: ignore[attr-defined]

        await service.settle("org-1", "agent-1", "deleg-1", 0.25)

        assert reservation.settled_usd == Decimal("0.2500")
        assert reservation.released_usd == Decimal("0.7500")
        assert reservation.state == "adjusted"
        service._apply_spend.assert_awaited_once_with("org-1", "agent-1", 0.25)  # type: ignore[attr-defined]
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_release_marks_reservation_released(self) -> None:
        db = AsyncMock()
        service = BudgetService(db)

        reservation = MagicMock()
        reservation.reserved_usd = Decimal("0.5000")
        reservation.settled_usd = Decimal("0.0000")
        reservation.released_usd = Decimal("0.0000")
        reservation.state = "reserved"

        service._get_reservation_for_update = AsyncMock(return_value=reservation)  # type: ignore[attr-defined]
        service._assert_invariant = AsyncMock()  # type: ignore[attr-defined]

        await service.release("org-1", "agent-1", "deleg-1")

        assert reservation.released_usd == Decimal("0.5000")
        assert reservation.state == "released"
        db.commit.assert_awaited_once()
