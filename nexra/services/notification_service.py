import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from models.org_member import OrgMember
from models.organization import Organization

logger = logging.getLogger("nexra.services.notifications")


class NotificationService:
    """Best-effort external alert delivery channels."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_org_admin_owner_emails(
        self,
        org_id: str,
        owner_email: str | None = None,
    ) -> list[str]:
        """Resolve notification recipients for an organization.

        Priority: admin member emails first, then owner email fallback.
        """
        member_result = await self.db.execute(
            select(OrgMember.email).where(
                OrgMember.org_id == org_id,
                OrgMember.role == "admin",
            )
        )
        admin_emails = sorted(
            {
                str(email).strip().lower()
                for (email,) in member_result.all()
                if email and str(email).strip()
            }
        )
        if admin_emails:
            return admin_emails

        fallback_owner = owner_email
        if not fallback_owner:
            org_result = await self.db.execute(
                select(Organization.owner_email).where(Organization.id == org_id)
            )
            fallback_owner = org_result.scalar_one_or_none()

        if fallback_owner and str(fallback_owner).strip():
            return [str(fallback_owner).strip().lower()]

        settings = get_settings()
        if settings.anomaly_email_recipients:
            return [
                part.strip().lower()
                for part in settings.anomaly_email_recipients.split(",")
                if part.strip()
            ]

        return []

    async def send_email(
        self,
        recipients: list[str],
        subject: str,
        body: str,
    ) -> bool:
        settings = get_settings()
        if not recipients:
            return False
        if not settings.sendgrid_api_key:
            logger.info("Email notification skipped: sendgrid_api_key not configured")
            return False

        payload: dict[str, Any] = {
            "personalizations": [{"to": [{"email": email} for email in recipients]}],
            "from": {"email": settings.notification_email_from},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        headers = {
            "Authorization": f"Bearer {settings.sendgrid_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.sendgrid_base_url.rstrip('/')}/v3/mail/send",
                    json=payload,
                    headers=headers,
                )
            if response.is_success:
                return True
            logger.warning(
                "Email notification failed with status %s",
                response.status_code,
            )
            return False
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("Email notification delivery error: %s", exc)
            return False

    async def send_slack_message(self, text: str, payload: dict[str, Any]) -> bool:
        settings = get_settings()
        if not settings.anomaly_slack_webhook_url:
            return False
        body = {"text": text, "payload": payload}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(settings.anomaly_slack_webhook_url, json=body)
            if response.is_success:
                return True
            logger.warning("Slack webhook failed with status %s", response.status_code)
            return False
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("Slack webhook delivery error: %s", exc)
            return False

    async def send_pagerduty_event(
        self,
        summary: str,
        source: str,
        severity: str,
        custom_details: dict[str, Any],
    ) -> bool:
        settings = get_settings()
        routing_key = settings.anomaly_pagerduty_routing_key
        if not routing_key:
            return False
        events_base_url = settings.pagerduty_events_base_url.rstrip("/")

        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": summary,
                "source": source,
                "severity": severity,
                "custom_details": custom_details,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{events_base_url}/v2/enqueue",
                    json=payload,
                )
            if response.is_success:
                return True
            logger.warning("PagerDuty event failed with status %s", response.status_code)
            return False
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("PagerDuty event delivery error: %s", exc)
            return False

    async def notify_hitl_approval_required(
        self,
        recipients: list[str],
        event_payload: dict[str, Any],
    ) -> None:
        body = (
            "Nexra delegation is pending human approval.\n\n"
            f"Delegation ID: {event_payload.get('delegation_id')}\n"
            f"Reason: {event_payload.get('reason')}\n"
            f"Approval deadline: {event_payload.get('approval_deadline')}\n"
            f"Approve URL: {event_payload.get('approval_url')}\n"
            f"Reject URL: {event_payload.get('reject_url')}\n"
            f"Context scope: {event_payload.get('context_scope', [])}\n"
        )
        try:
            await self.send_email(
                recipients,
                subject="[Nexra] Approval required for delegation",
                body=body,
            )
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("HiTL email notification failed: %s", exc)

    async def notify_spend_anomaly(
        self,
        recipients: list[str],
        anomaly: dict[str, Any],
    ) -> None:
        summary = (
            f"Anomaly detected for agent {anomaly.get('agent_id')} "
            f"(org {anomaly.get('org_id')}): current hourly spend {anomaly.get('current_hour_spend')} "
            f"exceeds threshold {anomaly.get('threshold')}"
        )
        body = f"{summary}\n\n{json.dumps(anomaly, indent=2, sort_keys=True)}"

        # Channel failures are isolated and must never block anomaly handling.
        try:
            await self.send_email(
                recipients,
                subject="[Nexra] Spend anomaly detected",
                body=body,
            )
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("Anomaly email notification failed: %s", exc)
        try:
            await self.send_slack_message(summary, anomaly)
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("Anomaly Slack notification failed: %s", exc)
        try:
            await self.send_pagerduty_event(
                summary=summary,
                source="nexra.anomaly",
                severity="warning",
                custom_details=anomaly,
            )
        except Exception as exc:  # pragma: no cover - defensive non-blocking path
            logger.warning("Anomaly PagerDuty notification failed: %s", exc)
