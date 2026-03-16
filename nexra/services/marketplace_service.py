import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.delegation import Delegation
from models.organization import Organization
from models.pending_payout import PendingPayout

logger = logging.getLogger("nexra.services.marketplace")


class MarketplaceService:
    """Stripe Connect marketplace settlement for cross-org delegations."""

    PLATFORM_FEE_RATE = Decimal("0.20")  # 20% platform fee

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key

    async def create_pending_payout(
        self, delegation: Delegation, callee_org_id: str, amount_usd: float
    ) -> PendingPayout:
        payout = PendingPayout(
            org_id=delegation.caller_org_id,
            delegation_id=delegation.id,
            callee_org_id=uuid.UUID(callee_org_id),
            amount_usd=Decimal(str(amount_usd)),
            status="pending",
        )
        self.db.add(payout)
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def settle_pending_payouts(self) -> int:
        """Settle all pending payouts via Stripe Connect transfers."""
        result = await self.db.execute(
            select(PendingPayout).where(PendingPayout.status == "pending")
        )
        payouts = list(result.scalars().all())
        settled = 0

        for payout in payouts:
            org_result = await self.db.execute(
                select(Organization).where(Organization.id == payout.callee_org_id)
            )
            callee_org = org_result.scalar_one_or_none()
            if not callee_org or not callee_org.stripe_connect_account_id:
                logger.warning(f"Skipping payout {payout.id}: no Connect account")
                continue

            net_amount = float(payout.amount_usd) * (1 - float(self.PLATFORM_FEE_RATE))
            amount_cents = int(net_amount * 100)

            if amount_cents <= 0:
                continue

            try:
                loop = asyncio.get_running_loop()
                dest = callee_org.stripe_connect_account_id
                meta = {"delegation_id": str(payout.delegation_id)}
                transfer = await loop.run_in_executor(
                    None,
                    lambda ac=amount_cents, d=dest, m=meta: stripe.Transfer.create(
                        amount=ac,
                        currency="usd",
                        destination=d,
                        metadata=m,
                    ),
                )
                payout.status = "settled"
                payout.stripe_transfer_id = transfer.id
                payout.settled_at = datetime.now(timezone.utc)
                settled += 1
            except stripe.StripeError as e:
                logger.error(f"Stripe transfer failed for payout {payout.id}: {e}")
                payout.status = "failed"

        if payouts:
            await self.db.commit()

        return settled

    async def initiate_connect_onboarding(self, org: Organization) -> str:
        """Create a Stripe Connect Express account and return onboarding URL."""
        loop = asyncio.get_running_loop()
        account = await loop.run_in_executor(
            None,
            lambda: stripe.Account.create(
                type="express",
                metadata={"nexra_org_id": str(org.id)},
            ),
        )

        org.stripe_connect_account_id = account.id
        await self.db.commit()

        settings = get_settings()
        link = await loop.run_in_executor(
            None,
            lambda: stripe.AccountLink.create(
                account=account.id,
                refresh_url=f"{settings.api_base_url}/v1/marketplace/connect-refresh",
                return_url=f"{settings.api_base_url}/v1/marketplace/connect-complete",
                type="account_onboarding",
            ),
        )
        return link.url
