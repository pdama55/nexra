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
        """Stripe Connect transfer stub. Full implementation in Phase 13."""
        logger.info(
            f"Connect payout stub: ${amount_usd:.4f} to org {callee_org.id} "
            f"for delegation {delegation.id}"
        )
