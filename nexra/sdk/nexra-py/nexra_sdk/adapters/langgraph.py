"""LangGraph adapter for Nexra SDK.

Provides tool functions compatible with LangGraph's tool interface.
"""
from typing import Any

from nexra_sdk.client import NexraClient


def nexra_tool(client: NexraClient):
    """Create a LangGraph-compatible tool for delegating tasks via Nexra.

    Usage with LangGraph:
        from nexra_sdk.adapters.langgraph import nexra_tool
        tool = nexra_tool(client)
        # Use in LangGraph node
    """
    async def delegate(
        agent_id: str,
        task: dict,
        budget_cap: float = 1.0,
        context_scope: list[str] | None = None,
    ) -> dict:
        """Delegate a task to an agent via Nexra."""
        result = await client.delegate(
            agent_id=agent_id,
            task=task,
            context_scope=context_scope,
            budget_cap=budget_cap,
        )
        return {
            "delegation_id": result.delegation_id,
            "status": result.status,
            "result": result.result,
        }

    delegate.__name__ = "nexra_delegate"
    delegate.__doc__ = "Delegate a task to an AI agent via Nexra governance layer"
    return delegate


def nexra_discover_tool(client: NexraClient):
    """Create a LangGraph-compatible tool for discovering agents via Nexra."""
    async def discover(query: str, limit: int = 5) -> list[dict]:
        """Discover agent capabilities via semantic search."""
        matches = await client.discover(query=query, limit=limit)
        return [
            {
                "agent_id": m.agent_id,
                "name": m.name,
                "match_score": m.match_score,
                "trust_score": m.trust_score,
            }
            for m in matches
        ]

    discover.__name__ = "nexra_discover"
    discover.__doc__ = "Discover AI agent capabilities via Nexra semantic search"
    return discover
