"""Unit tests for webhook worker retry semantics."""

import pytest

from workers.webhook_worker import NonRetryableWebhookError, _deliver


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http status {self.status_code}")


@pytest.mark.asyncio
async def test_deliver_401_is_non_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        async def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return _FakeResponse(401)

    monkeypatch.setattr("workers.webhook_worker.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(NonRetryableWebhookError):
        await _deliver(
            "https://example.com/webhook",
            {"hello": "world"},
            "a" * 32,
            "deleg-1",
        )


@pytest.mark.asyncio
async def test_deliver_success_posts_signed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {"called": False, "headers": None}

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        async def post(self, _url: str, content: bytes, headers: dict):  # type: ignore[no-untyped-def]
            captured["called"] = True
            captured["headers"] = headers
            assert content
            return _FakeResponse(200)

    monkeypatch.setattr("workers.webhook_worker.httpx.AsyncClient", FakeAsyncClient)

    await _deliver(
        "https://example.com/webhook",
        {"k": "v"},
        "b" * 32,
        "deleg-2",
    )

    assert captured["called"] is True
    headers = captured["headers"] or {}
    assert headers.get("X-Nexra-Signature")
    assert headers.get("X-Delegation-ID") == "deleg-2"
