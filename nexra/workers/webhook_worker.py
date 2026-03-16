import asyncio
import json
import logging

import httpx

from core.crypto import sign_webhook_payload
from workers.celery_app import celery_app

logger = logging.getLogger("nexra.workers.webhook")

DLQ_MAX_RETRIES = 3


class NonRetryableWebhookError(Exception):
    """Raised for webhook responses that must not be retried."""


@celery_app.task(bind=True, max_retries=DLQ_MAX_RETRIES, default_retry_delay=2)
def deliver_webhook_async(
    self,
    webhook_url: str,
    payload: dict,
    webhook_secret: str,
    delegation_id: str,
):
    """Async webhook delivery with exponential backoff.

    Retries up to 5 times. After exhaustion, logs to DLQ (dead letter queue).
    """
    try:
        asyncio.run(
            _deliver(webhook_url, payload, webhook_secret, delegation_id)
        )
    except NonRetryableWebhookError as exc:
        logger.error(
            "Webhook delivery non-retryable failure for %s: %s",
            delegation_id,
            exc,
        )
    except Exception as exc:
        backoff = min(2 * (2 ** self.request.retries), 30)
        logger.warning(
            f"Webhook delivery failed for {delegation_id}, "
            f"retry {self.request.retries + 1}/{DLQ_MAX_RETRIES} in {backoff}s: {exc}"
        )
        try:
            raise self.retry(exc=exc, countdown=backoff)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Webhook DLQ: delegation {delegation_id} to {webhook_url} "
                f"failed after {DLQ_MAX_RETRIES} retries"
            )


async def _deliver(
    webhook_url: str, payload: dict, webhook_secret: str, delegation_id: str
):
    signature = sign_webhook_payload(payload, webhook_secret)
    body_bytes = json.dumps(
        payload, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Nexra-Signature": signature,
        "X-Delegation-ID": delegation_id,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(webhook_url, content=body_bytes, headers=headers)
        if resp.status_code in (401, 403):
            raise NonRetryableWebhookError(
                f"received {resp.status_code}; stopping retries"
            )
        resp.raise_for_status()
