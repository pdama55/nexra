import asyncio
import logging

import stripe

from core.config import get_settings
from models.delegation import Delegation
from models.organization import Organization

logger = logging.getLogger("nexra.services.billing")


class BillingService:
    """Stripe billing integration.

    Records usage events via Stripe Metering API after each delegation.
    Billing failures are fire-and-forget — they never block delegation responses.
    """

    def __init__(self) -> None:
        settings = get_settings()
        stripe.api_key = settings.stripe_secret_key
        self.meter_id = settings.stripe_delegation_meter_id

    async def record_delegation_usage(
        self,
        org: Organization,
        delegation: Delegation,
        actual_cost_usd: float,
    ) -> None:
        if not org.stripe_id:
            logger.warning(f"Org {org.id} has no stripe_id — skipping billing")
            return

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: stripe.billing.MeterEvent.create(
                    event_name="nexra_delegation",
                    payload={
                        "stripe_customer_id": org.stripe_id,
                        "value": "1",
                    },
                    timestamp=int(delegation.created_at.timestamp()),
                ),
            )
            logger.info(f"Stripe usage event recorded for delegation {delegation.id}")
        except stripe.StripeError as e:
            logger.error(f"Stripe billing error for delegation {delegation.id}: {e}")

    async def trigger_connect_payout(
        self,
        callee_org: Organization,
        amount_usd: float,
        delegation: Delegation,
    ) -> None:
        """Attempt immediate Stripe Connect transfer for a settled delegation."""
        if amount_usd <= 0:
            return

        destination = getattr(callee_org, "stripe_connect_account_id", None)
        if not destination:
            logger.warning(
                "Org %s has no stripe_connect_account_id; payout deferred",
                callee_org.id,
            )
            return

        amount_cents = int(round(amount_usd * 100))
        if amount_cents <= 0:
            return

        try:
            loop = asyncio.get_running_loop()
            transfer = await loop.run_in_executor(
                None,
                lambda: stripe.Transfer.create(
                    amount=amount_cents,
                    currency="usd",
                    destination=destination,
                    metadata={"delegation_id": str(delegation.id)},
                ),
            )
            logger.info(
                "Stripe Connect payout created for delegation %s (transfer=%s)",
                delegation.id,
                transfer.id,
            )
        except stripe.StripeError as e:
            logger.error(
                "Stripe Connect payout failed for delegation %s: %s",
                delegation.id,
                e,
            )
