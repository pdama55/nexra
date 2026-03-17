import asyncio
import json as _json
import logging
import time

import httpx

from core.crypto import sign_webhook_payload
from core.errors import (
    CALLEE_WEBHOOK_FAILED,
    DELEGATION_TIMEOUT,
    WEBHOOK_SIGNATURE_REJECTED,
    NexraError,
)

logger = logging.getLogger("nexra.services.webhook")


class WebhookService:
    """Delivers signed webhooks to callee agents.

    MVP: synchronous HTTPX delivery with single retry on 5xx.
    """

    MAX_TIMEOUT_SECONDS = 30

    async def deliver_and_await(
        self,
        webhook_url: str,
        payload: dict,
        webhook_secret: str,
        delegation_id: str,
        timeout_ms: int,
    ) -> dict:
        """Deliver webhook and await response (synchronous mode).

        Serializes payload with sorted keys and no whitespace to match
        sign_webhook_payload's serialization. Sends as raw bytes via content=,
        NOT json=, to preserve HMAC consistency.
        """
        signature = sign_webhook_payload(payload, webhook_secret)
        effective_timeout = min(timeout_ms / 1000, self.MAX_TIMEOUT_SECONDS - 0.1)

        body_bytes = _json.dumps(
            payload, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-Nexra-Signature": signature,
            "X-Delegation-ID": delegation_id,
            "X-Nexra-Timestamp": str(int(time.time())),
        }

        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            try:
                resp = await client.post(webhook_url, content=body_bytes, headers=headers)
            except httpx.TimeoutException:
                raise NexraError(
                    408, DELEGATION_TIMEOUT,
                    f"Callee did not respond within {timeout_ms}ms",
                )
            except httpx.RequestError as e:
                raise NexraError(
                    503, CALLEE_WEBHOOK_FAILED,
                    f"Webhook delivery failed: {str(e)[:200]}",
                )

            if resp.status_code in (401, 403):
                raise NexraError(
                    503, WEBHOOK_SIGNATURE_REJECTED,
                    "Callee returned 401/403 — likely HMAC mismatch. Not retried.",
                )

            if resp.status_code >= 500:
                logger.warning(f"Webhook returned {resp.status_code}, retrying once...")
                await asyncio.sleep(1)
                try:
                    resp = await client.post(webhook_url, content=body_bytes, headers=headers)
                except (httpx.TimeoutException, httpx.RequestError) as e:
                    raise NexraError(
                        503, CALLEE_WEBHOOK_FAILED,
                        f"Webhook retry failed: {str(e)[:200]}",
                    )

            if not resp.is_success:
                raise NexraError(
                    503, CALLEE_WEBHOOK_FAILED,
                    f"Callee returned {resp.status_code}",
                )

            return resp.json()

    async def enqueue(
        self,
        webhook_url: str,
        payload: dict,
        webhook_secret: str,
        delegation_id: str,
    ) -> None:
        """Queue asynchronous callee webhook delivery."""
        from workers.webhook_worker import deliver_webhook_async

        deliver_webhook_async.delay(
            webhook_url=webhook_url,
            payload=payload,
            webhook_secret=webhook_secret,
            delegation_id=delegation_id,
        )

    async def deliver_callback(
        self,
        callback_url: str,
        payload: dict,
        delegation_id: str,
        timeout_ms: int = 10_000,
    ) -> None:
        """Deliver completion payload to caller callback URL."""
        effective_timeout = max(1.0, timeout_ms / 1000)
        headers = {
            "Content-Type": "application/json",
            "X-Delegation-ID": delegation_id,
            "X-Nexra-Timestamp": str(int(time.time())),
        }
        async with httpx.AsyncClient(timeout=effective_timeout) as client:
            try:
                response = await client.post(callback_url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                raise NexraError(
                    503,
                    CALLEE_WEBHOOK_FAILED,
                    f"Callback delivery failed: {str(exc)[:200]}",
                )

            if not response.is_success:
                raise NexraError(
                    503,
                    CALLEE_WEBHOOK_FAILED,
                    f"Callback endpoint returned {response.status_code}",
                )
