"""Contract-focused tests for Python SDK endpoint usage and envelope parsing."""

import sys
from pathlib import Path
from typing import Any

import pytest

SDK_ROOT = Path(__file__).resolve().parents[2] / "sdk" / "nexra-py"
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from nexra_sdk.client import NexraAPIError, NexraClient  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if not self.is_success:
            raise RuntimeError(f"http {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, responses: dict[tuple[str, str], _FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any]) -> _FakeResponse:
        self.calls.append({"method": "POST", "url": url, "json": json})
        return self.responses[("POST", url)]

    async def get(self, url: str) -> _FakeResponse:
        self.calls.append({"method": "GET", "url": url})
        return self.responses[("GET", url)]

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_sdk_uses_control_plane_paths_and_parses_data_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "http://localhost:8000/v1"
    responses = {
        ("POST", f"{base_url}/agents/register"): _FakeResponse(
            200,
            {"data": {"agent_id": "a1", "status": "probationary", "embedding_id": "emb-1", "registered_at": "2026-01-01T00:00:00Z"}},
        ),
        ("POST", f"{base_url}/capabilities/discover"): _FakeResponse(
            200,
            {"data": {"matches": [{"agent_id": "callee-1", "name": "Callee", "match_score": 0.9, "trust_score": 0.95, "status": "active"}]}},
        ),
        ("POST", f"{base_url}/delegate"): _FakeResponse(
            200,
            {"data": {"delegation_id": "d1", "status": "completed", "result": {"ok": True}}},
        ),
        ("GET", f"{base_url}/delegations/d1"): _FakeResponse(
            200,
            {"data": {"delegation_id": "d1", "status": "completed", "result": {"ok": True}}},
        ),
    }
    fake_client = _FakeAsyncClient(responses)

    monkeypatch.setattr(
        "nexra_sdk.client.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )

    client = NexraClient(api_key="nx_test", agent_id="agent-x", base_url=base_url)
    register = await client.register(
        agent_id="agent-x",
        name="Agent X",
        description="desc",
        capability_type="research",
        input_schema={},
        output_schema={},
        pricing={"per_call_usd": 0.1},
        sla={"p99_latency_ms": 1000, "availability": 0.99},
        webhook_url="https://example.com/hook",
        webhook_secret="a" * 32,
    )
    matches = await client.discover(query="analysis", limit=1)
    delegation = await client.delegate(agent_id="callee-1", task={"q": "hello"})
    delegation_status = await client.get_delegation("d1")

    assert register.agent_id == "a1"
    assert matches[0].agent_id == "callee-1"
    assert delegation.delegation_id == "d1"
    assert delegation_status.status == "completed"

    called_urls = [call["url"] for call in fake_client.calls]
    assert f"{base_url}/agents/register" in called_urls
    assert f"{base_url}/capabilities/discover" in called_urls
    assert f"{base_url}/delegate" in called_urls
    assert f"{base_url}/delegations/d1" in called_urls


@pytest.mark.asyncio
async def test_sdk_maps_error_envelope_to_nexra_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "http://localhost:8000/v1"
    responses = {
        ("POST", f"{base_url}/agents/register"): _FakeResponse(
            403,
            {"error": {"code": "POLICY_BLOCKED", "message": "blocked"}},
        ),
    }
    fake_client = _FakeAsyncClient(responses)
    monkeypatch.setattr(
        "nexra_sdk.client.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )

    client = NexraClient(api_key="nx_test", agent_id="agent-x", base_url=base_url)
    with pytest.raises(NexraAPIError) as exc:
        await client.register(
            agent_id="agent-x",
            name="Agent X",
            description="desc",
            capability_type="research",
            input_schema={},
            output_schema={},
            pricing={"per_call_usd": 0.1},
            sla={"p99_latency_ms": 1000, "availability": 0.99},
            webhook_url="https://example.com/hook",
            webhook_secret="a" * 32,
        )

    assert exc.value.code == "POLICY_BLOCKED"
