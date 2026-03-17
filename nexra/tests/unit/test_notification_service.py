"""Unit tests for NotificationService alert channels and fallbacks."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.notification_service import NotificationService


class _FakeAsyncClient:
    def __init__(self, post_impl: AsyncMock) -> None:
        self._post_impl = post_impl

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs):
        return await self._post_impl(*args, **kwargs)


@pytest.mark.asyncio
async def test_send_email_returns_false_when_provider_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    service = NotificationService(db)

    monkeypatch.setattr(
        "services.notification_service.get_settings",
        lambda: SimpleNamespace(
            sendgrid_api_key=None,
            sendgrid_base_url="https://api.sendgrid.com",
            notification_email_from="noreply@nexra.local",
            anomaly_slack_webhook_url=None,
            anomaly_pagerduty_routing_key=None,
            anomaly_email_recipients=None,
        ),
    )

    ok = await service.send_email(
        recipients=["admin@example.com"],
        subject="Test",
        body="body",
    )
    assert ok is False


@pytest.mark.asyncio
async def test_send_email_returns_true_on_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    service = NotificationService(db)

    monkeypatch.setattr(
        "services.notification_service.get_settings",
        lambda: SimpleNamespace(
            sendgrid_api_key="sg-test",
            sendgrid_base_url="https://api.sendgrid.com",
            notification_email_from="noreply@nexra.local",
            anomaly_slack_webhook_url=None,
            anomaly_pagerduty_routing_key=None,
            anomaly_email_recipients=None,
        ),
    )

    post_impl = AsyncMock(return_value=SimpleNamespace(is_success=True, status_code=202))
    monkeypatch.setattr(
        "services.notification_service.httpx.AsyncClient",
        lambda timeout=10.0: _FakeAsyncClient(post_impl),
    )

    ok = await service.send_email(
        recipients=["admin@example.com"],
        subject="Test",
        body="body",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_notify_spend_anomaly_isolates_channel_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    service = NotificationService(db)

    send_email = AsyncMock(side_effect=RuntimeError("email down"))
    send_slack = AsyncMock(side_effect=RuntimeError("slack down"))
    send_pagerduty = AsyncMock(side_effect=RuntimeError("pagerduty down"))

    monkeypatch.setattr(service, "send_email", send_email)
    monkeypatch.setattr(service, "send_slack_message", send_slack)
    monkeypatch.setattr(service, "send_pagerduty_event", send_pagerduty)

    await service.notify_spend_anomaly(
        recipients=["admin@example.com"],
        anomaly={
            "agent_id": "agent-1",
            "org_id": "org-1",
            "current_hour_spend": 9.2,
            "threshold": 1.3,
        },
    )

    send_email.assert_awaited_once()
    send_slack.assert_awaited_once()
    send_pagerduty.assert_awaited_once()
