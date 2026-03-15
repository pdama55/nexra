"""Unit tests for services.budget_service — spend tracking and cap enforcement."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.budget_service import BudgetCheckResult, BudgetService


def _make_budget_row(
    cap: float = 100.0,
    spent: float = 0.0,
) -> MagicMock:
    row = MagicMock()
    row.cap_usd = Decimal(str(cap))
    row.spent_usd = Decimal(str(spent))
    return row


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
        """If estimated_cost > request_cap, block immediately."""
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
        """If no daily/monthly budget rows exist, allow the delegation."""
        db = AsyncMock()

        # begin_nested context manager
        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        # Both daily and monthly queries return None
        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = None
        monthly_result = MagicMock()
        monthly_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(side_effect=[daily_result, monthly_result])

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.15,
            request_cap=1.0,
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_daily_cap_exceeded_blocks(self) -> None:
        """If daily spent + estimated > cap, block."""
        db = AsyncMock()

        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        # Daily row: cap=10, spent=9.90 → remaining=0.10
        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = _make_budget_row(cap=10.0, spent=9.90)

        db.execute = AsyncMock(return_value=daily_result)

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.50,
            request_cap=1.0,
        )
        assert result.allowed is False
        assert result.reason == "daily_cap"
        assert result.remaining_usd == pytest.approx(0.10)

    @pytest.mark.asyncio
    async def test_within_budget_allows(self) -> None:
        """If daily has room and monthly has room, allow."""
        db = AsyncMock()

        nested_ctx = AsyncMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=nested_ctx)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)
        db.begin_nested = MagicMock(return_value=nested_ctx)

        daily_result = MagicMock()
        daily_result.scalar_one_or_none.return_value = _make_budget_row(cap=100, spent=10)
        monthly_result = MagicMock()
        monthly_result.scalar_one_or_none.return_value = _make_budget_row(cap=1000, spent=50)

        db.execute = AsyncMock(side_effect=[daily_result, monthly_result])

        service = BudgetService(db)
        result = await service.check_and_reserve(
            org_id=str(uuid.uuid4()),
            agent_id="agent-1",
            estimated_cost=0.15,
            request_cap=1.0,
        )
        assert result.allowed is True
