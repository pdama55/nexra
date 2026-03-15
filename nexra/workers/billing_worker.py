import logging

import stripe

from core.config import get_settings
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.billing")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def record_stripe_usage(
    self, stripe_customer_id: str, delegation_id: str, timestamp: int
):
    """Background task to record Stripe meter event.

    Retries up to 3 times with 5s delay on failure.
    """
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    try:
        stripe.billing.MeterEvent.create(
            event_name="nexra_delegation",
            payload={
                "stripe_customer_id": stripe_customer_id,
                "value": "1",
            },
            timestamp=timestamp,
        )
        logger.info(f"Stripe usage recorded for delegation {delegation_id}")
    except stripe.StripeError as exc:
        logger.error(f"Stripe error: {exc}")
        raise self.retry(exc=exc)
