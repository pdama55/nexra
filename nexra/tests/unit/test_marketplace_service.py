"""Unit tests for MarketplaceService payout settlement behavior."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.marketplace_service import MarketplaceService


class _ScalarsAllResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def scalars(self) -> "_ScalarsAllResult":
        return self

    def all(self) -> list[object]:
        return self._items


class _ScalarOneResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _ImmediateLoop:
    async def run_in_executor(self, _executor: object, fn):  # type: ignore[no-untyped-def]
        return fn()


@pytest.mark.asyncio
async def test_settle_pending_payouts_applies_80_20_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payout = SimpleNamespace(
        id=uuid.uuid4(),
        status="pending",
        amount_usd=Decimal("10.00"),
        callee_org_id=uuid.uuid4(),
        delegation_id=uuid.uuid4(),
        stripe_transfer_id=None,
        settled_at=None,
    )
    callee_org = SimpleNamespace(
        id=payout.callee_org_id,
        stripe_connect_account_id="acct_123",
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsAllResult([payout]),
            _ScalarOneResult(callee_org),
        ]
    )
    db.commit = AsyncMock()

    monkeypatch.setattr(
        "services.marketplace_service.get_settings",
        lambda: SimpleNamespace(stripe_secret_key="sk_test"),
    )
    monkeypatch.setattr(
        "services.marketplace_service.asyncio.get_running_loop",
        lambda: _ImmediateLoop(),
    )
    transfer_create = MagicMock(return_value=SimpleNamespace(id="tr_123"))
    monkeypatch.setattr(
        "services.marketplace_service.stripe.Transfer.create",
        transfer_create,
    )

    service = MarketplaceService(db)
    settled = await service.settle_pending_payouts()

    assert settled == 1
    assert payout.status == "settled"
    assert payout.stripe_transfer_id == "tr_123"
    assert isinstance(payout.settled_at, datetime)
    assert payout.settled_at.tzinfo is not None
    transfer_create.assert_called_once()
    assert transfer_create.call_args.kwargs["amount"] == 800
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_settle_pending_payouts_skips_without_connect_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payout = SimpleNamespace(
        id=uuid.uuid4(),
        status="pending",
        amount_usd=Decimal("4.00"),
        callee_org_id=uuid.uuid4(),
        delegation_id=uuid.uuid4(),
        stripe_transfer_id=None,
        settled_at=None,
    )
    callee_org = SimpleNamespace(
        id=payout.callee_org_id,
        stripe_connect_account_id=None,
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _ScalarsAllResult([payout]),
            _ScalarOneResult(callee_org),
        ]
    )
    db.commit = AsyncMock()

    monkeypatch.setattr(
        "services.marketplace_service.get_settings",
        lambda: SimpleNamespace(stripe_secret_key="sk_test"),
    )
    monkeypatch.setattr(
        "services.marketplace_service.asyncio.get_running_loop",
        lambda: _ImmediateLoop(),
    )
    transfer_create = MagicMock()
    monkeypatch.setattr(
        "services.marketplace_service.stripe.Transfer.create",
        transfer_create,
    )

    service = MarketplaceService(db)
    settled = await service.settle_pending_payouts()

    assert settled == 0
    assert payout.status == "pending"
    transfer_create.assert_not_called()
    db.commit.assert_awaited_once()
