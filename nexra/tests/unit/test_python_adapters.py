"""Compatibility tests for Python SDK adapters against current client contract."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SDK_ROOT = Path(__file__).resolve().parents[2] / "sdk" / "nexra-py"
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from nexra_sdk.adapters.bedrock import BedrockNexraBridge  # noqa: E402
from nexra_sdk.adapters.crewai import NexraDiscoverTool, NexraTool  # noqa: E402
from nexra_sdk.adapters.langgraph import nexra_discover_tool, nexra_tool  # noqa: E402


@pytest.mark.asyncio
async def test_crewai_tools_call_client_contract() -> None:
    class FakeClient:
        async def delegate(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["agent_id"] == "callee-1"
            return SimpleNamespace(delegation_id="d1", status="completed", result={"ok": True})

        async def discover(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["query"] == "research"
            return [SimpleNamespace(agent_id="a1", name="A1", match_score=0.9, trust_score=0.8)]

    client = FakeClient()
    delegate_tool = NexraTool(client)
    discover_tool = NexraDiscoverTool(client)

    delegated = await delegate_tool._arun("callee-1", {"task": "x"})
    discovered = await discover_tool._arun("research", limit=1)

    assert delegated["delegation_id"] == "d1"
    assert discovered[0]["agent_id"] == "a1"


@pytest.mark.asyncio
async def test_langgraph_tools_call_client_contract() -> None:
    class FakeClient:
        async def delegate(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["agent_id"] == "callee-2"
            return SimpleNamespace(delegation_id="d2", status="completed", result={"ok": True})

        async def discover(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["query"] == "analysis"
            return [SimpleNamespace(agent_id="a2", name="A2", match_score=0.91, trust_score=0.89)]

    client = FakeClient()
    delegate_fn = nexra_tool(client)
    discover_fn = nexra_discover_tool(client)

    delegated = await delegate_fn("callee-2", {"task": "x"})
    discovered = await discover_fn("analysis", limit=1)

    assert delegated["delegation_id"] == "d2"
    assert discovered[0]["agent_id"] == "a2"


@pytest.mark.asyncio
async def test_bedrock_bridge_maps_discover_and_delegate_paths() -> None:
    class FakeClient:
        async def discover(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["query"] == "find callee"
            return [SimpleNamespace(agent_id="a3", name="A3", match_score=0.87)]

        async def delegate(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["agent_id"] == "callee-3"
            return SimpleNamespace(delegation_id="d3", status="completed", result={"ok": True})

    bridge = BedrockNexraBridge(FakeClient())

    discover_event = {
        "apiPath": "/discover",
        "parameters": [{"name": "query", "value": "find callee"}],
        "requestBody": {"content": {"application/json": {}}},
    }
    delegate_event = {
        "apiPath": "/delegate",
        "parameters": [],
        "requestBody": {
            "content": {
                "application/json": {
                    "agent_id": "callee-3",
                    "task": {"task": "hello"},
                }
            }
        },
    }

    discover_resp = await bridge.handle_action_group(discover_event)
    delegate_resp = await bridge.handle_action_group(delegate_event)

    assert discover_resp["response"]["httpStatusCode"] == 200
    assert delegate_resp["response"]["httpStatusCode"] == 200
